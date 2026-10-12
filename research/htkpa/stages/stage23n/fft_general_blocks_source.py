"""Stage23N: source-execute the 255 general base-FFT groups in Sonicake DLL.

Read-only PE + objdump. Low f64 SSE lane interpreter and independent DFT4 oracle.
Does NOT run DLL, verify native Windows CRT twiddle bits, later FFT stages,
FFT output, streaming resampler or NAM-to-CLO gains.
"""
from __future__ import annotations
import argparse
import cmath
import hashlib
import json
import math
import random
import re
import struct
import subprocess
from pathlib import Path

DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
GENERAL_BEGIN, GENERAL_END = 0x18000A550, 0x18000A7F9
PIN = {
  0x1800095f0:'call 0x18017e116',  # cos
  0x1800095fb:'call 0x18017e15e',  # sin
  0x180009600:'movsd qword ptr [rsi+rbx*8+0x8],xmm0',
  0x18000960a:'movsd qword ptr [rsi+rbx*8],xmm7',
  0x180009647:'call 0x1800099f0',
  0x180009a22:'sar r9d,1',
  0x180009a46:'add ecx,r9d',
  0x180009a49:'mov dword ptr [rbx+rdx*1-0x4],ecx',
  0x18000a520:'add ecx,0xffffffef',
  0x18000a528:'add rdx,0xa0',
  0x18000a535:'shr ecx,0x4',
  0x18000a53e:'inc ecx',
  0x18000a550:'movsd xmm11,qword ptr [r8+0x18]',
  0x18000a556:'add r8,0x20',
  0x18000a55a:'movsd xmm14,qword ptr [r9+0x18]',
  0x18000a560:'add r9,0x10',
  0x18000a577:'movsd xmm10,qword ptr [r8-0x10]',
  0x18000a580:'movsd xmm15,qword ptr [r9]',
  0x18000a601:'movsd qword ptr [rdx-0x20],xmm0',
  0x18000a634:'movsd qword ptr [rdx],xmm1',
  0x18000a6a0:'addsd xmm13,xmm15',
  0x18000a6b8:'movsd xmm10,qword ptr [r8]',
  0x18000a6bd:'movsd xmm11,qword ptr [r8+0x8]',
  0x18000a745:'movsd qword ptr [rdx+0x28],xmm1',
  0x18000a77c:'xorps xmm1,xmmword ptr [rip+0x242e6d]',
  0x18000a79e:'movsd qword ptr [rdx+0x40],xmm1',
  0x18000a7f3:'movsd qword ptr [rdx+0x58],xmm12',
  0x18000a7f9:'sub rdx,0xffffffffffffff80',
  0x18000a801:'jne 0x18000a550',
}
RANGES = ((0x1800095e0,0x180009650),(0x180009a18,0x180009a52),
          (0x18000a510,0x18000a545),(GENERAL_BEGIN,0x18000a810))
LINE=re.compile(r'^\s*(180[0-9a-f]+):\s+([a-z]+)\s+(.+?)(?:\s+#.*)?$')
MEM=re.compile(r'(?:qword|xmmword) ptr \[(rdx|r8|r9|rip)([+\-]0x[0-9a-f]+)?\]')

def pe_at(blob,va,count):
    pe=struct.unpack_from('<I',blob,0x3c)[0]
    assert blob[:2]==b'MZ' and blob[pe:pe+4]==b'PE\x00\x00'
    optional=pe+24
    rva=va-struct.unpack_from('<Q',blob,optional+24)[0]
    sections=optional+struct.unpack_from('<H',blob,pe+20)[0]
    for i in range(struct.unpack_from('<H',blob,pe+6)[0]):
        _,vaddr,raw_size,offset=struct.unpack_from('<4I',blob,sections+40*i+8)
        if vaddr<=rva and rva+count<=vaddr+raw_size:
            return blob[offset+rva-vaddr:offset+rva-vaddr+count]
    raise ValueError(hex(va))

def disassemble(dll):
    data=dll.read_bytes()
    assert hashlib.sha256(data).hexdigest()==DLL_SHA
    asm={}
    for lo,hi in RANGES:
        raw=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
            f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
        for line in raw.splitlines():
            m=LINE.match(line)
            if m:asm[int(m[1],16)]=(m[2],' '.join(m[3].lower().split()))
    for va,fragment in PIN.items():
        assert fragment in ' '.join(asm.get(va,('',''))),(hex(va),fragment,asm.get(va))
    instructions={a:v for a,v in asm.items() if GENERAL_BEGIN<=a<GENERAL_END}
    assert len(instructions)==147,len(instructions)
    sign_mask=struct.unpack('<Q',pe_at(data,0x18024D5F0,8))[0]
    assert sign_mask==0x8000000000000000
    return instructions,sign_mask

