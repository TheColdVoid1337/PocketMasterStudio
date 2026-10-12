"""Stage24A: source-pin FIR constructor/generator parameter lineage.

Optional private native coefficient dump is a diagnostic negative control,
not a source of accepted/fitted parameters. Does not execute vendor DLL.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, subprocess, sys
from array import array
from pathlib import Path

S=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(S/'stage23z'))
sys.path.insert(0,str(S/'stage23i'))
import window_pow_source as z
import native_fir_coefficients as prior

SHA=z.DLL_SHA
NATIVE_SHA=z.NATIVE_SHA
PINS={
 0x18000CF3C:'movsd xmm6,qword ptr [rip+0x23fd24]',
 0x18000CF44:'movsd xmm7,qword ptr [rip+0x23faec]',
 0x18000CFD3:'cvtss2sd xmm2,xmm8',
 0x18000CFDB:'cvtss2sd xmm1,xmm9',
 0x18000CFE0:'movsd qword ptr [rsp+0x28],xmm6',
 0x18000CFE6:'movsd qword ptr [rsp+0x20],xmm7',
 0x18000CFF3:'call 0x180011b60',
 0x180011BCC:'movaps xmm9,xmm2',
 0x180011BD0:'movaps xmm8,xmm1',
 0x180011C83:'comisd xmm9,xmm8',
 0x180011C8A:'movaps xmm6,xmm11',
 0x180011C94:'mulsd xmm6,xmm11',
 0x180011C99:'divsd xmm6,xmm8',
 0x180011CB4:'movsd xmm12,qword ptr [rsp+0x158]',
 0x180011CCC:'movsd qword ptr [rsp+0x20],xmm13',
 0x180011CD3:'movaps xmm2,xmm12',
 0x180011CD7:'movsd xmm1,qword ptr [rsp+0x150]',
 0x180011CE0:'movaps xmm0,xmm6',
 0x180011CE3:'call 0x18000bb80',
 0x18000BBF1:'movsd xmm0,qword ptr [rbx]',
 0x18000BBFE:'movsd xmm0,qword ptr [rbx+0x8]',
 0x18000BC0B:'movsd xmm0,qword ptr [rbx+0x10]',
 0x18000BCF1:'movsd qword ptr [rbx],xmm8',
 0x18000BCF6:'movsd qword ptr [rbx+0x8],xmm7',
 0x18000BCFB:'movsd qword ptr [rbx+0x10],xmm6',
 0x18000BD03:'movsd qword ptr [rbx+0x20],xmm9',
 0x18000BD12:'call 0x18000b0e0',
 0x18000B821:'subsd xmm11,xmm6',
 0x18000B826:'divsd xmm8,qword ptr [rdi]',
 0x18000B82B:'mulsd xmm11,qword ptr [rip+0x24124c]',
 0x18000B838:'movsd qword ptr [rsp+0x30],xmm8',
 0x18000B83F:'mulsd xmm11,qword ptr [rdi]',
 0x18000B844:'movsd qword ptr [rsp+0x48],xmm11',
 0x18000B854:'xorps xmm0,xmm0',
 0x18000B857:'xorps xmm7,xmm7',
 0x18000B8BB:'movsd qword ptr [rsp+0x40],xmm7',
 0x18000B8C1:'movsd qword ptr [rsp+0x50],xmm9',
 0x18000B8C8:'mov dword ptr [rbp-0x78],esi',
 0x18000B8D8:'movsd qword ptr [rbp-0x10],xmm0',
 0x18000B8E2:'movsd qword ptr [rbp-0x8],xmm0',
 0x18000B8F9:'movsd qword ptr [rbp+0x0],xmm0',
 0x18000B981:'call 0x180014810',
 0x180014824:'movsd xmm1,qword ptr [rcx+0x28]',
 0x18001487F:'movsd xmm6,qword ptr [rcx+0x20]',
 0x180014884:'call 0x180008fd0',
 0x180014953:'movaps xmm1,xmm6',
 0x18001496E:'call 0x18017e152',
 0x180008FD6:'mov eax,dword ptr [rcx+0x58]',
 0x180008FF1:'divsd xmm0,qword ptr [rcx]',
 0x180008FF5:'addsd xmm0,qword ptr [rcx+0xd0]',
 0x180009016:'mulsd xmm0,qword ptr [rbx+0xc0]',
 0x180009023:'divsd xmm0,qword ptr [rbx+0xc8]',
}
RANGES=[(0x18000CF30,0x18000CFFF),(0x180011BC0,0x180011CF0),
 (0x18000BB80,0x18000BD18),(0x18000B810,0x18000B850),
 (0x18000B850,0x18000B901),(0x18000B970,0x18000B988),
 (0x180014820,0x180014890),(0x180014940,0x180014980),
 (0x180008FD0,0x180009030)]
def verify_source(dll):
 assert hashlib.sha256(dll.read_bytes()).hexdigest()==SHA
 asm={}
 for lo,hi in RANGES:
  stdout=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',
   f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],text=True)
  for line in stdout.splitlines():
   m=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',line)
   if m:asm[int(m[1],16)]=' '.join(m[2].lower().split())
 for addr,fragment in PINS.items():
  assert fragment in asm.get(addr,''),(hex(addr),fragment,asm.get(addr))
 return len(PINS)
def native_ratio_gate(dll,native):
 # Diagnostic only. NEVER substitute native-inferred theta for source theta.
 meta,gamma,beta,old,corrected=z.calculate(dll)
 b=native.read_bytes();assert len(b)==4096*8
 assert hashlib.sha256(b).hexdigest()==NATIVE_SHA
 taps=array('d');taps.frombytes(b)
 if sys.byteorder!='little':taps.byteswap()
 data,c=prior.verify(dll)
 gf=meta['G_before_floor']
 f=lambda i: prior.bessel_native_approx(beta*math.sqrt(1-(i/gf)**2),c)
 w1=math.pow(f(1)/f(0),gamma);w2=math.pow(f(2)/f(0),gamma)
 phase=(1-meta['phase_correction'])*math.pi*meta['upstream_params']['cutoff']
 predicted_ratio=corrected[2]/corrected[1]
 observed_ratio=taps[2]/taps[1]
 conditional_phase=math.acos(observed_ratio*w1/w2)
 delta=conditional_phase-phase
 assert abs(delta)>1e-6 and abs(delta)<5e-6
 err=[v-t for v,t in zip(corrected,taps)]
 return {'private_native_sha256':NATIVE_SHA,'native_to_source_tap2_over_tap1':{
  'native_ratio':observed_ratio,'stage23z_ratio':predicted_ratio},
  'source_phase_radians':phase,
  'conditional_phase_from_native_tap_ratio_radians':conditional_phase,
  'conditional_phase_delta_radians':delta,
  'full_buffer_max_abs_error':max(map(abs,err)),
  'comparison_status':'negative: Stage23Z source model not native coefficient parity',
  'important':'conditional phase is a diagnostic assuming the existing Stage23Z envelope, not an accepted native parameter or a fitting result'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--dll',required=True,type=Path)
 ap.add_argument('--native-pre-fft',type=Path)
 a=ap.parse_args();count=verify_source(a.dll)
 result={'stage':'Stage24A','dll_sha256':SHA,'instruction_pins':count,
 'static_lineage':{
 'source_filter_call':'0x18000CFF3: 0x180011B60 → 0x180011CE3: 0x18000BB80 → 0x18000BD12: 0x18000B0E0 → 0x18000B981: 0x180014810',
 'filter_cache_parameters':'filter +0 cutoff f64, +0x8 quality f64, +0x10 attenuation f64, +0x20 normalization gain f64; see 0x18000BCF1-0x18000BD03',
 'window_generator_object':'RCX = RSP+0x30 at 0x18000B981; +0x0 pre-floor G f64, +0x10 lower oscillator 0, +0x18 upper oscillator angle f64, +0x20 exponent gamma f64, +0x58 window iteration counter u32, +0xC0 beta f64, +0xC8 I0(beta) f64, +0xD0 initial offset zero',
 'source_first_fir':['0x180011C83 source versus destination rates choose cutoff 0.5 or 0.5*rate_ratio','0x180011CE3 passes cutoff, quality, attenuation, normalization gain into filter cache constructor'],
 'recommended_capture':'trace one filter identity at 0x180011CE3 (XMM0/1/2 and stack parameter), 0x18000B981 (RCX generator fields) and compare to Stage23H predicted inputs. Do not dump entire signal.'},
 'no_native_execution':'Static pinned DLL plus optional private offline Stage23W coefficient comparison; four gains and CLO parity remain unknown.'}
 if a.native_pre_fft:result['conditional_native_ratio_diagnostic']=native_ratio_gate(a.dll,a.native_pre_fft)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
