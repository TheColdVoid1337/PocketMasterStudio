"""HTKPA Stage23K: original source-derived FFT radix-4 unity butterfly & stages.

No DLL execution, no native RAM parity, no whole FFT/resampler parity.
The 4096-double real-FFT buffer is dispatched through base 0xA370,
A850 strides 8,32,128,512 (in doubles), then radix-2 tail at 0xA0A0.
A850 first zero-twiddle branch equals a positive-exponent unnormalized
complex radix-4 butterfly on memory ordered [z0,z2,z1,z3].
"""
from __future__ import annotations
import argparse
import cmath
import hashlib
import math
import random
import re
import subprocess
import unittest
from pathlib import Path

DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PINS = {
 0x180009F0D:'cmp ecx,0x8',
 0x180009F15:'call 0x18000a370',
 0x180009F1A:'mov edx,0x8',
 0x180009F1F:'cmp ebx,0x20',
 0x180009F2C:'lea edi,[rdx+0x18]',
 0x180009F30:'mov r9,rbp',
 0x180009F33:'mov r8,rsi',
 0x180009F36:'mov ecx,ebx',
 0x180009F38:'call 0x18000a850',
 0x180009F3D:'mov edx,edi',
 0x180009F3F:'lea edi,[rdi*4+0x0]',
 0x180009F46:'cmp edi,ebx',
 0x180009F48:'jl 0x180009f30',
 0x180009F57:'lea eax,[rdx*4+0x0]',
 0x180009F5E:'cmp eax,ebx',
 0x180009F68:'jne 0x18000a0a0',
 0x18000A0D0:'movsd xmm4,qword ptr [rcx+r8*1]',
 0x18000A0D6:'movsd xmm3,qword ptr [rcx-0x8]',
 0x18000A0DE:'movsd xmm1,qword ptr [rcx+rdx*8]',
 0x18000A0E3:'addsd xmm0,xmm3',
 0x18000A0EA:'subsd xmm4,xmm3',
 0x18000A0EE:'subsd xmm2,qword ptr [rcx]',
 0x18000A0F2:'movsd qword ptr [rcx+r8*1],xmm0',
 0x18000A0F8:'addsd xmm1,qword ptr [rcx]',
 0x18000A0FC:'movsd qword ptr [rcx+rdx*8],xmm1',
 0x18000A101:'movsd qword ptr [rcx-0x8],xmm4',
 0x18000A106:'movsd qword ptr [rcx],xmm2',
 0x18000A8A5:'lea rcx,[r11*8+0x0]',
 0x18000A8AD:'shl rax,0x4',
 0x18000A8B4:'neg rdx',
 0x18000A8BF:'neg rbx',
 0x18000A8C2:'sub rdi,rcx',
 0x18000A8C5:'add rdx,rdx',
 0x18000A8C8:'lea r9,[rax+r8*1]',
 0x18000A8D2:'sub r8,rax',
 0x18000A8E0:'movsd xmm9,qword ptr [r9+rdx*8]',
 0x18000A8E6:'movsd xmm6,qword ptr [r9]',
 0x18000A8EF:'movsd xmm3,qword ptr [rcx+r9*1]',
 0x18000A8F5:'movsd xmm4,qword ptr [r9+0x8]',
 0x18000A906:'movsd xmm8,qword ptr [r8+r9*1]',
 0x18000A910:'addsd xmm7,qword ptr [r9+rbx*8]',
 0x18000A916:'subsd xmm9,qword ptr [r9+rbx*8]',
 0x18000A922:'subsd xmm4,qword ptr [rcx+r9*1+0x8]',
 0x18000A929:'movsd xmm5,qword ptr [rdi+r9*1]',
 0x18000A940:'addsd xmm0,xmm7',
 0x18000A944:'subsd xmm7,xmm3',
 0x18000A948:'addsd xmm1,xmm5',
 0x18000A94C:'subsd xmm5,xmm2',
 0x18000A950:'movsd qword ptr [r9+rdx*8],xmm0',
 0x18000A95A:'subsd xmm0,xmm4',
 0x18000A95E:'addsd xmm4,xmm9',
 0x18000A963:'movsd qword ptr [r8+r9*1],xmm1',
 0x18000A96C:'movsd qword ptr [r9],xmm7',
 0x18000A971:'addsd xmm1,xmm8',
 0x18000A976:'movsd qword ptr [r9+0x8],xmm5',
 0x18000A97C:'subsd xmm8,xmm6',
 0x18000A981:'movsd qword ptr [r9+rbx*8],xmm0',
 0x18000A987:'movsd qword ptr [rdi+r9*1],xmm1',
 0x18000A98D:'movsd qword ptr [rcx+r9*1],xmm4',
 0x18000A993:'movsd qword ptr [rcx+r9*1+0x8],xmm8',
}
RANGES=[(0x180009EF0,0x18000A120),(0x18000A850,0x18000A9A8)]


