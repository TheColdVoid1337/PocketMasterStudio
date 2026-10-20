#!/usr/bin/env python3
"""Stage105: offline gain, energy, residual and integer-lag topology diagnostic.

Reads only existing SHA-gated Stage102-104 private data. Does not rerun inference,
import private raw samples to source control, or infer vendor fitter parity.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[4]
PRIVATE_ROOT = ROOT / 'research/_LOCAL_FILES/stage102'
STAGE102 = ROOT / 'research/htkpa/stages/stage102/GO.py'
FRAMES = 1_600_000
FIT_START = 300_000
FIT_END = 1_500_000
COARSE = 200_000
FINE = 20_000
MAX_LAG = 4


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def read_f64_checked(path: Path, expected: str) -> list[float]:
    if not path.is_file() or path.stat().st_size != FRAMES * 8 or sha(path) != expected:
        raise ValueError('original Stage102 input/output f64le SHA or size mismatch')
    vals = [x[0] for x in struct.iter_unpack('<d', path.read_bytes())]
    if not all(math.isfinite(v) for v in vals):
        raise ValueError('nonfinite existing f64 samples')
    return vals


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError('Stage102 module missing')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def estimate(y: list[float], x: list[float], start: int, stop: int,
             *, lag: int = 0, input_signal: list[float] | None = None) -> dict:
    """Fit y[i] ≈ gain*x[i+lag] with no intercept, on a fixed common domain.

    Positive lag means the tested open sample is later than Manager reference.
    """
    if len(y) != len(x) or not (0 <= start < stop <= len(y)):
        raise ValueError('invalid matching windows')
    if start + lag < 0 or stop - 1 + lag >= len(x):
        raise ValueError('lag outside signal bounds')
    if input_signal is not None and len(input_signal) != len(y):
        raise ValueError('input length mismatch')
    xx = xy = yy = sx = sy = d2 = di2 = 0.0
    n = stop - start
    for i in range(start, stop):
        xi, yi = x[i + lag], y[i]
        if not math.isfinite(xi) or not math.isfinite(yi):
            raise ValueError('nonfinite signal samples')
        xx += xi * xi
        xy += xi * yi
        yy += yi * yi
        sx += xi
        sy += yi
        d2 += (yi - xi) ** 2
        if input_signal is not None:
            di = input_signal[i]
            if not math.isfinite(di):
                raise ValueError('nonfinite candidate DI')
            di2 += di * di
    if xx <= 1e-26 or yy <= 1e-26:
        return {'start':start,'stop_exclusive':stop,'frames':n,'lag':lag,'silent_or_degenerate':True}
    g = xy / xx
    resid2 = max(0.0, yy - xy * xy / xx)
    rm = math.sqrt(yy / n)
    # With y=k*x+c, estimate the intercept on the SAME domain, for diagnosis.
    centered_xx = xx - sx * sx / n
    centered_xy = xy - sx * sy / n
    centered_yy = max(0.0, yy - sy * sy / n)
    if centered_xx > 1e-26:
        affine_gain = centered_xy / centered_xx
        dc_offset = (sy - affine_gain * sx) / n
        affine_resid2 = max(0.0, centered_yy - centered_xy * centered_xy / centered_xx)
        affine_norm = math.sqrt(affine_resid2 / yy)
    else:
        affine_gain = dc_offset = affine_norm = None
    max_res = max_abs_index = 0
    max_res = 0.0
    max_abs_index = start
    for i in range(start, stop):
        delta = abs(y[i] - g * x[i + lag])
        if delta > max_res:
            max_res = delta
            max_abs_index = i
    return {
        'start':start, 'stop_exclusive':stop, 'frames':n,
        'lag':lag,'silent_or_degenerate':False,
        'gain_open_to_manager':g,
        'reference_rms':rm,'open_rms':math.sqrt(xx/n),
        'candidate_di_rms':math.sqrt(di2/n) if input_signal is not None else None,
        'zero_lag_cosine_if_lag_zero':xy / math.sqrt(xx*yy) if lag == 0 else None,
        'relative_rms_residual_after_gain':math.sqrt(resid2 / yy),
        'rms_residual_after_gain':math.sqrt(resid2/n),
        'max_abs_residual_after_gain':max_res,
        'max_abs_residual_index':max_abs_index,
        'rms_before_gain':math.sqrt(d2/n),
        'affine_gain_diagnostic':affine_gain,
        'dc_offset_diagnostic':dc_offset,
        'relative_rms_residual_after_gain_and_dc':affine_norm,
    }


def lag_sweep(y: list[float], x: list[float], start: int, stop: int,
              max_lag: int = MAX_LAG) -> dict:
    """Optimize integer lag on IDENTICAL central samples for fair comparison."""
    if max_lag < 1 or stop - start <= 2 * max_lag:
        raise ValueError('lag window too small')
    center_start,center_stop=start+max_lag,stop-max_lag
    scans = [estimate(y,x,center_start,center_stop,lag=lag)
             for lag in range(-max_lag,max_lag+1)]
    viable = [r for r in scans if not r['silent_or_degenerate']]
    if not viable:
        return {'silent_or_degenerate':True,'scans':scans}
    best = min(viable,key=lambda d:d['relative_rms_residual_after_gain'])
    zero = next(r for r in viable if r['lag']==0)
    return {
        'silent_or_degenerate':False,
        'lag_convention':'compare vendor[i] against open[i+lag]',
        'common_start':center_start,'common_stop_exclusive':center_stop,
        'best_integer_lag':best['lag'],
        'best_relative_rms':best['relative_rms_residual_after_gain'],
        'zero_lag_relative_rms':zero['relative_rms_residual_after_gain'],
        'lag_search_only_diagnostic_not_vendor_provenance':True,
        'scans':scans,
    }


def windows() -> tuple[list[tuple[str,int,int]],list[tuple[str,int,int]]]:
    coarse = [(f'block_{i+1:02d}',start,start+COARSE)
              for i,start in enumerate(range(FIT_START,FIT_END,COARSE))]
    fine = [(f'fine_{i+1:02d}',start,start+FINE)
            for i,start in enumerate(range(FIT_START,FIT_END,FINE))]
    return coarse,fine


def run(stage102_report:Path,stage97_zip:Path)->dict:
    path=stage102_report.resolve(strict=True)
    if not path.is_relative_to(PRIVATE_ROOT.resolve()) or path.name!='comparison_private.json':
        raise ValueError('source must be existing Stage102 private comparison_private.json')
    work=path.parent
    dest=work/'stage105_error_topology_private.json'
    if dest.exists():raise ValueError('refusing to overwrite Stage105 private report')
    s102=json.loads(path.read_text(encoding='utf-8'))
    s103p=work/'stage103_gain_audit_private.json'
    s104p=work/'stage104_prewarm_diff_private.json'
    if not s103p.is_file() or not s104p.is_file():
        raise ValueError('Stage103/104 completed private reports missing')
    s103=json.loads(s103p.read_text(encoding='utf-8'))
    s104=json.loads(s104p.read_text(encoding='utf-8'))
    if (s102.get('stage')!=102 or s102.get('status')!='SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED'
        or s102.get('frames_compared_from_start')!=FRAMES
        or s102.get('vendor_resampler_parity_verified') is not False
        or s102.get('di_44100_pcm16_identical') is not True
        or s103.get('stage')!=103 or s103.get('status')!='STAGE103_OFFLINE_GAIN_WINDOW_DIAGNOSTIC_COMPLETED'
        or s104.get('stage')!=104 or s104.get('status')!='STAGE104_OFFLINE_PREWARM_DIFFERENCE_LOCALIZED'
        or s104['ranges']['fit_full_300k_1500k']['bitwise_equal'] is not True
        or s104['ranges']['fit_full_300k_1500k']['different_f64_word_count']!=0):
        raise ValueError('original Stage102/103/104 status/prewarm gates failed')
    x=read_f64_checked(work/'open_nam_prewarm_off.f64le',s102['conditions']['off']['open_output_sha256'])
    candidate=read_f64_checked(work/'open_source_resampled_input_48000.f64le',s102['resampled_input_sha256'])
    if (s103['conditions']['off']['open_output_sha256']!=s102['conditions']['off']['open_output_sha256']
        or s104['raw_output_sha256']['off']!=s102['conditions']['off']['open_output_sha256']):
        raise ValueError('Stage103/104 off-output hash conflict')
    s102mod=load_module(STAGE102,'stage105_stage102')
    _,wav48=s102mod.authentic_wavs(stage97_zip)
    y=s102mod.wav_first_n_vendor_samples(wav48,FRAMES)
    if len(y)!=FRAMES:raise ValueError('vendor sample count mismatch')
    coarse,fine=windows()
    coarse_metrics={}
    for tag,lo,hi in coarse:
        val=estimate(y,x,lo,hi,input_signal=candidate)
        prior=s103['conditions']['off']['metrics'][f'fit_block_{int(tag[-2:]):02d}_{lo}_{hi}']
        if val['silent_or_degenerate'] or abs(val['gain_open_to_manager']-prior['gain_open_to_manager_least_squares'])>5e-9:
            raise ValueError('Stage103 per-block gain cross-check failed')
        val['integer_lag_sweep']=lag_sweep(y,x,lo,hi)
        coarse_metrics[tag]=val
    fine_metrics={tag:estimate(y,x,lo,hi,input_signal=candidate) for tag,lo,hi in fine}
    result={'stage':105,'status':'STAGE105_OFFLINE_GAIN_ENERGY_LAG_TOPOLOGY_COMPLETED',
      'source_gate':'existing SHA-checked Stage102/103/104 files and original SHA-pinned Stage97 ZIP',
      'prewarm_fit_window_bitwise_equal':True,
      'candidate_resampler_vendor_parity_verified':False,
      'vendor_model_byte_identity_verified':False,'vendor_nam_numeric_parity_verified':False,
      'vendor_fitter_parity_verified':False,'no_new_inference_or_vendordll':True,
      'coarse_200k':coarse_metrics,'fine_20k':fine_metrics}
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    early=[coarse_metrics[f'block_{i:02d}'] for i in range(1,5)]
    late=[coarse_metrics[f'block_{i:02d}'] for i in range(5,7)]
    energy=lambda data:sum(d['rms_residual_after_gain']**2 for d in data)
    first4=energy(early);total=first4+energy(late)
    top=sorted([v for v in fine_metrics.values() if not v['silent_or_degenerate']],
               key=lambda v:v['relative_rms_residual_after_gain'],reverse=True)[:5]
    return {'status':result['status'],
      'early_first4_fraction_of_individually_fitted_residual_energy':first4/total if total else None,
      'coarse_200k_summary':[{k:v[k] for k in ('start','stop_exclusive','gain_open_to_manager',
               'reference_rms','candidate_di_rms','relative_rms_residual_after_gain',
               'relative_rms_residual_after_gain_and_dc','max_abs_residual_index')}
          | {'best_integer_lag':v['integer_lag_sweep'].get('best_integer_lag'),
             'lag_zero_residual':v['integer_lag_sweep'].get('zero_lag_relative_rms'),
             'lag_best_residual':v['integer_lag_sweep'].get('best_relative_rms')}
         for v in coarse_metrics.values()],
      'largest_relative_residual_20k_windows':[{k:v[k] for k in ('start','stop_exclusive','gain_open_to_manager','relative_rms_residual_after_gain','candidate_di_rms')} for v in top],
      'private_report':str(dest),
      'vendor_fitter_parity_verified':False}


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage102-report',type=Path,required=True)
    p.add_argument('--stage97-zip',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.stage102_report,a.stage97_zip),indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,json.JSONDecodeError) as exc:
        print('[Stage105] '+str(exc),file=sys.stderr)
        sys.exit(2)
