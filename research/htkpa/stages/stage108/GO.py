#!/usr/bin/env python3
"""Stage108: offline test of candidate 0.31-scaled Open NAM -> Manager PCM16 output.

Original vendor 48-kHz WAV is read from SHA-pinned Stage97 ZIP; open f64 from
existing SHA-validated Stage102 output. No new NAM inference or vendor DLL.
Candidate quantizers are hypotheses, NOT established Sonicake algorithms.
"""
from __future__ import annotations

import argparse
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
FRAMES = 1_600_000
FIT_START = 300_000
FIT_END = 1_500_000
WINDOW_WIDTH = 200_000
REPORT_NAME = 'stage108_fixed_gain_pcm16_private.json'
FIXED_GAIN = 0.31
METHODS = ('nearest_even', 'nearest_away', 'trunc')
STAGE107_SILENT_BINS = (1_020_000, 1_040_000, 1_060_000, 1_080_000,
                        1_360_000, 1_380_000, 1_400_000)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as inp:
        for part in iter(lambda: inp.read(1_048_576), b''):
            h.update(part)
    return h.hexdigest()


def load_stage102():
    spec = importlib.util.spec_from_file_location('stage108_stage102', STAGE102_GO)
    if spec is None or spec.loader is None:
        raise ValueError('Stage102 source module not found')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def window_ranges() -> list[tuple[str, int, int]]:
    items = [('startup_0_300k', 0, FIT_START)]
    items.extend((f'fit_block_{i+1:02d}_{s}_{s+WINDOW_WIDTH}', s, s+WINDOW_WIDTH)
                 for i, s in enumerate(range(FIT_START, FIT_END, WINDOW_WIDTH)))
    items.append(('tail_1500k_1600k', FIT_END, FRAMES))
    return items


def quantize_sample(f64: float, gain: float, method: str) -> int:
    if not math.isfinite(f64) or not math.isfinite(gain) or gain <= 0:
        raise ValueError('nonfinite or invalid candidate f64/gain')
    q = f64 * gain * 32768.0
    if method == 'nearest_even':
        out = round(q)
    elif method == 'nearest_away':
        out = math.floor(q + 0.5) if q >= 0 else math.ceil(q - 0.5)
    elif method == 'trunc':
        out = math.trunc(q)
    else:
        raise ValueError('unknown candidate quantization method')
    return max(-32768, min(32767, out))


def empty_counts() -> dict:
    return dict(frames=0, exact=0, within_1=0, abs_err_sum=0,
                signed_err_sum=0, squared_err_sum=0, max_abs_err=0, clipped_candidate=0)


def add(count: dict, vendor: int, predicted: int, *, clipped: bool) -> None:
    delta = predicted - vendor
    ad = abs(delta)
    count['frames'] += 1
    count['exact'] += (delta == 0)
    count['within_1'] += (ad <= 1)
    count['abs_err_sum'] += ad
    count['signed_err_sum'] += delta
    count['squared_err_sum'] += delta * delta
    count['max_abs_err'] = max(ad, count['max_abs_err'])
    count['clipped_candidate'] += bool(clipped)


def join_counts(counts: list[dict]) -> dict:
    agg = empty_counts()
    for c in counts:
        for key in ('frames','exact','within_1','abs_err_sum','signed_err_sum',
                    'squared_err_sum','clipped_candidate'):
            agg[key] += c[key]
        agg['max_abs_err'] = max(agg['max_abs_err'], c['max_abs_err'])
    return agg


def finalize(c: dict) -> dict:
    if c['frames'] <= 0:
        raise ValueError('empty candidate result')
    n = c['frames']
    return {
        'frames':n,
        'exact_pcm16_count':c['exact'],
        'exact_pcm16_fraction':c['exact']/n,
        'within_one_pcm16_lsb_fraction':c['within_1']/n,
        'mean_abs_difference_pcm16_lsb':c['abs_err_sum']/n,
        'mean_signed_difference_pcm16_lsb':c['signed_err_sum']/n,
        'rms_difference_pcm16_lsb':math.sqrt(c['squared_err_sum']/n),
        'max_abs_difference_pcm16_lsb':c['max_abs_err'],
        'candidate_clipped_frames':c['clipped_candidate'],
        'gain_fitted_to_this_window':False,
        'no_lag_or_dc_fitted':True,
    }


