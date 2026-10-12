"""Source-pinned interpolation-table second pass for Sonicake HTKPA DLL.

Scope: static PE evidence, native 8-neighbor -> 3 polynomial coefficients,
phase/table geometry, and synthetic polynomial invariants. Does NOT generate
original 24-tap kernels or reproduce the complete resampler.
"""
from __future__ import annotations

import argparse
import hashlib
import math
import re
import struct
import subprocess
import unittest
from pathlib import Path

DLL_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
TABLE = 0x1802C7560
PHASES = 673
TAPS = 24
BYTES_PER_TAP = 3 * 8
BYTES_PER_PHASE = TAPS * BYTES_PER_TAP
RAW_PHASES = 681  # generated for esi from 0x2a4 (676) through -4 inclusive
OUTPUT_PHASES = 674  # 673 indices plus one guard row; final 8-point window uses row 680

# Each position is pinned to the instruction in the original DLL (VA, fragment).
PINS = {
    0x18001609B: "0x1802c7590",
    0x1800160B5: "mov esi,0x2a4",
    0x180016110: "movd xmm6,esi",
    0x18001611B: "divsd xmm6,xmm8",
    0x180016192: "call 0x180016a00",
    0x1800163DF: "add rdi,0x240",
    0x1800163E6: "cmp esi,0xfffffffc",
    0x1800163FF: "0x1802c7560",
    0x18001640F: "0x180326198",
    0x180016440: "movsd xmm4,qword ptr [rax]",
    0x180016444: "movsd xmm3,qword ptr [rax+0x900]",
    0x180016458: "movsd xmm7,qword ptr [rax+0x240]",
    0x180016465: "movsd xmm6,qword ptr [rax+0xb40]",
    0x18001647D: "movsd xmm8,qword ptr [rax+0x6c0]",
    0x180016486: "subsd xmm2,xmm6",
    0x18001649E: "movaps xmm1,xmm5",
    0x1800164A6: "subsd xmm1,xmm4",
    0x1800164BA: "mulsd xmm2,xmm12",
    0x1800164BF: "mulsd xmm0,xmm13",
    0x1800164C9: "movsd qword ptr [rax],xmm8",
    0x1800164D7: "addsd xmm2,xmm0",
    0x180016504: "addsd xmm2,xmm1",
    0x180016521: "divsd xmm2,xmm11",
    0x180016533: "movsd qword ptr [rax+0x8],xmm2",
    0x180016578: "divsd xmm9,xmm11",
    0x180016582: "movsd qword ptr [rax+0x10],xmm9",
    0x180016782: "add rax,0x60",
    0x18001678F: "0x1803261e0",
    0x180013763: "mulsd xmm5,xmm6",
    0x180013767: "cvttsd2si eax,xmm5",
    0x18001376F: "lea eax,[rax+rax*8]",
    0x180013772: "shl eax,0x3",
    0x18001377B: "subsd xmm5,xmm0",
    0x1800137AE: "mulsd xmm4,xmm5",
    0x1800137B2: "addsd xmm3,qword ptr [r9+rcx*8]",
    0x1800137C2: "addsd xmm3,xmm0",
}

# These numeric constants belong to the native second-pass stencil.
CONSTANTS = {
    0x18024CB58: 16.0, 0x18024CBE0: 61.0,
    0x18024CA70: 3.0, 0x18024CBF8: 76.0,
    0x18024CC10: 106.0, 0x18024CB30: 10.0,
    0x18024CAE0: 6.0, 0x18024CB88: 29.0,
    0x18024CC58: 167.0, 0x18024CCB8: 673.0,
    0x18024CB38: 12.0,
}


def pe_bytes_at(data: bytes, va: int, length: int) -> bytes:
    if data[:2] != b"MZ":
        raise ValueError("not PE")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe+4] != b"PE\0\0":
        raise ValueError("not PE")
    sections = struct.unpack_from("<H", data, pe+6)[0]
    opt = pe+24
    imagebase = struct.unpack_from("<Q", data, opt+24)[0]
    shdr = opt+struct.unpack_from("<H", data, pe+20)[0]
    rva = va-imagebase
    for i in range(sections):
        start = shdr+i*40
        _, vaddr, rawsize, rawptr = struct.unpack_from("<4I", data, start+8)
        if vaddr <= rva and rva+length <= vaddr+rawsize:
            offset = rawptr + rva-vaddr
            return data[offset:offset+length]
    raise ValueError(f"no file-backed PE data for {va:#x}")


