"""Stage23J: SHA-pinned source-first real FFT plan/call trace, not native parity.

Normal 44100->48000 branch: first FIR has 1417 nonzero taps in a 4096
double ring; FFT plan exponent=12, N=4096, cached trig/permutation buffers.
The caller selects EDX=1 (forward). 0x94F0 performs twiddle initialization,
0x99F0 swaps complex pairs, 0x9EF0 is the forward butterfly dispatcher,
and real DC/Nyquist bins are combined by sum/difference.
Only original PE disassembly is used; no vendor DLL execution.
"""
import argparse
import hashlib
import math
import re
import subprocess
from pathlib import Path

DLL_SHA="fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"

PINS={
 0x18000AFFA:"mov dword ptr [rax],ebp",
 0x18000B001:"shl eax,cl",
 0x18000B005:"mov dword ptr [rdi+0x4],eax",
 0x18000B010:"divsd xmm0,xmm1",
 0x18000B014:"movsd qword ptr [rdi+0x8],xmm0",
 0x18000B019:"mov qword ptr [rdi+0x18],rbp",
 0x18000B01D:"mov qword ptr [rdi+0x20],rbp",
 0x18000B05B:"mov qword ptr [rdi+0x18],rax",
 0x18000B073:"shl rcx,0x3",
 0x18000B07D:"mov qword ptr [rdi+0x20],rax",
 0x18000BAAC:"mov edx,0x1",
 0x18000BAB1:"mov r9,qword ptr [rbx+0x18]",
 0x18000BAB5:"mov r8,qword ptr [rdi+0x50]",
 0x18000BAB9:"mov ecx,dword ptr [rbx+0x4]",
 0x18000BABC:"mov qword ptr [rsp+0x20],rax",
 0x18000BAC1:"call 0x1800094f0",
 0x18000950C:"mov r12d,dword ptr [r9]",
 0x180009531:"lea eax,[r12*4+0x0]",
 0x180009548:"mov r12d,ebp",
 0x18000954F:"sar r12d,0x2",
 0x180009553:"mov dword ptr [r9],r12d",
 0x18000955F:"0x18024c918",
 0x18000956A:"sar ebx,1",
 0x180009574:"call 0x18017e0f8",
 0x180009592:"divsd xmm8,xmm6",
 0x18000959F:"call 0x18017e116",
 0x1800095FB:"call 0x18017e15e",
 0x180009635:"mov rdx,qword ptr [rsp+0xc8]",
 0x180009647:"call 0x1800099f0",
 0x180009773:"call 0x1800099f0",
 0x180009780:"call 0x180009ef0",
 0x18000974E:"cmp dword ptr [rsp+0xb8],0x0",
 0x18000975B:"jl 0x18000988b",
 0x18000986B:"movsd xmm2,qword ptr [rdi]",
 0x18000986F:"movsd xmm0,qword ptr [rdi+0x8]",
 0x180009874:"addsd xmm0,xmm2",
 0x180009878:"subsd xmm2,qword ptr [rdi+0x8]",
 0x18000987D:"movsd qword ptr [rdi],xmm0",
 0x180009881:"movsd qword ptr [rdi+0x8],xmm2",
 0x180009A00:"mov dword ptr [rdx],0x0",
 0x180009A1D:"mov r11,qword ptr [rsp+0x68]",
 0x180009A46:"add ecx,r9d",
 0x180009A49:"mov dword ptr [rbx+rdx*1-0x4],ecx",
 0x180009F12:"mov rdx,rsi",
 0x180009F15:"call 0x18000a370",
 0x180009F38:"call 0x18000a850",
}
RANGES=[
 (0x18000AFF0,0x18000B086),(0x18000BAA0,0x18000BAC6),
 (0x1800094F0,0x180009605),(0x180009630,0x180009660),
 (0x180009740,0x180009790),(0x180009860,0x18000988b),
 (0x1800099F0,0x180009A58),(0x180009EF0,0x180009F4F),
 (0x18017E0F2,0x18017E102),(0x18017E110,0x18017E11C),
 (0x18017E158,0x18017E164),
]

def verify(dll):
 assert hashlib.sha256(dll.read_bytes()).hexdigest()==DLL_SHA
 instr={}
 for lo,hi in RANGES:
  lines=subprocess.check_output(["objdump","-d","-M","intel","--no-show-raw-insn",
   f"--start-address={lo:#x}",f"--stop-address={hi:#x}",str(dll)],text=True)
  for line in lines.splitlines():
   m=re.match(r"\s*(180[0-9a-f]+):\s+(.+)",line)
   if m: instr[int(m[1],16)]=" ".join(m[2].lower().split())
 for va,needle in PINS.items():
  assert needle in instr.get(va,""),(hex(va),needle,instr.get(va))
 for thunk,iat in [(0x18017e0f8,"0x18018b9d0"),(0x18017e116,"0x18018ba70"),
                   (0x18017e15e,"0x18018ba18")]:
  assert iat in instr[thunk],(hex(thunk),iat)
 return len(PINS)

def basic_math():
 n=4096
 assert n==2**12
 angle=math.atan(1.)/(n//8) # atan(1)=pi/4 => 2*pi/n
 assert abs(angle-2*math.pi/n)<1e-15
 assert abs(2./n-1./2048)<1e-15
 for real,imag in [(0.,0.),(1.,0.),(0.,1.),(.15,-.25)]:
  dc=real+imag
  nyquist=real-imag
  assert abs((dc+nyquist)/2-real)<1e-15
  assert abs((dc-nyquist)/2-imag)<1e-15
 return {"N":n,"log2N":12,"forward_mode":1,"plan_scale":2/n,
  "twiddle_step":angle,"twiddle_cos_1":math.cos(angle),
  "twiddle_sin_1":math.sin(angle),"tests":6}

if __name__=="__main__":
 import json
 ap=argparse.ArgumentParser()
 ap.add_argument("--dll",type=Path,required=True)
 a=ap.parse_args()
 print(json.dumps({"pins":verify(a.dll),**basic_math(),
  "next_gate":"0x9EF0/0xA850 butterfly parity, then streaming overlap",
  "parity":"NOT_COMPUTED: native FFT memory and audio not captured"},indent=2))
