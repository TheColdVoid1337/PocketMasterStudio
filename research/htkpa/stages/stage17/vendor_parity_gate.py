#!/usr/bin/env python3
"""Read-only vendor-fidelity gate. Reference official CLOs ONLY for post-hoc evaluation.

Does not calculate a FIR from reference coefficients. Does not export or upload anything.
Use only when an independent fitter creates candidate files from NAM and probe WAV.
"""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
OFFSETS={'pre_fir':(136,128),'post_fir':(648,2048)}
EXPECTED={'2203':'50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7',
          'sc20':'2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a'}

def crc16_modbus(blob):
    x=0xffff
    for v in blob:
        x^=v
        for _ in range(8):x=(x>>1)^0xA001 if x&1 else x>>1
    return x

def read_clo(path):
    b=Path(path).read_bytes()
    if len(b)!=8840 or b[:4]!=b'VTSI':raise AssertionError('unexpected CLO length/header')
    expect=int.from_bytes(b[8:10],'big');computed=crc16_modbus(b[12:])
    if expect!=computed:raise AssertionError(f'invalid CRC {path}')
    arrays={k:np.frombuffer(b,dtype='<f4',count=n,offset=o).astype(float) for k,(o,n) in OFFSETS.items()}
    if not all(np.isfinite(arr).all() for arr in arrays.values()):raise AssertionError('nonfinite coefficients')
    return {'sha256':hashlib.sha256(b).hexdigest(),'crc':computed,'data':arrays}

def model_report(name,reference,candidate=None):
    ref=read_clo(reference)
    if ref['sha256']!=EXPECTED[name]:raise AssertionError(f'{name} reference does not match pinned capture')
    result={'model':name,'reference_sha256':ref['sha256'], 'reference_crc16':ref['crc'],
            'reference_coefficient_stats':{k:{'sum':float(np.sum(a)), 'l2':float(np.linalg.norm(a)),
              'nonzero_taps':int(np.count_nonzero(a))} for k,a in ref['data'].items()}}
    if candidate is None:
        result['independently_reconstructed_fir']='NOT_PROVIDED'
        result['vendor_parity']='NOT_TESTED'
        return result
    cand=read_clo(candidate)
    comparison={}
    for k,baseline in ref['data'].items():
        b=cand['data'][k]
        denominator=np.linalg.norm(baseline)
        comparison[k]={'relative_l2_error':float(np.linalg.norm(b-baseline)/denominator),
                       'max_abs_error':float(np.max(np.abs(b-baseline))),
                       'cosine_similarity':float(np.dot(b,baseline)/(np.linalg.norm(b)*denominator)) if np.linalg.norm(b)>0 else None,
                       'exact_float32_match':bool(np.array_equal(b,baseline))}
    result.update({'independently_reconstructed_fir':'CANDIDATE_PROVIDED','candidate_sha256':cand['sha256'],
                   'comparison':comparison, 'vendor_parity':'EXACT' if all(x['exact_float32_match'] for x in comparison.values()) else 'NOT_EXACT'})
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--official-2203',required=True,type=Path);p.add_argument('--official-sc20',required=True,type=Path)
    p.add_argument('--candidate-2203',type=Path);p.add_argument('--candidate-sc20',type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();res={'research_only':True,'reference_use':'read-only post-hoc coefficient comparison, NEVER optimization',
        '2203':model_report('2203',a.official_2203,a.candidate_2203),
        'sc20':model_report('sc20',a.official_sc20,a.candidate_sc20)}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(res,sort_keys=True,indent=2)+'\n')
    print(f"2203: {res['2203']['vendor_parity']}; SC20: {res['sc20']['vendor_parity']}")
if __name__=='__main__':main()
