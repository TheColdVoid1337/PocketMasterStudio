#!/usr/bin/env python3
"""Stage35 private binary block validation. No raw audio is printed or committed."""
import hashlib,json,tarfile,sys
from pathlib import Path
def main(filename):
    with tarfile.open(filename,'r:gz') as archive:
        manifest=json.load(archive.extractfile('frida_capture/manifest.json'))
        events=[json.loads(x) for x in archive.extractfile('frida_capture/events.jsonl')]
        blocks=[e for e in events if e.get('kind')=='binary_block']
        hits=[e for e in events if e.get('kind')=='hit' and e.get('site')=='one_binary_copy']
        if len(blocks)!=1 or len(hits)!=1:raise ValueError('Expected exactly one binary block and one hit')
        record=blocks[0]
        blob=archive.extractfile('frida_capture/'+record['file']).read()
        if len(blob)!=1972*8 or record.get('bytes')!=len(blob):raise ValueError('Incorrect length')
        if hashlib.sha256(blob).hexdigest()!=record['sha256']:raise ValueError('Incorrect SHA256')
        copied=int(hits[0]['fields']['byte_count']['value'],0)
        if copied!=len(blob):raise ValueError('Native memcpy byte count mismatch')
        if hits[0]['fields']['source_block'].get('error'):raise ValueError('Frida field error')
        st=manifest.get('state',{})
        if not st.get('runtime_verified') or st.get('field_errors') or st.get('hook_errors'):raise ValueError('Frida verification failed')
        print(json.dumps({'status':manifest.get('status'),'completion':manifest.get('method'),
              'block_samples_f64':1972,'captured_bytes':len(blob),'sha256':record['sha256'],
              'vendor_conversion_completed':manifest.get('method')=='stable_clo_after_hooks',
              'signal_parity_to_r8brain':'NOT_TESTED'},indent=2))
        if manifest.get('method')!='stable_clo_after_hooks':raise SystemExit('INCOMPLETE: not confirmed by CLO')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: check_capture.py capture.tar.gz')
    main(Path(sys.argv[1]))
