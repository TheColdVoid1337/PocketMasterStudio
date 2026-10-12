#!/usr/bin/env python3
"""Static WAV-reader proof and independent PCM16 buffer experiment.

Never executes the DLL. No resampler substitution, solver calls or CLO inputs.
Scope: ordinary RIFF PCM16 with separate destination buffers, default nearest
rounding; this is not a general implementation of every native reader branch.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'stage23d'))
from stage23d_source_provenance import DLL_SHA, pe_at

# Selected instruction predicates; full disassembly remains private/local.
PINS = {
    # WAV format registration, factory and reader constructor.
    0x180142509: 'call 0x1801434d0',
    0x180143512: '0x180249c10',
    0x18014247a: 'mov r9,qword ptr [rdx+0x50]',
    0x18014248e: 'call r9',
    0x18014334a: 'call 0x18008bb70',
    0x18014335a: 'cmp byte ptr [rax+0x85],0x0',
    0x180143361: 'je 0x180143408',
    0x18008bbe1: 'xor esi,esi',
    0x18008bbf1: 'mov byte ptr [rdi+0x24],sil',
    0x18008bc56: '0x180249390',
    0x18008bc76: 'mov word ptr [rdi+0x84],0x0',
    0x18008bd00: 'cmp eax,0x46464952',
    0x18008bd46: 'cmp eax,0x45564157',
    0x18008be4d: 'cmp ebx,0x20746d66',
    0x18008be68: 'movzx ebx,ax',
    0x18008be78: 'mov dword ptr [rdi+0x20],ecx',
    0x18008be8d: 'movsd qword ptr [rdi+0x8],xmm0',
    0x18008becc: 'mov dword ptr [rax+0x10],edx',
    0x18008bf0c: 'imul eax,edx',
    0x18008bf0f: 'shr eax,0x3',
    0x18008bf12: 'mov dword ptr [rdi+0x80],eax',
    0x18008bf18: 'cmp bx,0x3',
    0x18008bf1c: 'jne 0x18008bf27',
    0x18008bf1e: 'mov byte ptr [rdi+0x24],0x1',
    0x18008bf27: 'mov eax,0xfffe',
    0x18008bf2f: 'jne 0x18008c150',
    0x18008c17a: 'cmp bx,0x1',
    0x18008c17e: 'je 0x18008c442',
    0x18008c193: 'cmp ebx,0x61746164',
    0x18008c209: 'idiv rcx',
    0x18008c20c: 'mov qword ptr [rdi+0x18],rax',
    # Dispatch and integer deinterleave.
    0x18014171c: 'call qword ptr [rax+0x20]',
    0x18008d4b7: 'mov eax,0x1680',
    0x18008d4c1: 'idiv r8d',
    0x18008d511: 'cmp eax,0x10',
    0x18008d514: 'je 0x18008d574',
    0x18008d58a: 'call 0x180091110',
    0x1800911c3: 'add r9,r9',
    0x1800911d0: 'movzx eax,word ptr [rdx]',
    0x1800911d7: 'shl eax,0x10',
    0x1800911da: 'add rdx,r9',
    0x1800911e1: 'mov dword ptr [rcx-0x4],eax',
    0x1800911fb: 'add rbx,0x2',
    0x1800911ff: 'add r14,0x8',
    0x18014228d: 'call 0x180141680',
    0x1801422b9: 'cmp byte ptr [r14+0x24],0x0',
    0x1801422be: 'jne 0x1801423b9',
    0x1801422d1: 'call 0x1801417f0',
    0x180141804: '0x18024c4c4',
    0x180141869: 'cvtdq2ps xmm1,xmm0',
    0x18014186c: 'mulps xmm1,xmm2',
    # Loader channel zero and zero-filled 70s + 600 capacity.
    0x1800bf7f5: 'call 0x1801421c0',
    0x1800bf81c: 'mov r15,qword ptr [rax]',
    0x1800bf81f: '0x18024cda4',
    0x1800bf827: '0x18024ccb0',
    0x1800bf85c: 'xor edx,edx',
    0x1800bf865: 'call 0x1800a504e',
    0x1800bf897: 'mov eax,dword ptr [rdx+r15*1]',
    0x1800bf89b: 'mov dword ptr [rdx+rcx*1],eax',
    0x1800bf8b5: 'mulss xmm0,xmm6',
    0x1800bfc05: 'call 0x1801421c0',
    0x1800bfc2c: 'mov r15,qword ptr [rax]',
    0x1800bfc75: 'call 0x1800a504e',
    0x1800a504e: '0x18018b6a8',
    # Resampler input, binary32 length arithmetic and zero flush.
    0x18000d5ed: 'call 0x180143310',
    0x18000d76d: 'call 0x1801421c0',
    0x18000d786: 'call 0x18000ce00',
    0x18000cfa0: 'cvtps2pd xmm0,xmm0',
    0x18000d036: 'cvtdq2ps xmm0,xmm0',
    0x18000d039: 'mulss xmm0,xmm8',
    0x18000d03e: 'divss xmm0,xmm9',
    0x18000d043: 'cvttss2si rbx,xmm0',
    0x18000d0b0: 'mov qword ptr [rax],rbp',
    0x18000d10e: 'call r10',
    0x18000d13b: 'cmovg r13d,ebx',
    0x18000d16b: 'cvtpd2ps xmm0,xmm0',
    0x18000d17f: 'movss dword ptr [rcx+rdx*4],xmm0',
    # Intermediate file writer: mono and 24-bit request, not just a RAM copy.
    0x180010f22: 'mov r14d,0x1',
    0x18001100b: 'mov dword ptr [rsp+0x20],0x18',
    0x180011013: 'mov r9d,r14d',
    0x18000d840: 'mov eax,dword ptr [rbp+0x80]',
    0x18000d846: 'mov dword ptr [rsp+0x20],eax',
    0x18000d858: 'call 0x1801428e0',
    0x180142942: 'mov esi,dword ptr [rsp+0x100]',
    0x180142a14: 'mov dword ptr [rsp+0x20],esi',
    0x180142a24: 'call 0x18008dca0',
    0x18008dd09: 'mov eax,dword ptr [rbp+0x70]',
    0x18008dd0c: 'mov dword ptr [rdi+0x14],eax',
    0x18000d87f: 'call 0x180142000',
    0x180142198: 'call 0x1801408c0',
    # Fractional ring reset and streaming phase update (kernel still open).
    0x1800121d8: 'mov dword ptr [rsi+0x1028],0xf5',
    0x180013d3c: 'mov dword ptr [rcx+0x1028],0xf5',
    0x180013d49: 'mov qword ptr [rcx+0x1020],rdi',
    0x180013d50: 'add rcx,0x7b0',
    0x180013d59: 'lea r8d,[rdi+0x58]',
    0x180013d5d: 'call 0x1800a504e',
    0x180013d6e: 'movups xmmword ptr [rbx+0x1038],xmm0',
    0x18001362b: 'mov eax,0x100',
    0x180013640: 'lea rdi,[rbx+0x800]',
    0x18001372a: 'movzx eax,cl',
    0x18001373e: 'cmp edx,0xd',
    0x180013c59: 'mulsd xmm5,qword ptr [r10+0x1008]',
    0x180013c62: 'divsd xmm5,qword ptr [r10+0x1010]',
    0x180013c6b: 'addsd xmm5,qword ptr [r10+0x1040]',
    0x180013c74: 'cvttsd2si eax,xmm5',
    0x180013c9e: 'movzx r8d,al',
    0x180013cad: 'movsd qword ptr [r10+0x1038],xmm5',
    0x180013ce5: 'cmp dword ptr [r10+0x102c],0x3e8',
    0x180013d03: 'mov qword ptr [r10+0x1040],rcx',
    0x180013d0a: 'mov qword ptr [r10+0x102c],0x0',
}

RANGES = [(0x1801423f0, 0x180142553), (0x180143310, 0x180143525),
          (0x18008bb70, 0x18008bf35), (0x18008c150, 0x18008c220),
          (0x180141680, 0x180141980), (0x18008d3e0, 0x18008d6b7),
          (0x180091110, 0x18009122b), (0x1801421c0, 0x1801423db),
          (0x1800bf5e0, 0x1800bfce0), (0x1800a504e, 0x1800a5054),
          (0x18000d4a0, 0x18000d884), (0x18000ce00, 0x18000d1ae),
          (0x180010e70, 0x180011026), (0x1801428e0, 0x180142a6d),
          (0x18008dca0, 0x18008dd20), (0x180142000, 0x1801421b8),
          (0x180012170, 0x180012213), (0x1800135c0, 0x180013d87)]


def check_source(dll):
    data = dll.read_bytes()
    if hashlib.sha256(data).hexdigest() != DLL_SHA:
        raise ValueError('unexpected DLL hash')
    instructions = {}
    for lo, hi in RANGES:
        result = subprocess.check_output(['objdump', '-d', '-M', 'intel',
            '--no-show-raw-insn', f'--start-address={lo}', f'--stop-address={hi}', str(dll)], text=True)
        for line in result.splitlines():
            match = re.match(r'\s*(180[0-9a-f]+):\s+(.+)', line)
            if match:
                instructions[int(match[1], 16)] = ' '.join(match[2].lower().split())
    for address, expected in PINS.items():
        if expected not in instructions.get(address, ''):
            raise AssertionError((hex(address), expected, instructions.get(address)))
    pointers = {0x180249c60: 0x180143310, 0x1802493b0: 0x18008d3e0}
    for address, expected in pointers.items():
        assert struct.unpack('<Q', pe_at(data, address, 8))[0] == expected
    constants = {0x18024c4c4: 2**-31, 0x18024cd6c: 70.,
                 0x18024cda4: 600., 0x18024ccb0: 4.}
    for address, expected in constants.items():
        assert struct.unpack('<f', pe_at(data, address, 4))[0] == expected
    imports = subprocess.check_output(['objdump', '-p', str(dll)], text=True)
    assert re.search(r'0018b6a8\s+.*\bmemset\b', imports)
    return {'dll_sha256': DLL_SHA, 'instruction_pins': len(PINS),
            'addresses': [hex(a) for a in PINS], 'vtable_pointers': {hex(k): hex(v) for k, v in pointers.items()},
            'constants': {hex(k): v for k, v in constants.items()}, 'memset_import_verified': True}


def parse_pcm16(blob):
    """Strict small RIFF parser for these fixtures, not the vendor parser."""
    if blob[:4] != b'RIFF' or blob[8:12] != b'WAVE':
        raise ValueError('only RIFF/WAVE supported')
    end = struct.unpack_from('<I', blob, 4)[0] + 8
    if end != len(blob):
        raise ValueError('RIFF size mismatch')
    chunks, payload, fmt = [], None, None
    offset = 12
    while offset < end:
        if offset + 8 > end:
            raise ValueError('truncated chunk header')
        tag, size = struct.unpack_from('<4sI', blob, offset)
        start = offset + 8
        if start + size + (size & 1) > end:
            raise ValueError('truncated chunk payload')
        chunks.append({'tag': tag.decode('ascii'), 'size': size, 'offset': start})
        if tag == b'fmt ':
            if fmt is not None or size < 16:
                raise ValueError('invalid or duplicate fmt')
            fmt = struct.unpack_from('<HHIIHH', blob, start)
        if tag == b'data':
            if payload is not None:
                raise ValueError('duplicate data')
            payload = blob[start:start+size]
        offset = start + size + (size & 1)
    if fmt is None or payload is None:
        raise ValueError('missing fmt/data')
    tag, channels, rate, byte_rate, align, bits = fmt
    if tag != 1 or bits != 16 or channels not in (1, 2):
        raise ValueError('experiment supports ordinary mono/stereo PCM16 only')
    if align != channels*2 or byte_rate != rate*align or rate <= 0 or len(payload) % align:
        raise ValueError('invalid PCM layout')
    return {'format_tag': tag, 'channels': channels, 'rate': rate, 'bits': bits,
            'block_align': align, 'frames': len(payload)//align, 'chunks': chunks}, payload


def decode_pcm16_words(payload, channels):
    # movzx word; shl eax,16; store dword. Interpret the bit pattern as signed
    # for cvtdq2ps; every PCM16 left-justified value is exactly representable.
    words = np.frombuffer(payload, dtype='<u2').reshape(-1, channels)
    integers = (words.astype(np.uint32) << 16).view(np.int32)
    return integers.astype(np.float32) * np.float32(2**-31)


def loader_channel_zero(decoded, rate):
    frames = int(np.float32(np.float32(rate) * np.float32(70)))
    if len(decoded) < frames:
        raise ValueError('native loader requires at least 70 seconds')
    buffer = np.zeros(frames + 600, dtype=np.float32)
    buffer[:frames] = decoded[:frames, 0]
    return buffer


def resampled_count(frames, source_rate, target_rate):
    # Preserve cvtdq2ps -> mulss -> divss -> cvttss2si; not f64 N*ratio.
    return int(np.float32(np.float32(np.float32(frames) * np.float32(target_rate)) / np.float32(source_rate)))


def capture_experiment(private):
    rows = []
    manifest = json.loads((private/'manifest.json').read_text(encoding='utf-8'))
    expected = {r['path'].split('research/_LOCAL_FILES/', 1)[1]: r['sha256'] for r in manifest['files']}
    for model in ('2203', 'SC20'):
        for name in ('input_DI.wav', 'output_reference.wav'):
            relative = f'captures/{model}/{name}'
            blob = (private/relative).read_bytes()
            digest = hashlib.sha256(blob).hexdigest()
            assert digest == expected[relative]
            meta, payload = parse_pcm16(blob)
            decoded = decode_pcm16_words(payload, meta['channels'])
            independent, rate = sf.read(io.BytesIO(blob), dtype='float32', always_2d=True)
            assert rate == meta['rate'] and np.array_equal(decoded, independent)
            assert np.array_equal(decoded[:, 0], decoded[:, 1])
            row = {'model': model, 'role': 'DI' if name.startswith('input') else 'reference',
                   'wav_sha256': digest, **meta, 'reader_float_flag': 0,
                   'int32_normalization_branch': 'TAKEN_UNDER_SUCCESSFUL_WAV_READER_PATH',
                   'soundfile_all_channels_max_error': float(np.max(np.abs(decoded-independent))),
                   'decoded_channel_zero_f32_sha256': hashlib.sha256(decoded[:, 0].astype('<f4').tobytes()).hexdigest()}
            if row['role'] == 'reference':
                buffer = loader_channel_zero(decoded, rate)
                row.update({'pre_detrend_context_frames': len(buffer), 'zero_tail_frames': 600,
                            'pre_detrend_context_f32_sha256': hashlib.sha256(buffer.astype('<f4').tobytes()).hexdigest(),
                            'scope': 'reconstruction conditional on this saved WAV being the loaded file'})
            rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dll', type=Path, required=True)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = {'stage': '23E', 'source': check_source(args.dll),
              'capture_experiment': capture_experiment(args.private_root),
              'resampler_output_frames_44100_to_48000': resampled_count(3087000, 44100, 48000),
              'native_gain_parity': {'2203': 'NOT_COMPUTED', 'SC20': 'NOT_COMPUTED'},
              'open': ['native FIR taps and 673-phase coefficient generator',
                       'full streaming phase and edge reproduction',
                       '24-bit intermediate WAV writer rounding/clipping and reload',
                       'exact f32 target detrend/onset and session provenance']}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n', encoding='utf-8')
    print(f"Stage23E PASS: {len(PINS)} instruction pins; four WAVs; both gains NOT_COMPUTED")


if __name__ == '__main__':
    main()
