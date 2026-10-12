#!/usr/bin/env python3
"""Stage 12: DLL-pinned source-first audit of the Pre-FIR spectral kernel.
Reads DLL statically with objdump; DOES NOT execute DLL or emit CLO.
Array functions model only individually proven equations; not the full proprietary converter.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct, subprocess, re
from pathlib import Path
import numpy as np

EXPECTED_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PIN = {
  0x1800b733b:('log_scale_guard_call','call   0x1800b7150'),
  0x1800b7256:('guard_exponent_times_point05','0x18024c520'),
  0x1800b726f:('guard_pow10','call   0x18017e152'),
  0x1800b727a:('guard_relative_to_peak','mulsd  xmm0,xmm1'),
  0x1800b729f:('guard_compare_floor','comiss xmm2,xmm0'),
  0x1800b72a4:('guard_replace_tiny_value','movaps xmm1,xmm2'),
  0x1800b73bb:('logf_scalar','call   0x18017e14c'),
  0x1800b7450:('linear_regrid','call   0x1800b5d00'),
  0x1800b748f:('reverse_partner_load','[r14+rax*4]'),
  0x1800b7493:('reverse_partner_store','[r8-0x18]'),
  0x1800b7534:('trigonometric_basis','call   0x1800b52e0'),
  0x1800b754a:('transform_log_curve','call   0x1800b4a50'),
  0x1800b7569:('conjugate_folding','call   0x1800b6e30'),
  0x1800b7590:('transform_back','call   0x1800b4f60'),
  0x1800b75d5:('expf_magnitude','call   0x18017e12e'),
  0x1800b75e1:('cosf_phase','call   0x18017e11c'),
  0x1800b75f4:('sinf_phase','call   0x18017e164'),
  0x1800b75ea:('complex_real_write','movss'),
  0x1800b7601:('complex_imag_write','movss'),
  0x1800b6edb:('fold_real_add','addss'),
  0x1800b6eeb:('fold_imag_sub','subss'),
  0x1800b710c:('fold_nyquist_imag_sign','xorps'),
  0x1800b4c62:('transform_one_over_n_real','mulss'),
  0x1800b4c6d:('transform_one_over_n_imag','mulss'),
  0x1800b48f9:('inverse_real_difference','subss'),
  0x1800b530a:('trig_2pi_constant','0x18024ccf0'),
  0x1800b5322:('trig_2pi_over_n','divss  xmm7,xmm0'),
  0x1800b5421:('trig_sin_call','call   0x18017e15e'),
  0x1800b5436:('trig_cos_call','call   0x18017e116'),
  0x1800b49e7:('inverse_one_over_n','mulss'),
  0x1800b6a16:('parent_complex_synthesis','call   0x1800b72e0'),
  0x1800b6a50:('parent_basis','call   0x1800b52e0'),
  0x1800b6a66:('parent_inverse','call   0x1800b47f0'),
  0x1800b6b9d:('parent_dc_subtract_setup','divss'),
  0x1800b6d0e:('parent_energy_restore','divss'),
}

# PE RVA + section file raw pointer, using the standard PE section table.
def read_constants(dll: Path):
    b=dll.read_bytes()
    pe=struct.unpack_from('<I',b,0x3c)[0]
    nsects=struct.unpack_from('<H',b,pe+6)[0]
    osize=struct.unpack_from('<H',b,pe+20)[0]
    sections=[]
    for i in range(nsects):
        off=pe+24+osize+i*40
        size,va,rawsz,raw=struct.unpack_from('<IIII',b,off+8)
        sections.append((va,max(size,rawsz),raw))
    def fl(addr,format='<f'):
        rva=addr-0x180000000
        for va,size,raw in sections:
            if va<=rva<va+size: return struct.unpack_from(format,b,raw+rva-va)[0]
        raise ValueError(hex(addr))
    found={
        'scale_control':fl(0x18024cf38),
        'scale_to_power':fl(0x18024c520),
        'power_base':fl(0x18024cb30,'<d'),
        'epsilon':fl(0x18024c4d4),
        'inverse_transform_unity':fl(0x18024c6a0),
        'pi2':fl(0x18024ccf0),
    }
    assert found['scale_control']==-100.0
    assert abs(found['scale_to_power']-0.05)<1e-8
    assert found['power_base']==10.0
    assert found['epsilon']==2.0**-23
    assert found['inverse_transform_unity']==1.0
    assert abs(found['pi2']-2*math.pi)<3e-7
    return found

def read_disasm(dll:Path):
    ranges=[(0x1800b47f0,0x1800b4a40),(0x1800b4a50,0x1800b4ce0),
       (0x1800b52e0,0x1800b545b),
       (0x1800b68f0,0x1800b6e30),(0x1800b6e30,0x1800b7150),
       (0x1800b7150,0x1800b7660)]
    out={}
    for lo,hi in ranges:
        p=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',
            f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],
            check=True,text=True,capture_output=True)
        for line in p.stdout.splitlines():
            m=re.match(r'^\s*([0-9a-fA-F]+):\s+(.*)$',line)
            if m: out[int(m[1],16)]=m[2].strip()
    failed={hex(k):{'need':part,'actual':out.get(k,'<missing>')} for k,(_,part) in PIN.items() if part not in out.get(k,'')}
    if failed:raise AssertionError('DLL pin failure:\n'+json.dumps(failed,indent=2))
    return {hex(a):{'id':name,'assembly':out[a]} for a,(name,_) in PIN.items()}

def safe_log_vector(x, relative_floor=1e-5):
    """Model proven guard + log stage for positive magnitude inputs only.
    The DLL's path for negative values/NaN remains uncharacterized.
    """
    x=np.asarray(x,dtype=np.float32).copy()
    assert x.ndim==1 and len(x)>0 and np.isfinite(x).all() and np.all(x>=0)
    maximum=float(np.max(np.abs(x)))
    if maximum>0: x[x<maximum*relative_floor]=np.float32(maximum*relative_floor)
    return np.log(x+np.float32(2.0**-23))

def reflect_first_half_from_last(x):
    """Native 0x1800B7480... rewrite: first floor(N/2) bins from x[N-1-i]."""
    out=np.asarray(x,dtype=np.float32).copy()
    n=len(out)
    for i in range(n//2):out[i]=out[n-1-i]
    return out

def conjugate_fold(z):
    """Algebra pinned in 0x1800B6E30. Unknown small-N special cases excluded."""
    z=np.asarray(z,dtype=np.complex64)
    n=len(z)
    assert n>=5
    out=np.zeros(n,dtype=np.complex64)
    out[0]=z[0]
    for k in range(1,(n+1)//2):out[k]=z[k]+np.conj(z[n-k])
    if n%2==0:out[n//2]=np.conj(z[n//2])
    return out

def exp_complex(re,im):
    """The exact scalar operation at 0x1800B75D0...B7601."""
    re=np.asarray(re,dtype=np.float32)
    im=np.asarray(im,dtype=np.float32)
    return (np.exp(re)*np.cos(im)+1j*np.exp(re)*np.sin(im)).astype(np.complex64)

def inverse_complex_real(spec):
    """Algebraic reference for 0x1800B47F0, not bit-identical summation order."""
    z=np.asarray(spec,dtype=np.complex128)
    n=len(z)
    j=np.arange(n)[:,None]
    k=np.arange(n)[None,:]
    theta=2*math.pi*j*k/n
    return np.sum(z.real[None,:]*np.cos(theta)-z.imag[None,:]*np.sin(theta),axis=1)/n

def test_math():
    results=[]
    def chk(name,test):
        assert bool(test),name
        results.append(name)
    lo=safe_log_vector([1., 1e-9,0.])
    chk('guard threshold is max-100dB = 1e-5',np.allclose(lo[1:],np.log(1e-5+2**-23),rtol=1e-6))
    chk('guard keeps large amplitudes',abs(float(lo[0]))<5e-7)
    chk('log handles all-zero vector with epsilon',np.isfinite(safe_log_vector([0,0,0])).all())
    chk('first-half mirror has exact N-i-1 indexing',np.array_equal(reflect_first_half_from_last([1,2,3,4,5,6]),[6,5,4,4,5,6]))
    chk('first-half mirror odd-length',np.array_equal(reflect_first_half_from_last([1,2,3,4,5]),[5,4,3,4,5]))
    z=np.array([1+1j,2+3j,4+5j,6+7j,8+9j,10+11j],dtype=np.complex64)
    u=conjugate_fold(z)
    chk('fold = complex real sum, imaginary difference',np.allclose(u[1],(2+3j)+(10-11j)))
    chk('fold zeroes unselected tail',np.all(u[4:]==0))
    chk('fold handles odd length without Nyquist',np.isfinite(conjugate_fold(z[:-1])).all())
    chk('complex exponential is unit at zero',np.allclose(exp_complex([0],[0]),[1+0j]))
    chk('complex exponential represents exp(a+i*b)',np.allclose(exp_complex([1,0],[0,math.pi/2]),[math.e,1j],atol=2e-7))
    impulse=np.array([1,0,0,0,0,0,0,0],dtype=np.complex64)
    chk('trig basis uses period N',np.allclose(np.cos(2*np.pi*np.arange(8)/8),[1,2**-0.5,0,-2**-0.5,-1,-2**-0.5,0,2**-0.5],atol=1e-14))
    chk('inverse transform constant spectrum gives impulse',np.allclose(inverse_complex_real(np.ones(8,dtype=complex)),impulse.real,atol=1e-13))
    complex_spec=np.array([1+0j,2-0.25j,3+1j,-1+0.5j,4+0j,1-2j],dtype=complex)
    chk('inverse direct O(N²) agrees with numpy ifft real',np.allclose(inverse_complex_real(complex_spec),np.fft.ifft(complex_spec).real,atol=1e-13))
    return results

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dll',required=True,type=Path)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    actual=hashlib.sha256(args.dll.read_bytes()).hexdigest()
    if actual!=EXPECTED_SHA:raise SystemExit(f'DLL sha mismatch: {actual}')
    const=read_constants(args.dll)
    pins=read_disasm(args.dll)
    tests=test_math()
    evidence={'stage':'12','dll_sha256':actual,'address_checks':len(pins),
              'constants':const,'pins':pins,'math_tests':tests,
              'limitations':['No DLL execution','No exact full native FFT byte parity',
                             'No recovered official FIR from WAV','No produced CLO']}
    data=json.dumps(evidence,ensure_ascii=False,sort_keys=True,indent=2)+'\n'
    if args.output:args.output.write_text(data)
    print('PASS',len(pins),'address predicates;',len(const),'constants;',len(tests),'mathematical tests')
    print('evidence SHA256',hashlib.sha256(data.encode()).hexdigest())
if __name__=='__main__':main()