def evaluate(vendor_pcm: bytes, open_f64le: bytes, *, gains: dict[str, float]) -> dict:
    if len(vendor_pcm) != FRAMES * 4 or len(open_f64le) != FRAMES * 8:
        raise ValueError('original output byte count mismatch')
    if set(gains) != {'fixed_0p31','stage103_global_fit_control'}:
        raise ValueError('expected fixed and diagnostic control gains')
    for v in gains.values():
        if not isinstance(v, float) or not math.isfinite(v) or v <= 0:
            raise ValueError('invalid candidate gain')
    labels = [f'{g}__{m}' for g in gains for m in METHODS]
    parts = window_ranges()
    stats = {name:{label:empty_counts() for label in labels} for name,_,_ in parts}
    silence = {label:empty_counts() for label in labels}
    silent_ranges = tuple((i,i+20_000) for i in STAGE107_SILENT_BINS)
    silence_vendor_values = set()
    windows_iter=iter(parts)
    _, lo, hi = next(windows_iter)
    widx = 0
    for i, ((left,right),(x,)) in enumerate(zip(struct.iter_unpack('<hh',vendor_pcm),
                                                 struct.iter_unpack('<d',open_f64le))):
        if left != right:
            raise ValueError('vendor stereo channels differ')
        if not math.isfinite(x):
            raise ValueError('nonfinite original open core f64')
        if i == hi:
            widx += 1
            _,lo,hi = parts[widx]
        target = stats[parts[widx][0]]
        quiet = any(a <= i < b for a,b in silent_ranges)
        if quiet:
            silence_vendor_values.add(left)
        for gname,gain in gains.items():
            raw = x * gain * 32768.0
            clip = raw >= 32767.5 or raw <= -32768.5
            for method in METHODS:
                key=f'{gname}__{method}'
                pred=quantize_sample(x,gain,method)
                add(target[key],left,pred,clipped=clip)
                if quiet:
                    add(silence[key],left,pred,clipped=clip)
    if widx != len(parts)-1:
        raise ValueError('not all source frames enumerated')
    if any(sum(c['frames'] for c in labels_per.values()) != (end-start)*len(labels)
           for (name,start,end),labels_per in zip(parts,stats.values())):
        raise ValueError('candidate accounting failure')
    summaries = {}
    for name,_,_ in parts:
        summaries[name] = {label:finalize(stats[name][label]) for label in labels}
    aggregate = {}
    n_fit = (FIT_END-FIT_START)//WINDOW_WIDTH
    n_early = 2*n_fit//3
    if n_fit < 2 or n_early < 1 or n_early >= n_fit:
        raise ValueError('invalid partition for quiet/loud groups')
    for label in labels:
        aggregate[label] = {
            'all_0_1600k':finalize(join_counts([stats[name][label] for name,_,_ in parts])),
            'fit_full_300k_1500k':finalize(join_counts([stats[parts[i][0]][label] for i in range(1,1+n_fit)])),
            'quiet_early_300k_1100k':finalize(join_counts([stats[parts[i][0]][label] for i in range(1,1+n_early)])),
            'loud_late_1100k_1500k':finalize(join_counts([stats[parts[i][0]][label] for i in range(1+n_early,1+n_fit)])),
            'seven_zero_candidate_DI_bins':finalize(silence[label]),
        }
    return {
        'sample_rate_hz':48000, 'frames':FRAMES,
        'method':'fixed gain then int16 saturation plus explicit rounding candidate; no output DSP rerun',
        'candidate_gains':gains,
        'candidate_rounding_methods':list(METHODS),
        'vendor_7x20k_zero_di_pcm16_distinct_values':sorted(silence_vendor_values),
        'groups':summaries,
        'aggregates':aggregate,
        'native_output_gain_or_quantizer_proven':False,
    }


