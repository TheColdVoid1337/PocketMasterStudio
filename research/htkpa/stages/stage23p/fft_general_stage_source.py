"""Stage23P: source-check higher radix-4 twiddles for the 4096-double FIR FFT.

Disassembles original SHA-pinned 5868USB.dll and executes the two general
A850 SSE branches for every outer twiddle index and actual stride.
Independent DFT4 oracle checks 2592 synthetic inputs. No vendor execution,
native RAM comparison, complete FFT, audio or CLO parity.
"""
from __future__ import annotations
import argparse, cmath, hashlib, json, math, random, re, struct, subprocess
from pathlib import Path

DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINS={
 0x180009f1a:'mov edx,0x8',0x180009f2c:'lea edi,[rdx+0x18]',
 0x180009f38:'call 0x18000a850',0x180009f3f:'lea edi,[rdi*4+0x0]',
 0x18000a878:'movsxd r11,edx',0x18000a892:'lea r12d,[r11*4+0x0]',
 0x18000aaed:'jne 0x18000aa10',0x18000aaf3:'lea eax,[r12+r12*1]',
 0x18000aaf7:'cmp eax,r14d',0x18000aafa:'jge 0x18000af64',
 0x18000ab08:'lea edx,[rax+r11*1]',0x18000ab1e:'sub eax,r11d',
 0x18000ab27:'neg r11d',
 0x18000ab50:'movsd xmm12,qword ptr [r13+0x18]',
 0x18000ab56:'lea r14d,[r11+rdx*1]',
 0x18000ab5a:'movsd xmm13,qword ptr [r9+0x10]',
 0x18000ab60:'add r13,0x10',
 0x18000ab64:'movsd xmm14,qword ptr [r9+0x18]',
 0x18000ab6a:'add r9,0x20',
 0x18000ab76:'addsd xmm10,xmm12',
 0x18000ab7b:'movsd xmm11,qword ptr [r13+0x0]',
 0x18000ab8f:'subsd xmm10,xmm14',
 0x18000ab99:'cmp r14d,edx',
 0x18000ab9c:'jge 0x18000ad33',
 0x18000abf0:'movsd xmm8,qword ptr [rcx+r8*8]',
 0x18000acfd:'subsd xmm1,xmm0',
 0x18000ad13:'movsd qword ptr [r15+rcx*1+0x8],xmm2',
 0x18000ad1a:'add rcx,0x10',
 0x18000ad22:'jne 0x18000abf0',
 0x18000ad33:'movsd xmm13,qword ptr [r9]',
 0x18000ad3c:'movsd xmm14,qword ptr [r9+0x8]',
 0x18000ad4e:'movaps xmm10,xmm11',
 0x18000ad52:'addsd xmm10,xmm11',
 0x18000ad6c:'subsd xmm10,xmm14',
 0x18000ad71:'subsd xmm15,xmm0',
 0x18000ad79:'jge 0x18000af17',
 0x18000add0:'movsd xmm6,qword ptr [r8]',
 0x18000ae6b:'xorps xmm1,xmmword ptr [rip+0x24277e]',
 0x18000af02:'movsd qword ptr [r8+r14*1+0x8],xmm2',
 0x18000af09:'add r8,0x10',
 0x18000af11:'jne 0x18000add0',
 0x18000af17:'add rbx,qword ptr [rsp+0x108]',
 0x18000af1f:'lea edx,[rdx+r12*2]',
 0x18000af32:'cmp eax,dword ptr [rsp+0xf0]',
 0x18000af39:'jl 0x18000ab50',
}
RANGES=((0x180009f10,0x180009f50),(0x18000a870,0x18000a89c),
        (0x18000aae0,0x18000af40))
LINE=re.compile(r'^\s*(180[0-9a-f]+):\s+([a-z]+)\s+(.+?)(?:\s+#.*)?$')
MEM=re.compile(r'(?:qword|xmmword) ptr \[([^]]+)\]')
SSE={'movsd','movaps','addsd','subsd','mulsd'}

def pe_at(data,va,n):
 pe=struct.unpack_from('<I',data,0x3c)[0]
 assert data[:2]==b'MZ' and data[pe:pe+4]==b'PE\x00\x00'
 opt=pe+24;rva=va-struct.unpack_from('<Q',data,opt+24)[0]
 sections=opt+struct.unpack_from('<H',data,pe+20)[0]
 for i in range(struct.unpack_from('<H',data,pe+6)[0]):
  _,virt,raw,off=struct.unpack_from('<4I',data,sections+40*i+8)
  if virt<=rva and rva+n<=virt+raw:return data[off+rva-virt:off+rva-virt+n]
 raise ValueError(hex(va))

def source(dll):
 data=dll.read_bytes()
 assert hashlib.sha256(data).hexdigest()==DLL_SHA,'wrong original DLL'
 asm={}
 for lo,hi in RANGES:
  raw=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in raw.splitlines():
   m=LINE.match(line)
   if m:asm[int(m[1],16)]=(m[2],' '.join(m[3].lower().split()))
 for va,frag in PINS.items():
  assert frag in ' '.join(asm.get(va,('',''))),(hex(va),frag,asm.get(va))
 sign=struct.unpack('<Q',pe_at(data,0x18024d5f0,8))[0]
 assert sign==0x8000000000000000
 return asm,sign

def reverse10(value):
 assert 0<=value<1024
 return int(f'{value:010b}'[::-1],2)

