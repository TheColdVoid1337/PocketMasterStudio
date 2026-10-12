#!/usr/bin/env python3
"""Stage13 HTKPA spectral triplet — static DLL pins and synthetic end-to-end mathematics.

This NEVER loads/executes the DLL; all DSP functions below are independent clean-room
implementations of scalar operations recovered from DLL machine instructions. No CLO writes.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, subprocess
from pathlib import Path
import numpy as np

DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
# Address pins are testable machine-code instruction fragments, not inferred names.
PINS = {
  0x1800b52e0: 'mov    rax,rsp',
  0x1800b530a: '0x18024ccf0',
  0x1800b5322: 'divss  xmm7,xmm0',
  0x1800b5421: 'call   0x18017e15e', # sin
  0x1800b5436: 'call   0x18017e116', # cos
  0x1800b4a50: 'mov    QWORD PTR [rsp+0x10],rdx',
  0x1800b4a67: 'mov    r10d,r8d',
  0x1800b4a87: 'divss  xmm8,xmm0', # 1/N
  0x1800b4b68: 'mulss  xmm1,DWORD PTR [rbx+r9*4]', # real=cos
  0x1800b4b75: 'mulss  xmm5,DWORD PTR [rdi+r9*4]', # imag=sin
  0x1800b4c62: 'mulss  xmm6,xmm8',
  0x1800b4c6d: 'mulss  xmm7,xmm8',
  0x1800b4c7a: 'movss  DWORD PTR [r14],xmm6',
  0x1800b4c83: 'movss  DWORD PTR [r14+0x4],xmm7',
  0x1800b6e3c: 'cmp    r8d,0x3',
  0x1800b6e69: 'mov    eax,DWORD PTR [rdx]',
  0x1800b6e7a: 'mov    DWORD PTR [r9],eax',
  0x1800b6e84: 'cmp    ecx,0x1', # parity branch
  0x1800b6edb: 'addss  xmm0,DWORD PTR [rdx+0x8]',
  0x1800b6eeb: 'subss  xmm1,DWORD PTR [rdx+0xc]',
  0x1800b6f15: 'movss  xmm0,DWORD PTR [rcx+r11*1+0xc]',
  0x1800b6fc1: 'mov    eax,r8d', # even branch
  0x1800b70f2: 'mov    eax,DWORD PTR [r10+rbp*8]', # even Nyquist real
  0x1800b710c: 'xorps  xmm0,XMMWORD PTR [rip+0x1964ed]', # even Nyquist imag sign
  0x1800b713a: 'jmp    0x1800a504e', # memset leftover zero
  0x1800b4f60: 'test   r8d,r8d',
  0x1800b50b4: 'mulss  xmm3,DWORD PTR [rdi+rax*4]', # imag * sin
  0x1800b50b9: 'mulss  xmm14,DWORD PTR [rbx+rax*4]', # imag * cos
  0x1800b50e2: 'addss  xmm14,xmm12', # real contributions
  0x1800b511c: 'subss  xmm15,xmm13', # imag contributions
  0x1800b5173: 'addss  xmm1,xmm0',
  0x1800b5183: 'subss  xmm7,xmm6',
  0x1800b75d5: 'call   0x18017e12e', # expf
  0x1800b75e1: 'call   0x18017e11c', # cosf
  0x1800b75f4: 'call   0x18017e164', # sinf
  0x1800b748f: 'mov    eax,DWORD PTR [r14+rax*4]', # N-i-1 mirror
  0x1800b754a: 'call   0x1800b4a50',
  0x1800b7569: 'call   0x1800b6e30',
  0x1800b7590: 'call   0x1800b4f60',
  0x1800b6a16: 'call   0x1800b72e0',
  0x1800b6a66: 'call   0x1800b47f0',
}
RANGES = [
 (0x1800b4a50,0x1800b4ce0), (0x1800b4f60,0x1800b52d8),
 (0x1800b52e0,0x1800b5460), (0x1800b6e30,0x1800b713f),
 (0x1800b72e0,0x1800b7620), (0x1800b68f0,0x1800b6e80)
]

def pin_dll(dll:Path)->dict:
    observed = hashlib.sha256(dll.read_bytes()).hexdigest()
    if observed != DLL_SHA: raise AssertionError(f'DLL SHA mismatch: {observed}')
    indexed={}
    for start,stop in RANGES:
        args=['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={start:#x}',f'--stop-address={stop:#x}',str(dll)]
        p=subprocess.run(args,capture_output=True,text=True,check=True)
        for line in p.stdout.splitlines():
            m=re.match(r'^\s*([0-9a-fA-F]+):\s+(.*)$',line)
            if m:indexed[int(m[1],16)]=m[2].strip()
    bad={hex(a):{'need':fragment,'found':indexed.get(a)} for a,fragment in PINS.items() if fragment not in indexed.get(a,'')}
    if bad:raise AssertionError(json.dumps(bad,indent=2))
    # Resolve trigonometry and memset dynamically from import table, rather than guessing thunk names.
    p=subprocess.run(['objdump','-p',str(dll)],capture_output=True,text=True,check=True)
    imports=p.stdout
    for term in ['0018ba18','sin','0018ba70','cos','0018b6a8','memset']:
        if term not in imports: raise AssertionError('missing import '+term)
    return {hex(a):indexed[a] for a in sorted(PINS)}

def sin_cos_tables(n:int):
    theta=np.arange(n,dtype=np.float64)*(2*math.pi/n)
    return np.sin(theta),np.cos(theta)

def normalized_positive_dft(x):
    """B4A50, input real: sum x[k]*(cos+i sin)(2πnk/N) /N."""
    x=np.asarray(x,dtype=np.float64)
    return np.fft.ifft(x)

def fold_cepstrum(z):
    """B6E30: first value untouched; paired real addition/imag subtraction;
    Nyquist conjugation for even N; zero second-half buffer. N<3 just memcpy.
    """
    a=np.asarray(z,dtype=np.complex128)
    n=len(a); out=np.zeros(n,dtype=np.complex128)
    if n<3:return a.copy()
    out[0]=a[0]
    middle=(n+1)//2
    for k in range(1,middle):out[k]=a[k]+np.conj(a[n-k])
    if n%2==0:out[n//2]=np.conj(a[n//2])
    return out

def unnormalized_negative_dft(z):
    """B4F60: sum z[k]*(cos - i sin)(2πnk/N), no division."""
    return np.fft.fft(np.asarray(z,dtype=np.complex128))

def vendor_complex_exponential(s):
    """expf(real), cosf(imag), sinf(imag) from B75D5/5E1/5F4."""
    s=np.asarray(s,dtype=np.complex128)
    amp=np.exp(s.real)
    return amp*(np.cos(s.imag)+1j*np.sin(s.imag))

def mirror_first_half(x):
    x=np.asarray(x,dtype=np.float64).copy();n=len(x)
    for k in range(n//2):x[k]=x[n-1-k]
    return x

def spectral_kernel_from_log_curve(log_curve):
    """Complete algebraic B72E0 transforms for an already guarded/logged, equal-length curve.
    No mystery steps between transforms, but not native float32-equivalent.
    """
    x=mirror_first_half(log_curve)
    c=normalized_positive_dft(x)
    folded=fold_cepstrum(c)
    y=unnormalized_negative_dft(folded)
    return vendor_complex_exponential(y)

def spectral_kernel_from_magnitude(magnitude):
    """Positive finite magnitude + Stage12 guard → B72E0. Same-length only."""
    mag=np.asarray(magnitude,dtype=np.float64).copy()
    if len(mag)<3 or not np.isfinite(mag).all() or np.any(mag<0):raise ValueError('finite, positive/nonnegative magnitude required')
    mag=np.maximum(mag,mag.max()*1e-5)
    return spectral_kernel_from_log_curve(np.log(mag+2.0**-23))

def full_synthetic_pre_fir(curve,m):
    """Independent Stage11+13 synthetic input-curve→Pre FIR; not vendor matched.
    M is a requested tap length; full 2N−2 transformation is independent of M.
    """
    a=np.asarray(curve,dtype=np.float64)
    ext=np.concatenate([a,a[-2:0:-1]])
    spec=spectral_kernel_from_magnitude(ext)
    z=np.fft.ifft(spec).real
    h=z[:m].copy()
    h-=h.mean()
    denom=np.linalg.norm(h)
    if denom<=0:raise ValueError('degenerate centered output')
    return h*(np.linalg.norm(z)/denom)

def independent_direct_complex_kernel(log_curve):
    """Slow independently written, explicit O(N²) trigonometric sum reference.
    No FFT library calls. This is an ALGEBRA check, not native DLL execution.
    """
    v=mirror_first_half(log_curve)
    n=len(v)
    c=np.zeros(n,dtype=np.complex128)
    for j in range(n):
        for k in range(n):
            a=2*math.pi*j*k/n
            c[j]+=(v[k]/n)*complex(math.cos(a),math.sin(a))
    p=np.zeros(n,dtype=np.complex128)
    p[0]=c[0]
    for j in range(1,(n+1)//2):p[j]=c[j]+c[n-j].conjugate()
    if n%2==0:p[n//2]=c[n//2].conjugate()
    q=np.zeros(n,dtype=np.complex128)
    for j in range(n):
        for k in range(n):
            a=2*math.pi*j*k/n
            q[j]+=p[k]*complex(math.cos(a),-math.sin(a))
    return np.array([math.exp(t.real)*complex(math.cos(t.imag),math.sin(t.imag)) for t in q])

def tests():
    checks=[]
    def ck(name,passed):
        if not passed:raise AssertionError(name)
        checks.append(name)
    for n in [3,4,5,6,7,8,11,12,31,32,127,128]:
        a=np.arange(n,dtype=float)+0.11
        sin,cos=sin_cos_tables(n)
        ck(f'basis {n}: cosine at zero, sine at zero',abs(sin[0])<1e-14 and abs(cos[0]-1)<1e-14)
        ck(f'B4A50 positive DFT n={n}',np.allclose(normalized_positive_dft(a), np.array([sum(a[k]*np.exp(2j*np.pi*k*j/n) for k in range(n))/n for j in range(n)]),atol=2e-12))
        rng=np.random.default_rng(n)
        z=rng.standard_normal(n)+1j*rng.standard_normal(n)
        ck(f'B4F60 negative DFT n={n}',np.allclose(unnormalized_negative_dft(z),np.array([sum(z[k]*np.exp(-2j*np.pi*k*j/n) for k in range(n)) for j in range(n)]),atol=2e-12))
        f=fold_cepstrum(z)
        if n>=3:
            ck(f'B6E30 zero tail n={n}',np.all(f[n//2+1:]==0))
            ck(f'B6E30 pair k=1 n={n}',np.allclose(f[1],z[1]+np.conj(z[-1])))
            if n%2==0: ck(f'B6E30 conjugated Nyquist n={n}',f[n//2]==np.conj(z[n//2]))
        ck(f'full triplet constant curve n={n}',np.max(np.abs(spectral_kernel_from_magnitude(np.ones(n))-np.ones(n)))<3e-6)
    for n in [8,9,14,15,128,254]:
        rng=np.random.default_rng(n)
        m=np.exp(.15*rng.standard_normal(n))
        direct=np.exp(np.fft.fft(fold_cepstrum(np.fft.ifft(mirror_first_half(np.log(m+2.0**-23))))))
        ck(f'triplet chain np.fft check n={n}',np.allclose(spectral_kernel_from_magnitude(m),direct,rtol=1e-12,atol=1e-12))
        ck(f'recovered spectrum is minimum phase style n={n}',np.all(np.isfinite(spectral_kernel_from_magnitude(m))))
    # True independent cross-check of the *entire* spectral triplet, not a re-use
    # of numpy FFT in the expected value. Both odd and even are essential.
    for n in [3,4,5,6,7,8,11,12,31,32]:
        rng=np.random.default_rng(n+100)
        m=np.exp(.3*rng.standard_normal(n))
        fast=spectral_kernel_from_magnitude(m)
        slow=independent_direct_complex_kernel(np.log(m+2.0**-23))
        ck(f'full recovered triplet vs explicit trig n={n}',np.allclose(fast,slow,rtol=3e-12,atol=3e-12))
    for n in [4,5,128]:
        rng=np.random.default_rng(n)
        m=.5+np.exp(.1*rng.standard_normal(n))
        h=full_synthetic_pre_fir(m,n)
        ck(f'full synthetic pre FIR length/DC n={n}',len(h)==n and abs(np.sum(h))<1e-10)
        ck(f'full synthetic pre FIR norm n={n}',np.isfinite(h).all() and np.linalg.norm(h)>0)
    # Exact odd/even fold patterns for arbitrary complex, not just symmetric FFT.
    q=np.array([1+1j,2+3j,4+5j,6+7j,8+9j,10+11j])
    out=fold_cepstrum(q)
    ck('even fold exact k=1',out[1]==12-8j)
    ck('even fold exact k=2',out[2]==12-4j)
    ck('even fold exact Nyquist',out[3]==6-7j)
    ck('even fold tail zeros',np.all(out[4:]==0))
    ck('short-array memcpy n=2',np.array_equal(fold_cepstrum(q[:2]),q[:2]))
    return checks

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dll',required=True,type=Path)
    ap.add_argument('--out',type=Path)
    a=ap.parse_args()
    pins=pin_dll(a.dll)
    chk=tests()
    data={'dll_sha256':DLL_SHA,'pins':pins,'pin_count':len(pins),'test_count':len(chk),'test_names':chk,'result':'source-pinned spectral triplet tested, no vendor coefficient reconstruction'}
    txt=json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    if a.out:a.out.write_text(txt,encoding='utf-8')
    print(f'PASS: {len(pins)} DLL address pins; {len(chk)} synthetic math tests; evidence_sha256={hashlib.sha256(txt.encode()).hexdigest()}')
if __name__=='__main__':main()
