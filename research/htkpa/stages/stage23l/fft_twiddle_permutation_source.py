"""HTKPA Stage23L: FFT twiddle permutation and complex rotations.

Static original-DLL proof, not a Windows DLL execution or end-to-end FFT,
FIR, resampler or NAM->CLO parity. Uses objdump and stdlib only.
"""
import argparse
import hashlib
import math
import random
import re
import subprocess
from pathlib import Path

DLL_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
PINS = {
  0x180009548:"mov r12d,ebp", 0x18000954f:"sar r12d,0x2",
  0x18000956a:"sar ebx,1", 0x180009574:"call 0x18017e0f8",
  0x180009592:"divsd xmm8,xmm6",0x1800095f0:"call 0x18017e116",
  0x1800095fb:"call 0x18017e15e",
  0x180009600:"movsd qword ptr [rsi+rbx*8+0x8],xmm0",
  0x18000960a:"movsd qword ptr [rsi+rbx*8],xmm7",
  0x180009644:"mov ecx,r12d",0x180009647:"call 0x1800099f0",
  0x180009773:"call 0x1800099f0",0x180009780:"call 0x180009ef0",
  0x180009a00:"mov dword ptr [rdx],0x0",0x180009a06:"mov ebp,0x1",
  0x180009a22:"sar r9d,1",0x180009a40:"mov ecx,dword ptr [rdx]",
  0x180009a46:"add ecx,r9d",
  0x180009a49:"mov dword ptr [rbx+rdx*1-0x4],ecx",
  0x180009a52:"add r10d,r10d",0x180009a5d:"cmp eax,r9d",
  0x180009c00:"cmp rcx,rbp",0x180009e1f:"cmp esi,ebp",
  0x180009e31:"mov r9d,dword ptr [rdi]",
  0x180009e38:"mov r8d,dword ptr [r15]",
  0x180009e3b:"add r9d,r14d",0x180009e3e:"add r8d,r10d",
  0x180009e4b:"mov rax,qword ptr [r11+rcx*8]",
  0x180009e56:"movups xmm2,xmmword ptr [r11+rdx*8]",
  0x180009e71:"movups xmmword ptr [r11+rcx*8],xmm2",
  0x180009e79:"movups xmm2,xmmword ptr [r11+rdx*8]",
  0x180009e94:"movups xmmword ptr [r11+rcx*8],xmm2",
  0x18000a8a2:"mov rax,r11",
  0x18000a9a8:"movsd xmm10,qword ptr [r13+0x10]",
  0x18000aab1:"mulsd xmm0,xmm10",
  0x18000aab6:"mulsd xmm2,xmm10",
  0x18000aad0:"mulsd xmm0,xmm10",
  0x18000aad5:"mulsd xmm7,xmm10",
  0x18000ab50:"movsd xmm12,qword ptr [r13+0x18]",
  0x18000ab5a:"movsd xmm13,qword ptr [r9+0x10]",
  0x18000ab64:"movsd xmm14,qword ptr [r9+0x18]",
  0x18000ab7b:"movsd xmm11,qword ptr [r13+0x0]",
  0x18000ab76:"addsd xmm10,xmm12",
  0x18000ab85:"mulsd xmm10,xmm13",
  0x18000ab8a:"mulsd xmm0,xmm14",
  0x18000ab8f:"subsd xmm10,xmm14",
  0x18000ab94:"subsd xmm15,xmm0",
  0x18000ac7f:"mulsd xmm0,xmm4",
  0x18000ac8b:"mulsd xmm1,xmm5",
  0x18000ac98:"subsd xmm1,xmm0",
  0x18000aca0:"mulsd xmm0,xmm5",
  0x18000acac:"addsd xmm2,xmm0",
  0x18000acb0:"mulsd xmm1,xmm4",
  0x18000acb8:"mulsd xmm0,xmm3",
  0x18000acc9:"subsd xmm1,xmm0",
  0x18000acd1:"mulsd xmm0,xmm3",
  0x18000acde:"addsd xmm2,xmm0",
  0x18000ace2:"mulsd xmm1,xmm7",
  0x18000acea:"mulsd xmm0,xmm9",
  0x18000acfd:"subsd xmm1,xmm0",
  0x18000ad05:"mulsd xmm0,xmm7",
  0x18000ad0f:"addsd xmm2,xmm0",
}
RANGES = [(0x180009540,0x180009655),(0x180009765,0x180009790),
          (0x1800099f0,0x180009a70),(0x180009bf0,0x180009c25),
          (0x180009e1f,0x180009ea0),(0x18000a850,0x18000ad18)]