def schedule():
 stages=[]
 for stride in (8,32,128,512):
  j=1;outer=[]
  while 8*j*stride<4096:outer.append(j);j+=1
  initial=stride
  general=len(outer)*stride
  assert initial+general==512
  stages.append({'stride_doubles':stride,'first_special_butterflies':initial,
    'outer_indices':len(outer),'first_general_j':1 if outer else None,
    'last_general_j':outer[-1] if outer else None,
    'general_butterflies':general,'total_butterflies':initial+general})
 assert sum(s['outer_indices'] for s in stages)==81
 assert sum(s['general_butterflies'] for s in stages)==1368
 return stages

def offset(token,ptr):
 m=MEM.fullmatch(token)
 assert m,token
 val=0
 for part in re.findall(r'[+\-]?[^+\-]+',m[1]):
  sign=1
  if part.startswith('+'):part=part[1:]
  elif part.startswith('-'):sign=-1;part=part[1:]
  if '*' in part:
   r,k=part.split('*');val+=sign*ptr[r]*int(k)
  elif part in ptr:val+=sign*ptr[part]
  else:val+=sign*int(part,16)
 assert val%8==0,(token,val)
 return val//8

def execute(signal,stride,theta,third,code,mask):
 """Low SSE scalar interpreter, source addressing scaled to real stride."""
 assert len(signal)==4 and stride in (8,32,128)
 mem=[0.]*(3*stride+2)
 for i,z in enumerate(signal):mem[i*stride:i*stride+2]=[z.real,z.imag]
 ptr=({'rcx':2*stride*8,'r8':-2*stride,'rdi':8-16*stride,
  'r15':stride*8,'rsi':-stride,'rbp':8-8*stride} if not third else
  {'r8':2*stride*8,'rax':-2*stride,'rdi':8-16*stride,
  'r14':stride*8,'rsi':-stride,'rbp':8-8*stride})
 regs={f'xmm{i}':0. for i in range(16)}
 regs['xmm11']=math.cos(2*theta)
 regs['xmm12']=math.sin(2*theta)
 phi=theta+math.pi/4 if third else theta
 regs['xmm13']=math.cos(phi);regs['xmm14']=math.sin(phi)
 # Source AB76 doubles SIN(2theta); AD52 doubles COS(2theta).
 # Both are required: for third branch sin(2phi)=cos(2theta).
 trigger=regs['xmm11'] if third else regs['xmm12']
 tw=trigger+trigger
 regs['xmm10']=tw*regs['xmm13']-regs['xmm14']
 regs['xmm15']=regs['xmm13']-tw*regs['xmm14']
 start,end=(0x18000add0,0x18000af09) if third else (0x18000abf0,0x18000ad1a)
 operations=0;xors=0
 def read(a):return regs[a] if a.startswith('xmm') else mem[offset(a,ptr)]
 def write(a,v):
  if a.startswith('xmm'):regs[a]=v
  else:mem[offset(a,ptr)]=v
 for va in sorted(i for i in code if start<=i<end):
  op,args=code[va]
  if op=='xorps':
   assert third and va==0x18000ae6b
   dst=args.split(',',1)[0].strip()
   bits=struct.unpack('<Q',struct.pack('<d',regs[dst]))[0]^mask
   regs[dst]=struct.unpack('<d',struct.pack('<Q',bits))[0]
   xors+=1;continue
  if op not in SSE:continue
  dst,src=map(str.strip,args.split(',',1))
  v=read(src)
  value=v if op in ('movsd','movaps') else (
        read(dst)+v if op=='addsd' else
        read(dst)-v if op=='subsd' else read(dst)*v)
  write(dst,value);operations+=1
 assert (operations,xors)==(66,int(third)),(operations,xors)
 return [complex(mem[i*stride],mem[i*stride+1]) for i in range(4)]

def oracle(signal,phase):
 ordered=[signal[i] for i in (0,2,1,3)]
 return [sum(ordered[j]*cmath.exp(2j*math.pi*j*k/4) for j in range(4))
  *cmath.exp(1j*k*phase) for k in range(4)]

def check(dll):
 code,mask=source(dll)
 stages=schedule();rng=random.Random(0x23A850)
 worst=0.;cases=0
 for stage in stages:
  stride=stage['stride_doubles']
  for j in range(1,stage['outer_indices']+1):
   theta=math.atan(1.)/512*reverse10(2*j)
   phi=math.atan(1.)/512*reverse10(2*j+1)
   twice=math.atan(1.)/512*reverse10(j)
   assert abs(twice-2*theta)<2e-15
   assert abs(phi-(theta+math.pi/4))<2e-15
   tests=[[complex(k==p,0) for k in range(4)] for p in range(4)]
   tests += [[complex(0,k==p) for k in range(4)] for p in range(4)]
   tests += [[complex(rng.uniform(-1,1),rng.uniform(-1,1)) for _ in range(4)]
            for _ in range(8)]
   for signal in tests:
    for third,phase in ((False,theta),(True,phi)):
     actual=execute(signal,stride,theta,third,code,mask)
     expected=oracle(signal,phase)
     worst=max(worst,max(abs(a-b) for a,b in zip(actual,expected)))
     cases+=1
 assert cases==2592 and worst<2e-13,(cases,worst)
 return {'dll_sha256':DLL_SHA,'instruction_pins':len(PINS),
  'all_4096_double_stage_calls':stages,'general_outer_indices':81,
  'sse_per_general_butterfly':66,
  'general_butterflies_across_four_stages':1368,
  'synthetic_dft4_cases':cases,'maximum_abs_error':worst,
  'critical_fix':'AD52 doubles cos(2theta), AB76 doubles sin(2theta)',
  'scope':'source-executed general branches only; full FFT and native DLL RAM parity OPEN'}

if __name__=='__main__':
 p=argparse.ArgumentParser()
 p.add_argument('--dll',type=Path,required=True)
 print(json.dumps(check(p.parse_args().dll),indent=2))
