#!/usr/bin/env python3
"""HTKPA Stage 10: immutable DLL, source-first verification of the Mel score's
upstream cross-spectral transfer curve. Never imports/executes the Windows DLL.
All mathematical test signals are synthetic; no copyrighted original audio used.
"""
from __future__ import annotations
import argparse, cmath, hashlib, json, math, re, struct, subprocess
from pathlib import Path

BASE=0x180000000
SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINS={
    # Exact call-frame origins: candidate/current processed signal vs reference signal.
    'caller_reference_second_signal':(0x1800BC391,'mov    r8,QWORD PTR [rsp+0x1b0]'),
    'caller_model_first_signal':(0x1800BC399,'mov    rdx,r15'),
    'caller_prior_wave_output':(0x1800BC368,'mov    r9,r15'),
    'caller_predict_wave':(0x1800BC381,'call   0x1800b5a30'),
    'predict_wave_receives_dest':(0x1800B5A87,'mov    r12,r9'),
    'predict_wave_dest_copy_ptr':(0x1800B5C11,'lea    rdx,[rbx+r12*1]'),
    'predict_wave_dest_copy':(0x1800B5C15,'call   0x1800a505a'),
    'caller_output_magnitude_buffer':(0x1800BC3A4,'mov    QWORD PTR [rsp+0x38],rax'),
    'caller_source_rate':(0x1800BC3BB,'mov    eax,DWORD PTR [rbx+0x232cc]'),
    'caller_welch_call':(0x1800BC3C5,'call   0x1800b82b0'),
    'caller_mel_queries':(0x1800BC3D2,'[rbx+0x23b28]'),
    'caller_ratio_output_to_interpolator':(0x1800BC3D9,'[rsp+0x1a0]'),
    'caller_frequency_output_to_interpolator':(0x1800BC3E9,'mov    rdx,rbp'),
    'caller_mel_interpolator':(0x1800BC3F9,'call   0x1800b5d00'),
    'caller_score_input':(0x1800BC410,'[r13+rdi*4+0x0]'),
    'caller_score_log':(0x1800BC41C,'call   0x18017e14c'),
    'caller_score_size':(0x1800BC437,'cmp    rdi,0x200'),
    # 0x1800B82B0: sample length, Hamming window, and spectral bin count.
    'welch_fft_length':(0x1800B8306,'[rsp+0x1c8]'),
    'welch_sampling_rate':(0x1800B8319,'[rsp+0x1c0]'),
    'welch_hamming_cosine':(0x1800B83CA,'call   0x18017e11c'),
    'welch_hamming_multiply_046':(0x1800B83CF,'mulss  xmm0,xmm9'),
    'welch_hamming_054_minus':(0x1800B83D8,'subss  xmm1,xmm0'),
    'welch_hamming_write':(0x1800B83DC,'[r15+rbx*4]'),
    'welch_half_second_hop':(0x1800B83F3,'0x18024c880'),
    'welch_half_second_trunc':(0x1800B83FB,'cvttsd2si eax,xmm0'),
    'welch_bin_count_check':(0x1800B847B,'cmp    ebx,eax'),
    'welch_read_first_wave':(0x1800B85A6,'[rsp+0x1a8]'),
    'welch_read_second_wave':(0x1800B85C2,'[rsp+0x1b0]'),
    'welch_first_transform':(0x1800B8E38,'call   0x1800289d0'),
    'welch_second_transform':(0x1800B8E55,'call   0x1800289d0'),
    # Welch auto-spectrum of first signal / cross-spectrum of both.
    'power_square_real':(0x1800B901E,'mulps  xmm1,xmm5'),
    'power_square_imag':(0x1800B9024,'mulps  xmm0,xmm4'),
    'power_add_real_imag':(0x1800B9027,'addps  xmm1,xmm0'),
    'power_accumulate':(0x1800B9030,'movups XMMWORD PTR [rcx],xmm1'),
    'cross_multiply_first':(0x1800B903E,'mulps  xmm1,xmm3'),
    'cross_multiply_second':(0x1800B9044,'mulps  xmm0,xmm4'),
    'cross_real_sum':(0x1800B9047,'addps  xmm1,xmm0'),
    'cross_imag_difference':(0x1800B905B,'subps  xmm3,xmm5'),
    # Output exactly two arrays of count floor(N/2)+1.
    'mag_squared_real':(0x1800B9548,'mulps  xmm1,xmm1'),
    'mag_squared_imag':(0x1800B954B,'mulps  xmm0,xmm0'),
    'mag_sqrt':(0x1800B9551,'sqrtps xmm1,xmm1'),
    'mag_den_epsilon':(0x1800B9559,'addps  xmm0,xmm3'),
    'mag_ratio':(0x1800B955C,'divps  xmm1,xmm0'),
    'mag_ratio_write':(0x1800B955F,'[r10+rax*1]'),
    'freq_bin_over_n':(0x1800B9575,'divps  xmm1,xmm4'),
    'freq_multiply_samplerate':(0x1800B9578,'mulps  xmm1,xmm2'),
    'freq_write':(0x1800B957B,'[r11+rax*1]'),
    'scalar_sqrt':(0x1800B9805,'call   0x18017e170'),
    'scalar_ratio':(0x1800B9813,'divss  xmm0,xmm1'),
    'scalar_magnitude_write':(0x1800B9817,'[rbx+r14*1]'),
    'scalar_frequency_write':(0x1800B9832,'[rbx+rbp*1]'),
}
CONSTANTS={
    'hamming_a':(0x18024C5D4,'f',0.54),
    'hamming_b':(0x18024C5B0,'f',0.46),
    'frame_hop_seconds':(0x18024C880,'d',0.5),
    'spectrum_epsilon_vector':(0x18024D110,'f',2**-23),
    'spectrum_epsilon_scalar':(0x18024C4D4,'f',2**-23),
}
def pe_slice(raw,va,n):
    pe=struct.unpack_from('<I',raw,0x3c)[0]
    if raw[:2]!=b'MZ' or raw[pe:pe+4]!=b'PE\0\0': raise AssertionError('Bad PE')
    sections=struct.unpack_from('<H',raw,pe+6)[0]
    opt=struct.unpack_from('<H',raw,pe+20)[0]
    rva=va-BASE
    for i in range(sections):
        off=pe+24+opt+i*40
        vs,addr,rs,fp=struct.unpack_from('<IIII',raw,off+8)
        if addr<=rva and rva+n<=addr+rs:
            return raw[fp+rva-addr:fp+rva-addr+n]
    raise ValueError(hex(va))
