"""Stage23Q: integrated synthetic 2048-complex FFT from 4096 double slots.

Original 5868USB.dll PE SHA and 21 machine-code pins checked. The matrix
butterflies are algebraic reconstructions of source-interpreted Stage23M–P.
This tests *full mathematical integration*, NOT f64 SSE ordering, native
Windows CRT twiddles, real-spectrum packing, vendor RAM or NAM/CLO parity.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, subprocess
from pathlib import Path
import numpy as np
DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
N=2048
PINS={
0x180009773:'call 0x1800099f0',
0x180009780:'call 0x180009ef0',
0x180009A00:'mov dword ptr [rdx],0x0',
0x180009A22:'sar r9d,1',
0x180009A40:'mov ecx,dword ptr [rdx]',
0x180009A46:'add ecx,r9d',
0x180009A49:'mov dword ptr [rbx+rdx*1-0x4],ecx',
0x180009F15:'call 0x18000a370',
0x180009F1A:'mov edx,0x8',
0x180009F38:'call 0x18000a850',
0x180009F3F:'lea edi,[rdi*4+0x0]',
0x180009F68:'jne 0x18000a0a0',
0x18000A0E3:'addsd xmm0,xmm3',
0x18000A0EA:'subsd xmm4,xmm3',
0x18000A892:'lea r12d,[r11*4+0x0]',
0x18000A8E0:'movsd xmm9,qword ptr [r9+rdx*8]',
0x18000AA10:'movsd xmm7,qword ptr [rdx]',
0x18000AB76:'addsd xmm10,xmm12',
0x18000AD52:'addsd xmm10,xmm11',
0x18000AE6B:'xorps xmm1,xmmword ptr [rip+0x24277e]',
0x18000AF1F:'lea edx,[rdx+r12*2]',
}
RANGES=((0x180009760,0x180009786),(0x1800099F0,0x180009A60),
 (0x180009F08,0x180009F70),(0x18000A0D0,0x18000A0F5),
 (0x18000A880,0x18000A900),(0x18000AA08,0x18000AA30),
 (0x18000AB70,0x18000AB86),(0x18000AD48,0x18000AD65),
 (0x18000AE60,0x18000AE80),(0x18000AF17,0x18000AF35))

def source_pins(dll:Path):
 assert hashlib.sha256(dll.read_bytes()).hexdigest()==DLL_SHA,'wrong DLL'
 asm={}
 for lo,hi in RANGES:
  raw=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in raw.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if m:asm[int(m[1],16)]=' '.join(m[2].lower().split())
 for va,needle in PINS.items():
  assert needle in asm.get(va,''),(hex(va),needle,asm.get(va))
 return len(PINS)

def bit_reverse_indices(bits):
 size=1<<bits
 # Algebraic completion of 0x99F0 startup recurrence: p[0]=0,
 # p[1]=size, p[2]=size/2, p[3]=3*size/2 in DOUBLE offsets.
 value=np.arange(size,dtype=np.int64)
 flipped=np.zeros(size,dtype=np.int64)
 for i in range(bits):
  flipped=(flipped<<1)|(value&1)
  value>>=1
 if bits==11:
  assert (2*flipped[:4]).tolist()==[0,2048,1024,3072]
 return flipped

def radix4_actual_memory_order(groups):
 """StageK positive DFT4 with physical [z0,z2,z1,z3], no twiddles."""
 a,b,c,d=groups[...,0],groups[...,1],groups[...,2],groups[...,3]
 return np.stack([a+b+c+d,(a-b)+1j*(c-d),a+b-c-d,
                  (a-b)-1j*(c-d)],axis=-1)

def integrated_fft(arr):
 assert arr.shape==(N,) and np.iscomplexobj(arr)
 x=arr[bit_reverse_indices(11)].copy()
 angle=math.atan(1.0)/512.0
 reversed10=bit_reverse_indices(10)
 w=np.exp(1j*angle*reversed10)
 # 0xA370: 256 base blocks, each two source-derived 4-point butterflies.
 for b in range(N//8):
  k=np.arange(4)
  left=radix4_actual_memory_order(x[8*b:8*b+4])
  right=radix4_actual_memory_order(x[8*b+4:8*b+8])
  x[8*b:8*b+4]=left*(w[2*b]**k)
  x[8*b+4:8*b+8]=right*(w[2*b+1]**k)
 # 0xA850: scalar EDX=8,32,128,512; convert to complex stride.
 for scalar_stride in (8,32,128,512):
  stride=scalar_stride//2
  for block in range(N//(4*stride)):
   positions=4*stride*block+np.arange(stride)
   indices=positions[:,None]+stride*np.arange(4)
   values=x[indices]
   y=radix4_actual_memory_order(values)
   x[indices]=y*(w[block]**np.arange(4))
 # 0xA0A0: final scalar-stride 2048 doubles = 1024 complex.
 half=N//2
 top=x[:half].copy();bottom=x[half:].copy()
 x[:half]=top+bottom
 x[half:]=top-bottom
 return x

def run(dll):
 pins=source_pins(dll)
 rng=np.random.default_rng(0x23A370)
 impulse_positions=(0,1,2,3,4,8,16,63,64,255,256,511,512,1023,1024,1025,2047)
 cases=[]
 for i in impulse_positions:
  v=np.zeros(N,dtype=np.complex128);v[i]=1.;cases.append((f'impulse_{i}',v))
 for i in range(8):
  z=rng.standard_normal(N)+1j*rng.standard_normal(N)
  cases.append((f'complex_{i}',z))
 for i in range(4):cases.append((f'real_{i}',rng.standard_normal(N).astype(complex)))
 maximum=0.;worst_case=None;first_fail=None
 for name,data in cases:
  got=integrated_fft(data)
  oracle=np.fft.ifft(data)*N # positive exponent, unnormalized
  differences=np.abs(got-oracle)
  idx=int(np.argmax(differences));gap=float(differences[idx])
  if gap>maximum:maximum=gap;worst_case=(name,idx)
  if gap>2e-11 and first_fail is None:first_fail=(name,idx,gap)
 assert first_fail is None,first_fail
 # A deliberately unpermuted input must fail for impulse at original sample 1.
 signal=np.zeros(N,dtype=np.complex128);signal[1]=1.
 perm=bit_reverse_indices(11)
 assert np.max(np.abs(integrated_fft(signal[perm])-np.fft.ifft(signal)*N))>1
 return dict(original_dll_sha256=DLL_SHA,instruction_pins=pins,
  scalar_double_buffer=4096,complex_points=N,
  complex_input_permutation='11-bit reversal',
  complex_internal_sign='positive; numpy ifft * 2048',
  radix4_scalar_strides=[8,32,128,512],
  synthetic_cases=len(cases),max_abs_error=maximum,worst_case=worst_case,
  first_error_above_2e_minus_11=first_fail,
  strict_scope='complete algebraic complex FFT only: NOT vendor f64/CRT RAM parity or real FFT packing')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True)
 print(json.dumps(run(p.parse_args().dll),indent=2))
