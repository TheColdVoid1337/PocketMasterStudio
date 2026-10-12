"""HTKPA Stage23R: source-executed real FFT post-combine, N=4096 doubles.

Read-only PE/objdump; ~30 ordered low-scalar f64 SSE ops per mirrored pair;
full post-combine using the source-consistent Stage23Q complex FFT model.
Mathematical synthetic FFT parity only, not original Windows DLL execution,
CRT bit parity, resampler overlap, vendor RAM, audio or CLO parity.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess, sys
from pathlib import Path
import numpy as np

N=4096; M=N//2
DLL_SHA="fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
PINS={
  0x18000950C:'mov r12d,dword ptr [r9]',
  0x18000954F:'sar r12d,0x2',
  0x18000959F:'call 0x18017e116',
  0x180009647:'call 0x1800099f0',
  0x180009654:'mov r15d,dword ptr [r9+0x4]',
  0x180009658:'movsd xmm8,qword ptr [rip+0x24321f]',
  0x180009677:'sar r15d,0x2',
  0x18000967B:'mov dword ptr [r9+0x4],r15d',
  0x1800096CF:'movsd qword ptr [rcx+rax*8],xmm0',
  0x180009705:'mulsd xmm0,xmm8',
  0x18000970A:'movsd qword ptr [rdi+rbx*8],xmm0',
  0x180009712:'call 0x18017e15e',
  0x180009717:'mulsd xmm0,xmm8',
  0x180009726:'movsd qword ptr [rsi+0x8],xmm0',
  0x180009773:'call 0x1800099f0',
  0x180009780:'call 0x180009ef0',
  0x180009785:'movsxd rax,r12d',
  0x18000978A:'sar ecx,1',
  0x18000978F:'lea r8,[rsi+rax*8]',
  0x180009793:'lea eax,[r15+r15*1]',
  0x180009798:'idiv ecx',
  0x1800097A4:'movsxd rdx,eax',
  0x1800097AE:'lea rcx,[rdi+rcx*8]',
  0x1800097B2:'lea r11,[rdx*8+0x0]',
  0x1800097BA:'neg rdx',
  0x1800097BD:'shl rdx,0x3',
  0x1800097C1:'lea r9,[r8+rax*8]',
  0x1800097D0:'movsd xmm6,qword ptr [rdi+r14*8]',
  0x1800097D6:'add r8,r11',
  0x1800097D9:'movsd xmm4,qword ptr [rdi+r14*8+0x8]',
  0x1800097E3:'subsd xmm7,qword ptr [rcx-0x8]',
  0x1800097EB:'add r9,rdx',
  0x1800097EE:'addsd xmm1,qword ptr [rcx]',
  0x1800097F6:'subsd xmm5,qword ptr [r9]',
  0x1800097FE:'mulsd xmm7,qword ptr [r8]',
  0x18000980B:'mulsd xmm3,xmm5',
  0x180009813:'subsd xmm3,xmm0',
  0x180009817:'addsd xmm7,xmm1',
  0x180009823:'movsd qword ptr [rdi+r14*8],xmm6',
  0x180009829:'movsd qword ptr [rdi+r14*8+0x8],xmm4',
  0x180009830:'add r14,0x2',
  0x18000983D:'subsd xmm0,xmm7',
  0x180009841:'movsd qword ptr [rcx-0x8],xmm3',
  0x180009846:'movsd qword ptr [rcx],xmm0',
  0x18000984A:'sub rcx,0x10',
  0x18000984E:'cmp r14,r10',
  0x180009851:'jl 0x1800097d0',
  0x18000986B:'movsd xmm2,qword ptr [rdi]',
  0x180009874:'addsd xmm0,xmm2',
  0x180009878:'subsd xmm2,qword ptr [rdi+0x8]',
  0x18000987D:'movsd qword ptr [rdi],xmm0',
  0x180009881:'movsd qword ptr [rdi+0x8],xmm2',
}
RANGES=[(0x1800094f0,0x18000952d),(0x180009540,0x180009560),
 (0x180009590,0x180009653),(0x180009654,0x180009685),
 (0x1800096c0,0x1800096d9),(0x1800096f0,0x180009730),
 (0x18000976a,0x180009886)]
LINE=re.compile(r'^\s*(180[0-9a-f]+):\s+([a-z]+)\s+(.+?)(?:\s+#.*)?$')
MEM=re.compile(r'qword ptr \[([^]]+)\]')
SSE={'movsd','movaps','mulsd','addsd','subsd'}


def source(dll:Path):
 data=dll.read_bytes()
 assert hashlib.sha256(data).hexdigest()==DLL_SHA,'original vendor DLL SHA mismatch'
 instructions={}
 for low,high in RANGES:
  raw=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   f'--start-address={low:#x}',f'--stop-address={high:#x}',str(dll)],text=True)
  for line in raw.splitlines():
   m=LINE.match(line)
   if m:instructions[int(m[1],16)]=(m[2],' '.join(m[3].lower().split()))
 for a,p in PINS.items():
  assert p in ' '.join(instructions.get(a,('',''))),(hex(a),p,instructions.get(a))
 return instructions


def read_mem(op,pointers,mem,costable,sintable):
 m=MEM.fullmatch(op)
 assert m,op
 addr=0
 for term in re.findall(r'[+\-]?[^+\-]+',m.group(1)):
  sign=1
  if term.startswith('+'):term=term[1:]
  elif term.startswith('-'):term=term[1:];sign=-1
  if '*' in term:
   reg,n=term.split('*');addr+=sign*pointers[reg]*int(n)
  elif term in pointers:addr+=sign*pointers[term]
  else:addr+=sign*int(term,16)
 assert addr%8==0,(op,addr)
 # Pointers for external cos/sin tables occupy separate logical regions.
 if 'r8' in m.group(1):return float(costable[addr//8])
 if m.group(1)=='r9':return float(sintable[-addr//8])
 assert 0<=addr//8<len(mem),(op,addr)
 return float(mem[addr//8])


def write_mem(op,pointers,mem,value):
 m=MEM.fullmatch(op)
 assert m and m.group(1).startswith(('rcx','rdi')),(op,m)
 addr=0
 for term in re.findall(r'[+\-]?[^+\-]+',m.group(1)):
  sign=1
  if term.startswith('+'):term=term[1:]
  elif term.startswith('-'):term=term[1:];sign=-1
  if '*' in term:
   reg,n=term.split('*');addr+=sign*pointers[reg]*int(n)
  elif term in pointers:addr+=sign*pointers[term]
  else:addr+=sign*int(term,16)
 assert addr%8==0 and 0<=addr//8<len(mem),(op,addr)
 mem[addr//8]=value


def real_combine(complex_fft,code):
 assert complex_fft.shape==(M,)
 buf=np.empty(N,dtype=np.float64)
 buf[0::2]=complex_fft.real;buf[1::2]=complex_fft.imag
 # Source 0x9691..0x9730: half-scaled cosine/sine in a mirrored table.
 theta=math.atan(1.0)/512.0  # 2*pi/N
 costable=[0.5*math.cos(k*theta) for k in range(1024)]
 sintable=[0.5*math.sin(k*theta) for k in range(1024)]
 ptr={'rdi':0,'r14':2,'rcx':(N-1)*8,'r8':0,'r9':0,'rdx':-8,'r11':8}
 xmm={f'xmm{i}':0. for i in range(16)}
 xmm['xmm8']=0.5
 original_middle=(buf[M],buf[M+1])
 ops=0; iterations=0
 code_loop=sorted((addr,inst) for addr,inst in code.items() if 0x1800097D0<=addr<0x18000984E)
 for k in range(1,1024):
  for va,(op,args) in code_loop:
   if op=='add' and args=='r8,r11':ptr['r8']+=8;continue
   if op=='add' and args=='r9,rdx':ptr['r9']-=8;continue
   if op=='add' and args=='r14,0x2':ptr['r14']+=2;continue
   if op=='sub' and args=='rcx,0x10':ptr['rcx']-=16;continue
   if op not in SSE:raise AssertionError((hex(va),op,args))
   dst,src=map(str.strip,args.split(',',1))
   val=xmm[src] if src.startswith('xmm') else read_mem(src,ptr,buf,costable,sintable)
   if dst.startswith('xmm'):
    if op in ('movsd','movaps'):xmm[dst]=val
    elif op=='mulsd':xmm[dst]*=val
    elif op=='addsd':xmm[dst]+=val
    elif op=='subsd':xmm[dst]-=val
   else:
    assert op=='movsd'
    write_mem(dst,ptr,buf,val)
   ops+=1
  iterations+=1
 assert iterations==1023 and ptr['r14']==2048 and ptr['rcx']==(2049)*8
 assert (buf[M],buf[M+1])==original_middle,'middle packed complex bin must remain unchanged'
 # Exact source order for DC/Nyquist 0x986B–0x9881.
 first=float(buf[0]);second=float(buf[1])
 buf[0]=first+second;buf[1]=first-second
 return buf,ops


def numpy_packed(signal):
 n=len(signal);assert n==N
 transform=np.conj(np.fft.rfft(signal))
 packed=np.empty(n)
 packed[0]=transform[0].real;packed[1]=transform[-1].real
 packed[2::2]=transform[1:-1].real
 packed[3::2]=transform[1:-1].imag
 return packed


def run(dll:Path):
 code=source(dll)
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'stage23q'))
 from fft_complex_integration import integrated_fft
 rng=np.random.default_rng(0x23A970)
 cases=[]
 for pos in [0,1,2,3,4,7,31,1023,1024,2047,2048,2049,4095]:
  v=np.zeros(N);v[pos]=1;cases.append((f'impulse_{pos}',v))
 cases.extend([('zero',np.zeros(N)),('constant',np.ones(N)),('alternating',(-1.)**np.arange(N)),
   ('tone_7',np.cos(2*math.pi*7*np.arange(N)/N)),
   ('sine_33',np.sin(2*math.pi*33*np.arange(N)/N))])
 for j in range(10):cases.append((f'random_{j}',rng.standard_normal(N)))
 worst=0.;worst_where=None;all_ops=None
 for name,signal in cases:
  inner=integrated_fft(signal[::2]+1j*signal[1::2])
  got,operations=real_combine(inner,code)
  if all_ops is None:all_ops=operations
  assert operations==all_ops
  expected=numpy_packed(signal)
  delta=np.abs(got-expected);index=int(np.argmax(delta));err=float(delta[index])
  if err>worst:worst=err;worst_where=[name,index]
  assert err<3e-11,(name,index,err)
 assert len(cases)==28
 # Negative-sign packing must fail for impulse n=1 (positive transform case).
 impulse=np.zeros(N);impulse[1]=1
 got,_=real_combine(integrated_fft(impulse[::2]+1j*impulse[1::2]),code)
 negative=np.fft.rfft(impulse)
 assert abs(got[3]-negative[1].imag)>1e-3
 return {'original_dll_sha256':DLL_SHA,'instruction_pins':len(PINS),
  'complex_points':M,'real_samples':N,'source_real_pair_iterations':1023,
  'scalar_sse_operations_per_pair':all_ops//1023,
  'source_scalar_sse_operations_total':all_ops,
  'packed_layout':'[Re X0, Re X2048, Re X1, Im X1, ..., Re X2047, Im X2047]',
  'spectrum_sign':'positive; conjugate of numpy rfft',
  'untouched_middle_bin_k1024':True,
  'complete_real_fft_synthetic_cases':len(cases),'max_abs_error':worst,
  'worst_case':worst_where,
  'negative_sign_control':'passed',
  'limits':'source-executed real post-combine + algebraic Stage23Q inner complex FFT; no vendor Windows CRT/SSE native RAM parity, audio/gains/CLO'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dll',required=True,type=Path)
 print(json.dumps(run(p.parse_args().dll),indent=2))
