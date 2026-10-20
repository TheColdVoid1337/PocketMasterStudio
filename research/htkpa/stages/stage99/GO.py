#!/usr/bin/env python3
"""Stage99 matched raw NAM Core vs SonicMaster WaveNet experiment.

prepare: builds a diagnostic-only SonicMaster Dart-to-JS worker from the existing
Dart source (never alters the production worker).
compare: regenerates exactly Stage98's stimulus and runs both independently.
Results/data/provenance are private, stored under ignored research/_LOCAL_FILES.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
SONICMASTER=ROOT/'tools/nam_js/clo_dsp.dart'
WORKER_SOURCE=HERE/'sonicmaster_raw.dart'
NODE_RUNNER=HERE/'sonicmaster_raw.cjs'
PRIVATE=ROOT/'research/_LOCAL_FILES/stage99'
BUILD=PRIVATE/'sonicmaster_build'
MODEL_RATE=48000  # Existing SonicMaster probe is hardcoded for 48 kHz NAM.
FRAMES=8192
SOURCE_MARKER='Float64List _runWavenet('
PARSER_MARKER='(List<_LayerArray>, double) _parseModel('
APPEND='''
// Stage99 additive diagnostic function: only in a private copied source file.
// Does NOT resample, scale, prewarm, or fit. Same _parseModel/_runWavenet
// functions as the production SonicMaster probe.
Float64List stage99RawInference(String namJson, Float64List mono) {
  if (mono.length != 8192) throw StateError('Stage99: exactly 8192 samples required');
  for (final x in mono) {
    if (!x.isFinite) throw StateError('Stage99: nonfinite input');
  }
  final (las, headScale) = _parseModel(namJson);
  return _runWavenet(mono, las, headScale);
}
'''


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def execute(argv:list[str])->str:
    p=subprocess.run(argv,capture_output=True,text=True,check=False)
    if p.returncode:
        # For local operator diagnostics include bounded compiler output.
        # Avoid exposing original model/audio paths via public project evidence.
        raise RuntimeError(f'{Path(argv[0]).name} failed ({p.returncode}): '+(p.stderr or p.stdout)[-2500:])
    return p.stdout.strip()


def diagnostic_source(original:str)->str:
    # No fragile reimplementation or implicit import of a different DSP.
    if original.count(SOURCE_MARKER)!=1 or original.count(PARSER_MARKER)!=1:
        raise ValueError('SonicMaster source anchors changed; inspect before proceeding')
    if 'stage99RawInference' in original:
        raise ValueError('SonicMaster source already contains Stage99 diagnostic entry')
    if '(_srcRate = 48000)' in original:
        raise ValueError('Unexpected SonicMaster sample-rate definition')
    if 'const int _srcRate = 48000;' not in original:
        raise ValueError('Expected hardcoded SonicMaster 48000 Hz missing')
    return original.rstrip()+'\n'+APPEND


def sources()->dict:
    return {'dart_source_sha256':sha(SONICMASTER),
            'dart_worker_template_sha256':sha(WORKER_SOURCE),
            'node_runner_sha256':sha(NODE_RUNNER),
            'stage99_python_sha256':sha(Path(__file__))}


def prepare(build:Path=BUILD,dart:str='dart')->dict:
    if not shutil.which(dart):
        raise RuntimeError('Dart SDK executable missing; install Dart >= 3.10 and rerun Stage99 prepare')
    original=SONICMASTER.read_text(encoding='utf-8')
    amended=diagnostic_source(original)
    manifest_path=build/'stage99_sonicmaster_build.json'
    worker_js=build/'sonicmaster_raw.js'
    pins=sources()
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if any(manifest.get(k)!=v for k,v in pins.items()) or not worker_js.is_file() or sha(worker_js)!=manifest.get('worker_js_sha256'):
            raise ValueError('Stage99 Dart build differs from source; no overwrite; select a new --build-dir')
        return manifest
    build.mkdir(parents=True,exist_ok=True)
    copied=build/'clo_dsp.dart'
    diagnostic=build/'sonicmaster_raw.dart'
    if copied.exists() or diagnostic.exists() or worker_js.exists():
        raise ValueError('Stage99 build directory has partial files; inspect manually before retry')
    # Build in an isolated temp directory: a compiler error leaves no fake
    # successful or half-installed worker. The temp dir auto-cleans on failure.
    with tempfile.TemporaryDirectory(prefix='stage99_dart_',dir=build.parent) as tmp:
        tmp=Path(tmp)
        temp_source=tmp/'clo_dsp.dart'
        temp_worker=tmp/'sonicmaster_raw.dart'
        temp_js=tmp/'sonicmaster_raw.js'
        temp_source.write_text(amended,encoding='utf-8')
        temp_worker.write_bytes(WORKER_SOURCE.read_bytes())
        execute([dart,'compile','js','-O2','-o',str(temp_js),str(temp_worker)])
        if not temp_js.is_file() or temp_js.stat().st_size<1000:
            raise RuntimeError('Dart diagnostic compile did not create JS worker')
        manifest={'stage':99,'backend':'existing SonicMaster Dart WaveNet / diagnostic-only JS worker',
            **pins,'worker_js_sha256':sha(temp_js),'patched_dart_sha256':sha(temp_source),
            'compile_mode':'dart compile js -O2','model_rate_hz':MODEL_RATE,
            'frames':FRAMES,'resampler_used':False,'fitter_used':False,
            'production_worker_modified':False}
        temp_source.replace(copied)
        temp_worker.replace(diagnostic)
        temp_js.replace(worker_js)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest


def stimulus(rate:int=MODEL_RATE)->bytes:
    if rate!=MODEL_RATE:raise ValueError('Stage99 only supports 48000 Hz (existing SonicMaster WaveNet)')
    return b''.join(struct.pack('<d',
        (0.3 if i==64 else 0.0)+0.02*math.sin(2*math.pi*997*i/rate)
        +0.01*math.sin(2*math.pi*241*i/rate)) for i in range(FRAMES))


def doubles(path:Path)->list[float]:
    b=path.read_bytes()
    if len(b)!=FRAMES*8:raise ValueError('Expected exactly 8192 raw mono f64le frames')
    samples=[x[0] for x in struct.iter_unpack('<d',b)]
    if any(not math.isfinite(x) for x in samples):raise ValueError('Nonfinite raw sample')
    return samples


def metrics(ref:list[float],actual:list[float])->dict:
    if len(ref)!=FRAMES or len(actual)!=FRAMES:raise ValueError('Mismatched sample counts')
    if any(not math.isfinite(x) for x in ref+actual):raise ValueError('Nonfinite comparison data')
    err=[a-b for a,b in zip(actual,ref)]
    rms=math.sqrt(math.fsum(e*e for e in err)/FRAMES)
    ref_rms=math.sqrt(math.fsum(x*x for x in ref)/FRAMES)
    act_rms=math.sqrt(math.fsum(x*x for x in actual)/FRAMES)
    maxabs=max(abs(x) for x in err)
    return {'frames':FRAMES,'rms_error':rms,'max_abs_error':maxabs,
        'mean_error':math.fsum(err)/FRAMES,'reference_rms':ref_rms,
        'sonicmaster_rms':act_rms,'normalized_rms_error':rms/ref_rms if ref_rms>0 else None,
        'bitwise_equal':all(struct.pack('<d',a)==struct.pack('<d',b) for a,b in zip(ref,actual)),
        'largest_error_sample':max(range(FRAMES),key=lambda i:abs(err[i]))}


def load_stage98():
    p=ROOT/'research/htkpa/open_nam/GO.py'
    spec=importlib.util.spec_from_file_location('stage98_nam_core_for_comparison',p)
    if spec is None or spec.loader is None:raise ValueError('Stage98 NAM Core helper missing')
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    return mod


def model_mode(model:Path)->str:
    if not model.is_file() or model.suffix.lower()!='.nam' or model.stat().st_size>32*1024*1024:
        raise ValueError('Expected a private .nam <=32 MiB')
    data=json.loads(model.read_text(encoding='utf-8'))
    if data.get('sample_rate')!=MODEL_RATE or isinstance(data.get('sample_rate'),bool):
        raise ValueError('Model training sample rate must be 48000; no fake resampling')
    arch=data.get('architecture')
    if arch=='WaveNet':return 'plain_wavenet'
    if arch!='SlimmableContainer':raise ValueError('SonicMaster diagnostic WaveNet supports WaveNet or SlimmableContainer only')
    sub=data.get('config',{}).get('submodels',[])
    if not isinstance(sub,list) or not sub or any(not isinstance(s,dict) for s in sub):
        raise ValueError('Invalid submodels')
    mx=[s.get('max_value') for s in sub]
    if any(type(x) not in (float,int) or not math.isfinite(x) for x in mx) or any(b<=a for a,b in zip(mx,mx[1:])) or mx[-1]!=1.0:
        raise ValueError('Cannot prove SonicMaster max-quality child matches --slim=1.0')
    if sub[-1].get('model',{}).get('architecture')!='WaveNet':
        raise ValueError('SonicMaster diagnostic currently supports max-quality WaveNet only')
    return 'slim_1.0_last_wavenet'


def compare(model:Path,build:Path=BUILD,private:Path=PRIVATE)->dict:
    mode=model_mode(model)
    bp=build/'stage99_sonicmaster_build.json';js=build/'sonicmaster_raw.js'
    if not bp.is_file() or not js.is_file():raise ValueError('Compile Stage99 SonicMaster diagnostic with prepare first')
    bmanifest=json.loads(bp.read_text(encoding='utf-8'))
    if any(bmanifest.get(k)!=v for k,v in sources().items()) or sha(js)!=bmanifest.get('worker_js_sha256'):
        raise ValueError('Diagnostic worker/source hash mismatch')
    stage98=load_stage98()
    upstream=stage98.verify_source(stage98.DEFAULT_SOURCE)
    manifest_path=stage98.DEFAULT_BUILD/stage98.MARKER
    if not manifest_path.is_file():raise ValueError('Stage98 C++ build missing; run Stage98 build')
    cppmanifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if cppmanifest.get('source_commit')!=stage98.PIN or not cppmanifest.get('real_upstream_compile'):
        raise ValueError('Stage98 build is not pinned genuine upstream')
    label=sha(model)[:16]+'_48k_cold_'+mode
    output_dir=private/'comparisons'/label
    if output_dir.exists():raise ValueError('Comparison already exists; do not overwrite raw data')
    output_dir.mkdir(parents=True)
    inp=output_dir/'stimulus.f64le'
    cpp=output_dir/'nam_core.f64le'
    dart=output_dir/'sonicmaster.f64le'
    inp.write_bytes(stimulus())
    result_core=stage98.run(stage98.DEFAULT_BUILD,model,inp,cpp,MODEL_RATE,64,'off',
                            1.0 if mode.startswith('slim') else None)
    result_sonic=json.loads(execute(['node',str(NODE_RUNNER),'--model',str(model),
                    '--worker-js',str(js),'--input-f64le',str(inp),'--output-f64le',str(dart)]))
    if result_sonic.get('status')!='SONICMASTER_DART_RAW_DIAGNOSTIC_COMPLETED' or result_sonic.get('frames')!=FRAMES:
        raise ValueError('SonicMaster diagnostic did not report full completion')
    if result_sonic.get('input_sha256')!=sha(inp) or result_sonic.get('output_sha256')!=sha(dart):
        raise ValueError('SonicMaster reported hash mismatch')
    report={'stage':99,'status':'OPEN_NAM_VS_SONICMASTER_SAME_STIMULUS_RAW_COMPARISON_COMPLETED',
        'comparison':'direct raw WaveNet only','model_sha256':sha(model),
        'model_mode':mode,'input_sha256':sha(inp),'nam_core_output_sha256':sha(cpp),
        'sonicmaster_output_sha256':sha(dart),'sample_rate':MODEL_RATE,'frames':FRAMES,
        'core_binary_sha256':cppmanifest.get('binary_sha256'),
        'sonicmaster_worker_sha256':sha(js),'core_prewarm':'off',
        'core_block_size':64,'core_slim':1.0 if mode.startswith('slim') else None,
        'sonicmaster_state':'sequence-start zero-padding; no prewarm',
        'resampled':False,'fitted':False,'vendor_dll_parity_verified':False,
        'clo_generated':False,'metrics':metrics(doubles(cpp),doubles(dart)),
        'core_probe_status':result_core.get('status'),
        'sonicmaster_probe_status':result_sonic.get('status')}
    (output_dir/'comparison_private.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['prepare','compare'])
    ap.add_argument('--model',type=Path)
    ap.add_argument('--build-dir',type=Path,default=BUILD)
    ap.add_argument('--dart',default='dart')
    args=ap.parse_args()
    if args.action=='prepare':result=prepare(args.build_dir,args.dart)
    else:
        if args.model is None:ap.error('compare requires --model')
        result=compare(args.model,args.build_dir)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,json.JSONDecodeError) as exc:
        print('[Stage99] '+str(exc),file=sys.stderr)
        sys.exit(2)
