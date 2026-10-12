"""HTKPA Stage23C source-pinned FIR+fractional-polynomial-stage investigation.

Never loads or runs proprietary DLL. The DLL is read as PE bytes and disassembled
only for string-address evidence; scalar formulas are reconstructed separately.
This verifier is NOT a complete FIR generator, resampler, or real CLO fitter.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess
from pathlib import Path
from pe_bytes import dll_pe_at, DLL_SHA

PINS={
 # First native FIR stage and its sizing vtable.
 0x180011C67:'comisd xmm0,xmm8',
 0x180011C6C:'jbe    0x180011f24',
 0x180011C83:'comisd xmm9,xmm8',
 0x180011C90:'movaps xmm6,xmm9',
 0x180011C94:'mulsd  xmm6,xmm11',
 0x180011C99:'divsd  xmm6,xmm8',
 0x180011CE3:'call   0x18000bb80',
 0x180011CEF:'mov    r9d,0x1',
 0x180011CF5:'mov    r8d,r13d',
 0x180011CFE:'call   0x18000bdf0',
 0x180011D26:'[rbx+0x48],0x1',
 0x180011D37:'call   qword ptr [rax+0x20]',
 0x180011D6E:'movaps xmm0,xmm8',
 0x180011D72:'addsd  xmm0,xmm8',
 0x180011D77:'comisd xmm0,xmm9',
 0x180011D7C:'ja     0x180011f04',
 0x180011F1F:'jmp    0x180012170',
 0x180012170:'mov    ecx,0x1048',
 0x1800121AE:'0x180245170',
 0x1800121B8:'[rsi+0x1008],xmm1',
 0x1800121C0:'[rsi+0x1010],xmm9',
 0x1800121C9:'[rsi+0x1018],xmm7',
 0x1800121D8:'[rsi+0x1028],0xf5',
 0x18001222A:'[rbx+0x50],rsi',
 0x180012237:'call   qword ptr [rax+0x20]',
 0x18000BE15:'[rcx],rax',
 0x18000BE2A:'[rcx+0x28],r8d',
 0x18000BE35:'[rcx+0x2c],r9d',
 0x18000BF21:'[rdi+0x58],r14d',
 0x18000C140:'mov    eax,dword ptr [rcx+0x28]',
 0x18000C143:'imul   eax,edx',
 0x18000C146:'dec    eax',
 0x18000C148:'[rcx+0x58]',
 0x18000C14B:'[rcx+0x2c]',
 0x18000C14F:'idiv   dword ptr [rcx+0x2c]',
 # Final 24-sample polynomial interpolator; its capacity and phase-index logic.
 0x180013D90:'sub    rsp,0x28',
 0x180013D9C:'[rcx+0x1010]',
 0x180013DA4:'[rcx+0x1008]',
 0x180013DAC:'call   0x18017e10a',
 0x180013DB5:'inc    eax',
 0x1800135F1:'0x1802c7560',
 0x18001360C:'0x18024ccb8',
 0x180013763:'mulsd  xmm5,xmm6',
 0x180013767:'cvttsd2si eax,xmm5',
 0x18001376F:'lea    eax,[rax+rax*8]',
 0x180013772:'shl    eax,0x3',
 0x180013775:'movsxd rcx,eax',
 0x18001377B:'subsd  xmm5,xmm0',
 0x180013799:'[r9+rcx*8+0x8]',
 0x1800137D0:'[r10+rax*8+0x8]',
 0x180013C19:'[r10+rax*8+0xc0]',
 0x180013C38:'movsd  qword ptr [r12],xmm3',
 0x180013C59:'[r10+0x1008]',
 0x180013C62:'[r10+0x1010]',
 0x180013C95:'add    eax,ecx',
 0x180013CA9:'subsd  xmm5,xmm0',
 0x180013CAD:'[r10+0x1038],xmm5',
  # Phase/coefficient table producer in PE .text, initialized at runtime.
 0x1800163DF:'add    rdi,0x240',
 0x1800163FF:'0x1802c7560',
 0x180016444:'[rax+0x900]',
 0x18001644C:'[rax+0x480]',
 0x1800164C9:'[rax],xmm8',
 0x180016533:'[rax+0x8],xmm2',
 0x180016582:'[rax+0x10],xmm9',
 0x180016782:'add    rax,0x60',
  # Separate direct filter-coefficient generation, includes true Kaiser/Bessel-like window.
 0x18000B9A1:'call   0x18000afa0',
 0x18000B9C0:'addsd  xmm7,qword ptr [rax]',
 0x18000B9E3:'divsd  xmm1,xmm7',
 0x18000BA02:'mulsd  xmm0,qword ptr [rdx+rcx*8]',
 0x1800148D0:'[rbx+0x40]',
 0x1800148F4:'movaps xmm0,xmm6',
 0x18001490B:'call   0x180008fd0',
 0x180008FD6:'[rcx+0x58]',
 0x180008FF1:'[rcx]',
 0x180008FF5:'[rcx+0xd0]',
 0x180009001:'subsd  xmm1,xmm0',
 0x180009011:'call   0x18017e16a',
 0x18000901E:'call   0x180008e90',
 0x180009023:'divsd  xmm0,qword ptr [rbx+0xc8]',
}
RANGES=[(0x18000B981,0x18000BA20),(0x180008FD0,0x180009031),
        (0x1800148D0,0x180014930),(0x18000BDF0,0x18000BF27),
        (0x18000C140,0x18000C153),(0x180011C5E,0x180011D82),
        (0x180011F04,0x180011F24),(0x180012170,0x180012242),
        (0x180013D90,0x180013DBC),(0x1800135C0,0x180013660),
        (0x180013760,0x1800137E0),(0x180013BB6,0x180013CD0),
        (0x1800163D5,0x180016411),(0x180016440,0x180016540),(0x180016578,0x180016590),
        (0x180016768,0x180016795)]

def inspect_dll(dll:Path)->dict:
    data=dll.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    assert actual==DLL_SHA,(actual,DLL_SHA)
    ins={}
    for start,stop in RANGES:
        out=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={start:#x}',f'--stop-address={stop:#x}',str(dll)],text=True)
        for line in out.splitlines():
            m=re.match(r'^\s*([0-9a-f]+):\s+(.*)$',line)
            if m:ins[int(m[1],16)]=m[2].strip().lower()
    for addr,needle in PINS.items():
        assert needle.lower() in ins.get(addr,''),f'{addr:#x}: expected {needle!r}; got {ins.get(addr)!r}'
    def ptr(addr):return struct.unpack('<Q',dll_pe_at(data,addr,8))[0]
    fir_v=[ptr(0x180244EA0+i*8) for i in range(7)]
    poly_v=[ptr(0x180245170+i*8) for i in range(7)]
    assert fir_v == [0x18000CC70,0x18000C100,0x18000C110,0x18000C120,0x18000C140,0x18000C160,0x18000C220]
    assert poly_v == [0x180014320,0x180011AC0,0x180011B50,0x180013DC0,0x180013D90,0x180013D30,0x1800135C0]
    interp_bins=struct.unpack('<d',dll_pe_at(data,0x18024CCB8,8))[0]
    assert interp_bins==673.0
    assert 'ceil' in subprocess.check_output(['objdump','-p',str(dll)],text=True).split('0018ba30')[1][:50]
    try:
        dll_pe_at(data,0x1802C7560,8)
        table_backed=True
    except ValueError:
        table_backed=False
    assert not table_backed,'Phase polynomial table should be initialized in memory, not read as static PE bytes'
    return {
        'sha256':actual,'native_instruction_pins':len(PINS),
        'fir_vtable':list(map(hex,fir_v)),'poly_vtable':list(map(hex,poly_v)),
        'polynomial_phase_subdivisions':int(interp_bins),'samples_per_phase':24,
        'poly_coeffs_per_sample':3,'phase_stride_bytes':24*3*8,
        'runtime_generated_table_base':'0x1802C7560','table_stored_in_original_pe':table_backed,
        'table_producer':'0x1800163FF / 0x180016440..0x18001687B',
        'fir_coefficient_assembly':'0x180014810 oscillator + 0x180008FD0 radial/Bessel window + 0x18000B9E3 sum normalization',
        'native_address_pin_details':{f'{p:#x}':ins[p] for p in sorted(PINS)},
    }

def capacity_contract(input_count:int,source_fs:float,target_fs:float)->dict:
    """Reproduces only source-confirmed *capacity methods* for one-FIR-stage branch.
    First-stage ratio p=2,q=1, phase=0, then ceil(N*target/(2*source))+1.
    This is not the number of *actually written* samples nor audio parity.
    """
    assert input_count>=0 and source_fs>0 and target_fs>0
    assert source_fs!=target_fs and target_fs*2>source_fs
    fir_capacity=(2*input_count-1+0+1)//1
    fractional_capacity=math.ceil(fir_capacity*target_fs/(2*source_fs))+1
    return {'source_fs':source_fs,'target_fs':target_fs,'input_frames':input_count,
            'fir_up_factor':2,'fir_down_factor':1,
            'fir_capacity':fir_capacity,
            'fractional_stage_capacity':fractional_capacity,
            'nominal_target_frames':input_count*target_fs/source_fs,
            'caveat':'Capacity methods; runtime output count, padding and alignment not proven'}

def radial_kaiser_window_baseline(index:int,radius:float,shift:float,beta:float)->float:
    """Independent synthetic mathematical analogue of 0x8FD0 (SciPy optional).
    Native Bessel helper 0x8E90 has its own approximation; not bit parity.
    """
    from scipy.special import i0
    t=index/radius+shift
    return 0.0 if abs(t)>1 else float(i0(beta*math.sqrt(1-t*t))/i0(beta))

def synthetic_tests():
    checks=0
    x=capacity_contract(3_087_000,44100,48000);assert x['fir_capacity']==6_174_000;checks+=1
    assert x['fractional_stage_capacity']==3_360_001;checks+=1
    y=capacity_contract(3_360_000,48000,44100);assert y['fir_capacity']==6_720_000;checks+=1
    assert y['fractional_stage_capacity']==3_087_001;checks+=1
    assert x['fractional_stage_capacity']-1==3_360_000;checks+=1
    assert math.isclose(radial_kaiser_window_baseline(0,10,0,3),1.0);checks+=1
    assert radial_kaiser_window_baseline(11,10,0,3)==0;checks+=1
    assert radial_kaiser_window_baseline(5,10,0,3)<1;checks+=1
    assert (673*24*3*8)==387648;checks+=1
    assert (24*3*8)==576;checks+=1
    return checks

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dll',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ns=ap.parse_args()
    o={'stage':'23C source checkpoint','status':'FIR_PLUS_DYNAMIC_POLYNOMIAL_STAGE_PROVEN_NO_NATIVE_AUDIO_PARITY',
       'source':inspect_dll(ns.dll),'synthetic_math_checks_passed':synthetic_tests(),
       'capacity_example_input44100_target48000':capacity_contract(3_087_000,44100,48000),
       'capacity_example_input48000_target44100':capacity_contract(3_360_000,48000,44100),
       'open':['native Kaiser approximant and exact synthesis from 0xB0E0',
               'runtime generation of phase polynomial table and precise 24-tap interpolation parity',
               'metadata provenance, mode and branch-specific WAV sample rate, scaling',
               'actual two fit float32 buffers, detrend, onset, independent four-gain parity for both Marshall models']}
    ns.out.parent.mkdir(parents=True,exist_ok=True)
    ns.out.write_text(json.dumps(o,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
    print(f"Stage23C: verified {o['source']['native_instruction_pins']} machine pins, 2 PE vtables (14 function pointers), 673.0f64 constant; {o['synthetic_math_checks_passed']} synthetic checks")
    print('Strict real-Marshal 4 gains = NOT_COMPUTED; no DLL execution, no CLO generation.')
if __name__=='__main__':main()
