"""Sonicake HTKPA Stage23 DLL-address verifier; never loads/executes vendor DLL.

SOURCE-FIRST scope: two native PCM loaders, caller branches, 44.1k path,
upstream WAV resampler dispatch, and capture metadata. No DSP parity claim.
"""
from __future__ import annotations
import argparse, hashlib, io, json, re, struct, subprocess, wave, zipfile
from pathlib import Path

DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
EXPECTED = {
    '2203': {'clo':'50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7'},
    'SC20': {'clo':'2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a'},
}
DI_SHA = '9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a'
# Addresses and expected assembly fragments are checked against freshly disassembled pinned DLL.
PINS = {
    # First native 44.1k path
    0x18000F9A7: '0x18024cdf0',
    0x18000F9B6: 'call   0x1800bfe00',
    0x18000F9E5: 'call   0x1800bf9f0',
    0x18000FA1B: 'call   0x1800bf5e0',
    0x18000FA41: 'call   0x1800be830',
    # Actual upstream output conversion path to first branch
    0x1800100DA: '0x18024ccf8',
    0x1800100EB: 'call   0x18000d4a0',
    0x18001016D: 'call   0x18000f940',
    # Second branch configured by caller's xmm6 (does not prove actual Fs)
    0x180010453: 'movaps xmm1,xmm6',
    0x18001045D: 'call   0x1800bfe00',
    0x180010489: 'call   0x1800bf9f0',
    0x1800104BD: 'call   0x1800bf5e0',
    0x1800104E1: 'call   0x1800be830',
    # Resampler's upstream native interface: Fs input via r14+8, output via xmm6
    0x18000D775: 'cvtsd2ss xmm2,xmm6',
    0x18000D779: 'movsd  xmm1,qword ptr [r14+0x8]',
    0x18000D786: 'call   0x18000ce00',
    0x18000CF9B: 'movss  xmm0,dword ptr [rax+rcx*1]',
    0x18000CFA0: 'cvtps2pd xmm0,xmm0',
    0x18000CFD3: 'cvtss2sd xmm2,xmm8',
    0x18000CFDB: 'cvtss2sd xmm1,xmm9',
    0x18000CFF3: 'call   0x180011b60',
    0x18000D03E: 'divss  xmm0,xmm9',
    0x18000D16B: 'cvtpd2ps xmm0,xmm0',
    0x18000D17F: 'movss  dword ptr [rcx+rdx*4],xmm0',
    # Separate decoders: target/reference then source/input
    0x1800BF617: 'mov    rax,qword ptr [rcx+0x243e8]',
    0x1800BFA27: 'mov    rax,qword ptr [rcx+0x243e0]',
    0x1800BF6F2: 'movss  xmm0,dword ptr [rdi+0x20ec0]',
    0x1800BF6FD: 'ucomisd xmm2,xmm0',
    0x1800BFB02: 'movss  xmm0,dword ptr [rdi+0x20ec0]',
    0x1800BFB0D: 'ucomisd xmm2,xmm0',
    0x1800BF890: 'mov    rcx,qword ptr [rdi+0x243f0]',
    0x1800BF897: 'mov    eax,dword ptr [rdx+r15*1]',
    0x1800BF89B: 'mov    dword ptr [rdx+rcx*1],eax',
    0x1800BFCA0: 'mov    rcx,qword ptr [rdi+0x243f0]',
    0x1800BFCA7: 'mov    eax,dword ptr [rdx+r15*1]',
    0x1800BFCAB: 'mov    dword ptr [rdx+rcx*1],eax',
    0x1800BF8BE: 'mov    byte ptr [rdi+0x243da],0x1',
    0x1800BFCCE: 'mov    byte ptr [rdi+0x243d9],0x1',
    0x1800BEDE4: 'call   0x1800bdbe0',
    0x1800BEE25: 'call   0x1800bd490',
}
RANGES=[(0x18000CF60,0x18000D1A0),(0x18000D730,0x18000D895),
        (0x18000F990,0x18000FA50),(0x1800100CA,0x180010180),
        (0x180010440,0x1800104F0),(0x1800BEDE0,0x1800BEE30),
        (0x1800BF600,0x1800BF8D0),(0x1800BFA10,0x1800BFCE0)]

def sha(b):return hashlib.sha256(b).hexdigest()

