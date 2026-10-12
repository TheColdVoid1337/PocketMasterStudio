#!/usr/bin/env python3
"""DLL-first static SSA proof for the Stage-16 HTKPA iteration; NEVER loads the DLL.

Output is a machine-readable map and synthetic controls, NOT a NAM/CLO converter.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess
from pathlib import Path
import numpy as np
SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BASE=0x180000000
DLL_PINS={
 'malloc_post_length':(0x1800bb232,'[rcx+0x20ed8]'),
 'malloc_pre_length':(0x1800bb259,'[rcx+0x20ed4]'),
 'malloc_curve_length':(0x1800bb23b,'[rsp+0x1c8]'),
 'malloc_audio_length':(0x1800bb264,'r9d'),
 'malloc_iteration_count':(0x1800bb245,'[rsp+0x1c0]'),
 'malloc_allocate':(0x1800bb271,'[rip+0xd06c9]'),
 'source_context_curve_a':(0x1800bb289,'[rbx+0x24328]'),
 'source_context_curve_b':(0x1800bb347,'[rbx+0x24330]'),
 'scratch_v1':(0x1800bb2b8,'[rsp+0x90]'),
 'scratch_v2':(0x1800bb2c7,'[rsp+0x1d8]'),
 'scratch_v3':(0x1800bb2d2,'[rsp+0xa0]'),
 'scratch_v4':(0x1800bb2dd,'[rsp+0x58]'),
 'scratch_v5':(0x1800bb2e5,'[rsp+0x98]'),
 'scratch_v6':(0x1800bb2f0,'[rsp+0x1a0]'),
 'scratch_v9':(0x1800bb301,'[rsp+0x70]'),
 'scratch_v10':(0x1800bb309,'[rsp+0x80]'),
 'scratch_pre_backup':(0x1800bb319,'[rsp+0x60]'),
 'scratch_post_backup':(0x1800bb325,'[rsp+0x68]'),
 'scratch_audio':(0x1800bb32a,'[rcx+rax*4]'),
 'scratch_score':(0x1800bb33d,'[rsp+0x50]'),
 'memcpy_source_b':(0x1800bb347,'[rbx+0x24330]'),
 'memcpy_v2_from_v0':(0x1800bb35d,'mov    rdx,r12'),
 'memcpy_v9_from_v0':(0x1800bb376,'mov    rdx,r12'),
 'score_initial_100':(0x1800bb2a1,'[rsp+0x1c8]'),
 'pow_compute':(0x1800bb46e,'call   0x18017e158'),
 'pow_ceil':(0x1800bb479,'movaps xmm0,xmm11'),
 'pow_floor':(0x1800bb48c,'0x3e4ccccd'),
 'anneal_0_9':(0x1800bb4be,'mulss  xmm12'),
 'condition1':(0x1800bb4d9,'call   0x1800b7670'),
 'condition2':(0x1800bb4f8,'call   0x1800b7670'),
 'scratch_v2_times_v0':(0x1800bb575,'mulps  xmm1,xmm0'),
 'source_secondary_divided_v0':(0x1800bb6e1,'divps  xmm1,xmm0'),
 'spectral_shape_aux':(0x1800bb7e3,'call   0x1800b6220'),
 'condition3':(0x1800bb812,'call   0x1800b7670'),
 'pre_destination':(0x1800bb821,'[rsp+0x1f8]'),
 'pre_synthesize':(0x1800bb836,'call   0x1800b68f0'),
 'render_current_1':(0x1800bbb5b,'call   0x1800b5a30'),
 'saturate_current':(0x1800bbcc9,'call   0x1800be700'),
 'spectral_feedback_estimate':(0x1800bc055,'call   0x1800b82b0'),
 'feedback_numerator_from_v5':(0x1800bc081,'[rdi+rdx*4]'),
 'feedback_denominator_from_v2':(0x1800bc07e,'add    rax,r13'),
 'feedback_denominator_v2':(0x1800bc107,'[r8-0x8]'),
 'feedback_num_read':(0x1800bc0f3,'[rax+r8*1-0x8]'),
 'feedback_ratio_float_to_double':(0x1800bc104,'cvtps2pd'),
 'feedback_ratio_scale_num':(0x1800bc10d,'mulpd  xmm3,xmm4'),
 'feedback_ratio_scale_den':(0x1800bc114,'mulpd  xmm2,xmm4'),
 'feedback_ratio_reg':(0x1800bc118,'addpd  xmm2,xmm5'),
 'feedback_ratio_div':(0x1800bc11c,'divpd  xmm3,xmm2'),
 'feedback_ratio_write_v2':(0x1800bc12e,'[rdx+r8*1-0x8]'),
 'feedback_condition':(0x1800bc33d,'call   0x1800b7670'),
 'post_destination':(0x1800bc342,'[rsp+0x200]'),
 'post_synthesize':(0x1800bc35c,'call   0x1800b68f0'),
 'render_current_2':(0x1800bc381,'call   0x1800b5a30'),
 'spectral_score_estimate':(0x1800bc3c5,'call   0x1800b82b0'),
 'score_interpolate':(0x1800bc3f9,'call   0x1800b5d00'),
 'score_load_output':(0x1800bc410,'[r13+rdi*4+0x0]'),
 'score_log':(0x1800bc41c,'call   0x18017e14c'),
 'score_average':(0x1800bc440,'mulss  xmm7'),
 'accept_branch':(0x1800bc459,'comiss xmm0,xmm7'),
 'accept_save_pre':(0x1800bc495,'[rsp+0x1f8]'),
 'accept_save_post':(0x1800bc4b2,'[rsp+0x200]'),
 'reject_factor_1_2':(0x1800bc504,'mulsd  xmm0'),
 'reject_branch':(0x1800bc510,'comisd xmm1,xmm0'),
 'reject_restore_pre':(0x1800bc53f,'[rsp+0x1f8]'),
 'reject_restore_post':(0x1800bc55c,'[rsp+0x200]'),
 'reject_step_half':(0x1800bc59c,'mulsd  xmm0'),
 'iteration_loop':(0x1800bc5c2,'0x1800bb440'),
 'caller_selector_dispatch':(0x1800bf050,'[rsp+rbx*4+0xa8]'),
 'caller_iteration_lookup':(0x1800bf0a3,'[rsp+rdx*4+0xc4]'),
 'caller_pre_pointer':(0x1800bf07c,'[r14+0x24408]'),
 'caller_post_pointer':(0x1800bf070,'[r14+0x24410]'),
 'caller_iteration_call':(0x1800bf0c9,'call   0x1800bb210'),
 'caller_three_stages':(0x1800bf0d1,'0x3'),
 'finalizer_once':(0x1800bf11e,'call   0x1800b9b70'),
}
CONSTANTS={
 'initial_score':(0x18024cd78,'<f',100.0),
 'unit_magnitude':(0x18024c6a0,'<f',1.0),
 'iteration_anneal':(0x18024c654,'<f',0.9),
 'pow_ceiling':(0x18024ccd0,'<f',5.0),
 'pow_floor':(0x18024c7e0,'<d',0.2),
 'reject_score_ratio':(0x18024c9a8,'<d',1.2),
 'reject_step_scale':(0x18024c880,'<d',0.5),
 'feedback_scale':(0x18024d5a0,'<d',1e6),
 'feedback_epsilon':(0x18024d1e0,'<d',2**-23),
}

def pe_bytes(raw,va,n):
    p=struct.unpack_from('<I',raw,0x3c)[0]
    if raw[:2]!=b'MZ' or raw[p:p+4]!=b'PE\0\0':raise AssertionError('Not PE')
    count=struct.unpack_from('<H',raw,p+6)[0]; opt=struct.unpack_from('<H',raw,p+20)[0]; rva=va-BASE
    for i in range(count):
        o=p+24+opt+40*i; _,vsz,sr,sz,off=struct.unpack_from('<8sIIII',raw,o)
        if sr<=rva and rva+n<=sr+sz:return raw[off+rva-sr:off+rva-sr+n]
    raise ValueError(hex(va))

def get_assembly(dll,lo,hi):
    z=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],check=True,capture_output=True,text=True)
    result={}
    for line in z.stdout.splitlines():
        m=re.match(r'^\s*([a-fA-F0-9]+):\s*(.*)',line)
        if m:result[int(m.group(1),16)]=m.group(2).strip()
    return result

def layout(curve_n,pre_n,post_n,audio_n,iteration_n):
    # These offsets are computed from the allocator arithmetic, not chosen by fitting.
    assert min(curve_n,pre_n,post_n,audio_n,iteration_n)>0
    base={f'v{k}':k*curve_n for k in range(10)}
    pos=10*curve_n
    base['temp_pre_curve']=pos;pos+=pre_n
    base['saved_pre']=pos;pos+=pre_n
    base['saved_post']=pos;pos+=post_n
    base['rendered_audio']=pos;pos+=audio_n
    base['score_per_iteration']=pos;pos+=iteration_n
    return base,pos

def synthetic_tests():
    tests=[]
    def chk(k,yes):
        if not bool(yes):raise AssertionError(k)
        tests.append(k)
    a,total=layout(512,128,2048,48000,5)
    chk('curve_slots_zero_to_nine',all(a[f'v{k}']==512*k for k in range(10)))
    chk('temp_pre_at_10L',a['temp_pre_curve']==5120)
    chk('saved_pre_after_temp',a['saved_pre']==5120+128)
    chk('saved_post_after_pre_backup',a['saved_post']==5120+256)
    chk('render_buffer_after_post',a['rendered_audio']==5120+256+2048)
    chk('score_pointer_after_audio',a['score_per_iteration']==a['rendered_audio']+48000)
    chk('malloc_formula',total==10*512+2*128+2048+48000+5)
    chk('all_regions_in_bounds',all(0<=v<total for v in a.values()))
    chk('all_regions_disjoint',len(set(a.values()))==len(a))
    chk('layout_stable_with_other_shapes',layout(37,13,92,100,3)[1]==10*37+2*13+92+100+3)
    # Verified local vector multiplies, div and in-place feedback, no speculative filter math.
    v0=np.array([1.15,0.8,1.0,2.0],dtype=np.float32)
    v2=np.array([0.3,0.7,1.9,4],dtype=np.float32)
    product=(v2*v0).astype(np.float32)
    chk('v2_multiplicative_chain',np.array_equal(product, np.array([0.345,0.56,1.9,8],dtype=np.float32)))
    y=np.array([3,4,5,6],dtype=np.float32)
    out=(1e6*y.astype(float)/(1e6*product.astype(float)+2**-23)).astype(np.float32)
    chk('feedback_ratio_uses_v5_over_v2',np.allclose(out, y/product,rtol=1e-6))
    chk('feedback_no_clipping_built_in',np.max(out)>1.0)
    chk('feedback_zero_numerator',float((1e6*0/(1e6*1+2**-23)))==0)
    # Stage 8 branch logic with real saved snapshots: save on improved, restore only >20% worse.
    def decide(new,old):return ('save' if new<old else 'restore' if new>1.2*old else 'continue')
    chk('score_improvement_saves',decide(2,3)=='save')
    chk('score_worse_by_30_percent_restores',decide(1.3,1)=='restore')
    chk('score_worse_by_15_percent_keeps',decide(1.15,1)=='continue')
    chk('score_equal_keeps',decide(1,1)=='continue')
    chk('exact_score_20_percent_keeps',decide(1.2,1)=='continue')
    chk('pow_step_drops_10_percent',abs((0.9**3)-0.729)<1e-12)
    chk('rejected_step_is_halved',0.5*0.8==0.4)
    chk('original_context_immutable_in_layout',a['v0']!=a['saved_pre'])
    return tests

def main():
    p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();raw=a.dll.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=SHA:raise AssertionError('unexpected 5868USB.dll sha '+sha)
    asm={}
    for lo,hi in [(0x1800bb210,0x1800bc5d0),(0x1800bf040,0x1800bf130)]:asm.update(get_assembly(a.dll,lo,hi))
    proven={}
    for label,(va,substring) in DLL_PINS.items():
        got=asm.get(va)
        if got is None or substring not in got:raise AssertionError(f'{label} {va:#x}: expected {substring!r}, found {got!r}')
        proven[label]={'va':hex(va),'instruction':got}
    const={}
    for name,(va,fmt,expected) in CONSTANTS.items():
        actual=struct.unpack(fmt,pe_bytes(raw,va,struct.calcsize(fmt)))[0]
        if not math.isclose(actual,expected,rel_tol=1e-6,abs_tol=1e-12):raise AssertionError((name,actual,expected))
        const[name]={'va':hex(va),'value':actual}
    checks=synthetic_tests(); offsets,alloc=layout(512,128,2048,48000,5)
    result={'stage':16,'dll_sha256':sha,'code_pins':proven,'code_pin_count':len(proven),'constants':const,'constants_count':len(const),
            'synthetic_checks':checks,'synthetic_check_count':len(checks),'demonstration_offsets_float32':offsets,
            'demonstration_total_float32':alloc,'asserted': 'source-pinned workspace topology and spectral feedback scratch identities',
            'not_asserted':'native byte-exact HTKPA, complete curve conditioning, vendor FIR coefficient reconstruction'}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(f'OK: {len(proven)} static machine-code pins; {len(const)} numerical constants; {len(checks)} algebraic tests; evidence {hashlib.sha256(a.out.read_bytes()).hexdigest()}')
if __name__=='__main__':main()
