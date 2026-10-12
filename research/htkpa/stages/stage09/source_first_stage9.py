#!/usr/bin/env python3
"""Stage 9: read-only SHA-pinned checks of Windows HTKPA DLL + independent scalar reconstruction.

No DLL code is loaded or executed. Proprietary DLL is supplied by the user locally;
no DLL bytes or disassembly are packaged in the research archive.
"""
import argparse, hashlib, json, math, re, struct, subprocess
from pathlib import Path

BASE=0x180000000
DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'

# Exact instruction-address predicates verified from this one supplied DLL.
PINS={
 'init_log10_high':(0x1800bfe50,'call   0x18017e146'),
 'init_log10_low':(0x1800bfe6c,'call   0x18017e146'),
 'mel_linear_fill':(0x1800bfe85,'call   0x180027db0'),
 'mel_output_base':(0x1800bfe92,'[rdi+0x23b2c]'),
 'mel_initial_80hz':(0x1800bfeb0,'0x42a00000'),
 'mel_power_input':(0x1800bfec0,'[rbx-0x800]'),
 'mel_div_2595':(0x1800bfecb,'divss  xmm1,xmm7'),
 'mel_pow10':(0x1800bfecf,'call   0x18017e158'),
 'mel_minus_one':(0x1800bfed4,'subss  xmm0,xmm8'),
 'mel_scale_700':(0x1800bfed9,'mulss  xmm0,xmm9'),
 'mel_write_next':(0x1800bfede,'movss  DWORD PTR [rbx],xmm0'),
 'mel_510_values':(0x1800bfea2,'mov    esi,0x1fe'),
 'mel_final_10000hz':(0x1800bfeec,'0x461c4000'),
 'linear_fill_first':(0x180027dbe,'movss  DWORD PTR [r9],xmm0'),
 'linear_fill_interval':(0x180027dca,'divss  xmm3,xmm2'),
 'linear_fill_last':(0x180027e4e,'movss  DWORD PTR [r9+rdx*4-0x4],xmm1'),
 'fitter_lookup_x':(0x1800bc3d2,'[rbx+0x23b28]'),
 'fitter_arg_x':(0x1800bc3f4,'mov    QWORD PTR [rsp+0x20],rax'),
 'fitter_arg_npoints':(0x1800bc3e1,'mov    r8d,r14d'),
 'fitter_arg_queries':(0x1800bc3ec,'0x200'),
 'fitter_output_ptr':(0x1800bc3e4,'[rsp+0x30],r13'),
 'fitter_call_interpolator':(0x1800bc3f9,'call   0x1800b5d00'),
 'piecewise_alloc_slopes':(0x1800b5d29,'[rip+0xd5c11]'),
 'piecewise_diff_y':(0x1800b5dcf,'subss  xmm1,DWORD PTR [rcx-0x8]'),
 'piecewise_slope':(0x1800b5dd4,'divss  xmm1,xmm0'),
 'piecewise_intercept':(0x1800b5deb,'subss  xmm0,xmm1'),
 'piecewise_test_above':(0x1800b6048,'comiss xmm1,xmm2'),
 'piecewise_nearest_lower':(0x1800b6050,'jbe    0x1800b6058'),
 'piecewise_apply_slope':(0x1800b60ed,'mulss  xmm0,DWORD PTR [r10]'),
 'piecewise_apply_intercept':(0x1800b60f2,'addss  xmm0,DWORD PTR [rbp+r8*4+0x0]'),
 'piecewise_output_write':(0x1800b60fe,'movss  DWORD PTR [rdi+r10*1],xmm0'),
 'piecewise_fallback_maxfloat':(0x1800b5feb,'0x18024ce08'),
 'score_read_output':(0x1800bc410,'[r13+rdi*4+0x0]'),
 'score_epsilon_add':(0x1800bc417,'addss  xmm0,xmm15'),
 'score_logf':(0x1800bc41c,'call   0x18017e14c'),
 'score_abs_mask':(0x1800bc42b,'andps  xmm1,xmm14'),
 'score_loop_512':(0x1800bc437,'cmp    rdi,0x200'),
 'score_normalize_512':(0x1800bc440,'0x18024c4f0'),
}

CONSTANTS={
 'mel_divisor':(0x18024cdc0,2595.0),
 'mel_base':(0x18024cd24,10.0),
 'mel_offset':(0x18024c6a0,1.0),
 'mel_hz_scale':(0x18024cda8,700.0),
 'mel_high_argument':(0x18024cd38,15.285714149475098),
 'mel_low_argument':(0x18024c6f8,1.1142857074737549),
 'intensity_fallback':(0x18024ce08,3.4028234663852886e38),
 'score_epsilon':(0x18024c4d4,2**-23),
 'score_average':(0x18024c4f0,1/512),
}

def pe_bytes(raw,va,n):
    p=struct.unpack_from('<I',raw,0x3c)[0]
    assert raw[:2]==b'MZ' and raw[p:p+4]==b'PE\x00\x00'
    num=struct.unpack_from('<H',raw,p+6)[0]
    sz=struct.unpack_from('<H',raw,p+20)[0]
    rva=va-BASE
    for i in range(num):
        off=p+24+sz+i*40
        vs,virtual,rawsize,ptr=struct.unpack_from('<IIII',raw,off+8)
        if virtual<=rva and rva+n<=virtual+rawsize:
            return raw[ptr+rva-virtual:ptr+rva-virtual+n]
    raise ValueError(hex(va))

