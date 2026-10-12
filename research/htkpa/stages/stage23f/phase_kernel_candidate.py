"""Source-derived first pass of Sonicake HTKPA's 673-bin/24-tap phase table.

This implements the visible Kaiser/Bessel approximation, window^shape sinc,
normalization, and second-pass 8-neighbor quadratic interpolation. It has not
been compared with original DLL RAM, Windows CRT results or real DI output.
Do not label the resulting coefficients native-bit-identical.
"""
from __future__ import annotations

import argparse
import math
import re
import struct
import subprocess
import unittest
from pathlib import Path

from phase_table_stencil import (
    RAW_PHASES, OUTPUT_PHASES, TAPS, coefficients, pe_bytes_at, verify_dll,
)

# Table at 0x1802451b0, indexed by (ceil(radius)-3)*16 = 9*16 for radius 12.
RADIUS = 12.0
BETA = 12.55262798
SHAPE = 1.51553897
PARAMETER_TABLE = 0x1802451B0

I0_CONSTANTS = {
    0x18024CA90: 3.75,
    0x18024C678: 0.0045813,
    0x18024C738: 0.0360768,
    0x18024C808: 0.2659732,
    0x18024C9B0: 1.2067492,
    0x18024CA78: 3.0899424,
    0x18024CA88: 3.5156229,
    0x18024C660: 0.00392377,
    0x18024C700: 0.01647633,
    0x18024C720: 0.02635537,
    0x18024C710: 0.02057706,
    0x18024C6C0: 0.00916281,
    0x18024C630: 0.00157565,
    0x18024C648: 0.00225319,
    0x18024C6F0: 0.01328592,
    0x18024C838: 0.39894228,
}
PINS = {
    0x180008eac: "0x18024ca90",
    0x180008eb5: "comisd xmm8,xmm7",
    0x180008ec1: "mulsd xmm1,xmm1",
    0x180008f31: "call 0x18017e128",  # exp(double)
    0x180008f3c: "call 0x18017e16a",  # sqrt(double)
    0x180008fd6: "mov eax,dword ptr [rcx+0x58]",
    0x180008ff1: "divsd xmm0,qword ptr [rcx]",
    0x180008ff5: "addsd xmm0,qword ptr [rcx+0xd0]",
    0x180009011: "call 0x18017e16a",  # sqrt
    0x180009016: "mulsd xmm0,qword ptr [rbx+0xc0]",
    0x18000901e: "call 0x180008e90",
    0x180009023: "divsd xmm0,qword ptr [rbx+0xc8]",
    0x1800160a6: "0x1802451b0",
    0x1800160ad: "0x18024cb38",
    0x180016142: "movsxd rax,ecx",
    0x180016145: "sub rax,0x3",
    0x18001614c: "movsd xmm0,qword ptr [rbp+rax*8+0x0]",
    0x180016152: "movsd xmm1,qword ptr [rbp+rax*8+0x8]",
    0x180016167: "call 0x180008e90",
    0x18001616c: "divsd xmm6,xmm7",
    0x180016170: "0x180008fd0",
    0x180016192: "call 0x180016a00",
    0x1800161a0: "movaps xmm0,xmm1",
    0x1800161a3: "addsd xmm0,xmm9",
    0x18001624a: "divsd xmm2,xmm0",
    0x18001624e: "mulsd xmm1,xmm2",
    0x1800163df: "add rdi,0x240",
    0x180016a3a: "0x18024ca80",  # pi
    0x180016a4d: "call 0x18017e15e",  # sin(double)
    0x180016a67: "neg ebx",
    0x180016abf: "movsd xmm10,qword ptr [rdi+0x20]",
    0x180016c08: "call 0x18017e152",  # pow(double)
    0x180016c3a: "divsd xmm0,xmm9",  # divide by pi
}


