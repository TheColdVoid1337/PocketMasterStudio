#!/usr/bin/env python3
"""Stage100: bounded real NAM Core/SonicMaster matched-signal scale × block sweep.

Real DSP executes ONLY when the operator runs `run`. All original models, raw
samples, model hashes and output hashes remain below ignored _LOCAL_FILES.
Neither vendor DLL nor production browser / SonicMaster workers are modified.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STAGE99 = ROOT / 'research/htkpa/stages/stage99/GO.py'
PRIVATE = ROOT / 'research/_LOCAL_FILES/stage100'
FRAMES = 8192
RATE = 48000
# Four controlled regimes. An inverted waveform is important for asymmetric amps.
LEVELS = (('quiet', 0.1), ('reference', 1.0), ('drive', 2.0), ('inverted', -1.0))
BLOCKS = (16, 64, 1024)
BASELINE_BLOCK = 64
BASELINE_INPUT_SHA = 'f54ab8b3d61cd8d36fafa316f6542f18ede669febd88901b7c974b299de7745e'


def import_module(path: Path, label: str):
    spec = importlib.util.spec_from_file_location(label, path)
    if spec is None or spec.loader is None:
        raise ValueError('Required stage module missing')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[label] = mod
    spec.loader.exec_module(mod)
    return mod


def stage99_module():
    return import_module(STAGE99, 'stage100_stage99_helper')


def make_stimulus(stage99, scale: float) -> bytes:
    if not math.isfinite(scale) or scale not in dict(LEVELS).values():
        raise ValueError('Stimulus scale is outside fixed Stage100 matrix')
    base = stage99.stimulus(RATE)
    if len(base) != FRAMES * 8:
        raise ValueError('Stage99 stimulus has unexpected framing')
    import hashlib
    if hashlib.sha256(base).hexdigest() != BASELINE_INPUT_SHA:
        raise ValueError('Stage99 deterministic input no longer has the accepted SHA')
    if scale == 1.0:
        return base  # preserves exact Stage99 input bits
    vals = (x[0] for x in struct.iter_unpack('<d', base))
    result = b''.join(struct.pack('<d', value * scale) for value in vals)
    if len(result) != FRAMES * 8:
        raise ValueError('Scaled input changed frame count')
    return result


def preflight(model: Path, build_dir: Path | None = None):
    """Validate *everything possible* before writing a single sample."""
    if not shutil.which('node'):
        raise ValueError('Node.js executable missing')
    s99 = stage99_module()
    mode = s99.model_mode(model)
    if mode not in ('slim_1.0_last_wavenet', 'plain_wavenet'):
        raise ValueError('Unrecognized NAM model mode')
    build = build_dir or s99.BUILD
    manifest_path = build / 'stage99_sonicmaster_build.json'
    worker = build / 'sonicmaster_raw.js'
    if not manifest_path.is_file() or not worker.is_file():
        raise ValueError('Stage99 real compiled diagnostic missing; run Stage99 prepare')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    required = s99.sources()
    if (any(manifest.get(k) != v for k, v in required.items())
            or manifest.get('compile_mode') != 'dart compile js -O2'
            or manifest.get('model_rate_hz') != RATE or manifest.get('frames') != FRAMES
            or manifest.get('resampler_used') is not False
            or manifest.get('fitter_used') is not False
            or manifest.get('worker_js_sha256') != s99.sha(worker)):
        raise ValueError('Stage99 compiled diagnostic/source provenance mismatch')
    s98 = s99.load_stage98()
    s98.verify_source(s98.DEFAULT_SOURCE)
    native_manifest = s98.DEFAULT_BUILD / s98.MARKER
    if not native_manifest.is_file():
        raise ValueError('Stage98 genuine compiled NAM Core manifest missing')
    cm = json.loads(native_manifest.read_text(encoding='utf-8'))
    binary = s98.DEFAULT_BUILD / cm.get('binary_name', '')
    if (cm.get('source_commit') != s98.PIN or cm.get('real_upstream_compile') is not True
            or cm.get('bridge_sha256') != s98.sha(s98.HERE / 'htkpa_nam_probe.cpp')
            or cm.get('cmake_sha256') != s98.sha(s98.HERE / 'CMakeLists.txt')
            or not binary.is_file() or s98.sha(binary) != cm.get('binary_sha256')):
        raise ValueError('Stage98 rebuilt original upstream binary/hash not verified')
    # Confirm the known Stage99 raw f64 stimulus before any output directory.
    make_stimulus(s99, 1.0)
    return s99, s98, mode, worker, manifest, cm


def label_for(stage99, model: Path, mode: str) -> str:
    return stage99.sha(model)[:16] + '_48k_scale_block_v1_' + mode


def run(model: Path, private_root: Path = PRIVATE, build_dir: Path | None = None) -> dict:
    s99, s98, mode, worker, diagnostic, native = preflight(model, build_dir)
    folder = private_root / 'sweeps' / label_for(s99, model, mode)
    if folder.exists():
        raise ValueError('Stage100 sweep output already exists; refuse to overwrite')
    folder.mkdir(parents=True)
    progress = {'status': 'IN_PROGRESS', 'stage': 100,
                'expected_core_runs': len(LEVELS) * len(BLOCKS),
                'expected_sonicmaster_runs': len(LEVELS)}
    (folder / 'RUN_STATUS.json').write_text(json.dumps(progress, indent=2) + '\n', encoding='utf-8')
    conditions = []
    for level_name, scale in LEVELS:
        inp = folder / (level_name + '_input.f64le')
        inp.write_bytes(make_stimulus(s99, scale))
        dart_path = folder / (level_name + '_sonicmaster.f64le')
        dart_result = json.loads(s99.execute([
            'node', str(s99.NODE_RUNNER), '--model', str(model),
            '--worker-js', str(worker), '--input-f64le', str(inp),
            '--output-f64le', str(dart_path)]))
        if (dart_result.get('status') != 'SONICMASTER_DART_RAW_DIAGNOSTIC_COMPLETED'
                or dart_result.get('frames') != FRAMES
                or dart_result.get('input_sha256') != s99.sha(inp)
                or dart_result.get('output_sha256') != s99.sha(dart_path)):
            raise ValueError('Stage100 SonicMaster output/provenance mismatch')
        sonic_values = s99.doubles(dart_path)
        core_values = {}
        records = []
        for block in BLOCKS:
            cpp_path = folder / f'{level_name}_core_block{block}.f64le'
            core_result = s98.run(s98.DEFAULT_BUILD, model, inp, cpp_path, RATE,
                                  block, 'off', 1.0 if mode.startswith('slim') else None)
            if core_result.get('status') != 'NAM_CORE_UPSTREAM_INFERENCE_COMPLETED':
                raise ValueError('NAM Core did not complete inference')
            cpp_values = s99.doubles(cpp_path)
            core_values[block] = cpp_values
            # No latency shift, gain fitting, trimming or normalization applied.
            records.append({'block': block, 'core_sha256': s99.sha(cpp_path),
                            'core_vs_sonicmaster': s99.metrics(cpp_values, sonic_values)})
        baseline = core_values[BASELINE_BLOCK]
        invariance = {
            str(block): s99.metrics(baseline, core_values[block])
            for block in BLOCKS if block != BASELINE_BLOCK
        }
        conditions.append({'name': level_name, 'scale': scale,
                           'input_sha256': s99.sha(inp),
                           'sonicmaster_output_sha256': s99.sha(dart_path),
                           'core_by_block': records,
                           'core_block64_vs_other_blocks': invariance})
    result = {
        'status': 'STAGE100_OPERATOR_REAL_SWEEP_COMPLETED',
        'stage': 100, 'comparison': 'open C++ NAM Core vs SonicMaster Dart WaveNet only',
        'model_mode': mode, 'model_sha256': s99.sha(model),
        'sample_rate_hz': RATE, 'frames_per_run': FRAMES,
        'core_prewarm': 'off', 'core_slim': 1.0 if mode.startswith('slim') else None,
        'core_blocks': list(BLOCKS), 'base_stimulus_sha256': BASELINE_INPUT_SHA,
        'core_binary_sha256': native['binary_sha256'],
        'sonicmaster_worker_sha256': diagnostic['worker_js_sha256'],
        'core_runs': len(BLOCKS) * len(LEVELS), 'sonicmaster_runs': len(LEVELS),
        'resampled': False, 'fitted': False, 'vendor_dll_parity_verified': False,
        'clo_generated': False, 'engine_identical_general_case_verified': False,
        'conditions': conditions}
    (folder / 'sweep_private.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    (folder / 'RUN_STATUS.json').write_text(json.dumps({'status': 'COMPLETED', 'stage': 100}, indent=2) + '\n', encoding='utf-8')
    # Operator-facing summary has no private model hash / raw sample bytes.
    summary = {
        'status': result['status'], 'stage': 100,
        'model_mode': mode, 'frames_per_run': FRAMES,
        'core_runs': result['core_runs'], 'sonicmaster_runs': result['sonicmaster_runs'],
        'vendor_dll_parity_verified': False, 'clo_generated': False,
        'levels': [{
            'name': c['name'], 'scale': c['scale'],
            'core_vs_sonicmaster': [
                {'block': r['block'], 'rms_error': r['core_vs_sonicmaster']['rms_error'],
                 'max_abs_error': r['core_vs_sonicmaster']['max_abs_error'],
                 'normalized_rms_error': r['core_vs_sonicmaster']['normalized_rms_error']}
                for r in c['core_by_block']],
            'core_chunk_invariance': {key: {
                'rms_error': value['rms_error'],
                'max_abs_error': value['max_abs_error'],
                'bitwise_equal': value['bitwise_equal']}
                for key, value in c['core_block64_vs_other_blocks'].items()}
        } for c in conditions]
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('doctor', 'run'))
    ap.add_argument('--model', type=Path, required=True)
    a = ap.parse_args()
    if a.action == 'doctor':
        s99, _, mode, worker, diagnostic, native = preflight(a.model)
        result = {'status': 'STAGE100_PREFLIGHT_PASS', 'stage': 100,
                  'model_mode': mode, 'sample_rate_hz': RATE, 'frames': FRAMES,
                  'levels': [v for v, _ in LEVELS], 'blocks': list(BLOCKS),
                  'planned_native_runs': len(LEVELS) * len(BLOCKS),
                  'diagnostic_worker_sha256': diagnostic['worker_js_sha256'],
                  'core_binary_sha256': native['binary_sha256'],
                  'private_target_exists': (PRIVATE / 'sweeps' / label_for(s99, a.model, mode)).exists()}
    else:
        result = run(a.model)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as exc:
        print('[Stage100] ' + str(exc), file=sys.stderr)
        sys.exit(2)
