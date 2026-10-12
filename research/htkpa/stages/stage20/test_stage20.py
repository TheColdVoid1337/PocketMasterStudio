#!/usr/bin/env python3
"""Tests source-based partial native IIR reconstruction without DLL execution."""
import json,math,sys,struct,os
from pathlib import Path
import numpy as np
from scipy.signal import freqz, lfilter
sys.path.insert(0,str(Path(__file__).parent))
from stage20_iir_source import execute_sse_coeffs,native_constructor_defaults,native_iir_section,select_sections,pe_bytes,disasm,DLL_SHA
DLL=Path(os.environ.get('HTKPA_DLL_PATH','/mnt/data/htkpa_stage14_work/5868USB.dll'))
num=0

def check(expr,msg):
    global num
    assert expr,msg
    num+=1

for sr in (44100,48000,96000):
    c,gl,asm=execute_sse_coeffs(DLL,sr)
    check(len(c)==10,f'stores {sr}')
    check(len(gl)==5,f'global stores {sr}')
    check(len(asm)==152,f'opcode count {sr}')
    check(all(math.isfinite(x) for x in c.values()),f'finite {sr}')
    check(abs(c[hex(0x24388)]-c[hex(0x24398)])==0.0,f'b0=b2 20 {sr}')
    check(abs(c[hex(0x243b0)]-c[hex(0x243c0)])==0.0,f'b0=b2 10 {sr}')
    check(-2.01<c[hex(0x24390)]<-1.98,f'stable coeff {sr}')
    check(-2.01<c[hex(0x243b8)]<-1.98,f'stable coeff 2 {sr}')
    for base,freq in [(0x24388,40),(0x243b0,20)]:
        taps=[c[hex(base+8*i)] for i in range(5)]
        _,response=freqz(taps[:3],[1]+taps[3:],worN=2*np.pi*freq/sr)
        db=20*np.log10(abs(response[0]))
        check(abs(db+3.0103)<0.15,f'cutoff {sr} {freq}: {db}')
        # DC transfer close to zero; normalized numerator sign/cancellation.
        check(abs(sum(taps[:3]))<5e-7,f'DC {sr} {freq}')
        rng=np.random.default_rng(int(sr+freq))
        x=rng.standard_normal(100).astype(np.float32)*0.01
        got=native_iir_section(x,taps)
        ref=lfilter(taps[:3],[1.]+taps[3:],x.astype(np.float64)).astype(np.float32)
        check(np.max(abs(got-ref))<2e-5,f'lfilter {sr} {freq}')
        check(np.isfinite(got).all(),f'finite waveform {sr} {freq}')

# Compare independently native-coded initialization defaults to fresh Fs44.1
# SSE replay. Defaults (0xC04B0) are stored at nearly same calibration point.
d=native_constructor_defaults()
c,_,_=execute_sse_coeffs(DLL,44100)
for base in (0x24388,0x243b0):
    for i in range(5):
        check(abs(c[hex(base+8*i)]-d[base][i])<2e-7,f'ROM vs runtime {base:x}+{8*i}')
for base in (0x24338,0x24360):
    check(d[base]==[1.,0.,0.,0.,0.],f'ident {base:x}')
    x=np.array([0.,0.25,-0.5,0.75,-1.0,0.01],np.float32)
    check(np.array_equal(native_iir_section(x,d[base]),x),f'identical samples {base:x}')

# Native pointer-selector branch mode records checked separately using addresses.
for mode,expected in {0:(0x24360,0x24360),1:(0x24338,0x24388),2:(0x24338,0x243b0)}.items():
    check(select_sections({},mode)==expected,f'select {mode}')

# Sample-rate constants pinned to original PE bit patterns.
from stage20_iir_source import pe_bytes
raw=DLL.read_bytes()
vals={0x18024cddc:15791.4521484375,0x18024cd88:177.71580505371094,
      0x18024cd74:88.85771942138672,0x18024cdc4:3947.84716796875,
      0x18024cde8:31582.904296875,0x18024cdcc:7895.6943359375,
      0x18024d600:-0.0}
for va,val in vals.items():
    check(struct.unpack('<f',pe_bytes(raw,va,4))[0]==val,f'PE constant {hex(va)}')

# Confirmation that the native audio processor uses specific coefficient order
# and double accumulator / float32 round trip.
asmap={a:i for a,i in disasm(DLL,0x1800bd490,0x1800bd5d0)}
pins={0x1800bd564:'[rdi+0x232f0]',0x1800bd56f:'[rdi+0x232f8]',
      0x1800bd591:'[rdi+0x232e0]',0x1800bd599:'[rdi+0x232d8]',
      0x1800bd5a1:'[rdi+0x232e8]',0x1800bd5bb:'cvtpd2ps',
      0x1800bd5bf:'cvtps2pd',0x1800bd5c2:'mulsd',0x1800bd5c6:'cvtpd2ps'}
for va,p in pins.items():check(p in asmap[va],f'audio opcode {hex(va)}')
sel=dict(disasm(DLL,0x1800bec2b,0x1800bed11))
for va,f in {0x1800bec36:'[r14+0x24360]',0x1800bec59:'[r14+0x24338]',0x1800bec8f:'[r14+0x24360]',
             0x1800becb7:'[r14+0x24388]',0x1800becdf:'[r14+0x243b0]'}.items():
    check(f in sel[va],f'selection {hex(va)}')
# BDBE0 next-stage saturation fitter: only directly proven schedule/slots,
# not a fabricated numerical optimizer implementation.
sat=dict(disasm(DLL,0x1800bdbe0,0x1800be695))
sat_pins={
 0x1800bdc24:'0x18024c7a0',  # double 0.1 seconds × Fs
 0x1800bdc59:'divss  xmm0,xmm9',
 0x1800bdc6b:'cvttss2si ebx,xmm0',
 0x1800be418:'0x18024c608',  # float32 0.8
 0x1800be4ba:'call   0x18017e12e', # scalar expf thunk
 0x1800be4d5:'call   0x18017e12e',
 0x1800be519:'0x18024c9a8',  # double 1.2
 0x1800be529:'addsd  xmm0,xmm2', # increment
 0x1800be536:'comisd xmm3,xmm1',
 0x1800be5ae:'call   0x18017e12e',
 0x1800be631:'addsd  xmm0,xmm2',
 0x1800be63e:'comisd xmm3,xmm1',
 0x1800be661:'movss  DWORD PTR [rax],xmm0',
 0x1800be676:'movss  DWORD PTR [rax],xmm0',
 0x1800be682:'movss  DWORD PTR [rax],xmm10',
 0x1800be68f:'movss  DWORD PTR [rax],xmm9'
}
for va,code in sat_pins.items():check(code in sat[va],f'saturator pin {hex(va)}')
for va,val in {0x18024c7a0:0.1,0x18024c748:0.05,0x18024c9a8:1.2}.items():
    check(struct.unpack('<d',pe_bytes(raw,va,8))[0]==val,f'sat double {hex(va)}')
check(struct.unpack('<f',pe_bytes(raw,0x18024c608,4))[0]==np.float32(0.8), 'sat 0.8 float32')
print('STAGE20 PASSED' ,num,'independent checks, 3 sample rates, 2 cutoff responses')
