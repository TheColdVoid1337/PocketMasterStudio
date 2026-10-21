#!/usr/bin/env python3
"""Stage109: SHA-gated offline 0.31*open NAM -> floor(PCM16) residual topology.

No new NAM inference or proprietary Manager/DLL/fitter execution. Reads existing
private Stage102/107/108 reports and original SHA-pinned Stage97 vendor WAV.
All original WAV, NAM, f64 and private report bytes remain unmodified/private.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import sys
import wave

ROOT = Path(__file__).resolve().parents[4]
STAGE102_GO = ROOT / 'research/htkpa/stages/stage102/GO.py'
PRIVATE_ROOT = ROOT / 'research/_LOCAL_FILES/stage102'
FRAMES = 1_600_000
FIT_START, LATE_START, FIT_STOP = 300_000, 1_100_000, 1_500_000
BIN = 20_000
GAIN = 0.31
SILENCE_STARTS = (1_020_000, 1_040_000, 1_060_000, 1_080_000,
                  1_360_000, 1_380_000, 1_400_000)
REPORT = 'stage109_floor_residual_topology_private.json'


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for c in iter(lambda: f.read(1_048_576), b''):
            h.update(c)
    return h.hexdigest()


def load_stage102():
    s = importlib.util.spec_from_file_location('stage109_original_stage102', STAGE102_GO)
    if s is None or s.loader is None:
        raise ValueError('missing original Stage102 source')
    m = importlib.util.module_from_spec(s)
    sys.modules[s.name] = m
    s.loader.exec_module(m)
    return m


def encode_pcm16(x: float, mode: str) -> int:
    if not math.isfinite(x):
        raise ValueError('nonfinite original open NAM output')
    q = GAIN * x * 32768.0
    if not math.isfinite(q):
        raise ValueError('nonfinite scaled sample')
    if mode == 'floor':
        n = math.floor(q)
    elif mode == 'nearest_even':
        n = round(q)
    else:
        raise ValueError('unknown diagnostic PCM16 rounding mode')
    return max(-32768, min(32767, n))


def empty() -> dict:
    return {'frames':0,'exact':0,'within_1':0,'squared_error':0,
            'signed_error':0,'absolute_error':0,'max_abs_error':0,
            'positive_errors':0,'negative_errors':0,'large_abs_error_frames':0,
            'histogram':Counter()}


def add(stats: dict, predicted: int, original: int) -> None:
    d = predicted-original
    a = abs(d)
    stats['frames'] += 1
    stats['exact'] += d == 0
    stats['within_1'] += a <= 1
    stats['squared_error'] += d*d
    stats['signed_error'] += d
    stats['absolute_error'] += a
    stats['max_abs_error'] = max(stats['max_abs_error'],a)
    stats['positive_errors'] += d > 0
    stats['negative_errors'] += d < 0
    stats['large_abs_error_frames'] += a > 1
    if d in (-3,-2,-1,0,1,2,3):
        stats['histogram'][str(d)] += 1
    elif d < -3:
        stats['histogram']['<-3'] += 1
    else:
        stats['histogram']['>3'] += 1


def summary(a: dict) -> dict:
    n = a['frames']
    if n == 0: raise ValueError('empty active-data group')
    return {
        'frames':n,'exact_pcm16_count':a['exact'], 'exact_pcm16_fraction':a['exact']/n,
        'within_one_lsb_fraction':a['within_1']/n,
        'rms_error_pcm16_lsb':math.sqrt(a['squared_error']/n),
        'mean_signed_error_pcm16_lsb':a['signed_error']/n,
        'mean_abs_error_pcm16_lsb':a['absolute_error']/n,
        'max_abs_error_pcm16_lsb':a['max_abs_error'],
        'positive_error_frame_count':a['positive_errors'],
        'negative_error_frame_count':a['negative_errors'],
        'abs_error_gt_1_lsb_frames':a['large_abs_error_frames'],
        'integer_error_histogram_bounded':dict(sorted(a['histogram'].items()))
    }


def compare(vendor_pcm: bytes, open_f64: bytes) -> dict:
    if len(vendor_pcm) != FRAMES*4 or len(open_f64) != FRAMES*8:
        raise ValueError('source PCM16/f64 length does not match 1.6M-frame contract')
    if (FIT_STOP-FIT_START) % BIN or (LATE_START-FIT_START) % BIN or (FIT_STOP-LATE_START) % BIN:
        raise ValueError('window definition not a multiple of fine-bin width')
    if any(s < FIT_START or s+BIN > FIT_STOP or (s-FIT_START)%BIN for s in SILENCE_STARTS):
        raise ValueError('known silent bin outside fit window')
    silent = set(SILENCE_STARTS)
    groups={g:{m:empty() for m in ('floor','nearest_even')} for g in
            ('early_active','late_active','late_active_positive','late_active_negative')}
    fine={}
    late_floor_first = late_floor_last = None
    late_floor_mismatches = 0
    for start in range(FIT_START,FIT_STOP,BIN):
        stop=start+BIN
        if start in silent:
            continue
        region='early_active' if start<LATE_START else 'late_active'
        stats={m:empty() for m in ('floor','nearest_even')}
        for i in range(start,stop):
            left,right=struct.unpack_from('<hh',vendor_pcm,i*4)
            if left!=right: raise ValueError('original Manager output stereo channels differ')
            x=struct.unpack_from('<d',open_f64,i*8)[0]
            bins=('early_active',) if region=='early_active' else ('late_active',
                            'late_active_positive' if x>=0 else 'late_active_negative')
            for mode in ('floor','nearest_even'):
                pred=encode_pcm16(x,mode)
                add(stats[mode],pred,left)
                for g in bins:
                    add(groups[g][mode],pred,left)
                if region=='late_active' and mode=='floor' and pred!=left:
                    late_floor_mismatches += 1
                    if late_floor_first is None: late_floor_first=i
                    late_floor_last=i
        fine[str(start)]={'start':start,'stop_exclusive':stop,'region':region,
                          'floor':summary(stats['floor']),
                          'nearest_even':summary(stats['nearest_even'])}
    output_groups={g:{m:summary(v) for m,v in methods.items()} for g,methods in groups.items()}
    earliest=output_groups['early_active']['floor']
    late=output_groups['late_active']['floor']
    if earliest['frames']+late['frames']+len(silent)*BIN != FIT_STOP-FIT_START:
        raise ValueError('silent/active accounting error')
    if late['frames']-late['exact_pcm16_count'] != late_floor_mismatches:
        raise ValueError('late mismatch bookkeeping error')
    late_bins=[r for r in fine.values() if r['region']=='late_active']
    late_bins.sort(key=lambda x: (x['floor']['frames']-x['floor']['exact_pcm16_count']),reverse=True)
    return {
        'status':'STAGE109_OFFLINE_FIXED_FLOOR_RESIDUAL_TOPOLOGY_COMPLETED',
        'candidate':'clamp_s16(floor(0.31 * existing open NAM f64 * 32768))',
        'error_sign':'predicted_integer_minus_manager_integer',
        'fit_window':[FIT_START,FIT_STOP],
        'silent_di_20k_bins_excluded':sorted(silent),
        'groups':output_groups,
        'fine_nonzero_di_20k_bins':fine,
        'top_late_floor_mismatch_bins':[
            {'start':r['start'],'stop_exclusive':r['stop_exclusive'],
             'mismatch_frames':r['floor']['frames']-r['floor']['exact_pcm16_count'],
             'exact_fraction':r['floor']['exact_pcm16_fraction'],
             'rms_error_lsb':r['floor']['rms_error_pcm16_lsb'],
             'max_abs_error_lsb':r['floor']['max_abs_error_pcm16_lsb']}
            for r in late_bins[:8]],
        'late_floor_mismatch_frames':late_floor_mismatches,
        'late_floor_first_mismatch_index':late_floor_first,
        'late_floor_last_mismatch_index':late_floor_last,
        'no_nam_or_vendor_inference_or_dsp_rerun':True,
        'vendor_gain_quantizer_model_resampler_or_fitter_parity_verified':False,
    }


def run(stage108_report: Path, stage97_zip: Path) -> dict:
    report=stage108_report.resolve(strict=True)
    if not report.is_relative_to(PRIVATE_ROOT.resolve()) or report.name!='stage108_fixed_gain_pcm16_private.json':
        raise ValueError('must pass original private Stage108 report')
    work=report.parent
    dest=work/REPORT
    if dest.exists():
        raise ValueError('refusing to overwrite preexisting Stage109 private report')
    s108=json.loads(report.read_text(encoding='utf-8'))
    s102p=work/'comparison_private.json'
    s107p=work/'stage107_silence_floor_private.json'
    if not s102p.is_file() or not s107p.is_file():
        raise ValueError('Stage102/107 original reports missing')
    s102=json.loads(s102p.read_text(encoding='utf-8'))
    s107=json.loads(s107p.read_text(encoding='utf-8'))
    if (s108.get('stage')!=108 or s108.get('status')!='STAGE108_OFFLINE_FIXED_GAIN_PCM16_OUTPUT_TEST_COMPLETED'
        or s108.get('source_stage102_report_sha256')!=sha256(s102p)
        or s108.get('original_vendor_stage97_zip_sha256') is None
        or s102.get('stage')!=102 or s102.get('status')!='SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED'
        or s102.get('frames_compared_from_start')!=FRAMES
        or s102.get('vendor_resampler_parity_verified') is not False
        or s107.get('stage')!=107 or s107.get('status')!='STAGE107_SHA_GATED_SILENCE_FLOOR_INSPECTION_COMPLETED'
        or s107.get('silence_starts')!=list(SILENCE_STARTS)):
        raise ValueError('original Stage102/107/108 evidence provenance mismatch')
    openp=work/'open_nam_prewarm_off.f64le'
    expected=s102['conditions']['off']['open_output_sha256']
    if not openp.is_file() or openp.stat().st_size!=FRAMES*8 or sha256(openp)!=expected:
        raise ValueError('original Stage102 C++ output SHA or size mismatch')
    if s108.get('open_source_cpp_sha256')!=expected:
        raise ValueError('Stage108 output SHA differs from Stage102 original')
    stage102=load_stage102()
    if s108['original_vendor_stage97_zip_sha256']!=stage102.VENDOR_ARCHIVE_SHA:
        raise ValueError('original Stage97 vendor archive hash identity mismatch')
    _,vendor_wav=stage102.authentic_wavs(stage97_zip)
    with wave.open(io.BytesIO(vendor_wav),'rb') as reader:
        vendor_pcm=reader.readframes(FRAMES)
    result=compare(vendor_pcm,openp.read_bytes())
    # Revalidate Stage108 nearest-even *exact counts* with unchanged samples.
    baseline=s108['analysis']['aggregates']['fixed_0p31__nearest_even']
    for region,prior,silent_frames in (
        ('early_active','quiet_early_300k_1100k',len([v for v in SILENCE_STARTS if v<LATE_START])*BIN),
        ('late_active','loud_late_1100k_1500k',len([v for v in SILENCE_STARTS if v>=LATE_START])*BIN),
    ):
        current=result['groups'][region]['nearest_even']
        previous=baseline[prior]
        if (current['frames']!=previous['frames']-silent_frames
            or current['exact_pcm16_count']!=previous['exact_pcm16_count']-silent_frames):
            raise ValueError('recalculated active nearest-even counts contradict Stage108 private baseline')
    result.update({'stage':109,'source_stage108_report_sha256':sha256(report),
       'source_stage107_report_sha256':sha256(s107p),'open_source_cpp_sha256':expected,
       'original_vendor_stage97_zip_sha256':stage102.VENDOR_ARCHIVE_SHA})
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    out={k:result['groups'][k] for k in ('early_active','late_active','late_active_positive','late_active_negative')}
    return {'status':result['status'],
            'active_floor_vs_nearest_even':out,
            'late_floor_mismatch_frames':result['late_floor_mismatch_frames'],
            'late_floor_first_mismatch_index':result['late_floor_first_mismatch_index'],
            'late_floor_last_mismatch_index':result['late_floor_last_mismatch_index'],
            'top_late_floor_mismatch_bins':result['top_late_floor_mismatch_bins'],
            'private_report':str(dest),
            'native_gain_or_quantizer_or_fitter_parity_verified':False}


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage108-report',type=Path,required=True)
    p.add_argument('--stage97-zip',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(run(args.stage108_report,args.stage97_zip),indent=2))

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,RuntimeError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print('[Stage109] '+str(exc),file=sys.stderr)
        sys.exit(2)
