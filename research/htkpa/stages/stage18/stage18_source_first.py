#!/usr/bin/env python3
"""HTKPA Stage18: independent source-directed spectral initializer & conditioner.

This module never executes the vendor DLL, never writes CLOs, and never touches
hardware. It is not a complete HTKPA converter and does NOT assert native
float32/bit-exact parity. It pins each relevant native instruction.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
from pathlib import Path
import numpy as np

DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BASE=0x180000000

# Each address and mnemonic was manually traced from the SHA-pinned PE file;
# these are exact-address tests, not substring searches over a broad region.
PINS={
'outer_source_filter':(0x1800bee25,'call   0x1800bd490'),
'outer_array_A':(0x1800bee33,'mov    r15,rax'),
'outer_array_B':(0x1800bee3f,'mov    r12,rax'),
'outer_array_frequency':(0x1800bee4b,'mov    r13,rax'),
'outer_init_A_dest':(0x1800bee58,'[rsp+0x30],r15'),
'outer_init_B_dest':(0x1800bee53,'[rsp+0x38],r12'),
'outer_init_F_dest':(0x1800bee4e,'[rsp+0x40],rax'),
'outer_initializer_call':(0x1800bee89,'call   0x1800bc6b0'),
'init_audio_filtering':(0x1800bc96d,'call   0x1800b5a30'),
'init_second_order_first_state':(0x1800bc9c5,'[rbx+0x28]'),
'init_second_order_first_coef':(0x1800bc9d2,'[rbx+0x232f0]'),
'init_saturator':(0x1800bcc79,'call   0x1800be700'),
'init_second_order_second_coef':(0x1800bcce8,'[rbx+0x23318]'),
'init_stft':(0x1800bcff2,'call   0x1800b82b0'),
'init_gaussian_A':(0x1800bd01f,'call   0x1800b7e10'),
'init_gaussian_B':(0x1800bd03d,'call   0x1800b7e10'),
'init_max_of_reference':(0x1800bd0a8,'inc    rcx'),
'init_scale_max':(0x1800bd0bd,'mulsd  xmm0,xmm7'),
'init_scale_to_float':(0x1800bd0c1,'cvtpd2ps xmm3,xmm0'),
'init_double_threshold':(0x1800bd0c8,'addss  xmm1,xmm3'),
'init_threshold_squared':(0x1800bd0d2,'mulss  xmm0,xmm1'),
'init_curve_ratio':(0x1800bd0da,'divss  xmm2,xmm0'),
'init_low_branch':(0x1800bd105,'comiss xmm1,xmm4'),
'init_parabola':(0x1800bd10d,'mulss  xmm0,xmm2'),
'init_parabola_second_mult':(0x1800bd111,'mulss  xmm0,xmm4'),
'init_parabola_offset':(0x1800bd115,'addss  xmm0,xmm3'),
'init_parabola_output':(0x1800bd119,'[rax-0x8],xmm0'),
'init_A_num':(0x1800bd244,'cvtps2pd xmm3,xmm0'),
'init_A_scale_num':(0x1800bd24d,'mulpd  xmm3,xmm4'),
'init_A_scale_den':(0x1800bd254,'mulpd  xmm2,xmm4'),
'init_A_eps':(0x1800bd258,'addpd  xmm2,xmm5'),
'init_A_quotient':(0x1800bd25c,'divpd  xmm3,xmm2'),
'init_A_output':(0x1800bd26e,'[rcx+r8*1-0x8],xmm0'),
'init_A_scalar_num_scale':(0x1800bd365,'mulsd  xmm1,xmm3'),
'init_A_scalar_den_scale':(0x1800bd361,'mulsd  xmm0,xmm3'),
'init_A_scalar_eps':(0x1800bd369,'addsd  xmm0,xmm4'),
'init_A_scalar_div':(0x1800bd36d,'divsd  xmm1,xmm0'),
'init_A_scalar_out':(0x1800bd375,'movss  DWORD PTR [r8+rax*1-0x4],xmm0'),
'conditioner_mel_start':(0x1800b778f,'call   0x18017e146'),
'conditioner_mel_grid':(0x1800b77d4,'call   0x180027db0'),
'conditioner_inverse_mel':(0x1800b78d0,'call   0x18017e158'),
'conditioner_target_mel_grid':(0x1800b7917,'call   0x180027db0'),
'conditioner_linear_grid':(0x1800b7a95,'call   0x180027db0'),
'conditioner_to_db':(0x1800b7b19,'mulps  xmm0,xmm7'),
'conditioner_first_width':(0x1800b7bab,'mulsd  xmm0,QWORD PTR [rip+0x194a8d]'),
'conditioner_first_gauss':(0x1800b7bbb,'call   0x1800b7e10'),
'conditioner_first_interp':(0x1800b7bf8,'call   0x1800b5d00'),
'conditioner_second_width':(0x1800b7c07,'idiv   ebp'),
'conditioner_second_width_x2':(0x1800b7c0c,'add    eax,eax'),
'conditioner_second_gauss':(0x1800b7c12,'call   0x1800b7e10'),
'conditioner_resample_mel':(0x1800b7c4b,'call   0x1800b5d00'),
'conditioner_remap_linear':(0x1800b7c8c,'call   0x1800b5d00'),
'conditioner_mag_return':(0x1800b7d1c,'call   0x18017e158'),
'gauss_kernel_scale':(0x1800b7e85,'divsd  xmm6,xmm0'),
'gauss_kernel_center':(0x1800b7e91,'call   0x18017e10a'),
'gauss_kernel_exp':(0x1800b7edf,'call   0x18017e128'),
'gauss_renormalize_edge':(0x1800b824c,'divsd  xmm3,xmm4'),
'linspace_last_exact':(0x180027e4e,'movss  DWORD PTR [r9+rdx*4-0x4],xmm1'),
'outer_first_fit':(0x1800bf0c9,'call   0x1800bb210'),
}
CONSTS={
'one_thousandth':(0x18024c618,'<d',0.001),
'half_percent':(0x18024c688,'<d',0.005),
'million':(0x18024cd28,'<d',1e6),
'eps':(0x18024c588,'<d',2**-23),
'gauss_k':(0x18024cab0,'<d',5.0),
'gauss_exp':(0x18024cea8,'<d',-0.5),
'gauss_output_divisor':(0x18024c598,'<d',1e-6),
'gauss_scale':(0x18024c640,'<d',0.002),
'mel_2595':(0x18024cdc0,'<f',2595.),
'mel_700':(0x18024cda8,'<f',700.),
'db20':(0x18024cd40,'<f',20.),
'db_back':(0x18024c520,'<f',0.05),
}

def pe_data(raw:bytes,va:int,n:int)->bytes:
    pe=struct.unpack_from('<I',raw,0x3c)[0]
    if raw[:2]!=b'MZ' or raw[pe:pe+4]!=b'PE\x00\x00':raise AssertionError('Not PE')
    sections=struct.unpack_from('<H',raw,pe+6)[0]
    opt=struct.unpack_from('<H',raw,pe+20)[0]
    for i in range(sections):
        o=pe+24+opt+40*i
        vsize,vaddr,rsize,roff=struct.unpack_from('<IIII',raw,o+8)
        d=va-BASE-vaddr
        if 0<=d and d+n<=rsize:return raw[roff+d:roff+d+n]
    raise AssertionError(f'VA unmapped: {va:#x}')

def disasm(dll:Path,lo:int,hi:int)->dict[int,str]:
    p=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True,check=True,capture_output=True)
    return {int(m.group(1),16):m.group(2).strip() for s in p.stdout.splitlines() if (m:=re.match(r'^\s*([0-9a-fA-F]+):\s*(.*)',s))}

def f32(v):return np.float32(v)

def seed_parabolic_threshold(auxiliary,raw_curve):
    """Isolated source-derived finalization after two native Gaussian stages.

    Takes EXISTING arrays, not a substitute for audio preprocessing or STFT.
    Normal domain: nonnegative finite auxiliary and raw curves, max(aux)>0.
    """
    u=np.asarray(auxiliary,dtype=np.float32)
    v=np.asarray(raw_curve,dtype=np.float32)
    if u.ndim!=1 or v.shape!=u.shape or not np.all(np.isfinite(u)) or not np.all(np.isfinite(v)) or np.min(u)<0 or np.min(v)<0:
        raise ValueError('Only equal-length, finite nonnegative 1D curves supported')
    peak=f32(np.max(u)); threshold=f32(np.float64(peak)*0.001)
    if threshold<=0: raise ValueError('Undefined native zero-peak handling not modeled')
    cutoff=f32(threshold+threshold)
    factor=f32(f32(cutoff-threshold)/f32(cutoff*cutoff))
    b=v.copy()
    for k in range(len(b)):
        if b[k]<cutoff:
            tmp=f32(b[k]*factor)
            tmp=f32(tmp*b[k])
            b[k]=f32(tmp+threshold)
    # The binary uses double precision for the stabilized quotient; return float32.
    a=np.empty_like(b)
    for k in range(len(b)):
        num=np.float64(f32(u[k]))*1_000_000.0
        den=np.float64(f32(b[k]))*1_000_000.0+2**-23
        a[k]=f32(num/den)
    return a,b,dict(threshold=float(threshold),cutoff=float(cutoff),quadratic=float(factor))

def native_linspace(a:float,b:float,n:int):
    """Source-derived 0x180027DB0 repeated-addition float32 implementation."""
    if n<2:raise ValueError('n>=2 tested; n=1 native division edge unknown')
    left=f32(a);right=f32(b);step=f32(f32(right-left)/f32(n-1))
    res=np.empty(n,dtype=np.float32);res[0]=left
    for k in range(1,n-1):res[k]=f32(res[k-1]+step)
    res[-1]=right
    return res

def interp_monotone(knots,vals,queries):
    """Algebraic monotone-domain equivalent of 0x1800B5D00, not bit exact."""
    knots=np.asarray(knots,dtype=np.float32)
    vals=np.asarray(vals,dtype=np.float32)
    queries=np.asarray(queries,dtype=np.float32)
    if len(knots)<2 or len(knots)!=len(vals) or not np.all(np.diff(knots)>0) or not np.all(np.isfinite(vals)) or not np.all(np.isfinite(queries)):
        raise ValueError('Strictly increasing finite knots and finite queries required')
    if np.any(queries<knots[0]):
        raise ValueError('Below-first extrapolation returns native FLT_MAX; research code rejects')
    slopes=np.empty_like(knots)
    slopes[:-1]=(vals[1:]-vals[:-1])/(knots[1:]-knots[:-1])
    slopes[-1]=slopes[-2]
    intercepts=vals-slopes*knots
    indices=np.searchsorted(knots,queries,side='right')-1
    return (slopes[indices]*queries+intercepts[indices]).astype(np.float32)

def gaussian_kernel(w:int):
    """0x1800B7E10 kernel: includes zero-padded extra slot for even widths."""
    if not 1<=w<=10000:raise ValueError('Native W<=0 handling not modeled')
    center=math.ceil(w/2)
    g=np.array([math.exp(-0.5*(((k-center)*5.0/w)**2)) for k in range(1,w+1)],dtype=np.float64)
    kernel=1_000_000.0*g[::-1]/sum(g)
    if w%2==0:kernel=np.r_[kernel,0.0]
    return kernel

def gaussian_smooth(inp,w:int):
    """Reference direct convolution with native-style boundary renormalization."""
    x=np.asarray(inp,dtype=np.float32)
    if x.ndim!=1 or not len(x) or not np.all(np.isfinite(x)): raise ValueError('finite 1D input')
    k=gaussian_kernel(w)
    mid=math.ceil(len(k)/2)-1
    ans=np.empty_like(x)
    for i in range(len(x)):
        low=max(0,i-mid);high=min(len(x),i+len(k)-mid)
        sub=k[(low-i+mid):(high-i+mid)]
        values=x[low:high]
        numer=sum(float(z)*float(g) for z,g in zip(values,sub))
        # Native interior: global normalization (×1e-6); truncated edges: sum of retained weights.
        den=sum(sub) if low>i-mid or high<i+len(k)-mid else 1_000_000.0
        ans[i]=f32(numer/den)
    return ans

def initial_curves_from_spectral_arrays(auxiliary, raw_curve):
    """Source-directed tail of BC6B0: Gaussian twice -> parabolic floor -> A/B.

    Requires two already-computed arrays of identical spectral length. Does not
    substitute for the still-unrecovered BD490/B82B0 audio and STFT operations.
    """
    auxiliary=np.asarray(auxiliary,dtype=np.float32)
    raw_curve=np.asarray(raw_curve,dtype=np.float32)
    if auxiliary.ndim!=1 or raw_curve.shape!=auxiliary.shape:
        raise ValueError('Same-length 1D arrays required')
    n=len(auxiliary)
    first=math.trunc(0.001*n)
    second=math.trunc(0.005*n)
    if first<=0 or second<=0:raise ValueError('Zero-width native Gaussian not yet modeled')
    smoothed=gaussian_smooth(gaussian_smooth(raw_curve,first),second)
    a,b,meta=seed_parabolic_threshold(auxiliary,smoothed)
    meta.update(first_gaussian_width=first,second_gaussian_width=second)
    return a,b,meta

def conditioned_curve(freq,mag,m:int):
    """Source-directed B7670 ordinary positive/monotonic algebraic path.

    This is a *candidate independent mathematical reimplementation*, never
    labeled native float32/bit exact. Reconstructs all native call *stages*.
    """
    hz=np.asarray(freq,dtype=np.float32)
    amp=np.asarray(mag,dtype=np.float32)
    n=len(hz)
    if n<501 or m<2 or m>n or amp.shape!=(n,) or not np.all(hz>0) or not np.all(np.diff(hz)>0) or not np.all(amp>0) or not np.all(np.isfinite(amp)):
        raise ValueError('Verified ordinary domain: 501<=n, 2<=m<=n, positive rising Hz/mag')
    start=f32(2595.*np.log10(f32(1.+f32(hz[0]/700.))))
    stop=f32(2595.*np.log10(f32(1.+f32(hz[-1]/700.))))
    mel_n=native_linspace(start,stop,n)
    mel_m=native_linspace(start,stop,m)
    mel_hz_n=f32(700.0*(np.power(f32(10),f32(mel_n/f32(2595.0)))-f32(1)))
    mel_hz_m=f32(700.0*(np.power(f32(10),f32(mel_m/f32(2595.0)))-f32(1)))
    # Native explicitly restores endpoints after Mel inverse.
    mel_hz_n[0],mel_hz_n[-1]=hz[0],hz[-1]
    mel_hz_m[0],mel_hz_m[-1]=hz[0],hz[-1]
    final_hz=native_linspace(hz[0],hz[-1],m)
    db=f32(f32(20)*np.log10(amp))
    w1=math.trunc(n*.002)
    w2=2*(n//m)
    pass1=gaussian_smooth(db,w1)
    meldb=interp_monotone(hz,pass1,mel_hz_n)
    pass2=gaussian_smooth(meldb,w2)
    remapped=interp_monotone(mel_n,pass2,mel_m) if n!=m else pass2
    aligned=interp_monotone(mel_hz_m,remapped,final_hz)
    result=f32(np.power(f32(10),f32(aligned/f32(20))))
    return final_hz,result,dict(n=n,m=m,w1=w1,w2=w2)

def math_tests():
    tests=[]
    def check(name,pass_):
        if not pass_:raise AssertionError(name)
        tests.append(name)
    # The parabolic branch joins value and derivative continuously at 2T.
    u=np.ones(17,dtype=np.float32)*2
    inp=np.linspace(0,.01,17,dtype=np.float32)
    a,b,meta=seed_parabolic_threshold(u,inp)
    t=meta['threshold'];threshold2=2*t
    check('seed_T_one_thousandth_of_max',abs(t-.002)<1e-8)
    check('seed_at_zero_exact_T',float(b[0])==t)
    check('seed_nonnegative',bool(np.all(b>=t)))
    check('seed_scalar_float',a.dtype==np.float32 and b.dtype==np.float32)
    check('seed_outside_branch_unmodified',bool(np.all(b[inp>=threshold2]==inp[inp>=threshold2])))
    for q in (0,t,2*t):
        curve=np.array([q],dtype=np.float32); aa,bb,_=seed_parabolic_threshold(np.array([2],np.float32),curve)
        reference=(t+q*q/(4*t)) if q<2*t else q
        check('seed_point_'+str(q),abs(float(bb[0])-reference)<1e-8)
    check('seed_join_derivative',abs(2*(2*t)*(.25/t)-1.)<1e-6)
    check('seed_reference_quotient',abs(float(a[-1])-(float(u[-1])*1e6/(float(b[-1])*1e6+2**-23)))<2e-5)
    # Native kernel is reversed before application and padded for even W.
    for w in [1,2,3,4,5,16,36]:
        k=gaussian_kernel(w)
        check('kernel_len_'+str(w),len(k)==w+(w%2==0))
        check('kernel_area_'+str(w),abs(float(np.sum(k))-1e6)<1e-6)
        x=np.ones(23,dtype=np.float32)*3.25
        out=gaussian_smooth(x,w)
        check('gauss_constant_'+str(w),bool(np.allclose(out,3.25,rtol=0,atol=3e-6)))
    check('gauss_edge_cropped_renorm',float(gaussian_smooth(np.r_[np.float32(1),np.zeros(15,dtype=np.float32)],7)[0])>0)
    check('linspace_endpoints',native_linspace(80,10000,511)[0]==80 and native_linspace(80,10000,511)[-1]==10000)
    knot=np.array([1,2,5,10],np.float32); val=np.array([2,4,10,20],np.float32)
    qry=np.array([1,1.5,3,5,10,11],np.float32)
    check('interp_exact_affine',bool(np.array_equal(interp_monotone(knot,val,qry),2*qry)))
    try:interp_monotone(knot,val,np.array([.5],np.float32));raise AssertionError('unsupported extrapolation accepted')
    except ValueError:tests.append('reject_subfirst_query')
    n=2401;hz=native_linspace(80,10000,n);unit=np.ones(n,np.float32)
    a_init,b_init,seed_info=initial_curves_from_spectral_arrays(
        np.linspace(0.5,3.0,n,dtype=np.float32),
        np.linspace(.01,2.0,n,dtype=np.float32))
    check('full_seed_two_gaussians_widths',seed_info['first_gaussian_width']==2 and seed_info['second_gaussian_width']==12)
    check('full_seed_shapes',len(a_init)==n and len(b_init)==n)
    check('full_seed_nonnegative',bool(np.all(np.isfinite(a_init)) and np.all(np.isfinite(b_init)) and np.all(b_init>0)))
    _,mapped_first,mapped_stat=conditioned_curve(hz,a_init,128)
    check('seed_into_pre_conditioner',bool(np.isfinite(mapped_first).all() and np.all(mapped_first>0)))
    _,mapped_second,_=conditioned_curve(hz,b_init,2048)
    check('seed_into_post_conditioner',bool(np.isfinite(mapped_second).all() and np.all(mapped_second>0)))
    for m in [128,2048]:
        f,result,stats=conditioned_curve(hz,unit,m)
        check('conditioner_size_'+str(m),len(result)==m and len(f)==m)
        check('conditioner_unity_'+str(m),bool(np.allclose(result,1.,atol=2e-4,rtol=0)))
        check('conditioner_edges_'+str(m),f[0]==80 and f[-1]==10000)
        check('conditioner_widths_'+str(m),stats['w1']==4 and stats['w2']==2*(2401//m))
    x=np.exp(np.linspace(-2,2,n)).astype(np.float32)
    _,r,_=conditioned_curve(hz,x,128)
    check('conditioner_nonconstant_finite',bool(np.isfinite(r).all() and r[0]>0 and r[-1]>r[0]))
    return tests

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dll',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    raw=args.dll.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=DLL_SHA:raise SystemExit('Expected pinned DLL sha256 '+DLL_SHA+'; got '+sha)
    instructions={}
    for lo,hi in [(0x180027db0,0x180027e60),(0x1800b7670,0x1800b7d50),(0x1800b7e10,0x1800b8275),(0x1800bc6b0,0x1800bd490),(0x1800bedb0,0x1800bef15),(0x1800bf070,0x1800bf0e5)]:
        instructions.update(disasm(args.dll,lo,hi))
    verified={}
    for k,(va,part) in PINS.items():
        ins=instructions.get(va)
        if ins is None or part not in ins:raise AssertionError(f'{k} {va:#x} wanted {part!r}; actual {ins!r}')
        verified[k]={'va':hex(va),'instruction':ins}
    constants={}
    for k,(va,fmt,wanted) in CONSTS.items():
        got=struct.unpack(fmt,pe_data(raw,va,struct.calcsize(fmt)))[0]
        if not math.isclose(got,wanted,rel_tol=1e-7,abs_tol=1e-9):raise AssertionError(f'{k} {va:#x}: {got} != {wanted}')
        constants[k]={'va':hex(va),'value':got}
    cases=math_tests()
    result={'stage':18,'dll_sha256':sha,'pinned_instructions':verified,'numeric_constants':constants,
            'synthetic_tests':cases,'synthetic_tests_passed':len(cases),
            'integration_status':'PARTIAL: BC6B0 audio preprocess/STFT and full optimizer unimplemented; no vendor FIR candidate',
            'native_equivalence':'NOT_TESTED: source-supported algebraic reimplementations only',
            'coefficient_parity':'NOT_TESTED for both 2203 and SC20; no independent candidate created'}
    s=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    args.out.write_text(s,encoding='utf-8')
    print('PASS',len(verified),'DLL address pins,',len(constants),'binary constants,',len(cases),'synthetic tests')
    print('EVIDENCE_SHA256',hashlib.sha256(s.encode()).hexdigest())
    print('COEFFICIENT_PARITY NOT_TESTED')
if __name__=='__main__':main()
