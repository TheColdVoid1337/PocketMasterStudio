#!/usr/bin/env python3
"""Stage111: original-data SHA-gated offline GT1 event-boundary audit.

Uses pre-existing Stage97 vendor WAV and Stage102 f64/DI packed with verified
Stage110 private report. No new inference, resampling, DSP fitting or CLO.
Writes one private JSON exclusively. Public-facing summary is aggregate only.
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
STAGE110 = HERE.parent / 'stage110' / 'GO.py'
PRIMARY_PARENT=(1_340_000,1_360_000)
SECONDARY_PARENT=(1_480_000,1_500_000)
DI_END_LAST = 1_344_016  # anchored to Stage110 accepted operator observation
PRIMARY_FOCUS=(1_343_800,1_345_600)
SECONDARY_FOCUS=(1_487_800,1_488_400)
BIN=64
PHASES={
    'primary_before_input_cessation':(1_343_000,DI_END_LAST+1),
    'primary_first_1000_post_DI_zero':(DI_END_LAST+1,DI_END_LAST+1+1000),
    'primary_next_1000_post_DI_zero':(DI_END_LAST+1+1000,DI_END_LAST+1+2000),
    'secondary_pre_200':(1_487_800,1_488_000),
    'secondary_0_to_200':(1_488_000,1_488_200),
    'secondary_post_200':(1_488_200,1_488_400),
    'control_strong_DI':(1_300_000,1_302_000),
    'control_later_active':(1_460_000,1_462_000),
}

def load_stage110():
    s=importlib.util.spec_from_file_location('htkpa_stage111_verified_stage110',STAGE110)
    if s is None or s.loader is None:
        raise ValueError('existing public Stage110 source is missing')
    m=importlib.util.module_from_spec(s)
    sys.modules[s.name]=m
    s.loader.exec_module(m)
    return m

def event_metrics(vendor:bytes,open_bytes:bytes,di_bytes:bytes,start:int,stop:int,prev):
    if not (0<=start<stop<=prev.FRAMES):
        raise ValueError('invalid event audit window')
    total=stop-start;mis=large=max_abs=pos=neg=di_nonzero=0
    sum_d=sum_sq=di_sq=vendor_sq=open_sq=0
    gt1=[]
    for i in range(start,stop):
        a,b=struct.unpack_from('<hh',vendor,i*4)
        if a!=b: raise ValueError('original WAV stereo mismatch')
        x=struct.unpack_from('<d',open_bytes,i*8)[0]
        v=struct.unpack_from('<d',di_bytes,i*8)[0]
        if not math.isfinite(v) or not math.isfinite(x): raise ValueError('nonfinite open input/output')
        d=prev.candidate_floor(x)-a
        ad=abs(d)
        mis += ad>0;large += ad>1
        max_abs=max(max_abs,ad)
        pos += d>1;neg += d< -1
        sum_d+=d;sum_sq+=d*d
        di_nonzero+=v!=0.0
        di_sq+=v*v;vendor_sq+=(a/32768.0)**2;open_sq+=x*x
        if ad>1:gt1.append({'index':i,'predicted_minus_vendor_integer':d})
    return {
        'start':start,'stop_exclusive':stop,'frames':total,'mismatches':mis,'gt1':large,
        'gt1_positive':pos,'gt1_negative':neg,'max_abs_lsb':max_abs,
        'mean_signed_lsb':sum_d/total,'rms_lsb':math.sqrt(sum_sq/total),
        'candidate_di_nonzero_frames':di_nonzero,
        'candidate_di_rms':math.sqrt(di_sq/total),
        'manager_rms':math.sqrt(vendor_sq/total),'open_rms':math.sqrt(open_sq/total),
        'first_gt1_index':gt1[0]['index'] if gt1 else None,
        'last_gt1_index':gt1[-1]['index'] if gt1 else None,
        'gt1_events_private':gt1,
    }

def roll_grid(vendor,open_bytes,di_bytes,span,prev):
    start,stop=span
    return [event_metrics(vendor,open_bytes,di_bytes,a,min(a+BIN,stop),prev)
            for a in range(start,stop,BIN)]

def verify_stage110_report(report:dict, vendor, x, di, prev):
    if report.get('stage')!=110 or report.get('status')!='STAGE110_OFFLINE_1K_GT1_TOPOLOGY_COMPLETED' or report.get('source_reproducibility_gates_passed') is not True:
        raise ValueError('original Stage110 private report status/gates invalid')
    if report.get('stage109_reconciled')!={'early_active_frames':720000,'early_active_exact':75525,'late_active_frames':340000,'late_active_exact':335248,'late_active_gt1':462,'late_active_mismatches':4752}:
        raise ValueError('original Stage109 counters did not reconcile')
    rows=report.get('bins_1k')
    if not isinstance(rows,list) or len(rows)!=200:
        raise ValueError('Stage110 200-bin report missing')
    for index,original in enumerate(rows):
        start=prev.SCAN_START+index*1000
        if original.get('start')!=start or original.get('stop_exclusive')!=start+1000:
            raise ValueError('Stage110 bin index/accounting mismatch')
        recomputed=event_metrics(vendor,x,di,start,start+1000,prev)
        if (recomputed['mismatches']!=original['mismatch_frames'] or recomputed['gt1']!=original['abs_error_gt_1_lsb_frames']
            or recomputed['candidate_di_nonzero_frames']!=original['di_nonzero_frames']):
            raise ValueError('original Stage110 private report contradicts source bytes')
    if sum(r['abs_error_gt_1_lsb_frames'] for r in rows)!=462:
        raise ValueError('Stage110 gt1 universe mismatch')

def analyze(vendor:bytes,open_bytes:bytes,di_bytes:bytes,prev,report:dict):
    if len(vendor)!=prev.FRAMES*4 or len(open_bytes)!=prev.FRAMES*8 or len(di_bytes)!=prev.FRAMES*8:
        raise ValueError('source buffer size mismatch')
    verify_stage110_report(report,vendor,open_bytes,di_bytes,prev)
    # The original resampled candidate-DI ceases at this exact sample.
    if struct.unpack_from('<d',di_bytes,DI_END_LAST*8)[0]==0.0:
        raise ValueError('Stage110 claimed final nonzero DI frame is zero')
    if any(v!=0.0 for (v,) in struct.iter_unpack('<d',di_bytes[(DI_END_LAST+1)*8:PRIMARY_PARENT[1]*8])):
        raise ValueError('DI resumes after accepted cessation within primary parent bin')
    first=event_metrics(vendor,open_bytes,di_bytes,*PRIMARY_PARENT,prev)
    second=event_metrics(vendor,open_bytes,di_bytes,*SECONDARY_PARENT,prev)
    if (first['gt1'],second['gt1'])!=(429,33):
        raise ValueError('Stage110 parent GT1 counters contradict original source')
    phases={label:event_metrics(vendor,open_bytes,di_bytes,*span,prev) for label,span in PHASES.items()}
    a_grid=roll_grid(vendor,open_bytes,di_bytes,PRIMARY_FOCUS,prev)
    b_grid=roll_grid(vendor,open_bytes,di_bytes,SECONDARY_FOCUS,prev)
    a_gt1=first['gt1_events_private'];b_gt1=second['gt1_events_private']
    last_di=DI_END_LAST
    a_before=sum(evt['index']<=last_di for evt in a_gt1)
    a_after=len(a_gt1)-a_before
    largest=sorted(a_gt1+b_gt1,key=lambda r:abs(r['predicted_minus_vendor_integer']),reverse=True)[:12]
    public={
        'stage':111,'status':'STAGE111_OFFLINE_EVENT_BOUNDARY_AUDIT_COMPLETED',
        'source':'real authentic Stage97 + source-SHA-checked Stage102 through Stage110 private archive',
        'sample_rate_hz':prev.RATE,'fixed_gain_candidate':prev.GAIN,
        'quantizer_candidate':'clamp_s16(floor(0.31 * open_C++_NAM_f64 * 32768))',
        'candidate_di_last_nonzero_index':last_di,
        'primary_gt1_total':first['gt1'],
        'primary_gt1_before_or_at_di_end':a_before,'primary_gt1_after_di_end':a_after,
        'primary_gt1_first_index':a_gt1[0]['index'],'primary_gt1_last_index':a_gt1[-1]['index'],
        'primary_gt1_max_abs_lsb':first['max_abs_lsb'],
        'secondary_gt1_total':second['gt1'],
        'secondary_gt1_first_index':b_gt1[0]['index'], 'secondary_gt1_last_index':b_gt1[-1]['index'],
        'secondary_gt1_max_abs_lsb':second['max_abs_lsb'],
        'global_gt1_over_stage110_scan':462,
        'phase_summary':{k:{field:value for field,value in v.items() if field!='gt1_events_private'} for k,v in phases.items()},
        'primary_64_frame_top_gt1':[{k:v for k,v in row.items() if k in ('start','stop_exclusive','gt1','mismatches','max_abs_lsb','candidate_di_nonzero_frames')} for row in sorted(a_grid,key=lambda t:t['gt1'],reverse=True)[:10]],
        'secondary_64_frame_top_gt1':[{k:v for k,v in row.items() if k in ('start','stop_exclusive','gt1','mismatches','max_abs_lsb','candidate_di_nonzero_frames')} for row in sorted(b_grid,key=lambda t:t['gt1'],reverse=True)[:10]],
        'no_new_inference_or_resampling_or_native_runtime':True,
        'vendor_quantizer_gain_resampler_model_fitter_clo_hardware_parity_verified':False,
    }
    return {**public,'private_primary_64_frame_grid':a_grid,'private_secondary_64_frame_grid':b_grid,
            'private_primary_gt1_events':a_gt1,'private_secondary_gt1_events':b_gt1,
            'private_top_12_absolute_events':largest}

def run(private_inputs:Path,stage97_zip:Path,stage110_report:Path,output:Path):
    if output.exists():raise ValueError('refusing overwrite of Stage111 private report')
    if stage110_report.name!='stage110_micro_residual_private.json':
        raise ValueError('expected canonical original Stage110 report filename')
    prev=load_stage110()
    members,_,vendor=prev.read_inputs(private_inputs,stage97_zip)
    previous=json.loads(stage110_report.read_text(encoding='utf-8'))
    result=analyze(vendor,members['open_nam_prewarm_off.f64le'],members['open_source_resampled_input_48000.f64le'],prev,previous)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as file:
        json.dump(result,file,indent=2)
        file.write('\n')
    return {k:v for k,v in result.items() if not k.startswith('private_')} | {'private_report':str(output)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-inputs',type=Path,required=True)
    p.add_argument('--stage97-zip',type=Path,required=True)
    p.add_argument('--stage110-report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.private_inputs,a.stage97_zip,a.stage110_report,a.output),indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,KeyError,ValueError,TypeError,json.JSONDecodeError) as exc:
        print('[Stage111] '+str(exc),file=sys.stderr)
        sys.exit(2)