def verify_source(dll: Path) -> None:
    verify_dll(dll)
    data = dll.read_bytes()
    assert struct.unpack('<dd', pe_bytes_at(data, PARAMETER_TABLE + 9*16, 16)) == (BETA, SHAPE)
    for address, expected in I0_CONSTANTS.items():
        assert struct.unpack('<d', pe_bytes_at(data, address, 8))[0] == expected, hex(address)
    ins = {}
    ranges = [
        (0x180008E90, 0x180009031),
        (0x180016080, 0x180016260),
        (0x1800163DF, 0x1800163F1),
        (0x180016A00, 0x180016ACF),
        (0x180016BE0, 0x180016C50),
    ]
    for lo, hi in ranges:
        raw = subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
            f'--start-address={lo}',f'--stop-address={hi}',str(dll)], text=True)
        for line in raw.splitlines():
            m = re.match(r'\s*([0-9a-f]+):\s+(.+)',line)
            if m:
                ins[int(m.group(1),16)]=' '.join(m.group(2).lower().split())
    for addr, expected in PINS.items():
        assert expected in ins.get(addr,''), (hex(addr),expected,ins.get(addr))


def bessel_i0_native_approx(x: float) -> float:
    """Native Numerical-Recipes-like two-branch Bessel I0 approximant."""
    ax=abs(float(x))
    if ax < 3.75:
        v=x/3.75
        y=v*v
        t=0.0045813
        for c in (0.0360768,0.2659732,1.2067492,3.0899424,3.5156229,1.0):
            t=t*y+c
        return t
    y=3.75/ax
    t=0.00392377
    for sign,c in ((-1,0.01647633),(1,0.02635537),(-1,0.02057706),
                   (1,0.00916281),(-1,0.00157565),(1,0.00225319),
                   (1,0.01328592),(1,0.39894228)):
        t=t*y+sign*c
    return t*(math.exp(ax)/math.sqrt(ax))


def raw_kernel(phase: float) -> tuple[float, ...]:
    """The source-derived ordinary phase/shape branch, k=-12..11."""
    sin_phase=math.sin(math.pi*phase)
    denominator=bessel_i0_native_approx(BETA)
    weights=[]
    for k in range(-12,12):
        u=k/12.0+phase/12.0
        rad=1.0-u*u
        window=(bessel_i0_native_approx(BETA*math.sqrt(rad))/denominator
                if rad>=0.0 else 0.0)
        shaped=math.pow(window,SHAPE)
        x=k+phase
        if abs(x) <= 1e-13:
            value=shaped
        else:
            value=(shaped*(sin_phase if k%2==0 else -sin_phase)/x)/math.pi
        weights.append(value)
    total=0.0
    for w in weights:
        total+=w  # native addsd loop is sequential, not compensated
    scale=1.0/total
    return tuple(w*scale for w in weights)


def candidate_coefficients():
    raw=[raw_kernel(i/673.0) for i in range(676,-5,-1)]
    assert len(raw)==RAW_PHASES
    return tuple(tuple(coefficients(tuple(raw[p+j][tap] for j in range(8)))
                       for tap in range(TAPS)) for p in range(OUTPUT_PHASES))


class CandidateTests(unittest.TestCase):
    def test_i0_approx_anchors(self):
        self.assertAlmostEqual(bessel_i0_native_approx(0),1)
        self.assertAlmostEqual(bessel_i0_native_approx(1),1.266065848,places=7)
        self.assertAlmostEqual(bessel_i0_native_approx(BETA),32180.53295,places=3)

    def test_normalization(self):
        for p in (676,673,340,1,0,-4):
            kern=raw_kernel(p/673.0)
            self.assertEqual(len(kern),24)
            self.assertAlmostEqual(sum(kern),1.0,places=12)

    def test_candidate_table_dc(self):
        table=candidate_coefficients()
        self.assertEqual((len(table),len(table[0]),len(table[0][0])),(674,24,3))
        for p in (0,1,336,672,673):
            sums=[sum(row[j] for row in table[p]) for j in range(3)]
            self.assertAlmostEqual(sums[0],1.0,places=12)
            self.assertAlmostEqual(sums[1],0.0,places=12)
            self.assertAlmostEqual(sums[2],0.0,places=12)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--dll',type=Path,required=True)
    args=ap.parse_args()
    verify_source(args.dll)
    tests=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CandidateTests))
    print(f'Native I0 / phase-kernel candidate: {len(PINS)} source pins; {len(I0_CONSTANTS)} I0 constants; {tests.testsRun} tests')
    raise SystemExit(0 if tests.wasSuccessful() else 1)
