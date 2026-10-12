"""Stage23M: source-first emulation of the 8-complex special base FFT block.

Original 5868USB.dll SHA pinned. The first 16 doubles processed by function
0x18000A370 encode two DFT4 transforms in [0,2,1,3] input order, with the
second DFT4 output multiplied by exp(+i*pi*k/4), k=0..3.

A restricted interpreter executes 83 original, disassembled SSE scalar ops in
their exact order. This does NOT emulate 255 subsequent general blocks, native
Windows CRT table values, the full FFT, audio conversion or four CLO gains.
No original DLL is ever loaded or executed.
"""
from __future__ import annotations
import argparse
import cmath
import hashlib
import math
import random
import re
import subprocess
from pathlib import Path

DLL_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
START, END = 0x18000A370, 0x18000A512
PINS = {
  0x18000A37A:"movsd xmm5,qword ptr [rdx+0x20]",
  0x18000A38A:"subsd xmm5,qword ptr [rdx+0x30]",
  0x18000A3CC:"addsd xmm6,qword ptr [rdx+0x18]",
  0x18000A3D1:"subsd xmm8,qword ptr [rdx+0x18]",
  0x18000A3FB:"movsd qword ptr [rdx+0x8],xmm1",
  0x18000A408:"movsd qword ptr [rdx+0x28],xmm6",
  0x18000A417:"movsd qword ptr [rdx],xmm0",
  0x18000A43B:"movsd xmm8,qword ptr [rdx+0x48]",
  0x18000A446:"movsd xmm9,qword ptr [rdx+0x40]",
  0x18000A483:"movsd xmm10,qword ptr [r8]",
  0x18000A4D5:"mulsd xmm0,xmm10",
  0x18000A4DA:"mulsd xmm2,xmm10",
  0x18000A4DF:"movsd qword ptr [rdx+0x50],xmm0",
  0x18000A4E4:"movsd qword ptr [rdx+0x58],xmm2",
  0x18000A4FE:"mulsd xmm0,xmm10",
  0x18000A503:"mulsd xmm7,xmm10",
  0x18000A508:"movsd qword ptr [rdx+0x70],xmm0",
  0x18000A50D:"movsd qword ptr [rdx+0x78],xmm7",
  0x18000A512:"cmp ecx,0x10",
  0x18000A515:"jle 0x18000a824",
  0x18000A520:"add ecx,0xffffffef",
  0x18000A528:"add rdx,0xa0",
  0x18000A535:"shr ecx,0x4",
  0x18000A53E:"inc ecx",
  0x18000A550:"movsd xmm11,qword ptr [r8+0x18]",
  0x18000A556:"add r8,0x20",
  0x18000A560:"add r9,0x10",
  0x18000A7F9:"sub rdx,0xffffffffffffff80",
  0x18000A7FD:"sub rcx,0x1",
  0x18000A801:"jne 0x18000a550",
}
MEM = re.compile(r"qword ptr \[(rdx|r8)(?:\+(0x[0-9a-f]+))?\]")
LINE = re.compile(r"^\s*([0-9a-f]+):\s+([a-z]+)\s+(.*?)\s*(?:#.*)?$")


def original_instructions(dll: Path):
    assert hashlib.sha256(dll.read_bytes()).hexdigest() == DLL_SHA
    text = subprocess.check_output([
        "objdump", "-d", "-M", "intel", "--no-show-raw-insn",
        f"--start-address={START:#x}", "--stop-address=0x18000a810",
        str(dll)], text=True)
    code = {}
    for line in text.splitlines():
        match = LINE.match(line)
        if match:
            code[int(match[1], 16)] = (match[2], " ".join(match[3].lower().split()))
    for addr, fragment in PINS.items():
        assert fragment in " ".join(code.get(addr, ("",""))), (hex(addr),fragment,code.get(addr))
    return code


def execute_first_block(doubles, code, cos45=math.cos(math.pi/4)):
    """Interpret only original first-block scalar SSE instructions, not the DLL.

    The original R8 pointer was advanced by 16 bytes before the [R8] load.
    Its value is cos(pi/4), mathematically; Windows CRT last bits not proven.
    """
    assert len(doubles) == 16
    mem = list(map(float,doubles))
    xmm = {f"xmm{i}":0.0 for i in range(16)}
    executed=0
    for addr in sorted(a for a in code if START<=a<END):
        op,args=code[addr]
        if op not in ("movsd","movaps","addsd","subsd","mulsd"):
            continue
        dst,src=map(str.strip,args.split(",",1))
        if "[rax" in args or "[rsp" in args or "xmmword" in args:
            continue
        def val(operand):
            if operand.startswith("xmm"):
                return xmm[operand]
            m=MEM.fullmatch(operand)
            if not m:
                raise AssertionError((hex(addr),operand))
            region,offset=m.groups()
            if region=="r8":
                assert offset is None and addr==0x18000A483
                return cos45
            index=int(offset or "0",16)//8
            assert 0<=index<16
            return mem[index]
        if dst.startswith("xmm"):
            v=val(src)
            if op.startswith("mov"):xmm[dst]=v
            elif op=="addsd":xmm[dst]+=v
            elif op=="subsd":xmm[dst]-=v
            else:xmm[dst]*=v
        else:
            m=MEM.fullmatch(dst)
            assert op=="movsd" and m and m.group(1)=="rdx"
            mem[int(m.group(2) or "0",16)//8]=val(src)
        executed+=1
    assert executed==83, executed
    return [complex(mem[2*i],mem[2*i+1]) for i in range(8)], executed


def independent_dft4(x):
    return [sum(x[j]*cmath.exp(2j*math.pi*j*k/4)
                for j in range(4)) for k in range(4)]


def synthetic_checks(code):
    rng=random.Random(0x230A370)
    tests=[[complex(j==k,0) for j in range(8)] for k in range(8)]
    tests += [[complex(rng.uniform(-1,1),rng.uniform(-1,1)) for _ in range(8)]
              for _ in range(2048)]
    max_err=0.0
    for signal in tests:
        permuted=[signal[i] for i in (0,2,1,3,4,6,5,7)]
        buf=[v for z in permuted for v in (z.real,z.imag)]
        got,_=execute_first_block(buf,code)
        expected=(independent_dft4(signal[:4])+
            [z*cmath.exp(1j*math.pi*k/4)
             for k,z in enumerate(independent_dft4(signal[4:]))])
        max_err=max(max_err,max(abs(a-b) for a,b in zip(got,expected)))
    assert max_err<2.0e-14,max_err
    # 4096 doubles / 16 per 8-complex base block; 1 special + 255 general.
    remaining=((4096-17)>>4)+1
    assert remaining==255 and (1+remaining)*16==4096
    return {"original_address_pins":len(PINS),"scalar_SSE_ops_first_block":83,
            "synthetic_inputs":len(tests),"maximum_abs_error":max_err,
            "first_block_ordinary_DFT4":True,
            "second_block_phases":"0, pi/4, pi/2, 3pi/4",
            "twiddle_dependent_general_blocks_not_yet_emulated":remaining,
            "full_native_FFT_parity":False}


if __name__=="__main__":
    import json
    p=argparse.ArgumentParser()
    p.add_argument("--dll",required=True,type=Path)
    result=synthetic_checks(original_instructions(p.parse_args().dll))
    print(json.dumps({"dll_sha256":DLL_SHA,**result},indent=2))
