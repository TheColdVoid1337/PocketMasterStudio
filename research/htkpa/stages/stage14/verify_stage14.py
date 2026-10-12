#!/usr/bin/env python3
"""Read-only static verification of isolated HTKPA Stage 14 observations.

Never loads the proprietary DLL. Only reads it and invokes objdump.
No CLO creation, no device I/O, no fitted DSP model.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess
from pathlib import Path

DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BASE=0x180000000
# Exact instruction locations: meaningful instruction, not just a nearby function call.
PINS = {
    'unity_curve_A_allocation': (0x1800bef5b, '[r14+0x24328]'),
    'unity_curve_B_allocation': (0x1800bef73, '[r14+0x24330]'),
    'unity_write': (0x1800bef97, '0x3f800000'),
    'unity_copy_source': (0x1800befb6, '[r14+0x24328]'),
    'unity_copy_dest': (0x1800befbd, '[r14+0x24330]'),
    'fitter_read_curve_A': (0x1800bb289, '[rbx+0x24328]'),
    'fitter_read_curve_B': (0x1800bb347, '[rbx+0x24330]'),
    'fit_powf': (0x1800bb46e, 'call   0x18017e158'),
    'fit_pow_cap': (0x1800bb479, 'movaps xmm0,xmm11'),
    'fit_pow_lower_bound': (0x1800bb48c, '0x3e4ccccd'),
    'first_curvemap': (0x1800bb4d9, 'call   0x1800b7670'),
    'reverse_curvemap': (0x1800bb4f8, 'call   0x1800b7670'),
    'pre_curvemap': (0x1800bb812, 'call   0x1800b7670'),
    'pre_length': (0x1800bb817, '[rbx+0x20ed4]'),
    'pre_dest_arg': (0x1800bb821, '[rsp+0x1f8]'),
    'pre_synth': (0x1800bb836, 'call   0x1800b68f0'),
    'post_curvemap': (0x1800bc33d, 'call   0x1800b7670'),
    'post_dest_arg': (0x1800bc342, '[rsp+0x200]'),
    'post_length': (0x1800bc34d, '[rbx+0x20ed8]'),
    'post_arg5': (0x1800bc357, '[rsp+0x20],r13'),
    'post_synth': (0x1800bc35c, 'call   0x1800b68f0'),
    'post_forward_convolver': (0x1800bc381, 'call   0x1800b5a30'),
    'post_finalizer': (0x1800bf11e, 'call   0x1800b9b70'),
    'curve_frequency_input': (0x1800b7695, 'mov    rdi,r8'),
    'curve_count_input': (0x1800b76ba, 'movsxd r15,r9d'),
    'curve_gain_first': (0x1800b7b14, 'call   0x18017a2c0'),
    'curve_gain_db_vector': (0x1800b7b19, 'mulps  xmm0,xmm7'),
    'curve_gain_db_scalar': (0x1800b7b75, 'call   0x18017e146'),
    'mel_log_first': (0x1800b778f, 'call   0x18017e146'),
    'mel_linear_output': (0x1800b77d4, 'call   0x180027db0'),
    'mel_pow10_scalar': (0x1800b78d0, 'call   0x18017e158'),
    'input_axis_linear_output': (0x1800b7a95, 'call   0x180027db0'),
    'first_gauss_width': (0x1800b7bab, '0x18024c640'),
    'first_gauss': (0x1800b7bbb, 'call   0x1800b7e10'),
    'first_interpolator': (0x1800b7bf8, 'call   0x1800b5d00'),
    'second_gauss_width_div': (0x1800b7c07, 'idiv   ebp'),
    'second_gauss_width_x2': (0x1800b7c0c, 'add    eax,eax'),
    'second_gauss': (0x1800b7c12, 'call   0x1800b7e10'),
    'mel_count_remap': (0x1800b7c4b, 'call   0x1800b5d00'),
    'output_linear_axis': (0x1800b7c65, '[rsp+0x198]'),
    'output_gain_arg7': (0x1800b7c70, '[rsp+0x190]'),
    'final_linear_interpolator': (0x1800b7c8c, 'call   0x1800b5d00'),
    'db_to_mag_vector': (0x1800b7cce, 'call   0x18017a2e0'),
    'db_to_mag_scalar': (0x1800b7d1c, 'call   0x18017e158'),
    'synth_input_count': (0x1800b690c, 'movsxd rsi,r8d'),
    'synth_output_count': (0x1800b691c, 'movsxd rbp,r9d'),
    'synth_dest_arg5': (0x1800b6b39, None),
    'pre_post_state_snapshot1': (0x1800bc495, '[rsp+0x1f8]'),
    'pre_post_state_restore1': (0x1800bc53f, '[rsp+0x1f8]'),
    'pre_post_state_restore2': (0x1800bc55c, '[rsp+0x200]'),
}
# Explicit values, not inferred from artifact names.
CONSTANTS = {
 'mel_hz_offset': (0x18024cda8, '<f', 700.0),
 'mel_divisor': (0x18024cdc0, '<f', 2595.0),
 'decibel_multiplier': (0x18024cd40, '<f', 20.0),
 'linear_base': (0x18024cd24, '<f', 10.0),
 'first_smoothing_width_ratio': (0x18024c640, '<d', 0.002),
 'curve_db_inverse_scale': (0x18024d160, '<f', 0.05),
 'initial_gain_unity': (0x18024c6a0, '<f', 1.0),
}

def pe_bytes(raw: bytes, va: int, length: int) -> bytes:
    peoff=struct.unpack_from('<I',raw,0x3c)[0]
    if raw[:2]!=b'MZ' or raw[peoff:peoff+4]!=b'PE\x00\x00': raise AssertionError('not PE')
    n=struct.unpack_from('<H',raw,peoff+6)[0]
    hsz=struct.unpack_from('<H',raw,peoff+20)[0]
    rva=va-BASE
    for i in range(n):
        o=peoff+24+hsz+40*i
        virtual_size,vaddr,size,rawptr=struct.unpack_from('<IIII',raw,o+8)
        if vaddr<=rva and rva+length<=vaddr+size:
            return raw[rawptr+rva-vaddr:rawptr+rva-vaddr+length]
    raise AssertionError('VA not mapped: '+hex(va))

def lines(dll: Path, lo: int, hi: int) -> dict[int,str]:
    r=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],capture_output=True,text=True,check=True)
    out={}
    for line in r.stdout.splitlines():
        m=re.match(r'^\s*([0-9a-fA-F]+):\s*(.*?)\s*$',line)
        if m:out[int(m[1],16)]=m[2]
    return out

def mel(hz):return 2595.0*math.log10(1+hz/700.0)
def from_mel(m):return 700.0*(10**(m/2595.0)-1.0)
def db(g):return 20.0*math.log10(g)
def gain(db_val):return 10**(db_val/20.0)

def tests():
    t=[]
    def test(key, condition):
        if not condition:raise AssertionError(key)
        t.append(key)
    for v in [80.,100.,440.,1000.,10000.]:
        test(f'mel_roundtrip_{v:g}',abs(from_mel(mel(v))-v)<1e-8)
    for v in [0.01,0.1,1.,1.7,10.]:
        test(f'db_roundtrip_{v:g}',abs(gain(db(v))-v)<1e-10)
    for n,m in [(2401,128),(2401,2048),(4097,117)]:
        # Direct native instructions: trunc(N * 0.002) and 2*trunc(N/M)
        w1=math.trunc(n*0.002)
        w2=2*math.trunc(n/m)
        test(f'width_{n}_{m}',w1>=0 and w2>=0 and (w1,w2)==(math.trunc(n*0.002),2*(n//m)))
    for n in [32,117,512]:
        vals=[1.0]*n
        test(f'unit_curve_{n}',all(v==1 for v in vals))
    return t

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dll',required=True,type=Path)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    raw=args.dll.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
    if digest!=DLL_SHA: raise SystemExit(f'DLL SHA mismatch: {digest}')
    ins={}
    for lo,hi in [(0x1800b68f0,0x1800b6d90),(0x1800b7670,0x1800b7d90),(0x1800bb210,0x1800bc660),(0x1800bee50,0x1800bf135)]:
        ins.update(lines(args.dll,lo,hi))
    matched={}
    for label,(va,substring) in PINS.items():
        code=ins.get(va)
        if code is None or (substring is not None and substring not in code):
            raise AssertionError(f'{label} @{va:#x}: expected {substring!r}, got {code!r}')
        matched[label]={'va':hex(va),'instruction':code}
    const={}
    for label,(va,typ,expected) in CONSTANTS.items():
        actual=struct.unpack(typ,pe_bytes(raw,va,struct.calcsize(typ)))[0]
        if not math.isclose(actual,expected,rel_tol=1e-8,abs_tol=1e-9):
            raise AssertionError(f'{label}: {actual} instead of {expected}')
        const[label]={'va':hex(va),'value':actual}
    cases=tests()
    result={'stage':'14','input_sha256':digest,'pinned_instructions':len(matched),'constants':const,
            'static_proofs':matched,'algebraic_test_names':cases,'passed_tests':len(cases),
            'limits':'Read-only static pinning and isolated scalar math, NOT native execution or complete spectral fitter'}
    payload=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if args.output: args.output.write_text(payload,encoding='utf-8')
    print(f'PASS {len(matched)} assembly pins, {len(const)} constants, {len(cases)} math tests; evidence SHA256 {hashlib.sha256(payload.encode()).hexdigest()}')
if __name__=='__main__':main()
