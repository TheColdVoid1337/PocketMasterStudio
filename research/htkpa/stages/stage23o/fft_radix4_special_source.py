"""Stage23O: source-derived A850 radix-4 twiddle cases (static DLL only).

Disassembles/executes ordered scalar SSE for one d=8 complex butterfly
per three twiddle branches of 0x18000A850. Independent positive DFT4
oracles check real/imag impulses and deterministic random complex vectors.
Full native FFT, Windows CRT exact trig, DSP and gains remain UNPROVEN.
"""
import argparse, cmath, hashlib, json, math, random, re, struct, subprocess
from pathlib import Path

DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BRANCHES={
 'pi_over_4':(0x18000AA10,0x18000AAE5,{'rdx':384,'rcx':64,'r8':-16,'rbx':-120,'rdi':-8,'rsi':-56},32,math.pi/4,46),
 'pi_over_8':(0x18000ABF0,0x18000AD1A,{'rcx':640,'r8':-16,'rdi':-120,'r15':64,'rsi':-8,'rbp':-56},64,math.pi/8,66),
 'three_pi_over_8':(0x18000ADD0,0x18000AF09,{'r8':896,'rax':-16,'rdi':-120,'r14':64,'rsi':-8,'rbp':-56},96,3*math.pi/8,66),
}
PINS={
 0x180009F15:'call 0x18000a370',
 0x180009F1A:'mov edx,0x8',
 0x180009F38:'call 0x18000a850',
 0x180009F3D:'mov edx,edi',
 0x180009F3F:'lea edi,[rdi*4+0x0]',
 0x18000A8A5:'lea rcx,[r11*8+0x0]',
 0x18000A99A:'add r9,0x10',
 0x18000A9A8:'movsd xmm10,qword ptr [r13+0x10]',
 0x18000AA10:'movsd xmm7,qword ptr [rdx]',
 0x18000AAB1:'mulsd xmm0,xmm10',
 0x18000AADF:'movsd qword ptr [rdx+rcx*1+0x8],xmm7',
 0x18000AB50:'movsd xmm12,qword ptr [r13+0x18]',
 0x18000AB5A:'movsd xmm13,qword ptr [r9+0x10]',
 0x18000AB64:'movsd xmm14,qword ptr [r9+0x18]',
 0x18000AB76:'addsd xmm10,xmm12',
 0x18000AB7B:'movsd xmm11,qword ptr [r13+0x0]',
 0x18000AB8F:'subsd xmm10,xmm14',
 0x18000AB94:'subsd xmm15,xmm0',
 0x18000ABF0:'movsd xmm8,qword ptr [rcx+r8*8]',
 0x18000AC7F:'mulsd xmm0,xmm4',
 0x18000ACFD:'subsd xmm1,xmm0',
 0x18000AD13:'movsd qword ptr [r15+rcx*1+0x8],xmm2',
 0x18000AD33:'movsd xmm13,qword ptr [r9]',
 0x18000AD3C:'movsd xmm14,qword ptr [r9+0x8]',
 0x18000ADD0:'movsd xmm6,qword ptr [r8]',
 0x18000AE6B:'xorps xmm1,xmmword ptr [rip+0x24277e]',
 0x18000AE72:'subsd xmm1,xmm0',
 0x18000AF02:'movsd qword ptr [r8+r14*1+0x8],xmm2',
}
RANGES=[(0x180009F10,0x180009F50),(0x18000A89A,0x18000A9B0),
 (0x18000AB40,0x18000ABAD),(0x18000AD28,0x18000AD80),
 (0x18000AA10,0x18000AAEE),(0x18000ABF0,0x18000AD23),
 (0x18000ADD0,0x18000AF18)]
LINE=re.compile(r'^\s*(180[0-9a-f]+):\s+([a-z]+)\s+(.+?)(?:\s+#.*)?$')
MEM=re.compile(r'(?:qword|xmmword) ptr \[([^]]+)\]',re.I)
SSE=('movsd','movaps','mulsd','addsd','subsd')

def pe_at(data,va,length):
 p=struct.unpack_from('<I',data,0x3c)[0]
 assert data[:2]==b'MZ' and data[p:p+4]==b'PE\x00\x00'
 opt=p+24;rva=va-struct.unpack_from('<Q',data,opt+24)[0]
 sec=opt+struct.unpack_from('<H',data,p+20)[0]
 for i in range(struct.unpack_from('<H',data,p+6)[0]):
  _,vaddr,size,offset=struct.unpack_from('<4I',data,sec+40*i+8)
  if vaddr<=rva and rva+length<=vaddr+size:
   return data[offset+rva-vaddr:offset+rva-vaddr+length]
 raise ValueError(hex(va))

def source(dll):
 pe=dll.read_bytes()
 assert hashlib.sha256(pe).hexdigest()==DLL_SHA,'original DLL SHA mismatch'
 asm={}
 for lo,hi in RANGES:
  out=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in out.splitlines():
   m=LINE.match(line)
   if m:asm[int(m[1],16)]=(m[2],' '.join(m[3].lower().split()))
 for va,fragment in PINS.items():
  assert fragment in ' '.join(asm.get(va,('',''))),(hex(va),fragment,asm.get(va))
 mask=struct.unpack('<Q',pe_at(pe,0x18024D5F0,8))[0]
 assert mask==0x8000000000000000
 return asm,mask