def instructions(dll,lo,hi):
    x=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],capture_output=True,text=True,check=True)
    found={}
    for line in x.stdout.splitlines():
        m=re.match(r'^\s*([0-9a-fA-F]+):\s*(.*?)\s*$',line)
        if m:found[int(m.group(1),16)]=m.group(2)
    return found

def f32(v):return struct.unpack('<f',struct.pack('<f',v))[0]

def mel(hz):return 2595.0*math.log10(1.0+hz/700.0)
def inv_mel(m):return 700.0*(10.0**(m/2595.0)-1.0)

def compute_grid(n=512):
    # Mathematical representation of independently pinned DLL instructions.
    # DLL uses float32 intermediates and a linear-fill routine using repeated additions;
    # Python doubles differ by rounding within the final few Hz at the high end.
    low,high=mel(80.0),mel(10000.0)
    return [inv_mel(low+(high-low)*i/(n-1)) for i in range(n)]

def piecewise_map(a,b,queries):
    """Independent algebraic restatement of 0x1800B5D00 for finite strictly rising knots.
    Chooses the nearest knot with nonnegative (query-a[i]) residual, not closest absolute.
    Extrapolates above the last knot using the last segment; underflows -> FLT_MAX.
    """
    if len(a)!=len(b) or len(a)<2 or any(a[i+1]<=a[i] for i in range(len(a)-1)):
        raise ValueError('This replica models only nondegenerate increasing input knots')
    slopes=[(b[i+1]-b[i])/(a[i+1]-a[i]) for i in range(len(a)-1)]
    slopes.append(slopes[-1])
    intercept=[b[i]-slopes[i]*a[i] for i in range(len(a))]
    out=[]
    for q in queries:
        eligible=[(q-x,i) for i,x in enumerate(a) if q-x>=0]
        if not eligible: out.append(3.4028234663852886e38)
        else:
            j=min(eligible,key=lambda t:t[0])[1]
            out.append(slopes[j]*q+intercept[j])
    return out

def score(v):
    eps=2**-23
    return sum(abs(math.log(x+eps)) for x in v)/len(v)

def local_tests():
    g=compute_grid()
    assert len(g)==512 and abs(g[0]-80)<1e-9 and abs(g[-1]-10000)<1e-8
    assert all(g[i]<g[i+1] for i in range(511))
    assert abs(mel(g[200])-(mel(80)+(mel(10000)-mel(80))*200/511))<1e-10
    assert all(abs(v-z)<1e-8 for v,z in zip(piecewise_map([0,2,4],[1,5,9],[0,1,2,3,4,5]),[1,3,5,7,9,11]))
    assert piecewise_map([80,100],[1,2],[79])==[3.4028234663852886e38]
    assert abs(score([1.0]*512)) <1e-6
    assert abs(score([2.0]*512)-math.log(2.0+2**-23))<1e-10
    return {'unit_tests':7,'grid_freq_indices_hz':{'0':g[0],'1':g[1],'10':g[10],'100':g[100],'256':g[256],'511':g[511]},'grid_first_step_hz':g[1]-g[0],'grid_last_step_hz':g[-1]-g[-2]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('dll',type=Path)
    p.add_argument('--out',type=Path)
    args=p.parse_args()
    raw=args.dll.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    assert sha==DLL_SHA,f'Unexpected DLL SHA: {sha}'
    ins={}
    for lo,hi in [(0x180027db0,0x180027e60),(0x1800b5d00,0x1800b6131),(0x1800bc35c,0x1800bc448),(0x1800bfe00,0x1800bff10)]:ins.update(instructions(args.dll,lo,hi))
    evidence={}
    for key,(addr,part) in PINS.items():
        v=ins.get(addr,'')
        assert part in v, f'{key} expected {part!r} at {addr:x}; got {v!r}'
        evidence[key]={'va':hex(addr),'instruction':v}
    constants={}
    for k,(va,expected) in CONSTANTS.items():
        actual=struct.unpack('<f',pe_bytes(raw,va,4))[0]
        assert abs(actual-expected)<=max(1e-6,abs(expected)*1e-7),(k,actual,expected)
        constants[k]={'va':hex(va),'float32':actual}
    tests=local_tests()
    result={'dll_sha256':sha,'pinned_instructions':len(PINS),'constants':constants,'evidence':evidence,'local_tests':tests,'status':'Math and buffer lineage confirmed; meaning of source A/B curves and exact end-to-end FIR not yet recovered.'}
    if args.out:args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f"SHA verified, {len(PINS)} address pins, {len(constants)} constants, {tests['unit_tests']} synthetic mathematical tests passed")
    print('Mel-spaced grid sample [0,1,256,511]:',tests['grid_freq_indices_hz']['0'],tests['grid_freq_indices_hz']['1'],tests['grid_freq_indices_hz']['256'],tests['grid_freq_indices_hz']['511'])

if __name__=='__main__':main()