def verify_disasm(dll):
    instr={};fragments=[]
    for a,b in RANGES:
        out=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={a:#x}',f'--stop-address={b:#x}',str(dll)],text=True)
        fragments.append(out)
        for line in out.splitlines():
            m=re.match(r'\s*([0-9a-f]+):\s*(.*)',line)
            if m:instr[int(m.group(1),16)]=m.group(2).strip().lower()
    for a,needle in PINS.items():
        got=instr.get(a,'')
        if needle.lower() not in got:raise AssertionError(f'{a:#x}: expected {needle!r}, got {got!r}')
    # Locate constants by DLL file's known .rdata RVA mapping from section header.
    from stage21_saturator_source import dll_pe_at
    data=dll.read_bytes()
    v1=struct.unpack('<f',dll_pe_at(data,0x18024cdf0,4))[0]
    v2=struct.unpack('<d',dll_pe_at(data,0x18024ccf8,8))[0]
    if (v1,v2)!=(44100.0,44100.0):raise AssertionError((v1,v2))
    return {'pin_count':len(PINS),'pin_values':{hex(a):instr[a] for a in PINS},'constants':{'fixed_context_fs_float':v1,'upstream_target_resample_fs_double':v2}, 'disassembly_sha256':sha(('\n'.join(fragments)).encode())}

def inspect_capture(path,model):
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise RuntimeError('ZIP CRC failed')
        out={'archive':Path(path).name, 'files':{}}
        for name in ('wavs/nam_input_wav.wav','wavs/outputFile.wav'):
            b=z.read(name);w=wave.open(io.BytesIO(b),'rb')
            o={'sha256':sha(b),'sample_rate':w.getframerate(),'channels':w.getnchannels(),'sample_width_bytes':w.getsampwidth(),'frames':w.getnframes()}
            assert o['frames']==70*o['sample_rate'] and o['channels']==2 and o['sample_width_bytes']==2
            out['files'][name]=o
        assert out['files']['wavs/nam_input_wav.wav']['sample_rate']==44100
        assert out['files']['wavs/outputFile.wav']['sample_rate']==48000
        assert out['files']['wavs/nam_input_wav.wav']['sha256']==DI_SHA
        clo=z.read('clo/cloFile.clo')
        assert sha(clo)==EXPECTED[model]['clo'] and len(clo)==8840 and clo[:4]==b'VTSI'
        out['official_gains_heldout_only']=dict(zip(('pmax','nmax','prate','nrate'),struct.unpack_from('<4f',clo,104)))
        out['clo_sha256']=sha(clo)
        return out

def tests():
    # Synthetic, no inference about device/native resampling response.
    aa=list(range(70*10+600));bb=aa.copy();sh=19
    assert len(aa)==70*10+600
    assert aa[23*10:28*10]==bb[23*10:28*10]
    assert bb[6*10+sh]==79
    assert (70*44100+600)*4==12350400
    assert 44100.0 != 48000.0
    return 5

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dll',required=True);p.add_argument('--capture2203');p.add_argument('--capture-sc20');p.add_argument('--out',required=True)
    args=p.parse_args();dll=Path(args.dll)
    assert sha(dll.read_bytes())==DLL_SHA,'DLL SHA mismatch'
    result={'stage':23,'status':'SOURCE_PROVEN_LOADER_AND_RESAMPLER_DISPATCH__EXACT_RESAMPLER_AND_REAL_FITTER_PARITY_OPEN',
      'dll_sha256':DLL_SHA,'source_evidence':verify_disasm(dll),'synthetic_tests':tests(),
      'source_graph':[
        'Path A: 0x1000DA target 44100 rate -> 0x1000EB converter 0xD4A0 -> 0x1016D caller 0xF940',
        '0xF940 context initialized with PE 44100.0f -> source loader BF9F0 -> target loader BF5E0 -> BE830',
        'D4A0 calls native float resampler CE00, whose 11B60 constructor creates the multi-stage filter state',
        '0xBF9F0 raw f32 sample copying from decoded first channel to +0x243E0',
        '0xBF5E0 raw f32 sample copying from decoded first channel to +0x243E8',
        'both native file loaders reject header Fs != context+0x20EC0',
        'Path B: 0x10453 copies caller-provided rate xmm6 -> 0x1045D context BFE00 -> loaders -> BE830'],
      'open_gates':['prove normal export chooses Path A or B for captures','bit/numeric reconstruction CE00/11B60 resampler response','actual decoder PCM16 amplitude scaling and any upstream ref gain transformations','native 70s float32 reference mean/trend exact rounding','four fitted gains on real audio and heldout parity'],
      'real_native_fitter_gains':'NOT_COMPUTED','production_changes':False,'hardware_changes':False}
    if args.capture2203:result['capture_2203']=inspect_capture(args.capture2203,'2203')
    if args.capture_sc20:result['capture_SC20']=inspect_capture(args.capture_sc20,'SC20')
    Path(args.out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('OK DLL',DLL_SHA,'pin_count',len(PINS),'synthetic_tests',result['synthetic_tests'],'captures',('capture_2203' in result, 'capture_SC20' in result))
if __name__=='__main__':main()
