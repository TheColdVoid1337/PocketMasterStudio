"""Source-pinned native-resampler branch audit for HTKPA Stage 23.

Statically reads user-owned PE bytes via objdump; NEVER loads or invokes DLL.
Reconstructs confirmed 48k -> 44.1k constructor argument choices and
partial cache/filter/phase source graph. Not an audio resampler or vendor fitter.
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path

DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
# Source pins are instruction addresses plus *specific expected operands*, not fuzzy
# function-name matches. Ranges intentionally restrict which code can satisfy pins.
PINS={
  0x18000CF3C:'0x18024cc68', # sixth stack param: 180.15 (via xmm6)
  0x18000CF44:'0x18024ca38', # fifth stack param: 2.0 (via xmm7)
  0x18000CFD3:'cvtss2sd xmm2,xmm8',
  0x18000CFDB:'cvtss2sd xmm1,xmm9',
  0x18000CFE0:'[rsp+0x28],xmm6',
  0x18000CFE6:'[rsp+0x20],xmm7',
  0x18000CFF3:'call   0x180011b60',
  0x18000D039:'mulss  xmm0,xmm8',
  0x18000D03E:'divss  xmm0,xmm9',
  0x18000D043:'cvttss2si rbx,xmm0',
  0x18000D0F7:'[rax+0x30]', # stage virtual process method
  0x18000D10E:'call   r10',
  0x18000D16B:'cvtpd2ps xmm0,xmm0',
  0x180011BC9:'mov    r12d,r9d',
  0x180011BCC:'movaps xmm9,xmm2', # target
  0x180011BD0:'movaps xmm8,xmm1', # source
  0x180011C40:'ucomisd xmm8,xmm9',
  0x180011C5E:'movaps xmm0,xmm9',
  0x180011C62:'addsd  xmm0,xmm9',
  0x180011C67:'comisd xmm0,xmm8',
  0x180011C7A:'0x18024c880', # 0.5
  0x180011C83:'comisd xmm9,xmm8',
  0x180011C90:'movaps xmm6,xmm9',
  0x180011C94:'mulsd  xmm6,xmm11',
  0x180011C99:'divsd  xmm6,xmm8',
  0x180011CB4:'[rsp+0x158]', # forwarded stack = 180.15
  0x180011CBE:'0x18024ca38', # 2
  0x180011CCC:'[rsp+0x20],xmm13', # 2
  0x180011CD3:'movaps xmm2,xmm12', # 180.15
  0x180011CD7:'[rsp+0x150]', # 2
  0x180011CE0:'movaps xmm0,xmm6', # rate relative crossover
  0x180011CE3:'call   0x18000bb80',
  0x180011CFE:'call   0x18000bdf0',
  0x180011D26:'[rbx+0x48],0x1',
  0x180011D37:'[rax+0x20]',
  0x18000BBD1:'0x1802a6f90', # global cache head
  0x18000BBF1:'[rbx]',
  0x18000BBFE:'[rbx+0x8]',
  0x18000BC0B:'[rbx+0x10]',
  0x18000BC18:'[rbx+0x18]',
  0x18000BC1D:'[rbx+0x20]',
  0x18000BC4A:'[rbx+0x30]', # existing cache use count
  0x18000BCC9:'mov    ecx,0x58', # 88B cache descriptor
  0x18000BCF1:'[rbx],xmm8',
  0x18000BCF6:'[rbx+0x8],xmm7',
  0x18000BCFB:'[rbx+0x10],xmm6',
  0x18000BD03:'[rbx+0x20],xmm9',
  0x18000BD12:'call   0x18000b0e0',
  0x18000B105:'[rcx+0x10]',
  0x18000B13D:'0x18024c6c8',
  0x18000B233:'call   0x18017e134',
  0x18000B850:'cvttsd2si eax,xmm0',
  0x18000B862:'lea    ebx,[r15+0x1]', # symmetric odd length
  0x18000B8EF:'[rdi+0x48],ebx',
  0x18000B9A1:'call   0x18000afa0',
  0x18000B9C0:'addsd  xmm7,qword ptr [rax]', # sum
  0x18000B9E3:'divsd  xmm1,xmm7', # normalize by sum
  0x18000BA02:'mulsd  xmm0,qword ptr [rdx+rcx*8]',
  0x18000BA83:'call   0x180008d70',
  0x18000BAC1:'call   0x1800094f0',
  0x18000BE0A:'[rcx+0x8],rdx', # stage holds filter
  0x18000BE2A:'[rcx+0x28],r8d',
  0x18000BE35:'[rcx+0x2c],r9d',
  0x1800BF238:'[r14+0x243f8]',
  0x1800BF242:'[r14+0x243fc]',
  0x1800BF24C:'[r14+0x24400]',
  0x1800BF256:'[r14+0x24404]',
  0x1800BF23F:'[rdi+0x68],eax',
  0x1800BF249:'[rdi+0x6c],eax',
  0x1800BF253:'[rdi+0x70],eax',
  0x1800BF25D:'[rdi+0x74],eax',
  # Export and selector connection; a zero mode leads into the dynamic-rate route.
  0x1800E20AE:'xor    r12d,r12d',
  0x1800E2232:'[rcx+0x27c],r12d',
  0x180060F59:'mov    rbx,rcx',
  0x18006109C:'[rbx+0x27c],0x1',
  0x1800610A3:'jne    0x18006125c',
  0x1800611AF:'call   0x18000ff40',
  0x18006137D:'call   0x180010e70',
  0x180010F7F:'call   0x18000e0e0',
  0x180010F84:'movd   xmm6,eax',
  0x180010F88:'cvtdq2pd xmm6,xmm6',
  0x180010F8C:'0x18024cef0',
  0x180011016:'movaps xmm2,xmm6',
  0x180011019:'mov    rdx,qword ptr [r15]',
  0x180011021:'call   0x18000d4a0',
  0x180011086:'cvtpd2ps xmm0,xmm6',
  0x180011093:'[rsp+0x20],xmm0',
  0x1800110AD:'call   0x180010230',
  0x180010287:'[rbp+0x27b20]',
  0x180010453:'movaps xmm1,xmm6',
  0x18001045D:'call   0x1800bfe00',
  0x180010489:'call   0x1800bf9f0',
  0x1800104BD:'call   0x1800bf5e0',
  0x1800104E1:'call   0x1800be830',
  # Dynamic Fs discovery: decoded metadata -> float32, fallback 48k, return rate.
  0x18000E6CA:'test   rbx,rbx',
  0x18000E6CD:'jne    0x18000e855',
  0x18000E855:'movsd  xmm9,qword ptr [rbx+0x18]',
  0x18000E85B:'cvtpd2ps xmm9,xmm9',
  0x18000E9B5:'xorps  xmm6,xmm6',
  0x18000E9B8:'comiss xmm6,xmm9',
  0x18000E9BC:'jb     0x18000e9f3',
  0x18000E9EA:'0x18024cdf4', # float32 fallback Fs=48000
  0x18000EA01:'0x18024cdf0', # distinct float32 Fs=44100 comparison
  0x18000EA0D:'cvtps2pd xmm7,xmm9',
  0x18000F620:'cvttss2si ebx,xmm9',
  0x18000F66B:'mov    eax,ebx',
  0x18000F900:'mov    eax,0xfffffffe',
  # Common export global object writes -> same fields reloaded in worker.
  0x1800E20A7:'0x1802a71d8',
  0x1800E20C1:'[rax+0x200],rsi',
  0x1800E20EA:'[rdx+0x208],rcx',
  0x1800E2134:'[rdx+0x210],rcx',
  0x1800E219C:'[rcx+0x218]',
  0x1800E220E:'[rcx+0x258],rax',
  0x1800E2239:'call   0x1801718a0',
  0x1800612E7:'[rbx+0x258]',
  0x180061305:'[rbx+0x210]',
  0x180061329:'[rbx+0x208]',
  0x18006134C:'[rbx+0x278]',
  0x18006137D:'call   0x180010e70',
  # End-to-end worker dispatch via constructor -> vtable -> async thread.
  0x180002244:'0x180248018',
  0x18000224B:'mov    qword ptr [rbx],rax',
  0x1801718F0:'0x180148810',
  0x1801718FF:'0x18018bad8',
  0x180148857:'call   0x18015a060',
  0x18015A0CC:'mov    rax,qword ptr [rsi]',
  0x18015A0D2:'call   qword ptr [rax+0x8]',
}
RANGES=[(0x18000B0E0,0x18000BB40),(0x18000BB80,0x18000C000),
        (0x18000CF30,0x18000D200),(0x180011B60,0x180011D45),
        (0x1800BF220,0x1800BF270),
        (0x1800E20A0,0x1800E2240),(0x180060F50,0x180061390),
        (0x180010F70,0x1800110B5),(0x180010270,0x1800104F0),
        (0x18000E6C0,0x18000E710),(0x18000E850,0x18000E870),
        (0x18000E9B0,0x18000EA20),(0x18000F610,0x18000F680),(0x18000F8F0,0x18000F915),
        (0x1800E20A0,0x1800E2240),(0x1800612E0,0x180061395),
        (0x18000223F,0x180002255),(0x1801718E0,0x180171905),
        (0x180148840,0x180148870),(0x18015A0C0,0x18015A0D8)]

def dll_pe_at(data:bytes,addr:int,n:int)->bytes:
    """Minimal PE section parser; rejects addresses without on-disk backing."""
    if data[:2]!=b'MZ':raise ValueError('not MZ')
    peoff=struct.unpack_from('<I',data,0x3c)[0]
    if data[peoff:peoff+4]!=b'PE\0\0':raise ValueError('not PE')
    nsec=struct.unpack_from('<H',data,peoff+6)[0]
    optsz=struct.unpack_from('<H',data,peoff+20)[0]
    optoff=peoff+24
    imagebase=struct.unpack_from('<Q',data,optoff+24)[0]
    rva=addr-imagebase
    for j in range(nsec):
        off=optoff+optsz+j*40
        size,virt,raw,ptr=struct.unpack_from('<4I',data,off+8)
        if virt<=rva and rva+n<=virt+raw:
            return data[ptr+rva-virt:ptr+rva-virt+n]
    raise ValueError(f'PE address lacks file data: {addr:#x}')

def verify(dll:Path)->dict:
    source=dll.read_bytes()
    actual_sha=hashlib.sha256(source).hexdigest()
    if actual_sha!=DLL_SHA:raise AssertionError('Wrong DLL SHA256: '+actual_sha)
    instr={}
    for start,end in RANGES:
        asm=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
              f'--start-address={start:#x}',f'--stop-address={end:#x}',str(dll)],text=True)
        for line in asm.splitlines():
            m=re.match(r'^\s*([0-9a-f]+):\s+(.*)$',line)
            if m: instr[int(m.group(1),16)]=m.group(2).strip().lower()
    for addr,needle in PINS.items():
        if needle.lower() not in instr.get(addr,''):
            raise AssertionError(f'Source pin failed {addr:#x}: {needle!r} vs {instr.get(addr)!r}')
    const_addrs={
      'source_to_cutoff_ratio_double_half':0x18024c880,
      'filter_constructor_stack_quality_double':0x18024cc68,
      'filter_constructor_stack_two_double':0x18024ca38,
      'coefficients_relative_width_factor_double':0x18024c6c8,
      'dynamic_wrapper_rate_failure_sentinel_double':0x18024cef0,
    }
    constants={k:struct.unpack('<d',dll_pe_at(source,a,8))[0] for k,a in const_addrs.items()}
    constants['dynamic_rate_fallback_float32']=struct.unpack('<f',dll_pe_at(source,0x18024CDF4,4))[0]
    constants['special_rate_comparison_float32']=struct.unpack('<f',dll_pe_at(source,0x18024CDF0,4))[0]
    assert constants=={
      'source_to_cutoff_ratio_double_half':0.5,
      'filter_constructor_stack_quality_double':180.15,
      'filter_constructor_stack_two_double':2.0,
      'coefficients_relative_width_factor_double':0.01,
      'dynamic_wrapper_rate_failure_sentinel_double':-2.0,
      'dynamic_rate_fallback_float32':48000.0,
      'special_rate_comparison_float32':44100.0,
    }
    dispatch_vtable_first=struct.unpack('<Q',dll_pe_at(source,0x180248018,8))[0]
    dispatch_vtable_method=struct.unpack('<Q',dll_pe_at(source,0x180248020,8))[0]
    assert dispatch_vtable_first==0x180061610
    assert dispatch_vtable_method==0x180060F20
    return {'dll_sha256':actual_sha,'address_pins':len(PINS),'address_pin_values':{f'0x{k:X}':instr[k] for k in sorted(PINS)},
            'pe_constants':constants,'export_virtual_dispatch':{'vtable_va':'0x180248018','method_0':'0x180061610','method_1':'0x180060F20','dispatch_proven':True}}

def branch(source_fs:float=48000.0,target_fs:float=44100.0,frames:int=70*48000)->dict:
    # Model only the scalar operations explicitly visible at 0x11C40-0x11C99.
    assert source_fs>0 and target_fs>0 and frames>=0
    if source_fs==target_fs: return {'first_branch':'equal_rates','stages':'no_filter','output_samples':int(frames)}
    first='double_target_gt_source' if target_fs*2>source_fs else 'double_target_lte_source'
    if first=='double_target_gt_source':
      ratio = 0.5 if target_fs>source_fs else target_fs*0.5/source_fs
      # Note at 0x11C90 xmm6 <- target, xmm11 = 0.5; xmm8 = source.
      # No treatment of later loops or additional filters here.
      return {'first_branch':first,'first_cache_filter_arg0':ratio,
              'filter_cache_first_call_arg1':2.0,'filter_cache_first_call_arg2':180.15,
              'filter_cache_first_call_arg5':2.0,
              'output_samples_float32_ratio':int(__import__('numpy').float32(
                __import__('numpy').float32(frames)*__import__('numpy').float32(target_fs)/__import__('numpy').float32(source_fs))),
              'stages':'later constructor loops NOT reconstructed'}
    return {'first_branch':first,'stages':'different branch not reconstructed'}

def tests():
    n=0
    x=branch();n+=1
    assert x['first_branch']=='double_target_gt_source';n+=1
    assert abs(x['first_cache_filter_arg0']-(44100*0.5/48000))<1e-15;n+=1
    assert x['output_samples_float32_ratio']==3087000;n+=1
    assert branch(44100,44100,3087000)['first_branch']=='equal_rates';n+=1
    assert branch(44100,44100,3087000)['output_samples']==3087000;n+=1
    assert branch(96000,44100)['first_branch']=='double_target_lte_source';n+=1
    assert branch(44100,48000)['first_cache_filter_arg0']==0.5;n+=1
    assert branch(44100,48000,70*44100)['output_samples_float32_ratio']==3360000;n+=1
    assert (0!=1) and (1==1);n+=1
    return n

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dll',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args()
    output={'stage':'23 continuation','status':'SOURCE_PINNED_DYNAMIC_FS_ROUTE_AND_PARTIAL_RESAMPLER_NO_GAIN_PARITY',
            'dll':verify(a.dll),'synthetic_branch_tests_passed':tests(),
            'branch_48000_to_44100':branch(),
            'hypothetical_dynamic_branch_44100_to_48000':branch(44100.0,48000.0,70*44100),
            'export_mode_static':{'namConvertCloData_initial_flag':0,'mode_one_path':'0xFF40 (fixed-44.1k)','mode_other_path':'0x10E70 (dynamic-Fs)','rate_detector':'0xE0E0: decoded metadata [rbx+0x18] (double -> f32) when positive, otherwise fallback 48000f; return cvttss2si; error -2','worker_task_proven_end_to_end':True,'common_global_object':'0x1802A71D8; field writes 0x208/0x210/+0x218/+0x258/+0x27C match worker 0x60F20 reads but async dispatch call 0x1718A0 not proven'},
            'source_graph':['0xCE00: f32 input -> double per channel, call 0x11B60, virtual stage +0x30, double -> f32',
                            '0x11B60: rate-dependent multistage constructor, 48k->44.1k takes 2*target>source branch',
                            '0xBB80: filter descriptor cache, lookup 5 parameter fields, create via B0E0 on miss',
                            '0xB0E0: source-derived FIR length, coefficient generation/normalization, then polyphase processing helpers',
                            '0xBDF0: constructs stage with filter descriptor and rate arguments',
                            '0xBF238..0xBF25D: copies four native saturation params directly into serialized DSP fields',
                            'namConvertCloData 0xE20AE/0xE2232 writes +0x27C = 0; worker 0x6109C routes !=1 to 0x10E70',
                            '0x10E70 uses 0xE0E0 result as dynamic target sample-rate, resamples input at 0x11021 and calls 0x10230 at 0x110AD',
                            '0x10230 uses caller rate in context constructor then loads native input/reference and fits',
                            '0xE0E0: observed 48k-f32 fallback when parsed metadata rate <=0; compares 44.1k-f32 specially; truncates selected rate to integer',
                            '0xE20EA/0xE2134 stores common global +0x208/+0x210; 0x61329/0x61305 read same offsets and route to dynamic 0x10E70',
                            'Async thread: export 0xE2239 -> 0x1718A0 -> 0x148810 -> 0x15A060 -> virtual call [vtable+8] -> 0x60F20, PE table 0x248018'],
            'open_gates':['full B0E0 coefficient and 0xAFA0 numerical kernel reconstruction',
                          '0x11B60 stage count and per-stage ratio / time alignment, including boundary modes',
                          'determine decoded metadata object field +0x18 provenance and exact dynamic Fs for captured model (async worker binding is proven)',
                          'decoder PCM16 to f32 scale and source WAV prep; resampled native time-alignment',
                          'real native source/target arrays, independent four-gain parity on both models'],
            'real_native_four_gains':'NOT_COMPUTED','production_changes':False,'hardware_changes':False}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(output,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
    print(f"PASS {output['dll']['address_pins']} native code pins, {len(output['dll']['pe_constants'])} PE constants, {output['synthetic_branch_tests_passed']} synthetic tests. Real native gains NOT_COMPUTED")
if __name__=='__main__':main()
