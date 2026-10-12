"""Stage23S: source-constrained HTKPA FIR FFT multiply + streaming gate.

Targets exact SHA-pinned original PE; no Windows DLL execution.
Two branch-specific packed multiplication kernels are compared to independent
synthetic frequency-domain oracles. A symmetric FIR counterexample intentionally
DISPROVES assuming the nonzero-flag branch is conventional complex convolution.
It does NOT determine which native runtime representation actually reaches
this branch, complete inverse FFT scale, overlap or real audio parity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path
import numpy as np

DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
N=4096
PINS={
 0x18000B996:'mov byte ptr [rdi+0x34],0x1',
 0x18000B9A1:'call 0x18000afa0',
 0x18000BAAC:'mov edx,0x1',
 0x18000BAC1:'call 0x1800094f0',
 0x18000BE0A:'mov qword ptr [rcx+0x8],rdx',
 0x18000BE2A:'mov dword ptr [rcx+0x28],r8d',
 0x18000BE35:'mov dword ptr [rcx+0x2c],r9d',
 0x18000BE45:'shl eax,cl',
 0x18000BE47:'mov dword ptr [rdi+0x34],eax',
 0x18000BEB7:'mov eax,dword ptr [rdx+0x48]',
 0x18000BEC0:'mov edx,dword ptr [r10+0x4c]',
 0x18000BECE:'jmp 0x18000bee1',
 0x18000BEE1:'mov dword ptr [rdi+0x3c],eax',
 0x18000BEE7:'mov dword ptr [rdi+0x40],ecx',
 0x18000BEED:'mov edx,dword ptr [r10+0x38]',
 0x18000BF3D:'mov dword ptr [rdi+0x44],r10d',
 0x18000C0BA:'movsxd r8,dword ptr [rdi+0x34]',
 0x18000C0BE:'mov qword ptr [rdi+0x70],rax',
 0x18000C0CA:'mov qword ptr [rdi+0x78],rdx',
 0x18000C0DC:'call 0x18000c160',
 0x18000C166:'movsxd r8,dword ptr [rcx+0x3c]',
 0x18000C17C:'cmp byte ptr [rbx+0x30],0x0',
 0x18000C1F5:'mov eax,dword ptr [rbx+0x40]',
 0x18000C1FB:'mov dword ptr [rbx+0x80],eax',
 0x18000C220:'mov rax,rsp',
 0x18000C422:'mov eax,dword ptr [rsi+0x3c]',
 0x18000C445:'call 0x1800a505a',
 0x18000C45F:'call 0x1800a505a',
 0x18000C468:'mov edx,0x1',
 0x18000C484:'call 0x1800094f0',
 0x18000C55E:'mov rcx,qword ptr [rsi+0x8]',
 0x18000C56A:'mov rdi,qword ptr [rcx+0x50]',
 0x18000C56E:'cmp byte ptr [rcx+0x34],0x0',
 0x18000C572:'mov ecx,0x2',
 0x18000C577:'movsd xmm0,qword ptr [rdx]',
 0x18000C57E:'mulsd xmm0,qword ptr [rdi]',
 0x18000C58B:'mulsd xmm1,qword ptr [rdx+0x8]',
 0x18000C595:'je 0x18000c5df',
 0x18000C5B0:'movsd xmm0,qword ptr [rax]',
 0x18000C5B7:'mulsd xmm0,qword ptr [rdx+rax*1]',
 0x18000C5CB:'mulsd xmm1,qword ptr [rdx+rax*1-0x8]',
 0x18000C5DF:'cmp dword ptr [r8+0x4],ecx',
 0x18000C5F0:'movsd xmm2,qword ptr [rdi+rax*1-0x8]',
 0x18000C5F9:'movsd xmm4,qword ptr [rdi+rax*1]',
 0x18000C60D:'mulsd xmm1,xmm4',
 0x18000C611:'mulsd xmm4,xmm3',
 0x18000C615:'mulsd xmm0,xmm3',
 0x18000C619:'mulsd xmm5,xmm2',
 0x18000C61D:'addsd xmm1,xmm0',
 0x18000C621:'subsd xmm5,xmm4',
 0x18000C625:'movsd qword ptr [rax],xmm1',
 0x18000C629:'movsd qword ptr [rax-0x8],xmm5',
 0x18000C664:'mov rax,qword ptr [rsi+0x20]',
 0x18000C668:'mov edx,0xffffffff',
 0x18000C684:'call 0x1800094f0',
 0x18000C689:'sub r12d,dword ptr [rsi+0x38]',
 0x18000C6D2:'mov eax,dword ptr [rsi+0x84]',
 0x18000C6E2:'mov dword ptr [rsi+0x84],eax',
 0x18000C6F0:'mov dword ptr [rsi+0x84],0x0',
 0x18000C84F:'mov rax,qword ptr [rsi+0x70]',
 0x18000C85D:'mov qword ptr [rsi+0x70],r9',
 0x18000C861:'mov qword ptr [rsi+0x78],rax',
}
RANGES=((0x18000B98C,0x18000B9A9),(0x18000BAA3,0x18000BACE),
 (0x18000BE04,0x18000BE52),(0x18000BEA9,0x18000BF4F),
 (0x18000C0B0,0x18000C0E5),(0x18000C160,0x18000C21F),
 (0x18000C220,0x18000C255),(0x18000C41F,0x18000C490),
 (0x18000C550,0x18000C69A),(0x18000C6D0,0x18000C704),
 (0x18000C847,0x18000C86B))

def pin_source(dll:Path):
 assert hashlib.sha256(dll.read_bytes()).hexdigest()==DLL_SHA,'original DLL SHA mismatch'
 asm={}
 for lo,hi in RANGES:
  out=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in out.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if m:asm[int(m.group(1),16)]=' '.join(m.group(2).lower().split())
 for a,needle in PINS.items():
  assert needle in asm.get(a,''),(hex(a),needle,asm.get(a))
 return len(PINS)

def pack_positive_fft(real):
 """[DC, Nyquist, Re1, Im1,...]; independent of vendor FFT code."""
 z=np.conj(np.fft.rfft(real));p=np.empty(N,dtype=np.float64)
 p[0]=z[0].real;p[1]=z[-1].real
 p[2::2]=z[1:-1].real;p[3::2]=z[1:-1].imag
 return p

def unpack_positive_fft(p):
 assert p.shape==(N,)
 out=np.empty(N//2+1,dtype=np.complex128)
 out[0]=p[0];out[-1]=p[1];out[1:-1]=p[2::2]+1j*p[3::2]
 return out

def multiply_source(x,h,flag):
 """Ordered SSE arithmetic of C577-C636 for packed 4096-double arrays."""
 assert flag in (0,1) and x.shape==h.shape==(N,)
 y=np.empty_like(x)
 # C577-C590 are outside the flag-specific loops.
 y[0]=float(x[0])*float(h[0]);y[1]=float(x[1])*float(h[1])
 for i in range(2,N,2):
  if flag:
   # C5B0–C5D1: *independent* scalar products.
   y[i]=float(x[i])*float(h[i])
   y[i+1]=float(x[i+1])*float(h[i+1])
  else:
   # C5F0–C629: preserve SSE low-scalar op order, without FMA.
   f_re=float(h[i]);f_im=float(h[i+1]);s_re=float(x[i]);s_im=float(x[i+1])
   tmp_im=s_re
   tmp_im=tmp_im*f_im
   f_im=f_im*s_im
   tmp_re=f_re*s_im
   s_re=s_re*f_re
   tmp_im=tmp_im+tmp_re
   s_re=s_re-f_im
   y[i]=s_re;y[i+1]=tmp_im
 return y

def check(dll):
 pins=pin_source(dll)
 # First FIR work-counts from Stage23G/H and original BDF0/C160 pins.
 G=708;length=2*G+1;buffer=N
 initialized={'fir_half_length':G,'fir_length':length,'fft_scalar_doubles':N,
  'initial_fill':buffer-(length-1),'initial_skip':buffer-(length-1)+G}
 assert initialized['initial_fill']==2680 and initialized['initial_skip']==3388
 rng=np.random.default_rng(0x23C5F0)
 worst_real=0.;worst_lane=0.
 for i in range(30):
  x=rng.uniform(-2,2,N);h=rng.uniform(-2,2,N)
  source_complex=multiply_source(x,h,0)
  ref_complex=np.empty(N,dtype=np.float64)
  ref_complex[:2]=x[:2]*h[:2]
  a=x[2::2]+1j*x[3::2];b=h[2::2]+1j*h[3::2]
  z=a*b
  ref_complex[2::2]=z.real;ref_complex[3::2]=z.imag
  worst_real=max(worst_real,float(np.max(np.abs(ref_complex-source_complex))))
  source_lane=multiply_source(x,h,1)
  worst_lane=max(worst_lane,float(np.max(np.abs(source_lane-x*h))))
 assert worst_real<4e-15 and worst_lane==0.,(worst_real,worst_lane)
 # A symmetric first FIR has an almost purely real conventional spectrum.
 # If the nonzero-flag lane-wise multiply receives that representation,
 # its output is NOT the conventional convolution spectrum.
 symmetric=np.zeros(N);symmetric[0]=.5;symmetric[1]=.25;symmetric[-1]=.25
 samples=np.arange(N);sine=np.sin(2*math.pi*33*samples/N)
 x=pack_positive_fft(sine);h=pack_positive_fft(symmetric)
 mask=multiply_source(x,h,1);normal=multiply_source(x,h,0)
 source_t=np.fft.irfft(np.conj(unpack_positive_fft(mask)),n=N)
 conventional_t=np.fft.irfft(np.conj(unpack_positive_fft(normal)),n=N)
 rms=lambda a:float(np.sqrt(np.mean(a*a)))
 scalar_rms=rms(source_t);normal_rms=rms(conventional_t)
 assert normal_rms>.1 and scalar_rms<1e-11*normal_rms,(scalar_rms,normal_rms)
 return {'dll_sha256':DLL_SHA,'machine_instruction_pins':pins,
  'filter_source_initial_flag_at_B996':1,
  'flag_0':'complex multiply each packed spectrum pair after DC/Nyquist',
  'flag_nonzero':'independent real/imag double multiplication after DC/Nyquist',
  'forward_mode':1,'inverse_mode':-1,
  'fft_blocks_in_fir_stage':initialized,
  'synthetic_4096_double_random_tests':30,
  'max_complex_vs_independent_error':worst_real,
  'max_lane_vs_independent_error':worst_lane,
  'symmetric_three_tap_sine33_conventional_rms':normal_rms,
  'symmetric_three_tap_sine33_flag1_rms':scalar_rms,
  'critical_open_conflict':'flag1 scalar multiply with ordinary symmetric packed FFT suppresses sine; verify actual native filter coefficient representation / flag and inverse normalization before asserting convolution',
  'not_proven':'normal runtime branch activation, native RAM/CRT, full convolution, overlap streaming, sample alignment, gains or CLO'}

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--dll',required=True,type=Path)
 print(json.dumps(check(ap.parse_args().dll),indent=2))
