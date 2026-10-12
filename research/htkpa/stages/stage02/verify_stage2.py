#!/usr/bin/env python3
"""Read-only, pinned-binary checks for HTKPA fitting stage 2.

Never loads or executes DLL. Uses objdump -d -M intel and objdump -p
for binary static data, direct instruction proof, and PE import verification.
"""
import argparse, hashlib, json, re, struct, subprocess
from pathlib import Path

SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BASE=0x180000000
RANGES={
 'fit_nonlinearity':(0x1800bdbe0,0x1800be700),
 'iir_preprocessing':(0x1800bd490,0x1800bdbe0),
 'rate_specific_preprocessing':(0x1800bc6b0,0x1800bd490),
 'three_region_processing':(0x1800bb210,0x1800bc6b0),
 'nonlinear_forward':(0x180028690,0x18002870e),
 'nonlinear_buffer_update':(0x1800be700,0x1800be824),
 'htkpa_caller':(0x1800be830,0x1800bf55d),
}

def sections(buf):
 assert buf[:2]==b'MZ'
 pe=struct.unpack_from('<I',buf,0x3c)[0]
 assert buf[pe:pe+4]==b'PE\0\0'
 n, opt=struct.unpack_from('<H',buf,pe+6)[0],struct.unpack_from('<H',buf,pe+20)[0]
 off=pe+24+opt
 return [struct.unpack_from('<IIII',buf,off+40*i+8) for i in range(n)]

def at(buf,sec,va,fmt):
 rva=va-BASE
 for vs,base,rs,raw in sec:
  if base<=rva and rva+struct.calcsize(fmt)<=base+rs:
   return struct.unpack_from(fmt,buf,raw+rva-base)[0]
 raise ValueError(f'unmapped VA {va:x}')

def capture(lines,lo,hi):
 out=[]
 for line in lines:
  m=re.match(r'^\s*([0-9a-fA-F]+):\s+',line)
  if m and lo<=int(m.group(1),16)<hi:out.append(line.strip())
 return out