def inspect(dll:Path)->int:
    blob=dll.read_bytes()
    assert hashlib.sha256(blob).hexdigest()==DLL_SHA, 'wrong original DLL'
    disasm={}
    for lo,hi in RANGES:
        txt=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
            f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
        for line in txt.splitlines():
            m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
            if m:
                disasm[int(m[1],16)]=' '.join(m[2].lower().split())
    for addr,needle in PINS.items():
        assert needle in disasm.get(addr,''),(hex(addr),needle,disasm.get(addr))
    return len(PINS)


def dispatch(scalar_count:int):
    """Follow ECX/EDX/EDI control flow in 0x9EF0 for scalar double count."""
    if scalar_count<=32:
        raise ValueError('only 4096 normal branch covered by this checkpoint')
    current=8
    next_value=32
    radix4=[]
    while True:
        radix4.append(current)
        current=next_value
        next_value*=4
        if not next_value<scalar_count:
            break
    return {'scalar_doubles':scalar_count,'base_kernel':'0x18000a370',
            'radix4_A850_EDX_stride_doubles':radix4,
            'radix2_tail_A0A0':4*current!=scalar_count,
            'tail_EDX_stride_doubles':current}


def positive_radix4_memory_order(z0:complex,z2:complex,z1:complex,z3:complex):
    """Literal real/imag arithmetic of first A850 loop, for four complex inputs.

    Memory groups are [z0,z2,z1,z3]. Each group is 2 double scalars.
    No twiddle multiplications in this first special-case butterfly.
    """
    a_re=z0.real+z2.real; a_im=z0.imag+z2.imag
    b_re=z1.real+z3.real; b_im=z1.imag+z3.imag
    c_re=z0.real-z2.real; c_im=z0.imag-z2.imag
    d_re=z1.real-z3.real; d_im=z1.imag-z3.imag
    return [complex(a_re+b_re,a_im+b_im),
            complex(c_re-d_im,c_im+d_re),
            complex(a_re-b_re,a_im-b_im),
            complex(c_re+d_im,c_im-d_re)]


def final_radix2_pair(left:complex,right:complex):
    """Final 0xA0D0..0xA106: two halves at a 2048-double offset."""
    return complex(left.real+right.real,left.imag+right.imag),complex(
        left.real-right.real,left.imag-right.imag)


def independent_positive_dft(z):
    return [sum(z[j]*cmath.exp(2j*math.pi*j*k/len(z)) for j in range(len(z)))
            for k in range(len(z))]


class Checks(unittest.TestCase):
    def test_4096_route(self):
        self.assertEqual(dispatch(4096),{'scalar_doubles':4096,
            'base_kernel':'0x18000a370',
            'radix4_A850_EDX_stride_doubles':[8,32,128,512],
            'radix2_tail_A0A0':True,'tail_EDX_stride_doubles':2048})

    def test_final_radix2_pair(self):
        rnd=random.Random(4096)
        for _ in range(128):
            left=complex(rnd.uniform(-1,1),rnd.uniform(-1,1))
            right=complex(rnd.uniform(-1,1),rnd.uniform(-1,1))
            got=final_radix2_pair(left,right)
            expected=independent_positive_dft([left,right])
            for a,b in zip(got,expected):
                self.assertLess(abs(a-b),1e-15)

    def test_radix4_against_independent_dft(self):
        rnd=random.Random(238)
        inputs=[[complex(float(j==i),0) for j in range(4)] for i in range(4)]
        inputs += [[complex(rnd.uniform(-2,2),rnd.uniform(-2,2)) for _ in range(4)]
                   for _ in range(128)]
        for z in inputs:
            actual=positive_radix4_memory_order(z[0],z[2],z[1],z[3])
            expected=independent_positive_dft(z)
            for a,b in zip(actual,expected):
                self.assertLess(abs(a-b),2e-13)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True)
    args=p.parse_args()
    print('Source pins:',inspect(args.dll))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    print('Dispatcher:',dispatch(4096))
    raise SystemExit(0 if result.wasSuccessful() else 1)
