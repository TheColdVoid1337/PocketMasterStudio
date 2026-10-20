#!/usr/bin/env python3
"""Stage102: independent first-1.6M-frame NAM Core/Manager output boundary.

Uses source-exact *open SonicMaster* DI->48k resampling as ONE candidate;
strictly NOT proven equivalent to Sonicake's proprietary input preprocessing.
Raw data and model are never committed; outputs stay under ignored _LOCAL_FILES.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import wave
import io

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PRIVATE = ROOT / 'research/_LOCAL_FILES/stage102'
STAGE100 = ROOT / 'research/htkpa/stages/stage100/GO.py'
SONIC_SOURCE = ROOT / 'tools/nam_js/clo_dsp.dart'
REFERENCE_GZ = ROOT / 'src/assets/nam_reference_di_44100.f32.gz'
VENDOR_ARCHIVE_SHA = '2f96dce1ae479a93975cf6247a88a4a08c11de7ae5cab41648faa0d7902e6f46'
RATE = 48000
FRAMES = 1600000
FIT_START = 300000
FIT_END = 1500000
ORIGINAL_FRAMES = 3360000
SOURCE_ANCHOR = 'Float64List _resampleDiTo48(List<double> referenceDi44100)'


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def stage100():
    s = importlib.util.spec_from_file_location('stage102_stage100', STAGE100)
    if not s or not s.loader:
        raise ValueError('Stage100 module not found')
    m = importlib.util.module_from_spec(s)
    sys.modules[s.name] = m
    s.loader.exec_module(m)
    return m


def authentic_wavs(bundle: Path) -> tuple[bytes, bytes]:
    if not bundle.is_file() or sha(bundle) != VENDOR_ARCHIVE_SHA:
        raise ValueError('Stage97 original vendor ZIP SHA mismatch or missing')
    from zipfile import ZipFile
    with ZipFile(bundle) as z:
        names = {v.filename for v in z.infolist()}
        expected = {'clo/', 'logs/', 'wavs/', 'clo/cloFile.clo',
                    'logs/tone_import.log', 'wavs/nam_input_wav.wav', 'wavs/outputFile.wav'}
        if names != expected:
            raise ValueError('Stage97 ZIP member allowlist mismatch')
        a, b = z.read('wavs/nam_input_wav.wav'), z.read('wavs/outputFile.wav')
    for data, rate, frames in [(a,44100,3087000),(b,48000,ORIGINAL_FRAMES)]:
        with wave.open(io.BytesIO(data),'rb') as w:
            if (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes(),w.getcomptype()) != (2,2,rate,frames,'NONE'):
                raise ValueError('Stage97 WAV metadata mismatch')
            pcm=w.readframes(frames)
        if len(pcm)!=frames*4 or pcm[0::4]!=pcm[2::4] or pcm[1::4]!=pcm[3::4]:
            raise ValueError('Stage97 WAV mono-duplicate channels check failed')
    return a,b


def check_di_identity(vendor44: bytes, public_gz:Path) -> tuple[bytes,str]:
    """Re-check the closed Stage101 direct-quantization identity gate."""
    if public_gz.stat().st_size>7000000:
        raise ValueError('reference DI gz too big')
    compressed=public_gz.read_bytes()
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as inp:
        b=inp.read(3087000*4+1)
    if len(b)!=3087000*4:
        raise ValueError('public reference DI frame count mismatch')
    with wave.open(io.BytesIO(vendor44),'rb') as w:
        pcm=w.readframes(3087000)
    for i, ((left, right), (f,)) in enumerate(zip(struct.iter_unpack('<hh',pcm),struct.iter_unpack('<f',b))):
        if not math.isfinite(f) or left!=right or max(-32768,min(32767,round(f*32768.0)))!=left:
            raise ValueError('Stage101 DI PCM16 exact identity failed at frame '+str(i))
    return b, hashlib.sha256(compressed).hexdigest()


def candidate_source() -> str:
    text = SONIC_SOURCE.read_text(encoding='utf-8')
    if text.count(SOURCE_ANCHOR)!=1 or '_resample(di44, _srcRate, _deviceRate, maxOut: _runLen)' not in text:
        raise ValueError('SonicMaster source resampling anchors changed')
    return text + '\n// Stage102 diagnostic only; private source copy, not production.\n' + (
        'Float64List stage102OpenSourceDiTo48(List<double> di44) => _resampleDiTo48(di44);\n')


DART_MAIN = '''import 'dart:io';
import 'dart:typed_data';
import 'resampler_source.dart';
void main(List<String> args) {
  if (args.length != 2) throw ArgumentError('expected input f32le and output f64le');
  final b = File(args[0]).readAsBytesSync();
  if (b.lengthInBytes != 3087000 * 4) throw StateError('DI size mismatch');
  final view = ByteData.sublistView(b);
  final source = Float64List(3087000);
  for (var i=0;i<source.length;i++) {
    source[i]=view.getFloat32(i*4,Endian.little);
  }
  final out = stage102OpenSourceDiTo48(source);
  if (out.length != 1600000) throw StateError('unexpected resampler length');
  final bytes = ByteData(out.length * 8);
  for (var i=0;i<out.length;i++) bytes.setFloat64(i*8,out[i],Endian.little);
  final dest=File(args[1]);
  if (dest.existsSync()) throw StateError('refusing overwrite');
  dest.writeAsBytesSync(bytes.buffer.asUint8List(),flush:true);
  stdout.writeln('{"status":"SONICMASTER_SOURCE_RESAMPLER_48K_DONE","frames":1600000}');
}
'''


def prepare_resampler(directory:Path):
    if not shutil.which('dart'):
        raise ValueError('Dart SDK not installed')
    content=candidate_source()
    directory.mkdir(parents=True,exist_ok=True)
    copy=directory/'resampler_source.dart'
    main=directory/'run_resampler.dart'
    exe=directory/'stage102_resampler'
    for p in (copy,main,exe):
        if p.exists():
            raise ValueError('Stage102 private source/binary already exists; refuse overwrite')
    copy.write_text(content,encoding='utf-8')
    main.write_text(DART_MAIN,encoding='utf-8')
    cmd=['dart','compile','exe',str(main),'-o',str(exe)]
    proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=False)
    if proc.returncode or not exe.is_file():
        raise RuntimeError('Stage102 private Dart VM resampler compile failed; inspect local private build')
    return {'source_sha256':sha(SONIC_SOURCE),'binary_sha256':sha(exe),'binary_path':str(exe)}


def metrics(reference, test):
    """No fitted gain/lag; direct sign-preserving sample comparison."""
    if len(reference)!=len(test) or not reference:
        raise ValueError('empty or mismatched samples')
    energy=error2=dot=energy_test=0.0
    m=0.0
    for a,b in zip(reference,test):
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError('nonfinite sample')
        delta=a-b
        error2+=delta*delta;energy+=a*a;energy_test+=b*b;dot+=a*b
        m=max(m,abs(delta))
    n=len(reference)
    rms=math.sqrt(error2/n);rref=math.sqrt(energy/n)
    return {'frames':n,'rms_error':rms,'max_abs_error':m,
            'reference_rms':rref,'test_rms':math.sqrt(energy_test/n),
            'normalized_rms_error':rms/rref if rref else None,
            'zero_lag_cosine_similarity':dot/math.sqrt(energy*energy_test) if energy*energy_test else None,
            'gain_fitted':False,'lag_aligned':False}


def wav_first_n_vendor_samples(wav_data, n=FRAMES):
    with wave.open(io.BytesIO(wav_data),'rb') as w:
        raw=w.readframes(n)
    if len(raw)!=n*4:
        raise ValueError('vendor 48-kHz PCM was truncated')
    return [left/32768.0 for left,right in struct.iter_unpack('<hh',raw)]


def f64file(path:Path):
    data=path.read_bytes()
    if len(data)!=FRAMES*8:raise ValueError('open native output byte count mismatch')
    return [v[0] for v in struct.iter_unpack('<d',data)]


def run(model:Path,bundle:Path):
    s100=stage100()
    s99,s98,mode,worker,diagnostic,native=s100.preflight(model)
    if not model.is_file() or mode != 'slim_1.0_last_wavenet':
        raise ValueError('Stage102 is pinned to the accepted Stage97 slimmable full-size WaveNet model mode')
    wav44,wav48=authentic_wavs(bundle)
    pub_di,pub_sha=check_di_identity(wav44,REFERENCE_GZ)
    label=s99.sha(model)[:16]+'_stage102_open_sonicmaster_di_resample_v1'
    target=PRIVATE/label
    if target.exists():raise ValueError('Stage102 private directory already exists; refuse overwrite')
    prepped=prepare_resampler(target/'build')
    inp=target/'source_di_44100_f32le.private'
    inp.write_bytes(pub_di)
    resamp=target/'open_source_resampled_input_48000.f64le'
    exe=target/'build/stage102_resampler'
    proc=subprocess.run([str(exe),str(inp),str(resamp)],capture_output=True,text=True,check=False)
    if proc.returncode or not resamp.is_file() or resamp.stat().st_size!=FRAMES*8:
        raise RuntimeError('Stage102 source-derived resampler failed')
    reference=wav_first_n_vendor_samples(wav48)
    conditions={}
    for warm in ('off','on'):
        output=target/('open_nam_prewarm_'+warm+'.f64le')
        s98.run(s98.DEFAULT_BUILD,model,resamp,output,RATE,64,warm,1.0)
        open_vals=f64file(output)
        conditions[warm]={
          'all_first_1600000':metrics(reference,open_vals),
          'fit_window_300k_1500k':metrics(reference[FIT_START:FIT_END],open_vals[FIT_START:FIT_END]),
          'open_output_sha256':s99.sha(output)}
    report={'stage':102,'status':'SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED',
            'provenance':'vendor WAV original SHA-pinned Stage97 ZIP; open resampler from SonicMaster Dart; original NAM Core C++',
            'operator_vendor_model_byte_identity_proven':False,
            'sample_rate_hz':48000,'vendor_wav_full_frames':ORIGINAL_FRAMES,
            'frames_compared_from_start':FRAMES,'di_44100_pcm16_identical':True,
            'candidate_input_resampler':'open SonicMaster; NOT vendor-verified',
            'source_dart_sha256':prepped['source_sha256'],
            'private_resampler_binary_sha256':prepped['binary_sha256'],
            'model_sha256':s99.sha(model), 'di_gzip_sha256':pub_sha,
            'resampled_input_sha256':s99.sha(resamp),
            'native_core_binary_sha256':native['binary_sha256'],
            'conditions':conditions,'vendor_resampler_parity_verified':False,
            'vendor_nam_inference_numeric_parity_verified':False,
            'vendor_fitter_numeric_parity_verified':False,
            'clo_generated':False}
    (target/'comparison_private.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    summary={'stage':102,'status':report['status'],'frames':FRAMES,
             'fit_window':[FIT_START,FIT_END],
             'same_di_pcm16':True,'prewarm_off':conditions['off']['fit_window_300k_1500k'],
             'prewarm_on':conditions['on']['fit_window_300k_1500k'],
             'open_resampler_not_vendor_verified':True,
             'vendor_nam_inference_parity_verified':False,
             'private_report':str(target/'comparison_private.json')}
    return summary


def doctor(model:Path,bundle:Path):
    s100=stage100();s99,_,mode,_,_,native=s100.preflight(model)
    a,b=authentic_wavs(bundle)
    content=candidate_source()
    return {'status':'STAGE102_PREFLIGHT_PASS','model_mode':mode,
            'vendor_wav_48k_frames':ORIGINAL_FRAMES,
            'source_dart_sha256':sha(SONIC_SOURCE),
            'dart_found':bool(shutil.which('dart')),
            'di_present':REFERENCE_GZ.is_file(),
            'existing_private_run':(PRIVATE/(s99.sha(model)[:16]+'_stage102_open_sonicmaster_di_resample_v1')).exists(),
            'vendor_model_proven_identical':False,'source_derived_candidate_only':True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('doctor','run'))
    p.add_argument('--model',type=Path,required=True)
    p.add_argument('--stage97-zip',type=Path,required=True)
    a=p.parse_args()
    result=doctor(a.model,a.stage97_zip) if a.action=='doctor' else run(a.model,a.stage97_zip)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,json.JSONDecodeError) as e:
        print('[Stage102] '+str(e),file=sys.stderr)
        sys.exit(2)
