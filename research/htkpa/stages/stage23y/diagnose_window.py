"""Stage23Y: source-first isolate the Stage23I/native FIR window discrepancy.

Requires SHA-pinned original DLL and repo Stage23H/I code. An optional user-private
native pre-FFT dump enables measured comparisons; never stores/dumps native taps
in repo. Diagnostic only: a native coefficient file is NOT a fit target.
"""
import argparse, hashlib, json, math, re, struct, subprocess, sys
from pathlib import Path
from array import array

STAGES=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGES/'stage23i'))
import native_fir_coefficients as stage23i

DLL_SHA=stage23i.DLL_SHA
NATIVE_SHA='649adeb70df4bb17f73ca09c0e4bc8bd3511271fa388d989bb2094ead22b0770'
CANDIDATE_SHA='ff4b587594a156df2fe8fd34a7a639eeb09e3cc9a59fcfba93afa17737d241be'
PINS={
 0x18000B838:'movsd qword ptr [rsp+0x30],xmm8',
 0x18000B8D0:'movsd xmm0,qword ptr [rip+0x241348]',
 0x18000B8D8:'movsd qword ptr [rbp-0x10],xmm0',
 0x18000B8DD:'call 0x180008e90',
 0x18000B8E2:'movsd qword ptr [rbp-0x8],xmm0',
 0x18000B8F9:'movsd qword ptr [rbp+0x0],xmm0',
 0x18000B981:'call 0x180014810',
 0x180008FD6:'mov eax,dword ptr [rcx+0x58]',
 0x180008FF1:'divsd xmm0,qword ptr [rcx]',
 0x180008FF5:'addsd xmm0,qword ptr [rcx+0xd0]',
 0x180009001:'subsd xmm1,xmm0',
 0x180009011:'call 0x18017e16a',
 0x180009016:'mulsd xmm0,qword ptr [rbx+0xc0]',
 0x18000901E:'call 0x180008e90',
 0x180009023:'divsd xmm0,qword ptr [rbx+0xc8]',
}
RANGES=[(0x18000B830,0x18000B843),(0x18000B8C8,0x18000B906),
        (0x18000B975,0x18000B988),(0x180008FD0,0x180009031)]

def pins(dll):
 ins={}
 for lo,hi in RANGES:
  out=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
       f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in out.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if m:ins[int(m[1],16)]=' '.join(m[2].lower().split())
 for addr,fragment in PINS.items():assert fragment in ins.get(addr,''),(hex(addr),ins.get(addr))
 return len(PINS)

def source_candidate(data,c):
 m=stage23i.reproduce(data)
 g=m['G'];gf=m['G_before_floor'];assert g==708
 theta=(1-m['phase_correction'])*math.pi*m['upstream_params']['cutoff']
 sine=math.sin(m['intermediate_y']);beta=c(0x18024CC20)
 assert beta==125.
 denominator=stage23i.bessel_native_approx(beta,c)
 fast=0.;fast_prev=math.sin(-theta);cosfast=2.*math.cos(theta)
 raw=[]
 for n in range(g+1):
  t=n/gf
  window=stage23i.bessel_native_approx(beta*math.sqrt(1-t*t),c)/denominator
  if n==0:sample=theta*sine/math.pi*window
  else:
   nextfast=fast*cosfast-fast_prev;fast_prev,fast=fast,nextfast
   sample=fast*sine/n/math.pi*window
  raw.append(sample)
 centered=list(reversed(raw[1:]))+raw
 total=0.
 for v in centered:total+=v
 size=2*(1<<(2*g).bit_length())
 scale=(4./size)/total
 out=array('d',[0.]*size)
 for n,v in enumerate(raw):out[n]=v*scale
 for n in range(1,g+1):out[size-n]=out[n]
 if sys.byteorder!='little':out.byteswap()
 payload=out.tobytes();assert hashlib.sha256(payload).hexdigest()==CANDIDATE_SHA
 return out,m,theta,beta

