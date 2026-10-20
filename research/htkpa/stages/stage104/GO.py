#!/usr/bin/env python3
"""HTKPA Stage104: SHA-gated offline prewarm ON/OFF f64le difference localization.

Analyzes ONLY existing Stage102/103 private outputs; no inference, no vendor DLL,
no new audio render, no model data or source file mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[4]
PRIVATE_ROOT = ROOT / 'research/_LOCAL_FILES/stage102'
FRAMES = 1_600_000
BYTES = 8 * FRAMES
WINDOWS = {
    'initial_0_300k': (0, 300_000),
    **{f'fit_block_{i+1:02d}_{start}_{start+200000}': (start, start+200_000)
       for i, start in enumerate(range(300_000, 1_500_000, 200_000))},
    'tail_1500k_1600k': (1_500_000, 1_600_000),
    'fit_full_300k_1500k': (300_000, 1_500_000),
    'all_0_1600k': (0, FRAMES),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def localized_diff(data_off: bytes, data_on: bytes, start: int, stop: int) -> dict:
    """Count exactly different f64 bit patterns and numeric delta in one range."""
    if len(data_off) != len(data_on) or len(data_off) % 8 or not (0 <= start < stop <= len(data_off)//8):
        raise ValueError('invalid comparison data/window')
    off = memoryview(data_off)
    on = memoryview(data_on)
    mismatch = 0
    signed_zero_only = 0
    first = last = None
    max_delta = 0.0
    sq = 0.0
    for idx in range(start, stop):
        a = struct.unpack_from('<d', off, idx*8)[0]
        b = struct.unpack_from('<d', on, idx*8)[0]
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError('nonfinite original C++ f64 sample')
        difference = a-b
        sq += difference*difference
        max_delta = max(max_delta, abs(difference))
        if off[idx*8:idx*8+8] != on[idx*8:idx*8+8]:
            mismatch += 1
            if first is None: first=idx
            last = idx
            if a == b: signed_zero_only += 1
    return {
        'start':start, 'stop_exclusive':stop, 'frames':stop-start,
        'different_f64_word_count':mismatch,
        'different_f64_word_fraction':mismatch/(stop-start),
        'first_different_sample_absolute':first,
        'last_different_sample_absolute':last,
        'numerically_equal_but_bitwise_different_count':signed_zero_only,
        'rms_difference':math.sqrt(sq/(stop-start)),
        'max_abs_difference':max_delta,
        'bitwise_equal':mismatch == 0,
    }


def run(report_path: Path) -> dict:
    report_path = report_path.resolve(strict=True)
    if not report_path.is_relative_to(PRIVATE_ROOT.resolve()):
        raise ValueError('Stage104 only reads existing private Stage102 run')
    if report_path.name != 'comparison_private.json':
        raise ValueError('expected Stage102 comparison_private.json')
    work = report_path.parent
    diag_path = work/'stage103_gain_audit_private.json'
    if not diag_path.is_file():
        raise ValueError('Stage103 original private report missing')
    output = work/'stage104_prewarm_diff_private.json'
    if output.exists():
        raise ValueError('refusing to overwrite existing Stage104 result')
    old = json.loads(report_path.read_text(encoding='utf-8'))
    diag = json.loads(diag_path.read_text(encoding='utf-8'))
    if (old.get('stage') != 102 or old.get('status') != 'SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED'
        or old.get('frames_compared_from_start') != FRAMES or old.get('di_44100_pcm16_identical') is not True
        or old.get('vendor_resampler_parity_verified') is not False):
        raise ValueError('Stage102 input report provenance mismatch')
    if (diag.get('stage') != 103 or diag.get('status') != 'STAGE103_OFFLINE_GAIN_WINDOW_DIAGNOSTIC_COMPLETED'
        or diag.get('prewarm_output_bitwise_equal') is not False):
        raise ValueError('Stage103 diagnostic report provenance mismatch')
    inputs = {}
    verified_shas = {}
    for name in ('off', 'on'):
        f = work/f'open_nam_prewarm_{name}.f64le'
        if not f.is_file() or f.stat().st_size != BYTES:
            raise ValueError('Stage102 raw output missing or wrong frame count')
        expected = old['conditions'][name]['open_output_sha256']
        if sha256(f) != expected or diag['conditions'][name]['open_output_sha256'] != expected:
            raise ValueError('Stage102/103 output SHA mismatch')
        inputs[name] = f.read_bytes()
        verified_shas[name] = expected
    if verified_shas['off'] == verified_shas['on']:
        raise ValueError('Stage103 reported differing outputs but original SHA equals')
    ranges = {label:localized_diff(inputs['off'], inputs['on'], *limits)
              for label, limits in WINDOWS.items()}
    report = {
        'stage':104,
        'status':'STAGE104_OFFLINE_PREWARM_DIFFERENCE_LOCALIZED',
        'evidence_class':'existing SHA-verified Stage102 open-core raw outputs; original Stage103 private report',
        'raw_output_sha256':verified_shas,
        'source_audio_or_vendor_dll_reexecuted':False,
        'new_nam_inference_performed':False,
        'ranges':ranges,
        'vendor_resampler_parity_verified':False,
        'vendor_model_identity_verified':False,
        'vendor_nam_parity_verified':False,
        'vendor_fitter_parity_verified':False,
    }
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return {
        'status':report['status'],
        'overall':ranges['all_0_1600k'],
        'first_300k':ranges['initial_0_300k'],
        'fitter_window':ranges['fit_full_300k_1500k'],
        'tail_100k':ranges['tail_1500k_1600k'],
        'fit_subwindows_differing':[name for name in WINDOWS if name.startswith('fit_block_') and not ranges[name]['bitwise_equal']],
        'private_report':str(output),
        'vendor_parity_verified':False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage102-report',type=Path,required=True)
    args = p.parse_args()
    print(json.dumps(run(args.stage102_report),indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,json.JSONDecodeError) as e:
        print('[Stage104] '+str(e),file=sys.stderr)
        sys.exit(2)
