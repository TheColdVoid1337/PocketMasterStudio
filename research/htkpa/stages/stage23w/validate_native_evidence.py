import json
from pathlib import Path
p=Path(__file__).with_name('native_evidence.json')
d=json.loads(p.read_text())
assert d['status']=='NATIVE_HIT' and d['captured_arrays']
assert d['captured_branches']['lane_0x18000c5b0'].startswith('hit')
assert d['captured_branches']['complex_0x18000c5f0'] == 'not hit'
assert d['dll_sha256']=='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
assert 'Executive result' in Path(__file__).resolve().parents[4].joinpath('docs/HTKPA_STAGE23W_NATIVE_HANDOFF.md').read_text()
assert 'pairwise lane max error 0.0' in d['numerical_checks']
print('Stage23W native-evidence validation: PASS')