def expect(lines, address, fragment):
 tgt=f'{address:x}:'
 a=[s for s in lines if s.startswith(tgt)]
 if len(a)!=1 or fragment not in a[0]:
  raise AssertionError(f'Expected {tgt} containing {fragment}; found {a}')
 return a[0]

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('dll',type=Path)
 ap.add_argument('--cached-disasm',type=Path,help='Full objdump -d -M intel cached disassembly')
 ap.add_argument('--out',type=Path,default=Path('stage2_evidence.json'))
 a=ap.parse_args()
 buf=a.dll.read_bytes(); sha=hashlib.sha256(buf).hexdigest()
 if sha!=SHA:raise SystemExit('Wrong DLL SHA256; this analysis is pinned to one build')
 sec=sections(buf)
 if a.cached_disasm:
  lines=a.cached_disasm.read_text(encoding='utf-8',errors='replace').splitlines()
 else:
  p=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',
     '--start-address=0x180028690','--stop-address=0x1800bf560',str(a.dll)],
     check=True,capture_output=True,text=True)
  lines=p.stdout.splitlines()
 imp=subprocess.run(['objdump','-p',str(a.dll)],check=True,capture_output=True,text=True).stdout
 import_exp=bool(re.search(r'0018b9a8\s+<none>\s+\S+\s+expf',imp))
 if not import_exp:raise AssertionError('expf import at RVA 18b9a8 not found')
 blocks={k:capture(lines,*r) for k,r in RANGES.items()}
 proofs={}
 checks={
  'nl_input_positive':('nonlinear_forward',0x18002869d,'comiss xmm5,xmm4'),
  'nl_positive_rate':('nonlinear_forward',0x1800286b2,'mulss  xmm2,xmm5'),
  'nl_positive_exp':('nonlinear_forward',0x1800286c0,'call   0x18017e12e'),
  'nl_positive_subtract':('nonlinear_forward',0x1800286cd,'subss  xmm1,xmm0'),
  'nl_positive_amp':('nonlinear_forward',0x1800286d1,'mulss  xmm1,xmm7'),
  'nl_negative_rate':('nonlinear_forward',0x1800286e7,'mulss  xmm3,xmm5'),
  'nl_negative_exp':('nonlinear_forward',0x1800286ee,'call   0x18017e12e'),
  'nl_negative_subtract':('nonlinear_forward',0x1800286f3,'subss  xmm0,DWORD PTR'),
  'nl_negative_amp':('nonlinear_forward',0x180028700,'mulss  xmm0,xmm6'),
  'amp_pos_store':('fit_nonlinearity',0x1800be661,'movss  DWORD PTR [rax],xmm0'),
  'amp_neg_store':('fit_nonlinearity',0x1800be676,'movss  DWORD PTR [rax],xmm0'),
  'rate_pos_store':('fit_nonlinearity',0x1800be682,'movss  DWORD PTR [rax],xmm10'),
  'rate_neg_store':('fit_nonlinearity',0x1800be68f,'movss  DWORD PTR [rax],xmm9'),
  'iir_feedback1':('iir_preprocessing',0x1800bd564,'mulsd  xmm1,QWORD PTR [rdi+0x232f0]'),
  'iir_feedback2':('iir_preprocessing',0x1800bd56f,'mulsd  xmm0,QWORD PTR [rdi+0x232f8]'),
  'iir_feedforward0':('iir_preprocessing',0x1800bd599,'mulsd  xmm0,QWORD PTR [rdi+0x232d8]'),
  'iir_feedforward1':('iir_preprocessing',0x1800bd591,'mulsd  xmm1,QWORD PTR [rdi+0x232e0]'),
  'iir_feedforward2':('iir_preprocessing',0x1800bd5a1,'mulsd  xmm2,QWORD PTR [rdi+0x232e8]'),
  'rate_44100':('rate_specific_preprocessing',0x1800bc739,'ucomiss xmm0,DWORD PTR'),
  'rate_48000':('rate_specific_preprocessing',0x1800bc7ef,'ucomiss xmm0,DWORD PTR'),
  'rate_96000':('rate_specific_preprocessing',0x1800bc89e,'ucomiss xmm0,DWORD PTR'),
  'pass_select_2':('htkpa_caller',0x1800bee9f,'0x2'),
  'pass_select_1':('htkpa_caller',0x1800beeaa,'0x1'),
  'pass_select_3':('htkpa_caller',0x1800beeb5,'0x3'),
  'pass_call':('htkpa_caller',0x1800bf0c9,'call   0x1800bb210'),
  'pass_bound':('htkpa_caller',0x1800bf0d1,'cmp    rbx,0x3'),
 }
 for name,(block,addr,substr) in checks.items():proofs[name]=expect(blocks[block],addr,substr)
 constants={
  'probe_rate_1':(0x18024cdf0,'<f'),
  'probe_rate_2':(0x18024cdf4,'<f'),
  'probe_rate_3':(0x18024cdf8,'<f'),
  'fitting_rate_factor_start':(0x18024c608,'<f'),
  'fitting_rate_factor_step':(0x18024c748,'<d'),
  'fitting_rate_factor_end':(0x18024c9a8,'<d'),
  'rate_preprocess_constant_1':(0x18024c4f4,'<f'),
  'rate_preprocess_constant_2':(0x18024ce2c,'<f'),
  'positive_nl_unity':(0x18024c6a0,'<f'),
  'sign_bit_flip_mask':(0x18024d600,'<I'),
 }
 value={k:at(buf,sec,va,fmt) for k,(va,fmt) in constants.items()}
 if [value[k] for k in ['probe_rate_1','probe_rate_2','probe_rate_3']]!=[44100.,48000.,96000.]:
  raise AssertionError('Rate-specific constants differ from expected')
 assert abs(value['fitting_rate_factor_start']-0.8)<1e-5
 assert value['fitting_rate_factor_step']==0.05
 assert value['fitting_rate_factor_end']==1.2
 # from additional disasm: the two separate positive/negative loops
 for label,address,fragment in [
  ('rate_sweep_pos',0x1800be529,'addsd  xmm0,xmm2'),
  ('rate_sweep_neg',0x1800be631,'addsd  xmm0,xmm2'),
  ('saturator_scalar_positive',0x1800be4ba,'call   0x18017e12e'),
  ('saturator_scalar_negative',0x1800be4d5,'call   0x18017e12e')]:
  proofs[label]=expect(blocks['fit_nonlinearity'],address,fragment)
 output={'dll_sha256':sha,'status':'Static analysis only — no DLL execution',
   'imported_expf_rva':hex(0x18b9a8),'call_thunk_expf_va':hex(0x18017e12e),
   'constants':value,'verified_instructions':proofs,
   'code_ranges':{k:[hex(x) for x in rr] for k,rr in RANGES.items()},
   'inference':{
    'saturator':'f(x) = Pmax*(1-exp(-Prate*x)) if x>0, else Nmax*(exp(Nrate*x)-1)',
    'parameter_fit':'0x1800bdbe0 stores gains at context+0x243f8..0x24404, with 0.8:0.05:1.2 search factors',
    'iir_preprocess':'0x1800bd490 has direct-form-II style second-order recursive stages and separate coefficient banks',
    'rate_branches':'0x1800bc6b0 checks 44100,48000,96000 and loads separate coefficient vectors',
    'loop':'Three calls to 0x1800bb210 via selectors 2,1,3; NOT proof of repeating an identical fit.',
    'unsolved':'Design/filter fit in 0x1800bb210 and 0x1800b9b70, coeff table derivation, exact calibration',
   }}
 a.out.parent.mkdir(exist_ok=True,parents=True)
 a.out.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(f'PASS {len(proofs)} pinned assembly checks; expf import confirmed; sample-rate banks = 44100/48000/96000')
 print('PASS scalar exponential saturator, parameter writes and 3 selectors (2,1,3)')
 print('Saved evidence:',a.out)

if __name__=='__main__':main()
