"""HTKPA 5868USB.dll: source-pinned FIR -> polynomial initial-phase checkpoint.

For normal successful 44100 -> 48000 resampling, the filter descriptor at
+0x40 is initialized to zero and the 2:1 FIR constructor receives a zero
phase. Its fractional output phase is zero, passed to interpolator +0x1018.
This does NOT prove sample alignment, latency, full resampler or CLO parity.
Static PE only: never invokes the vendor DLL. SHA-pinned.
"""
import argparse
import hashlib
import math
import re
import subprocess
from pathlib import Path

DLL_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
PINS = {
    0x18000b238: "xor esi,esi",
    0x18000b99d: "mov qword ptr [rdi+0x40],rsi",
    0x18000bcce: "call qword ptr",
    0x18000bd12: "call 0x18000b0e0",
    0x18000bd6d: "mov rax,rbx",
    0x180011c1e: "mov r13d,0x2",
    0x180011c51: "mov r14d,0x1",
    0x180011c5a: "xorps xmm10,xmm10",
    0x180011c67: "comisd xmm0,xmm8",
    0x180011c6c: "jbe 0x180011f24",
    0x180011c83: "comisd xmm9,xmm8",
    0x180011c8a: "movaps xmm6,xmm11",
    0x180011ce8: "movsd qword ptr [rsp+0x20],xmm10",
    0x180011cef: "mov r9d,0x1",
    0x180011cf5: "mov r8d,r13d",
    0x180011cfe: "call 0x18000bdf0",
    0x18000bf11: "mulsd xmm2,qword ptr [rsp+0x50]",
    0x18000bf17: "addsd xmm2,qword ptr [r10+0x40]",
    0x18000bf33: "cvttsd2si ecx,xmm2",
    0x18000bf4f: "subsd xmm2,xmm0",
    0x18000bf53: "divsd xmm2,xmm1",
    0x18000bf57: "movsd qword ptr [rdi+0x48],xmm2",
    0x180011d63: "movsd xmm7,qword ptr [rax+0x48]",
    0x180011d7c: "ja 0x180011f04",
    0x180011f1f: "jmp 0x180012170",
    0x1800121c9: "movsd qword ptr [rsi+0x1018],xmm7",
    0x1800121fb: "movsd xmm0,qword ptr [rsi+0x1018]",
    0x180012207: "movups xmmword ptr [rsi+0x1038],xmm0",
}
RANGES = [
    (0x18000b230,0x18000b245),
    (0x18000b990,0x18000b9a6),
    (0x18000bcc9,0x18000bcdc),
    (0x18000bd09,0x18000bd1b),
    (0x18000bd60,0x18000bd72),
    (0x18000bf00,0x18000bf60),
    (0x180011c10,0x180011d06),
    (0x180011d50,0x180011d85),
    (0x180011f04,0x180011f24),
    (0x1800121c0,0x180012211),
]


def verify(dll: Path):
    assert hashlib.sha256(dll.read_bytes()).hexdigest() == DLL_SHA
    asm = {}
    for lo, hi in RANGES:
        listing = subprocess.check_output(
            ["objdump", "-d", "-M", "intel", "--no-show-raw-insn",
             f"--start-address={lo}", f"--stop-address={hi}", str(dll)], text=True)
        for line in listing.splitlines():
            m = re.match(r"\s*(180[0-9a-f]+):\s+(.+)", line)
            if m:
                asm[int(m[1], 16)] = " ".join(m[2].lower().split())
    for address, fragment in PINS.items():
        assert fragment in asm.get(address, ""), (hex(address), fragment, asm.get(address))
    # This is the shortest successful normal 44100 -> 48000 branch:
    # 2*target > source, target > source, and 2*source > target.
    source_fs, target_fs = 44100.0, 48000.0
    assert 2*target_fs > source_fs and target_fs > source_fs
    assert 2*source_fs > target_fs
    # Input phase at 0x11c5a is 0.0; cache constructor sets +0x40 to 0.
    # 0xBDF0: x = up*initial_phase + filter_offset;
    # output phase = (x - trunc(x)) / down, written to FIR+0x48.
    up, down, initial_phase, filter_offset = 2, 1, 0.0, 0.0
    x = up*initial_phase + filter_offset
    phase = (x-math.trunc(x))/down
    assert phase == 0.0
    print(f"PASS: {len(PINS)} exact instruction-address pins, FIR phase = {phase}")
    print("OPEN: exact group delay/sample alignment, FIR taps, audio and gains.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", type=Path, required=True)
    verify(parser.parse_args().dll)
