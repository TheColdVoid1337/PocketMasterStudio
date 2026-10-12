#!/usr/bin/env python3
"""Read-only Stage 19: extract exact 50-coefficient FIR banks from 5868USB.dll.

Audits real user-captured 70-second DI (PCM16, two identical channels) but does
NOT assert that the incomplete audio/STFT chain has produced vendor initial A/B.
No DLL is executed, and no CLO is created.
"""
import argparse, hashlib, io, json, math, re, struct, subprocess, wave, zipfile
from pathlib import Path
import numpy as np
from scipy.signal import lfilter

DLL_HASH='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
BASE=0x180000000
BANKS={
 44100:{'addresses':[0x18024d6f0,0x18024d700,0x18024d240,0x18024d210,0x18024d6a0,0x18024d140,0x18024d130,0x18024d630,0x18024d6b0,0x18024d6c0,0x18024d690,0x18024d6d0,0x18024c4f4,0x18024c514], 'test':0x1800bc739, 'branch':0x1800bc753},
 48000:{'addresses':[0x18024d270,0x18024d740,0x18024d200,0x18024d1b0,0x18024d620,0x18024d660,0x18024d610,0x18024d180,0x18024d170,0x18024d120,0x18024d640,0x18024d680,0x18024ce2c,0x18024c510], 'test':0x1800bc7ef, 'branch':0x1800bc802},
 96000:{'addresses':[0x18024d530,0x18024d730,0x18024d760,0x18024d710,0x18024d6e0,0x18024d230,0x18024d1f0,0x18024d1d0,0x18024d220,0x18024d650,0x18024d150,0x18024d670,0x18024ce34,0x18024ce30], 'test':0x1800bc89e,'branch':0x1800bc8b1}}

def pe_data(data,va,n):
    hdr=struct.unpack_from('<I',data,0x3c)[0]
    if data[:2]!=b'MZ' or data[hdr:hdr+4]!=b'PE\0\0':raise AssertionError('not a PE binary')
    sections=struct.unpack_from('<H',data,hdr+6)[0]
    opt=struct.unpack_from('<H',data,hdr+20)[0]
    for i in range(sections):
        o=hdr+24+opt+40*i
        _,vaddr,rsize,roff=struct.unpack_from('<IIII',data,o+8)
        d=va-BASE-vaddr
        if 0<=d and d+n<=rsize:return data[roff+d:roff+d+n]
    raise AssertionError(f'unmapped {va:#x}')

def disassembly(dll,lo,hi):
    p=subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)],check=True,text=True,capture_output=True)
    return {int(m.group(1),16):m.group(2).strip() for line in p.stdout.splitlines() if (m:=re.match(r'\s*([0-9a-f]+):\s*(.*)',line))}

def extract_banks(data,asm):
    result={}; pins=[]
    for rate,defn in BANKS.items():
        start=defn['branch'];code=asm.get(start,'')
        assert f'# 0x{defn["addresses"][0]:x}' in code, (rate,code)
        pins.append({'address':hex(start),'opcode':code})
        vals=[]
        for i,addr in enumerate(defn['addresses']):
            n=16 if i<12 else 4
            blob=pe_data(data,addr,n)
            floats=np.frombuffer(blob,dtype='<f4')
            vals.extend(float(v) for v in floats)
        h=np.asarray(vals,dtype='<f4');assert h.size==50
        assert np.isfinite(h).all()
        result[rate]=h
    extra={
        0x1800bc94d:'lea    rdx,[rsp+0x50]',
        0x1800bc955:'[rsp+0x20],r12d',
        0x1800bc95a:'mov    r8d,0x32',
        0x1800bc96d:'call   0x1800b5a30',
        0x1800bcc79:'call   0x1800be700',
        0x1800bcff2:'call   0x1800b82b0',
        0x1800bd4f6:'call   0x18017e10a',
        0x1800bd50f:'[rdi+0x20],rax',
        0x1800bd513:'[rdi+0x28],rax',
        0x1800bd517:'[rdi+0x30],rax',
        0x1800bd5bb:'cvtpd2ps xmm0,xmm1',
        0x1800bd5c2:'mulsd  xmm1,xmm7',
        0x1800bd808:'call   0x180027e60',
        0x1800bd828:'call   0x1800be700',
        0x1800bd83c:'[rdi+0x20c98],rax',
        0x1800bd843:'[rdi+0x20ca0],rax',
        0x1800bd84a:'[rdi+0x20ca8],rax',
        0x1800be72a:'call   0x1800284f0',
        0x1800be76d:'call   0x180028690',
        0x1800be81f:'jmp    0x1800285b0',
        0x1800b83f3:'[rip+0x194485]',
        0x1800b83fb:'cvttsd2si eax,xmm0',
        0x1800b83ca:'call   0x18017e11c',
        0x1800bee25:'call   0x1800bd490',
        0x1800bee89:'call   0x1800bc6b0',
    }
    for address,fragment in extra.items():
        code=asm.get(address,'');assert fragment in code,(hex(address),code,fragment)
        pins.append({'address':hex(address),'opcode':code})
    # Prove each of the 42 PE source-constant reads occurs within the
    # *matching* sample-rate branch, not merely somewhere in the DLL.
    branch_ranges={44100:(0x1800bc753,0x1800bc7ef),
                   48000:(0x1800bc802,0x1800bc89e),
                   96000:(0x1800bc8b1,0x1800bc948)}
    for rate,(lo,hi) in branch_ranges.items():
        relevant={addr:code for addr,code in asm.items() if lo<=addr<hi}
        for i,source_va in enumerate(BANKS[rate]['addresses']):
            matches=[(addr,code) for addr,code in relevant.items()
                     if f'# 0x{source_va:x}' in code]
            assert len(matches)==1,(rate,i,hex(source_va),matches)
            addr,code=matches[0]
            assert ('movaps' in code if i<12 else 'movss' in code), (rate,i,code)
            pins.append({'address':hex(addr),'opcode':code,'source_coefficient_index':i*4 if i<12 else 48+(i-12),'frequency_branch':rate})
    return result,pins

