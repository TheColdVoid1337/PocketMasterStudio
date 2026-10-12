#!/usr/bin/env python3
"""Read-only static verifier + independent scalar DSP checks for Sonicake HTKPA Stage 15.

Does not execute the DLL, generate hardware profiles, use private audio, or connect to a pedal.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess
from pathlib import Path
import numpy as np

SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BASE=0x180000000
# Exact machine-code addresses, instructions to test; anchors include both vector and scalar paths.
PINS={
 'feedback_spectrum_eval':(0x1800bc055,'call   0x1800b82b0'),
 'feedback_ratio_vector_numerator':(0x1800bc10d,'mulpd  xmm3,xmm4'),
 'feedback_ratio_vector_denominator':(0x1800bc114,'mulpd  xmm2,xmm4'),
 'feedback_ratio_vector_epsilon':(0x1800bc118,'addpd  xmm2,xmm5'),
 'feedback_ratio_vector_divide':(0x1800bc11c,'divpd  xmm3,xmm2'),
 'feedback_ratio_vector_write':(0x1800bc12e,'movsd'),
 'feedback_ratio_scalar_num':(0x1800bc226,'mulsd  xmm1,xmm6'),
 'feedback_ratio_scalar_den':(0x1800bc222,'mulsd  xmm0,xmm6'),
 'feedback_ratio_scalar_eps':(0x1800bc22a,'addsd  xmm0,xmm10'),
 'feedback_ratio_scalar_divide':(0x1800bc22f,'divsd  xmm1,xmm0'),
 'feedback_ratio_scalar_write':(0x1800bc237,'movss'),
 'feedback_curvemap':(0x1800bc33d,'call   0x1800b7670'),
 'feedback_post_ptr':(0x1800bc342,'[rsp+0x200]'),
 'feedback_post_synth':(0x1800bc35c,'call   0x1800b68f0'),
 'fit_end_finalizer_post_arg5':(0x1800bf100,'[r14+0x24410]'),
 'fit_end_finalizer_call':(0x1800bf11e,'call   0x1800b9b70'),
 'finalizer_support_times_0_1s':(0x1800b9bcb,'mulsd  xmm0,xmm12'),
 'finalizer_ceil':(0x1800b9bd0,'call   0x18017e10a'),
 'finalizer_output_second_filter':(0x1800ba3bc,'call   0x1800b63a0'),
 'finalizer_transform_1':(0x1800ba8a3,'call   0x1800b4cf0'),
 'finalizer_transform_2':(0x1800ba8bb,'call   0x1800b4cf0'),
 'finalizer_spectrum_magnitude':(0x1800ba97b,'call   0x18017e170'),
 'finalizer_ratio_vector_scale':(0x1800bac8b,'mulpd  xmm3,xmm4'),
 'finalizer_ratio_vector_den':(0x1800bac92,'mulpd  xmm2,xmm4'),
 'finalizer_ratio_vector_eps':(0x1800bac96,'addpd  xmm2,xmm5'),
 'finalizer_ratio_vector_div':(0x1800bac9a,'divpd  xmm3,xmm2'),
 'finalizer_clamp_max':(0x1800baeb3,'0x41200000'),
 'finalizer_clamp_min':(0x1800baec6,'0x3dcccccd'),
 'finalizer_gaussian_smooth':(0x1800baef9,'call   0x1800b7e10'),
 'finalizer_256_fir_apply':(0x1800baf88,'call   0x1800b65a0'),
 'finalizer_output_audio':(0x1800bafab,'call   0x1800b5a30'),
 'finalizer_rms_sqrt_target':(0x1800bb0c0,'call   0x18017e170'),
 'finalizer_rms_sqrt_render':(0x1800bb0cb,'call   0x18017e170'),
 'finalizer_rms_ratio':(0x1800bb0e2,'divss  xmm7,xmm0'),
 'finalizer_gain_mul':(0x1800bb12f,'mulps  xmm0,xmm2'),
 'corrector_scratch_256_1':(0x1800b65b8,'0x400'),
 'corrector_scratch_256_2':(0x1800b65cc,'0x400'),
 'corrector_resample_bins':(0x1800b65fd,'call   0x1800b7670'),
 'corrector_synth_256':(0x1800b6621,'call   0x1800b68f0'),
 'corrector_conv_accumulate':(0x1800b66aa,'addss  xmm0'),
 'corrector_conv_iterations':(0x1800b6694,'0x20'),
 'corrector_conv_outer_index':(0x1800b6751,'add    rdx,0x4'),
 'corrector_truncate_copy':(0x1800b6771,'call   0x1800a505a'),
 'corrector_mean_div':(0x1800b67ea,'divss  xmm2,xmm0'),
 'corrector_mean_sub':(0x1800b682b,'subps  xmm0,xmm3'),
 'corrector_scalar_mean_sub':(0x1800b68b0,'subss  xmm0,xmm2'),
}
CONSTANTS={
 'feedback_spectrum_multiplier':(0x18024d5a0,'<d',1000000.0),
 'feedback_epsilon':(0x18024d1e0,'<d',2**-23),
 'finalizer_spectrum_multiplier':(0x18024cd28,'<d',1000000.0),
 'finalizer_epsilon':(0x18024c588,'<d',2**-23),
 'finalizer_ratio_limit_hi':(0x18024cd24,'<f',10.0),
 'finalizer_ratio_limit_lo':(0x18024c7a0,'<d',0.1),
 'finalizer_support_seconds':(0x18024c7a0,'<d',0.1),
 'finalizer_energy_norm_1e_minus3':(0x18024c618,'<d',0.001),
}
def pe_read(b:bytes,va:int,n:int)->bytes:
    if b[:2]!=b'MZ': raise AssertionError('bad DOS magic')
    po=struct.unpack_from('<I',b,0x3c)[0]
    if b[po:po+4]!=b'PE\0\0': raise AssertionError('bad PE')
    sections=struct.unpack_from('<H',b,po+6)[0]
    opt=struct.unpack_from('<H',b,po+20)[0]
    rv=va-BASE
    for i in range(sections):
        off=po+24+opt+40*i
        vsize,rva,size,rawoff=struct.unpack_from('<IIII',b,off+8)
        if rva<=rv and rv+n<=rva+size: return b[rawff(rv,rva,rawoff):rawff(rv,rva,rawoff)+n]
    raise ValueError(hex(va))
def rawff(rv,rva,raw):return raw+rv-rva

def disasm(dll:Path,lo:int,hi:int):
    z=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],capture_output=True,text=True,check=True)
    out={}
    for line in z.stdout.splitlines():
        m=re.match(r'^\s*([a-fA-F0-9]+):\s*(.+)$',line)
        if m:out[int(m[1],16)]=m[2].strip()
    return out

def regularized_ratio(a,b):
    """Algebraic analog of native float->double->float vector division (no DLL)."""
    a=np.asarray(a,dtype=np.float32).astype(np.float64)
    b=np.asarray(b,dtype=np.float32).astype(np.float64)
    return (1e6*a/(1e6*b+2**-23)).astype(np.float32)

def correction_convolution(h,corr):
    """Clean-room scalar model of 256-tap truncated causal convolution + DC removal."""
    h=np.asarray(h,dtype=np.float32)
    corr=np.asarray(corr,dtype=np.float32)
    if len(corr)!=256:raise ValueError('expected native length 256')
    tmp=np.zeros(len(h)+255,dtype=np.float32)
    for k,v in enumerate(h):
        for i,c in enumerate(corr):
            tmp[k+i]=np.float32(tmp[k+i]+np.float32(v*c))
    result=tmp[:len(h)].copy()
    result=np.asarray(result-result.sum(dtype=np.float32)/np.float32(len(result)),dtype=np.float32)
    return result

def rms_gain_calibration(h,desired,generated):
    """Outer finalizer gain-ratio model; arrays must be the same DI window."""
    desired=np.asarray(desired,dtype=np.float32)
    generated=np.asarray(generated,dtype=np.float32)
    if desired.shape!=generated.shape:raise ValueError('matching shapes required')
    numerator=np.sqrt(np.sum(desired.astype(np.float64)**2))
    denominator=np.sqrt(np.sum(generated.astype(np.float64)**2))
    if denominator==0:raise ValueError('zero reference energy; native edge path unknown')
    return np.asarray(h,dtype=np.float32)*np.float32(numerator/denominator)

def tests():
    passed=[]
    def check(name,ok):
        if not bool(ok):raise AssertionError(name)
        passed.append(name)
    a=np.array([1.7,2.0,0.05],dtype=np.float32)
    b=np.array([1.,2.,1.],dtype=np.float32)
    z=regularized_ratio(a,b)
    check('unit_regularized_ratio',np.allclose(z,[1.7,1.,0.05],atol=1e-6))
    check('zero_numerator',regularized_ratio([0],[1])[0]==0)
    check('zero_both_is_zero',regularized_ratio([0],[0])[0]==0)
    check('scaled_epsilon',regularized_ratio([2],[0])[0]>1e12)
    check('scale_invariance_nonzero',np.allclose(regularized_ratio([1],[1]),regularized_ratio([2],[2]),atol=1e-6))
    # 256-tap identity corrective filter should yield DC-subtracted original.
    impulse=np.zeros(256,dtype=np.float32);impulse[0]=1
    h=np.array([1,2,4,8],dtype=np.float32)
    r=correction_convolution(h,impulse)
    check('conv_identity_dc',np.allclose(r,h-h.mean()))
    check('conv_has_zero_dc',abs(float(r.sum()))<2e-6)
    kernel=np.zeros(256,dtype=np.float32);kernel[:3]=[1,2,-1]
    r=correction_convolution(h,kernel)
    expected=np.convolve(h.astype(float),kernel.astype(float))[:len(h)]
    expected=expected-expected.mean()
    check('causal_truncated_conv',np.allclose(r,expected,atol=2e-6))
    check('causal_not_circular',not np.allclose(r,correction_convolution(h,np.roll(kernel,1))))
    # Factor of 3 reference output should raise FIR gain by 3.
    yy=np.array([1.,2.,4.],dtype=np.float32)
    h=np.array([0.2,-0.4],dtype=np.float32)
    check('match_rms_3x',np.allclose(rms_gain_calibration(h,3*yy,yy),3*h))
    check('match_rms_1x',np.allclose(rms_gain_calibration(h,yy,yy),h))
    try:rms_gain_calibration(h,yy,np.zeros_like(yy));check('rms_zero_rejected',False)
    except ValueError:check('rms_zero_rejected',True)
    try:correction_convolution(h,np.ones(128,dtype=np.float32));check('wrong_kernel_rejected',False)
    except ValueError:check('wrong_kernel_rejected',True)
    return passed

def main():
    p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True);p.add_argument('--out',type=Path)
    a=p.parse_args()
    raw=a.dll.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=SHA:raise AssertionError(f'Incorrect DLL SHA256 {sha}')
    lines={}
    for lo,hi in [(0x1800b65a0,0x1800b68f0),(0x1800b9b70,0x1800bb210),(0x1800bb210,0x1800bc600),(0x1800bf0f0,0x1800bf160)]:
        lines.update(disasm(a.dll,lo,hi))
    pins={}
    for label,(va,needle) in PINS.items():
        found=lines.get(va)
        if found is None or needle not in found:raise AssertionError(f'{label}: {va:x} expected {needle}; got {found}')
        pins[label]={'address':hex(va),'assembly':found}
    const={}
    for label,(va,typ,want) in CONSTANTS.items():
        got=struct.unpack(typ,pe_read(raw,va,struct.calcsize(typ)))[0]
        if not math.isclose(got,want,rel_tol=1e-12,abs_tol=1e-15):raise AssertionError(f'{label} {got} != {want}')
        const[label]={'address':hex(va),'value':got}
    cases=tests()
    result={'stage':15,'sha256_dll':sha,'verified_instruction_count':len(pins),'verified_instructions':pins,
            'constants':const,'test_names':cases,'passed_tests':len(cases),
            'limitations':'Static evidence + isolated original algebraic tests only; not complete or bit-exact HTKPA.'}
    evidence=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    if a.out:a.out.write_text(evidence,encoding='utf-8')
    print(f'PASS: {len(pins)} machine instructions, {len(const)} constants, {len(cases)} tests; evidence SHA256 {hashlib.sha256(evidence.encode()).hexdigest()}')
if __name__=='__main__':main()
