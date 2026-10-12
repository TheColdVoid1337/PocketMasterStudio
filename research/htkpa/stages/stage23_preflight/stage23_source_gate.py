#!/usr/bin/env python3
"""Stage 23 source-first intake and static-disassembly evidence collector.

This never executes, loads, imports or links the proprietary 5868USB.dll.
NO native loader parity, 4-gain parity, or real WAV input buffers are inferred.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
import wave
import zipfile
from datetime import datetime, timezone
from pathlib import Path

DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
DLL_BYTES = 2_902_016
MODEL = {
    '2203': {'nam_sha': '29abbdbf982ee64b963d1d8de06848d1b06450a623bb08ba3ffefce146dfac42',
             'clo_sha': '50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7'},
    'sc20': {'nam_sha': '509ad3d6dc31cf0539afe4a264ff7386d6282ffe9d1e0de4b6cce514b1915b11',
             'clo_sha': '2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a'},
}
DI_SHA = '9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a'
# Ranges are investigation targets, NOT established function ends.
RANGES = [
    ('alloc_0x1800B5640', 0x1800B5640, 0x1800B5760),
    ('appNamConvertCloData_0x1800ABEB0', 0x1800ABEB0, 0x1800AC300),
    ('namConvertCloData_0x1800E1F70', 0x1800E1F70, 0x1800E3100),
    ('outer_0x1800BE830', 0x1800BE830, 0x1800BF150),
    ('wav_loaders_0x1800BF890_0x1800BFCA0', 0x1800BF890, 0x1800C0300),
]
PINNED = {
    'allocator_store_input': 0x1800B56B5,
    'allocator_store_reference': 0x1800B56F2,
    'reference_mean': 0x1800BE8E7,
    'reference_detrend': 0x1800BE9F2,
    'onset_scan': 0x1800BEA5D,
    'input_pointer': 0x1800BEAF8,
    'reference_pointer': 0x1800BEAFF,
    'input_23_sec': 0x1800BEB2B,
    'target_23_sec': 0x1800BEB41,
    'fit_sample_count': 0x1800BEDD8,
    'fit_call': 0x1800BEDE4,
    'later_iir_call': 0x1800BEE25,
}
INSTR_RE = re.compile(r'^\s*([0-9a-fA-F]+):\s+([a-z][a-z0-9.]*)\s*(.*?)\s*$')
CALL_RE = re.compile(r'\b(?:call|jmp)\s+(?:[a-z]+\s+)?(?:0x)?(180[0-9a-fA-F]{6,})\b', re.I)
FIELD_RE = re.compile(r'\b0x(243e0|243e8|243f0|243f8|243fc|24400|24404)\b', re.I)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def matching_member(z: zipfile.ZipFile, ending: str) -> str:
    ending = ending.replace('\\', '/').lower()
    matches = [x for x in z.namelist() if x.replace('\\', '/').lower().endswith(ending) and not x.endswith('/')]
    if len(matches) != 1:
        raise ValueError(f'{ending!r}: expected unique ZIP member; got {matches!r}')
    return matches[0]


def validate_zip(path: Path) -> dict:
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad is not None:
            raise ValueError(f'ZIP CRC failure at {bad}')
        return {'source': str(path), 'size': path.stat().st_size, 'sha256': sha256_file(path),
                'member_count': len(z.namelist()), 'zip_crc': 'PASS'}


def get_dll(args, private: Path) -> tuple[Path | None, dict]:
    if args.installer and args.dll:
        raise ValueError('Specify either --installer or --dll, not both')
    if not args.installer and not args.dll:
        return None, {'status': 'MISSING_DLL', 'sha256_verified': False}
    if args.dll:
        dll = Path(args.dll)
        provenance = {'origin': 'direct_file', 'path': str(dll)}
    else:
        installer = Path(args.installer)
        provenance = {'origin': 'official_user_zip', 'archive': validate_zip(installer)}
        with zipfile.ZipFile(installer) as z:
            member = matching_member(z, '/5868USB.dll')
            content = z.read(member)
            provenance['zip_member'] = member
        dll = private / '5868USB.dll'
        dll.write_bytes(content)
    size, sha = dll.stat().st_size, sha256_file(dll)
    provenance.update({'sha256': sha, 'size': size,
                       'sha256_verified': sha == DLL_SHA, 'size_verified': size == DLL_BYTES})
    if sha != DLL_SHA or size != DLL_BYTES:
        raise ValueError(f'Wrong DLL build (sha={sha}, bytes={size}); refusing static inference')
    provenance['status'] = 'PINNED_DLL_VERIFIED'
    return dll, provenance


def wav_metadata(data: bytes) -> dict:
    from io import BytesIO
    with wave.open(BytesIO(data), 'rb') as w:
        nch, width, fs, count, typ = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype()
        pcm = w.readframes(count)
    identical = None
    if nch == 2 and width == 2 and len(pcm) % 4 == 0:
        # Compare raw little-endian PCM16 channel words without any conversion.
        import numpy as np
        a = np.frombuffer(pcm, dtype='<i2').reshape(-1, 2)
        identical = bool(np.array_equal(a[:, 0], a[:, 1]))
    return {'sample_rate_hz_in_file': fs, 'channels_in_file': nch, 'sample_width_bytes': width,
            'frames_in_file': count, 'duration_seconds': count / fs, 'compression': typ,
            'stereo_channels_byte_identical': identical,
            'native_context_fs': 'NOT_PROVEN', 'native_context_float32_scaling': 'NOT_PROVEN'}


def capture_record(name: str, path: Path, private: Path) -> dict:
    rec = validate_zip(path)
    rec['label'] = name
    rec['members'] = {}
    out = private / ('capture_' + name)
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        for typ, suffix in [('input_wav', 'wavs/nam_input_wav.wav'),
                            ('output_wav', 'wavs/outputFile.wav'),
                            ('official_clo', 'clo/cloFile.clo')]:
            member = matching_member(z, suffix)
            content = z.read(member)
            dest = out / (typ + ('.wav' if typ.endswith('wav') else '.clo'))
            dest.write_bytes(content)
            meta = {'zip_member': member, 'extracted_private_path': str(dest),
                    'size': len(content), 'sha256': sha256_bytes(content)}
            if typ.endswith('wav'):
                meta['wav'] = wav_metadata(content)
                if typ == 'input_wav':
                    meta['matches_common_DI_sha'] = meta['sha256'] == DI_SHA
            else:
                meta['matches_model_official_clo_sha'] = meta['sha256'] == MODEL[name]['clo_sha']
                if len(content) >= 140:
                    meta['VTSI_magic'] = content[:4] == b'VTSI'
                    meta['four_official_gains_ORACLE_ONLY'] = list(struct.unpack_from('<4f', content, 104))
            rec['members'][typ] = meta
    return rec


def disassemble(dll: Path, dest: Path) -> dict:
    objdump = shutil.which('objdump')
    if not objdump:
        raise RuntimeError('GNU objdump not found; no static disassembly can be produced')
    dest.mkdir(parents=True, exist_ok=True)
    records, pinned = [], {}
    all_refs = []
    for label, begin, end in RANGES:
        cmd = [objdump, '-d', '-M', 'intel', '--no-show-raw-insn',
               f'--start-address=0x{begin:x}', f'--stop-address=0x{end:x}', str(dll)]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if p.returncode:
            raise RuntimeError(f'objdump exit={p.returncode} on {label}: {p.stderr[-500:]}')
        text = p.stdout
        (dest / (label + '.asm')).write_text(text, encoding='utf-8')
        lines = []
        refs = []
        for line in text.splitlines():
            m = INSTR_RE.match(line)
            if not m:
                continue
            addr = int(m.group(1), 16)
            lines.append(addr)
            for n, x in PINNED.items():
                if addr == x:
                    pinned[n] = {'address': f'0x{addr:X}', 'instruction': line.strip(), 'source_range': label}
            cf = CALL_RE.search(line)
            fields = FIELD_RE.findall(line)
            if cf or fields:
                refs.append({'at': f'0x{addr:X}', 'instruction': line.strip(),
                             'branch_destination': '0x' + cf.group(1).lower() if cf else None,
                             'context_fields': ['0x'+i.lower() for i in fields]})
        records.append({'label': label, 'requested_begin': f'0x{begin:X}', 'requested_end': f'0x{end:X}',
                        'instructions_observed': len(lines), 'asm_file': label+'.asm',
                        'asm_sha256': sha256_bytes(text.encode('utf-8')), 'call_or_field_records': len(refs)})
        all_refs.extend(refs)
    (dest / 'call_and_field_index.json').write_text(json.dumps(all_refs, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    return {'source_sha256': sha256_file(dll), 'ranges': records,
            'address_pins_in_dumps': pinned,
            'address_pins_missing': [n for n in PINNED if n not in pinned],
            'call_and_field_index': 'call_and_field_index.json',
            'IMPORTANT': 'Address presence is NOT a proof of producer→consumer dataflow or resample semantics.'}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--installer', help='User-provided Sonicake Manager.zip containing assets/5868USB.dll')
    ap.add_argument('--dll', help='Direct already-extracted exact DLL')
    ap.add_argument('--capture-2203', help='User-provided 2203 Manager capture ZIP')
    ap.add_argument('--capture-sc20', help='User-provided SC20 Manager capture ZIP')
    ap.add_argument('--nam-2203', help='Optional matching 2203 NAM')
    ap.add_argument('--nam-sc20', help='Optional matching SC20 NAM')
    ap.add_argument('--out', default='stage23_evidence', help='Private working output directory; never commit it')
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    private = out / '_private_DO_NOT_COMMIT'
    private.mkdir(exist_ok=True)
    report = {'tool_version': '0.1.0-preflight', 'stage': 23,
              'mode': 'STATIC_SOURCE_GATE_ONLY', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'constraints': ['DLL never executed or loaded', 'No assumptions about native Fs / conversion',
                              'Official CLO only read as held-out oracle', 'No physical pedal writes'],
              'real_native_buffer_proven': False, 'real_four_gains_independently_computed': False,
              'producer_consumer_graph_fully_proven': False}
    try:
        dll, report['dll'] = get_dll(args, private)
        captures = {}
        for name, path in [('2203', args.capture_2203), ('sc20', args.capture_sc20)]:
            if path:
                captures[name] = capture_record(name, Path(path), private)
        report['captures'] = captures
        for name, path in [('2203', args.nam_2203), ('sc20', args.nam_sc20)]:
            if path:
                nam_sha = sha256_file(Path(path))
                report.setdefault('nam_sources', {})[name] = {
                    'sha256': nam_sha, 'matches_handoff_pin': nam_sha == MODEL[name]['nam_sha']}
        if dll is not None:
            report['static_disassembly'] = disassemble(dll, out / 'disassembly')
            report['status'] = 'STATIC_WINDOWS_CAPTURED__NATIVE_LOADER_DATAFLOW_NOT_YET_PROVEN'
        else:
            report['status'] = 'BLOCKED_MISSING_PINNED_DLL_BYTES'
        if len(captures) < 2:
            report['parity_gate'] = 'BLOCKED_MISSING_ONE_OR_BOTH_VENDOR_CAPTURE_BYTES'
        else:
            report['parity_gate'] = 'BLOCKED_NATIVE_LOADER_NOT_YET_RECONSTRUCTED'
    except Exception as exc:
        report['status'] = 'FAILED_SOURCE_INTEGRITY_OR_TOOL'
        report['error'] = repr(exc)
    (out / 'gate.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status':report['status'],'evidence':str(out/'gate.json'),
                      'real_four_gains_independently_computed': False}, indent=2))
    return 1 if report['status'] in ['FAILED_SOURCE_INTEGRITY_OR_TOOL','BLOCKED_MISSING_PINNED_DLL_BYTES'] else 0


if __name__ == '__main__':
    sys.exit(main())
