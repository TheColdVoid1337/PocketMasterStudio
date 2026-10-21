#!/usr/bin/env python3
"""HTKPA Stage112: offline fixed-gain residual/signal-slope morphology audit.

Requires original Stage97 and source-checked Stage102->111 private evidence.
Does not fit gain, lag, offset, phase, model, resampling or perform inference.
Only a new private metrics JSON is written, with exclusive no-overwrite.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
STAGE111_PATH = HERE.parent / 'stage111' / 'GO.py'
STAGE110_NAME = 'stage110_micro_residual_private.json'
STAGE111_NAME = 'stage111_event_boundary_private.json'
REPORT_NAME = 'stage112_waveform_morphology_private.json'
STATUS = 'STAGE112_OFFLINE_WAVEFORM_MORPHOLOGY_COMPLETED'
DI_END_LAST = 1_344_016
SECONDARY_EVENT = (1_488_000, 1_488_200)
BINS = 16

# Original Stage111 phase definitions form predeclared controls.
PHASES = {
    'primary_before_input_cessation': (1_343_000, 1_344_017),
    'primary_first_1000_post_DI_zero': (1_344_017, 1_345_017),
    'primary_next_1000_post_DI_zero': (1_345_017, 1_346_017),
    'secondary_pre_200': (1_487_800, 1_488_000),
    'secondary_0_to_200': SECONDARY_EVENT,
    'secondary_post_200': (1_488_200, 1_488_400),
    'control_strong_DI': (1_300_000, 1_302_000),
    'control_later_active': (1_460_000, 1_462_000),
}
# Additional local inspection grids are explicitly fixed, not peak-fitted.
LOCAL_GRIDS = {
    'primary_DI_end_tail_16': (1_343_960, 1_345_240),
    'secondary_active_burst_16': (1_487_984, 1_488_128),
}


def load_stage111():
    spec=importlib.util.spec_from_file_location('htkpa_stage112_verified_111', STAGE111_PATH)
    if spec is None or spec.loader is None:
        raise ValueError('public Stage111 code missing')
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod


def pearson(a:list[float], b:list[float]) -> float|None:
    if len(a)!=len(b) or not a:
        raise ValueError('Pearson vectors must be equal nonempty length')
    am=sum(a)/len(a); bm=sum(b)/len(b)
    xx=sum((x-am)**2 for x in a)
    yy=sum((y-bm)**2 for y in b)
    if xx<=1e-24 or yy<=1e-24:
        return None
    return sum((x-am)*(y-bm) for x,y in zip(a,b))/math.sqrt(xx*yy)


def mean_or_none(vals:list[float]) -> float|None:
    return sum(vals)/len(vals) if vals else None


def shape_metrics(vendor:bytes, output:bytes, di:bytes, start:int, stop:int, base) -> dict:
    if not (0<=start<stop<=base.FRAMES):
        raise ValueError('invalid waveform morphology interval')
    n=stop-start
    if len(vendor)!=base.FRAMES*4 or len(output)!=base.FRAMES*8 or len(di)!=base.FRAMES*8:
        raise ValueError('invalid source byte sizes')
    signed:list[float]=[]
    slopes:list[float]=[]
    di_slopes:list[float]=[]
    di_values:list[float]=[]
    gt1_flags:list[bool]=[]
    mismatch=nonzero_di=0
    peak=0
    first=last=None
    for i in range(start,stop):
        v,w=struct.unpack_from('<hh',vendor,i*4)
        if v!=w: raise ValueError('original Manager WAV stereo mismatch')
        x=struct.unpack_from('<d',output,i*8)[0]
        d=struct.unpack_from('<d',di,i*8)[0]
        pre_x=struct.unpack_from('<d',output,(i-1)*8)[0] if i>0 else x
        pre_d=struct.unpack_from('<d',di,(i-1)*8)[0] if i>0 else d
        if not all(math.isfinite(t) for t in (x,d,pre_x,pre_d)):
            raise ValueError('nonfinite existing source sample')
        delta=base.candidate_floor(x)-v
        gt=abs(delta)>1
        mismatch+=delta!=0
        nonzero_di+=d!=0
        if gt:
            if first is None:first=i
            last=i
        peak=max(peak,abs(delta))
        signed.append(float(delta))
        slopes.append(base.GAIN*32768.0*(x-pre_x))
        di_slopes.append(d-pre_d)
        di_values.append(d)
        gt1_flags.append(gt)
    gt1=sum(gt1_flags)
    abs_slope=[abs(x) for x in slopes]
    # Stable rank selection, exactly ceil(10%) frames even when magnitudes tie.
    top_count=max(1,(n+9)//10)
    top=set(sorted(range(n),key=lambda i:(-abs_slope[i],i))[:top_count])
    gt_slope=[abs_slope[i] for i in range(n) if gt1_flags[i]]
    non_gt_slope=[abs_slope[i] for i in range(n) if not gt1_flags[i]]
    return {
        'start':start,'stop_exclusive':stop,'frames':n,
        'candidate_di_nonzero_frames':nonzero_di,
        'candidate_di_rms':math.sqrt(sum(x*x for x in di_values)/n),
        'candidate_di_first_derivative_rms':math.sqrt(sum(x*x for x in di_slopes)/n),
        'gt1':gt1,'mismatches':mismatch,'gt1_positive':sum(x>1 for x in signed),
        'gt1_negative':sum(x< -1 for x in signed),
        'first_gt1_index':first,'last_gt1_index':last,
        'max_abs_residual_lsb':peak,
        'residual_rms_lsb':math.sqrt(sum(x*x for x in signed)/n),
        'residual_mean_signed_lsb':sum(signed)/n,
        'candidate_open_slope_mean_abs_lsb_per_frame':sum(abs_slope)/n,
        'candidate_open_slope_rms_lsb_per_frame':math.sqrt(sum(x*x for x in slopes)/n),
        'candidate_open_slope_gt1_mean_abs_lsb_per_frame':mean_or_none(gt_slope),
        'candidate_open_slope_non_gt1_mean_abs_lsb_per_frame':mean_or_none(non_gt_slope),
        'gt1_in_top_10pct_open_slope':sum(gt1_flags[i] for i in top),
        'top_10pct_frame_count':top_count,
        'pearson_signed_integer_residual_vs_candidate_open_slope':pearson(signed,slopes),
        'pearson_abs_integer_residual_vs_abs_candidate_open_slope':pearson([abs(v) for v in signed],abs_slope),
        'pearson_abs_integer_residual_vs_abs_candidate_DI_slope':pearson([abs(v) for v in signed],[abs(v) for v in di_slopes]),
    }


def validate_previous(stage111_report:dict, independently_recomputed:dict) -> None:
    if (stage111_report.get('stage')!=111
        or stage111_report.get('status')!='STAGE111_OFFLINE_EVENT_BOUNDARY_AUDIT_COMPLETED'
        or stage111_report.get('primary_gt1_total')!=429
        or stage111_report.get('secondary_gt1_total')!=33
        or stage111_report.get('global_gt1_over_stage110_scan')!=462
        or stage111_report.get('candidate_di_last_nonzero_index')!=DI_END_LAST):
        raise ValueError('Stage111 original private report status/counters invalid')
    for field in ('primary_gt1_total','secondary_gt1_total','primary_gt1_after_di_end','candidate_di_last_nonzero_index'):
        if independently_recomputed[field]!=stage111_report[field]:
            raise ValueError('Stage111 reconstructed evidence disagrees with stored report')
    for phase in PHASES:
        a=stage111_report['phase_summary'][phase]
        b=independently_recomputed['phase_summary'][phase]
        for field in ('start','stop_exclusive','mismatches','gt1','candidate_di_nonzero_frames'):
            if a[field]!=b[field]:
                raise ValueError('Stage111 original phase count contradiction')
    for field in ('private_primary_gt1_events','private_secondary_gt1_events'):
        if stage111_report[field]!=independently_recomputed[field]:
            raise ValueError('Stage111 original GT1 event list contradiction')


def analyze(vendor:bytes,output:bytes,di:bytes,base,stage111_source:dict,checked_111:dict)->dict:
    validate_previous(stage111_source,checked_111)
    summaries={name:shape_metrics(vendor,output,di,*bounds,base) for name,bounds in PHASES.items()}
    for name,row in summaries.items():
        prior=stage111_source['phase_summary'][name]
        if any(row[k]!=prior[k] for k in ('gt1','mismatches','candidate_di_nonzero_frames','first_gt1_index','last_gt1_index')):
            raise ValueError('Stage111 phase-based morphology accounting mismatch')
        if not math.isclose(row['residual_rms_lsb'],prior['rms_lsb'],rel_tol=1e-12,abs_tol=1e-12):
            raise ValueError('Stage111 phase residual RMS mismatch')
    local_grid={name:[shape_metrics(vendor,output,di,lo,min(lo+BINS,hi),base)
                      for lo in range(start,hi,BINS)]
                for name,(start,hi) in LOCAL_GRIDS.items()}
    # Original anchored events/DI cessation remain fixed and are reverified above.
    public={
        'stage':112,'status':STATUS,'sample_rate_hz':base.RATE,
        'gain_candidate':base.GAIN,
        'error_sign':'predicted_integer_minus_original_manager_integer',
        'source_gates':'original Stage97 ZIP SHA; Stage102-110 reports; Stage111 replay and exact event lists',
        'candidate_di_last_nonzero_index':DI_END_LAST,
        'gt1_primary_post_DI_zero':summaries['primary_first_1000_post_DI_zero']['gt1']+summaries['primary_next_1000_post_DI_zero']['gt1'],
        'gt1_secondary_active_200':summaries['secondary_0_to_200']['gt1'],
        'region_metrics':summaries,
        'local_grid_16_summary':{name:{'total_frames':sum(r['frames'] for r in rows),
              'gt1':sum(r['gt1'] for r in rows),
              'most_affected_3':[{'start':r['start'],'stop_exclusive':r['stop_exclusive'],
                   'gt1':r['gt1'],'max_abs_residual_lsb':r['max_abs_residual_lsb']}
                   for r in sorted(rows,key=lambda z:z['gt1'],reverse=True)[:3]]}
              for name,rows in local_grid.items()},
        'new_inference_or_resampling_or_native_execution':False,
        'gain_lag_or_offset_fitted':False,
        'native_vendor_quantizer_gain_model_resampler_fitter_clo_hardware_parity_verified':False,
    }
    return {**public,'private_16_frame_local_grid':local_grid}


def run(inputs:Path, stage97:Path, stage110_report:Path, stage111_report:Path, output:Path)->dict:
    if output.exists():raise ValueError('refusing overwrite of Stage112 private report')
    if stage110_report.name!=STAGE110_NAME or stage111_report.name!=STAGE111_NAME:
        raise ValueError('incorrect prior-stage canonical report filename')
    stage111=load_stage111()
    stage110=stage111.load_stage110()
    members,_,vendor=stage110.read_inputs(inputs,stage97)
    s110=json.loads(stage110_report.read_text(encoding='utf-8'))
    s111=json.loads(stage111_report.read_text(encoding='utf-8'))
    b=members['open_nam_prewarm_off.f64le'];di=members['open_source_resampled_input_48000.f64le']
    independently_checked=stage111.analyze(vendor,b,di,stage110,s110)
    result=analyze(vendor,b,di,stage110,s111,independently_checked)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as out:
        json.dump(result,out,indent=2,allow_nan=False)
        out.write('\n')
    return {k:v for k,v in result.items() if not k.startswith('private_')} | {'private_report':str(output)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-inputs',type=Path,required=True)
    parser.add_argument('--stage97-zip',type=Path,required=True)
    parser.add_argument('--stage110-report',type=Path,required=True)
    parser.add_argument('--stage111-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.private_inputs,args.stage97_zip,args.stage110_report,args.stage111_report,args.output),indent=2,allow_nan=False))

if __name__=='__main__':
    try:main()
    except (OSError,KeyError,ValueError,TypeError,json.JSONDecodeError) as exc:
        print('[Stage112] '+str(exc),file=sys.stderr)
        sys.exit(2)