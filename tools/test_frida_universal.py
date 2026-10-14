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
STAGE50=HERE.parent/"research"/"htkpa"/"stages"/"stage50"/"frida.json"
STAGE51=HERE.parent/"research"/"htkpa"/"stages"/"stage51"/"frida.json"
STAGE52=HERE.parent/"research"/"htkpa"/"stages"/"stage52"/"frida.json"
STAGE53=HERE.parent/"research"/"htkpa"/"stages"/"stage53"/"frida.json"
STAGE54=HERE.parent/"research"/"htkpa"/"stages"/"stage54"/"frida.json"
STAGE58=HERE.parent/"research"/"htkpa"/"stages"/"stage58"/"frida.json"
STAGE64=HERE.parent/"research"/"htkpa"/"stages"/"stage64"/"frida.json"

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

    def test_stage64_one_hook_extended_output_byte_limit_and_fixed_rate_geometry(self):
        raw=json.loads(STAGE64.read_text(encoding="utf-8"))
        cfg=core.validate(raw)
        old=core.validate(json.loads(STAGE53.read_text(encoding="utf-8")))
        self.assertEqual(cfg["sites"],old["sites"])
        self.assertEqual(cfg["sha256"],old["sha256"])
        self.assertEqual(cfg["rate_probe"],old["rate_probe"])
        self.assertNotIn("input_probe",cfg)
        self.assertNotIn("output_probe",cfg)
        self.assertNotIn("coeff_probe",cfg)
        self.assertEqual(cfg["long_probe"]["total_max_bytes"],9448)
        self.assertEqual(cfg["long_probe"]["forward"]["copied_f64"],1067)
        self.assertEqual(cfg["long_probe"]["reverse"]["copied_f64"],114)
        js=guarded.agent_source(cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertEqual(js.count(".readByteArray("),1)
        self.assertEqual(js.count(".readDouble("),2)
        self.assertIn("fractional_r9_ref_onleave_extended",js)
        self.assertIn("outputRef.readPointer()",js)
        self.assertIn("longForwardDone",js)
        self.assertIn("longReverseDone",js)
        for token in ("LONG_PROBE_ENTER_EXTENSION","LONG_PROBE_LEAVE_EXTENSION",
                      "RATE_PROBE_EXTENSION","COEFF_PROBE_EXTENSION","JSON_SPEC"):
            self.assertNotIn(token,js)
        if shutil.which("node"):
            with tempfile.TemporaryDirectory() as td:
                fname=Path(td)/"stage64_agent.js"
                fname.write_text(js,encoding="utf-8")
                p=subprocess.run(["node","--check",str(fname)],
                                 capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)

    def test_stage64_sha_guarded_full_1067_and_114_blocks_recover_and_archive(self):
        import hashlib
        import tarfile
        cfg=core.validate(json.loads(STAGE64.read_text(encoding="utf-8")))
        forward_data=bytes(range(256))+b"\x00"*(1067*8-256)
        reverse_data=bytes(reversed(range(256)))+b"\x01"*(114*8-256)
        prefix_sha={
            "forward":hashlib.sha256(forward_data[:256]).hexdigest(),
            "reverse":hashlib.sha256(reverse_data[:256]).hexdigest()}
        def event(side,owner):
            c=cfg["long_probe"][side]
            return {"kind":"fractional_extended_output","valid":True,
                    "side":side,"site":cfg["sites"][0]["name"],
                    "observed":c["observed"],"processor_pointer":owner,
                    "input_f64":c["input_f64"],"output_f64":c["output_f64"],
                    "copied_f64":c["copied_f64"],"copied_bytes":c["copied_f64"]*8,
                    "rate_numerator":c["numerator"],
                    "rate_denominator":c["denominator"],
                    "provenance":"fractional_r9_ref_onleave_extended"}
        with tempfile.TemporaryDirectory() as td, patch.dict(guarded.LONG_PREFIX_SHA,prefix_sha):
            folder=Path(td)
            st={}
            forward=event("forward","0x4444")
            reverse=event("reverse","0x8888")
            with self.assertRaises(ValueError):
                guarded.persist_fractional_long_output(cfg,st,folder,forward,forward_data[:-8])
            with self.assertRaises(ValueError):
                guarded.persist_fractional_long_output(cfg,st,folder,forward,
                    b"\xff"*256+forward_data[256:])
            first=guarded.persist_fractional_long_output(cfg,st,folder,forward,forward_data)
            self.assertTrue(st["long_forward_valid"])
            self.assertEqual(st["long_total_bytes"],8536)
            with self.assertRaises(ValueError):
                guarded.persist_fractional_long_output(cfg,st,folder,forward,forward_data)
            with self.assertRaises(ValueError):
                guarded.persist_fractional_long_output(
                    cfg,st,folder,event("reverse","0x4444"),reverse_data)
            second=guarded.persist_fractional_long_output(cfg,st,folder,reverse,reverse_data)
            self.assertTrue(st["long_reverse_valid"])
            self.assertEqual(st["long_total_bytes"],9448)
            self.assertEqual(first["first32_sha256"],prefix_sha["forward"])
            self.assertEqual(second["first32_sha256"],prefix_sha["reverse"])
            (folder/"events.jsonl").write_text(
                json.dumps(first)+"\n"+json.dumps(second)+"\n",encoding="utf-8")
            restored={}
            guarded.reconcile(folder,restored)
            guarded.reconcile(folder,restored)
            self.assertTrue(restored["long_forward_valid"])
            self.assertTrue(restored["long_reverse_valid"])
            self.assertEqual(restored["long_total_bytes"],9448)
            for fname in ("config.json","manifest.json","HANDOFF.md"):
                (folder/fname).write_text("ok",encoding="utf-8")
            (folder/"unapproved_native_extra.f64le").write_bytes(b"PRIVATE")
            destination=folder/"stage64_test.tar.gz"
            core.archive(folder,destination)
            with tarfile.open(destination,"r:gz") as t:
                members=t.getnames()
                self.assertIn("frida_capture/forward_1067.f64le.bin",members)
                self.assertIn("frida_capture/reverse_114.f64le.bin",members)
                self.assertNotIn("frida_capture/unapproved_native_extra.f64le",members)
                self.assertEqual(
                    t.extractfile("frida_capture/reverse_114.f64le.bin").read(),
                    reverse_data)

    def test_stage64_rejects_modified_bounds_and_incompatible_probes(self):
        raw=json.loads(STAGE64.read_text(encoding="utf-8"))
        for change in (
            lambda c:c["long_probe"]["forward"].update(observed=2),
            lambda c:c["long_probe"]["forward"].update(copied_f64=1068),
            lambda c:c["long_probe"]["reverse"].update(input_f64=255),
            lambda c:c["long_probe"]["reverse"].update(output_f64=118),
            lambda c:c["long_probe"]["reverse"].update(denominator=48000),
            lambda c:c["long_probe"].update(total_max_bytes=20000),
            lambda c:c["long_probe"].update(extra="any"),
            lambda c:c["long_probe"]["forward"].update(observed=True),
            lambda c:c.update(output_probe={"output_samples":32}),
            lambda c:c.update(coeff_probe={"table_rva":0x2C7560}),
        ):
            modified=copy.deepcopy(raw)
            change(modified)
            with self.assertRaises((TypeError,ValueError,KeyError)):
                core.validate(modified)

    def test_stage58_single_hook_coefficient_bank_contract(self):
        cfg=core.validate(json.loads(STAGE58.read_text(encoding="utf-8")))
        base=core.validate(json.loads(STAGE53.read_text(encoding="utf-8")))
        self.assertEqual(cfg["sites"],base["sites"])
        self.assertEqual(cfg["rate_probe"],base["rate_probe"])
        self.assertEqual(cfg["coeff_probe"],
            {"table_rva":0x2C7560,"phase_count":673,"stride_f64":72,
             "total_max_bytes":387648,"trigger_input_f64":3})
        self.assertNotIn("input_probe",cfg)
        self.assertNotIn("output_probe",cfg)
        js=guarded.agent_source(cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertEqual(js.count(".readByteArray("),1)
        self.assertEqual(js.count(".readDouble("),2)
        self.assertIn("native_dll_data_phase_bank",js)
        self.assertIn("coeffProbeDone",js)
        self.assertNotIn("COEFF_PROBE_EXTENSION",js)
        self.assertNotIn("RATE_PROBE_EXTENSION",js)
        self.assertNotIn("INPUT_PROBE_EXTENSION",js)
        self.assertNotIn("OUTPUT_PROBE_ENTER_EXTENSION",js)
        if shutil.which("node"):
            with tempfile.TemporaryDirectory() as d:
                path=Path(d)/"stage58.js"
                path.write_text(js,encoding="utf-8")
                p=subprocess.run(["node","--check",str(path)],
                                 capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)

    def test_stage58_native_table_checksum_and_partial_recovery(self):
        import hashlib
        import struct
        import tarfile
        cfg=core.validate(json.loads(STAGE58.read_text(encoding="utf-8")))
        e={"kind":"fractional_coeff_bank","valid":True,"site":"fractional_entry_io",
           "observed":17,"processor_pointer":"0x1234","input_f64":3,
           "copied_bytes":387648,"table_rva":0x2C7560,"phase_count":673,
           "stride_f64":72,"rate_numerator":96000,"rate_denominator":44100,
           "provenance":"native_dll_data_phase_bank"}
        bank=struct.pack("<d",1.0)+b"\x00"*(387648-8)
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            st={}
            with self.assertRaises(ValueError):
                guarded.persist_fractional_coeff_bank(cfg,st,folder,e,b"\x00"*387648)
            with self.assertRaises(ValueError):
                guarded.persist_fractional_coeff_bank(cfg,st,folder,e,bank[:-8])
            out=guarded.persist_fractional_coeff_bank(cfg,st,folder,e,bank)
            self.assertTrue(st["coeff_bank_valid"])
            self.assertEqual(st["coeff_bank_bytes"],387648)
            self.assertEqual(out["sha256"],hashlib.sha256(bank).hexdigest())
            with self.assertRaises(ValueError):
                guarded.persist_fractional_coeff_bank(cfg,st,folder,e,bank)
            (folder/"events.jsonl").write_text(json.dumps(out)+"\n",encoding="utf-8")
            restored={}
            guarded.reconcile(folder,restored)
            self.assertTrue(restored["coeff_bank_valid"])
            self.assertEqual(restored["coeff_bank_sha256"],out["sha256"])
            for name in ("config.json","manifest.json","HANDOFF.md"):
                (folder/name).write_text("ok",encoding="utf-8")
            (folder/"private_unapproved.bin").write_bytes(b"NO")
            dest=folder/"test.tar.gz"
            core.archive(folder,dest)
            with tarfile.open(dest,"r:gz") as t:
                members=t.getnames()
                self.assertIn("frida_capture/frac_coeff_bank_673x72.f64le.bin",members)
                self.assertNotIn("frida_capture/private_unapproved.bin",members)
                self.assertEqual(t.extractfile(
                    "frida_capture/frac_coeff_bank_673x72.f64le.bin").read(),bank)

    def test_stage58_reject_modified_table_rva_and_oversized_read(self):
        raw=json.loads(STAGE58.read_text(encoding="utf-8"))
        for change in [
            lambda x:x["coeff_probe"].update(table_rva=0x2C7568),
            lambda x:x["coeff_probe"].update(phase_count=674),
            lambda x:x["coeff_probe"].update(stride_f64=73),
            lambda x:x["coeff_probe"].update(total_max_bytes=387656),
            lambda x:x["coeff_probe"].update(trigger_input_f64=0),
            lambda x:x["coeff_probe"].update(table_rva=True),
            lambda x:x["coeff_probe"].update(javascript="bad"),
            lambda x:x.update(input_probe={"first_f64":3}),
            lambda x:x.update(output_probe={"output_samples":32}),
        ]:
            config=copy.deepcopy(raw)
            change(config)
            with self.assertRaises((ValueError,TypeError,KeyError)):
                core.validate(config)

    def test_stage54_private_96k_input_and_48k_output_prefixes(self):
        raw=json.loads(STAGE54.read_text(encoding="utf-8"))
        cfg=core.validate(raw)
        prior=core.validate(json.loads(STAGE53.read_text(encoding="utf-8")))
        self.assertEqual(cfg["mode"],"guarded_fractional_io")
        self.assertEqual(cfg["sites"],prior["sites"])
        self.assertEqual(cfg["rate_probe"],prior["rate_probe"])
        self.assertEqual(cfg["sha256"],prior["sha256"])
        self.assertEqual(cfg["input_probe"],
            {"first_f64":3,"second_f64":256,"total_max_bytes":2072,
             "numerator":96000,"denominator":44100})
        self.assertEqual(cfg["output_probe"],
            {"output_samples":32,"total_max_bytes":256,
             "numerator":88200,"denominator":48000,
             "first_input_f64":6170612,"first_output_f64":3358150})
        js=guarded.agent_source(cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertEqual(js.count(".readByteArray("),2)
        self.assertEqual(js.count(".readDouble("),2)
        self.assertIn("inputProbeProcessor",js)
        self.assertIn("inputProbeStep",js)
        self.assertIn("this.context.rdx",js)
        self.assertIn("kind:'fractional_input_prefix'",js)
        self.assertIn("fractional_rdx_onenter",js)
        self.assertIn("fractional_r9_ref_onleave",js)
        self.assertIn("this.context.r9",js)
        self.assertIn("kind:'fractional_output_prefix'",js)
        self.assertNotIn("writeByteArray(",js)
        self.assertNotIn("RATE_PROBE_EXTENSION",js)
        self.assertNotIn("INPUT_PROBE_EXTENSION",js)
        self.assertNotIn("OUTPUT_PROBE_ENTER_EXTENSION",js)
        self.assertNotIn("OUTPUT_PROBE_LEAVE_EXTENSION",js)
        self.assertNotIn("readByteArray(",guarded.agent_source(prior))
        if shutil.which("node"):
            with tempfile.TemporaryDirectory() as d:
                f=Path(d)/"stage54_agent.js"
                f.write_text(js,encoding="utf-8")
                chk=subprocess.run(["node","--check",str(f)],
                                   capture_output=True,text=True)
                self.assertEqual(chk.returncode,0,chk.stderr)

    def test_stage54_capture_strict_order_sha_recovery_and_tar_allowlist(self):
        import hashlib
        import tarfile
        cfg=core.validate(json.loads(STAGE54.read_text(encoding="utf-8")))
        owner="0x1234abcd"
        def event(step, observed, ptr=owner):
            n=3 if step==1 else 256
            return {"kind":"fractional_input_prefix","valid":True,
                "site":"fractional_entry_io","step":step,"observed":observed,
                "processor_pointer":ptr,"input_f64":n,
                "copied_bytes":8*n,"rate_numerator":96000,
                "rate_denominator":44100,"provenance":"fractional_rdx_onenter"}
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            state={}
            a=bytes(range(24))
            b=bytes(range(256))*8
            c=bytes(range(256))
            native_out_event={
                "kind":"fractional_output_prefix","valid":True,
                "site":"fractional_entry_io","observed":1,
                "processor_pointer":"0x4567","input_f64":6170612,
                "output_f64":3358150,"copied_f64":32,"copied_bytes":256,
                "rate_numerator":88200,"rate_denominator":48000,
                "provenance":"fractional_r9_ref_onleave"}
            out=guarded.persist_fractional_output(cfg,state,folder,native_out_event,c)
            self.assertTrue(state["output_probe_valid"])
            self.assertEqual(state["output_probe_bytes"],256)
            with self.assertRaises(ValueError):
                guarded.persist_fractional_output(cfg,state,folder,native_out_event,c)
            with self.assertRaises(ValueError):
                guarded.persist_fractional_input(cfg,state,folder,event(2,18),b)
            one=guarded.persist_fractional_input(cfg,state,folder,event(1,17),a)
            self.assertEqual(state["input_prefix_events"],1)
            self.assertFalse(state["input_prefix_valid"])
            with self.assertRaises(ValueError):
                guarded.persist_fractional_input(cfg,state,folder,
                    event(2,18,"0xdeadbeef"),b)
            with self.assertRaises(ValueError):
                guarded.persist_fractional_input(cfg,state,folder,event(2,18),b[:-1])
            two=guarded.persist_fractional_input(cfg,state,folder,event(2,18),b)
            self.assertTrue(state["input_prefix_valid"])
            self.assertEqual(state["input_prefix_total_bytes"],2072)
            self.assertEqual(one["sha256"],hashlib.sha256(a).hexdigest())
            self.assertEqual(two["sha256"],hashlib.sha256(b).hexdigest())
            self.assertEqual((folder/"input_0001.bin").read_bytes(),a)
            self.assertEqual((folder/"input_0002.bin").read_bytes(),b)
            with self.assertRaises(ValueError):
                guarded.persist_fractional_input(cfg,state,folder,event(2,19),b)
            (folder/"events.jsonl").write_text(
                "".join(json.dumps(item)+"\n" for item in [out,one,two]),encoding="utf-8")
            restored={}
            guarded.reconcile(folder,restored)
            guarded.reconcile(folder,restored)
            self.assertTrue(restored["input_prefix_valid"])
            self.assertEqual(restored["input_prefix_total_bytes"],2072)
            self.assertEqual(restored["input_prefix_events"],2)
            self.assertTrue(restored["output_probe_valid"])
            self.assertEqual(restored["output_probe_bytes"],256)
            for name in ["config.json","manifest.json","HANDOFF.md"]:
                (folder/name).write_text("ok",encoding="utf-8")
            (folder/"should_not_copy.raw").write_bytes(b"RAW PRIVATE")
            dest=folder/"test.tar.gz"
            core.archive(folder,dest)
            with tarfile.open(dest,"r:gz") as tar:
                members=tar.getnames()
                self.assertIn("frida_capture/input_0001.bin",members)
                self.assertIn("frida_capture/input_0002.bin",members)
                self.assertIn("frida_capture/output_0001.bin",members)
                self.assertEqual(tar.extractfile("frida_capture/output_0001.bin").read(),c)
                self.assertNotIn("frida_capture/should_not_copy.raw",members)
                self.assertEqual(tar.extractfile("frida_capture/input_0002.bin").read(),b)

    def test_stage54_rejects_unsafe_configs_and_wrong_byte_budgets(self):
        original=json.loads(STAGE54.read_text(encoding="utf-8"))
        for change in [
            lambda c:c["input_probe"].update(first_f64=4),
            lambda c:c["input_probe"].update(second_f64=257),
            lambda c:c["input_probe"].update(total_max_bytes=65536),
            lambda c:c["input_probe"].update(numerator=44100),
            lambda c:c["input_probe"].update(denominator=48000),
            lambda c:c["input_probe"].update(extra="bad"),
            lambda c:c["output_probe"].update(output_samples=33),
            lambda c:c["output_probe"].update(total_max_bytes=2048),
            lambda c:c["output_probe"].update(first_input_f64=6170613),
            lambda c:c["output_probe"].update(numerator=96000),
            lambda c:c["output_probe"].update(javascript="bad"),
            lambda c:c.update(rate_probe=None),
            lambda c:c["sites"].append(copy.deepcopy(c["sites"][0])),
        ]:
            candidate=copy.deepcopy(original)
            change(candidate)
            with self.assertRaises((ValueError,KeyError,TypeError)):
                core.validate(candidate)

    def test_stage53_fractional_rate_field_contract(self):
        config=core.validate(json.loads(STAGE53.read_text(encoding="utf-8")))
        previous=core.validate(json.loads(STAGE52.read_text(encoding="utf-8")))
        self.assertEqual(config["sites"],previous["sites"])
        self.assertEqual(config["rate_probe"],
                         {"numerator_offset":4104,"denominator_offset":4112})
        generated=guarded.agent_source(config)
        self.assertEqual(generated.count("Interceptor.attach("),1)
        self.assertEqual(generated.count(".readDouble("),2)
        self.assertEqual(guarded.agent_source(previous).count(".readDouble("),0)
        self.assertIn("record.step_output_input_ratio",generated)
        self.assertNotIn("readByteArray(",generated)

    def test_stage53_bad_rate_offsets_refused(self):
        raw=json.loads(STAGE53.read_text(encoding="utf-8"))
        for field,bad in [("numerator_offset",4105),("denominator_offset",4120),
                          ("numerator_offset",True)]:
            with self.subTest(field=field,bad=bad):
                cfg=copy.deepcopy(raw)
                cfg["rate_probe"][field]=bad
                with self.assertRaises((ValueError,TypeError,KeyError)):
                    core.validate(cfg)

    def test_stage52_exact_fractional_entry_one_hook_on_enter_and_on_leave(self):
        cfg=core.validate(json.loads(STAGE52.read_text(encoding="utf-8")))
        self.assertEqual(cfg["mode"],"guarded_fractional_io")
        self.assertEqual(cfg["sha256"],self.cfg["sha256"])
        self.assertEqual(cfg["sites"][0]["rva"],0x135c0)
        self.assertEqual(cfg["sites"][0]["guard"]["vtable_rva"],0x245170)
        self.assertEqual(cfg["sites"][0]["guard"]["max_observations"],64)
        self.assertEqual(cfg["sites"][0]["guard"]["max_input_f64"],7000000)
        self.assertEqual(cfg["sites"][0]["guard"]["max_output_f64"],7000000)
        self.assertNotIn("binary_capture",cfg)
        self.assertNotIn("trace",cfg)
        js=guarded.agent_source(cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertEqual(js.count("onEnter()"),1)
        self.assertEqual(js.count("onLeave(retval)"),1)
        self.assertIn("const inputCount = this.context.r8",js)
        self.assertIn("const outputCount = retval",js)
        self.assertIn("this.observation",js)
        self.assertIn("kind:'fractional_io'",js)
        for forbidden in ("readByteArray(","readDouble(","readFloat(","writeByteArray("):
            self.assertNotIn(forbidden,js)
        self.assertEqual(guarded.agent_source(self.cfg).count("Interceptor.attach("),1)
        if shutil.which("node"):
            with tempfile.TemporaryDirectory() as d:
                f=Path(d)/"stage52.js"
                f.write_text(js,encoding="utf-8")
                p=subprocess.run(["node","--check",str(f)],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)

    def test_stage52_reject_unchecked_or_oversized_trace_configs(self):
        cfg=json.loads(STAGE52.read_text(encoding="utf-8"))
        for edit in [
            lambda c:c["sites"][0]["guard"].update(max_input_f64=7000001),
            lambda c:c["sites"][0]["guard"].update(max_output_f64=8000000),
            lambda c:c["sites"][0]["guard"].update(max_observations=1000),
            lambda c:c["sites"][0]["guard"].update(javascript="bad"),
            lambda c:c["sites"][0]["guard"].update(kind="processor_output"),
            lambda c:c["sites"][0].update(address="-1"),
            lambda c:c["sites"][0].update(fields=[{"type":"f64_binary"}]),
            lambda c:c["sites"].append(copy.deepcopy(c["sites"][0])),
            lambda c:c.update(binary_capture={"max_total_bytes":256}),
            lambda c:c.update(trace={"max_events":64}),
            lambda c:c.update(mode="guarded_f64_binary"),
            lambda c:c["completion"].update(path="../unsafe"),
        ]:
            altered=copy.deepcopy(cfg)
            edit(altered)
            with self.assertRaises((ValueError,TypeError,KeyError)):
                core.validate(altered)

    def test_stage52_io_recovery_and_safe_gui_close_before_unload(self):
        cfg=core.validate(json.loads(STAGE52.read_text(encoding="utf-8")))
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            e=[{"kind":"hook_attached","hooks_installed":1},
               {"kind":"fractional_io","valid":True,"observed":18,
                "site":"fractional_entry_io","input_f64":237,"output_f64":114},
               {"kind":"fractional_io","valid":True,"observed":19,
                "site":"fractional_entry_io","input_f64":238,"output_f64":118}]
            (root/"events.jsonl").write_text(
                "".join(json.dumps(item)+"\n" for item in e),encoding="utf-8")
            restored={}
            guarded.reconcile(root,restored)
            guarded.reconcile(root,restored)
            self.assertTrue(restored["metadata_valid"])
            self.assertEqual(restored["last_metadata"]["output_f64"],118)
            self.assertEqual(restored["io_events"],2)
        log=[]
        class Script:
            def unload(self):log.append("unload")
        class Session:
            def detach(self):log.append("detach")
        st={"launched_by_tool":True,"runtime_verified":True,"hook_attached":True,
            "completion_verified":True,"metadata_valid":True,"io_events":21}
        def close(device,pid,state,cfg,report):
            log.append("close")
            state["cleanup_status"]="CLOSED_GRACEFULLY"
        with patch("frida_guarded.close_owned_target",side_effect=close), \
             patch("frida_guarded.process_exists",return_value=False):
            guarded.finalize_guarded_capture(object(),1234,st,cfg,
                                             lambda *x:None,Script(),Session())
        self.assertEqual(log,["close"])
        self.assertEqual(st["cleanup_order"],"OWNED_GUI_BEFORE_FRIDA")
        self.assertEqual(st["frida_cleanup_status"],"TARGET_EXIT_RELEASED_HOOK")

    def test_stage51_postcall_r8_debug_is_not_fractional_input(self):
        cfg=core.validate(json.loads(STAGE51.read_text(encoding="utf-8")))
        baseline=core.validate(json.loads(STAGE50.read_text(encoding="utf-8")))
        self.assertEqual(cfg["mode"],"guarded_f64_binary")
        self.assertEqual(cfg["sites"],baseline["sites"])
        self.assertEqual(cfg["sha256"],baseline["sha256"])
        self.assertEqual(cfg["binary_capture"],baseline["binary_capture"])
        self.assertEqual(cfg["trace"],{"max_events":64,"input_count_reg":"r8"})
        js=guarded.agent_source(cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertEqual(js.count(".readByteArray("),1)
        self.assertIn("traceEvent.postcall_r8d",js)
        self.assertNotIn("traceEvent.input_f64",js)
        self.assertIn("c.r8.and(ptr('0xffffffff'))",js)
        self.assertIn("kind:'trace_return'",js)
        self.assertNotIn("readDouble(",js)
        self.assertNotIn("writeByteArray(",js)
        if shutil.which("node"):
            with tempfile.TemporaryDirectory() as d:
                f=Path(d)/"agent51.js"
                f.write_text(js,encoding="utf-8")
                p=subprocess.run(["node","--check",str(f)],
                                 capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
        self.assertNotIn("input_count_reg",baseline["trace"])
        self.assertNotIn(".readByteArray(",guarded.agent_source(self.cfg))

    def test_stage51_rejects_non_r8_or_unbounded_trace(self):
        base=json.loads(STAGE51.read_text(encoding="utf-8"))
        for edit in [
            lambda x:x["trace"].update(input_count_reg="r9"),
            lambda x:x["trace"].update(input_count_reg="rax"),
            lambda x:x["trace"].update(input_count_reg=None),
            lambda x:x["trace"].update(max_events=65),
            lambda x:x["trace"].update(unchecked_js="bad"),
            lambda x:x["binary_capture"].update(max_samples_per_event=33),
            lambda x:x["sites"].append(copy.deepcopy(x["sites"][0])),
        ]:
            x=copy.deepcopy(base)
            edit(x)
            with self.assertRaises((ValueError,KeyError,TypeError)):
                core.validate(x)

    def test_stage50_same_single_hook_64_return_trace_one_audio_prefix(self):
        raw=json.loads(STAGE50.read_text(encoding="utf-8"))
        cfg=core.validate(raw)
        original=core.validate(json.loads(STAGE49.read_text(encoding="utf-8")))
        self.assertEqual(cfg["mode"],"guarded_f64_binary")
        self.assertEqual(len(cfg["sites"]),1)
        self.assertEqual(cfg["sites"][0]["rva"],0x1190c)
        self.assertEqual(cfg["sites"][0]["guard"]["vtable_rva"],0x245170)
        self.assertEqual(cfg["sha256"],self.cfg["sha256"])
        self.assertEqual(cfg["trace"],{"max_events":64})
        self.assertEqual(cfg["binary_capture"],original["binary_capture"])
        js=guarded.agent_source(cfg)
        self.assertEqual(js.count("Interceptor.attach("),1)
        self.assertEqual(js.count(".readByteArray("),1)
        self.assertIn("kind:'trace_return'",js)
        self.assertIn("kind:'trace_reject'",js)
        self.assertIn("spec.trace && metadataSent",js)
        self.assertIn("observed >= spec.trace.max_events",js)
        self.assertNotIn("readDouble(",js)
        self.assertNotIn("writeByteArray(",js)
        if shutil.which("node"):
            with tempfile.TemporaryDirectory() as d:
                agent=Path(d)/"stage50_agent.js"
                agent.write_text(js,encoding="utf-8")
                p=subprocess.run(["node","--check",str(agent)],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
        # Stage48 remains free of any wave reads; Stage49 one-shot unchanged.
        self.assertNotIn(".readByteArray(",guarded.agent_source(self.cfg))
        self.assertNotIn("trace",original)

    def test_stage50_trace_journal_reconcile_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            events=[
                {"kind":"hook_attached","hooks_installed":1},
                {"kind":"trace_return","site":"post_fractional_output",
                 "observed":1,"output_f64":0},
                {"kind":"trace_reject","observed":1,"reason":"return count zero or out of bounds"},
                {"kind":"trace_return","site":"post_fractional_output",
                 "observed":18,"output_f64":114},
                {"kind":"trace_cap_reached","observations":64},
            ]
            (root/"events.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in events),encoding="utf-8")
            state={"trace_returns":2,"trace_rejections":1}
            guarded.reconcile(root,state)
            guarded.reconcile(root,state)
            self.assertEqual(state["trace_returns"],2)
            self.assertEqual(state["trace_rejections"],1)
            self.assertTrue(state["trace_cap_reached"])

    def test_stage50_trace_override_is_strictly_bounded(self):
        raw=json.loads(STAGE50.read_text(encoding="utf-8"))
        for edit in [
            lambda c:c["trace"].update(max_events=65),
            lambda c:c["trace"].update(max_events=0),
            lambda c:c["trace"].update(max_events=True),
            lambda c:c["trace"].update(javascript="evil"),
            lambda c:c["sites"][0]["guard"].update(max_observations=63),
            lambda c:c["sites"].append(copy.deepcopy(c["sites"][0])),
            lambda c:c["binary_capture"].update(max_total_bytes=257),
        ]:
            cfg=copy.deepcopy(raw)
            edit(cfg)
            with self.assertRaises((ValueError,TypeError,KeyError)):
                core.validate(cfg)
        cfg=copy.deepcopy(self.raw)
        cfg["trace"]={"max_events":64}
        with self.assertRaises(ValueError):
            core.validate(cfg)

    def test_universal_capture_publishes_only_tar_and_recovers_crash_offline(self):
        import tarfile
        with tempfile.TemporaryDirectory() as d:
            temp=Path(d)
            private=temp/"research"/"_LOCAL_FILES"/"frida_captures"
            stage=temp/"research"/".research_run_staging"
            with patch.object(core,"FRIDA_STAGING",stage):
                folder=core.new_staged_capture()
                for name in ["config.json","manifest.json","events.jsonl","HANDOFF.md"]:
                    (folder/name).write_text(name,encoding="utf-8")
                (folder/"block_0001.bin").write_bytes(bytes(range(32)))
                (folder/"secret.wav").write_bytes(b"NEVER ARCHIVE ME")
                saved=core.publish_capture(folder,private)
                self.assertTrue(saved.is_file())
                self.assertFalse(folder.exists())
                self.assertEqual(list(private.iterdir()),[saved])
                with tarfile.open(saved,"r:gz") as t:
                    self.assertIn("frida_capture/block_0001.bin",t.getnames())
                    self.assertFalse(any("secret" in m for m in t.getnames()))
                # Wrapper crash before manifest finish retains loose private
                # files only in ignored STAGING, NEVER under _LOCAL_FILES.
                abandoned=core.new_staged_capture()
                (abandoned/"config.json").write_text("{}",encoding="utf-8")
                (abandoned/"events.jsonl").write_text(
                    '{"kind":"binary_hit","valid":true}\n',encoding="utf-8")
                (abandoned/"block_0001.bin").write_bytes(b"captured")
                reports=[]
                self.assertEqual(core.recover_frida_staging(private),0)
                self.assertEqual(len(list(private.glob("*.tar.gz"))),2)
                self.assertEqual(len([x for x in private.iterdir() if x.is_dir()]),0)
                self.assertFalse(abandoned.exists())
                recovered=private/(abandoned.name+".tar.gz")
                with tarfile.open(recovered) as t:
                    manifest=json.loads(t.extractfile("frida_capture/manifest.json").read())
                    self.assertEqual(manifest["status"],"RECOVERED_UNVERIFIED_INTERRUPTED")
                    self.assertFalse(manifest["original_runtime_verified"])
                    self.assertEqual(t.extractfile("frida_capture/block_0001.bin").read(),b"captured")

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
