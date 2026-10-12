"""Stage23U: source-execute HTKPA real inverse FFT precombine & final conjugation.

DLL is only checked/statically disassembled; never loaded or executed.
Combine with Stage23Q algebraic inner stages and Stage23R synthetic forward
FFT. Round-trip tests are synthetic; native SSE/CRT/RAM parity remains OPEN.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess, sys
from pathlib import Path
import numpy as np

DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
N=4096;M=N//2
PINS={
0x18000974e:'cmp dword ptr [rsp+0xb8],0x0',
0x18000975b:'jl 0x18000988b',
0x180009892:'subsd xmm1,qword ptr [rdi+0x8]',
0x180009897:'mulsd xmm1,xmm8',
0x1800098a1:'subsd xmm0,xmm1',
0x1800098b2:'xorps xmm1,xmmword ptr [rip+0x243d37]',
0x1800098c3:'movsd qword ptr [rdi+0x8],xmm1',
0x180009900:'movsd xmm7,qword ptr [rdi+r14*8+0x8]',
0x180009907:'add r10,rbx',
0x18000990a:'addsd xmm7,qword ptr [rcx]',
0x18000990e:'movsd xmm6,qword ptr [rdi+r14*8]',
0x180009914:'add r11,rdx',
0x18000991a:'movaps xmm5,xmm8',
0x18000991e:'subsd xmm1,qword ptr [rcx-0x8]',
0x180009923:'subsd xmm5,qword ptr [r11]',
0x18000992b:'mulsd xmm3,qword ptr [r10]',
0x180009933:'mulsd xmm1,qword ptr [r10]',
0x180009938:'mulsd xmm7,xmm5',
0x18000993c:'mulsd xmm0,xmm5',
0x180009940:'subsd xmm7,xmm1',
0x180009944:'addsd xmm3,xmm0',
0x180009948:'movaps xmm0,xmm7',
0x18000994b:'subsd xmm0,qword ptr [rdi+r14*8+0x8]',
0x180009952:'subsd xmm6,xmm3',
0x180009956:'movsd qword ptr [rdi+r14*8+0x8],xmm0',
0x18000995d:'movsd qword ptr [rdi+r14*8],xmm6',
0x180009963:'add r14,0x2',
0x180009967:'addsd xmm3,qword ptr [rcx-0x8]',
0x18000996c:'subsd xmm7,qword ptr [rcx]',
0x180009970:'movsd qword ptr [rcx-0x8],xmm3',
0x180009975:'movsd qword ptr [rcx],xmm7',
0x180009979:'sub rcx,0x10',
0x180009986:'movsd xmm0,qword ptr [rdi+r8*8+0x8]',
0x180009991:'xorps xmm0,xmmword ptr [rip+0x243c58]',
0x18000999a:'movsd qword ptr [rdi+r8*8+0x8],xmm0',
0x1800099a4:'call 0x1800099f0',
0x1800099b1:'call 0x18000a120',
0x18000a145:'call 0x18000a370',
0x18000a168:'call 0x18000a850',
0x18000a191:'cmp eax,ebx',
0x18000a19e:'jne 0x18000a2ed',
0x18000a2ed:'test edx,edx',
0x18000a2f1:'movsd xmm5,qword ptr [rip+0x2432f7]',
0x18000a322:'movsd xmm4,qword ptr [rcx+r8*1]',
0x18000a328:'movsd xmm3,qword ptr [rcx-0x8]',
0x18000a330:'movsd xmm1,qword ptr [rcx+rdx*8]',
0x18000a335:'addsd xmm0,xmm3',
0x18000a339:'movsd xmm2,qword ptr [rcx]',
0x18000a33d:'subsd xmm4,xmm3',
0x18000a341:'subsd xmm2,xmm1',
0x18000a345:'xorps xmm1,xmm5',
0x18000a348:'movsd qword ptr [rcx+r8*1],xmm0',
0x18000a34e:'subsd xmm1,qword ptr [rcx]',
0x18000a352:'movsd qword ptr [rcx+rdx*8],xmm1',
0x18000a357:'movsd qword ptr [rcx-0x8],xmm4',
0x18000a35c:'movsd qword ptr [rcx],xmm2',
}
RANGES=((0x180009740,0x180009765),(0x18000988b,0x1800099b8),
        (0x18000a13e,0x18000a179),(0x18000a180,0x18000a1a8),
        (0x18000a2e8,0x18000a36b))
OP={'movsd','movaps','subsd','addsd','mulsd','xorps'}

def check_pe(path:Path):
 data=path.read_bytes()
 assert hashlib.sha256(data).hexdigest()==DLL_SHA,'Original DLL differs'
 asm={}
 for lo,hi in RANGES:
  raw=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
    f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(path)],text=True)
  for line in raw.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if m:
    p=m[2].lower().split('#')[0].strip();asm[int(m[1],16)]=' '.join(p.split())
 for va,fragment in PINS.items():
  assert fragment in asm.get(va,''),(hex(va),fragment,asm.get(va))
 return asm

def flip_sign(v):
 bits=struct.unpack('<Q',struct.pack('<d',float(v)))[0]^0x8000000000000000
 return struct.unpack('<d',struct.pack('<Q',bits))[0]

def source_inverse_precombine(packed,asm):
 assert packed.shape==(N,)
 b=packed.copy()
 # Source 0x988B–0x98C3, including signed flip after DC-Nyquist split.
 dc,nyq=float(b[0]),float(b[1]);half=(dc-nyq)*0.5
 b[1]=flip_sign(half);b[0]=dc-half
 co=[0.5*math.cos(2*math.pi*k/N) for k in range(1024)]
 si=[0.5*math.sin(2*math.pi*k/N) for k in range(1024)]
 sequence=[(addr,asm[addr]) for addr in sorted(asm) if 0x180009900<=addr<0x180009979]
 alu=0;iterations=0
 for k in range(1,1024):
  a=2*k;z=2*(M-k);regs={f'xmm{i}':0. for i in range(16)}
  regs['xmm8']=0.5
  mem={
   '[rdi+r14*8+0x8]':a+1,'[rdi+r14*8]':a,
   '[rcx]':z+1,'[rcx-0x8]':z,
  }
  def read(x):
   if x.startswith('xmm'):return regs[x]
   if x=='qword ptr [r10]':return co[k]
   if x=='qword ptr [r11]':return si[k]
   return float(b[mem[x.removeprefix('qword ptr ')]])
  def write(x,v):
   if x.startswith('xmm'):regs[x]=v
   else:b[mem[x.removeprefix('qword ptr ')]]=v
  for va,instruction in sequence:
   op,_,args=instruction.partition(' ')
   if op not in OP:continue
   left,right=map(str.strip,args.split(',',1))
   v=read(right)
   if op in ('movsd','movaps'):out=v
   elif op=='subsd':out=read(left)-v
   elif op=='addsd':out=read(left)+v
   elif op=='mulsd':out=read(left)*v
   else:raise AssertionError((hex(va),op))
   write(left,out);alu+=1
  iterations+=1
 # Source 0x9986–0x999A flips the sole central-bin imaginary value.
 b[M+1]=flip_sign(b[M+1])
 return b[::2]+1j*b[1::2],alu,iterations

def before_terminal(data):
 """Algebraic Stage23Q DIT prefix; A120 final radix-2 is emulated below."""
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage23q'))
 from fft_complex_integration import bit_reverse_indices,radix4_actual_memory_order
 x=data[bit_reverse_indices(11)].copy()
 angle=math.atan(1.)/512.
 w=np.exp(1j*angle*bit_reverse_indices(10))
 for group in range(M//8):
  for local,start in enumerate((0,4)):
   off=8*group+start
   x[off:off+4]=radix4_actual_memory_order(x[off:off+4])*(w[2*group+local]**np.arange(4))
 for stride_d in (8,32,128,512):
  stride=stride_d//2
  for group in range(M//(4*stride)):
   ix=4*stride*group+np.arange(stride)[:,None]+stride*np.arange(4)
   x[ix]=radix4_actual_memory_order(x[ix])*(w[group]**np.arange(4))
 return x

def source_inverse_last(pre,asm):
 x=before_terminal(pre)
 result=np.empty_like(x)
 # A2ED–A368 final radix-2 kernel, source DFT + conjugate sign-bit.
 code=[(addr,asm[addr]) for addr in sorted(asm) if 0x18000a322<=addr<=0x18000a35c]
 ops=0;flips=0
 for j in range(M//2):
  a=x[j];b=x[j+M//2]
  mem={'[rcx+r8*1]':float(a.real),'[rcx+rdx*8]':float(a.imag),
       '[rcx-0x8]':float(b.real),'[rcx]':float(b.imag)}
  regs={f'xmm{i}':0. for i in range(16)}
  for addr,insn in code:
   op,_,args=insn.partition(' ')
   if op not in OP:continue
   lhs,rhs=map(str.strip,args.split(',',1))
   def get(s):return regs[s] if s.startswith('xmm') else mem[s.removeprefix('qword ptr ')]
   if op=='xorps':out=flip_sign(get(lhs));flips+=1
   else:
    v=get(rhs)
    out= v if op in ('movsd','movaps') else (get(lhs)+v if op=='addsd' else get(lhs)-v)
   if lhs.startswith('xmm'):regs[lhs]=out
   else:mem[lhs.removeprefix('qword ptr ')]=out
   ops+=1
  result[j]=complex(mem['[rcx+r8*1]'],mem['[rcx+rdx*8]'])
  result[j+M//2]=complex(mem['[rcx-0x8]'],mem['[rcx]'])
 assert flips==1024
 return result,ops,flips

def run(dll):
 asm=check_pe(dll)
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage23q'))
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage23r'))
 from fft_complex_integration import integrated_fft
 from fft_real_packing_source import real_combine
 source_real=__import__('fft_real_packing_source').source(dll)
 rng=np.random.default_rng(0x23A120)
 cases=[]
 for k in [0,1,2,3,17,31,63,1023,1024,2047,2048,2049,4095]:
  x=np.zeros(N);x[k]=1.;cases.append((f'impulse_{k}',x))
 for name,x in [('zero',np.zeros(N)),('constant',np.ones(N)),('alternating',(-1.)**np.arange(N)),
  ('cos17',np.cos(2*math.pi*17*np.arange(N)/N)),('sin33',np.sin(2*math.pi*33*np.arange(N)/N))]:cases.append((name,x))
 for k in range(10):cases.append((f'random_{k}',rng.standard_normal(N)))
 worst=0.;first_failure=None;worst_case=None;pre_err=0.;last_err=0.;count=None
 for name,signal in cases:
  input_complex=signal[::2]+1j*signal[1::2]
  forward_complex=integrated_fft(input_complex)
  packed,_=real_combine(forward_complex,source_real)
  pre,ops,iterations=source_inverse_precombine(packed,asm)
  test_pre=float(np.max(np.abs(pre-np.conj(forward_complex))))
  pre_err=max(pre_err,test_pre)
  result,terminal_ops,flips=source_inverse_last(pre,asm)
  expected_last=np.conj(integrated_fft(pre))
  last_err=max(last_err,float(np.max(np.abs(result-expected_last))))
  real=np.empty(N);real[::2]=result.real;real[1::2]=result.imag
  d=np.abs(real-(M*signal));index=int(np.argmax(d));error=float(d[index])
  if error>worst:worst=error;worst_case=[name,index]
  if error>3e-11 and first_failure is None:first_failure=[name,index,error]
  if count is None:count=[ops,iterations,terminal_ops,flips]
  assert [ops,iterations,terminal_ops,flips]==count
 assert len(cases)==28 and first_failure is None,(len(cases),first_failure)
 assert last_err<3e-11 and pre_err<4e-13,(last_err,pre_err)
 # Negative control: omit final source conjugation: this cannot reproduce
 # general asymmetric time-domain data.
 s=np.zeros(N);s[1]=1
 z=integrated_fft(s[::2]+1j*s[1::2]);p,_=real_combine(z,source_real)
 pre,_,_=source_inverse_precombine(p,asm)
 bad=integrated_fft(pre);wrong=np.empty(N);wrong[::2]=bad.real;wrong[1::2]=bad.imag
 negative_error=float(np.max(np.abs(wrong-M*s)))
 assert negative_error>1000,negative_error
 return {'original_dll_sha256':DLL_SHA,'instruction_pins':len(PINS),
 'real_input_doubles':N,'inner_complex_points':M,
 'synthetic_full_real_forward_inverse_cases':len(cases),
 'mirror_pairs_per_case':count[1],
 'precombine_scalar_sse_ops_per_case':count[0],
 'terminal_radix2_scalar_ops_per_case':count[2],
 'terminal_xorps_sign_flips_per_case':count[3],
 'max_precombine_complex_conjugate_error':pre_err,
 'max_terminal_complex_conjugate_fft_error':last_err,
 'max_full_roundtrip_error_vs_2048_x':worst,
 'worst_case':worst_case,'first_error_above_3e_minus_11':first_failure,
 'negative_control_without_terminal_conjugation_max_error':negative_error,
 'proven_synthetic_inverse_gain':2048,'stage23s_rounded_branch_probe':fir_branch_probe(dll),
 'status':'synthetic source-executed precombine and terminal; algebraic inner FFT. No Windows vendor DLL RAM/CRT/SSE bit parity, FIR stream or CLO equivalence'}

def fir_branch_probe(dll):
 """Stage23S flag conflict through Stage23U source inverse, not numpy.irfft."""
 asm=check_pe(dll)
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage23s'))
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage23r'))
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage23q'))
 from fft_fir_multiply_source import multiply_source
 from fft_real_packing_source import real_combine,source
 from fft_complex_integration import integrated_fft
 code=source(dll)
 h=np.zeros(N);h[0]=1/2048;h[1]=1/4096;h[-1]=1/4096
 sine=np.sin(2*math.pi*33*np.arange(N)/N)
 to_packed=lambda s: real_combine(integrated_fft(s[::2]+1j*s[1::2]),code)[0]
 x_spec=to_packed(sine);h_spec=to_packed(h)
 results={}
 for flag in (0,1):
  p=multiply_source(x_spec,h_spec,flag)
  inv,_,_=source_inverse_precombine(p,asm)
  out,_,_=source_inverse_last(inv,asm)
  real=np.empty(N);real[::2]=out.real;real[1::2]=out.imag
  results['flag'+str(flag)+'_sine33_rms']=float(np.sqrt(np.mean(real**2)))
 assert results['flag0_sine33_rms']>.1 and results['flag1_sine33_rms']<1e-10
 return results

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True)
 print(json.dumps(run(p.parse_args().dll),indent=2))
