"""Source-pinned float32-to-PCM24 writer path; never executes the DLL."""
import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path

DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINS={
 0x18008dd5c:'0x1802496a8', 0x18008e1aa:'cmp eax,0x18',
 0x1801409e0:'movss xmm0,dword ptr [rdx]', 0x1801409e8:'cvtps2pd xmm0,xmm0',
 0x1801409eb:'comisd xmm7,xmm0', 0x1801409f1:'mov dword ptr [rcx],0x80000000',
 0x1801409f9:'comisd xmm0,xmm6', 0x1801409ff:'mov dword ptr [rcx],0x7fffffff',
 0x180140a07:'mulsd xmm0,xmm8', 0x180140a0c:'addsd xmm0,xmm9',
 0x180140a17:'mov eax,dword ptr [rsp+0x20]',
 0x18008e2f0:'mov r8d,dword ptr [rdx-0x4]', 0x18008e2fb:'sar r8d,0x8',
 0x18008e305:'mov byte ptr [rax],r8b', 0x18008e310:'mov byte ptr [rax+0x1],cl',
 0x18008e313:'mov byte ptr [rax+0x2],r8b'}
RANGES=[(0x18008dd50,0x18008dd70),(0x18008e190,0x18008e320),(0x1801409d0,0x180140a20)]

def pe_at(data,va,n):
 pe=struct.unpack_from('<I',data,0x3c)[0]; opt=pe+24; base=struct.unpack_from('<Q',data,opt+24)[0]
 for i in range(struct.unpack_from('<H',data,pe+6)[0]):
  off=opt+struct.unpack_from('<H',data,pe+20)[0]+40*i; _,rva,raw,fileoff=struct.unpack_from('<4I',data,off+8)
  if rva<=va-base and va-base+n<=rva+raw:return data[fileoff+va-base-rva:fileoff+va-base-rva+n]
 raise ValueError(hex(va))

def verify(dll):
 data=dll.read_bytes(); assert hashlib.sha256(data).hexdigest()==DLL_SHA
 asm={}
 for lo,hi in RANGES:
  for line in subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True).splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if m: asm[int(m[1],16)]=' '.join(m[2].lower().split())
 for a,x in PINS.items(): assert x in asm.get(a,''),(hex(a),asm.get(a))
 constants={hex(a):struct.unpack('<d',pe_at(data,a,8))[0] for a in (0x18024ced0,0x18024c918,0x18024cd50,0x18024cd90)}
 assert constants=={'0x18024ced0':-1.0,'0x18024c918':1.0,'0x18024cd50':2147483647.0,'0x18024cd90':6755399441055744.0}
 assert struct.unpack('<Q',pe_at(data,0x1802496b0,8))[0]==0x18008e0e0
 return {'dll_sha256':DLL_SHA,'instruction_pins':len(PINS),'constants':constants,'writer_vtable_slot_8':'0x18008e0e0'}

def i32_from_f32(value):
 x=struct.unpack('<f',struct.pack('<f',value))[0]
 if x<=-1.0:return -0x80000000
 if x>=1.0:return 0x7fffffff
 bits=struct.unpack('<Q',struct.pack('<d',float(x)*2147483647.0+6755399441055744.0))[0]
 return struct.unpack('<i',struct.pack('<I',bits&0xffffffff))[0]
def pcm24(value):
 q=i32_from_f32(value)>>8
 return bytes((q&255,(q>>8)&255,(q>>16)&255))
def tests():
 assert i32_from_f32(-1)==-0x80000000 and i32_from_f32(1)==0x7fffffff
 assert i32_from_f32(0)==0 and i32_from_f32(.5)==0x40000000 and i32_from_f32(-.5)==-0x40000000
 assert pcm24(-1)==b'\x00\x00\x80' and pcm24(1)==b'\xff\xff\x7f' and pcm24(0)==b'\0\0\0'
 return 7
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 result={'stage':'23X','status':'SOURCE_PINNED_PCM24_WRITER','source':verify(a.dll),'tests':tests(),'scope':'writer quantization and packing only; no DLL execution, WAV write, reload or resampler parity'}
 a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
