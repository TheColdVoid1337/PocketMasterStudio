#!/usr/bin/env python3
"""Stage23D: statically verify NAM-driven native Fs + WAV stream provenance.

Never loads or executes Sonicake DLL. It optionally inspects the user's local
NAM/WAV files. Vendor CLO data are NEVER inputs to this verifier.
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct, subprocess, wave
from pathlib import Path

DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
NAM_HASHES = {'2203':'29abbdbf982ee64b963d1d8de06848d1b06450a623bb08ba3ffefce146dfac42',
              'SC20':'509ad3d6dc31cf0539afe4a264ff7386d6282ffe9d1e0de4b6cce514b1915b11'}
PINS = {
  0x1800E20C1:'[rax+0x200],rsi',            # First argument, output CLO buffer
  0x1800E20EA:'[rdx+0x208],rcx',            # Next argument, input DI WAV
  0x1800E2134:'[rdx+0x210],rcx',            # Third argument, target output WAV
  0x1800E2157:'mov    rdx,r15',             # Fourth argument, NAM path
  0x1800E219C:'[rcx+0x218]',                # Store NAM path
  0x1800E2232:'[rcx+0x27c],r12d',          # mode 0
  0x180061305:'[rbx+0x210]',               # target WAV in export worker
  0x180061329:'[rbx+0x208]',               # input WAV in export worker
  0x18006137D:'call   0x180010e70',
  0x180010EAF:'mov    r13,r8',              # fourth NAM path, from worker r8
  0x180010EB2:'mov    r12,rdx',             # target
  0x180010EB5:'mov    r15,rcx',             # input
  0x180010F41:'mov    rax,qword ptr [r15]',
  0x180010F72:'lea    r8,[rsp+0x48]',      # second WAV target
  0x180010F77:'lea    rdx,[rsp+0x50]',     # first WAV input
  0x180010F7F:'call   0x18000e0e0',        # Model/render and frequency detection
  0x18000E154:'mov    r15,rcx',            # first E0E0 arg: NAM model descriptor
  0x18000E2EF:'mov    rdi,r15',
  0x18000E65D:'call   0x180008b80',        # UTF conversion of NAM path
  0x18000E698:'call   0x1800cc4e0',       # parse NAM metadata
  0x18000E855:'[rbx+0x18]',               # model sampleRate DOUBLE
  0x18000E85B:'cvtpd2ps xmm9,xmm9',
  0x18000E8A2:'0x180244800',              # exact PE string: [NAM] model sampleRate:
  0x18000E9B8:'comiss xmm6,xmm9',
  0x18000E9EA:'0x18024cdf4',              # fallback 48000.0f
  0x18000F620:'cvttss2si ebx,xmm9',       # return selected model Fs
  0x18000F66B:'mov    eax,ebx',
  0x180011016:'movaps xmm2,xmm6',         # selected Fs to WAV resampler
  0x180011019:'mov    rdx,qword ptr [r15]',# First input WAV path
  0x180011021:'call   0x18000d4a0',
  0x1800110AD:'call   0x180010230',
  0x180010453:'movaps xmm1,xmm6',         # model Fs initializes native context
  0x180010489:'call   0x1800bf9f0',       # first loader
  0x1800104BD:'call   0x1800bf5e0',       # reference loader
  0x1800BFA27:'[rcx+0x243e0]',           # first buffer
  0x1800BF617:'[rcx+0x243e8]',           # target buffer
  0x180142201:'[rdx]',                   # input channels
  0x180142223:'[rax]',                   # channel 0 selected
  0x1800BFC2C:'[rax]',                   # input loader channel-0 pointer
  0x1800BFCA7:'[rdx+r15*1]',             # 32-bit source sample load
  0x1800BFCAB:'[rdx+rcx*1]',             # native input f32 copy
  0x1800BEDE4:'call   0x1800bdbe0',      # before separate IIR
}
STRINGS={0x1802446D8:'[NAM] ========== getNamOutput start ==========',
         0x180244708:'[NAM] namFile: ',
         0x180244730:'[NAM] outputFile: ',
         0x180244800:'[NAM] model sampleRate: ',
         0x180244820:'[NAM] WARN sampleRate<=0, using 48000'}
RANGES=[(0x1800E1F70,0x1800E2240),(0x180060F20,0x180061390),
 (0x180010E70,0x1800110C0),(0x18000E0E0,0x18000F675),
 (0x180010230,0x1800104F0),(0x1800BF9F0,0x1800BFCC0),
 (0x1800BF5E0,0x1800BF635),(0x1801421C0,0x180142250),
 (0x1800BE830,0x1800BEDEF)]

def pe_at(data:bytes,addr:int,n:int)->bytes:
    if data[:2]!=b'MZ':raise ValueError('not PE MZ')
    o=struct.unpack_from('<I',data,0x3c)[0]
    if data[o:o+4]!=b'PE\0\0':raise ValueError('not PE header')
    ns,optsz=struct.unpack_from('<H',data,o+6)[0],struct.unpack_from('<H',data,o+20)[0]
    base=struct.unpack_from('<Q',data,o+24+24)[0]
    for j in range(ns):
        p=o+24+optsz+40*j
        vsize,rva,rawsize,rawptr=struct.unpack_from('<4I',data,p+8)
        off=addr-base-rva
        if 0<=off and off+n<=rawsize:return data[rawptr+off:rawptr+off+n]
    raise ValueError(f'PE virtual addr has no raw bytes: {addr:#x}')

def check_source(dll:Path):
    data=dll.read_bytes();h=hashlib.sha256(data).hexdigest()
    if h!=DLL_SHA:raise ValueError(f'DLL hash mismatch {h}')
    lines=[]
    for lo,hi in RANGES:
        lines.extend(subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
                f'--start-address={lo}',f'--stop-address={hi}',str(dll)],text=True).splitlines())
    instr={}
    for s in lines:
        m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',s)
        if m:instr[int(m[1],16)]=' '.join(m[2].lower().split())
    checks=[]
    for va,expected in PINS.items():
        actual=instr.get(va,'')
        if ' '.join(expected.lower().split()) not in actual:
            raise AssertionError(f'{va:#x}: expected {expected!r}, got {actual!r}')
        checks.append({'va':hex(va),'asm':actual})
    string_results={}
    for va,value in STRINGS.items():
        got=pe_at(data,va,len(value)+1)
        if got!=value.encode('ascii')+b'\x00':raise AssertionError((hex(va),got))
        string_results[hex(va)]=value
    const=struct.unpack('<f',pe_at(data,0x18024CDF4,4))[0]
    assert const==48000.0
    return {'dll_sha256':h,'address_pins_passed':len(checks),'original_pe_log_strings':string_results,
            'native_fallback_fs':const,'checks':checks}

def extract_model_rates(obj):
    root=obj['sample_rate']
    subs=[s['model']['sample_rate'] for s in obj['config']['submodels']]
    if not subs: raise ValueError('no NAM submodels')
    return root,subs

def validate_nam(path:Path,model:str):
    b=path.read_bytes();h=hashlib.sha256(b).hexdigest()
    if h!=NAM_HASHES[model]:raise ValueError(f'{model}: unexpected NAM hash {h}')
    obj=json.loads(b)
    root,nested=extract_model_rates(obj)
    if root!=48000 or not nested or any(v!=48000 for v in nested):raise AssertionError('NAM sample rate mismatch')
    return {'model':model,'sha256':h,'root_sample_rate':root,'submodel_sample_rates':nested}

def wav_summary(path:Path):
    with wave.open(str(path),'rb') as w:
        return {'rate':w.getframerate(),'channels':w.getnchannels(),
                'sample_width':w.getsampwidth(),'frames':w.getnframes()}

def main():
    a=argparse.ArgumentParser();a.add_argument('--dll',type=Path,required=True)
    a.add_argument('--2203-nam',type=Path);a.add_argument('--sc20-nam',type=Path)
    a.add_argument('--2203-capture',type=Path);a.add_argument('--sc20-capture',type=Path)
    a.add_argument('--out',type=Path,required=True)
    args=a.parse_args();result={'stage':'23D','status':'SOURCE_PROVEN_RATE_AND_WAV_ROLES__NO_NUMERICAL_PARITY',
        'source':check_source(args.dll),'models':{}}
    for model,nam,capture in [('2203',args.__dict__['2203_nam'],args.__dict__['2203_capture']),
                              ('SC20',args.sc20_nam,args.sc20_capture)]:
        model_result={}
        if nam:model_result['NAM']=validate_nam(nam,model)
        if capture:
            x=wav_summary(capture/'nam_input_wav.wav');y=wav_summary(capture/'outputFile.wav')
            assert x=={'rate':44100,'channels':2,'sample_width':2,'frames':3087000}
            assert y=={'rate':48000,'channels':2,'sample_width':2,'frames':3360000}
            model_result['wav_DI']=x;model_result['wav_reference']=y
        result['models'][model]=model_result
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('PASS: source pins',result['source']['address_pins_passed'],'model metadata',
          ', '.join(m for m,v in result['models'].items() if v.get('NAM')) or 'not provided')
    print('OPEN: exact native resampler / audio scaling and independent vendor gains NOT COMPUTED')
if __name__=='__main__':main()
