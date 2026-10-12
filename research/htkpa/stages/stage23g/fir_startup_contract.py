"""Source-first FIR startup timing on original Sonicake 5868USB.dll.

READ ONLY. The 44.1k -> 48k path uses first-stage FIR up=2, down=1,
initial phase=0. Symbolically reconstructs the FIR constructor/reset fields
from the *actual* PE instructions and its exponent table. This does not
compute the real filter's half-length G or prove emitted sample alignment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

DLL_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
PINS = {
    # Filter builder: half-length G, odd kernel L=2G+1.
    0x18000B850: "cvttsd2si eax,xmm0",
    0x18000B85E: "lea r15d,[rax+rax*1]",
    0x18000B862: "lea ebx,[r15+0x1]",
    0x18000B8EF: "mov dword ptr [rdi+0x48],ebx",
    0x18000B942: "movsxd rax,r15d",
    0x18000B94E: "mov dword ptr [rdi+0x4c],ecx",
    0x18000B99A: "mov dword ptr [rdi+0x38],eax",
    0x18000B99D: "mov qword ptr [rdi+0x40],rsi",
    # Constructor: power-of-two up=2 branch; buffer fill and initial discard.
    0x18000BE3D: "mov ecx,dword ptr [rax+0x4c]",
    0x18000BE40: "mov eax,0x2",
    0x18000BE45: "shl eax,cl",
    0x18000BE47: "mov dword ptr [rdi+0x34],eax",
    0x18000BE4E: "movsxd r9,dword ptr [rdi+0x28]",
    0x18000BE93: "movsx eax,byte ptr [r9+r8*1]",
    0x18000BE98: "lea r11d,[rax-0x1]",
    0x18000BEAD: "shl eax,cl",
    0x18000BEB2: "cmp eax,r9d",
    0x18000BEB7: "mov eax,dword ptr [rdx+0x48]",
    0x18000BEBA: "dec eax",
    0x18000BEBD: "idiv r9d",
    0x18000BEC4: "imul r9d,eax",
    0x18000BEC8: "sub ecx,r9d",
    0x18000BEE1: "mov dword ptr [rdi+0x3c],eax",
    0x18000BEE7: "mov dword ptr [rdi+0x40],ecx",
    0x18000BEED: "mov edx,dword ptr [r10+0x38]",
    0x18000BF11: "mulsd xmm2,qword ptr [rsp+0x50]",
    0x18000BF17: "addsd xmm2,qword ptr [r10+0x40]",
    0x18000BF33: "cvttsd2si ecx,xmm2",
    0x18000BF3A: "add r10d,edx",
    0x18000BF3D: "mov dword ptr [rdi+0x44],r10d",
    0x18000BF57: "movsd qword ptr [rdi+0x48],xmm2",
    # Startup reset zeros history, initializes skip counter and buffer offset.
    0x18000C166: "movsxd r8,dword ptr [rcx+0x3c]",
    0x18000C177: "call 0x1800a504e",
    0x18000C17C: "cmp byte ptr [rbx+0x30],0x0",
    0x18000C182: "mov eax,dword ptr [rbx+0x44]",
    0x18000C185: "mov dword ptr [rbx+0x84],eax",
    0x18000C1F5: "mov eax,dword ptr [rbx+0x40]",
    0x18000C1F8: "sub eax,dword ptr [rbx+0x58]",
    0x18000C1FB: "mov dword ptr [rbx+0x80],eax",
    # Streaming: zero insertion for 2x; actual filter; startup skip and swap.
    0x18000C232: "mov r15d,dword ptr [rcx+0x28]",
    0x18000C23F: "imul r15d,r8d",
    0x18000C280: "mov ebp,dword ptr [rsi+0x80]",
    0x18000C296: "cmp r15d,ebp",
    0x18000C350: "mov rax,qword ptr [r14]",
    0x18000C355: "mov qword ptr [r8],rax",
    0x18000C35C: "mov qword ptr [r8+0x8],r11",
    0x18000C360: "mov qword ptr [r8+0x10],r11",
    0x18000C684: "call 0x1800094f0",
    0x18000C6D2: "mov eax,dword ptr [rsi+0x84]",
    0x18000C6E2: "mov dword ptr [rsi+0x84],eax",
    0x18000C6F0: "mov dword ptr [rsi+0x84],0x0",
    0x18000C85D: "mov qword ptr [rsi+0x70],r9",
    0x18000C861: "mov qword ptr [rsi+0x78],rax",
    # 2:1 at 44.1 ->48 and phase handed to polynomial stage.
    0x180011C1E: "mov r13d,0x2",
    0x180011C5A: "xorps xmm10,xmm10",
    0x180011CE8: "movsd qword ptr [rsp+0x20],xmm10",
    0x180011CEF: "mov r9d,0x1",
    0x180011CF5: "mov r8d,r13d",
    0x180011CFE: "call 0x18000bdf0",
    0x180011D63: "movsd xmm7,qword ptr [rax+0x48]",
    0x1800121C9: "movsd qword ptr [rsi+0x1018],xmm7",
}
RANGES = [
    (0x18000B840,0x18000B870),(0x18000B8E0,0x18000B8FF),
    (0x18000B930,0x18000B965),(0x18000B985,0x18000B9AB),
    (0x18000BE30,0x18000BF64),(0x18000C160,0x18000C21E),
    (0x18000C220,0x18000C3A0),(0x18000C670,0x18000C700),
    (0x18000C840,0x18000C870),(0x180011C10,0x180011D06),
    (0x180011D58,0x180011D69),(0x1800121B8,0x1800121E1),
]

def original_exponent_table(pe: bytes) -> tuple[int, ...]:
    """PE-file backed bytes at original image VA 0x180245280, not runtime RAM."""
    header = struct.unpack_from("<I", pe, 0x3c)[0]
    optional = header + 24
    base = struct.unpack_from("<Q", pe, optional+24)[0]
    count = struct.unpack_from("<H", pe, header+6)[0]
    sections = optional+struct.unpack_from("<H", pe, header+20)[0]
    rva = 0x180245280-base
    for i in range(count):
        off = sections+40*i
        virtual_size, va, length, offset = struct.unpack_from("<4I", pe, off+8)
        if va <= rva and rva+256 <= va+length:
            return struct.unpack_from("<256b", pe, offset+rva-va)
    raise ValueError("missing exponent table")

def startup(g: int) -> dict:
    """Source-derived values for filter half length g, FIRST FIR ONLY."""
    if not 1 <= g <= 100_000:
        raise ValueError("synthetic filter G out of range")
    length = 2*g+1
    exponent = (length-1).bit_length()
    q = 1 << exponent
    processing_span = 2*q             # FIR+0x34
    initial_fill = processing_span-2*g # FIR+0x40 -> reset+0x80
    initial_skip = processing_span-g   # FIR+0x44 -> reset+0x84
    assert initial_skip == initial_fill+g
    return {"G":g,"filter_length":length,"exponent":exponent,
            "processing_span":processing_span,
            "initial_fill":initial_fill,
            "initial_skip":initial_skip,"fractional_phase":0.0}

def verify(dll: Path) -> dict:
    data = dll.read_bytes()
    assert hashlib.sha256(data).hexdigest() == DLL_SHA
    table = original_exponent_table(data)
    assert all(table[n]==n.bit_length() for n in range(1,256))
    assert table[0] == 1 and table[2] == 2
    disasm = {}
    for lo, hi in RANGES:
        listing = subprocess.check_output(["objdump","-d","-M","intel",
            "--no-show-raw-insn",f"--start-address={lo:#x}",
            f"--stop-address={hi:#x}",str(dll)],text=True)
        for line in listing.splitlines():
            m = re.match(r"\s*(180[0-9a-f]+):\s+(.+)",line)
            if m:
                disasm[int(m[1],16)] = " ".join(m[2].lower().split())
    for va, text in PINS.items():
        assert text in disasm.get(va,""),(hex(va),text,disasm.get(va))
    return {"dll_sha256":DLL_SHA,"address_pins":len(PINS),
            "exponent_table_bytes":256,
            "mode":"first stage 44100 -> 48000, up=2 down=1",
            "synthetic_examples":[startup(g) for g in (1,7,100,256,1023)],
            "not_yet_proven":["actual G for the 180.15 filter quality",
                "first emitted sample temporal alignment",
                "exact flush/streaming parity and complete DSP"]}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--dll",type=Path,required=True)
    print(json.dumps(verify(p.parse_args().dll),indent=2))