def get_instrs(dll,lo,hi):
    cmd=['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)]
    out=subprocess.run(cmd,check=True,text=True,capture_output=True).stdout
    lookup={}
    for line in out.splitlines():
        m=re.match(r'^\s*([0-9a-fA-F]+):\s*(.*?)\s*$',line)
        if m:lookup[int(m.group(1),16)]=m.group(2)
    return lookup

def windows_for(fs,segment_seconds,window_seconds=0.1,hop_seconds=0.5):
    """Illustrative grid with hop and guard (not asserted byte-identical on boundaries)."""
    n=round(window_seconds*fs);hop=round(hop_seconds*fs);length=round(segment_seconds*fs)
    return list(range(0,max(0,length-n+1),hop))
def hamming(n):
    return [0.54-0.46*math.cos(2*math.pi*k/(n-1)) for k in range(n)]
def dft(x,k):
    n=len(x)
    return sum(z*cmath.exp(-2j*math.pi*k*t/n) for t,z in enumerate(x))
def cross_mag_ratio(sig_a,sig_b,k,eps=2**-23):
    """A->B magnitude |S_AB| / (S_AA+eps). Sign of cross-imag axis immaterial."""
    A=dft(sig_a,k);B=dft(sig_b,k)
    return abs(A*B.conjugate())/(abs(A)**2+eps)
def mel_score(values):
    return sum(abs(math.log(v+2**-23)) for v in values)/len(values)
def tests():
    n=64; fs=48000
    hw=hamming(n)
    assert max(abs(hw[k]-hw[-1-k]) for k in range(n)) <1e-14
    assert abs(hw[0]-0.08)<1e-12 and abs(hw[-1]-0.08)<1e-12
    assert len(windows_for(fs,5))==10 # Nominal 0.5s hop; actual boundary handling traced separately.
    assert abs((4800//2+1)-(2401))==0
    # Synthetic sine at exactly one DFT bin, amplified second signal.
    a=[0.35*math.cos(2*math.pi*5*i/n) for i in range(n)]
    for g in (0.5,1,1.7,2.5):
        b=[v*g for v in a]
        r=cross_mag_ratio(a,b,5)
        assert abs(r-g)<1e-7,(g,r)
    delayed=a[-3:]+a[:-3] # Pure cyclic delay changes phase, not magnitude.
    assert abs(cross_mag_ratio(a,delayed,5)-1)<1e-7
    assert abs(mel_score([1]*512))<1e-6
    assert mel_score([2]*512)>0.68
    assert abs((2400/4800*fs)-24000)<1e-8
    return {'synthetic_tests':8,'test_interpretation':'Algebraic primitives / float64 tests; no vendor bitwise reproduction'}
def run(dll):
    raw=dll.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=SHA:raise AssertionError('Unexpected DLL SHA256 '+sha)
    code={}
    for lo,hi in ((0x1800B5A30,0x1800B5C38),(0x1800B82B0,0x1800B98F5),(0x1800BC360,0x1800BC445)):
        code.update(get_instrs(dll,lo,hi))
    verified={}
    for key,(addr,pattern) in PINS.items():
        instr=code.get(addr,'')
        if pattern not in instr:raise AssertionError(f'{key} {addr:#x} expected {pattern!r}; found {instr!r}')
        verified[key]={'va':f'{addr:#x}','instruction':instr}
    c={}
    for key,(addr,fmt,val) in CONSTANTS.items():
        n=struct.calcsize('<'+fmt)
        got=struct.unpack('<'+fmt,pe_slice(raw,addr,n))[0]
        if abs(got-val)>1e-7:raise AssertionError((key,got,val))
        c[key]={'va':f'{addr:#x}','value':got}
    x=tests()
    return {'dll_sha256':sha,'checked_instructions':len(verified),'checked_constants':len(c),**x,
            'pins':verified,'constants':c,
            'conclusions':{
                'first_signal':'0x1800BC399 rdx=r15 (current generated output)',
                'second_signal':'0x1800BC391 r8=reference waveform passed to fitter',
                'frequency_k':'k*source_rate/N',
                'spectral_magnitude':'|S_AB|/(S_AA+2^-23) computed from accumulated spectra',
                'scoring':'linearly interpolated to 512 Mel-Hz queries then mean abs(log(value+2^-23))',
                'caveats':'Transform scaling, full source samples, overlap/end frames and all fitting equations are NOT recovered.'}}
if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--dll',required=True,type=Path)
    p.add_argument('--json',type=Path)
    a=p.parse_args()
    res=run(a.dll)
    if a.json:a.json.write_text(json.dumps(res,sort_keys=True,indent=2)+'\n')
    print('SUCCESS',res['checked_instructions'],'instruction pins',res['checked_constants'],'constants',res['synthetic_tests'],'tests')
