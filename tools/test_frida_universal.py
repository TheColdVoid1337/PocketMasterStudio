"""Offline contract tests for universal tools/frida_capture.py (no Frida required)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import frida_capture as core
import frida_guarded as guarded

STAGE48=HERE.parent/"research"/"htkpa"/"stages"/"stage48"/"frida.json"
STAGE49=HERE.parent/"research"/"htkpa"/"stages"/"stage49"/"frida.json"

class UniversalFridaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=json.loads(STAGE48.read_text(encoding="utf-8"))
        cls.cfg=core.validate(cls.raw)

    def test_stage48_single_guarded_site(self):
        self.assertEqual(self.cfg["mode"],"guarded_metadata")
        self.assertEqual(len(self.cfg["sites"]),1)
        self.assertEqual(self.cfg["sites"][0]["rva"],0x1190c)
        self.assertEqual(self.cfg["sites"][0]["guard"]["vtable_rva"],0x245170)
        self.assertEqual(self.cfg["sha256"],
            "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")

    def test_stage48_json_executable_and_clo_paths(self):
        self.assertEqual(self.cfg["lifecycle"]["start"],"fresh")
        self.assertEqual(self.cfg["lifecycle"]["close"],"if_launched")
        self.assertTrue(self.cfg["lifecycle"]["executable"].endswith(".exe"))
        self.assertEqual(self.cfg["completion"]["path"],
            "C:/Users/TheColdVoid/AppData/Roaming/Sonicake/Sonicake Manager")

    def test_guarded_lifecycle_invalid_paths_and_controls(self):
        changes=[
            lambda c:c["lifecycle"].update(executable="../unsafe.exe"),
            lambda c:c["lifecycle"].update(executable="C:/bad/../escape.exe"),
            lambda c:c["lifecycle"].update(executable=""),
            lambda c:c["lifecycle"].update(start="force_kill_all"),
            lambda c:c["lifecycle"].update(close="kill_any_pid"),
            lambda c:c["lifecycle"].update(close_timeout_seconds=0),
            lambda c:c["completion"].update(path="../relative"),
            lambda c:c["completion"].update(path="C:/bad/../escape"),
            lambda c:c["completion"].update(appdata_subdir="also/ambiguous"),
        ]
        for i,fn in enumerate(changes):
            with self.subTest(case=i):
                copy_config=copy.deepcopy(self.raw)
                fn(copy_config)
                with self.assertRaises((ValueError,TypeError,KeyError)):
                    core.validate(copy_config)

    def test_managed_launch_refuses_existing_and_starts_only_its_own(self):
        config=self.cfg
        logs=[]
        class FakeDevice:
            def __init__(self,processes):self.processes=processes;self.spawned=[]
            def enumerate_processes(self):return self.processes
            def spawn(self,argv):
                self.spawned.append(argv)
                return 14777
        existing=FakeDevice([SimpleNamespace(name="Sonicake Manager.exe",pid=14000)])
        with self.assertRaises(ValueError):
            guarded.launch_target(existing,SimpleNamespace(pid=None),
                config,lambda *x:logs.append(x),{})
        self.assertEqual(existing.spawned,[])
        no_processes=FakeDevice([])
        state={}
        with patch("frida_guarded.Path.is_file",return_value=True):
            pid,owned=guarded.launch_target(no_processes,SimpleNamespace(pid=None),
                config,lambda *x:logs.append(x),state)
        self.assertEqual(pid,14777)
        self.assertTrue(owned)
        self.assertTrue(state["launched_by_tool"])
        self.assertFalse(state["target_resumed"])
        self.assertEqual(len(no_processes.spawned),1)

    def test_close_only_owned_and_graceful(self):
        config=self.cfg
        class FakeDevice:
            def __init__(self):self.killed=[]
            def kill(self,pid):self.killed.append(pid)
        d=FakeDevice()
        nonowned={"launched_by_tool":False}
        guarded.close_owned_target(d,14000,nonowned,config,lambda *x:None)
        self.assertEqual(nonowned["cleanup_status"],"NOT_OWNED_OR_DISABLED")
        self.assertEqual(d.killed,[])
        suspended={"launched_by_tool":True,"target_resumed":False}
        with patch("frida_guarded.process_exists",return_value=True):
            guarded.close_owned_target(d,14001,suspended,config,lambda *x:None)
        self.assertEqual(suspended["cleanup_status"],"KILLED_OWN_SUSPENDED_TARGET")
        self.assertEqual(d.killed,[14001])
        running={"launched_by_tool":True,"target_resumed":True}
        with patch("frida_guarded.process_exists",side_effect=[True,False]), \
             patch("frida_guarded.request_graceful_close_windows",return_value=1):
            guarded.close_owned_target(d,14002,running,config,lambda *x:None)
        self.assertEqual(running["cleanup_status"],"CLOSED_GRACEFULLY")
        self.assertEqual(d.killed,[14001])

    def test_owned_gui_close_comes_before_binary_unload_after_stable_clo(self):
        cfg=core.validate(json.loads(STAGE49.read_text(encoding="utf-8")))
        events=[]
        report=lambda *args:events.append(("log",args[0],args[1:]))
        class Script:
            def unload(self):events.append(("script_unload",))
        class Session:
            def detach(self):events.append(("session_detach",))
        state={"launched_by_tool":True,"target_resumed":True,
               "runtime_verified":True,"hook_attached":True,
               "binary_valid":True,"completion_verified":True}
        def owned_close(device,pid,out_state,config,callback):
            events.append(("close_owned",pid))
            out_state["cleanup_status"]="CLOSED_GRACEFULLY"
            out_state["close_messages_sent"]=3
        with patch("frida_guarded.close_owned_target",side_effect=owned_close), \
             patch("frida_guarded.process_exists",return_value=False):
            guarded.finalize_guarded_capture(object(),12440,state,cfg,report,
                                            Script(),Session())
        self.assertEqual(state["cleanup_order"],"OWNED_GUI_BEFORE_FRIDA")
        self.assertEqual(state["frida_cleanup_status"],"TARGET_EXIT_RELEASED_HOOK")
        self.assertEqual(state["close_messages_sent"],3)
        self.assertEqual([e for e in events if e[0] in
                          ("close_owned","script_unload","session_detach")],
                         [("close_owned",12440)])
        self.assertTrue(any(e[0]=="log" and e[1]=="CLOSE" for e in events))

    def test_stage48_unload_first_path_remains_unchanged(self):
        cfg=self.cfg
        events=[]
        class Script:
            def unload(self):events.append("unload")
        class Session:
            def detach(self):events.append("detach")
        def closed(device,pid,state,config,report):
            events.append("close")
            state["cleanup_status"]="CLOSED_GRACEFULLY"
        state={"launched_by_tool":True,"target_resumed":True,
               "runtime_verified":True,"hook_attached":True,
               "metadata_valid":True,"completion_verified":True}
        with patch("frida_guarded.close_owned_target",side_effect=closed):
            guarded.finalize_guarded_capture(object(),4524,state,cfg,
                                             lambda *a:None,Script(),Session())
        self.assertEqual(events,["unload","detach","close"])
        self.assertEqual(state["cleanup_order"],"FRIDA_BEFORE_OWNED_GUI")

    def test_exited_without_wm_close_is_not_claimed_graceful(self):
        cfg=self.cfg
        class Device:
            pass
        state={"launched_by_tool":True,"target_resumed":True}
        logs=[]
        with patch("frida_guarded.process_exists",side_effect=[True,False]), \
             patch("frida_guarded.request_graceful_close_windows",return_value=0):
            guarded.close_owned_target(Device(),12440,state,cfg,
                                       lambda *a:logs.append(a))
        self.assertEqual(state["cleanup_status"],"EXITED_WITHOUT_WM_CLOSE")
        self.assertEqual(state["close_messages_sent"],0)
        self.assertTrue(any("NOT confirmed" in str(e) for e in logs))

    def test_win32_enumwindows_requires_lparam_and_only_closes_owned_pid(self):
        """Stage48 regression: EnumWindows(callback) raised because Win32 needs LPARAM."""
        import ctypes
        from types import SimpleNamespace
        calls=[]
        class ApiFunction:
            def __init__(self, fn):
                self.fn=fn
                self.argtypes=None
                self.restype=None
            def __call__(self,*args):
                return self.fn(*args)

        def enumerate_windows(callback,lparam):
            calls.append(("EnumWindows",lparam))
            assert lparam == 0
            # One window belongs to our tool-owned PID, one does NOT.
            assert callback(111,0)
            assert callback(222,0)
            return 1

        def get_window_pid(hwnd,out_pid):
            out_pid._obj.value = 4524 if hwnd == 111 else 2222
            return 1

        def send_close(hwnd,msg,wparam,lparam):
            calls.append(("WM_CLOSE",hwnd,msg,wparam,lparam))
            return 1

        user32=SimpleNamespace(
            EnumWindows=ApiFunction(enumerate_windows),
            GetWindowThreadProcessId=ApiFunction(get_window_pid),
            IsWindow=ApiFunction(lambda hwnd: True),
            PostMessageW=ApiFunction(send_close),
        )
        with patch.object(ctypes,"WinDLL",return_value=user32,create=True), \
             patch.object(ctypes,"WINFUNCTYPE",
                          side_effect=lambda *signature:(lambda callback:callback),
                          create=True):
            sent=guarded.request_graceful_close_windows(4524)
        self.assertEqual(sent,1)
        self.assertEqual(calls,[("EnumWindows",0),("WM_CLOSE",111,0x0010,0,0)])

    def test_no_hook_lifecycle_smoke_uses_owned_spawn_resume_close(self):
        """Isolate WM_CLOSE without a DLL attach, callback, NAM or CLO creation."""
        class FakeDevice:
            def __init__(self):
                self.spawned=[]
                self.resumed=[]
            def enumerate_processes(self):return []
            def spawn(self,command):
                self.spawned.append(command)
                return 4524
            def resume(self,pid):
                self.resumed.append(pid)
        d=FakeDevice()
        fake_frida=SimpleNamespace(get_local_device=lambda:d)
        logs=[]
        def fake_close(device,pid,state,cfg,report):
            self.assertEqual(pid,4524)
            self.assertTrue(state["launched_by_tool"])
            state["cleanup_status"]="CLOSED_GRACEFULLY"
        with patch.object(guarded,"os",SimpleNamespace(name="nt")), \
             patch.object(guarded.platform,"architecture",return_value=("64bit","Windows")), \
             patch.dict(sys.modules,{"frida":fake_frida}), \
             patch("frida_guarded.preflight_paths"), \
             patch("frida_guarded.Path.is_file",return_value=True), \
             patch("frida_guarded.time.sleep"), \
             patch("frida_guarded.close_owned_target",side_effect=fake_close):
            code=guarded.smoke_lifecycle(SimpleNamespace(pid=None),self.cfg,
                                        lambda *x:logs.append(x))
        self.assertEqual(code,0)
        self.assertEqual(d.resumed,[4524])
        self.assertEqual(len(d.spawned),1)
        self.assertTrue(any("ZERO hooks" in str(entry) for entry in logs))

    def test_one_delayed_hook_no_audio_reads(self):
        js=guarded.agent_source(self.cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertIn("rpc.exports",js)
        self.assertIn("Process.attachModuleObserver",js)
        for forbidden in (".readByteArray(", ".readDouble(", ".readFloat(", ".writeByteArray("):
            self.assertNotIn(forbidden,js)

    def test_stage49_guarded_single_prefix_and_stage48_no_audio(self):
        raw=json.loads(STAGE49.read_text(encoding="utf-8"))
        cfg=core.validate(raw)
        self.assertEqual(cfg["mode"],"guarded_f64_binary")
        self.assertEqual(len(cfg["sites"]),1)
        self.assertEqual(cfg["sites"][0]["rva"],0x1190c)
        self.assertEqual(cfg["sites"][0]["guard"]["vtable_rva"],0x245170)
        self.assertEqual(cfg["sha256"],self.cfg["sha256"])
        self.assertEqual(cfg["binary_capture"]["max_events"],1)
        self.assertEqual(cfg["binary_capture"]["max_samples_per_event"],32)
        self.assertEqual(cfg["binary_capture"]["max_total_bytes"],256)
        self.assertEqual(cfg["binary_capture"]["scratch_output_offset"],112)
        self.assertEqual(cfg["binary_capture"]["fallback_input_reg"],"rdi")
        js=guarded.agent_source(cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertEqual(js.count(".readByteArray("),1)
        self.assertIn("output pointer provenance mismatch",js)
        self.assertNotIn("readDouble(",js)
        self.assertNotIn("readFloat(",js)
        stage48js=guarded.agent_source(self.cfg)
        self.assertEqual(stage48js.count("Interceptor.attach("),1)
        self.assertNotIn(".readByteArray(",stage48js)
        if shutil.which("node"):
            with tempfile.TemporaryDirectory() as d:
                f=Path(d)/"agent49.js"
                f.write_text(js,encoding="utf-8")
                p=subprocess.run(["node","--check",str(f)],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)

    def test_stage49_binary_schema_rejects_unsafe_overrides(self):
        raw=json.loads(STAGE49.read_text(encoding="utf-8"))
        def invalid(edit):
            c=copy.deepcopy(raw)
            edit(c)
            with self.assertRaises((ValueError,KeyError,TypeError)):
                core.validate(c)
        invalid(lambda c:c["binary_capture"].update(max_samples_per_event=33))
        invalid(lambda c:c["binary_capture"].update(max_total_bytes=2048))
        invalid(lambda c:c["binary_capture"].update(max_events=2))
        invalid(lambda c:c["binary_capture"].update(max_events=True))
        invalid(lambda c:c["binary_capture"].update(scratch_output_offset=113))
        invalid(lambda c:c["binary_capture"].update(fallback_input_reg="invalid"))
        invalid(lambda c:c["binary_capture"].update(javascript="readEverything()"))
        invalid(lambda c:c["sites"][0].update(fields=[{"name":"x","type":"f64_binary"}]))
        invalid(lambda c:c.update(mode="guarded_metadata"))
        invalid(lambda c:c["sites"].append(copy.deepcopy(c["sites"][0])))

    def test_stage49_bounded_binary_host_persistence_recovery_and_archive(self):
        cfg=core.validate(json.loads(STAGE49.read_text(encoding="utf-8")))
        event={"kind":"binary_hit","valid":True,"site":"post_fractional_output",
               "observed":18,"output_f64":114,"output_bytes":912,
               "copied_f64":32,"copied_bytes":256,"readable_range":True,
               "provenance":"selected_scratch_or_input"}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            st={"binary_valid":False}
            payload=bytes(range(256))
            e=guarded.persist_guarded_binary(cfg,st,root,event,payload)
            self.assertTrue(st["binary_valid"])
            self.assertEqual(st["binary_bytes"],256)
            self.assertEqual((root/"block_0001.bin").read_bytes(),payload)
            import hashlib
            self.assertEqual(e["sha256"],hashlib.sha256(payload).hexdigest())
            with self.assertRaises(ValueError):
                guarded.persist_guarded_binary(cfg,st,root,event,payload)
            (root/"events.jsonl").write_text(json.dumps(e)+"\n",encoding="utf-8")
            recovered={}
            guarded.reconcile(root,recovered)
            self.assertTrue(recovered["binary_valid"])
            self.assertTrue(recovered["metadata_valid"])
            (root/"block_0001.bin").write_bytes(b"x"*256)
            tampered={}
            guarded.reconcile(root,tampered)
            self.assertFalse(tampered.get("binary_valid",False))
            (root/"block_0001.bin").write_bytes(payload)
            for name in ("config.json","manifest.json","HANDOFF.md"):
                (root/name).write_text("test",encoding="utf-8")
            (root/"do_not_archive.wav").write_bytes(b"SECRET")
            import tarfile
            core.archive(root,root/"test.tar.gz")
            with tarfile.open(root/"test.tar.gz") as tar:
                names=[member.name for member in tar]
            self.assertIn("frida_capture/block_0001.bin",names)
            self.assertFalse(any("do_not_archive" in name for name in names))
        with tempfile.TemporaryDirectory() as d:
            st={}
            with self.assertRaises(ValueError):
                guarded.persist_guarded_binary(cfg,st,Path(d),event,b"too short")
            with self.assertRaises(ValueError):
                guarded.persist_guarded_binary(cfg,st,Path(d),
                    dict(event,provenance="unverified"),bytes(range(256)))
            self.assertFalse(st.get("binary_valid",False))

    def test_legacy_unchanged(self):
        old=core.validate({"module":"5868USB.dll","sha256":"f"*64,
             "sites":[{"name":"block","address":"0x18000c838",
                       "fields":[{"name":"block","type":"f64_binary",
                                  "reg":"rdx","count":1972}]}]})
        self.assertEqual(old["sites"][0]["rva"],0xc838)
        self.assertEqual(old["sites"][0]["fields"][0]["count"],1972)
        self.assertIn("Interceptor.attach(",core.agent_source(old))
        self.assertNotIn("mode",old)

    def test_no_unchecked_user_js(self):
        for modifications in [
            lambda x:x["sites"][0]["guard"].update(javascript="send('bad')"),
            lambda x:x["sites"][0].update(fields=[{"name":"audio","type":"f64_binary","reg":"rdx","count":64}]),
            lambda x:x["sites"][0]["guard"].update(max_samples=100000),
            lambda x:x["sites"][0]["guard"].update(owner_reg="xmm8"),
            lambda x:x["sites"][0]["guard"].update(owner_offset=-8),
            lambda x:x["completion"].update(appdata_subdir="../secret"),
            lambda x:x["target"].update(process_name_contains=""),
            lambda x:x["sites"].append(copy.deepcopy(x["sites"][0])),
        ]:
            with self.subTest(modification=str(modifications)):
                candidate=copy.deepcopy(self.raw)
                modifications(candidate)
                with self.assertRaises((ValueError,TypeError,KeyError)):
                    core.validate(candidate)

    def test_ctrl_c_journal_recovery_and_clo_recursive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            ev=[
                {"kind":"module_found","name":"5868USB.dll"},
                {"kind":"hook_attached","site":"post_fractional_output","hooks_installed":1},
                {"kind":"first_rejected_return","reason":"return count zero or out of bounds"},
                {"kind":"metadata_hit","site":"post_fractional_output","valid":True,
                 "output_f64":114,"output_bytes":912,"observed":18},
            ]
            (root/"events.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in ev),encoding="utf-8")
            state={}
            guarded.reconcile(root,state)
            self.assertEqual(state["journal_events"],4)
            self.assertEqual(state["last_metadata"]["output_f64"],114)
            self.assertTrue(state["hook_attached"])
            self.assertEqual(guarded.interrupted_status(state),
                "METADATA_OBSERVED_OPERATOR_INTERRUPTED")
            sub=root/"nested";sub.mkdir()
            (sub/"new.clo").write_bytes(b"fake")
            self.assertEqual(len(guarded.snapshot(root,True)),1)
            self.assertEqual(len(guarded.snapshot(root,False)),0)

    def test_tar_archive_remains_allowlisted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for file in ("config.json","manifest.json","events.jsonl","HANDOFF.md"):
                (root/file).write_text("test",encoding="utf-8")
            (root/"private_audio.wav").write_bytes(b"NO")
            dest=root/"output.tar.gz"
            core.archive(root,dest)
            import tarfile
            with tarfile.open(dest) as t:
                names=[x.name for x in t]
            self.assertTrue(all("private_audio" not in n for n in names))

    def test_js_syntax_if_node_exists(self):
        node=shutil.which("node")
        if not node:self.skipTest("node not installed")
        with tempfile.TemporaryDirectory() as d:
            fn=Path(d)/"agent.js"
            fn.write_text(guarded.agent_source(self.cfg),encoding="utf-8")
            result=subprocess.run([node,"--check",str(fn)],text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=="__main__":
    unittest.main()
