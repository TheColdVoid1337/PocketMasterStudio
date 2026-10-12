#!/usr/bin/env python3
"""Static, read-only HTKPA stage-3 check pinned to one user-supplied DLL.

Never loads or executes vendor code; uses GNU objdump + raw PE section mapping.
"""
import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path

EXPECTED_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
IMAGE_BASE=0x180000000

RANGES={
 'spectral_finisher':(0x1800b9b70,0x1800bb210),
 'iterative_fit':(0x1800bb210,0x1800bc6b0),
 'spectral_helper':(0x1800b82b0,0x1800b8400),
 'complex_circular_convolution':(0x1800b4cf0,0x1800b4eb0),
 'basis_helper':(0x1800b52e0,0x1800b5400),
}
PROOFS={
 # (block, VA, exact opcode substring)
 'iter_powf':('iterative_fit',0x1800bb46e,'call   0x18017e158'),
 'iter_clamp_ceiling_5':('iterative_fit',0x1800bb479,'movaps xmm0,xmm11'),
 'iter_clamp_floor_0_2':('iterative_fit',0x1800bb48c,'0x3e4ccccd'),
 'iter_exponent_decay_0_9':('iterative_fit',0x1800bb4be,'mulss  xmm12,DWORD PTR'),
 'iter_elementwise_multiply':('iterative_fit',0x1800bb575,'mulps  xmm1,xmm0'),
 'iter_elementwise_divide':('iterative_fit',0x1800bb6e1,'divps  xmm1,xmm0'),
 'iter_first_frequency_helper':('iterative_fit',0x1800bb4d9,'call   0x1800b7670'),
 'iter_further_convolution':('iterative_fit',0x1800bbb5b,'call   0x1800b5a30'),
 'iter_nonlinearity':('iterative_fit',0x1800bbcc9,'call   0x1800be700'),
 'iter_filter_design_a':('iterative_fit',0x1800bc055,'call   0x1800b82b0'),
 'iter_filter_design_b':('iterative_fit',0x1800bc3c5,'call   0x1800b82b0'),
 'iter_filter_512_check':('iterative_fit',0x1800bc437,'cmp    rdi,0x200'),
 'iter_filter_512_scale':('iterative_fit',0x1800bc440,'mulss  xmm7,DWORD PTR'),
 'iter_logf':('iterative_fit',0x1800bc41c,'call   0x18017e14c'),
 'iter_close_step':('iterative_fit',0x1800bc5c2,'jne    0x1800bb440'),
 'finish_0_1sec_support':('spectral_finisher',0x1800b9bcb,'mulsd  xmm0,xmm12'),
 'finish_saturator':('spectral_finisher',0x1800ba019,'call   0x1800be700'),
 'finish_cosf_taper':('spectral_finisher',0x1800ba820,'call   0x18017e11c'),
 'finish_sqrt_magnitude':('spectral_finisher',0x1800ba97b,'call   0x18017e170'),
 'finish_stable_spectral_ratio':('spectral_finisher',0x1800bac9a,'divpd  xmm3,xmm2'),
 'finish_ratio_clip_upper':('spectral_finisher',0x1800baeb3,'0x41200000'),
 'finish_ratio_clip_lower':('spectral_finisher',0x1800baec6,'0x3dcccccd'),
 'finish_complex_transform':('spectral_finisher',0x1800ba8a3,'call   0x1800b4cf0'),
 'finish_filter_step':('spectral_finisher',0x1800baef9,'call   0x1800b7e10'),
 'finish_output_amplitude_norm':('spectral_finisher',0x1800bb0e2,'divss  xmm7,xmm0'),
 'hamming_cosf':('spectral_helper',0x1800b83ca,'call   0x18017e11c'),
 'hamming_multiply_046':('spectral_helper',0x1800b83cf,'mulss  xmm0,xmm9'),
 'hamming_subtract_054':('spectral_helper',0x1800b83d8,'subss  xmm1,xmm0'),
 'circular_modulus':('complex_circular_convolution',0x1800b4de6,'idiv   r10d'),
 'circular_complex_imag_sign':('complex_circular_convolution',0x1800b4e25,'subss  xmm6,xmm5'),
 'basis_inv_N':('basis_helper',0x1800b5322,'divss  xmm7,xmm0'),
}
CONSTANTS={
 'ten_percent_second':(0x18024c7a0,'<d'),
 'iter_exponent_decay':(0x18024c654,'<f'),
 'iter_ceil':(0x18024ccd0,'<f'),
 'iter_floor':(0x18024c7e0,'<d'),
 'finish_ratio_ceil':(0x18024cd24,'<f'),
 'finish_ratio_floor':(0x18024c7a0,'<d'),
 'hamming_a':(0x18024c5d4,'<f'),
 'hamming_b':(0x18024c5b0,'<f'),
 'hamming_2pi':(0x18024ccf0,'<f'),
 'eval_sample_count_reciprocal':(0x18024c4f0,'<f'),
 'freq_ratio_eps':(0x18024c588,'<d'),
}

