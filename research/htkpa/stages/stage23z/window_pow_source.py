"""Stage23Z: fix Stage23I FIR's omitted pow(window, gamma).

Static original PE instruction/import proof and source-derived coefficients
against optional user-private native pre-FFT dump. No Windows DLL execution.
No fitted coefficients or bitwise native parity claim.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re,subprocess,sys
from pathlib import Path
from array import array
STAGES=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGES/'stage23i'))
import native_fir_coefficients as prior
DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
NATIVE_SHA='649adeb70df4bb17f73ca09c0e4bc8bd3511271fa388d989bb2094ead22b0770'
STAGE23I_SHA='ff4b587594a156df2fe8fd34a7a639eeb09e3cc9a59fcfba93afa17737d241be'
N=4096
PINS={
 0x18000B8AF:'andps xmm9,xmmword ptr [rip+0x241d29]',
 0x18000B8C1:'movsd qword ptr [rsp+0x50],xmm9',
 0x18000B8D0:'movsd xmm0,qword ptr [rip+0x241348]',
 0x18000B8D8:'movsd qword ptr [rbp-0x10],xmm0',
 0x18000B8E2:'movsd qword ptr [rbp-0x8],xmm0',
 0x18000B8F9:'movsd qword ptr [rbp+0x0],xmm0',
 0x18000B981:'call 0x180014810',
 0x18001487F:'movsd xmm6,qword ptr [rcx+0x20]',
 0x180014884:'call 0x180008fd0',
 0x180014953:'movaps xmm1,xmm6',
 0x18001496E:'call 0x18017e152',
 0x180014978:'subsd xmm1,qword ptr [rbx+0x10]',
 0x180014986:'mulsd xmm1,xmm0',
 0x1800149A0:'movsd xmm6,qword ptr [rbx+0x20]',
 0x1800149A8:'call 0x180008fd0',
 0x1800149B2:'movaps xmm1,xmm6',
 0x1800149C4:'call 0x18017e152',
 0x180014A0D:'mulsd xmm3,xmm0',
 0x180008FD6:'mov eax,dword ptr [rcx+0x58]',
 0x180009011:'call 0x18017e16a',
 0x180009016:'mulsd xmm0,qword ptr [rbx+0xc0]',
 0x18000901E:'call 0x180008e90',
 0x180009023:'divsd xmm0,qword ptr [rbx+0xc8]',
 0x18017E152:'jmp qword ptr [rip+0xd8b0]',
}
RANGES=((0x18000B8A0,0x18000B902),(0x18000B970,0x18000B98A),
 (0x180014875,0x18001498F),(0x18001499C,0x180014A31),
 (0x180008FD0,0x180009030),(0x18017E14C,0x18017E158))
def verify_pe(dll):
 assert hashlib.sha256(dll.read_bytes()).hexdigest()==DLL_SHA
 seen={}
 for lo,hi in RANGES:
  txt=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for row in txt.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',row)
   if m:seen[int(m[1],16)]=' '.join(m[2].lower().split())
 for va,frag in PINS.items():assert frag in seen.get(va,''),(hex(va),frag,seen.get(va))
 imports=subprocess.check_output(['objdump','-p',str(dll)],text=True)
 assert re.search(r'0018ba08\s+<none>\s+00fe\s+pow\b',imports)
 assert re.search(r'0018ba18\s+<none>\s+0112\s+sin\b',imports)
 return len(PINS)
def f64le(values):
 ar=array('d',values)
 if sys.byteorder!='little':ar.byteswap()
 return ar.tobytes()
def calculate(dll):
 data,c=prior.verify(dll)
 meta=prior.reproduce(data);g=meta['G'];gf=meta['G_before_floor']
 assert g==708
 theta=(1-meta['phase_correction'])*math.pi*meta['upstream_params']['cutoff']
 gamma=abs(meta['intermediate_y']);beta=c(0x18024CC20)
 assert beta==125.0 and gamma>0
 denominator=prior.bessel_native_approx(beta,c)
 old=[];corrected=[];fast=0.;prev=math.sin(-theta);step=2*math.cos(theta)
 for i in range(g+1):
  t=i/gf
  window=prior.bessel_native_approx(beta*math.sqrt(1-t*t),c)/denominator
  power=math.pow(window,gamma)
  if i==0:
   old_val=theta*math.sin(gamma)/math.pi*window
   corrected_val=theta*power/math.pi
  else:
   nxt=fast*step-prev
   prev,fast=fast,nxt
   old_val=fast*math.sin(gamma)/i/math.pi*window
   corrected_val=fast*power/i/math.pi
  old.append(old_val);corrected.append(corrected_val)
 def normalize(raw):
  centered=list(reversed(raw[1:]))+raw
  acc=0.
  for v in centered:acc+=v
  scale=(4./N)/acc
  output=[0.]*N
  for i,v in enumerate(raw):output[i]=v*scale
  for i in range(1,g+1):output[N-i]=output[i]
  return output
 old=normalize(old);corrected=normalize(corrected)
 assert hashlib.sha256(f64le(old)).hexdigest()==STAGE23I_SHA,'old candidate SHA drift'
 return meta,gamma,beta,old,corrected
def run(dll,native=None):
 pins=verify_pe(dll);meta,gamma,beta,old,corrected=calculate(dll)
 result={'stage':'Stage23Z','status':'SOURCE_CORRECTION_NUMERIC_NATIVE_CHECK',
 'dll_sha256':DLL_SHA,'new_instruction_pins':pins,
 'pow_import_iat':'0x18018BA08','pow_thunk':'0x18017E152',
 'sin_import_iat':'0x18018BA18','generator':'0x180014810',
 'generator_exponent':gamma,'generator_bessel_beta':beta,
 'old_stage23i_candidate_sha256':STAGE23I_SHA,
 'corrected_candidate_sha256':hashlib.sha256(f64le(corrected)).hexdigest(),
 'corrected_equation':'sin(theta*n)/(n*pi) * pow(I0(beta*sqrt(1-(n/Gf)^2))/I0(beta), gamma), normalized to sum=1/1024 (n=0 uses theta/pi)',
 'known_limit':'No Windows CRT/libm/SSE bit parity or source-to-native coefficient equality',
 'native_check':'not_provided'}
 if native is not None:
  raw=native.read_bytes()
  assert hashlib.sha256(raw).hexdigest()==NATIVE_SHA
  assert len(raw)==N*8
  observed=array('d');observed.frombytes(raw)
  if sys.byteorder!='little':observed.byteswap()
  import numpy as np
  actual=np.asarray(observed,dtype=np.float64)
  old=np.asarray(old,dtype=np.float64);corrected=np.asarray(corrected,dtype=np.float64)
  e0=np.abs(old-actual);e1=np.abs(corrected-actual)
  result.update({'native_check':'private_original_runtime_buffer_compared',
   'native_coeff_sha256':NATIVE_SHA,
   'old_error_max':float(e0.max()),'old_error_rms':float(np.sqrt(np.mean(e0*e0))),
   'corrected_error_max':float(e1.max()),'corrected_error_rms':float(np.sqrt(np.mean(e1*e1))),
   'max_error_improvement_factor':float(e0.max()/e1.max()),
   'rms_error_improvement_factor':float(np.sqrt(np.mean(e0*e0))/np.sqrt(np.mean(e1*e1))),
   'active_taps_differ_after_correction':int(np.count_nonzero(corrected[:709]!=actual[:709]))*2-1,
   'examples':[{'tap':i,'native':float(actual[i]),'old':float(old[i]),'corrected':float(corrected[i])} for i in (0,10,100,400,600)]})
  assert result['corrected_error_max']<1e-9
  assert result['max_error_improvement_factor']>1000
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True)
 p.add_argument('--native-pre-fft',type=Path);p.add_argument('--out',type=Path)
 a=p.parse_args();r=run(a.dll,a.native_pre_fft)
 txt=json.dumps(r,indent=2)+'\n'
 if a.out:a.out.write_text(txt,encoding='utf8')
 print(txt)
