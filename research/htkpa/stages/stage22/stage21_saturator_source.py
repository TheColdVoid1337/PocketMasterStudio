#!/usr/bin/env python3
"""Stage 21: DLL-grounded envelope extrema + two-step nonlinear-rate search.

READ ONLY. The proprietary 5868USB.dll is *disassembled*, NEVER loaded/executed.
The exact native audio-envelope repacking in 0x1800BDF47..0x1800BE16C
and signal preprocessing are not implemented; do not use this as a complete
NAM→CLO saturation fit. No CLO-writing interface is provided.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, struct, subprocess
from pathlib import Path
import numpy as np

DLL_HASH='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
DSTART=0x1800BDBE0; DEND=0x1800BE6F6
# Instants are deliberately tied to semantic operations, not merely any instruction.
PINS={
  0x1800BDBF9:'[rcx+0x20ec0]', 0x1800BDC24:'0x18024c7a0',
  0x1800BDC59:'divss  xmm0,xmm9', 0x1800BDC66:'call   0x18017e13a',
  0x1800BDC6B:'cvttss2si ebx,xmm0', 0x1800BDC6F:'lea    eax,[rbx+rbx*2]',
  0x1800BDD1A:'mulss  xmm0,xmm9', 0x1800BDD32:'cvttss2si eax,xmm0',
  0x1800BDD8A:'andps  xmm0,xmm2', 0x1800BDD98:'[r8+rcx*1],xmm1',
  0x1800BDDA8:'[rcx],xmm1', 0x1800BDDB6:'[rdx+rcx*1],xmm1',
  0x1800BDECD:'movss  xmm1,DWORD PTR [rdx+rcx*1]',
  0x1800BDED6:'xorps  xmm1,xmm7', 0x1800BDEE1:'maxss  xmm0,xmm8',
  0x1800BDF12:'lea    eax,[rbp*2+0x0]',
  0x1800BDF26:'mov    QWORD PTR [rsp+0x70],rax',
  0x1800BDF34:'lea    r14,[r12+rax*4]',
  0x1800BDF38:'mov    QWORD PTR [rsp+0x68],r14',
  0x1800BE000:'movss  xmm0,DWORD PTR [r8+rdx*1]',
  0x1800BE011:'movss  DWORD PTR [rcx+r10*1-0x14],xmm0',
  0x1800BE01D:'mov    DWORD PTR [rcx+r9*1-0x14],eax',
  0x1800BE025:'mov    DWORD PTR [rcx+r12*1-0x10],eax',
  0x1800BE02E:'mov    DWORD PTR [rcx-0x14],eax',
  0x1800BE03B:'movss  DWORD PTR [rcx+r10*1-0x10],xmm0',
  0x1800BE04F:'mov    DWORD PTR [rcx+rsi*4-0x10],eax',
  0x1800BE078:'mov    DWORD PTR [rcx+r15*1-0x10],eax',
  0x1800BE0D3:'cmp    rbp,r13',
  0x1800BE147:'movss  DWORD PTR [rcx+r9*1-0x4],xmm0',
  0x1800BE153:'mov    DWORD PTR [rcx+rdi*1-0x4],eax',
  0x1800BE15A:'mov    DWORD PTR [rcx+rsi*4-0x4],eax',
  0x1800BE163:'mov    DWORD PTR [rcx-0x4],eax',

  0x1800BE18A:'0x18024c880',0x1800BE1D4:'0x18024cea8',
  0x1800BE259:'mulsd  xmm0,xmm1', 0x1800BE25D:'mulsd  xmm1,xmm1',
  0x1800BE261:'addsd  xmm5,xmm0', 0x1800BE26C:'addsd  xmm4,xmm1',
  0x1800BE30E:'divsd  xmm5,xmm4',0x1800BE361:'subsd  xmm3,xmm0',
  0x1800BE440:'divsd  xmm3,xmm4', 0x1800BE444:'cvtsd2ss xmm10,xmm5',
  0x1800BE449:'cvtsd2ss xmm12,xmm3', 0x1800BE462:'divss  xmm12,xmm6',
  0x1800BE47A:'divss  xmm10,xmm8',
  0x1800BE418:'0x18024c608',0x1800BE42E:'0x18024c748',
  0x1800BE4B3:'0x18024d600',0x1800BE4BA:'call   0x18017e12e',
  0x1800BE4C2:'subss  xmm2,xmm0',0x1800BE4D5:'call   0x18017e12e',
  0x1800BE4DD:'subss  xmm2,xmm6',0x1800BE4F5:'mulss  xmm1,xmm1',
  0x1800BE4F9:'addss  xmm7,xmm1',
  0x1800BE50B:'comiss xmm13,xmm7',0x1800BE515:'movaps xmm14,xmm9',
  0x1800BE529:'addsd  xmm0,xmm2',0x1800BE52D:'cvtpd2ps xmm9,xmm0',
  0x1800BE536:'comisd xmm3,xmm1',0x1800BE53A:'jae    0x1800be480',
  0x1800BE554:'mulss  xmm10,xmm14',0x1800BE5AE:'call   0x18017e12e',
  0x1800BE5C9:'call   0x18017e12e',0x1800BE5E9:'mulss  xmm1,xmm1',
  0x1800BE5ED:'addss  xmm7,xmm1',0x1800BE615:'comiss xmm15,xmm7',
  0x1800BE625:'movaps xmm9,xmm11',0x1800BE631:'addsd  xmm0,xmm2',
  0x1800BE63E:'comisd xmm3,xmm1',0x1800BE642:'jae    0x1800be560',
  0x1800BE65C:'mulss  xmm9,xmm12',0x1800BE661:'movss  DWORD PTR [rax],xmm0',
  0x1800BE676:'movss  DWORD PTR [rax],xmm0',0x1800BE682:'movss  DWORD PTR [rax],xmm10',
  0x1800BE68F:'movss  DWORD PTR [rax],xmm9',
}
# Little-endian virtual addresses of DLL .rdata; exact values pinned and decoded from PE.
CONSTANTS={
  0x18024C7A0:('d',0.1),0x18024C748:('d',0.05),
  0x18024C9A8:('d',1.2),0x18024C880:('d',0.5),
  0x18024CEA8:('d',-0.5),0x18024C608:('f',0.8),
  0x18024C6A0:('f',1.0),0x18024CE08:('f',3.4028234663852886e38)
}

def dll_pe_at(b,va,n):
    pe=struct.unpack_from('<I',b,0x3c)[0]
    assert b[:2]==b'MZ' and b[pe:pe+4]==b'PE\0\0'
    sections=struct.unpack_from('<H',b,pe+6)[0]
    opt=struct.unpack_from('<H',b,pe+20)[0]
    for i in range(sections):
        off=pe+24+opt+i*40
        virtualsize, rva, rawsize, rawstart=struct.unpack_from('<IIII',b,off+8)
        relative=va-0x180000000-rva
        if 0<=relative and relative+n<=rawsize: return b[rawstart+relative:rawstart+relative+n]
    raise ValueError('unmapped '+hex(va))

def pin_dll(dll):
    data=Path(dll).read_bytes()
    assert hashlib.sha256(data).hexdigest()==DLL_HASH,'Unrecognized DLL SHA: refuse analysis'
    out=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={DSTART:#x}',f'--stop-address={DEND:#x}',str(dll)],text=True)
    asm={int(m.group(1),16):m.group(2).strip() for s in out.splitlines() if (m:=re.match(r'\s*([0-9a-f]+):\s*(.*)',s))}
    checks=[]
    for va,frag in PINS.items():
        ins=asm.get(va,'')
        if frag not in ins: raise AssertionError(f'{va:#x}: expected {frag!r}, got {ins!r}')
        checks.append({'va':hex(va),'assembly':ins})
    for va,(typ,expect) in CONSTANTS.items():
        n=4 if typ=='f' else 8
        val=struct.unpack('<'+typ,dll_pe_at(data,va,n))[0]
        assert np.isclose(val,expect,rtol=3e-7,atol=0),(va,val,expect)
    # Import table confirms floorf, expf, to distinguish 0.1-sec integer floor
    imports=subprocess.check_output(['objdump','-p',str(dll)],text=True)
    assert '0018b9b8' in imports and 'floorf' in imports
    assert '0018b9a8' in imports and 'expf' in imports
    return checks

def f32(v): return np.float32(v)

def native_grid():
    """Each search multiplier native: float32(0.8), plus double 0.05, cast float32."""
    m=f32(.8); values=[]
    while float(m)<=1.2:
        values.append(float(m))
        m=f32(float(m)+.05)
        assert len(values)<=12
    return values

def envelope_extrema(input_signal, reference_signal, fs):
    """First loop in BDBE0. Does NOT implement later native envelope permutation.

    Returns abs(max input), max positive output, min negative output and
    their global extrema. Zero-initialization of all three scratch vectors.
    """
    x=np.asarray(input_signal,dtype=np.float32)
    y=np.asarray(reference_signal,dtype=np.float32)
    assert x.ndim==y.ndim==1 and x.size==y.size and np.isfinite(x).all() and np.isfinite(y).all()
    size=f32(float(f32(fs))*.1)
    blocks=math.floor(float(f32(f32(x.size)/size)))
    blocks=max(0,blocks)
    ab=np.zeros(blocks,dtype=np.float32)
    pos=np.zeros(blocks,dtype=np.float32)
    neg=np.zeros(blocks,dtype=np.float32)
    for i in range(blocks):
        # native cvtdq2ps → mulss→cvttss2si
        lo=int(f32(f32(i)*size));hi=int(f32(f32(i+1)*size))
        if hi<=lo:continue
        ab[i]=np.max(np.abs(x[lo:hi]))
        pos[i]=np.maximum(f32(0),np.max(y[lo:hi]))
        neg[i]=np.minimum(f32(0),np.min(y[lo:hi]))
    return dict(block_size=float(size),blocks=blocks,abs_input=ab,positive_target=pos,negative_target=neg,
                positive_amplitude=float(pos.max(initial=f32(0))),negative_amplitude=float((-neg).max(initial=f32(0))))

def prediction(x,pmax,nmax,prate,nrate):
    """Stage20 proven saturator shape, independent scalar f32 CRT analog.
    Parameters are explicitly PROVIDED (not derived from official CLO).
    """
    xx=np.asarray(x,dtype=np.float32)
    z=np.empty_like(xx)
    for i,xv in enumerate(xx):
        if xv>0:
            v=f32(-f32(f32(prate)*xv))
            e=f32(math.exp(float(v)))
            z[i]=f32(f32(pmax)*f32(f32(1)-e))
        else:
            v=f32(f32(nrate)*xv)
            e=f32(math.exp(float(v)))
            z[i]=f32(f32(nmax)*f32(e-f32(1)))
    return z

def scalar_loss(x,y,pmax,nmax,prate,nrate):
    result=prediction(x,pmax,nmax,prate,nrate)
    v=f32(0)
    for a,b in zip(np.asarray(y,dtype=np.float32),result):
        d=f32(a-b)
        v=f32(v+f32(d*d))
    return float(v)

def two_rate_sweep(x,y,pmax,nmax,initial_prate,initial_nrate):
    """Faithful normal-domain grid + two stage SSE-score structure.

    x/y MUST already be native envelope-repacked 2B-element paired arrays.
    Native BDF47..BE16C repacking is NOT implemented by this function.
    """
    xx=np.asarray(x,dtype=np.float32); yy=np.asarray(y,dtype=np.float32)
    assert xx.shape==yy.shape and xx.ndim==1 and np.isfinite(xx).all() and np.isfinite(yy).all()
    pmax,nmax,pr,nr=map(f32,(pmax,nmax,initial_prate,initial_nrate))
    grid=native_grid(); bestp=(float('inf'),None)
    histpos=[];histneg=[]
    for m in grid:
        rate=f32(f32(m)*pr)
        loss=scalar_loss(xx,yy,pmax,nmax,rate,nr)
        histpos.append({'multiplier':m,'sse':loss})
        # native `comiss best,new; jb skip`: tie goes to later candidate
        if loss<=bestp[0]:bestp=(loss,m)
    pr=f32(pr*f32(bestp[1]))
    bestn=(float('inf'),None)
    for m in grid:
        rate=f32(f32(m)*nr)
        loss=scalar_loss(xx,yy,pmax,nmax,pr,rate)
        histneg.append({'multiplier':m,'sse':loss})
        if loss<=bestn[0]:bestn=(loss,m)
    nr=f32(nr*f32(bestn[1]))
    return dict(pmax=float(pmax),nmax=float(nmax),prate=float(pr),nrate=float(nr),
                pos_best=bestp,neg_best=bestn,final_sse=scalar_loss(xx,yy,pmax,nmax,pr,nr),
                pos_search=histpos,neg_search=histneg)



def native_envelope_pairing(extrema):
    """Exact BDF47..BE16C array permutation for any B>=0.

    Original three B-float scratch curves: X=max(abs(input)),
    P=max(0, reference), N=min(0, reference). Native allocates
    TWO length-2B curves (=4B floats), NOT two length-B curves.

    qX = [-X[B-1], ...,-X[0], X[0],...,X[B-1]]
    qY = [ N[B-1], ..., N[0], P[0],...,P[B-1]]
    """
    X=np.asarray(extrema['abs_input'],dtype=np.float32)
    P=np.asarray(extrema['positive_target'],dtype=np.float32)
    N=np.asarray(extrema['negative_target'],dtype=np.float32)
    assert X.shape==P.shape==N.shape
    return np.concatenate((-X[::-1],X)),np.concatenate((N[::-1],P))


def first_halfmax_count(values,cutoff,positive=True):
    """Native BE1A0/BE1E0: first 1-based index crossing half global peak."""
    v=np.asarray(values,dtype=np.float32)
    for i,y in enumerate(v):
        if (y>=cutoff if positive else y<=cutoff):
            return i+1
    return 0


def initial_native_rates(extrema):
    """Native BE240..BE47A: two half-maximum truncated OLS estimates.

    Implements DLL summation as float64 on float32 extrema. The ordinary
    positive finite case is defined; zero or empty regression denominators
    raise rather than synthesizing arbitrary parameters.
    """
    X=np.asarray(extrema['abs_input'],dtype=np.float32)
    P=np.asarray(extrema['positive_target'],dtype=np.float32)
    N=np.asarray(extrema['negative_target'],dtype=np.float32)
    pmax=f32(extrema['positive_amplitude'])
    nmax=f32(extrema['negative_amplitude'])
    assert pmax>0 and nmax>0,'need both polarities in reference waveform'
    kp=first_halfmax_count(P,f32(float(pmax)*.5),True)
    kn=first_halfmax_count(N,f32(-float(nmax)*.5),False)
    assert kp>0 and kn>0
    def slope(y,n,negative):
        # BE259/BE261: numerator product double (f32 inputs); BE26C denom
        numerator=0.;denominator=0.
        for xval,yval in zip(X[:n],y[:n]):
            if negative: numerator-=float(xval)*float(yval)
            else:numerator+=float(xval)*float(yval)
            denominator+=float(xval)*float(xval)
        assert denominator>0,'zero input envelope in threshold region'
        return f32(numerator/denominator)
    slope_p=slope(P,kp,False)
    slope_n=slope(N,kn,True)
    return {'pmax':float(pmax),'nmax':float(nmax),
            'positive_threshold_count':kp,'negative_threshold_count':kn,
            'positive_slope':float(slope_p),'negative_slope':float(slope_n),
            'initial_prate':float(f32(slope_p/pmax)),
            'initial_nrate':float(f32(slope_n/nmax))}


def fit_preprocessed_waveforms(input_preprocessed,reference_preprocessed,fs):
    """Normal-domain self-contained translation of 0x1800BDBE0.

    IMPORTANT: these args are the function's TWO INPUT BUFFERS, not raw WAV.
    Actual audio preprocessing (50tap/IIR/pre-DSP) must be reproduced
    before calling this on official Manager recordings.
    """
    env=envelope_extrema(input_preprocessed,reference_preprocessed,fs)
    if env['blocks']<2:raise ValueError('not enough 0.1s extrema groups')
    rate=initial_native_rates(env)
    xx,yy=native_envelope_pairing(env)
    r=two_rate_sweep(xx,yy,rate['pmax'],rate['nmax'],rate['initial_prate'],rate['initial_nrate'])
    return {'num_blocks':env['blocks'],'native_envelope_samples':len(xx),
            'initialization':rate,
            'native_four_parameters':[r['pmax'],r['nmax'],r['prate'],r['nrate']],
            'initial_sse':scalar_loss(xx,yy,rate['pmax'],rate['nmax'],rate['initial_prate'],rate['initial_nrate']),
            'fitted_sse':r['final_sse'],'positive_multiplier':r['pos_best'][1],
            'negative_multiplier':r['neg_best'][1]}

def read_vendor_gains(clo):
    """Evaluation ONLY: never pass returned values to a fitting function."""
    raw=Path(clo).read_bytes()
    assert len(raw)==8840 and raw[:4]==b'VTSI'
    return dict(zip(('pmax','nmax','prate','nrate'),struct.unpack_from('<4f',raw,104)))

def run_test():
    checks=[]
    def check(label,cond):
        assert cond,label;checks.append(label)
    g=native_grid()
    check('native multiplier count',len(g)==9)
    check('first multiplier',abs(g[0]-.8)<1e-6)
    check('last multiplier',abs(g[-1]-1.1999998)<1e-6)
    check('native midpoint',g[4]==1.0)
    check('step monotonic',all(g[i]<g[i+1] for i in range(8)))
    check('noninclusion of next',float(f32(g[-1]+.05))>1.2)
    for fs in (44100,48000,96000):
        x=np.arange(1,4*int(fs*.1)+1,dtype=np.float32)*0
        y=x.copy();y[1]=1;y[3]=-2
        e=envelope_extrema(x,y,fs)
        check(f'{fs} 0.1s support',abs(e['block_size']-fs*.1)<1e-4)
        check(f'{fs} nonempty bins',e['blocks']==4)
        check(f'{fs} positive/negative maxima',(e['positive_amplitude'],e['negative_amplitude'])==(1.,2.))
    e=envelope_extrema(np.array([-2,1,3,0,-4,2,3,5],dtype=np.float32),
                       np.array([-.5,3,-1,-2,1,-3,2,4],dtype=np.float32),fs=10)
    check('1-sample block absolute',np.array_equal(e['abs_input'],np.array([2,1,3,0,4,2,3,5],dtype=np.float32)))
    check('1-sample block pos',np.array_equal(e['positive_target'],np.array([0,3,0,0,1,0,2,4],dtype=np.float32)))
    check('1-sample block neg',np.array_equal(e['negative_target'],np.array([-.5,0,-1,-2,0,-3,0,0],dtype=np.float32)))
    xx=np.array([-2,-1,-.25,0,.25,.5,1.,2.],dtype=np.float32)
    def satfloat(x,pp,nn,pr,nr):
        return pp*(1-np.exp(-pr*x)) if x>0 else nn*(np.exp(nr*x)-1)
    for v in xx:
        check(f'signed saturator {v}',abs(float(prediction([v],1.3,1.7,.8,1.2)[0])-satfloat(float(v),1.3,1.7,.8,1.2))<5e-7)
    check('zero input exactly zero',prediction([0.],1.5,1.7,.8,1.2)[0]==0)
    check('known parameters zero loss',scalar_loss(xx,prediction(xx,1.3,1.7,.8,1.2),1.3,1.7,.8,1.2)==0)
    for pf,nf in ((1.0,1.0),(1.1,.9),(.85,1.15)):
        y=prediction(xx,1.3,1.7,float(f32(.8*pf)),float(f32(1.2*nf)))
        r=two_rate_sweep(xx,y,1.3,1.7,.8,1.2)
        check(f'sweep positive recovered {pf}',abs(r['prate']-.8*pf)<.045)
        check(f'sweep negative recovered {nf}',abs(r['nrate']-1.2*nf)<.06)
        check(f'sweep improves error {pf}/{nf}',r['final_sse']<=scalar_loss(xx,y,1.3,1.7,.8,1.2)+1e-7)
    y=prediction(xx,1.3,1.7,.96,1.32)
    score=two_rate_sweep(xx,y,1.3,1.7,.8,1.2)
    check('nine x two evaluations',len(score['pos_search'])==len(score['neg_search'])==9)
    check('positive final 0.96',abs(score['prate']-.96)<1e-4)
    check('negative final 1.32',abs(score['nrate']-1.32)<1e-4)
    # Verify exact four-block permutation, halfmax regression, and synthetic
    # end-to-end optimizer on already-preprocessed input/reference arrays.
    for b in (1,2,3,4,5,8,9,12):
        extrema={'abs_input':np.arange(1,b+1,dtype=np.float32),
                 'positive_target':np.arange(1,b+1,dtype=np.float32)*.3,
                 'negative_target':-np.arange(1,b+1,dtype=np.float32)*.4}
        px,py=native_envelope_pairing(extrema)
        check(f'permutation size b{b}',len(px)==len(py)==2*b)
        check(f'permutation input b{b}',np.array_equal(px,np.r_[-extrema['abs_input'][::-1],extrema['abs_input']]))
        check(f'permutation output b{b}',np.array_equal(py,np.r_[extrema['negative_target'][::-1],extrema['positive_target']]))
    check('positive half maximum first index',first_halfmax_count([.05,.1,.3,.7],.25)==3)
    check('negative half maximum first index',first_halfmax_count([-.01,-.05,-.3,-.7],-.25,False)==3)
    check('positive threshold not found',first_halfmax_count([0,0],.5)==0)
    check('negative threshold not found',first_halfmax_count([0,0],-.5,False)==0)
    simple={'abs_input':np.array([.1,.3,.5],dtype=np.float32),
            'positive_target':np.array([.2,.6,1.],dtype=np.float32),
            'negative_target':np.array([-.1,-.3,-.5],dtype=np.float32),
            'positive_amplitude':1.,'negative_amplitude':.5}
    init=initial_native_rates(simple)
    check('OLS positive slope 2',abs(init['positive_slope']-2)<1e-6)
    check('OLS negative slope 1',abs(init['negative_slope']-1)<1e-6)
    check('native rates from slopes',abs(init['initial_prate']-2)<1e-6 and abs(init['initial_nrate']-2)<1e-6)
    check('OLS halfmax cutoff index',init['positive_threshold_count']==2 and init['negative_threshold_count']==2)
    # Realistic synthetic arrays are fed as PREPROCESSED signal buffers.
    fs=1000
    t=np.arange(60_000,dtype=np.float32)/fs
    drive=np.sin(2*np.pi*7*t)*np.linspace(.005,.12,len(t),dtype=np.float32)
    target=prediction(drive,.075,.09,16.,12.)
    end_to_end=fit_preprocessed_waveforms(drive,target,fs)
    check('end-to-end has enough blocks',end_to_end['num_blocks']>=590)
    check('end-to-end finite positive parameters',all(np.isfinite(end_to_end['native_four_parameters'])) and all(v>0 for v in end_to_end['native_four_parameters']))
    check('end-to-end scores finite',np.isfinite(end_to_end['initial_sse']) and np.isfinite(end_to_end['fitted_sse']))
    check('end-to-end no deterioration',end_to_end['fitted_sse']<=end_to_end['initial_sse']+1e-6)
    check('end-to-end known multiplier',end_to_end['positive_multiplier'] in native_grid() and end_to_end['negative_multiplier'] in native_grid())
    # No vendor-derived gains used as solver inputs.
    return checks

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dll',required=True);ap.add_argument('--output');a=ap.parse_args()
    pins=pin_dll(a.dll)
    checks=run_test()
    result={'stage':21,'dll_sha256':DLL_HASH,'instruction_pins':len(pins),'synthetic_assertions':len(checks),
            'pinned_constants':{hex(k):dict(type=t,value=float(struct.unpack('<'+t,dll_pe_at(Path(a.dll).read_bytes(),k,4 if t=='f' else 8))[0])) for k,(t,_) in CONSTANTS.items()},
            'native_grid':native_grid(), 'tests':checks,'asserted_fitter_scope':'ordinary-domain full 0x1800BDBE0 envelope extraction + permutation + OLS + two sweeps, provided already preprocessed audio',
            'native_envelope_repacking':'COMPUTED_NORMAL_DOMAIN','initial_slope_regression':'COMPUTED_NORMAL_DOMAIN',
            'real_wav_parameter_fit':'NOT_COMPUTED_UPSTREAM_PREPROCESSING_REQUIRED','vendor_fir_parity':'NOT_TESTED'}
    text=json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+'\n'
    if a.output:Path(a.output).write_text(text)
    print(f'PASSED pinned instructions={len(pins)} constants={len(CONSTANTS)} mathematical_assertions={len(checks)}')
    print('STRICT GATE: full native saturation fit from WAV = NOT_COMPUTED')
if __name__=='__main__': main()
