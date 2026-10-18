"""Stage96 offline gates; never attach to Frida or start Sonicake Manager."""
from __future__ import annotations

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import frida_capture as runner
import frida_invocation as trace

AUDITOR_PATH = ROOT / 'research/htkpa/stages/stage96/audit_invocation_trace.py'
spec = importlib.util.spec_from_file_location('stage96_auditor', AUDITOR_PATH)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)
CFG = ROOT / 'research/htkpa/stages/stage96/frida.json'


def fixture_events():
    events = [{'kind': 'module_loaded', 'runtime_sha256': trace.ORIGINAL_SHA}]
    events += [{'kind': 'hook_attached', 'site': name} for name in trace.PINNED]
    events.append({'kind': 'ready', 'installed': 8, 'requested': 8})
    next_id, stacks = 0, {}

    def enter(site, tid=17, ret=None):
        nonlocal next_id
        next_id += 1
        stack = stacks.setdefault(tid, [])
        events.append({'kind': 'trace_enter', 'site': site, 'thread': tid,
                       'id': next_id, 'parent_id': stack[-1] if stack else None,
                       'rva': trace.PINNED[site], 'return_rva': hex(ret) if ret else None})
        stack.append(next_id)
        return next_id

    def leave(site, tid=17):
        stack = stacks[tid]
        events.append({'kind': 'trace_leave', 'site': site, 'thread': tid,
                       'id': stack.pop()})

    enter('wrapper_10e70')
    enter('nam_worker_e0e0', ret=0x10F84)
    leave('nam_worker_e0e0')
    enter('wav_fitter_d4a0', ret=0x11026)
    leave('wav_fitter_d4a0')
    enter('clone_10230', ret=0x110B2)
    enter('resample_be830', ret=0x104E6)
    enter('resample_ce00', ret=0xBF369)
    leave('resample_ce00')
    leave('resample_be830')
    leave('clone_10230')
    leave('wrapper_10e70')
    return events