def pe_sections(b):
 if b[:2]!=b'MZ': raise AssertionError('not MZ')
 pe=struct.unpack_from('<I',b,0x3c)[0]
 if b[pe:pe+4]!=b'PE\0\0': raise AssertionError('not PE')
 n=struct.unpack_from('<H',b,pe+6)[0]
 opt=struct.unpack_from('<H',b,pe+20)[0]
 s=pe+24+opt
 return [struct.unpack_from('<IIII',b,s+40*i+8) for i in range(n)]

def va_read(b,sec,va,fmt):
 rva=va-IMAGE_BASE
 for vsize,rbase,rawsize,rawfile in sec:
  if rbase<=rva and rva+struct.calcsize(fmt)<=rbase+rawsize:
   return struct.unpack_from(fmt,b,rawfile+rva-rbase)[0]
 raise ValueError(f'Invalid VA: {va:x}')

def disasm(dll,lo,hi):
 p=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',
  f'--start-address={hex(lo)}',f'--stop-address={hex(hi)}',str(dll)],
  capture_output=True,text=True,check=True)
 return [s.strip() for s in p.stdout.splitlines() if re.match(r'^\s*[0-9a-fA-F]+:',s)]

def main():
 a=argparse.ArgumentParser();a.add_argument('dll',type=Path);a.add_argument('--out',type=Path,default=Path('stage3_evidence.json'))
 arg=a.parse_args()
 b=arg.dll.read_bytes();sha=hashlib.sha256(b).hexdigest()
 if sha!=EXPECTED_SHA:raise SystemExit(f'Binary SHA mismatch: {sha}; expected {EXPECTED_SHA}')
 sec=pe_sections(b)
 blocks={k:disasm(arg.dll,*v) for k,v in RANGES.items()}
 found={}
 for name,(block,addr,frag) in PROOFS.items():
  lines=[l for l in blocks[block] if l.startswith(f'{addr:x}:')]
  if len(lines)!=1 or frag not in lines[0]:
   raise AssertionError(f'{name} at {addr:x} with {frag}: {lines}')
  found[name]=lines[0]
 values={k:va_read(b,sec,addr,fmt) for k,(addr,fmt) in CONSTANTS.items()}
 for name,expected in {'ten_percent_second':.1,'iter_exponent_decay':.9,'hamming_a':.54,'hamming_b':.46,
                        'eval_sample_count_reciprocal':1/512,'finish_ratio_ceil':10,'finish_ratio_floor':.1}.items():
  if abs(values[name]-expected)>1e-5:raise AssertionError((name,values[name],expected))
 # The imported CRT names (not hypothetical labels) establish powf/logf/sqrtf/cosf.
 imports=subprocess.run(['objdump','-p',str(arg.dll)],capture_output=True,text=True,check=True).stdout
 for addr,name in [('0018ba10','powf'),('0018ba00','logf'),('0018ba38','sqrtf'),('0018b990','cosf')]:
  if not re.search(r'\b'+addr+r'\s+<none>\s+\S+\s+'+name+r'\b',imports):raise AssertionError((addr,name))
 result={'sha256':sha,'status':'static only; DLL NOT executed','verified_instructions_count':len(found),
         'instructions':found,'constants':values,
         'import_thunks':{'powf':'0x18017e158','logf':'0x18017e14c','sqrtf':'0x18017e170','cosf':'0x18017e11c'},
         'branches':{k:[hex(x) for x in v] for k,v in RANGES.items()},
         'caveat':'Identified local mathematical operations, NOT full end-to-end equivalent or exact filter mapping.'}
 arg.out.parent.mkdir(parents=True,exist_ok=True)
 arg.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print('PASS',len(found),'independently verified instructions; four imported math funcs; eleven pinned constants')
 print('Saved',arg.out)

if __name__=='__main__':main()
