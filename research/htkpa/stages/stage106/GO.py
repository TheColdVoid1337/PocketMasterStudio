#!/usr/bin/env python3
"""HTKPA Stage106: offline metrics-only fine-window energy/residual attribution.

Reads the completed *private* Stage105 summary JSON, not WAV or raw f64.
This is descriptive correlation, never proof of a proprietary DSP behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
PRIVATE_ROOT = ROOT / 'research/_LOCAL_FILES/stage102'
FIT_START = 300_000
FIT_STOP = 1_500_000
FINE = 20_000
COARSE = 200_000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as src:
        for buf in iter(lambda: src.read(1024 * 1024), b''):
            h.update(buf)
    return h.hexdigest()


def finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f'non-numeric {label}')
    x = float(value)
    if not math.isfinite(x) or x < 0:
        raise ValueError(f'invalid {label}')
    return x


def get_windows(payload: dict, label: str, width: int) -> list[dict]:
    raw = payload.get(label)
    total = (FIT_STOP - FIT_START) // width
    if not isinstance(raw, dict) or len(raw) != total:
        raise ValueError(f'expected {total} {label} windows')
    windows: list[dict] = []
    for i in range(total):
        key = f'{"block" if width == COARSE else "fine"}_{i+1:02d}'
        if key not in raw or not isinstance(raw[key], dict):
            raise ValueError(f'missing {key}')
        row = raw[key]
        a, b = FIT_START + i * width, FIT_START + (i + 1) * width
        if row.get('start') != a or row.get('stop_exclusive') != b or row.get('frames') != width or row.get('silent_or_degenerate') is not False:
            raise ValueError(f'invalid time/window metadata for {key}')
        for field in ('reference_rms','open_rms','candidate_di_rms',
                      'rms_residual_after_gain','relative_rms_residual_after_gain'):
            finite_nonnegative(row.get(field), f'{key}.{field}')
        ref = row['reference_rms']
        norm = row['relative_rms_residual_after_gain']
        residual = row['rms_residual_after_gain']
        if ref <= 0 or abs(residual - ref * norm) > 1e-8 * max(ref, 1e-8):
            raise ValueError(f'inconsistent RMS normalization for {key}')
        windows.append(row)
    return windows


def energy_stats(rows: list[dict]) -> dict:
    if not rows: raise ValueError('empty group')
    reference2 = sum(r['reference_rms']**2 for r in rows)
    residual2 = sum(r['rms_residual_after_gain']**2 for r in rows)
    di2 = sum(r['candidate_di_rms']**2 for r in rows)
    n = len(rows)
    return {
        'bins':n,
        'reference_rms':math.sqrt(reference2/n),
        'di_rms':math.sqrt(di2/n),
        'individual_gain_fit_residual_rms':math.sqrt(residual2/n),
        'individual_gain_fit_residual_normalized':math.sqrt(residual2/reference2) if reference2 > 0 else None,
        'residual_energy_sum_per_equal_length_bin':residual2,
        'reference_energy_sum_per_equal_length_bin':reference2,
        'quantization_step_pcm16':1/32768,
        'residual_rms_in_pcm16_steps':math.sqrt(residual2/n)*32768,
    }


def average_ranks(seq: list[float]) -> list[float]:
    out = [0.0] * len(seq)
    for v in set(seq):
        ix = [i for i, x in enumerate(seq) if x == v]
        places = [j for j, x in enumerate(sorted(seq)) if x == v]
        avg = (places[0]+places[-1])/2+1
        for i in ix: out[i]=avg
    return out


def rank_correlation(x: list[float], y: list[float]) -> float | None:
    if len(x)!=len(y) or len(x)<3: raise ValueError('rank sample mismatch')
    a,b=average_ranks(x),average_ranks(y)
    am,bm=sum(a)/len(a),sum(b)/len(b)
    xx=sum((u-am)**2 for u in a)
    yy=sum((v-bm)**2 for v in b)
    return sum((u-am)*(v-bm) for u,v in zip(a,b))/math.sqrt(xx*yy) if xx*yy else None


def analyze(payload: dict) -> dict:
    if (payload.get('stage') != 105
        or payload.get('status') != 'STAGE105_OFFLINE_GAIN_ENERGY_LAG_TOPOLOGY_COMPLETED'
        or payload.get('no_new_inference_or_vendordll') is not True
        or payload.get('candidate_resampler_vendor_parity_verified') is not False
        or payload.get('vendor_model_byte_identity_verified') is not False
        or payload.get('vendor_fitter_parity_verified') is not False):
        raise ValueError('Stage105 provenance flags do not match')
    fine = get_windows(payload,'fine_20k',FINE)
    coarse = get_windows(payload,'coarse_200k',COARSE)
    # Fitting a gain independently in each fine bin cannot yield larger squared
    # total error than fitting a single scalar on the containing coarse bin.
    for i,row in enumerate(coarse):
        cfine = fine[i*10:(i+1)*10]
        fine_energy = sum(r['rms_residual_after_gain']**2 for r in cfine)/len(cfine)
        if fine_energy > row['rms_residual_after_gain']**2 * (1+1e-5) + 1e-16:
            raise ValueError('fine/coarse least-squares energy contradiction')
    early,late=energy_stats(coarse[:4]),energy_stats(coarse[4:])
    early_err,late_err=early['residual_energy_sum_per_equal_length_bin'],late['residual_energy_sum_per_equal_length_bin']
    early_ref,late_ref=early['reference_energy_sum_per_equal_length_bin'],late['reference_energy_sum_per_equal_length_bin']
    top_drop=None
    for p,q in zip(fine,fine[1:]):
        if p['relative_rms_residual_after_gain']<=0 or q['relative_rms_residual_after_gain']<=0:continue
        drop = math.log10(p['relative_rms_residual_after_gain']/q['relative_rms_residual_after_gain'])
        if top_drop is None or drop > top_drop['log10_residual_drop']:
            top_drop={'between_absolute_samples':[p['stop_exclusive']-1,q['start']],
                      'log10_residual_drop':drop,
                      'previous_relative_residual':p['relative_rms_residual_after_gain'],
                      'next_relative_residual':q['relative_rms_residual_after_gain'],
                      'previous_di_rms':p['candidate_di_rms'],
                      'next_di_rms':q['candidate_di_rms']}
    top_energy_bins=sorted(fine,key=lambda r:r['rms_residual_after_gain']**2,reverse=True)[:5]
    valid=[r for r in fine if r['candidate_di_rms']>0 and r['relative_rms_residual_after_gain']>0]
    corr = rank_correlation([math.log10(r['candidate_di_rms']) for r in valid],
                            [math.log10(r['relative_rms_residual_after_gain']) for r in valid]) if len(valid)>=3 else None
    return {
        'stage':106,'status':'STAGE106_PRIVATE_METRICS_ONLY_ENERGY_ASSOCIATION_COMPLETED',
        'method':'postprocess stored Stage105 diagnostics only; per-window gains are individually fitted, not shared global gain',
        'early_first4':early,'late_last2':late,
        'fraction_per_window_gain_fitted_residual_energy_in_early':early_err/(early_err+late_err) if early_err+late_err else None,
        'fraction_reference_squared_energy_in_early':early_ref/(early_ref+late_ref) if early_ref+late_ref else None,
        'candidate_di_rms_ratio_late_over_early':late['di_rms']/early['di_rms'] if early['di_rms']>0 else None,
        'spearman_rank_correlation_log_di_rms_vs_log_relative_residual_in_20k_bins':corr,
        'largest_adjacent_20k_relative_residual_drop':top_drop,
        'top_5_absolute_residual_energy_20k_bins':[
            {'start':r['start'],'stop_exclusive':r['stop_exclusive'],
             'rms_residual_after_gain':r['rms_residual_after_gain'],
             'candidate_di_rms':r['candidate_di_rms'],
             'relative_rms_residual_after_gain':r['relative_rms_residual_after_gain']}
            for r in top_energy_bins],
        'vendor_resampler_parity_verified':False,
        'vendor_model_identity_verified':False,
        'vendor_nam_fitter_parity_verified':False,
        'new_inference_performed':False,
        'causal_explanation_proven':False,
    }


def run(source: Path) -> dict:
    src = source.resolve(strict=True)
    if src.name != 'stage105_error_topology_private.json' or not src.is_relative_to(PRIVATE_ROOT.resolve()):
        raise ValueError('input must be ignored Stage105 private report')
    dest = src.parent/'stage106_metrics_audit_private.json'
    if dest.exists(): raise ValueError('refusing to overwrite Stage106 report')
    if src.stat().st_size > 5_000_000:raise ValueError('unexpected Stage105 report size')
    result = analyze(json.loads(src.read_text(encoding='utf-8')))
    result['source_stage105_report_sha256']=sha256(src)
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return {
        'status':result['status'],
        'early_residual_energy_fraction':result['fraction_per_window_gain_fitted_residual_energy_in_early'],
        'early_reference_energy_fraction':result['fraction_reference_squared_energy_in_early'],
        'late_over_early_candidate_di_rms_ratio':result['candidate_di_rms_ratio_late_over_early'],
        'early_residual_rms_pcm16_steps':result['early_first4']['residual_rms_in_pcm16_steps'],
        'late_residual_rms_pcm16_steps':result['late_last2']['residual_rms_in_pcm16_steps'],
        'spearman_rank_correlation_di_level_vs_relative_error':result['spearman_rank_correlation_log_di_rms_vs_log_relative_residual_in_20k_bins'],
        'largest_adjacent_20k_residual_drop':result['largest_adjacent_20k_relative_residual_drop'],
        'private_report':str(dest),
        'vendor_parity_verified':False
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage105-report',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(run(args.stage105_report),indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print('[Stage106] '+str(exc),file=sys.stderr)
        sys.exit(2)
