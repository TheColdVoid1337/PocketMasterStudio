#!/usr/bin/env python3
"""Offline Stage96 audit: exact original SHA and strict Frida call nesting.

No DLL execution, process inspection, network access, or sensitive bytes output.
Never equate parent/return-address evidence with CLO conversion completion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path

EXPECTED_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINNED = {
    'wrapper_ff40': 0xFF40, 'wrapper_10e70': 0x10E70,
    'nam_worker_e0e0': 0xE0E0, 'wav_fitter_d4a0': 0xD4A0,
    'clone_f940': 0xF940, 'clone_10230': 0x10230,
    'resample_be830': 0xBE830, 'resample_ce00': 0xCE00,
}
RETURNS = {
    'wrapper_ff40': {'nam_worker_e0e0': 0x10048,
                     'wav_fitter_d4a0': 0x100F0, 'clone_f940': 0x10172},
    'wrapper_10e70': {'nam_worker_e0e0': 0x10F84,
                      'wav_fitter_d4a0': 0x11026, 'clone_10230': 0x110B2},
    'clone_f940': {'resample_be830': 0xFA46},
    'clone_10230': {'resample_be830': 0x104E6},
    'resample_be830': {'resample_ce00': (0xBF369, 0xBF484)},
}
MEMBERS = {'config.json', 'manifest.json', 'events.jsonl', 'HANDOFF.md'}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def load_capture(path):
    blobs = {}
    with tarfile.open(path, 'r:gz') as tar:
        members = tar.getmembers()
        if len(members) != 4 or sum(m.size for m in members) > 2_000_000:
            raise ValueError('Stage96 capture member count or byte cap invalid')
        for m in members:
            if not m.isfile() or m.name != 'frida_capture/' + m.name.split('/')[-1]:
                raise ValueError('unsafe archive member')
            name = m.name.split('/')[-1]
            if name not in MEMBERS or name in blobs or m.size > 1_500_000:
                raise ValueError('unknown, duplicate or oversized member')
            blobs[name] = tar.extractfile(m).read()
    if set(blobs) != MEMBERS:
        raise ValueError('missing required archive members')
    config = json.loads(blobs['config.json'])
    manifest = json.loads(blobs['manifest.json'])
    events = [json.loads(line) for line in blobs['events.jsonl'].splitlines() if line.strip()]
    return config, manifest, events


def _rva(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-f]+', value):
        raise ValueError('non-canonical return RVA')
    return int(value, 16)


def audit(dll, capture):
    if digest(dll) != EXPECTED_SHA:
        raise ValueError('wrong original DLL SHA256')
    config, manifest, events = load_capture(capture)
    reasons = []
    event_budget = config.get('max_events') if type(config.get('max_events')) is int else 0
    if (config.get('mode') != 'invocation_trace'
            or config.get('module') != '5868USB.dll'
            or config.get('sha256') != EXPECTED_SHA
            or type(config.get('max_events')) is not int
            or not 64 <= config['max_events'] <= 128
            or type(config.get('max_depth')) is not int
            or not 4 <= config['max_depth'] <= 12):
        reasons.append('config_identity_or_bounds')
    sites = config.get('sites', [])
    if not isinstance(sites, list) or len(sites) != 8 or {
            s.get('name'): s.get('rva') for s in sites if isinstance(s, dict)} != PINNED:
        reasons.append('pinned_sites')
    if any(type(s.get('max_hits')) is not int or not 1 <= s['max_hits'] <= 6
           or s.get('fields') != [] for s in sites if isinstance(s, dict)):
        reasons.append('site_limits_or_fields')
    if {s.get('name') for s in sites if isinstance(s, dict) and s.get('required')} != {
            'nam_worker_e0e0', 'wav_fitter_d4a0'}:
        reasons.append('required_site_contract')
    if (manifest.get('mode') != 'invocation_trace'
            or manifest.get('expected_sha256') != EXPECTED_SHA
            or not manifest.get('state', {}).get('runtime_verified')
            or not manifest.get('state', {}).get('ready')
            or manifest.get('state', {}).get('hook_errors') != 0
            or manifest.get('hook_count') != 8):
        reasons.append('manifest_runtime_or_hook_gate')

    loaded = [e for e in events if e.get('kind') == 'module_loaded']
    hooks = [e.get('site') for e in events if e.get('kind') == 'hook_attached']
    ready = [e for e in events if e.get('kind') == 'ready']
    if len(loaded) != 1 or loaded[0].get('runtime_sha256') != EXPECTED_SHA:
        reasons.append('journal_runtime_sha')
    if len(hooks) != 8 or set(hooks) != set(PINNED):
        reasons.append('journal_hook_installation')
    if len(ready) != 1 or ready[0].get('installed') != 8 or ready[0].get('requested') != 8:
        reasons.append('journal_ready')
    if any(e.get('kind') in ('trace_error', 'trace_limit', 'hook_error', 'frida_error',
                             'binary_block') for e in events):
        reasons.append('frida_fault_or_trace_limit')

    calls, stacks, entries, leaves, site_counts = {}, {}, 0, 0, {}
    last_id = 0
    for index, e in enumerate(events):
        kind = e.get('kind')
        if kind not in ('trace_enter', 'trace_leave'):
            continue
        tid, invocation_id, site = e.get('thread'), e.get('id'), e.get('site')
        if type(tid) is not int or type(invocation_id) is not int or invocation_id < 1 or site not in PINNED:
            reasons.append('invalid_trace_event'); continue
        stack = stacks.setdefault(tid, [])
        if kind == 'trace_enter':
            entries += 1
            site_counts[site] = site_counts.get(site, 0) + 1
            parent = stack[-1] if stack else None
            if (invocation_id <= last_id or invocation_id in calls or e.get('parent_id') != parent
                    or e.get('rva') != PINNED[site]):
                reasons.append('id_parent_or_rva_mismatch'); continue
            last_id = invocation_id
            try:
                ret = _rva(e.get('return_rva'))
            except ValueError:
                reasons.append('invalid_return_rva'); continue
            calls[invocation_id] = {'id': invocation_id, 'site': site,
                                    'thread': tid, 'parent_id': parent,
                                    'return_rva': ret, 'enter_index': index,
                                    'leave_index': None}
            stack.append(invocation_id)
        else:
            leaves += 1
            if not stack or stack[-1] != invocation_id or calls.get(invocation_id, {}).get('site') != site:
                reasons.append('non_lifo_exit'); continue
            stack.pop()
            calls[invocation_id]['leave_index'] = index
    if entries > event_budget or entries + leaves > event_budget:
        reasons.append('journal_event_budget')
    if any(site_counts.get(s['name'], 0) > s['max_hits'] for s in sites if isinstance(s, dict)):
        reasons.append('journal_per_site_budget')
    if (isinstance(manifest.get('state', {}).get('site_hits'), dict)
            and site_counts != {k: v for k, v in manifest['state']['site_hits'].items() if v}):
        reasons.append('manifest_hit_count_mismatch')
    if entries != leaves or any(stacks.values()) or any(c['leave_index'] is None for c in calls.values()):
        reasons.append('unpaired_invocations')
    if not entries:
        reasons.append('no_invocations')
    children = {}
    for c in calls.values():
        children.setdefault(c['parent_id'], []).append(c)

    routes = []
    if not reasons:
        for root in calls.values():
            if root['site'] not in ('wrapper_ff40', 'wrapper_10e70'):
                continue
            immediate = children.get(root['id'], [])
            nam = [c for c in immediate if c['site'] == 'nam_worker_e0e0'
                   and c['return_rva'] == RETURNS[root['site']]['nam_worker_e0e0']]
            fitter = [c for c in immediate if c['site'] == 'wav_fitter_d4a0'
                      and c['return_rva'] == RETURNS[root['site']]['wav_fitter_d4a0']]
            for n in nam:
                for f in fitter:
                    if not (root['enter_index'] < n['enter_index'] < n['leave_index']
                            < f['enter_index'] < f['leave_index'] < root['leave_index']):
                        continue
                    clone_name = 'clone_f940' if root['site'] == 'wrapper_ff40' else 'clone_10230'
                    clones = [c for c in immediate if c['site'] == clone_name
                              and c['return_rva'] == RETURNS[root['site']][clone_name]
                              and f['leave_index'] < c['enter_index'] < c['leave_index'] < root['leave_index']]
                    branch = False
                    resampler = False
                    for cl in clones:
                        for be in children.get(cl['id'], []):
                            if be['site'] != 'resample_be830' or be['return_rva'] != RETURNS[clone_name]['resample_be830']:
                                continue
                            branch = True
                            resampler |= any(ce['site'] == 'resample_ce00'
                                             and ce['return_rva'] in RETURNS['resample_be830']['resample_ce00']
                                             for ce in children.get(be['id'], []))
                    routes.append({'wrapper': root['site'], 'same_invocation': True,
                                   'clone_branch_observed': branch,
                                   'resampler_nested_observed': resampler,
                                   'worker_return_rva': hex(n['return_rva']),
                                   'fitter_return_rva': hex(f['return_rva'])})
    if reasons:
        status = 'UNVERIFIED_TRACE'
    elif routes:
        status = 'RUNTIME_SAME_WRAPPER_INVOCATION_NAM_THEN_FITTER_OBSERVED'
    else:
        status = 'RUNTIME_HOOKS_VERIFIED_NO_BOUND_WRAPPER_ROUTE'
    return {
        'stage': 96, 'status': status, 'reasons': sorted(set(reasons)),
        'original_dll_sha256': EXPECTED_SHA,
        'captured_hooks_only': manifest.get('status') == 'CAPTURED_HOOKS_ONLY',
        'completion_verified': False, 'clo_completion_claim': False,
        'trace_entries': entries, 'trace_leaves': leaves,
        'validated_bound_routes': routes if not reasons else [],
        'evidence_boundary': 'Same-thread instrumented call-stack nesting if audited; no inter-thread correlation, DSP parity or CLO completion.'
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dll', type=Path, required=True)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    report = audit(args.dll, args.capture)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'stage': report['stage'], 'status': report['status'],
                      'trace_entries': report['trace_entries'],
                      'validated_routes': len(report['validated_bound_routes']),
                      'reasons': report['reasons']}))
    return 0 if report['status'] != 'UNVERIFIED_TRACE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
