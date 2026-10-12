"""Stage23T: distinguish filter +0x34 from processor +0x34; trace FIR
spectrum pointer and derive inverse-real-FFT DC gain. Research-only.

Static original PE, address pins, deterministic synthetic counterexample.
This does NOT execute the original Windows DLL, prove real native filter RAM,
or establish whole-stream FIR or NAM/CLO parity.
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

SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
N=4096
PINS={
 0x18000AFB2:'movsxd rbp,edx',
 0x18000B001:'shl eax,cl',
 0x18000B005:'mov dword ptr [rdi+0x4],eax',
 0x18000B010:'divsd xmm0,xmm1',
 0x18000B014:'movsd qword ptr [rdi+0x8],xmm0',
 0x18000BBF1:'movsd xmm0,qword ptr [rbx]',
 0x18000BBFE:'movsd xmm0,qword ptr [rbx+0x8]',
 0x18000BC0B:'movsd xmm0,qword ptr [rbx+0x10]',
 0x18000BC18:'cmp dword ptr [rbx+0x18],esi',
 0x18000BC1D:'movsd xmm0,qword ptr [rbx+0x20]',
 0x18000BCC9:'mov ecx,0x58',
 0x18000BCE8:'mov qword ptr [rax+0x50],rsi',
 0x18000BCF1:'movsd qword ptr [rbx],xmm8',
 0x18000BD03:'movsd qword ptr [rbx+0x20],xmm9',
 0x18000BD12:'call 0x18000b0e0',
 0x18000B95A:'mov rcx,qword ptr [rdi+0x50]',
 0x18000B978:'mov qword ptr [rdi+0x50],rax',
 0x18000B996:'mov byte ptr [rdi+0x34],0x1',
 0x18000B99D:'mov qword ptr [rdi+0x40],rsi',
 0x18000B9A1:'call 0x18000afa0',
 0x18000B9A6:'cmp byte ptr [rdi+0x34],sil',
 0x18000B9C0:'addsd xmm7,qword ptr [rax]',
 0x18000B9D9:'movsd xmm1,qword ptr [rbx+0x8]',
 0x18000B9DE:'mulsd xmm1,qword ptr [rdi+0x20]',
 0x18000B9E3:'divsd xmm1,xmm7',
 0x18000BA31:'mov rcx,qword ptr [rdi+0x50]',
 0x18000BA53:'sub r15d,dword ptr [rdi+0x48]',
 0x18000BA99:'mov rax,qword ptr [rdi+0x50]',
 0x18000BAAC:'mov edx,0x1',
 0x18000BAB5:'mov r8,qword ptr [rdi+0x50]',
 0x18000BAC1:'call 0x1800094f0',
 0x18000BE0A:'mov qword ptr [rcx+0x8],rdx',
 0x18000BE3D:'mov ecx,dword ptr [rax+0x4c]',
 0x18000BE45:'shl eax,cl',
 0x18000BE47:'mov dword ptr [rdi+0x34],eax',
 0x18000C55E:'mov rcx,qword ptr [rsi+0x8]',
 0x18000C56A:'mov rdi,qword ptr [rcx+0x50]',
 0x18000C56E:'cmp byte ptr [rcx+0x34],0x0',
 0x18000C595:'je 0x18000c5df',
 0x18000C5B0:'movsd xmm0,qword ptr [rax]',
 0x18000C5F0:'movsd xmm2,qword ptr [rdi+rax*1-0x8]',
 0x18000C668:'mov edx,0xffffffff',
 0x18000C684:'call 0x1800094f0',
 0x18000974E:'cmp dword ptr [rsp+0xb8],0x0',
 0x18000975B:'jl 0x18000988b',
 0x18000988B:'movsd xmm0,qword ptr [rdi]',
 0x180009892:'subsd xmm1,qword ptr [rdi+0x8]',
 0x180009897:'mulsd xmm1,xmm8',
 0x18000989C:'movsd qword ptr [rdi+0x8],xmm1',
 0x1800098A1:'subsd xmm0,xmm1',
 0x1800098A5:'movsd qword ptr [rdi],xmm0',
 0x1800099A4:'call 0x1800099f0',
 0x1800099B1:'call 0x18000a120',
 0x18000A142:'mov rdx,rsi',
 0x18000A145:'call 0x18000a370',
 0x18000A168:'call 0x18000a850',
}
RANGES=(
 (0x18000AFB0,0x18000B019),(0x18000BBE9,0x18000BC33),
 (0x18000BCC0,0x18000BD1C),(0x18000B950,0x18000BA00),
 (0x18000BA20,0x18000BA66),(0x18000BA95,0x18000BAD0),
 (0x18000BE00,0x18000BE50),(0x18000C550,0x18000C5FC),
 (0x18000C660,0x18000C697),(0x180009740,0x180009762),
 (0x18000988B,0x1800098AF),(0x18000999C,0x1800099B8),
 (0x18000A132,0x18000A17A))

def pe_double(data,addr):
 pe=struct.unpack_from('<I',data,0x3c)[0]
 assert data[:2]==b'MZ' and data[pe:pe+4]==b'PE\0\0'
 opt=pe+24;image=struct.unpack_from('<Q',data,opt+24)[0]
 section=opt+struct.unpack_from('<H',data,pe+20)[0]
 for j in range(struct.unpack_from('<H',data,pe+6)[0]):
  _,v,size,raw=struct.unpack_from('<4I',data,section+40*j+8)
  if v<=addr-image and addr-image+8<=v+size:
   return struct.unpack_from('<d',data,raw+addr-image-v)[0]
 raise ValueError(hex(addr))

def verify(dll:Path):
 data=dll.read_bytes()
 assert hashlib.sha256(data).hexdigest()==SHA,'wrong DLL'
 instructions={}
 for lo,hi in RANGES:
  dump=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
      f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in dump.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if m:instructions[int(m[1],16)]=' '.join(m[2].lower().split())
 for va,insn in PINS.items():
  assert insn in instructions.get(va,''),(hex(va),insn,instructions.get(va))
 # Scan the complete builder rather than just checking selected pins; the
 # constructor's **direct RDI-relative** flag store is uniquely B996.
 dump=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   '--start-address=0x18000b0e0','--stop-address=0x18000bb40',str(dll)],text=True)
 writes=[]
 for line in dump.splitlines():
  m=re.match(r'\s*(180[0-9a-f]+):\s+([^ ]+)\s+(.+)',line)
  if m and re.search(r'\[rdi\+0x34\]',m[3]) and m[2] in ('mov','movsd','movaps') and m[3].split(',')[0].endswith('[rdi+0x34]'):
   writes.append(int(m[1],16))
 assert writes==[0x18000B996],writes
 assert pe_double(data,0x18024ca38)==2.0
 assert pe_double(data,0x18024c880)==0.5
 return len(PINS),writes

def math_checks():
 # The source-derived Stage23H/I normal filter has 1417 taps in a 4096
 # scalar buffer, and gain target 1/1024 BEFORE FFT. This small filter is
 # a synthetic surrogate for the symmetry/branch contradiction, not vendor RAM.
 G=708
 assert 2*G+1==1417
 fft_exponent=(2*G).bit_length()+1
 assert fft_exponent==12 and (1<<fft_exponent)==N
 fft_plan_scale=2/(1<<fft_exponent)
 gain_target=2*fft_plan_scale
 assert gain_target==1/1024
 # Source inverse path (0x988B-98A5) converts packed real DC [S,0]
 # to complex DC [S/2,S/2]; unnormalized 2048-complex inverse then
 # gives S/2 in each interleaved output real slot. A120 has no 1/N divide.
 inverse_dc_factor=0.5
 dc_cascade_gain=N*gain_target*inverse_dc_factor
 assert dc_cascade_gain==2.0
 n=np.arange(N)
 example=np.zeros(N,dtype=np.float64)
 example[0]=gain_target/2
 example[1]=gain_target/4
 example[-1]=gain_target/4
 real_fft=np.conj(np.fft.rfft(example))
 assert abs(real_fft[0].real-gain_target)<1e-17
 assert np.max(np.abs(real_fft.imag))<1e-17
 tone=np.sin(2*math.pi*33*n/N)
 t=np.conj(np.fft.rfft(tone))
 packed_t=np.empty(N);packed_h=np.empty(N)
 packed_t[:2]=[t[0].real,t[-1].real]
 packed_h[:2]=[real_fft[0].real,real_fft[-1].real]
 packed_t[2::2]=t[1:-1].real;packed_t[3::2]=t[1:-1].imag
 packed_h[2::2]=real_fft[1:-1].real;packed_h[3::2]=real_fft[1:-1].imag
 scalar=packed_t*packed_h
 conventional=t*real_fft
 rms=lambda v:float(np.sqrt(np.mean(np.square(v))))
 # The *native inverse* has gain N/2 relative to np.irfft. The same
 # multiplier applies to both paths, thus it cannot repair the ratio.
 def inverse_packed(p):
  z=np.empty(N//2+1,dtype=complex)
  z[0]=p[0];z[-1]=p[1]
  z[1:-1]=p[2::2]+1j*p[3::2]
  return np.fft.irfft(np.conj(z),n=N)*(N//2)
 lane_rms=rms(inverse_packed(scalar))
 complex_rms=rms(np.fft.irfft(np.conj(conventional),n=N)*(N//2))
 assert complex_rms>.1 and lane_rms<complex_rms*1e-10,(lane_rms,complex_rms)
 const_input=np.ones(N)
 h_dc=real_fft[0].real
 dc_spectrum=(N*h_dc)
 assert abs(dc_spectrum*inverse_dc_factor-2.)<1e-12
 return {'filter_source_flag_on_fresh_build':1,
   'processor_object_field_0x34':N,
   'filter_object_flag_field_0x34':1,
   'filter_spectrum_pointer_field_0x50':'same filter coefficient ring before/after forward FFT',
   'fft_plan_size_doubles':N,
   'fft_plan_preinverse_coefficient_scale':fft_plan_scale,
   'source_derived_filter_DC_sum_target':gain_target,
   'inverse_DC_only_output_per_unit_packed_DC':inverse_dc_factor,
   'predicted_DC_gain_for_2x_FIR':dc_cascade_gain,
   'three_tap_synthetic_sine33_conventional_rms_with_inverse_gain':complex_rms,
   'three_tap_synthetic_sine33_flag1_lane_rms_with_inverse_gain':lane_rms,
   'outstanding_conflict':'flag 1 lane multiplication suppresses quadrature despite 2x DC gain; no native filter RAM or exact runtime provenance'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True)
 pins,writes=verify(p.parse_args().dll)
 print(json.dumps({'dll_sha256':SHA,'instruction_pins':pins,
  'filter_constructor_direct_rdi_flag_writes':[hex(x) for x in writes],
  **math_checks(),'scope':'static source pins + synthetic math; no Windows native execution or real FIR output parity'},indent=2))
