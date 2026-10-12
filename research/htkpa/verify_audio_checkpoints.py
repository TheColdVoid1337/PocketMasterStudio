#!/usr/bin/env python3
"""Run unchanged Stage21/22/23C/23D scripts using private, temporary aliases.

Requires Python, objdump, NumPy, SciPy, SoundFile. Never loads the vendor DLL.
Only temporary copies and new verification outputs are written; inputs are read-only.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = args.private_root.resolve()
    repo = Path(__file__).resolve().parents[2]
    stages = repo / 'research/htkpa/stages'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    dll = private / 'vendor/5868USB.dll'
    rows = []

    def run(label, *arguments):
        command = [sys.executable, *map(str, arguments)]
        result = subprocess.run(command, cwd=repo, text=True, capture_output=True)
        print(label, 'exit', result.returncode)
        print(result.stdout + result.stderr, end='')
        rows.append({'check': label, 'exit_code': result.returncode})
        if result.returncode:
            raise RuntimeError(f'{label} failed')

    with tempfile.TemporaryDirectory(prefix='htkpa-check-') as temporary:
        compat = Path(temporary)
        for model in ('2203', 'SC20'):
            (compat / model).mkdir()
            for old, new in [('nam_input_wav.wav', 'input_DI.wav'),
                             ('outputFile.wav', 'output_reference.wav')]:
                shutil.copyfile(private / 'captures' / model / new, compat / model / old)
        run('Stage21', stages/'stage21/stage21_saturator_source.py',
            '--dll', dll, '--output', out/'stage21.json')
        run('Stage21 pointer trace', stages/'stage21/native_repack_trace.py', '--dll', dll)
        run('Stage22', stages/'stage22/stage22_pre_fit_trace.py',
            '--dll', dll, '--out', out/'stage22.json')
        run('Stage23C', stages/'stage23c/stage23_polyphase_source.py',
            '--dll', dll, '--out', out/'stage23c.json')
        common = ['--dll', dll, '--2203-capture', compat/'2203',
                  '--sc20-capture', compat/'SC20']
        for suffix in ('', '_repeat'):
            run('Stage23D'+suffix, stages/'stage23d/stage23d_source_provenance.py',
                *common, '--2203-nam', private/'models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam',
                '--sc20-nam', private/'models/Marshall JCM 800 SC20 Full Rig.nam',
                '--out', out/f'stage23d{suffix}.json')
        assert (out/'stage23d.json').read_bytes() == (out/'stage23d_repeat.json').read_bytes()
        run('Stage23D five tests', '-m', 'unittest', 'discover', '-s',
            stages/'stage23d', '-p', 'test_*.py', '-v')
        run('Stage23D PCM addendum', stages/'stage23d/stage23d_pcm_decoder_branch.py', *common)
    report = {'checks': rows, 'stage23d_repeat_identical': True,
              'stage23d_sha256': hashlib.sha256((out/'stage23d.json').read_bytes()).hexdigest(),
              'scope': 'Static source and synthetic checks; real native gain parity NOT_COMPUTED'}
    (out/'verification_summary.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