def get_samples(zip_path,n='wavs/nam_input_wav.wav',seconds=70):
    with zipfile.ZipFile(zip_path) as z:
        payload=z.read(n)
    with wave.open(io.BytesIO(payload),'rb') as w:
        sr=w.getframerate();channels=w.getnchannels();sw=w.getsampwidth();frames=w.getnframes()
        assert channels==2 and sw==2 and frames==seconds*sr
        raw=w.readframes(frames)
    vals=np.frombuffer(raw,dtype='<i2').reshape(-1,channels)
    if not np.array_equal(vals[:,0],vals[:,1]):raise AssertionError('expected identical stereo channels')
    return vals[:,0].astype(np.float32)/32768.0,sr,hashlib.sha256(payload).hexdigest()

def audit_wav(banks,zipfile_path):
    di,sr,dihash=get_samples(zipfile_path)
    assert sr in banks
    # Pure causal reference FIR from the *real* user-captured DI and the DLL's
    # matching-rate 50-tap table. This is not the entire native B5A30 process.
    early=lfilter(banks[sr].astype(np.float64),[1.],di.astype(np.float64)).astype(np.float32)
    segs={}
    for label,start,seconds in [('quiet',6,15),('loud',23,5),('third',30,20),('final',50,20)]:
        x=early[int(start*sr):int((start+seconds)*sr)]
        segs[label]={'start_s':start,'duration_s':seconds,'rms':float(np.sqrt(np.mean(x.astype(np.float64)**2))),'peak':float(np.max(np.abs(x)))}
    with zipfile.ZipFile(zipfile_path) as z:
        output_bytes=z.read('wavs/outputFile.wav')
    with wave.open(io.BytesIO(output_bytes),'rb') as o:
        assert o.getframerate()==48000 and o.getnframes()==70*48000 and o.getnchannels()==2 and o.getsampwidth()==2
        output_pcm=np.frombuffer(o.readframes(o.getnframes()),dtype='<i2').reshape(-1,2)
    assert np.array_equal(output_pcm[:,0],output_pcm[:,1])
    output_reference=output_pcm[:,0].astype(np.float64)/32768.0
    return {'source_zip_name':zipfile_path.name,'raw_DI_WAV_sha256':dihash,'sample_rate':sr,
            'reference_output_WAV_sha256':hashlib.sha256(output_bytes).hexdigest(),
            'reference_output_rate':48000,'reference_output_RMS':float(np.sqrt(np.mean(output_reference**2))),
            'reference_output_peak':float(np.max(np.abs(output_reference))),
            'samples':len(di),'samples_first8':early[:8].tolist(),'full_reference_FIR_RMS':float(np.sqrt(np.mean(early.astype(np.float64)**2))),
            'full_reference_FIR_peak':float(np.max(np.abs(early))), 'segments':segs}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--dll',required=True,type=Path)
    ap.add_argument('--zip-2203',type=Path);ap.add_argument('--zip-sc20',type=Path)
    ap.add_argument('--out',type=Path);args=ap.parse_args()
    data=args.dll.read_bytes();sha=hashlib.sha256(data).hexdigest()
    if sha!=DLL_HASH:raise SystemExit('DLL SHA mismatch; refusing analysis')
    instruction_map={}
    for lo,hi in [(0x1800bc6b0,0x1800bd050),(0x1800bd490,0x1800bd950),(0x1800be700,0x1800be830),
                  (0x1800b82b0,0x1800b8430),(0x1800bee00,0x1800beeb0)]:
        instruction_map.update(disassembly(args.dll,lo,hi))
    banks,pins=extract_banks(data,instruction_map)
    result={'research_only':True,'vendor_initial_A_B':'NOT_COMPUTED',
            'reason':'Native input audio preparation and B82B0 spectral buffer operation not fully implemented; no vendor FIR used.',
            'dll_sha256':sha,'instruction_checks':len(pins),'assertions':pins,
            'tables':{str(k):{'tap_count':len(v),'sha256_le_float32':hashlib.sha256(v.tobytes()).hexdigest(),
                         'first_8_taps':v[:8].tolist(),'sum':float(np.sum(v,dtype=np.float64)),
                         'l2':float(np.linalg.norm(v.astype(np.float64))),'max_abs':float(np.max(np.abs(v)))} for k,v in banks.items()},
            'raw_probe_audit':[]}
    # Compare genuinely independent user-captured 2203 and SC20 packages.
    for path in [args.zip_2203,args.zip_sc20]:
        if path:result['raw_probe_audit'].append(audit_wav(banks,path))
    if len(result['raw_probe_audit'])==2:
        result['identical_DI_WAVs_between_models']=(result['raw_probe_audit'][0]['raw_DI_WAV_sha256']==result['raw_probe_audit'][1]['raw_DI_WAV_sha256'])
    js=json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+'\n'
    if args.out:args.out.write_text(js)
    else:print(js)
    print('STAGE19 OK:',len(pins),'source instruction checks,',len(banks),'PE float32 banks; A/B NOT COMPUTED')

if __name__=='__main__':main()
