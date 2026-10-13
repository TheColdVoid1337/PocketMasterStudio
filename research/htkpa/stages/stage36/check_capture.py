#!/usr/bin/env python3
"""Stage36 bounded input/output binary capture validation. No audio disclosure."""
import hashlib,json,sys,tarfile
from pathlib import Path
def main(filename):
    with tarfile.open(filename,'r:gz') as arc:
        man=json.load(arc.extractfile('frida_capture/manifest.json'))
        events=[json.loads(x) for x in arc.extractfile('frida_capture/events.jsonl')]
        chunks={}
        for e in events:
            if e.get('kind')!='binary_block':continue
            site=e.get('site')
            if site not in ('input','output') or site in chunks:raise ValueError('unexpected binary site/duplicate')
            name='frida_capture/'+e['file']
            blob=arc.extractfile(name).read()
            expect=256 if site=='input' else 1972
            if len(blob)!=expect*8 or e.get('bytes')!=len(blob):raise ValueError('block length mismatch')
            if hashlib.sha256(blob).hexdigest()!=e.get('sha256'):raise ValueError('SHA mismatch')
            chunks[site]={'samples':expect,'bytes':len(blob),'sha256':e['sha256']}
    st=man.get('state',{})
    hits={e['site']:e for e in events if e.get('kind')=='hit' and e.get('site') in ('input','output')}
    good=(set(chunks)=={'input','output'} and set(hits)=={'input','output'}
          and st.get('runtime_verified') and not st.get('field_errors') and not st.get('hook_errors')
          and man.get('method')=='stable_clo_after_hooks')
    print(json.dumps({'status':'PASS_CAPTURE_ONLY' if good else 'INCOMPLETE',
                      'completion':man.get('method'),'blocks':chunks,
                      'paired_same_run':set(chunks)=={'input','output'},
                      'mathematically_matched_fir_blocks':False,
                      'full_r8brain_parity':'NOT_TESTED'},indent=2))
    if not good:raise SystemExit(2)
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: check_capture.py archive.tar.gz')
    main(Path(sys.argv[1]))