def verify_dll(dll: Path) -> None:
    data = dll.read_bytes()
    assert hashlib.sha256(data).hexdigest() == DLL_SHA, "wrong original DLL"
    for va, expected in CONSTANTS.items():
        assert struct.unpack("<d", pe_bytes_at(data, va, 8))[0] == expected, hex(va)
    chunks = [(0x180016080, 0x1800161A0), (0x1800163D0, 0x180016610),
              (0x180016760, 0x1800167A0), (0x180013760, 0x1800137D0)]
    asm = {}
    for start, end in chunks:
        result = subprocess.check_output(["objdump", "-d", "-M", "intel", "--no-show-raw-insn",
                                          f"--start-address={start}", f"--stop-address={end}", str(dll)], text=True)
        for row in result.splitlines():
            m = re.match(r"\s*([0-9a-f]+):\s+(.+)", row)
            if m:
                asm[int(m[1], 16)] = " ".join(m[2].lower().split())
    for va, fragment in PINS.items():
        assert fragment in asm.get(va, ""), (hex(va), fragment, asm.get(va))


def coefficients(x: tuple[float, ...]) -> tuple[float, float, float]:
    """One tap of 8 consecutive raw phase rows; source arithmetic ordering.

    x0..x7 are consecutive rows separated by 0x240 bytes for a fixed tap.
    The output row is in-place at row x0, indexed by x3's raw phase.
    """
    if len(x) != 8:
        raise ValueError("need eight raw phase rows")
    x0, x1, x2, x3, x4, x5, x6, x7 = x
    b = ((x1 - x5)*16.0 + (x4 - x2)*61.0 + (x6 - x0)*3.0) / 76.0
    c = ((x2+x4)*106.0 + x6*10.0 + x0*6.0 - x7*3.0
         - (x1+x5)*29.0 - x3*167.0) / 76.0
    return x3, b, c


def phase_coordinate(phase: float) -> tuple[int, float]:
    """Only the ordinary 0 <= phase < 1 domain of the native sampler."""
    if not 0.0 <= phase < 1.0 or not math.isfinite(phase):
        raise ValueError("phase outside proven ordinary domain")
    scaled = phase * 673.0
    index = math.trunc(scaled)
    return index, scaled-float(index)


def polynomial_at(coeffs: tuple[float, float, float], residual: float) -> float:
    a, b, c = coeffs
    return a + residual*b + residual*residual*c


class StencilChecks(unittest.TestCase):
    def test_phase_generator_shape(self):
        self.assertEqual(list(range(676, -5, -1))[-1], -4)
        self.assertEqual(len(range(676, -5, -1)), RAW_PHASES)
        self.assertEqual(OUTPUT_PHASES*TAPS*BYTES_PER_TAP, 0x1803261E0-TABLE)
        self.assertEqual((RAW_PHASES-OUTPUT_PHASES), 7)
        self.assertEqual(BYTES_PER_PHASE, 0x240)

    def test_polynomial_invariants(self):
        # For degree <=2, stencil recovers x3, local first derivative, quadratic term.
        for a, b, c in [(1,0,0), (2,1,0), (4,-3,2)]:
            row = tuple(a+b*k+c*k*k for k in range(8))
            A, B, C = coefficients(row)
            self.assertAlmostEqual(A, a+3*b+9*c, places=12)
            self.assertAlmostEqual(B, b+6*c, places=12)
            self.assertAlmostEqual(C, c, places=12)

    def test_phase_sample_addressing(self):
        for phase, index, fraction in [(0.0,0,0.0), (0.5,336,0.5), (672/673,672,0.0)]:
            n, r=phase_coordinate(phase)
            self.assertEqual(n,index)
            self.assertAlmostEqual(r,fraction,places=10)
            self.assertLess(n,PHASES)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--dll', type=Path, required=True)
    args=p.parse_args()
    verify_dll(args.dll)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(StencilChecks))
    print(f"Native phase-table stencil: {len(PINS)} pins, {len(CONSTANTS)} constants; tests={'PASS' if result.wasSuccessful() else 'FAIL'}")
    raise SystemExit(0 if result.wasSuccessful() else 1)
