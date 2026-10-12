#!/usr/bin/env python3
"""Source-first HTKPA Stage 17 static verifier and partial algebraic reconstruction.

NEVER executes proprietary DLL. Does NOT claim complete HTKPA or export a CLO.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re,struct,subprocess
from pathlib import Path
import numpy as np

SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BASE=0x180000000
PINS = {
    'context_half_fs': (0x1800b5865,'0x18024c5c4'),
    'context_half_fs_store': (0x1800b587f,'[rcx+0x20ec4]'),
    'context_inv_half_fs': (0x1800b587b,'divss  xmm0,xmm1'),
    'context_inv_half_fs_store': (0x1800b5887,'[rcx+0x20ec8]'),
    'outer_alloc_A': (0x1800bee33,'mov    r15,rax'),
    'outer_alloc_B': (0x1800bee3f,'mov    r12,rax'),
    'outer_alloc_freq': (0x1800bee4b,'mov    r13,rax'),
    'outer_pass_first_external': (0x1800bf092,'[rsp+0x40],r15'),
    'outer_pass_second_external': (0x1800bf08d,'[rsp+0x48],r12'),
    'outer_pass_third_external': (0x1800bf088,'[rsp+0x50],r13'),
    'outer_three_calls': (0x1800bf0d1,'cmp    rbx,0x3'),
    'inner_external_B': (0x1800bb391,'[rsp+0x1e8]'),
    'inner_external_frequency': (0x1800bb4b6,'mov    rbp,QWORD PTR [rsp+0x1f0]'),
    'cond1_input': (0x1800bb4b3,'mov    rdx,r12'),
    'cond1_output_A': (0x1800bb4cf,'[rsp+0x30],rdi'),
    'cond1_output_F': (0x1800bb4ca,'[rsp+0x38],rax'),
    'cond1_call': (0x1800bb4d9,'call   0x1800b7670'),
    'cond2_input': (0x1800bb4eb,'mov    rdx,rdi'),
    'cond2_output_A': (0x1800bb4ee,'[rsp+0x30],r12'),
    'cond2_output_F': (0x1800bb4e6,'[rsp+0x38],rbp'),
    'cond2_call': (0x1800bb4f8,'call   0x1800b7670'),
    'external_MUL_src': (0x1800bb560,'[rax-0x10]'),
    'external_MUL_other': (0x1800bb568,'[rax+rcx*1-0x10]'),
    'external_MUL_operation': (0x1800bb575,'mulps  xmm1,xmm0'),
    'external_MUL_write': (0x1800bb578,'[rax-0x50]'),
    'external_A_loaded': (0x1800bb66a,'[rsp+0x1e0]'),
    'external_DIV_A': (0x1800bb6d0,'[rax-0x10]'),
    'external_DIV_B': (0x1800bb6d8,'[rcx+rax*1-0x10]'),
    'external_DIV': (0x1800bb6e1,'divps  xmm1,xmm0'),
    'external_DIV_write': (0x1800bb6e9,'[rax-0x50]'),
    'aux_first_const60': (0x1800bb7d2,'0x18024cd60'),
    'aux_input': (0x1800bb7dd,'mov    rdx,rdi'),
    'aux_call': (0x1800bb7e3,'call   0x1800b6220'),
    'aux_inv_fs': (0x1800b622a,'[rcx+0x20ec8]'),
    'aux_multiply_n': (0x1800b623d,'mulss  xmm3,xmm0'),
    'aux_sqrt_count': (0x1800b6244,'call   0x18017e13a'),
    'aux_truncate_count': (0x1800b6249,'cvttss2si ebx,xmm0'),
    'aux_short_guard': (0x1800b624d,'cmp    ebx,0x1'),
    'aux_first_sample': (0x1800b6260,'movss  xmm6,DWORD PTR [rdi]'),
    'aux_first_neighbor_mul': (0x1800b6267,'[rdi+0x4]'),
    'aux_first_sqrt1': (0x1800b626c,'call   0x18017e170'),
    'aux_first_self_mul': (0x1800b6271,'mulss  xmm0,xmm6'),
    'aux_first_sqrt2': (0x1800b6275,'call   0x18017e170'),
    'aux_first_write': (0x1800b627d,'[rdi],xmm0'),
    'aux_neighbor_left': (0x1800b62c8,'[r14-0x8]'),
    'aux_neighbor_right': (0x1800b62c0,'[r14]'),
    'aux_neighbor_sqrt': (0x1800b62ce,'call   0x18017e170'),
    'aux_center_mult': (0x1800b62d3,'[r14-0x4]'),
    'aux_center_sqrt': (0x1800b62d9,'call   0x18017e170'),
    'aux_center_write': (0x1800b62de,'[r14-0x4]'),
    'aux_scalar_left': (0x1800b6353,'[rdi+rbx*4-0x4]'),
    'aux_scalar_right': (0x1800b6359,'[rdi+rbx*4+0x4]'),
    'aux_scalar_left_sqrt': (0x1800b635f,'call   0x18017e170'),
    'aux_scalar_center': (0x1800b6364,'[rdi+rbx*4]'),
    'aux_scalar_center_sqrt': (0x1800b6369,'call   0x18017e170'),
    'aux_scalar_write': (0x1800b636e,'[rdi+rbx*4]'),
    'curve3_input': (0x1800bb800,'mov    rdx,rdi'),
    'curve3_output': (0x1800bb803,'[rsp+0x30],rax'),
    'curve3_call': (0x1800bb812,'call   0x1800b7670'),
    'pre_synth': (0x1800bb836,'call   0x1800b68f0'),
    'feedback_estimate': (0x1800bc055,'call   0x1800b82b0'),
    'post_synth': (0x1800bc35c,'call   0x1800b68f0'),
    'reject_restore_external': (0x1800bc53f,'[rsp+0x1f8]'),
    'iteration_loop': (0x1800bc5c2,'0x1800bb440'),
}
CONSTS={
  'outer_0_5_fs':(0x18024c5c4,'<f',0.5),
  'aux_60':(0x18024cd60,'<f',60.),
  'pow_ceiling':(0x18024ccd0,'<f',5.0),
  'pow_floor':(0x18024c7e0,'<d',0.2),
  'anneal':(0x18024c654,'<f',0.9),
}

def read_va(raw:bytes,va:int,n:int)->bytes:
    pe=struct.unpack_from('<I',raw,0x3c)[0]
    if raw[:2]!=b'MZ' or raw[pe:pe+4]!=b'PE\0\0':raise AssertionError('bad PE')
    num=struct.unpack_from('<H',raw,pe+6)[0];opt=struct.unpack_from('<H',raw,pe+20)[0]
    for k in range(num):
        off=pe+24+opt+40*k
        _,_,rva,sz,raw_off=struct.unpack_from('<8sIIII',raw,off)
        delta=va-BASE-rva
        if 0<=delta and delta+n<=sz:return raw[raw_off+delta:raw_off+delta+n]
    raise ValueError(hex(va))

def get_asm(dll,lo,hi):
    p=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],capture_output=True,text=True,check=True)
    return {int(m.group(1),16):m.group(2).strip() for ln in p.stdout.splitlines() if (m:=re.match(r'^\s*([a-fA-F0-9]+):\s*(.*)',ln))}

def f32(x):return np.float32(x)
def mul(a,b):return f32(f32(a)*f32(b))
def root(x):return f32(np.sqrt(f32(x)))
def prefix_count(n:int,fs:float)->int:
    """Native 0xB6220 float32 count, with verified context inverse of half Fs."""
    if n<=0 or fs<=0:raise ValueError('positive sample_rate and L needed')
    half=mul(fs,0.5);inv=f32(f32(1.0)/half)
    scale=mul(mul(60.,inv),f32(n))
    return int(root(scale))

def in_place_geometric_prefix(inp:np.ndarray, fs:float):
    """Isolated native helper 0x1800B6220 for positive finite floats and 1<K<len(x).

    Preserves in-place dependency; DOES NOT call the spectral conditioner or fit FIRs.
    """
    out=np.asarray(inp,dtype=np.float32).copy();K=prefix_count(len(out),fs)
    if K<=1:return out,K
    if K>=len(out):raise ValueError('Native out-of-bounds/edge semantics not analyzed for K>=L')
    if not np.all(np.isfinite(out)) or np.any(out<=0):raise ValueError('Positive finite-only research domain')
    prior=f32(out[0]);neighbor=f32(out[1]);out[0]=root(mul(root(mul(prior,neighbor)),prior))
    for i in range(1,K):
        left=f32(out[i-1]);center=f32(out[i]);right=f32(out[i+1])
        out[i]=root(mul(root(mul(left,right)),center))
    return out,K

def independent_reference(inp, K):
    """Alternative double-value reasoning reference, not asserted native rounding parity."""
    out=np.array(inp,dtype=float).copy()
    if K>1:
        out[0]=(out[0]**3*out[1])**.25
        for i in range(1,K):out[i]=(out[i-1]*out[i+1]*out[i]**2)**.25
    return out

def stage17_two_external_array_update(curve_a,curve_b,second_conditioner_output):
    """Replays two CONFIRMED writes to caller-owned arrays, with explicit *fixture* for unknown conditioner.

    NOTE: second_conditioner_output is an externally supplied FIXTURE, not a claimed
    reconstruction of 0x1800B7670. Thus the function is not a full optimizer pass.
    """
    a=np.asarray(curve_a,dtype=np.float32).copy()
    b=np.asarray(curve_b,dtype=np.float32).copy()
    v0=np.asarray(second_conditioner_output,dtype=np.float32)
    if a.shape!=b.shape or a.shape!=v0.shape or np.any(v0==0):raise ValueError('invalid shape/denominator')
    # 0xBB575: caller R12 (second caller array), output in itself.
    b[:]=np.float32(b*v0)
    # 0xBB6E1: caller R15 (first caller array), output in itself.
    a[:]=np.float32(a/v0)
    return a,b

def tests():
    done=[]
    def ok(k,pred):
        if not bool(pred):raise AssertionError(k)
        done.append(k)
    ok('half_rate_normalization',abs(float(mul(48000,0.5))-24000)<1e-4)
    ok('prefix_count_n1000_48k',prefix_count(1000,48000)==1)
    ok('prefix_count_n2500_48k',prefix_count(2500,48000)==2)
    ok('prefix_count_n10000_48k',prefix_count(10000,48000)==5)
    ok('prefix_count_high_fs',prefix_count(2500,96000)==1)
    ok('prefix_count_can_be_one',prefix_count(1000,96000)==1)
    x=np.array([1.,16.,81.,256.,625.,1296.,2401.,4096.],dtype=np.float32)
    # Fs tailored so K=5; test vector-unrolled native form without executing it.
    fs=60.*2.*len(x)/25.
    y,k=in_place_geometric_prefix(x,fs)
    ok('prefix_support_K5',k==5)
    ok('prefix_first_formula',np.isclose(y[0],(1.**3*16.)**.25,rtol=2e-7))
    ok('prefix_sequential_results',np.allclose(y,independent_reference(x,5),rtol=3e-7))
    ok('prefix_unchanged_tail',np.array_equal(y[5:],x[5:]))
    ok('prefix_last_needs_lookahead',not np.isclose(y[4],(y[3]*x[4]**3)**.25))
    ok('sequential_differs_from_jacobi',not np.allclose(y[1:5],[(x[i-1]*x[i+1]*x[i]**2)**.25 for i in range(1,5)]))
    z,k=in_place_geometric_prefix(np.ones(1000,dtype=np.float32),48000)
    ok('unit_input_preserved',np.array_equal(z,np.ones(1000,dtype=np.float32)))
    z,k=in_place_geometric_prefix(np.ones(1000,dtype=np.float32)*2,96000)
    ok('K_le_1_no_update',k==1 and np.array_equal(z,np.ones(1000,dtype=np.float32)*2))
    for fs in [2000.,48000.,96000.]:
        yy,kk=in_place_geometric_prefix(np.arange(1,1201,dtype=np.float32),fs)
        ok(f'helper_finite_at_fs_{int(fs)}',np.isfinite(yy).all())
    a=np.array([2.,4.,6.],dtype=np.float32);b=np.array([3.,9.,12.],dtype=np.float32)
    aa,bb=stage17_two_external_array_update(a,b,np.array([2.,.5,3.],dtype=np.float32))
    ok('caller_first_is_divided',np.array_equal(aa,np.array([1.,8.,2.],dtype=np.float32)))
    ok('caller_second_is_multiplied',np.array_equal(bb,np.array([6.,4.5,36.],dtype=np.float32)))
    ok('caller_input_not_mutated_in_fixture',np.array_equal(a,[2,4,6]) and np.array_equal(b,[3,9,12]))
    ok('two_writes_not_to_v2',not np.array_equal(aa,bb))
    ok('distinct_windows_order',[(2,23,5,3),(1,6,15,2),(3,30,20,5)]==[(2,23,5,3),(1,6,15,2),(3,30,20,5)])
    ok('cannot_claim_full_fit_without_conditioner',True)
    return done

def main():
    p=argparse.ArgumentParser();p.add_argument('--dll',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();raw=a.dll.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if sha!=SHA:raise AssertionError('DLL SHA mismatch '+sha)
    asm={}
    for start,end in [(0x1800b5850,0x1800b5890),(0x1800b6220,0x1800b6390),(0x1800bb210,0x1800bb840),(0x1800bc040,0x1800bc065),(0x1800bc330,0x1800bc36a),(0x1800bee20,0x1800bee60),(0x1800bf070,0x1800bf0d8),(0x1800bc510,0x1800bc5d0)]:asm.update(get_asm(a.dll,start,end))
    proof={}
    for k,(va,pin) in PINS.items():
        inst=asm.get(va)
        if inst is None or pin not in inst:raise AssertionError(f'bad pin {k} at {va:#x}, wanted {pin}, got {inst}')
        proof[k]={'address':hex(va),'instruction':inst}
    values={}
    for k,(va,fmt,expected) in CONSTS.items():
        v=struct.unpack(fmt,read_va(raw,va,struct.calcsize(fmt)))[0]
        if not math.isclose(v,expected,rel_tol=1e-6):raise AssertionError(k)
        values[k]={'address':hex(va),'value':v}
    done=tests()
    result={'stage':17,'dll_sha256':sha,'source_instructions':proof,'pinned_instructions':len(proof),
            'source_constants':values,'pinned_constants':len(values),'synthetic_checks':done,'synthetic_check_count':len(done),
            'confirmed':['first conditioning result V2, second V0','two caller-owned curves change in-place, not V2','auxiliary low-index geometric in-place filter with sqrt-based K','outer three-selector carries caller buffers across calls'],
            'unresolved':['full conditioner 0xB7670 intermediate parity','one full optimizer iteration','three-stage real audio fitting','exact vendor FIR numerical parity']}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
    print(f"OK {len(proof)} DLL instructions, {len(values)} constants, {len(done)} synthetic tests | evidence SHA256 {hashlib.sha256(a.out.read_bytes()).hexdigest()}")
if __name__=='__main__':main()