def fixture_tar(directory, events, manifest_edit=None, config_edit=None):
    cfg = runner.validate(json.loads(CFG.read_text()))
    if config_edit:
        config_edit(cfg)
    manifest = {'mode': 'invocation_trace', 'expected_sha256': trace.ORIGINAL_SHA,
                'status': 'CAPTURED_HOOKS_ONLY', 'hook_count': 8,
                'state': {'runtime_verified': True, 'ready': True, 'hook_errors': 0}}
    if manifest_edit:
        manifest_edit(manifest)
    parts = {'config.json': json.dumps(cfg).encode(),
             'manifest.json': json.dumps(manifest).encode(),
             'events.jsonl': ''.join(json.dumps(x) + '\n' for x in events).encode(),
             'HANDOFF.md': b'Stage96 synthetic unit fixture'}
    path = directory / 'synthetic.tar.gz'
    with tarfile.open(path, 'w:gz') as tar:
        for name, data in parts.items():
            info = tarfile.TarInfo('frida_capture/' + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


class Stage96(unittest.TestCase):
    def setUp(self):
        self.cfg = json.loads(CFG.read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def audit(self, events=None, manifest_edit=None, config_edit=None):
        capture = fixture_tar(self.directory, fixture_events() if events is None else events,
                              manifest_edit, config_edit)
        with patch.object(auditor, 'digest', return_value=trace.ORIGINAL_SHA):
            return auditor.audit(self.directory / 'fake-original-not-read.dll', capture)

    def test_exact_pinned_config_normalized_and_no_reads(self):
        normalized = runner.validate(self.cfg)
        self.assertEqual(normalized['mode'], 'invocation_trace')
        self.assertEqual(len(normalized['sites']), 8)
        self.assertTrue(all(s['fields'] == [] for s in normalized['sites']))
        self.assertEqual(sum(s['max_hits'] for s in normalized['sites']), 32)
        js = runner.agent_source(normalized)
        self.assertEqual(js.count('Interceptor.attach('), 1)
        self.assertIn('onEnter()', js)
        self.assertIn('onLeave()', js)
        for dangerous in ('readByteArray', 'readPointer', 'writeByteArray', '.replace(', 'Stalker.', 'Memory.scan'):
            self.assertNotIn(dangerous, js)
        if shutil.which('node'):
            p = subprocess.run(['node', '--check'], input=js, text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js unavailable: JS behavioral test skipped')
    def test_real_agent_js_invocation_nesting_in_mocked_frida_runtime(self):
        js = runner.agent_source(runner.validate(self.cfg))
        # Exercise the actual generated JS using Frida-like NativePointer and
        # listener stubs, including the per-invocation object and return RVA.
        harness = r'''
const vm=require('node:vm');
class Ptr {
 constructor(n){this.n=n;}
 add(n){return new Ptr(this.n+n);}
 sub(p){return new Ptr(this.n-p.n);}
 compare(p){return Math.sign(this.n-p.n);}
 toString(radix=16){return radix===16?'0x'+this.n.toString(16):String(this.n);}
}
const base=0x180000000,hooks={},events=[];
const scope={
 Process:{getCurrentThreadId:()=>17,attachModuleObserver:obs=>obs.onAdded({
   name:'5868USB.dll',path:'pinned-original.dll',base:new Ptr(base),size:0x300000})},
 Interceptor:{attach:(p,callbacks)=>{hooks[p.n-base]=callbacks;}},
 send:x=>events.push(x),Date,JSON,Object,String,Error
};
vm.runInNewContext(JS_HERE,scope);
function enter(rva,ret){
 const ctx={threadId:17,returnAddress:new Ptr(base+ret)};
 hooks[rva].onEnter.call(ctx);return ctx;
}
function leave(rva,ctx){hooks[rva].onLeave.call(ctx);}
let root=enter(0x10e70,0x12345);
let nam=enter(0xe0e0,0x10f84);leave(0xe0e0,nam);
let fit=enter(0xd4a0,0x11026);leave(0xd4a0,fit);
let clone=enter(0x10230,0x110b2);
let resample=enter(0xbe830,0x104e6);
let inner=enter(0xce00,0xbf369);leave(0xce00,inner);
leave(0xbe830,resample);leave(0x10230,clone);leave(0x10e70,root);
process.stdout.write(JSON.stringify(events));
'''.replace('JS_HERE', json.dumps(js))
        run = subprocess.run(['node', '-e', harness], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        events = json.loads(run.stdout)
        self.assertEqual(len([e for e in events if e['kind']=='hook_attached']), 8)
        self.assertFalse(any(e['kind'] in ('trace_error','trace_limit') for e in events))
        self.assertEqual(len([e for e in events if e['kind']=='trace_enter']), 6)
        self.assertEqual(len([e for e in events if e['kind']=='trace_leave']), 6)
        events[0]['runtime_sha256'] = trace.ORIGINAL_SHA
        observed = self.audit(events)
        self.assertEqual(observed['status'],
                         'RUNTIME_SAME_WRAPPER_INVOCATION_NAM_THEN_FITTER_OBSERVED', observed)

    def test_unreviewed_address_limits_and_fields_rejected(self):
        bad = [lambda c: c['sites'][0].update(address='0xff41'),
               lambda c: c['sites'][0].update(max_hits=100),
               lambda c: c['sites'][0].update(fields=[]),
               lambda c: c.update(max_events=1000),
               lambda c: c.update(sha256='0'*64),
               lambda c: c.update(unsafe_js='send(1)'),
               lambda c: c['sites'][2].update(required=False),
               lambda c: c['sites'][1].update(name='wrapper_ff40')]
        for edit in bad:
            with self.subTest(edit=edit):
                cfg = json.loads(CFG.read_text())
                edit(cfg)
                with self.assertRaises(ValueError):
                    runner.validate(cfg)

    def test_verified_direct_10e70_route_with_nested_clone_resampler(self):
        result = self.audit()
        self.assertEqual(result['status'], 'RUNTIME_SAME_WRAPPER_INVOCATION_NAM_THEN_FITTER_OBSERVED')
        self.assertEqual(result['trace_entries'], 6)
        self.assertEqual(result['trace_leaves'], 6)
        route = result['validated_bound_routes'][0]
        self.assertEqual(route['wrapper'], 'wrapper_10e70')
        self.assertTrue(route['clone_branch_observed'])
        self.assertTrue(route['resampler_nested_observed'])
        self.assertFalse(result['completion_verified'])

    def test_same_thread_sequential_but_not_nested_is_not_bridge(self):
        events = fixture_events()
        # Make NAM/fitter root-level siblings; internally balanced still, but
        # cannot bind to the same wrapper invocation.
        for event in events:
            if event['kind'] == 'trace_enter' and event['site'] in ('nam_worker_e0e0','wav_fitter_d4a0'):
                event['parent_id'] = None
        self.assertEqual(self.audit(events)['status'], 'UNVERIFIED_TRACE')

    def test_correctly_closed_independent_worker_and_fitter_not_promoted(self):
        events = fixture_events()
        # Remove all wrapper/call-path hooks, then rebuild depth zero correctly.
        basics = events[:10]
        basics += [
            {'kind': 'trace_enter', 'id': 1, 'site': 'nam_worker_e0e0', 'rva': 0xE0E0, 'parent_id': None, 'thread': 17, 'return_rva': '0xeb23'},
            {'kind': 'trace_leave', 'id': 1, 'site': 'nam_worker_e0e0', 'thread': 17},
            {'kind': 'trace_enter', 'id': 2, 'site': 'wav_fitter_d4a0', 'rva': 0xD4A0, 'parent_id': None, 'thread': 17, 'return_rva': '0x11026'},
            {'kind': 'trace_leave', 'id': 2, 'site': 'wav_fitter_d4a0', 'thread': 17}]
        self.assertEqual(self.audit(basics)['status'], 'RUNTIME_HOOKS_VERIFIED_NO_BOUND_WRAPPER_ROUTE')

    def test_wrong_return_rva_fails_route_not_trace(self):
        events = fixture_events()
        for e in events:
            if e.get('kind') == 'trace_enter' and e['site'] == 'wav_fitter_d4a0':
                e['return_rva'] = '0x11027'
        self.assertEqual(self.audit(events)['status'], 'RUNTIME_HOOKS_VERIFIED_NO_BOUND_WRAPPER_ROUTE')

    def test_missing_leave_cross_thread_and_non_lifo_are_fail_closed(self):
        for transformation in (
            lambda es: es.pop(-1),
            lambda es: next(e for e in es if e['kind']=='trace_leave').update(thread=99),
            lambda es: next(e for e in es if e['kind']=='trace_leave').update(id=1),
            lambda es: es.append({'kind':'trace_limit', 'reason':'max_hits'}),
        ):
            with self.subTest(transformation=transformation):
                events=fixture_events()
                transformation(events)
                self.assertEqual(self.audit(events)['status'], 'UNVERIFIED_TRACE')

    def test_module_sha_hooks_and_config_fail_closed(self):
        events = fixture_events()
        events[0]['runtime_sha256'] = '0'*64
        self.assertEqual(self.audit(events)['status'], 'UNVERIFIED_TRACE')
        self.assertEqual(self.audit(manifest_edit=lambda m: m['state'].update(hook_errors=1))['status'], 'UNVERIFIED_TRACE')
        self.assertEqual(self.audit(config_edit=lambda c: c['sites'][0].update(rva=0xff41))['status'], 'UNVERIFIED_TRACE')

    def test_original_sha_required_independently_of_manifest(self):
        capture = fixture_tar(self.directory, fixture_events())
        with patch.object(auditor, 'digest', return_value='0'*64):
            with self.assertRaises(ValueError):
                auditor.audit(self.directory/'wrong.dll', capture)


if __name__ == '__main__':
    unittest.main()
