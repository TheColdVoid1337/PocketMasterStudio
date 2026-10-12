#!/usr/bin/env python3
"""Read-only, SHA-pinned analysis of HTKPA Pre-FIR candidate generation.

Does not load or execute Sonicake code. This is neither a vendor converter nor a
claim of recovering the whole fitting algorithm. Only machine-code-backed
operations are modeled here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
import struct
import subprocess
from pathlib import Path

SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
# Exact VA : (descriptive ID, substring that must be in disassembly at that VA)
PINS = {
  0x1800bf07c: ('main_pre_context', '0x24408'),
  0x1800bf083: ('main_pre_stack', '[rsp+0x58]'),
  0x1800bf070: ('main_post_context_reference', '0x24410'),
  0x1800bf077: ('main_post_stack_reference', '[rsp+0x60]'),
  0x1800bf0c9: ('main_call_fitter', 'call   0x1800bb210'),
  0x1800bb4d9: ('first_frequency_mapping', 'call   0x1800b7670'),
  0x1800bb4f8: ('second_frequency_mapping', 'call   0x1800b7670'),
  0x1800bb812: ('third_frequency_mapping', 'call   0x1800b7670'),
  0x1800bb46e: ('candidate_power', 'call   0x18017e158'),
  0x1800bb479: ('candidate_high_clamp', 'movaps xmm0,xmm11'),
  0x1800bb48c: ('candidate_low_clamp', '0x3e4ccccd'),
  0x1800bb4be: ('iteration_decay', 'mulss  xmm12'),
  0x1800bb575: ('candidate_multiply', 'mulps  xmm1,xmm0'),
  0x1800bb6e1: ('candidate_divide', 'divps  xmm1,xmm0'),
  0x1800bb7e3: ('candidate_filter_conditioner', 'call   0x1800b6220'),
  0x1800bb817: ('candidate_pre_input_length', '0x20ed4'),
  0x1800bb81e: ('candidate_pre_output_length', 'mov    r9d,r8d'),
  0x1800bb821: ('candidate_live_pre_pointer', '[rsp+0x1f8]'),
  0x1800bb831: ('candidate_destination_arg', '[rsp+0x20]'),
  0x1800bb836: ('candidate_pre_synth_call', 'call   0x1800b68f0'),
  0x1800b7bbb: ('mapping_gaussian_1', 'call   0x1800b7e10'),
  0x1800b7bf8: ('mapping_interpolation_1', 'call   0x1800b5d00'),
  0x1800b7c12: ('mapping_gaussian_2', 'call   0x1800b7e10'),
  0x1800b7c4b: ('mapping_interpolation_2', 'call   0x1800b5d00'),
  0x1800b7c8c: ('mapping_interpolation_3', 'call   0x1800b5d00'),
  0x1800b691f: ('synth_double_support', '[rsi+rsi*1]'),
  0x1800b6925: ('synth_support_minus_two', '[rax-0x2]'),
  0x1800b695b: ('synth_copy_first_half', 'call   0x1800a505a'),
  0x1800b69a0: ('synth_reflected_sample_load', 'mov    eax,DWORD PTR [rdx+0x8]'),
  0x1800b6a16: ('synth_transform_one', 'call   0x1800b72e0'),
  0x1800b6a50: ('synth_generate_basis', 'call   0x1800b52e0'),
  0x1800b6a66: ('synth_complex_operation', 'call   0x1800b47f0'),
  0x1800b6b18: ('synth_full_energy_sqrt', 'call   0x18017e170'),
  0x1800b6b39: ('synth_copy_declared_output', 'call   0x1800a505a'),
  0x1800b6b9d: ('synth_mean', 'divss  xmm2,xmm0'),
  0x1800b6beb: ('synth_remove_mean', 'subps  xmm0,xmm3'),
  0x1800b6d07: ('synth_centered_energy_sqrt', 'call   0x18017e170'),
  0x1800b6d0e: ('synth_energy_scale', 'divss  xmm7,xmm0'),
  0x1800b6d52: ('synth_scale_output', 'mulps  xmm0,xmm2'),
  0x1800b6db8: ('synth_scale_output_tail', 'mulps  xmm0,xmm7'),
  0x1800b73b1: ('fft_helper_log_eps', '[rbp+rbx*4+0x0]'),
  0x1800b7450: ('fft_helper_interp', 'call   0x1800b5d00'),
  0x1800b748f: ('fft_helper_symmetric_reverse', '[r14+rax*4]'),
}


def disasm(dll: Path):
    out={}
    for lo, hi in [(0x1800b47f0,0x1800b4a50),(0x1800b68f0,0x1800b6e30),
                   (0x1800b72e0,0x1800b7660),(0x1800b7670,0x1800b7d90),
                   (0x1800bb200,0x1800bbc90),(0x1800bf040,0x1800bf0e0)]:
        p=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',
                          f'--start-address={lo:#x}', f'--stop-address={hi:#x}',str(dll)],
                         text=True,capture_output=True,check=True)
        for line in p.stdout.splitlines():
            m=re.match(r'\s*([0-9a-fA-F]+):\s*(.*)',line)
            if m: out[int(m.group(1),16)] = m.group(2).strip()
    return out


def reflect_edge_exclusive(a):
    """Proven finite-array assembly: [x0..xN-1, xN-2..x1]."""
    if len(a)<2: raise ValueError('N >= 2 required')
    return list(a)+list(a[-2:0:-1])


def restore_zero_dc_energy(transform_output, output_length):
    """Proven *final* Stage-11 normalization, NOT the missing spectral transform.

    The full-length transformed array has M elements, first output_length taps
    are kept, centered, and their L2 restored to the full M-element input norm.
    """
    if output_length<1 or output_length>len(transform_output): raise ValueError('bad length')
    target=math.sqrt(sum(float(x)**2 for x in transform_output))
    output=[float(x) for x in transform_output[:output_length]]
    mean=sum(output)/len(output)
    centered=[x-mean for x in output]
    norm=math.sqrt(sum(x*x for x in centered))
    if norm==0: raise ValueError('degenerate zero centered energy: DLL behavior not established')
    return [x*target/norm for x in centered]


def read_pre(clo: bytes):
    assert len(clo)==8840 and clo[:4]==b'VTSI'
    return struct.unpack_from('<128f',clo,136)


def caller_stack_arg_offset(callee_disp):
    """Rebase callee stack offset to caller stack offset: call/pushes/sub."""
    return callee_disp-(8 + 8*8 + 0x158)


def run_tests():
    assert caller_stack_arg_offset(0x1F8)==0x58  # Pre-FIR
    assert caller_stack_arg_offset(0x200)==0x60  # Post-FIR
    # Endpoint-excluding mirror: length is exactly 2*N-2.
    assert reflect_edge_exclusive([1,2,3,4])==[1,2,3,4,3,2]
    assert reflect_edge_exclusive([4,7])==[4,7]
    assert len(reflect_edge_exclusive(list(range(2048))))==4094
    for spec,L in [([1.,2.,5.,8.,3.,-2.],4), ([3.,1.,4.,1.,5.,9.],3),([-8.,-3.,-1.,2.,7.,9.],5)]:
        result=restore_zero_dc_energy(spec,L)
        assert abs(sum(result))<1e-12
        assert abs(math.sqrt(sum(x*x for x in result))-math.sqrt(sum(x*x for x in spec)))<1e-12
    # Symmetric input can have nonzero DC; output projection removes it.
    x=restore_zero_dc_energy([3,2,1,-1,-2,-3],4)
    assert abs(sum(x))<1e-12
    return 9


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dll',type=Path,required=True)
    ap.add_argument('--official-2203',type=Path)
    ap.add_argument('--official-sc20',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    b=a.dll.read_bytes()
    sha=hashlib.sha256(b).hexdigest()
    assert sha==SHA, 'Wrong DLL version; do not apply pinned instruction conclusions'
    asm=disasm(a.dll)
    proofs={}
    for va,(name,needle) in PINS.items():
        line=asm.get(va,'')
        assert needle in line,(hex(va),name,needle,line)
        proofs[name]={'va':f'0x{va:x}','assembly':line}
    cases={}
    for name,p in [('JCM800_2203',a.official_2203),('SC20_Full_Rig',a.official_sc20)]:
        if not p: continue
        t=read_pre(p.read_bytes())
        support=[x for x in t if x!=0]
        assert len(support)==117
        cases[name]={'official_pre_sum':sum(t),'official_pre_l2':math.sqrt(sum(x*x for x in t)),
                     'dc_sum_to_l2':abs(sum(t))/math.sqrt(sum(x*x for x in t)),
                     'nonzero_taps':len(support), 'note':'cross-check only; not an output of the DLL helper'}
    tests=run_tests()
    result={'stage':'11','dll_sha256':sha,'static_pins':len(proofs),
            'tests':tests,'machine_evidence':proofs,'official_check':cases,
            'limits':['No proprietary DLL executed','No complete Pre-FIR impulse response from NAM/WAV',
                     'Full frequency mapping / transform in b7670, b72e0 and b47f0 remains open',
                     'No exact pre/post coefficient recovery','No hardware CLO created']}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print('SHA verified; pins',len(proofs),'tests',tests)
    for k,v in cases.items():print(k,'pre sum',v['official_pre_sum'],'sum/L2',v['dc_sum_to_l2'])

if __name__=='__main__':main()
