"""HTKPA Stage23H: source-pinned first FIR half-length G for 44100 -> 48000.

Original DLL only, static PE instruction and constant inspection. No native
execution or evidence of complete coefficient, resampler or four-gain parity.
The chosen empirical branch and CRT approximations have an integer rounding
margin of > 0.07, so ordinary platform libm differences cannot change G.
"""
import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
from pathlib import Path

DLL_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
PINS = {
  0x18000cf3c:"0x18024cc68",
  0x18000cf44:"0x18024ca38",
  0x18000cfe0:"movsd qword ptr [rsp+0x28],xmm6",
  0x18000cfe6:"movsd qword ptr [rsp+0x20],xmm7",
  0x18000cff3:"call 0x180011b60",
  0x180011c83:"comisd xmm9,xmm8",
  0x180011c8a:"movaps xmm6,xmm11",
  0x180011ce3:"call 0x18000bb80",
  0x18000b13d:"mulsd xmm10,qword ptr",
  0x18000b15f:"comisd xmm10,xmm12",
  0x18000b1dc:"comisd xmm0,qword ptr",
  0x18000b1e6:"0x18024ce78",
  0x18000b217:"addsd xmm1,qword ptr",
  0x18000b21f:"mulsd xmm1,qword ptr",
  0x18000b227:"divsd xmm1,qword ptr",
  0x18000b233:"call 0x18017e134",
  0x18000b24f:"cmp eax,ecx",
  0x18000b279:"comisd xmm10,xmm8",
  0x18000b29b:"movsx eax,byte ptr",
  0x18000b2ac:"divsd xmm0,qword ptr",
  0x18000b2b4:"subsd xmm7,xmm0",
  0x18000b2c3:"call 0x18017e116",
  0x18000b2e7:"call 0x18017e116",
  0x18000b335:"call 0x18017e128",
  0x18000b36c:"comisd xmm0,xmm9",
  0x18000b371:"jb 0x18000b616",
  0x18000b616:"comisd xmm10,xmm12",
  0x18000b6b8:"comisd xmm10,xmm8",
  0x18000b75e:"movaps xmm0,xmm2",
  0x18000b79b:"call 0x18017e116",
  0x18000b7c2:"call 0x18017e0f8",
  0x18000b7de:"call 0x18017e140",
  0x18000b81c:"mulsd xmm8,xmm12",
  0x18000b826:"divsd xmm8,qword ptr [rdi]",
  0x18000b84b:"call 0x18017e134",
  0x18000b850:"cvttsd2si eax,xmm0",
  0x18000b85e:"lea r15d,[rax+rax*1]",
  0x18000b862:"lea ebx,[r15+0x1]",
  0x18000b8ef:"mov dword ptr [rdi+0x48],ebx",
}
RANGES = [
  (0x18000cf30,0x18000cf50),(0x18000cfd0,0x18000cffa),
  (0x180011c75,0x180011cf0),(0x18000b130,0x18000b855),
  (0x18000b85e,0x18000b867),(0x18000b8eb,0x18000b8f3),
]

def raw_at(data, va, length):
  pe=struct.unpack_from("<I",data,0x3c)[0]
  assert data[:2]==b"MZ" and data[pe:pe+4]==b"PE\x00\x00"
  opt=pe+24
  base=struct.unpack_from("<Q",data,opt+24)[0]
  sec=opt+struct.unpack_from("<H",data,pe+20)[0]
  count=struct.unpack_from("<H",data,pe+6)[0]
  rva=va-base
  for i in range(count):
    _size,vaddr,rawsize,offset=struct.unpack_from("<4I",data,sec+40*i+8)
    if vaddr<=rva and rva+length<=vaddr+rawsize:
      return data[offset+rva-vaddr:offset+rva-vaddr+length]
  raise ValueError("PE VA not file backed: "+hex(va))

