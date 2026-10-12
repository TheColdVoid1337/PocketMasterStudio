#!/usr/bin/env python3
"""Source-driven read-only replay of the native Win64 SSE coefficient constructor.

Never imports/runs proprietary code. Replays only opcode families *actually* found
in SHA-pinned 5868USB.dll between 0x1800BFF17 and 0x1800C0216.

rdi +0x20ec0 holds the sample rate float32. `movsd` outputs are float64,
computed via explicitly float32 intermediates (SSE mulss/addss/divss).
"""
import argparse,hashlib,json,re,struct,subprocess,sys
from pathlib import Path
import numpy as np
BASE=0x180000000
DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
START=0x1800bff17; STOP=0x1800c021e
CONTEXT_OFFSETS=list(range(0x24388,0x243d8,8))
GLOBAL_VAS=[0x18028d448,0x18028d450,0x18028d458,0x18028f720,0x18028f728]

def pe_bytes(data,va,n):
    at=struct.unpack_from('<I',data,0x3c)[0]
    assert data[:2]==b'MZ' and data[at:at+4]==b'PE\0\0'
    count=struct.unpack_from('<H',data,at+6)[0]; opt=struct.unpack_from('<H',data,at+20)[0]
    for i in range(count):
        p=at+24+opt+40*i
        virt_size,virtual,rawsize,rawstart=struct.unpack_from('<IIII',data,p+8)
        rel=va-BASE-virtual
        if 0<=rel and rel+n<=rawsize: return data[rawstart+rel:rawstart+rel+n]
    raise ValueError('not mapped in PE: '+hex(va))

