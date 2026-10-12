"""Source-derived PCM24 round trip; finite f32, nearest-even environment only.

No DLL execution and no audio/CLO files written. Native source authorities:
1408C0 float -> int32; 08E0E0 writer; 091230 reader; 1417F0 normalization.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'stage23d'))
from stage23d_source_provenance import DLL_SHA, pe_at


def instructions(dll, ranges):
    data = dll.read_bytes()
    if hashlib.sha256(data).hexdigest() != DLL_SHA:
        raise ValueError('unexpected DLL SHA256')
    result = {}
    for lo, hi in ranges:
        raw = subprocess.check_output(['objdump', '-d', '-M', 'intel', '--no-show-raw-insn',
            f'--start-address={lo}', f'--stop-address={hi}', str(dll)], text=True)
        for line in raw.splitlines():
            m = re.match(r'\s*(180[0-9a-f]+):\s+(.+)', line)
            if m:
                result[int(m[1], 16)] = ' '.join(m[2].lower().split())
    return data, result


def verify_pins(assembly, pins):
    for va, expected in pins.items():
        if expected not in assembly.get(va, ''):
            raise AssertionError((hex(va), expected, assembly.get(va)))


PINS = {
    0x18014091e: 'cmp byte ptr [rcx+0x18],0x0',
    0x180140922: 'je 0x180140932',
    0x18008dd0f: 'mov byte ptr [rdi+0x18],r12b',
    0x18008dcd8: 'xor r12d,r12d',
    0x18014096f: '0x18024ced0',
    0x180140979: '0x18024c918',
    0x180140981: '0x18024cd50',
    0x18014098a: '0x18024cd90',
    0x1801409e0: 'movss xmm0,dword ptr [rdx]',
    0x1801409e8: 'cvtps2pd xmm0,xmm0',
    0x1801409eb: 'comisd xmm7,xmm0',
    0x1801409ef: 'jb 0x1801409f9',
    0x1801409f1: 'mov dword ptr [rcx],0x80000000',
    0x1801409f9: 'comisd xmm0,xmm6',
    0x1801409fd: 'jb 0x180140a07',
    0x1801409ff: 'mov dword ptr [rcx],0x7fffffff',
    0x180140a07: 'mulsd xmm0,xmm8',
    0x180140a0c: 'addsd xmm0,xmm9',
    0x180140a11: 'movsd qword ptr [rsp+0x20],xmm0',
    0x180140a17: 'mov eax,dword ptr [rsp+0x20]',
    0x180140a3e: 'call qword ptr [rax+0x8]',
    0x18008e188: 'mov eax,dword ptr [rbp+0x14]',
    0x18008e1aa: 'cmp eax,0x18',
    0x18008e1ad: 'je 0x18008e29d',
    0x18008e330: 'mov r8d,dword ptr [rcx]',
    0x18008e337: 'sar r8d,0x8',
    0x18008e33e: 'mov byte ptr [rax],r8b',
    0x18008e341: 'sar edx,0x8',
    0x18008e344: 'sar r8d,0x10',
    0x18008e348: 'mov byte ptr [rax+0x1],dl',
    0x18008e34b: 'mov byte ptr [rax+0x2],r8b',
    0x18008d56a: 'call 0x180091230',
    0x180091300: 'movzx edx,byte ptr [rax+0x1]',
    0x180091308: 'movsx r8d,byte ptr [rax+0x2]',
    0x18009130d: 'shl r8d,0x8',
    0x180091311: 'or r8d,edx',
    0x180091314: 'movzx edx,byte ptr [rax]',
    0x180091317: 'shl r8d,0x8',
    0x18009131e: 'or r8d,edx',
    0x180091321: 'shl r8d,0x8',
    0x180141869: 'cvtdq2ps xmm1,xmm0',
    0x18014186c: 'mulps xmm1,xmm2',
}


def check_source(dll):
    data, asm = instructions(dll, [(0x1801408c0,0x180140a91), (0x18008dca0,0x18008dd20),
        (0x18008e0e0,0x18008e394), (0x18008d554,0x18008d574),
        (0x180091230,0x180091374), (0x1801417f0,0x180141980)])
    verify_pins(asm, PINS)
    assert struct.unpack('<Q', pe_at(data,0x1802496b0,8))[0] == 0x18008e0e0
    constants = {0x18024ced0:-1., 0x18024c918:1., 0x18024cd50:2147483647.,
                 0x18024cd90:6755399441055744.}
    for va, expected in constants.items():
        assert struct.unpack('<d',pe_at(data,va,8))[0] == expected
    return {'instruction_pins':len(PINS), 'writer_slot_8':'0x18008e0e0',
            'constants':{hex(k):v for k,v in constants.items()}}


def float_to_int32(values):
    x = np.asarray(values, dtype=np.float32).astype(np.float64)
    if not np.isfinite(x).all():
        raise ValueError('nonfinite domain is not implemented')
    # Keep mulsd and addsd separate; inspect LOW dword, do not cast double to int.
    scaled = np.clip(x, -1., 1.) * 2147483647.
    biased = scaled + 6755399441055744.
    result = (biased.view(np.uint64) & 0xffffffff).astype(np.uint32).view(np.int32)
    return np.where(x <= -1., -2147483648,
                    np.where(x >= 1., 2147483647, result)).astype(np.int32)


def pack_pcm24(integers):
    words = np.asarray(integers, dtype=np.int32) >> 8
    return np.stack((words & 255, (words >> 8) & 255, (words >> 16) & 255), axis=-1).astype(np.uint8).tobytes()


def decode_pcm24(payload):
    b = np.frombuffer(payload, np.uint8).reshape(-1, 3).astype(np.uint32)
    words = ((b[:,0] | b[:,1] << 8 | b[:,2] << 16) << 8).view(np.int32)
    return words.astype(np.float32) * np.float32(2**-31)


def roundtrip(values):
    return decode_pcm24(pack_pcm24(float_to_int32(values)))


def experiment():
    # Independent int conversion oracle; no vendor coefficients/audio involved.
    rng = np.random.default_rng(23)
    random_bits = rng.integers(0, 2**32, 1_000_000, dtype=np.uint32)
    x = random_bits.view(np.float32)
    x = x[np.isfinite(x)]
    scaled = np.clip(x.astype(np.float64), -1., 1.) * 2147483647.
    expected = np.rint(scaled).astype(np.int64)
    expected[x <= -1.] = -2147483648
    expected[x >= 1.] = 2147483647
    assert np.array_equal(float_to_int32(x), expected)
    y = np.linspace(-1., 1., 100001, dtype=np.float32)
    q = roundtrip(y)
    generic = (np.clip(np.rint(y.astype(np.float64)*8388608.), -8388608, 8388607)/8388608.).astype(np.float32)
    return {'finite_random_f32_checked':len(x), 'int32_oracle_mismatches':0,
            'uniform_grid_samples':len(y), 'direct_round24_disagreements':int(np.count_nonzero(q != generic)),
            'max_roundtrip_error_grid':float(np.max(np.abs(q-y))),
            'scope':'source-derived finite-domain arithmetic; no native DLL execution / resampled DI / gains'}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r={'dll_sha256':DLL_SHA,'source':check_source(a.dll),'experiment':experiment()}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(r['experiment'],indent=2))