def reversed_ten_bits(x):
    assert 0<=x<1024
    return int(f'{x:010b}'[::-1],2)

def twiddles():
    step=math.atan(1.0)/512.0  # original atan(1) / (1024/2)
    return [v for k in range(1024)
            for v in (math.cos(reversed_ten_bits(k)*step),
                      math.sin(reversed_ten_bits(k)*step))]

def execute_group(source,number,code,mask,table):
    """General block number=1..255; 8 complex numbers in 16 doubles."""
    assert 1<=number<=255 and len(source)==8
    memory=[float(q) for z in source for q in (z.real,z.imag)]
    regs={f'xmm{i}':0.0 for i in range(16)}
    rdx=32; r8=16+32*(number-1); r9=16*(number-1)
    scalar_ops=0
    def read(operand):
        if operand.startswith('xmm'):return regs[operand]
        m=MEM.fullmatch(operand)
        if not m:raise AssertionError(('read',operand))
        base,part=m.groups();delta=int(part,16) if part else 0
        if base=='rdx':return memory[(rdx+delta)//8]
        if base=='r8':return table[(r8+delta)//8]
        if base=='r9':return table[(r9+delta)//8]
        raise AssertionError(('source',operand))
    def write(operand,value):
        if operand.startswith('xmm'):regs[operand]=value;return
        m=MEM.fullmatch(operand)
        assert m and m.group(1)=='rdx',operand
        memory[(rdx+(int(m.group(2),16) if m.group(2) else 0))//8]=value
    for address,(op,args) in sorted(code.items()):
        if op=='add' and args=='r8,0x20':r8+=32;continue
        if op=='add' and args=='r9,0x10':r9+=16;continue
        dest,src=map(str.strip,args.split(',',1))
        if op=='xorps':
            assert address==0x18000A77C and dest=='xmm1' and 'rip+' in src
            bits=struct.unpack('<Q',struct.pack('<d',regs[dest]))[0]^mask
            regs[dest]=struct.unpack('<d',struct.pack('<Q',bits))[0]
            continue
        assert op in ('movsd','movaps','addsd','subsd','mulsd'),(hex(address),op)
        value=read(src)
        if op in ('movsd','movaps'):result=value
        elif op=='addsd':result=read(dest)+value
        elif op=='subsd':result=read(dest)-value
        else:result=read(dest)*value
        write(dest,result)
        scalar_ops+=1
    assert scalar_ops==144,scalar_ops
    return [complex(*memory[2*j:2*j+2]) for j in range(8)],scalar_ops

def independent_oracle(data,number):
    """Separate positive DFT4 formula; input memory is bit-reversed within each four."""
    angles=[reversed_ten_bits(2*number+s)*math.atan(1.0)/512.0 for s in (0,1)]
    out=[]
    for half in range(2):
        z=[data[4*half+j] for j in (0,2,1,3)]
        for k in range(4):
            dft=sum(z[t]*cmath.exp(2j*math.pi*t*k/4) for t in range(4))
            out.append(dft*cmath.exp(1j*k*angles[half]))
    return out

def check(dll):
    code,mask=disassemble(dll)
    table=twiddles()
    assert [reversed_ten_bits(k) for k in range(4)]==[0,512,256,768]
    rng=random.Random(0x23A550)
    maximum=0.0;cases=0
    for number in range(1,256):
        cases_for_block=[[complex(j==k,0) for j in range(8)] for k in range(8)]
        cases_for_block += [[complex(rng.uniform(-1,1),rng.uniform(-1,1)) for _ in range(8)] for _ in range(4)]
        for data in cases_for_block:
            got,ops=execute_group(data,number,code,mask,table)
            expected=independent_oracle(data,number)
            maximum=max(maximum,max(abs(a-b) for a,b in zip(got,expected)))
            cases+=1
    assert maximum<1e-12,maximum
    return {'verified_instruction_pins':len(PIN),'decoded_general_instructions':len(code),
            'low_f64_scalar_sse_operations_per_block':ops,'general_blocks':255,
            'oracle_cases':cases,'max_abs_difference':maximum,
            'fft_twiddle_pair_bit_reverse_bits':10,
            'original_sign_mask_hex':hex(mask),
            'status':'general base FFT blocks source-emulated; no full FFT or vendor RAM parity'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True)
    print(json.dumps(check(p.parse_args().dll),indent=2))
