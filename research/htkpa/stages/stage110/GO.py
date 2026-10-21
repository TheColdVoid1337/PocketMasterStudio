#!/usr/bin/env python3
"""Stage110: original-data SHA-gated *offline* PCM16 floor-residual 1k topology.

Consumes existing PRIVATE Stage102/105/107/108/109 reports and original Stage97
ZIP. No fresh inference, proprietary runtime, fitting, resampling, or WAV output.
Requires a private input ZIP with exactly the seven named files. Writes exactly
one explicitly selected private JSON report (exclusive creation; no overwrite).
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys
import wave
from zipfile import ZipFile

FRAMES = 1_600_000
RATE = 48_000
GAIN = 0.31
BIN = 1_000
SCAN_START, SCAN_STOP = 1_300_000, 1_500_000
FIT_START, FIT_LATE, FIT_STOP, PARENT_BIN = 300_000, 1_100_000, 1_500_000, 20_000
QUASI_IDLE_START = 1_420_000
HIGHLIGHT_STARTS = (1_344_000, 1_345_000, 1_488_000)
EXPECTED_RECONCILIATION = (720000, 75525, 340000, 335248, 462, 4752)
STAGE97_SHA = '2f96dce1ae479a93975cf6247a88a4a08c11de7ae5cab41648faa0d7902e6f46'
SILENT = (1_020_000, 1_040_000, 1_060_000, 1_080_000, 1_360_000, 1_380_000, 1_400_000)
PRIVATE_MEMBERS = (
    'open_nam_prewarm_off.f64le', 'open_source_resampled_input_48000.f64le',
    'comparison_private.json', 'stage105_error_topology_private.json',
    'stage107_silence_floor_private.json', 'stage108_fixed_gain_pcm16_private.json',
    'stage109_floor_residual_topology_private.json',
)
VENDOR_MEMBERS = frozenset({'clo/', 'logs/', 'wavs/', 'clo/cloFile.clo',
                            'logs/tone_import.log', 'wavs/nam_input_wav.wav', 'wavs/outputFile.wav'})


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def required_zip(zip_path: Path, expected: tuple[str, ...]) -> dict[str, bytes]:
    with ZipFile(zip_path) as z:
        names = [i.filename for i in z.infolist()]
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('private archive member allowlist / duplicates failure')
        for info in z.infolist():
            if info.is_dir() or info.file_size > FRAMES * 8 + 1024:
                raise ValueError('private archive member shape/size failure')
        return {name: z.read(name) for name in expected}


def vendor_pcm(stage97: Path) -> bytes:
    if sha_file(stage97) != STAGE97_SHA:
        raise ValueError('original Stage97 archive SHA mismatch')
    with ZipFile(stage97) as z:
        members = [i.filename for i in z.infolist()]
        if len(members) != len(set(members)) or set(members) != VENDOR_MEMBERS:
            raise ValueError('Stage97 archive member allowlist failure')
        blob = z.read('wavs/outputFile.wav')
    with wave.open(io.BytesIO(blob), 'rb') as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype()) != (2,2,RATE,3_360_000,'NONE'):
            raise ValueError('original Stage97 outputFile.wav format failure')
        return w.readframes(FRAMES)


def candidate_floor(x: float) -> int:
    if not math.isfinite(x):
        raise ValueError('nonfinite open-NAM sample')
    return max(-32768, min(32767, math.floor(GAIN * x * 32768.0)))


def metrics_at(vendor: bytes, output: bytes, di: bytes, start: int, stop: int) -> dict:
    if not 0 <= start < stop <= FRAMES:
        raise ValueError('invalid bin indices')
    count = large = signed = squared = zero_di = max_abs = 0
    first_gt1 = last_gt1 = first_nonzero_di = last_nonzero_di = None
    di_energy = reference_energy = open_energy = 0.0
    for i in range(start, stop):
        a, b = struct.unpack_from('<hh', vendor, i * 4)
        if a != b:
            raise ValueError('Manager WAV left/right channel mismatch')
        x = struct.unpack_from('<d', output, i * 8)[0]
        input_sample = struct.unpack_from('<d', di, i * 8)[0]
        if not math.isfinite(input_sample):
            raise ValueError('nonfinite candidate DI')
        delta = candidate_floor(x) - a
        magnitude = abs(delta)
        count += magnitude != 0
        large += magnitude > 1
        signed += delta
        squared += delta * delta
        max_abs = max(max_abs, magnitude)
        if magnitude > 1:
            if first_gt1 is None:
                first_gt1 = i
            last_gt1 = i
        if input_sample == 0.0:
            zero_di += 1
        else:
            if first_nonzero_di is None:
                first_nonzero_di = i
            last_nonzero_di = i
        di_energy += input_sample * input_sample
        reference_energy += (a / 32768.0)**2
        open_energy += x*x
    n = stop-start
    return {
        'start':start, 'stop_exclusive':stop, 'frames':n,
        'mismatch_frames':count, 'abs_error_gt_1_lsb_frames':large,
        'rms_error_lsb':math.sqrt(squared/n), 'mean_signed_error_lsb':signed/n,
        'max_abs_error_lsb':max_abs,
        'di_nonzero_frames':n-zero_di, 'candidate_di_rms':math.sqrt(di_energy/n),
        'manager_rms':math.sqrt(reference_energy/n),'open_rms':math.sqrt(open_energy/n),
        'first_gt1_index':first_gt1, 'last_gt1_index':last_gt1,
        'first_nonzero_di_index':first_nonzero_di,'last_nonzero_di_index':last_nonzero_di,
    }


def read_inputs(private_zip: Path, stage97_zip: Path) -> tuple[dict[str, bytes], dict, bytes]:
    members=required_zip(private_zip, PRIVATE_MEMBERS)
    if len(members['open_nam_prewarm_off.f64le']) != FRAMES*8 or len(members['open_source_resampled_input_48000.f64le']) != FRAMES*8:
        raise ValueError('invalid 1.6M f64 source sizes')
    js={name:json.loads(members[name]) for name in PRIVATE_MEMBERS if name.endswith('.json')}
    s102=js['comparison_private.json'];s105=js['stage105_error_topology_private.json'];s107=js['stage107_silence_floor_private.json'];s108=js['stage108_fixed_gain_pcm16_private.json'];s109=js['stage109_floor_residual_topology_private.json']
    base_sha=sha(members['open_nam_prewarm_off.f64le'])
    if (s102.get('stage')!=102 or s102.get('status')!='SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED'
        or s102.get('vendor_resampler_parity_verified') is not False
        or s102.get('frames_compared_from_start')!=FRAMES
        or base_sha!=s102['conditions']['off']['open_output_sha256']
        or sha(members['open_source_resampled_input_48000.f64le'])!=s102['resampled_input_sha256']
        or s105.get('stage')!=105 or s105.get('status')!='STAGE105_OFFLINE_GAIN_ENERGY_LAG_TOPOLOGY_COMPLETED'
        or s107.get('stage')!=107 or s107.get('status')!='STAGE107_SHA_GATED_SILENCE_FLOOR_INSPECTION_COMPLETED'
        or s107.get('silence_starts')!=list(SILENT)
        or s108.get('stage')!=108 or s108.get('status')!='STAGE108_OFFLINE_FIXED_GAIN_PCM16_OUTPUT_TEST_COMPLETED'
        or s108.get('source_stage102_report_sha256')!=sha(members['comparison_private.json'])
        or s108.get('open_source_cpp_sha256')!=base_sha
        or s109.get('stage')!=109 or s109.get('status')!='STAGE109_OFFLINE_FIXED_FLOOR_RESIDUAL_TOPOLOGY_COMPLETED'
        or s109.get('source_stage108_report_sha256')!=sha(members['stage108_fixed_gain_pcm16_private.json'])
        or s109.get('source_stage107_report_sha256')!=sha(members['stage107_silence_floor_private.json'])
        or s109.get('open_source_cpp_sha256')!=base_sha
        or s109.get('silent_di_20k_bins_excluded')!=list(SILENT)
        or s108.get('original_vendor_stage97_zip_sha256')!=STAGE97_SHA
        or s109.get('original_vendor_stage97_zip_sha256')!=STAGE97_SHA):
        raise ValueError('source SHA/status/policy provenance gate failed')
    return members,js,vendor_pcm(stage97_zip)


def analyze(members: dict[str, bytes], js: dict, wav_pcm: bytes) -> dict:
    x=members['open_nam_prewarm_off.f64le'];di=members['open_source_resampled_input_48000.f64le']
    if len(wav_pcm)!=FRAMES*4:
        raise ValueError('Manager 1.6M stereo PCM16 length mismatch')
    rows=[metrics_at(wav_pcm,x,di,s,min(s+BIN,SCAN_STOP)) for s in range(SCAN_START,SCAN_STOP,BIN)]
    # Independently recheck every Stage109 20k-window that was marked active, and
    # its entire early/late exact and >1 LSB count denominators.
    s109=js['stage109_floor_residual_topology_private.json']
    early_exact=late_exact=late_large=late_nonmatches=early_n=late_n=0
    for start in range(FIT_START,FIT_STOP,PARENT_BIN):
        if start in SILENT:
            continue
        p=metrics_at(wav_pcm,x,di,start,start+PARENT_BIN)
        prior=s109['fine_nonzero_di_20k_bins'][str(start)]['floor']
        if (p['mismatch_frames'] != PARENT_BIN-prior['exact_pcm16_count']
            or p['abs_error_gt_1_lsb_frames'] != prior['abs_error_gt_1_lsb_frames']):
            raise ValueError(f'Stage109 original 20k floor reconciliation failed at {start}')
        if start < FIT_LATE:
            early_n += PARENT_BIN; early_exact += PARENT_BIN-p['mismatch_frames']
        else:
            late_n += PARENT_BIN; late_exact += PARENT_BIN-p['mismatch_frames']
            late_large += p['abs_error_gt_1_lsb_frames'];late_nonmatches += p['mismatch_frames']
    if (early_n,early_exact,late_n,late_exact,late_large,late_nonmatches)!=EXPECTED_RECONCILIATION:
        raise ValueError('Stage109 group crosscheck failed')
    if len(rows)!=(SCAN_STOP-SCAN_START)//BIN:
        raise ValueError('1k grid accounting mismatch')
    # Cross-check the Stage105 candidate DI RMS at the previously questionable
    # quasi-idle bin. This diagnostic intentionally does not recategorize Stage109.
    m1420=metrics_at(wav_pcm,x,di,QUASI_IDLE_START,QUASI_IDLE_START+PARENT_BIN)
    prior1420=next(v for v in js['stage105_error_topology_private.json']['fine_20k'].values() if v['start']==QUASI_IDLE_START)
    if not math.isclose(m1420['candidate_di_rms'],prior1420['candidate_di_rms'],rel_tol=1e-9,abs_tol=1e-14):
        raise ValueError('Stage105 quiet-window DI RMS contradiction')
    gt1=[i for i in rows if i['abs_error_gt_1_lsb_frames']]
    lead=[r for r in rows if r['start'] in HIGHLIGHT_STARTS]
    return {
        'stage':110, 'status':'STAGE110_OFFLINE_1K_GT1_TOPOLOGY_COMPLETED',
        'sample_rate_hz':RATE, 'candidate':'clamp_s16(floor(0.31 * existing open NAM f64 * 32768))',
        'error_sign':'predicted_minus_manager_integer',
        'source_checks':'original Stage97 SHA + Stage102/105/107/108/109 chain and Stage109 full active 20k reconciliation',
        'source_reproducibility_gates_passed':True,
        'no_new_inference_resampling_vendor_runtime_fitter_or_device':True,
        'vendor_gain_quantizer_model_resampler_or_fitter_parity_verified':False,
        'scan_window':[SCAN_START,SCAN_STOP], 'one_k_bin_width':BIN,
        'bins_1k':rows,'bins_with_gt1':[{'start':r['start'],'gt1':r['abs_error_gt_1_lsb_frames'], 'mismatches':r['mismatch_frames'], 'max_abs_lsb':r['max_abs_error_lsb']} for r in gt1],
        'primary_hotspot_1k':max(gt1,key=lambda r:r['abs_error_gt_1_lsb_frames'])['start'],
        'stage109_reconciled':{'early_active_frames':early_n,'early_active_exact':early_exact,
         'late_active_frames':late_n,'late_active_exact':late_exact,'late_active_gt1':late_large,
         'late_active_mismatches':late_nonmatches},
        'quasi_idle_1420k':{'candidate_di_rms':m1420['candidate_di_rms'],
                           'nonzero_di_frames':m1420['di_nonzero_frames'],
                           'perfect_pcm16_match':m1420['mismatch_frames']==0},
        'highlights':[{'start':r['start'],'gt1':r['abs_error_gt_1_lsb_frames'],
                       'mismatches':r['mismatch_frames'],'di_nonzero_frames':r['di_nonzero_frames']} for r in lead],
    }


def run(private_zip: Path, stage97_zip: Path, output: Path) -> dict:
    # Enforce no-overwrite before expensive processing, exclusive write after
    # validation. Caller must choose a private, untracked output location.
    if output.exists():
        raise ValueError('refusing to overwrite existing Stage110 private report')
    members,js,wav=read_inputs(private_zip,stage97_zip)
    result=analyze(members,js,wav)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
        f.write('\n')
    return {k:v for k,v in result.items() if k not in ('bins_1k',)} | {'private_report':str(output)}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-inputs',type=Path,required=True)
    p.add_argument('--stage97-zip',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.private_inputs,a.stage97_zip,a.output),indent=2))

if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,RuntimeError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print('[Stage110] '+str(exc),file=sys.stderr)
        sys.exit(2)