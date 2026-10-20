#!/usr/bin/env python3
"""Stage107: offline silence-bin DC floor versus active residual audit.

Consumes SHA-gated EXISTING Stage102 original C++ f64/DI and authentic Stage97
Manager ZIP plus Stage105/106 private metrics; no inference, resampling, DLL,
FIR fitting, CLO generation or modification of originals.
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
PRIVATE_ROOT = ROOT / 'research/_LOCAL_FILES/stage102'
STAGE102_GO = ROOT / 'research/htkpa/stages/stage102/GO.py'
TOTAL_FRAMES = 1_600_000
FRAME_BYTES = 8
BIN = 20_000
FIT_START = 300_000
FIT_STOP = 1_500_000
OUTPUT_NAME = 'stage107_silence_floor_private.json'


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1_048_576), b''):
            h.update(chunk)
    return h.hexdigest()


def imported_stage102():
    s = importlib.util.spec_from_file_location('stage107_stage102', STAGE102_GO)
    if s is None or s.loader is None:
        raise ValueError('Stage102 source module missing')
    m = importlib.util.module_from_spec(s)
    sys.modules[s.name] = m
    s.loader.exec_module(m)
    return m


def checked_f64_bytes(path: Path, expected_sha: str) -> bytes:
    if not path.is_file() or path.stat().st_size != TOTAL_FRAMES * FRAME_BYTES or sha(path) != expected_sha:
        raise ValueError('Original Stage102 f64 input/output failed SHA256 or frame-size gate')
    return path.read_bytes()


def get_fine_rows(stage105: dict) -> list[dict]:
    raw = stage105.get('fine_20k')
    if not isinstance(raw, dict) or len(raw) != 60:
        raise ValueError('Need exactly 60 Stage105 fine 20k metrics')
    out = []
    for k in range(60):
        item = raw.get(f'fine_{k+1:02d}')
        start = FIT_START + k * BIN
        if not isinstance(item, dict) or (item.get('start'), item.get('stop_exclusive'),
            item.get('frames'), item.get('silent_or_degenerate')) != (start, start+BIN, BIN, False):
            raise ValueError(f'Stage105 fine bin metadata mismatch: index={k}')
        di = item.get('candidate_di_rms')
        if isinstance(di, bool) or not isinstance(di, (int,float)) or not math.isfinite(di) or di < 0:
            raise ValueError('Invalid Stage105 candidate DI RMS')
        out.append(item)
    return out


def analyze_window(wav_pcm_stereo: bytes, input_di_f64: bytes, output_open_f64: bytes,
                   start: int, stop: int) -> dict:
    """PCM16 histogram and f64 mean/variance; no interpolation or time/gain fitting."""
    if not (len(wav_pcm_stereo) == TOTAL_FRAMES*4 and len(input_di_f64) == TOTAL_FRAMES*8
            and len(output_open_f64) == TOTAL_FRAMES*8 and 0 <= start < stop <= TOTAL_FRAMES):
        raise ValueError('Mismatched validated data or invalid window')
    n = stop-start
    sx=sy=sxx=syy=sxy=sdi2=0.0
    count_nonzero_di=0
    pcm=Counter()
    open_min=float('inf');open_max=float('-inf')
    for i in range(start,stop):
        raw_v = struct.unpack_from('<h', wav_pcm_stereo, i*4)[0]
        y = raw_v/32768.0
        x = struct.unpack_from('<d', output_open_f64, i*8)[0]
        di = struct.unpack_from('<d', input_di_f64, i*8)[0]
        if not math.isfinite(x) or not math.isfinite(di):
            raise ValueError('nonfinite f64 in existing Stage102 input/output')
        pcm[raw_v]+=1
        sx+=x;sy+=y;sxx+=x*x;syy+=y*y;sxy+=x*y;sdi2+=di*di
        count_nonzero_di += di != 0.0
        open_min=min(open_min,x);open_max=max(open_max,x)
    xm=sx/n;ym=sy/n
    xx=max(0.,sxx/n - xm*xm)
    yy=max(0.,syy/n - ym*ym)
    if sxx <= 0:
        gain = None; residual_rms = None
    else:
        gain=sxy/sxx
        residual_rms=math.sqrt(max(0.0,(syy-2*gain*sxy+gain*gain*sxx)/n))
    error31=math.sqrt(max(0.0,(syy-2*0.31*sxy+(0.31*0.31)*sxx)/n))
    return {
        'start':start,'stop_exclusive':stop,'frames':n,
        'candidate_di_rms':math.sqrt(sdi2/n),
        'candidate_di_nonzero_frames':count_nonzero_di,
        'vendor_pcm16_unique_values_count':len(pcm),
        'vendor_pcm16_top_values':[{'sample_int16':k,'frames':v} for k,v in pcm.most_common(5)],
        'vendor_mean':ym,'vendor_std':math.sqrt(yy),'vendor_rms':math.sqrt(syy/n),
        'open_mean':xm,'open_std':math.sqrt(xx),'open_rms':math.sqrt(sxx/n),
        'open_min':open_min,'open_max':open_max,
        'gain_fit_open_to_vendor_diagnostic_only':gain,
        'gain_only_fit_residual_rms':residual_rms,
        'fixed_0p31_residual_rms_not_fitted':error31,
        'interpolation_or_lag_performed':False,
        'proprietary_gain_parameter_proven':False,
    }


def run(stage102_report: Path, stage97_zip: Path) -> dict:
    source = stage102_report.resolve(strict=True)
    if not source.is_relative_to(PRIVATE_ROOT.resolve()) or source.name != 'comparison_private.json':
        raise ValueError('Source must be an existing ignored Stage102 private report')
    work = source.parent
    dest = work / OUTPUT_NAME
    if dest.exists():
        raise ValueError('refusing to overwrite Stage107 original private result')
    s102 = json.loads(source.read_text(encoding='utf-8'))
    p105 = work / 'stage105_error_topology_private.json'
    p106 = work / 'stage106_metrics_audit_private.json'
    if not p105.is_file() or not p106.is_file():
        raise ValueError('Stage105/106 original private metrics reports missing')
    s105 = json.loads(p105.read_text(encoding='utf-8'))
    s106 = json.loads(p106.read_text(encoding='utf-8'))
    if (s102.get('stage') != 102 or s102.get('status') != 'SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED'
        or s102.get('frames_compared_from_start') != TOTAL_FRAMES
        or s102.get('vendor_resampler_parity_verified') is not False
        or s102.get('di_44100_pcm16_identical') is not True
        or s105.get('stage') != 105 or s105.get('status') != 'STAGE105_OFFLINE_GAIN_ENERGY_LAG_TOPOLOGY_COMPLETED'
        or s105.get('no_new_inference_or_vendordll') is not True
        or s106.get('stage') != 106 or s106.get('status') != 'STAGE106_PRIVATE_METRICS_ONLY_ENERGY_ASSOCIATION_COMPLETED'
        or s106.get('source_stage105_report_sha256') != sha(p105)):
        raise ValueError('Stage102/105/106 provenance or source report SHA mismatch')
    rows = get_fine_rows(s105)
    silent = [r for r in rows if r['candidate_di_rms'] == 0.0]
    if not silent:
        raise ValueError('No silent DI windows in Stage105; this gate is not applicable')
    top_absolute = s106.get('top_5_absolute_residual_energy_20k_bins')
    if not isinstance(top_absolute,list) or len(top_absolute)!=5:
        raise ValueError('Stage106 absolute residual top-five list missing')
    starts = {r['start'] for r in rows}
    targeted = {r['start'] for r in silent}
    targeted.update({r['start'] for r in rows if 1_300_000 <= r['start'] < 1_420_000})
    for row in top_absolute:
        if not isinstance(row,dict) or row.get('start') not in starts:
            raise ValueError('Invalid Stage106 top-five bin start')
        targeted.add(row['start'])
    di = checked_f64_bytes(work/'open_source_resampled_input_48000.f64le',s102['resampled_input_sha256'])
    op = checked_f64_bytes(work/'open_nam_prewarm_off.f64le',s102['conditions']['off']['open_output_sha256'])
    stage102 = imported_stage102()
    _, vendor_wav = stage102.authentic_wavs(stage97_zip)
    with wave.open(io.BytesIO(vendor_wav),'rb') as w:
        vendor_pcm = w.readframes(TOTAL_FRAMES)
    if len(vendor_pcm)!=TOTAL_FRAMES*4:
        raise ValueError('Original vendor output truncated before 1.6M frames')
    results={}
    for start in sorted(targeted):
        row = analyze_window(vendor_pcm,di,op,start,start+BIN)
        was_silent=(start in {r['start'] for r in silent})
        if was_silent and row['candidate_di_nonzero_frames']!=0:
            raise ValueError('Stage105 zero-DI fine bin is not exactly zero in SHA-pinned f64 input')
        if (not was_silent) and row['candidate_di_rms']==0.0:
            raise ValueError('Stage105 active-DI bin disagrees with source input')
        results[str(start)] = {'di_silent_bin':was_silent,**row}
    report={
        'stage':107,'status':'STAGE107_SHA_GATED_SILENCE_FLOOR_INSPECTION_COMPLETED',
        'method':'source-exact private SHA-verified Stage102 open NAM output and input + original Stage97 PCM16 WAV',
        'silence_bin_count':len(silent),'total_stage105_20k_bins':60,
        'silence_starts':[r['start'] for r in silent],
        'source_stage105_report_sha256':sha(p105),
        'source_stage106_report_sha256':sha(p106),
        'raw_input_and_open_output_sha_gated':True,
        'vendor_original_zip_sha_gated':True,
        'selected_20k_windows':results,
        'no_new_inference_or_conversion':True,
        'proprietary_fitter_parity_verified':False,
        'vendor_resampler_or_model_identity_verified':False,
        'clo_produced':False,
    }
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return {
        'status':report['status'],'silence_bin_count':len(silent),
        'silence_starts':report['silence_starts'],
        'zero_input_output_floor':[
            {'start':r['start'], 'vendor_pcm16_unique_values_count':results[str(r['start'])]['vendor_pcm16_unique_values_count'],
             'vendor_pcm16_top_values':results[str(r['start'])]['vendor_pcm16_top_values'][:3],
             'vendor_mean':results[str(r['start'])]['vendor_mean'],
             'vendor_std':results[str(r['start'])]['vendor_std'],
             'open_mean':results[str(r['start'])]['open_mean'],
             'open_std':results[str(r['start'])]['open_std'],
             'fixed_0p31_residual_rms':results[str(r['start'])]['fixed_0p31_residual_rms_not_fitted']}
            for r in silent],
        'selected_active_windows':[{'start':s, 'relative_rms_after_gain':results[str(s)]['gain_only_fit_residual_rms']/results[str(s)]['vendor_rms']}
                                   for s in sorted(targeted) if s not in {r['start'] for r in silent} and results[str(s)]['vendor_rms']>0],
        'private_report':str(dest),
        'vendor_parity_verified':False,
    }


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage102-report',type=Path,required=True)
    p.add_argument('--stage97-zip',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.stage102_report,a.stage97_zip),indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,json.JSONDecodeError) as exc:
        print('[Stage107] '+str(exc),file=sys.stderr)
        sys.exit(2)
