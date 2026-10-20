#!/usr/bin/env python3
"""Stage103: analyze existing private Stage102 raw outputs; no new inference/DLL.

Tests if one global gain describes the vendor WAV vs upstream NAM Core over
multiple fixed time slices. Gain estimation is diagnostic, NOT vendor parity.
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
STAGE102 = ROOT / 'research/htkpa/stages/stage102/GO.py'
PRIVATE_ROOT = ROOT / 'research/_LOCAL_FILES/stage102'
FRAMES = 1_600_000
FIT_START = 300_000
FIT_END = 1_500_000
CHUNK = 200_000


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as fd:
        for buf in iter(lambda: fd.read(1024 * 1024), b''):
            h.update(buf)
    return h.hexdigest()


def segment_metrics(reference: list[float], test: list[float], start: int, stop: int) -> dict:
    if not (0 <= start < stop <= len(reference) == len(test)):
        raise ValueError('invalid or mismatched sample window')
    sy=xx=yy=yx=err=0.0
    for i in range(start, stop):
        y=reference[i]; x=test[i]
        if not math.isfinite(y) or not math.isfinite(x):
            raise ValueError('non-finite sample')
        sy+=y; xx+=x*x; yy+=y*y; yx+=y*x;err+=(y-x)**2
    n=stop-start
    if xx <= 0 or yy <= 0:
        raise ValueError('silence means gain or cosine undefined')
    gain=yx/xx
    # Least-squares optimum for a single scalar and no DC offset, no lag fit.
    corrected_energy=max(0.0, yy-yx*yx/xx)
    corrected_rms=math.sqrt(corrected_energy/n)
    corrected_max=max(abs(reference[i]-gain*test[i]) for i in range(start,stop))
    return {'start':start,'stop_exclusive':stop,'frames':n,
            'gain_open_to_manager_least_squares':gain,
            'raw_rms_error':math.sqrt(err/n),
            'manager_rms':math.sqrt(yy/n),'open_rms':math.sqrt(xx/n),
            'zero_lag_cosine_similarity':yx/math.sqrt(xx*yy),
            'rms_after_gain_only':corrected_rms,
            'normalized_rms_after_gain_only':corrected_rms/math.sqrt(yy/n),
            'max_abs_error_after_gain_only':corrected_max,
            'gain_fitted_for_diagnostic_only':True,
            'lag_fitted':False,
            'dc_offset_fitted':False}


def evaluate(reference: list[float], test: list[float]) -> dict:
    windows={'initial_0_300k':(0,FIT_START),
             'fit_full_300k_1500k':(FIT_START,FIT_END),
             'tail_1500k_1600k':(FIT_END,FRAMES)}
    for i,start in enumerate(range(FIT_START,FIT_END,CHUNK)):
        windows[f'fit_block_{i+1:02d}_{start}_{start+CHUNK}']=(start,start+CHUNK)
    if len(reference)!=FRAMES or len(test)!=FRAMES:
        raise ValueError('expected 1,600,000 samples per signal')
    results={name:segment_metrics(reference,test,*span) for name,span in windows.items()}
    gains=[v['gain_open_to_manager_least_squares'] for k,v in results.items() if k.startswith('fit_block_')]
    avg=sum(gains)/len(gains)
    results['fit_block_gain_range']={'min':min(gains),'max':max(gains),
         'mean':avg,'range_percent_of_abs_mean':100*(max(gains)-min(gains))/abs(avg) if avg else None}
    return results


def import_stage102():
    spec=importlib.util.spec_from_file_location('stage103_stage102',STAGE102)
    if spec is None or spec.loader is None:
        raise ValueError('Stage102 audit module missing')
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod


def read_checked_samples(path:Path, expected_sha:str) -> list[float]:
    if not path.is_file() or path.stat().st_size != FRAMES*8:
        raise ValueError('Stage102 existing f64le output is missing or wrong size')
    if sha256(path)!=expected_sha:
        raise ValueError('Stage102 output hash differs from original private report')
    return [s[0] for s in struct.iter_unpack('<d',path.read_bytes())]


def run(report_path:Path, stage97_zip:Path) -> dict:
    report_path=report_path.resolve(strict=True)
    if not report_path.is_relative_to(PRIVATE_ROOT.resolve()):
        raise ValueError('Stage103 may only consume Stage102 private runs')
    if report_path.name!='comparison_private.json':
        raise ValueError('must pass Stage102 comparison_private.json')
    work=report_path.parent
    dest=work/'stage103_gain_audit_private.json'
    if dest.exists():
        raise ValueError('refusing to overwrite Stage103 gain audit')
    report=json.loads(report_path.read_text(encoding='utf-8'))
    if (report.get('stage')!=102
            or report.get('status')!='SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED'
            or report.get('frames_compared_from_start')!=FRAMES
            or report.get('di_44100_pcm16_identical') is not True
            or report.get('vendor_resampler_parity_verified') is not False):
        raise ValueError('unexpected Stage102 private evidence or provenance')
    source=work/'open_source_resampled_input_48000.f64le'
    if not source.is_file() or sha256(source)!=report.get('resampled_input_sha256'):
        raise ValueError('Stage102 resampled candidate SHA mismatch')
    s102=import_stage102()
    _,vendor=s102.authentic_wavs(stage97_zip)
    reference=s102.wav_first_n_vendor_samples(vendor,FRAMES)
    outputs={}
    for tag in ('off','on'):
        p=work/f'open_nam_prewarm_{tag}.f64le'
        expected=report['conditions'][tag]['open_output_sha256']
        outputs[tag]={'sha256':expected,'samples':read_checked_samples(p,expected)}
    result={'stage':103,'status':'STAGE103_OFFLINE_GAIN_WINDOW_DIAGNOSTIC_COMPLETED',
            'source_gate':'authentic Stage97 original ZIP; Stage102 original report and SHA-pinned original C++ outputs',
            'reference_origin':'original Manager 48-kHz outputFile.wav first 1.6M PCM16 frames',
            'reference_model_identity_verified':False,
            'vendor_resampler_parity_verified':False,
            'vendor_fitter_parity_verified':False,
            'gain_values_are_diagnostic_not_native_parameters':True,
            'prewarm_output_bitwise_equal':outputs['off']['sha256']==outputs['on']['sha256'],
            'conditions':{tag:{'open_output_sha256':output['sha256'],
                                'metrics':evaluate(reference,output['samples'])}
                          for tag,output in outputs.items()}}
    if not result['prewarm_output_bitwise_equal']:
        result['prewarm_difference_rms']=math.sqrt(sum((a-b)**2 for a,b in zip(
            outputs['off']['samples'], outputs['on']['samples']))/FRAMES)
    dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    fit=result['conditions']['off']['metrics']['fit_full_300k_1500k']
    return {'status':result['status'],'fit_gain_open_to_manager':fit['gain_open_to_manager_least_squares'],
            'fit_rms_after_gain_only':fit['rms_after_gain_only'],
            'fit_normalized_rms_after_gain_only':fit['normalized_rms_after_gain_only'],
            'prewarm_output_bitwise_equal':result['prewarm_output_bitwise_equal'],
            'fit_gain_range_percent':result['conditions']['off']['metrics']['fit_block_gain_range']['range_percent_of_abs_mean'],
            'private_report':str(dest),
            'vendor_nam_or_fitter_parity_verified':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage102-report',type=Path,required=True)
    p.add_argument('--stage97-zip',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(run(args.stage102_report,args.stage97_zip),indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,json.JSONDecodeError) as exc:
        print('[Stage103] '+str(exc),file=sys.stderr)
        sys.exit(2)
