"""Stage24B SHA-pinned static FIR generator-argument gate (no DLL execution)."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINS={
0x18000CF3C:'movsd xmm6,qword ptr [rip+',0x18000CF44:'movsd xmm7,qword ptr [rip+',
0x18000CFD3:'cvtss2sd xmm2,xmm8',0x18000CFDB:'cvtss2sd xmm1,xmm9',
0x18000CFE0:'movsd qword ptr [rsp+0x28],xmm6',0x18000CFE6:'movsd qword ptr [rsp+0x20],xmm7',
0x18000CFF3:'call 0x180011b60',0x180011BCC:'movaps xmm9,xmm2',
0x180011BD0:'movaps xmm8,xmm1',0x180011C83:'comisd xmm9,xmm8',
0x180011C8A:'movaps xmm6,xmm11',0x180011C90:'movaps xmm6,xmm9',
0x180011C94:'mulsd xmm6,xmm11',0x180011C99:'divsd xmm6,xmm8',
0x180011CD3:'movaps xmm2,xmm12',0x180011CD7:'movsd xmm1,qword ptr [rsp+0x150]',
0x180011CE0:'movaps xmm0,xmm6',0x180011CE3:'call 0x18000bb80',
0x18000BCF1:'movsd qword ptr [rbx],xmm8',0x18000BCF6:'movsd qword ptr [rbx+0x8],xmm7',
0x18000BCFB:'movsd qword ptr [rbx+0x10],xmm6',0x18000BD03:'movsd qword ptr [rbx+0x20],xmm9',
0x18000BD12:'call 0x18000b0e0',0x18000B821:'subsd xmm11,xmm6',
0x18000B826:'divsd xmm8,qword ptr [rdi]',0x18000B82B:'mulsd xmm11,qword ptr [rip+',
0x18000B838:'movsd qword ptr [rsp+0x30],xmm8',0x18000B83F:'mulsd xmm11,qword ptr [rdi]',
0x18000B84B:'call 0x18017e134',0x18000B8AF:'andps xmm9,xmmword ptr [rip+',
0x18000B8C1:'movsd qword ptr [rsp+0x50],xmm9',0x18000B8D0:'movsd xmm0,qword ptr [rip+',
0x18000B8DD:'call 0x180008e90',0x18000B8F9:'movsd qword ptr [rbp+0x0],xmm0',
0x18000B97C:'lea rcx,[rsp+0x30]',0x18000B981:'call 0x180014810',
0x18001487F:'movsd xmm6,qword ptr [rcx+0x20]',0x180014884:'call 0x180008fd0',
0x180014953:'movaps xmm1,xmm6',0x18001496E:'call 0x18017e152',
0x180008FD6:'mov eax,dword ptr [rcx+0x58]',0x180008FF1:'divsd xmm0,qword ptr [rcx]',
0x180009016:'mulsd xmm0,qword ptr [rbx+0xc0]',0x180009023:'divsd xmm0,qword ptr [rbx+0xc8]'
}
RANGES=[(0x18000cf30,0x18000d010),(0x180011b60,0x180011cf0),
(0x18000bb80,0x18000bd1a),(0x18000b0e0,0x18000ba00),
(0x180014810,0x180014990),(0x180008fd0,0x180009031)]
def check(dll):
 data=dll.read_bytes()
 assert hashlib.sha256(data).hexdigest()==SHA,'wrong original DLL'
 asm={}
 for lo,hi in RANGES:
  txt=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
      f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in txt.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if m:asm[int(m[1],16)]=' '.join(m[2].lower().split())
 for va,needle in PINS.items():
  assert needle in asm.get(va,''),(hex(va),needle,asm.get(va))
 pe=struct.unpack_from('<I',data,0x3c)[0]
 opt=pe+24;base=struct.unpack_from('<Q',data,opt+24)[0]
 sec=opt+struct.unpack_from('<H',data,pe+20)[0]
 sections=[struct.unpack_from('<4I',data,sec+40*i+8)
   for i in range(struct.unpack_from('<H',data,pe+6)[0])]
 def f64(va):
  rva=va-base
  for _,start,size,offset in sections:
   if start<=rva and rva+8<=start+size:
    return struct.unpack_from('<d',data,offset+rva-start)[0]
  raise ValueError(hex(va))
 constants={'attenuation':f64(0x18024cc68),'quality':f64(0x18024ca38),
  'half_cutoff':f64(0x18024c880),'window_beta':f64(0x18024cc20),
  'pi':f64(0x18024ca80)}
 assert constants=={'attenuation':180.15,'quality':2.0,'half_cutoff':0.5,
   'window_beta':125.0,'pi':3.141592653589793}
 return {'stage':'Stage24B','status':'STATIC_VERIFIED_NO_NEW_NATIVE_RUN',
  'dll_sha256':SHA,'instruction_pins':len(PINS),'source_defaults':constants,
  'filter_fields_at_0x18000BD12':{'+0x00':'cutoff f64','+0x08':'quality f64',
      '+0x10':'attenuation f64','+0x20':'gain f64'},
  'generator_fields_at_0x18000B981':{'+0x00':'pre-floor G f64','+0x0c':'G u32',
   '+0x18':'theta f64','+0x20':'gamma f64','+0x58':'index u32',
   '+0xc0':'beta f64','+0xc8':'I0(beta) f64','+0xd0':'offset f64'},
  'cutoff_branch':'0x180011C83: 0.5 if rate2 > rate1, else 0.5*rate2/rate1',
  'limitation':'Original Windows DLL was not executed; no runtime coefficient/argument parity.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dll',required=True,type=Path)
 print(json.dumps(check(p.parse_args().dll),indent=2))