def run(stage102_report: Path, stage97_zip: Path) -> dict:
    source=stage102_report.resolve(strict=True)
    if not source.is_relative_to(PRIVATE_ROOT.resolve()) or source.name != 'comparison_private.json':
        raise ValueError('must use original private Stage102 report')
    work=source.parent
    dest=work/REPORT_NAME
    if dest.exists():
        raise ValueError('refusing overwrite of prior Stage108 evidence')
    s102=json.loads(source.read_text(encoding='utf-8'))
    s103_path=work/'stage103_gain_audit_private.json'
    s107_path=work/'stage107_silence_floor_private.json'
    if not s103_path.is_file() or not s107_path.is_file():
        raise ValueError('completed Stage103 and Stage107 private reports required')
    s103=json.loads(s103_path.read_text(encoding='utf-8'))
    s107=json.loads(s107_path.read_text(encoding='utf-8'))
    if (s102.get('stage')!=102
        or s102.get('status')!='SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED'
        or s102.get('frames_compared_from_start')!=FRAMES
        or s102.get('di_44100_pcm16_identical') is not True
        or s102.get('vendor_resampler_parity_verified') is not False
        or s103.get('stage')!=103
        or s103.get('status')!='STAGE103_OFFLINE_GAIN_WINDOW_DIAGNOSTIC_COMPLETED'
        or s107.get('stage')!=107
        or s107.get('status')!='STAGE107_SHA_GATED_SILENCE_FLOOR_INSPECTION_COMPLETED'
        or s107.get('silence_starts')!=list(STAGE107_SILENT_BINS)):
        raise ValueError('Stage102/103/107 original provenance/status mismatch')
    control=s103['conditions']['off']['metrics']['fit_full_300k_1500k']['gain_open_to_manager_least_squares']
    if not isinstance(control,(float,int)) or isinstance(control,bool) or abs(control-0.3098390026147448)>1e-9:
        raise ValueError('original Stage103 global gain unexpectedly changed')
    file=work/'open_nam_prewarm_off.f64le'
    if file.stat().st_size != FRAMES * 8 or sha256(file)!=s102['conditions']['off']['open_output_sha256']:
        raise ValueError('Stage102 original C++ output SHA/size mismatch')
    s102mod=load_stage102()
    _,vendor_wav=s102mod.authentic_wavs(stage97_zip)
    with wave.open(io.BytesIO(vendor_wav),'rb') as wav:
        pcm=wav.readframes(FRAMES)
    data=evaluate(pcm,file.read_bytes(),gains={'fixed_0p31':FIXED_GAIN,
                                              'stage103_global_fit_control':float(control)})
    result={'stage':108,'status':'STAGE108_OFFLINE_FIXED_GAIN_PCM16_OUTPUT_TEST_COMPLETED',
            'source_stage102_report_sha256':sha256(source),
            'open_source_cpp_sha256':s102['conditions']['off']['open_output_sha256'],
            'original_vendor_stage97_zip_sha256':s102mod.VENDOR_ARCHIVE_SHA,
            'stage103_private_report_sha256':sha256(s103_path),
            'stage107_private_report_sha256':sha256(s107_path),
            'new_nam_inference_or_manager_execution':False,
            'vendor_resampler_or_model_identity_verified':False,
            'vendor_output_quantizer_or_gain_verified':False,
            'vendor_fitter_parity_verified':False,
            'analysis':data}
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    chosen=data['aggregates']['fixed_0p31__nearest_even']
    control_out=data['aggregates']['stage103_global_fit_control__nearest_even']
    return {'status':result['status'],
        'fixed_0p31_nearest_even':{name:chosen[name] for name in
             ('fit_full_300k_1500k','quiet_early_300k_1100k',
              'loud_late_1100k_1500k','seven_zero_candidate_DI_bins')},
        'global_gain_control_fit_exact_pcm16_fraction':control_out['fit_full_300k_1500k']['exact_pcm16_fraction'],
        'rounding_method_fit_exact_fractions':{
            method:data['aggregates'][f'fixed_0p31__{method}']['fit_full_300k_1500k']['exact_pcm16_fraction']
            for method in METHODS},
        'private_report':str(dest),
        'native_output_gain_or_quantizer_proven':False,
        'vendor_fitter_parity_verified':False}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage102-report',type=Path,required=True)
    parser.add_argument('--stage97-zip',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.stage102_report,args.stage97_zip),indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,json.JSONDecodeError) as e:
        print('[Stage108] '+str(e),file=sys.stderr)
        sys.exit(2)
