#!/usr/bin/env python3
"""HTKPA Stage113: authenticated original 44.1k input vs 48k candidate transition support.

An **offline source provenance audit**, NOT a test of Sonicake vendor-side 48k
resampling. Reads the original Stage97 input WAV and the existing Stage102
open-source resampler f64; uses prior reports without recomputing Stage110-112.
No model inference, resampling, DSP fitting, vendor DLL or CLO. Only one private
JSON report may be created; files are read-only and existing results protected.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import sys
import wave
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[4]
STAGE110_GO = ROOT / 'research/htkpa/stages/stage110/GO.py'
RATE_44 = 44_100
RATE_48 = 48_000
FRAMES_44 = 3_087_000
FRAMES_48 = 1_600_000
# Windows defined before viewing the new source mapping, from Stage111 hotspot locations.
PRIMARY_SEARCH = (1_342_000, 1_350_000)
REENTRY_SEARCH = (1_430_000, 1_450_000)
SECONDARY_WINDOWS = ((1_487_800, 1_488_000), (1_488_000, 1_488_200), (1_488_200, 1_488_400))
EXPECTED_SOURCE_LAST = 1_234_799
EXPECTED_CANDIDATE_LAST = 1_344_016
EXPECTED_SOURCE_REENTRY = 1_323_001
EXPECTED_CANDIDATE_REENTRY = 1_439_984
EXPECTED_SECONDARY_NONZERO_DI = 200


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as inp:
        for chunk in iter(lambda:inp.read(1_048_576), b''):
            h.update(chunk)
    return h.hexdigest()


def load_stage110():
    spec = importlib.util.spec_from_file_location('htkpa113_source_gate_110', STAGE110_GO)
    if spec is None or spec.loader is None:
        raise ValueError('missing published Stage110 source for input provenance gate')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def source_frame_time_48(index44: int) -> Fraction:
    if index44 < 0:
        raise ValueError('negative source frame index')
    return Fraction(index44 * RATE_48, RATE_44)


def input44_wave(stage97: Path) -> bytes:
    with ZipFile(stage97) as z:
        members = [x.filename for x in z.infolist()]
        expected = {'clo/', 'logs/', 'wavs/', 'clo/cloFile.clo',
                    'logs/tone_import.log', 'wavs/nam_input_wav.wav', 'wavs/outputFile.wav'}
        if len(members) != len(set(members)) or set(members) != expected:
            raise ValueError('Stage97 original member allowlist failure')
        blob=z.read('wavs/nam_input_wav.wav')
    with wave.open(io.BytesIO(blob),'rb') as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype()) != (2,2,RATE_44,FRAMES_44,'NONE'):
            raise ValueError('Stage97 original input WAV metadata mismatch')
        pcm=w.readframes(FRAMES_44)
    if len(pcm)!=FRAMES_44*4:
        raise ValueError('original input WAV PCM16 incomplete')
    if pcm[0::4]!=pcm[2::4] or pcm[1::4]!=pcm[3::4]:
        raise ValueError('original input WAV stereo channels differ')
    return pcm


def scan_pcm44(data: bytes, start: int, stop: int) -> dict:
    if len(data)%4 or not 0 <= start < stop <= len(data)//4:
        raise ValueError('invalid original PCM44 scan range')
    first=last=None
    active=0
    energy=0.0
    for idx in range(start,stop):
        left,right=struct.unpack_from('<hh',data,4*idx)
        if left!=right:raise ValueError('original PCM44 stereo channels differ')
        if left:
            if first is None:first=idx
            last=idx
            active+=1
        energy+=(left/32768.0)**2
    return {'start':start,'stop_exclusive':stop,'frames':stop-start,
            'nonzero_frames':active,'first_nonzero_index':first,'last_nonzero_index':last,
            'rms':math.sqrt(energy/(stop-start))}


def scan_f64(data: bytes, start: int, stop: int) -> dict:
    if len(data)%8 or not 0 <= start < stop <= len(data)//8:
        raise ValueError('invalid candidate f64 scan range')
    first=last=None
    active=0
    energy=0.0
    for idx in range(start,stop):
        (v,)=struct.unpack_from('<d',data,8*idx)
        if not math.isfinite(v):raise ValueError('nonfinite candidate 48k f64 input')
        if v!=0.0:
            if first is None:first=idx
            last=idx
            active+=1
        energy+=v*v
    return {'start':start,'stop_exclusive':stop,'frames':stop-start,
            'nonzero_frames':active,'first_nonzero_index':first,'last_nonzero_index':last,
            'rms':math.sqrt(energy/(stop-start))}


def source_bounds_for_48_window(start: int,stop: int) -> tuple[int,int]:
    if not 0<=start<stop:
        raise ValueError('invalid time-projection window')
    # Interval [start, stop) mapped onto a covering grid in 44.1 kHz;
    # end is exclusive; use ceil to avoid losing the last source sample.
    a=start*RATE_44//RATE_48
    b=(stop*RATE_44+RATE_48-1)//RATE_48
    return (a,b)


def analyze(pcm44:bytes, candidate48:bytes, past:dict)->dict:
    if len(pcm44)!=FRAMES_44*4 or len(candidate48)!=FRAMES_48*8:
        raise ValueError('original 44.1k / candidate 48k source shape mismatch')
    def scans(region):
        a,b=region
        lo,hi=source_bounds_for_48_window(a,b)
        return scan_pcm44(pcm44,lo,hi),scan_f64(candidate48,a,b)
    primary_source,primary_candidate=scans(PRIMARY_SEARCH)
    entry_source,entry_candidate=scans(REENTRY_SEARCH)
    sl=primary_source['last_nonzero_index'];cl=primary_candidate['last_nonzero_index']
    sf=entry_source['first_nonzero_index'];cf=entry_candidate['first_nonzero_index']
    if None in (sl,cl,sf,cf):raise ValueError('missing input transition in predeclared search windows')
    if (sl,cl,sf,cf)!=(EXPECTED_SOURCE_LAST,EXPECTED_CANDIDATE_LAST,EXPECTED_SOURCE_REENTRY,EXPECTED_CANDIDATE_REENTRY):
        raise ValueError('original 44k ↔ 48k candidate transition anchors changed')
    source_mid=scan_pcm44(pcm44,sl+1,sf)
    candidate_mid=scan_f64(candidate48,cl+1,cf)
    if source_mid['nonzero_frames']!=0 or candidate_mid['nonzero_frames']!=0:
        raise ValueError('unexpected nonzero candidate/source sample in verified zero bridge')
    if past['stage111']['candidate_di_last_nonzero_index']!=cl or past['stage112']['candidate_di_last_nonzero_index']!=cl:
        raise ValueError('Stage111/112 original candidate DI boundary contradiction')
    if past['stage111']['primary_gt1_after_di_end']!=408 or past['stage112']['gt1_primary_post_DI_zero']!=408:
        raise ValueError('previous nonzero DI/residual event evidence changed')
    if past['stage112']['gt1_secondary_active_200']!=32:
        raise ValueError('previous active-input GT1 event evidence changed')
    secondary=[]
    for window in SECONDARY_WINDOWS:
        source,candidate=scans(window)
        if candidate['nonzero_frames']!=EXPECTED_SECONDARY_NONZERO_DI or source['nonzero_frames']!=source['frames']:
            raise ValueError('previously active secondary input pocket no longer continuous in source/candidate')
        secondary.append({'window_48k':list(window),'source_original_44k':source,'candidate_open_48k':candidate})
    sl48=source_frame_time_48(sl)
    sf48=source_frame_time_48(sf)
    return {
        'stage':113,
        'status':'STAGE113_OFFLINE_SOURCE_INPUT_TRANSITION_SUPPORT_COMPLETED',
        'provenance':'SHA-authenticated original Stage97 input 44.1k PCM16 versus preexisting Stage102 open candidate resampled 48k f64',
        'original_source_44_rate_hz':RATE_44,'candidate_input_48_rate_hz':RATE_48,
        'vendor_44_to_48_resampler_equivalence_verified':False,
        'open_resampler_candidate_not_native_vendor_intermediate':True,
        'source_last_nonzero_pcm44_index':sl,
        'source_last_nonzero_mapped_48_fraction':[sl48.numerator,sl48.denominator],
        'source_last_nonzero_mapped_48_float':float(sl48),
        'candidate_last_nonzero_48_index':cl,
        'candidate_end_extension_frames':float(Fraction(cl)-sl48),
        'source_first_reentry_pcm44_index':sf,
        'source_first_reentry_mapped_48_fraction':[sf48.numerator,sf48.denominator],
        'source_first_reentry_mapped_48_float':float(sf48),
        'candidate_first_reentry_48_index':cf,
        'candidate_reentry_advance_frames':float(sf48-Fraction(cf)),
        'original_source_exact_zero_bridge_frames_44':source_mid['frames'],
        'candidate_exact_zero_bridge_frames_48':candidate_mid['frames'],
        'candidate_last_nonzero_48_vs_stage111':True,
        'secondary_three_active_input_windows':secondary,
        'stage111_primary_gt1_after_candidate_zero_onset':408,
        'stage112_secondary_gt1_at_active_input':32,
        'no_new_resampling_or_inference_or_fitting_or_native_execution':True,
        'vendor_resampler_model_gain_quantizer_fitter_clo_or_device_parity_verified':False,
    }


def run(private_zip:Path,stage97_zip:Path,report110:Path,report111:Path,report112:Path,output:Path)->dict:
    if output.exists():raise ValueError('refusing to overwrite existing Stage113 private report')
    prev=load_stage110()
    members,js,_ = prev.read_inputs(private_zip,stage97_zip)  # authenticated, no Stage110 analysis rerun
    prior={}
    for stage,report,expect in (
        (110,report110,'STAGE110_OFFLINE_1K_GT1_TOPOLOGY_COMPLETED'),
        (111,report111,'STAGE111_OFFLINE_EVENT_BOUNDARY_AUDIT_COMPLETED'),
        (112,report112,'STAGE112_OFFLINE_WAVEFORM_MORPHOLOGY_COMPLETED')):
        value=json.loads(report.read_text(encoding='utf-8'))
        if value.get('stage')!=stage or value.get('status')!=expect:
            raise ValueError(f'original Stage{stage} report status mismatch')
        prior['stage'+str(stage)]=value
    s110=prior['stage110']['stage109_reconciled']
    if (s110['late_active_gt1'],s110['late_active_mismatches'])!=(462,4752):
        raise ValueError('Stage110 original mismatch ledger contradiction')
    if prior['stage111']['secondary_gt1_total']!=33:
        raise ValueError('Stage111 secondary parent count contradiction')
    pcm=input44_wave(stage97_zip)
    report=analyze(pcm,members['open_source_resampled_input_48000.f64le'],prior)
    report['private_report_sha256']={
        'stage110':sha256_file(report110),'stage111':sha256_file(report111),'stage112':sha256_file(report112)
    }  # private only; never publish raw IDs/hashes
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
    return {k:v for k,v in report.items() if k!='private_report_sha256'} | {'private_report':str(output)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private-inputs',type=Path,required=True)
    p.add_argument('--stage97-zip',type=Path,required=True)
    p.add_argument('--stage110-report',type=Path,required=True)
    p.add_argument('--stage111-report',type=Path,required=True)
    p.add_argument('--stage112-report',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=run(a.private_inputs,a.stage97_zip,a.stage110_report,a.stage111_report,a.stage112_report,a.output)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print('[Stage113] '+str(exc),file=sys.stderr)
        sys.exit(2)