def diagnose(dll,native=None):
 assert hashlib.sha256(dll.read_bytes()).hexdigest()==DLL_SHA
 count=pins(dll)
 data,c=stage23i.verify(dll)
 candidate,meta,theta,beta=source_candidate(data,c)
 result={'original_dll_sha256':DLL_SHA,'new_source_instruction_pins':count,
  'stage23i_candidate_sha256':CANDIDATE_SHA,'candidate_beta_parameter':beta,
  'candidate_angle_radians':theta,'candidate_half_length':meta['G'],
  'candidate_g_before_floor':meta['G_before_floor'],
  'candidate_center':candidate[0],
  'source_window_sites':{'beta_literal':'0x18000B8D0','generator':'0x180014810',
    'window_routine':'0x180008FD0','numerator_beta_field':'context+0xc0',
    'denominator_field':'context+0xc8','index_offset_field':'context+0xd0'},
  'source_comparison':'Stage23I candidate byte-identical to published Stage23I SHA; Windows CRT parity not established',
  'native_audit_status':'NOT_SUPPLIED','limits':'No DLL native execution in this script; a user-private RAM dump is optional.'}
 if native is None:return result
 b=native.read_bytes();assert hashlib.sha256(b).hexdigest()==NATIVE_SHA,'unexpected native coefficient dump'
 assert len(b)==4096*8
 from array import array as A
 observed=A('d');observed.frombytes(b)
 if sys.byteorder!='little':observed.byteswap()
 assert sum(v!=0 for v in observed)==1417
 active=list(range(709))+list(range(4096-708,4096))
 diffs=[candidate[i]-observed[i] for i in range(4096)]
 rms=math.sqrt(sum(x*x for x in diffs)/4096)
 assert abs(max(map(abs,diffs))-1.6025453961367097e-06)<1e-16
 assert all(candidate[i]==0==observed[i] for i in range(709,4096-708))
 checks=[]
 for i in (10,50,100,200,400,600):
  sinc=math.sin(theta*i)/(theta*i)
  observed_window=observed[i]/observed[0]/sinc
  source_window=stage23i.bessel_native_approx(beta*math.sqrt(1-(i/meta['G_before_floor'])**2),c)/stage23i.bessel_native_approx(beta,c)
  checks.append({'index':i,'candidate_f64':candidate[i], 'native_f64':observed[i],
   'native_envelope_over_source_sinc':observed_window,
   'source_kaiser_envelope':source_window,
   'envelope_ratio_native_to_candidate':observed_window/source_window})
 result.update({'native_audit_status':'NATIVE_RAM_DUMP_COMPARED',
  'native_pre_fft_sha256':NATIVE_SHA,'native_nonzero_coefficients':len(active),
  'different_active_coefficients':sum(candidate[i]!=observed[i] for i in active),
  'max_abs_error':max(map(abs,diffs)),'all_buffer_rms_error':rms,
  'native_center':observed[0], 'native_sum':sum(observed),
  'relative_envelope_checks':checks,
  'conclusion':'Source candidate decays far faster away from center; cannot be explained by f64 rounding; do not invent a corrected beta.',
  'next_source_or_native_target':'Observe actual generator state/context at 0x180014810 and first 0x180008FD0: fields +0,+0x58,+0xc0,+0xc8,+0xd0; then verify oscillator and 0x180014810 output BEFORE 0x18000B9C0 normalization.'})
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True)
 p.add_argument('--native-pre-fft',type=Path,default=None,help='private 4096-double native coeff input, never committed')
 p.add_argument('--out',type=Path,help='optional sanitized summary JSON (no raw samples)')
 args=p.parse_args();result=diagnose(args.dll,args.native_pre_fft)
 txt=json.dumps(result,indent=2)+'\n'
 if args.out:args.out.write_text(txt)
 print(txt)
