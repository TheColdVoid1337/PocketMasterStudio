#!/usr/bin/env python3
"""Stage32: inspect local Frida f64 input/output gate without committing private audio."""
import sys, json, tarfile, collections
from pathlib import Path
def main(path):
    with tarfile.open(path,'r:gz') as t:
        manifest=json.load(t.extractfile('frida_capture/manifest.json'))
        events=[json.loads(line) for line in t.extractfile('frida_capture/events.jsonl')]
    captures=collections.defaultdict(list)
    for e in events:
        if e.get('kind')!='hit':continue
        errors={k:v['error'] for k,v in e.get('fields',{}).items() if isinstance(v,dict) and 'error' in v}
        captures[e['site']].append({'thread':e.get('thread'),'errors':errors,'fields':e['fields']})
    for site,arr in captures.items():
        print('[SITE]',site,'hits',len(arr),'field-error events',sum(bool(x['errors']) for x in arr))
        for e in arr[:4]:
            f=e['fields']
            print(' thread',e['thread'],'bytes',f.get('bytes',{}).get('value'),
                  'input_count',f.get('input_count',{}).get('value'),
                  'prefix_values',len(f.get('output_1972_f64',f.get('input_1024_f64',{})).get('values',[])),
                  'errors',e['errors'])
    state=manifest.get('state',{})
    print('[MANIFEST]',manifest.get('status'),'state_valid',state.get('valid_field_hits'),'errors',state.get('field_errors'))
    if not captures['fir_output_memcpy']:raise SystemExit('[FAIL] output hook not observed')
    if state.get('field_errors'):raise SystemExit('[INCOMPLETE] field reading errors, analyze before claiming parity')
    print('[LIMIT] FIR-stage buffers ONLY. These outputs are not directly 48 kHz / PCM24 and are not native-vs-r8brain parity.')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: check_full_blocks.py frida_archive.tar.gz')
    main(Path(sys.argv[1]))
