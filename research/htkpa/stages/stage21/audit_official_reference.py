#!/usr/bin/env python3
"""Reference check ONLY. Does NOT generate gains or fit to vendor CLO parameters."""
import argparse, hashlib, io, json, struct, wave, zipfile
from pathlib import Path
import numpy as np
SOURCES={
'JCM800_2203':('Sonicake Manager Files.zip','50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7'),
'JCM800_SC20':('Sonicake Manager(1).zip','2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a')}

def inspect(root):
    result={'purpose':'READ_ONLY vendor-file verification; params MUST NOT be used as fitter input',
            'native_parameters_recomputed':'NOT_COMPUTED','initial_A_B':'NOT_COMPUTED','models':{}}
    inputs=[]
    for name,(filename,sha) in SOURCES.items():
        with zipfile.ZipFile(Path(root)/filename) as z:
            clo=z.read('clo/cloFile.clo')
            assert len(clo)==8840 and clo[:4]==b'VTSI' and hashlib.sha256(clo).hexdigest()==sha
            row={'clo_sha256':sha,'vendor_only_gains':dict(zip(('pmax','nmax','prate','nrate'),struct.unpack_from('<4f',clo,104)))}
            for label,entry in [('DI','wavs/nam_input_wav.wav'),('model_output','wavs/outputFile.wav')]:
                audio=z.read(entry)
                with wave.open(io.BytesIO(audio),'rb') as wav:
                    row[label]={'sample_rate':wav.getframerate(),'channels':wav.getnchannels(),
                                'frames':wav.getnframes(),'duration_seconds':wav.getnframes()/wav.getframerate(),
                                'sha256':hashlib.sha256(audio).hexdigest()}
                if label=='DI':inputs.append(row[label]['sha256'])
            result['models'][name]=row
    result['identical_source_DI']=inputs[0]==inputs[1]
    assert result['identical_source_DI']
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    evidence=inspect(a.root)
    Path(a.output).write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    print('VERIFIED matched 70s source DI, 2 vendor CLO SHA pins; independent gain fit NOT_COMPUTED')
