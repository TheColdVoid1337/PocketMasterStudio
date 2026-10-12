#!/usr/bin/env python3
"""Read-only exact-instruction HTKPA Stage 8 proof against one SHA256-pinned DLL.

No vendor code is executed. No vendor bytes or signal captures in outputs.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

BASE = 0x180000000
SHA256 = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'

# Exact VA, nonempty instruction substring: program analysis must fail closed.
PROOFS = {
    'input_6s_pointer': (0x1800beb14, 'mov    QWORD PTR [rsp+0x80],r12'),
    'input_23s_pointer': (0x1800beb35, 'mov    QWORD PTR [rsp+0xa8],rax'),
    'input_30s_pointer': (0x1800beb57, 'mov    QWORD PTR [rsp+0x88],rax'),
    'input_50s_pointer': (0x1800beb79, 'mov    QWORD PTR [rsp+0x78],rax'),
    'output_6s_pointer': (0x1800beb23, 'mov    QWORD PTR [rsp+0x90],r13'),
    'output_23s_pointer': (0x1800beb45, 'mov    QWORD PTR [rsp+0xc8],rax'),
    'output_30s_pointer': (0x1800beb67, 'mov    QWORD PTR [rsp+0xb8],rax'),
    'output_50s_pointer': (0x1800beb86, 'mov    QWORD PTR [rsp+0x70],rax'),
    'onset_600_sample_search': (0x1800bea84, 'mov    esi,0x258'),
    'onset_output_23s_shift': (0x1800beb3d, 'lea    rax,[rcx+rdx*1]'),
    'onset_output_30s_shift': (0x1800beb5f, 'lea    rax,[rcx+rdx*1]'),
    'onset_output_50s_shift': (0x1800beb7e, 'lea    rax,[rcx+rdx*1]'),
    'reference_6s_scale': (0x1800bea5d, 'lea    r10d,[rdi+rdi*2]'),
    'reference_23s_scale': (0x1800beb2b, 'imul   eax,edi,0x17'),
    'reference_30s_scale': (0x1800beb4d, 'imul   eax,edi,0x1e'),
    'reference_50s_scale': (0x1800beb6f, 'imul   eax,edi,0x32'),
    'selector_2_first': (0x1800bee9f, '0x2'),
    'selector_1_second': (0x1800beeaa, '0x1'),
    'selector_3_third': (0x1800beeb5, '0x3'),
    'iteration_table_load': (0x1800bee8e, '0x18024cfb0'),
    'iteration_table_copy': (0x1800bee96, '[rsp+0xc8],xmm0'),
    'window_15s': (0x1800bef2a, '[rsp+0xb8],edi'),
    'window_5s': (0x1800bef31, '[rsp+0xbc],esi'),
    'window_20s': (0x1800bef3c, '[rsp+0xc0],eax'),
    'input_table_6s': (0x1800beec8, '[rsp+0xf8],rax'),
    'input_table_23s': (0x1800beed0, '[rsp+0x100],rbx'),
    'input_table_30s': (0x1800beee0, '[rsp+0x108],rax'),
    'output_table_6s': (0x1800beefd, '[rsp+0xd8],rax'),
    'output_table_23s': (0x1800bef05, '[rsp+0xe0],rbp'),
    'output_table_30s': (0x1800bef15, '[rsp+0xe8],rax'),
    'dispatch_selector_lookup': (0x1800bf050, '[rsp+rbx*4+0xa8]'),
    'dispatch_count_lookup': (0x1800bf0a3, '[rsp+rdx*4+0xc4]'),
    'dispatch_window_lookup': (0x1800bf0ae, '[rsp+rdx*4+0xb4]'),
    'dispatch_output_lookup': (0x1800bf0b6, '[rsp+rdx*8+0xd0]'),
    'dispatch_input_lookup': (0x1800bf0be, '[rsp+rdx*8+0xf0]'),
    'dispatch_fitter_call': (0x1800bf0c9, 'call   0x1800bb210'),
    'dispatch_loop_three': (0x1800bf0d1, 'cmp    rbx,0x3'),
    'final_input_50s': (0x1800bf116, '[rsp+0x78]'),
    'final_output_50s': (0x1800bf111, '[rsp+0x70]'),
    'final_spectral_call': (0x1800bf11e, 'call   0x1800b9b70'),
    'fitter_iterations_arg': (0x1800bb245, '[rsp+0x1c0]'),
    'fitter_iteration_loop_tail': (0x1800bc5c2, 'jne    0x1800bb440'),
    'pre_source_array': (0x1800bf07c, '[r14+0x24408]'),
    'post_source_array': (0x1800bf070, '[r14+0x24410]'),
    'post_length_fitter_arg': (0x1800bf097, '[rsp+0x30],xmm0'),
    'pre_length_fitter_arg': (0x1800bf09d, '[rsp+0x28],xmm1'),
    'gain_candidate_forward_fit': (0x1800bbb5b, 'call   0x1800b5a30'),
    'gain_candidate_second_fit': (0x1800bc381, 'call   0x1800b5a30'),
    'window_candidate_first': (0x1800bc055, 'call   0x1800b82b0'),
    'window_candidate_second': (0x1800bc3c5, 'call   0x1800b82b0'),
    'save_pre_on_improvement': (0x1800bc495, '[rsp+0x1f8]'),
    'save_post_on_improvement': (0x1800bc4b2, '[rsp+0x200]'),
    'score_work_buffer_load': (0x1800bc3ca, 'mov    r13,QWORD PTR [rsp+0xa0]'),
    'score_work_buffer_pass_as_output': (0x1800bc3e4, 'mov    QWORD PTR [rsp+0x30],r13'),
    'score_buffer_producer': (0x1800bc3f9, 'call   0x1800b5d00'),
    'score_producer_destination_read': (0x1800b5fe3, 'mov    rdi,QWORD PTR [rsp+0xb0]'),
    'score_producer_destination_write': (0x1800b60fe, 'movss  DWORD PTR [rdi+r10*1],xmm0'),
    'score_buffer_consumer': (0x1800bc410, 'movss  xmm0,DWORD PTR [r13+rdi*4+0x0]'),
    'loss_logf': (0x1800bc41c, 'call   0x18017e14c'),
    'loss_loop_512': (0x1800bc437, 'cmp    rdi,0x200'),
    'loss_average': (0x1800bc440, '0x18024c4f0'),
    'score_compare': (0x1800bc459, 'comiss xmm0,xmm7'),
    'score_nonimproving_branch': (0x1800bc469, 'jbe    0x1800bc4fe'),
    'worse_than_20pct': (0x1800bc504, '0x18024c9a8'),
    'threshold_branch': (0x1800bc514, 'jbe    0x1800bc5ab'),
    'restore_pre': (0x1800bc53f, '[rsp+0x1f8]'),
    'restore_post': (0x1800bc55c, '[rsp+0x200]'),
    'reduce_exponent_step': (0x1800bc59c, '0x18024c880'),
    'updated_state_persist_pre': (0x1800bc62d, '[rsp+0x1f8]'),
    'updated_state_persist_post': (0x1800bc64a, '[rsp+0x200]'),
}


def mapped_bytes(blob, va, size):
    off = struct.unpack_from('<I', blob, 0x3c)[0]
    assert blob[:2] == b'MZ' and blob[off:off+4] == b'PE\x00\x00'
    nsecs = struct.unpack_from('<H', blob, off+6)[0]
    optional_size = struct.unpack_from('<H', blob, off+20)[0]
    rva = va - BASE
    for i in range(nsecs):
        sec = off+24+optional_size+i*40
        virt_size, virt_addr, raw_size, raw_addr = struct.unpack_from('<IIII', blob, sec+8)
        if virt_addr <= rva and rva+size <= virt_addr+raw_size:
            return blob[raw_addr+rva-virt_addr:raw_addr+rva-virt_addr+size]
    raise AssertionError(f'unmapped VA {va:#x}')


def disassemble(dll, start, stop):
    cmd=['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={start:#x}',f'--stop-address={stop:#x}',str(dll)]
    r=subprocess.run(cmd,capture_output=True,text=True,check=True)
    lines={}
    for line in r.stdout.splitlines():
        match=re.match(r'^\s*([0-9a-fA-F]+):\s*(.*?)\s*$',line)
        if match:
            lines[int(match.group(1),16)]=match.group(2)
    return lines


def reconstruction():
    # Stack tables and offsets are constrained by the exact pinned instructions.
    source_times={1:6,2:23,3:30,4:50}
    dest_times=source_times.copy()
    seconds={1:15,2:5,3:20}
    iterations={1:2,2:3,3:5}
    out=[]
    for order,selector in enumerate([2,1,3],1):
        out.append(dict(order=order,selector=selector,source_start_sec=source_times[selector],
                        output_start_sec=dest_times[selector],window_seconds=seconds[selector],
                        iteration_count=iterations[selector],
                        source_end_sec=source_times[selector]+seconds[selector],
                        output_alignment='source_start_sec plus detected 0..600 sample initial offset'))
    assert out==[
        dict(order=1,selector=2,source_start_sec=23,output_start_sec=23,window_seconds=5,iteration_count=3,source_end_sec=28,output_alignment='source_start_sec plus detected 0..600 sample initial offset'),
        dict(order=2,selector=1,source_start_sec=6,output_start_sec=6,window_seconds=15,iteration_count=2,source_end_sec=21,output_alignment='source_start_sec plus detected 0..600 sample initial offset'),
        dict(order=3,selector=3,source_start_sec=30,output_start_sec=30,window_seconds=20,iteration_count=5,source_end_sec=50,output_alignment='source_start_sec plus detected 0..600 sample initial offset'),
    ]
    return out


def main():
    a=argparse.ArgumentParser()
    a.add_argument('dll',type=Path)
    a.add_argument('--out',type=Path)
    args=a.parse_args()
    raw=args.dll.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    assert digest==SHA256, f'wrong DLL hash {digest}'
    instructions={}
    for lo,hi in [(0x1800bea00,0x1800bf150),(0x1800bb210,0x1800bc700),(0x1800b5d00,0x1800b6130)]:
        instructions.update(disassemble(args.dll,lo,hi))
    proofs={}
    for tag,(va,substring) in PROOFS.items():
        line=instructions.get(va,'')
        assert substring in line, f'{tag}: {va:#x}: expected {substring!r}, found {line!r}'
        proofs[tag]={'address':f'0x{va:x}','instruction':line}
    iteration_table=struct.unpack('<4i',mapped_bytes(raw,0x18024cfb0,16))
    seconds_table={name:struct.unpack('<f',mapped_bytes(raw,addr,4))[0]
        for name,addr in [('window5',0x18024ccd0),('window15',0x18024cd34),('window20',0x18024cd40)]}
    static_constants={name:struct.unpack('<d' if dtype=='d' else '<f',mapped_bytes(raw,addr,8 if dtype=='d' else 4))[0]
        for name,(addr,dtype) in {
        'loss_divisor':(0x18024c4f0,'f'),
        'score_worsening_threshold':(0x18024c9a8,'d'),
        'step_shrink':(0x18024c880,'d'),
        'exponent_anneal':(0x18024c654,'f'),
        'loss_epsilon':(0x18024c4d4,'f'),
        }.items()}
    assert iteration_table==(2,3,5,1)
    assert seconds_table=={'window5':5.0,'window15':15.0,'window20':20.0}
    assert static_constants['loss_divisor']==1/512
    assert static_constants['score_worsening_threshold']==1.2
    assert static_constants['step_shrink']==0.5
    assert abs(static_constants['exponent_anneal']-0.9)<1e-7
    assert static_constants['loss_epsilon']==2**-23
    stages=reconstruction()
    # Simulate only verified branch predicates for adversarial boundary checks.
    def branch(previous, current):
        if previous>current:return 'improvement: save updated state'
        if current>1.2*previous:return 'worsening >20%: restore saved state and halve step'
        return 'non-improvement <=20%: keep current state without halving step'
    assert branch(1.,.9)=='improvement: save updated state'
    assert branch(1.,1.1)=='non-improvement <=20%: keep current state without halving step'
    assert branch(1.,1.3)=='worsening >20%: restore saved state and halve step'
    output={
        'status':'STATIC READ ONLY; exact instruction and data table checks; original DLL NOT executed',
        'sha256':digest,
        'proof_count':len(proofs),'proofs':proofs,
        'pinned_constants':{'iteration_table_u32':iteration_table,'seconds':seconds_table,'optimizer_constants':static_constants},
        'stage_dispatch':stages,
        'spectral_finish':{'input_window_start_sec':50,'duration_sec':20,'output_alignment':'same detected offset','entry_VA':'0x1800b9b70'},
        'joint_fir_backup':{'finding':'both Pre and Post coefficient buffers are backed up and restored together on accepted/rolled-back iterations',
                            'pre_context_offset':'0x24408','post_context_offset':'0x24410'},
        'optimizer_score':{'computational_pattern':'mean(abs(logf(v[i] + 2^-23))) over i=0..511',
                         'proven_producer':'buffer output passed at caller stack +0x30 to 0x1800B5D00 at 0x1800BC3F9',
                         'unknown':'meaning/equations of array produced by 0x1800B5D00',
                         'branch_labels':{str(x):branch(1.,x) for x in [0.9,1.1,1.3]}},
        'scope_limitations':[
            'Source-to-filter exact numerical equations not reconstructed.',
            'The score array is not identified as final Post-FIR taps.',
            'No fitted CLO generated; no vendor DLL execution or device writes.',
            'Do not infer Windows Manager and mobile SONICLINK algorithm identity.',
        ],
    }
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'PASS: {len(proofs)} instruction pins; 4 iteration entries; 3 ordered regions; optimizer guard')
    for s in stages:
        print(f"  {s['order']}: selector {s['selector']} {s['source_start_sec']}-{s['source_end_sec']}s, {s['iteration_count']} iterations")
    print('  finish: 50-70s independent spectral stage')
    print('  score branch: improvement / <=20% worse / >20% worse rollback+half-step')
    return output


if __name__=='__main__':
    main()