def disasm(dll,start=START,stop=STOP):
    s=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={start:#x}',f'--stop-address={stop:#x}',str(dll)],text=True)
    return [(int(m.group(1),16),m.group(2).strip()) for line in s.splitlines() if (m:=re.match(r'\s*([0-9a-f]+):\s*(.*?)\s*$',line))]

def f32(v): return np.float32(v)
def native_constructor_defaults():
    """Source constants from 0x1800C04B0. Each group is FIVE float64 taps."""
    def d(h): return struct.unpack('<d',struct.pack('<Q',h))[0]
    return {
        0x24338: [1., 0., 0., 0., 0.],
        0x24360: [1., 0., 0., 0., 0.],
        0x24388: [d(h) for h in [
            0x3fefdf0dd923c898, 0xbfffdf0dd923c898,
            0x3fefdf0dd923c898, 0xbfffdefce36437d8,
            0x3fefbe3d9dc6b2b0]],
        0x243b0: [d(h) for h in [
            0x3fefef82acf4ed9b,0xbfffef82acf4ed9b,
            0x3fefef82acf4ed9b,0xbfffef7e6d55b710,
            0x3fefdf0dd928484d]],
    }


def native_iir_section(input_audio,coefs):
    """0x1800BD550..0x1800BD5CA: one recursion, float64 state,
    float32 middle rounding, double output scale, final float32.

    Coefficient order [b0,b1,b2,a1,a2] is grounded by loads at
    0x1800BD564/0x1800BD56F/0x1800BD591/0x1800BD599/0x1800BD5A1.
    Each invocation resets w[n-1],w[n-2] to zero.
    """
    b0,b1,b2,a1,a2=map(float,coefs)
    audio=np.asarray(input_audio,dtype=np.float32)
    out=np.empty_like(audio)
    w1=w2=0.0
    for i,x in enumerate(audio):
        drive=float(np.float32(x))*1000.0
        # Native subtraction order is a2*w2 first, then a1*w1.
        w=(drive-a2*w2)-a1*w1
        # Native adds (b1*w1 + b2*w2) before b0*w.
        mid=(b1*w1+b2*w2)+b0*w
        out[i]=np.float32(float(np.float32(mid))*0.001)
        w2,w1=w1,w
    return out

def execute_sse_coeffs(dll,sample_rate):
    data=Path(dll).read_bytes()
    if hashlib.sha256(data).hexdigest()!=DLL_SHA: raise ValueError('DLL SHA mismatch')
    asm=disasm(dll)
    regs={f'xmm{i}':('f',np.float32(0)) for i in range(16)}
    context={};globals_={};audit=[]
    for addr,ins in asm:
        if addr>0x1800c0216:break
        op,sep,rest=ins.partition(' ')
        if op in ['movss','movaps','movsd','xorps','mulss','addss','subss','divss','cvtps2pd','cvtss2sd']:
            operands=rest.split(' # ')[0].split(',')
            if op=='xorps':
                dst,src=map(str.strip,operands)
                if dst==src: regs[dst]=('f',f32(0))
                else:
                    a=struct.unpack('<I',struct.pack('<f',regs[dst][1]))[0]
                    b=struct.unpack('<I',struct.pack('<f',regs[src][1]))[0]
                    regs[dst]=('f',f32(struct.unpack('<f',struct.pack('<I',a^b))[0]))
                audit.append((addr,ins));continue
            if op=='cvtps2pd':
                dst,src=map(str.strip,operands);regs[dst]=('d',float(np.float32(regs[src][1]))); audit.append((addr,ins));continue
            if op=='cvtss2sd':
                dst,src=map(str.strip,operands);regs[dst]=('d',float(np.float32(regs[src][1]))); audit.append((addr,ins));continue
            if len(operands)!=2:raise ValueError((hex(addr),ins))
            dst,src=map(str.strip,operands)
            if dst.startswith('QWORD PTR [rdi+'):
                offset=int(dst.split('[rdi+')[1].split(']')[0],16)
                assert op=='movsd'
                val=float(regs[src][1]);context[offset]=val;audit.append((addr,ins));continue
            if dst.startswith('QWORD PTR [rip+'):
                assert op=='movsd'
                m=re.search(r'# (0x[0-9a-f]+)',ins);assert m
                globals_[int(m.group(1),16)]=float(regs[src][1]);audit.append((addr,ins));continue
            if dst.startswith('xmm'):
                if src.startswith('xmm'):
                    typ,value=regs[src]
                else:
                    ptr=re.search(r'\[rdi\+(0x[0-9a-f]+)\]',src)
                    if ptr:
                        assert int(ptr.group(1),16)==0x20ec0
                        value=f32(sample_rate);typ='f'
                    else:
                        m=re.search(r'# (0x[0-9a-f]+)',ins)
                        if m:
                            sourceaddr=int(m.group(1),16)
                            assert 'DWORD PTR' in src or 'QWORD PTR' in src,(hex(addr),ins)
                            value=struct.unpack('<f' if 'DWORD PTR' in src else '<d',pe_bytes(data,sourceaddr,4 if 'DWORD PTR' in src else 8))[0]
                            typ='f' if 'DWORD PTR' in src else 'd'
                        elif 'rsp+' in src:
                            # Restore callee-saved registers after all outputs, safe to ignore.
                            assert addr>=0x1800c01da,(hex(addr),ins)
                            audit.append((addr,ins));continue
                        else:raise ValueError((hex(addr),ins))
                if op in ('movss','movsd','movaps'):
                    regs[dst]=(typ,value)
                elif op in ('mulss','addss','subss','divss'):
                    assert regs[dst][0]=='f' and typ=='f',(hex(addr),regs[dst],(typ,value))
                    lhs=f32(regs[dst][1]);rhs=f32(value)
                    with np.errstate(all='raise'):
                        val={'mulss':lambda:f32(lhs*rhs),'addss':lambda:f32(lhs+rhs),
                             'subss':lambda:f32(lhs-rhs),'divss':lambda:f32(lhs/rhs)}[op]()
                    regs[dst]=('f',val)
                else:raise ValueError((hex(addr),ins))
                audit.append((addr,ins));continue
        if op=='movaps' and 'XMMWORD PTR [rsp' in ins:continue
        if op in ('lea','nop','repz'):continue
        # Prevent accidentally ignoring relevant instructions in the bounded region.
        raise ValueError('unhandled at '+hex(addr)+' '+ins)
    assert all(k in context for k in CONTEXT_OFFSETS),(sorted(context),CONTEXT_OFFSETS)
    assert all(k in globals_ for k in GLOBAL_VAS),(globals_,GLOBAL_VAS)
    assert len([a for a,_ in audit if 0x1800bff17<=a<=0x1800c0216])>=135
    return {f'{k:#x}':context[k] for k in CONTEXT_OFFSETS},{f'{k:#x}':globals_[k] for k in GLOBAL_VAS},audit

def select_sections(context,mode):
    """Native 0x1800BEC36..0x1800BED00. mode equals context[0x232d0]."""
    first=0x24360 if mode==0 else 0x24338
    if mode==0:second=0x24360
    elif mode==1:second=0x24388
    elif mode==2:second=0x243b0
    else:second=None
    return first,second

def main():
    p=argparse.ArgumentParser();p.add_argument('--dll',required=True,type=Path);p.add_argument('--out',type=Path);args=p.parse_args()
    allvals={};n=0
    for rate in (44100,48000,96000):
        ctx,g,audit=execute_sse_coeffs(args.dll,rate);n=len(audit)
        allvals[str(rate)]={'context_constructor':ctx,'global_constructor':g}
    r={'dll_sha256':DLL_SHA,'research_only':True,'exact_vendor_A_B':'NOT_COMPUTED',
       'synthetic_emulation_instructions':n,'rates':allvals,
       'mode_mapping':{str(m):{'first':hex(select_sections({},m)[0]),'second':hex(select_sections({},m)[1]) if select_sections({},m)[1] else None} for m in (0,1,2)},
       'warning':'SSE opcode replay only; DSP and real WAV A/B not integrated; no DLL execution'}
    s=json.dumps(r,sort_keys=True,indent=2)+'\n'
    if args.out:args.out.write_text(s)
    else:print(s)

if __name__=='__main__':main()
