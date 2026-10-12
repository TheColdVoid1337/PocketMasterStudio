"""Stage23V: source-pin FIR double buffer handoff and 2-block streaming counts.

Static original PE only. The passthrough arrays stand in for the result
of FFT multiply/inverse: their values are deliberately NOT native FIR output.
Proves pointer movements, 708-double scratch tail, skip/accounting and
chunking invariance for 44.1k -> 48k FIR up2, N=4096, G=708.
No vendor DLL execution, coefficient/runtime branch parity or CLO output.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
import numpy as np

DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
N=4096;G=708;H=N-2*G;O=G;TAIL_START=H-G
PINS={
  0x18000be0a:'mov qword ptr [rcx+0x8],rdx',
  0x18000be2a:'mov dword ptr [rcx+0x28],r8d',
  0x18000be35:'mov dword ptr [rcx+0x2c],r9d',
  0x18000be47:'mov dword ptr [rdi+0x34],eax',
  0x18000bee1:'mov dword ptr [rdi+0x3c],eax',
  0x18000bee7:'mov dword ptr [rdi+0x40],ecx',
  0x18000befc:'mov dword ptr [rdi+0x38],edx',
  0x18000bf3d:'mov dword ptr [rdi+0x44],r10d',
  0x18000bfa1:'mov esi,dword ptr [rsi+0x4c]',
  0x18000bffb:'mov dword ptr [rdi+0x54],0xffffffff',
  0x18000c0ba:'movsxd r8,dword ptr [rdi+0x34]',
  0x18000c0be:'mov qword ptr [rdi+0x70],rax',
  0x18000c0ca:'mov qword ptr [rdi+0x78],rdx',
  0x18000c0d8:'mov qword ptr [rdi+0x68],rax',
  0x18000c17c:'cmp byte ptr [rbx+0x30],0x0',
  0x18000c185:'mov dword ptr [rbx+0x84],eax',
  0x18000c1fb:'mov dword ptr [rbx+0x80],eax',
  0x18000c207:'mov dword ptr [rbx+0x88],eax',
  0x18000c213:'mov dword ptr [rbx+0x90],eax',
  0x18000c23f:'imul r15d,r8d',
  0x18000c280:'mov ebp,dword ptr [rsi+0x80]',
  0x18000c2a2:'mov dword ptr [rsi+0x80],eax',
  0x18000c2e8:'mov ecx,dword ptr [rsi+0x88]',
  0x18000c32f:'idiv ecx',
  0x18000c3b0:'mov rax,qword ptr [r14]',
  0x18000c3b8:'mov qword ptr [r8],rax',
  0x18000c3d0:'mov qword ptr [rax],r11',
  0x18000c422:'mov eax,dword ptr [rsi+0x3c]',
  0x18000c425:'mov rdx,qword ptr [rsi+0x68]',
  0x18000c439:'mov qword ptr [rsp+0x98],r14',
  0x18000c441:'lea rcx,[rax+rcx*8]',
  0x18000c445:'call 0x1800a505a',
  0x18000c44a:'sub ebx,dword ptr [rsi+0x3c]',
  0x18000c45b:'mov rcx,qword ptr [rsi+0x68]',
  0x18000c45f:'call 0x1800a505a',
  0x18000c468:'mov edx,0x1',
  0x18000c484:'call 0x1800094f0',
  0x18000c56a:'mov rdi,qword ptr [rcx+0x50]',
  0x18000c56e:'cmp byte ptr [rcx+0x34],0x0',
  0x18000c668:'mov edx,0xffffffff',
  0x18000c684:'call 0x1800094f0',
  0x18000c689:'sub r12d,dword ptr [rsi+0x38]',
  0x18000c6a2:'lea rax,[rsp+0xa0]',
  0x18000c6ad:'mov r9d,r12d',
  0x18000c6c0:'call 0x18000ca90',
  0x18000c6d2:'mov eax,dword ptr [rsi+0x84]',
  0x18000c6e2:'mov dword ptr [rsi+0x84],eax',
  0x18000c6f0:'mov dword ptr [rsi+0x84],0x0',
  0x18000c759:'mov rdx,qword ptr [rsi+0x78]',
  0x18000c824:'movsxd rax,r12d',
  0x18000c838:'call 0x1800a505a',
  0x18000c84f:'mov rax,qword ptr [rsi+0x70]',
  0x18000c859:'mov r9,qword ptr [rsi+0x78]',
  0x18000c85d:'mov qword ptr [rsi+0x70],r9',
  0x18000c861:'mov qword ptr [rsi+0x78],rax',
  0x18000c920:'mov qword ptr [rsp+0x8],rbx',
  0x18000c957:'mov dword ptr [r10+0x88],ecx',
  0x18000ca58:'mov dword ptr [r10+0x88],eax',
  0x18000ca90:'mov qword ptr [rsp+0x10],rbx',
  0x18000cade:'mov eax,dword ptr [rbp+0x84]',
  0x18000caee:'mov dword ptr [rbp+0x84],eax',
  0x18000cafb:'mov dword ptr [rbp+0x84],0x0',
}
RANGES=((0x18000BE00,0x18000BE54),(0x18000BED0,0x18000BF45),
 (0x18000BF95,0x18000C0E8),(0x18000C170,0x18000C220),
 (0x18000C230,0x18000C421),(0x18000C41F,0x18000C48a),
 (0x18000C550,0x18000C575),(0x18000C660,0x18000C720),
 (0x18000C750,0x18000C880),(0x18000C920,0x18000CB20))

def inspect(dll):
 data=dll.read_bytes()
 assert hashlib.sha256(data).hexdigest()==DLL_SHA,'wrong 5868USB.dll'
 asm={}
 for lo,hi in RANGES:
  out=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for row in out.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',row)
   if m:asm[int(m[1],16)]=' '.join(m[2].lower().split())
 for a,frag in PINS.items():
  assert frag in asm.get(a,''),(hex(a),frag,asm.get(a))
 # Win64 memcpy(dst=RCX,src=RDX,size=R8); two copies reverse pointers.
 return len(PINS)

class TwoBlockState:
 def __init__(self):
  self.buffers=[np.zeros(N,dtype=np.float64),np.zeros(N,dtype=np.float64)]
  self.work,self.previous=0,1
  self.scratch=np.zeros(G,dtype=np.float64)
  self.skip=H+G
  self.blocks=0
  self.events=[]
 def emit(self,section,part,output):
  take=min(self.skip,len(part));self.skip-=take
  if take<len(part):output.extend(part[take:].tolist())
  self.events.append({'block':self.blocks,'segment':section,
   'candidate_doubles':len(part),'skipped':take,'emitted':len(part)-take,
   'remaining_initial_skip':self.skip})
 def block(self,frames):
  assert frames.shape==(H//2,)
  b=self.buffers[self.work]
  b[0:H:2]=frames
  b[1:H:2]=0.0
  # C441-C445: dst(work+H), src(scratch), size=G.
  b[H:H+G]=self.scratch
  # C450-C45F: dst(scratch), src(work+H-G), size=G.
  self.scratch[:]=b[H-G:H]
  # FFT-multiply-inverse deliberately not implemented.
  prev=self.buffers[self.previous]
  output=[]
  self.emit('previous_tail',prev[N-G:N],output)
  self.emit('previous_front',prev[:H-G],output)
  self.work,self.previous=self.previous,self.work
  self.blocks+=1
  return np.array(output,dtype=np.float64)
 def process(self,x):
  assert len(x)%(H//2)==0
  return np.concatenate([self.block(part) for part in x.reshape(-1,H//2)])

def verify_two_block():
 assert (H,G,TAIL_START)==(2680,708,1972)
 signal=np.arange(4*(H//2),dtype=np.float64)+100.0
 whole=TwoBlockState();together=whole.process(signal)
 split=TwoBlockState();pieces=[split.process(signal[i:i+H//2]) for i in range(0,len(signal),H//2)]
 separated=np.concatenate(pieces)
 np.testing.assert_array_equal(together,separated)
 assert [len(x) for x in pieces]==[0,1972,2680,2680],list(map(len,pieces))
 assert len(together)==4*H-(H+G)==7332
 assert [a['skipped'] for a in split.events][:4]==[G,H-G,G,0]
 assert sum(e['skipped'] for e in whole.events)==H+G
 assert whole.skip==split.skip==0
 assert whole.blocks==split.blocks==4
 assert np.array_equal(whole.scratch,split.scratch)
 assert whole.work==split.work and whole.previous==split.previous
 for a,b in zip(whole.buffers,split.buffers):np.testing.assert_array_equal(a,b)
 assert together[0]==signal[0]
 bad=np.zeros(N);bad[:H:2]=signal[:H//2]
 naive_bad=bad.copy();naive_bad[H-G:H]=0
 assert np.any(bad[H-G:H]!=naive_bad[H-G:H])
 return {'frames_per_block':H//2,'new_upsampled_doubles_per_block':H,
  'saved_scratch_doubles':G,'scratch_source_start':H-G,
  'scratch_injected_at':H,'fft_buffer_doubles':N,
  'startup_skip':H+G,'first_four_block_emitted_doubles':[len(p) for p in pieces],
  'total_emitted_doubles_after_4_blocks':len(together),
  'two_call_vs_one_call_bitwise_equal':True,
  'skipped_units':sum(e['skipped'] for e in whole.events),
  'events_first_two_blocks':split.events[:4],
  'test_scope':'synthetic passthrough buffer-state model, not FFT/inverse/FIR signal parity'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True)
 a=p.parse_args()
 print(json.dumps({'original_dll_sha256':DLL_SHA,'instruction_pins':inspect(a.dll),
  'first_stage_44k1_to_48k':verify_two_block(),
  'still_open':'filter flag1 spectrum representation, actual convolution and native RAM/audio/CLO parity'},indent=2))

if __name__=='__main__':main()