def index(operand,ptr):
 m=MEM.fullmatch(operand)
 assert m,operand
 out=0
 for term in re.findall(r'[+\-]?[^+\-]+',m[1]):
  sign=1
  if term.startswith('+'):term=term[1:]
  elif term.startswith('-'):sign=-1;term=term[1:]
  if '*' in term:
   r,k=term.split('*');out+=sign*ptr[r]*int(k)
  elif term in ptr:out+=sign*ptr[term]
  else:out+=sign*int(term,16)
 assert out%8==0,(operand,out)
 return out//8

def coeffs(angle):
 # 0xAB50 loads cos/sin(pi/4) from the permuted table at index 1;
 # second coefficient pair is index 2 (pi/8) or 3 (3pi/8).
 regs={f'xmm{i}':0. for i in range(16)}
 regs['xmm11']=math.cos(math.pi/4)
 regs['xmm12']=math.sin(math.pi/4)
 regs['xmm13']=math.cos(angle)
 regs['xmm14']=math.sin(angle)
 double_sin=regs['xmm12']+regs['xmm12']
 regs['xmm10']=double_sin*regs['xmm13']-regs['xmm14']
 regs['xmm15']=regs['xmm13']-double_sin*regs['xmm14']
 return regs

def execute(name,signal,asm,signmask):
 start,end,ptr,offset,angle,expected_ops=BRANCHES[name]
 assert len(signal)==4
 mem=[0.]*160
 for k,z in enumerate(signal):mem[offset+8*k:offset+8*k+2]=[z.real,z.imag]
 reg=coeffs(angle)
 if name=='pi_over_4':reg['xmm10']=math.cos(angle)
 ops=0;xor=0
 def read(x):
  return reg[x] if x.startswith('xmm') else mem[index(x,ptr)]
 def write(x,v):
  if x.startswith('xmm'):reg[x]=v
  else:mem[index(x,ptr)]=v
 for addr in sorted(i for i in asm if start<=i<end):
  op,args=asm[addr]
  if op=='xorps':
   assert name=='three_pi_over_8' and addr==0x18000AE6B
   dst=args.split(',',1)[0].strip()
   bits=struct.unpack('<Q',struct.pack('<d',reg[dst]))[0]^signmask
   reg[dst]=struct.unpack('<d',struct.pack('<Q',bits))[0]
   xor+=1;continue
  if op not in SSE:continue
  dst,src=map(str.strip,args.split(',',1))
  v=read(src)
  if op in ('movsd','movaps'):result=v
  elif op=='addsd':result=read(dst)+v
  elif op=='subsd':result=read(dst)-v
  else:result=read(dst)*v
  write(dst,result)
  ops+=1
 assert ops==expected_ops,(name,ops)
 assert xor==int(name=='three_pi_over_8')
 return [complex(*mem[offset+8*k:offset+8*k+2]) for k in range(4)],ops

def oracle(signal,angle):
 z=[signal[k] for k in (0,2,1,3)]
 return [sum(z[j]*cmath.exp(2j*math.pi*j*k/4) for j in range(4))
         *cmath.exp(1j*k*angle) for k in range(4)]

def check(dll):
 asm,mask=source(dll);rng=random.Random(0x23A850)
 result={};all_cases=0;worst=0.
 for name,(_,_,_,_,angle,_) in BRANCHES.items():
  cases=[[complex(j==k,0) for j in range(4)] for k in range(4)]
  cases += [[complex(0,j==k) for j in range(4)] for k in range(4)]
  cases += [[complex(rng.uniform(-2,2),rng.uniform(-2,2)) for _ in range(4)]
            for _ in range(1024)]
  maximum=0.
  for signal in cases:
   actual,ops=execute(name,signal,asm,mask)
   expected=oracle(signal,angle)
   maximum=max(maximum,max(abs(a-b) for a,b in zip(actual,expected)))
  assert maximum<2e-13,(name,maximum)
  result[name]={'phase_rad':angle,'source_scalar_sse_ops':ops,
                'sign_xor_ops':int(name=='three_pi_over_8'),
                'oracle_cases':len(cases),'maximum_abs_difference':maximum}
  all_cases+=len(cases);worst=max(worst,maximum)
 assert sum(x['source_scalar_sse_ops'] for x in result.values())==178
 return {'dll_sha256':DLL_SHA,'address_pins':len(PINS),'stage_scalar_doubles':4096,
  'radix4_stage_strides_doubles':[8,32,128,512],
  'tested_representative_stride_doubles':8,
  'branches':result,'test_cases':all_cases,'max_abs_error':worst,
  'unproven':'whole FFT, all twiddle-loop iterations, CRT bits, native RAM, audio, CLO gains'}

if __name__=='__main__':
 p=argparse.ArgumentParser()
 p.add_argument('--dll',type=Path,required=True)
 print(json.dumps(check(p.parse_args().dll),indent=2))
