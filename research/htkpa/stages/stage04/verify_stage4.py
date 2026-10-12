#!/usr/bin/env python3
"""Read-only static trace of Sonicake HTKPA's last FIR stage.

Requires GNU objdump and supplied DLL/CLOs. Does not run vendor code.
Never writes to the source files, a pedal, or the project repository.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess
from pathlib import Path

EXPECTED_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BASE = 0x180000000

# Exact assembly instructions to verify in the DLL pinned above.
PROOFS = {
    'initialize_post_zero': (0x1800bed51,'call   0x1800a504e'),
    'initialize_post_impulse': (0x1800bed5d,'0x3f800000'),
    'post_initial_filter_apply': (0x1800bed78,'call   0x1800c0d40'),
    'three_stage_optimizer': (0x1800bf0c9,'call   0x1800bb210'),
    'spectral_finalizer': (0x1800bf11e,'call   0x1800b9b70'),
    'pre_context_ptr': (0x1800bf12e,'0x24408'),
    'pre_context_copy': (0x1800bf135,'call   0x1800c0d40'),
    'post_context_ptr': (0x1800bf141,'0x24410'),
    'post_context_copy': (0x1800bf14f,'call   0x1800c0d40'),
    'pack_pre_tap_count': (0x1800bf263,'0x20ed4'),
    'pack_post_tap_count': (0x1800bf27a,'0x20ed8'),
    'pre_raw_filter_copy': (0x1800bf320,'0x24408'),
    'pre_resample_call': (0x1800bf364,'call   0x18000ce00'),
    'pre_tail_zero': (0x1800bf386,'call   0x1800a504e'),
    'post_raw_filter_copy': (0x1800bf440,'0x24410'),
    'post_resample_call': (0x1800bf47f,'call   0x18000ce00'),
    'post_tail_zero': (0x1800bf4a7,'call   0x1800a504e'),
    'crc_container_magic': (0x1800bf4df,'0x49535456'),
    'raw_input_length': (0x18000d031,'[rsi+0x4]'),
    'resample_multiply_target_rate': (0x18000d039,'mulss  xmm0,xmm8'),
    'resample_divide_source_rate': (0x18000d03e,'divss  xmm0,xmm9'),
    'resample_trunc_output_len': (0x18000d043,'cvttss2si rbx,xmm0'),
    'resample_allocate_output': (0x18000d065,'call   0x180012340'),
}

def sections(blob):
    assert blob[:2] == b'MZ'
    off = struct.unpack_from('<I',blob,0x3c)[0]
    assert blob[off:off+4] == b'PE\0\0'
    n,sz = struct.unpack_from('<H',blob,off+6)[0],struct.unpack_from('<H',blob,off+20)[0]
    sec=off+24+sz
    return [struct.unpack_from('<IIII',blob,sec+40*i+8) for i in range(n)]

def uva(blob,sec,va,fmt):
    rva=va-BASE
    for virt_size, virt_addr, raw_size, raw_off in sec:
        if virt_addr<=rva<virt_addr+raw_size:
            return struct.unpack_from(fmt,blob,raw_off+(rva-virt_addr))[0]
    raise AssertionError(f'Address not mapped: 0x{va:x}')

def disasm(dll,lo,hi):
    r=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],capture_output=True,text=True,check=True)
    return {int(s.split(':')[0],16):s.strip() for s in r.stdout.splitlines() if re.match(r'^\s*[0-9a-fA-F]+:',s)}

def crc16(data):
    crc=65535
    for x in data:
        crc^=x
        for _ in range(8): crc=(crc>>1)^(0xA001 if crc&1 else 0)
    return crc

def read_clo(p):
    data=p.read_bytes()
    assert len(data)==8840 and data[:4]==b'VTSI'
    assert crc16(data[12:]) == struct.unpack_from('>H',data,8)[0], f'bad CRC: {p}'
    assert struct.unpack_from('<III',data,0x78)==(0,128,128)
    return {'pre':struct.unpack_from('<128f',data,136),'post':struct.unpack_from('<2048f',data,648),'raw':data}

def support(a):
    active=[i for i,v in enumerate(a) if v!=0]
    assert len(active)>0
    assert active[0]==0 and active==list(range(active[-1]+1)), 'unexpected gap in nonzero taps'
    return {'nonzero':len(active), 'last_nonzero_index':active[-1], 'trailing_zeros':len(a)-len(active)}

def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cosine(a,b):return dot(a,b)/(math.sqrt(dot(a,a))*math.sqrt(dot(b,b)))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dll',required=True,type=Path)
    ap.add_argument('--official-2203',required=True,type=Path)
    ap.add_argument('--void-2203',required=True,type=Path)
    ap.add_argument('--official-sc20',required=True,type=Path)
    ap.add_argument('--void-sc20',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    args=ap.parse_args()
    binary=args.dll.read_bytes()
    sha=hashlib.sha256(binary).hexdigest()
    assert sha==EXPECTED_SHA, f'unexpected DLL SHA256: {sha}'
    source=disasm(args.dll,0x1800bed00,0x1800bf550)
    source.update(disasm(args.dll,0x18000ce00,0x18000d0a0))
    result_proofs={}
    for name,(at,needle) in PROOFS.items():
        line=source.get(at,'')
        assert needle in line, f'{name}: expected {needle!r} in {line!r}'
        result_proofs[name]=line
    sect=sections(binary)
    target_rate=uva(binary,sect,0x18024cdf0,'<f')
    assert target_rate==44100., target_rate
    header={}
    for name,off,v in [('sample_rate_target',0x18024cdf0,44100.)]:header[name]=uva(binary,sect,off,'<f')
    # Source rate is grounded in the vendor's 48-kHz NAM-output WAV and
    # corroborated by tap supports, not obtained by executing any DLL context.
    source_rate=48000.
    predicted={str(n):int(struct.unpack('<f',struct.pack('<f',n*target_rate/source_rate))[0]) for n in [128,2048]}
    assert predicted=={'128':117,'2048':1881}
    cases={}
    for k,offs,vod in [('JCM800_2203',args.official_2203,args.void_2203),('SC20_Full_Rig',args.official_sc20,args.void_sc20)]:
        a,b=read_clo(offs),read_clo(vod)
        for lab,clo in [('official',a),('void',b)]:
            for which in ['pre','post']:
                observed=support(clo[which]);assert observed['nonzero']==predicted[str(len(clo[which]))], (k,lab,which,observed)
        cases[k]={
           'official_sha256':hashlib.sha256(a['raw']).hexdigest(),
           'void_sha256':hashlib.sha256(b['raw']).hexdigest(),
           'official_pre':support(a['pre']),'official_post':support(a['post']),
           'void_pre':support(b['pre']),'void_post':support(b['post']),
           'shape_difference':{
               'pre_tap_cosine':cosine(a['pre'],b['pre']),
               'post_tap_cosine':cosine(a['post'],b['post']),
               'post_first512_tap_cosine':cosine(a['post'][:512],b['post'][:512]),
           }
        }
    out={
      'research_status':'read-only; DLL never executed; production converter untouched',
      'dll_sha256':sha,'sample_rate_target_hz':target_rate,
      'source_rate_hz_inferred_from_output_wav':source_rate,
      'filter_effective_length_formula':'int32_truncate(input_taps * target_Hz / source_Hz)',
      'predicted_effective_taps':predicted,
      'verified_assembly_instructions':len(result_proofs),
      'static_assembly_proofs':result_proofs,'cases':cases,
      'critical_limitation':'This reproduces support/packing, NOT the 128/2048 nonzero coefficient values from NAM/WAV; official FIR coefficient generation is still unresolved.',
      'root_cause_caveat':'The Void baseline has the same 117/1881 support. Resampling does not explain its timbre discrepancy with Sonicake.'
    }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print('PASS',len(result_proofs),'static instructions; official and Void filters in 2 models verified')
    print('Output',args.out)
    for k,v in cases.items():
        print(k,'support',v['official_pre']['nonzero'],v['official_post']['nonzero'],'pre similarity',round(v['shape_difference']['pre_tap_cosine'],4),'post similarity',round(v['shape_difference']['post_tap_cosine'],4))

if __name__=='__main__':main()
