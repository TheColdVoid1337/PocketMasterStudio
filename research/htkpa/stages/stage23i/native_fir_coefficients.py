"""HTKPA Stage23I: source-derived 1417-tap FIR and cyclic FFT layout.

Validates original PE SHA, 49 instruction pins and 18 constants; reconstructs
the scalar FIR *candidate*. Does not execute DLL or prove native CRT/FFT/audio
bit parity, nor official CLO gains. No proprietary audio or binaries committed.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess, sys
from pathlib import Path
from array import array

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'stage23h'))
from native_fir_length import raw_at, reproduce

DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINS={
0x18000AFF0:'0x18024ca38',0x18000B001:'shl eax,cl',0x18000B010:'divsd xmm0,xmm1',
0x18000BCFB:'movsd qword ptr [rbx+0x10],xmm6',0x18000BD03:'movsd qword ptr [rbx+0x20],xmm9',
0x18000B838:'movsd qword ptr [rsp+0x30],xmm8',0x18000B83F:'mulsd xmm11,qword ptr [rdi]',
0x18000B854:'xorps xmm0,xmm0',0x18000B86A:'call 0x18017e15e',
0x18000B896:'subsd xmm0,xmm11',0x18000B89B:'call 0x18017e15e',
0x18000B8A6:'movaps xmm0,xmm11',0x18000B8AA:'call 0x18017e116',
0x18000B8D0:'0x18024cc20',0x18000B8DD:'call 0x180008e90',
0x18000B8EF:'mov dword ptr [rdi+0x48],ebx',
0x18000B957:'shl r12d,cl',0x18000B964:'lea r15d,[r12+r12*1]',
0x18000B981:'call 0x180014810',0x18000B99D:'mov qword ptr [rdi+0x40],rsi',
0x18000B9A1:'call 0x18000afa0',0x18000B9C0:'addsd xmm7,qword ptr [rax]',
0x18000B9D9:'movsd xmm1,qword ptr [rbx+0x8]',0x18000B9DE:'mulsd xmm1,qword ptr [rdi+0x20]',
0x18000B9E3:'divsd xmm1,xmm7',0x18000BA02:'mulsd xmm0,qword ptr [rdx+rcx*8]',
0x18000BA07:'movsd qword ptr [rdx+r8*1-0x8],xmm0',
0x18000BA40:'mov rax,qword ptr [rcx+r9*1-0x8]',
0x18000BA45:'mov qword ptr [rcx+rdx*1+0x8],rax',
0x180009001:'subsd xmm1,xmm0',0x180009011:'call 0x18017e16a',
0x180009016:'mulsd xmm0,qword ptr [rbx+0xc0]',
0x18000901E:'call 0x180008e90',0x180009023:'divsd xmm0,qword ptr [rbx+0xc8]',
0x180014824:'movsd xmm1,qword ptr [rcx+0x28]',
0x180014833:'mulsd xmm0,qword ptr [rcx+0x38]',
0x180014854:'subsd xmm0,qword ptr [rcx+0x30]',
0x180014884:'call 0x180008fd0',
0x180014946:'comisd xmm8,xmm2',0x18001496E:'call 0x18017e152',
0x18001497D:'movsd xmm9,qword ptr [rip',
0x1800149A8:'call 0x180008fd0',
0x1800149C4:'call 0x18017e152',
0x180014A04:'subsd xmm3,xmm2',
0x180014A1B:'divsd xmm3,xmm0',
0x180014A1F:'divsd xmm3,xmm9',
0x180008EB5:'comisd xmm8,xmm7',0x180008F24:'movaps xmm0,xmm7',
0x180008FBF:'mulsd xmm0,xmm6'
}
RANGES=[(0x18000AFF0,0x18000B015),(0x18000BCF0,0x18000BD0B),
 (0x18000B82A,0x18000B8B3),(0x18000B8C5,0x18000B8F3),
 (0x18000B94E,0x18000B9B0),(0x18000B9B0,0x18000BA56),
 (0x180008E90,0x180009031),(0x180014820,0x180014A35)]
CONSTANTS={
0x18024c918:1.,0x18024ca90:3.75,0x18024cc20:125.,
0x18024c678:0.0045813,0x18024c738:0.0360768,0x18024c808:0.2659732,
0x18024c9b0:1.2067492,0x18024ca78:3.0899424,0x18024ca88:3.5156229,
0x18024c660:0.00392377,0x18024c700:0.01647633,0x18024c720:0.02635537,
0x18024c710:0.02057706,0x18024c6c0:0.00916281,0x18024c630:0.00157565,
0x18024c648:0.00225319,0x18024c6f0:0.01328592,0x18024c838:0.39894228}

def verify(dll):
 data=dll.read_bytes()
 assert hashlib.sha256(data).hexdigest()==DLL_SHA, "wrong original DLL"
 asm={}
 for lo,hi in RANGES:
  txt=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
    f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in txt.splitlines():
   match=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if match:asm[int(match[1],16)]=' '.join(match[2].lower().split())
 for address,fragment in PINS.items():
  assert fragment in asm.get(address,''),(hex(address),fragment,asm.get(address))
 c=lambda address:struct.unpack('<d',raw_at(data,address,8))[0]
 for address,value in CONSTANTS.items():
  assert c(address)==value,(hex(address),c(address),value)
 return data,c

def bessel_native_approx(x,c):
 """Reconstruct native 0x180008E90 Horner branches; platform exp/sqrt."""
 ax=abs(x);base=c(0x18024ca90)
 if ax<base:
  v=x/base;z=v*v
  t=c(0x18024c678)*z+c(0x18024c738)
  for a in (0x18024c808,0x18024c9b0,0x18024ca78,0x18024ca88,0x18024c918):
   t=t*z+c(a)
  return t
 z=base/ax
 t=c(0x18024c660)*z-c(0x18024c700)
 for sign,address in [(1,0x18024c720),(-1,0x18024c710),(1,0x18024c6c0),
                      (-1,0x18024c630),(1,0x18024c648),(1,0x18024c6f0),(1,0x18024c838)]:
  t=t*z+sign*c(address)
 return (math.exp(ax)/math.sqrt(ax))*t

def reconstruct(data,c):
 meta=reproduce(data)
 g=meta['G'];gf=meta['G_before_floor']
 correction=meta['phase_correction'];y=meta['intermediate_y']
 assert g==708 and 2*g+1==1417
 angular=(1.0-correction)*math.pi*meta['upstream_params']['cutoff']
 # 0x14810 two oscillators: sin(0*n) and sin(angular*n).
 slow,slowprev=0.,0.
 fast,fastprev=0.,math.sin(-angular)
 cosfast=2.0*math.cos(angular)
 sin_y=math.sin(y)
 beta=c(0x18024cc20)
 denominator=bessel_native_approx(beta,c)
 raw=[]
 for n in range(g+1):
  t=n/gf
  window=bessel_native_approx(beta*math.sqrt(1.0-t*t),c)/denominator
  if n==0:
   sample=angular*sin_y/math.pi*window
  else:
   nextslow=slow*2.0-slowprev;slowprev,slow=slow,nextslow
   nextfast=fast*cosfast-fastprev;fastprev,fast=fast,nextfast
   sample=(fast-slow)*sin_y/n/math.pi*window
  raw.append(sample)
 # Original 0xB9C0 loop sums the centered source array in storage order.
 centered=list(reversed(raw[1:]))+raw
 total=0.
 for value in centered:total+=value
 exponent=(2*g).bit_length()
 half_fft=1<<exponent
 length=half_fft*2
 # AFA0 stores 2/(2**(exponent+1)); BB80 supplies gain 2.0.
 scale=((2./(1<<(exponent+1)))*2.)/total
 packed=[0.]*length
 for n,value in enumerate(raw):packed[n]=value*scale
 for n in range(1,g+1):packed[length-n]=packed[n]
 assert length==4096 and abs(sum(packed)-1./1024)<1e-14
 assert all(packed[i]==0. for i in range(g+1,length-g))
 le=array('d',packed)
 if sys.byteorder!='little':le.byteswap()
 return {'G':g,'taps':2*g+1,'fft_buffer_size':length,
  'native_fft_gain_target':1./1024,'candidate_fft_gain_sum':sum(packed),
  'center_coefficient':packed[0],'first_positive_taps':packed[1:6],
  'raw_symmetric_sum':total,'normalization_multiplier':scale,
  'nonzero_bins':2*g+1,
  'candidate_float64_le_sha256':hashlib.sha256(le.tobytes()).hexdigest(),
  'instruction_pins':len(PINS),'PE_constants':len(CONSTANTS),
  'scope':'static-source reconstruction; original DLL not executed; no RAM/FFT/audio/gain parity'}

if __name__=='__main__':
 ap=argparse.ArgumentParser()
 ap.add_argument('--dll',type=Path,required=True)
 args=ap.parse_args()
 data,c=verify(args.dll)
 print(json.dumps(reconstruct(data,c),indent=2,sort_keys=True))
