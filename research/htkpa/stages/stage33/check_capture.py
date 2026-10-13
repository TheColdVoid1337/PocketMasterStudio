#!/usr/bin/env python3
"""Stage33: validate one-read native blocks, keep audio exclusively in local archive."""
import argparse, hashlib, json, struct, tarfile
from pathlib import Path
def analyze(path):
    with tarfile.open(path,'r:gz') as t:
        events=[json.loads(x) for x in t.extractfile('frida_capture/events.jsonl')]
        man=json.load(t.extractfile('frida_capture/manifest.json'))
    state=man.get('state',{})
    blocks=[]
    for e in events:
        if e.get('kind')!='hit':continue
        field='input_2048' if e.get('site')=='input_entry' else 'data_1972'
        value=e['fields'].get(field,{})
        if 'error' in value:raise ValueError(str(value['error']))
        if value.get('encoding')!='hex_f64le':raise ValueError('bad sample encoding')
        buf=bytes.fromhex(value['hex'])
        expected=8*value['count']
        if len(buf)!=expected:raise ValueError('bad byte length')
        count=struct.unpack('<'+str(value['count'])+'d',buf)
        item={'site':e['site'],'thread':e.get('thread'),'samples':len(count),
              'sha256':hashlib.sha256(buf).hexdigest(),
              'first3':list(count[:3])}
        if field=='data_1972':
            n=int(e['fields']['copy_bytes']['value'],0)
            item['memcpy_bytes']=n
            if n!=len(buf):raise ValueError('memcpy length mismatch')
        blocks.append(item)
    print(json.dumps({'status':man.get('status'),'completion':man.get('method'),
        'runtime_verified':state.get('runtime_verified'),'field_errors':state.get('field_errors'),
        'blocks':blocks,'limits':'FIR boundary only; native conversion success requires stable_clo_after_hooks; r8brain parity NOT TESTED'},indent=2))
    if not state.get('runtime_verified') or state.get('field_errors') or not blocks:raise SystemExit(2)
    if man.get('method')!='stable_clo_after_hooks':raise SystemExit('[INCOMPLETE] no CLO completion evidence')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('archive',type=Path)
    a=ap.parse_args();analyze(a.archive)