def verify_source(dll: Path) -> int:
    assert hashlib.sha256(dll.read_bytes()).hexdigest()==DLL_SHA,"wrong original DLL"
    asm={}
    for lo,hi in RANGES:
        raw=subprocess.check_output(["objdump","-d","-M","intel","--no-show-raw-insn",
               f"--start-address={lo:#x}",f"--stop-address={hi:#x}",str(dll)],text=True)
        for line in raw.splitlines():
            match=re.match(r"\s*(180[0-9a-f]+):\s+(.+)",line)
            if match:
                asm[int(match[1],16)]=" ".join(match[2].lower().split())
    for va,pred in PINS.items():
        assert pred in asm.get(va,""),(hex(va),pred,asm.get(va))
    return len(PINS)

def twiddle_anchors(N: int=4096):
    """Proven initial integer offsets and first two complex-pair exchanges.

    The entire 0x99F0 swap network remains to be independently reconstructed.
    """
    assert N==4096
    n=N//4  # call at 0x9644 after 0x954f
    perm=[0]
    for offset in (n//2,n//4):
        perm += [v+offset for v in perm]
    assert perm[:3]==[0,512,256]
    swaps=((2,512),(4,256))
    theta=math.atan(1.0)/(n//2)
    return {"permutation_prefix":perm[:4],"first_pair_exchanges":swaps,
            "phase_step":theta,
            "w45":(math.cos(512*theta),math.sin(512*theta)),
            "w22_5":(math.cos(256*theta),math.sin(256*theta))}

def native_rotations():
    a=twiddle_anchors()
    c45,s45=a["w45"]
    c22,s22=a["w22_5"]
    # 0xAB76-AB94 reconstruct the third complex twiddle.
    s67=2.0*s45*c22-s22
    c67=c22-2.0*s45*s22
    return [(c45,s45),(c22,s22),(c67,s67)]

def mul_native(z: complex,c: float,s: float)->complex:
    """The ordered mulsd/subsd/addsd combination (no FMA)."""
    return complex(z.real*c-z.imag*s,z.imag*c+z.real*s)

def mathematical_checks():
    a=twiddle_anchors()
    assert a["first_pair_exchanges"]==((2,512),(4,256))
    phases=(math.pi/4,math.pi/8,3*math.pi/8)
    twiddles=native_rotations()
    for (c,s),phase in zip(twiddles,phases):
        assert abs(c-math.cos(phase))<8e-16
        assert abs(s-math.sin(phase))<8e-16
        assert abs(c*c+s*s-1.0)<2e-15
    rng=random.Random(0x23)
    for _ in range(1000):
        z=complex(rng.uniform(-2,2),rng.uniform(-2,2))
        for c,s in twiddles:
            assert abs(mul_native(z,c,s)-z*complex(c,s))<1e-15
    return a,twiddles

if __name__=="__main__":
    import json
    p=argparse.ArgumentParser()
    p.add_argument("--dll",required=True,type=Path)
    args=p.parse_args()
    pin_count=verify_source(args.dll)
    anchors,twiddles=mathematical_checks()
    print(json.dumps({"dll_sha256":DLL_SHA,"verified_address_pins":pin_count,
           "permutation_prefix":anchors["permutation_prefix"],
           "first_pair_exchanges":anchors["first_pair_exchanges"],
           "ordinary_radix4_angles":["pi/4","pi/8","3pi/8"],
           "synthetic_complex_products":3000,
           "scope":"only first pinned swaps and three rotations; full FFT parity open"},
           indent=2))