def verify_original(dll):
  data=dll.read_bytes()
  assert hashlib.sha256(data).hexdigest()==DLL_SHA, "incorrect vendor DLL"
  ins={}
  for lo,hi in RANGES:
    raw=subprocess.check_output(["objdump","-d","-M","intel","--no-show-raw-insn",
        f"--start-address={lo:#x}",f"--stop-address={hi:#x}",str(dll)],text=True)
    for line in raw.splitlines():
      m=re.match(r"\s*(180[0-9a-f]+):\s+(.+)",line)
      if m:ins[int(m[1],16)]=" ".join(m[2].lower().split())
  for addr,needle in PINS.items():
    assert needle in ins.get(addr,""),(hex(addr),needle,ins.get(addr))
  imports=subprocess.check_output(["objdump","-p",str(dll)],text=True)
  for iat,name in [("0018b9b0","floor"),("0018ba70","cos"),
                   ("0018b9a0","exp"),("0018b9d0","atan"),("0018b9e8","log")]:
    assert re.search(r"\b"+iat+r"\s+.*\b"+name+r"\b",imports)
  return data

def reproduce(data):
  c=lambda a:struct.unpack("<d",raw_at(data,a,8))[0]
  cutoff=c(0x18024c880)
  quality=c(0x18024ca38)
  attenuation=c(0x18024cc68)
  assert (cutoff,quality,attenuation)==(0.5,2.0,180.15)
  transition=quality*c(0x18024c6c8)
  assert transition<c(0x18024c7a0)<c(0x18024c7f8)
  assert attenuation>=c(0x18024cc18)
  a=-attenuation+c(0x18024ce78)
  position=c(0x18024c880)-(a+c(0x18024cbb8))*c(0x18024cc90)/c(0x18024cc60)
  index=min(0x108,max(0,math.floor(position)))
  lookup=struct.unpack("<b",raw_at(data,0x180244d50+index,1))[0]
  a-=lookup/c(0x18024cc70)
  e=math.exp(a*c(0x18024c6b0))
  y=math.exp(a*c(0x18024c7b0)+c(0x18024c898))*(e*c(0x18024c5e0))+a*a*c(0x18024c570)
  y-=c(0x18024c6b8)
  y-=a*c(0x18024c610)
  y-=math.exp(a*c(0x18024c770))*c(0x18024c790)
  y-=(a*c(0x18024c5b8))*e
  assert y>c(0x18024c760),"unexpected branch at 0xB36C"
  y2=y*y
  width=(y*c(0x18024c990)-y2*c(0x18024cab8)
       -math.cos(y*c(0x18024c998)-y*y2*c(0x18024caf8))*(a*c(0x18024c7d8)))/transition
  correction=(math.atan(y*c(0x18024cbd0))*transition*c(0x18024c780)
       +math.log(y)*transition*c(0x18024c750)
       +transition*c(0x18024c8b8)-y*c(0x18024c768)*transition)
  g_float=width*c(0x18024c7f8)/cutoff
  g=math.floor(g_float)
  assert (index,lookup,g)==(197,49,708),(index,lookup,g)
  size=2*(1<<(2*g).bit_length())
  return {"dll_sha256":DLL_SHA,"instruction_pins":len(PINS),
    "upstream_params":{"cutoff":cutoff,"quality":quality,"attenuation":attenuation},
    "selected_branch":"B616 -> B6B8 -> B75E",
    "transition":transition,"lookup_index":index,"lookup_value":lookup,
    "attenuation_parameter_after_lookup":a,
    "intermediate_y":y,"width":width,"phase_correction":correction,
    "G_before_floor":g_float,"G":g,"filter_length":2*g+1,
    "fir_working_span":size,"initial_fill":size-2*g,"initial_skip":size-g,
    "floor_margin":min(g_float-g,math.ceil(g_float)-g_float),
    "parity":"static source-derived parameters only; no native DLL execution"}

if __name__=="__main__":
  p=argparse.ArgumentParser()
  p.add_argument("--dll",required=True,type=Path)
  result=reproduce(verify_original(p.parse_args().dll))
  print(json.dumps(result,indent=2,sort_keys=True))
