#!/usr/bin/env python3
"""DLL read-only instruction trace + two paired CLO phase fingerprints.

No executable vendor code is loaded/run, and no sound patches are emitted.
Only hashes/statistics are emitted; no proprietary original tap vectors.
"""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
import numpy as np
from minimum_phase import minimum_phase_from_magnitude, cosine, relative_error

EXPECTED='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
PROOFS={
 'logf_spectrum': (0x1800b73bb,'call   0x18017e14c'),
 'spectral_interpolation': (0x1800b7450,'call   0x1800b5d00'),
 'mirror_reverse_index': (0x1800b748f,'[r14+rax*4]'),
 'complex_spectrum_transform': (0x1800b754a,'call   0x1800b4a50'),
 'complex_conjugate_fold': (0x1800b7569,'call   0x1800b6e30'),
 'complex_reconstruction': (0x1800b7590,'call   0x1800b4f60'),
 'exp_of_log_re': (0x1800b75d5,'call   0x18017e12e'),
 'cos_of_phase': (0x1800b75e1,'call   0x18017e11c'),
 'exp_times_cos': (0x1800b75e6,'mulss  xmm0,xmm6'),
 'sin_of_phase': (0x1800b75f4,'call   0x18017e164'),
 'exp_times_sin': (0x1800b75f9,'mulss  xmm0,xmm6'),
 'store_real': (0x1800b75ea,'movss  DWORD PTR'),
 'store_imag': (0x1800b7601,'movss  DWORD PTR'),
 'hermitian_re_add': (0x1800b6edb,'addss'),
 'hermitian_im_subtract': (0x1800b6eeb,'subss'),
 'spectrum_complex_fft_basis': (0x1800b7534,'call   0x1800b52e0'),
 'block_transform_initialization': (0x1800b5aa5,'call   0x1800c0d40'),
 'block_transform_call': (0x1800b5b4b,'call   0x1800c0f60'),
 'fixed_fft_work_buffer': (0x1800b65b8,'0x400'),
 'fixed_work_count': (0x1800b65f5,'0x100'),
}


def disasm(dll,lo,hi):
    cmd=['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo:#x}',f'--stop-address={hi:#x}',str(dll)]
    r=subprocess.run(cmd,capture_output=True,text=True,check=True)
    return {int(x.split(':')[0].strip(),16):x.strip() for x in r.stdout.splitlines() if re.match(r'^\s*[0-9a-fA-F]+:',x)}


def crc16(data):
    x=65535
    for v in data:
        x ^= v
        for _ in range(8): x=(x>>1)^(0xA001 if x&1 else 0)
    return x


def read_clo(path):
    b=path.read_bytes()
    assert len(b)==8840 and b[:4]==b'VTSI'
    assert crc16(b[12:]) == struct.unpack_from('>H',b,8)[0]
    return {'pre': np.frombuffer(b,dtype='<f4',count=128,offset=136).astype(float),
            'post':np.frombuffer(b,dtype='<f4',count=1881,offset=648).astype(float),
            'sha256':hashlib.sha256(b).hexdigest()}


def audit(name,path):
    data=read_clo(path); result={'sha256':data['sha256']}
    for part in ['pre','post']:
        h=data[part]
        minphase=minimum_phase_from_magnitude(h)
        result[part]={'minphase_cosine':cosine(h,minphase),
                      'normalized_residual':relative_error(h,minphase),
                      'peak_tap':int(np.argmax(abs(h))),
                      'tap_count_analyzed':int(h.size)}
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--dll',required=True,type=Path)
    for k in ['official_2203','void_2203','official_sc20','void_sc20','v01_2203','v02c_2203']:
        p.add_argument('--'+k.replace('_','-'),required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    a=p.parse_args(); digest=hashlib.sha256(a.dll.read_bytes()).hexdigest()
    assert digest==EXPECTED,('Unknown DLL: '+digest)
    dis={};dis.update(disasm(a.dll,0x1800b52e0,0x1800b53a0));dis.update(disasm(a.dll,0x1800b5a30,0x1800b5b80));dis.update(disasm(a.dll,0x1800b65a0,0x1800b6620));dis.update(disasm(a.dll,0x1800b6e30,0x1800b6f00));dis.update(disasm(a.dll,0x1800b72e0,0x1800b7620))
    got={}
    for label,(addr,fragment) in PROOFS.items():
        line=dis.get(addr,'')
        assert fragment in line,(label,hex(addr),fragment,line)
        got[label]=line
    summary={'dll_sha256':digest,'static_pin_count':len(got),'static_pins':got,'cases':{}}
    for k in ['official_2203','void_2203','official_sc20','void_sc20','v01_2203','v02c_2203']:
        summary['cases'][k]=audit(k,getattr(a,k))
    for k in ['official_2203','official_sc20']:
        assert summary['cases'][k]['post']['minphase_cosine']>0.998
    for k in ['void_2203','void_sc20']:
        assert abs(summary['cases'][k]['post']['minphase_cosine'])<0.5
    for k in ['official_2203','official_sc20']:
        assert summary['cases'][k]['pre']['minphase_cosine']>0.999
    j=read_clo(a.official_2203)['post']
    result={}
    for k in ['void_2203','v01_2203','v02c_2203']:
        x=read_clo(getattr(a,k))['post']
        result[k]={'raw_cosine_with_official':cosine(j,x),
                   'projected_cosine_with_official':cosine(j,minimum_phase_from_magnitude(x))}
    summary['2203_cross_reference']=result
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'passed':True,'proofs':len(got),'cases':{k:{'post_cosine':round(v['post']['minphase_cosine'],6),'pre_cosine':round(v['pre']['minphase_cosine'],6)} for k,v in summary['cases'].items()}},indent=2))
if __name__=='__main__':main()
