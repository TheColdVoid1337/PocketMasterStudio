#!/usr/bin/env python3
"""Read-only reverse engineering evidence for user-supplied Sonicake 5868USB.dll.
Never loads/executes the DLL; no device connection. Uses objdump for x64 disassembly.
"""
import argparse
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

BASE = 0x180000000
DLL_SHA256 = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
ENTRY = 0x1800BE830
END = 0x1800BF55D


def pe_sections(data):
    if data[:2] != b'MZ': raise ValueError('not MZ')
    pe = struct.unpack_from('<I', data, 0x3c)[0]
    if data[pe:pe + 4] != b'PE\0\0': raise ValueError('not PE')
    count = struct.unpack_from('<H', data, pe + 6)[0]
    opt_size = struct.unpack_from('<H', data, pe + 20)[0]
    off = pe + 24 + opt_size
    out = []
    for k in range(count):
        p = off + 40 * k
        name = data[p:p + 8].split(b'\0', 1)[0].decode('ascii', errors='replace')
        vs, va, rs, raw = struct.unpack_from('<IIII', data, p + 8)
        out.append((name, va, vs, rs, raw))
    return out


def pe_read(data, sections, va, fmt):
    rva = va - BASE
    for name, start, vs, rs, raw in sections:
        if start <= rva and rva + struct.calcsize(fmt) <= start + rs:
            return struct.unpack_from(fmt, data, raw + rva - start)[0]
    raise ValueError('VA unmapped: ' + hex(va))


def lines_between(lines, start, stop):
    out = []
    for line in lines:
        m = re.match(r'^\s*([0-9a-fA-F]+):\s+', line)
        if m and start <= int(m.group(1), 16) < stop:
            out.append(line.strip())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dll', type=Path, help='Path to user-provided 5868USB.dll')
    ap.add_argument('--cached-disasm', type=Path, help='Optional existing objdump -d -M intel text')
    ap.add_argument('--out', type=Path, default=Path('htkpa_static_evidence.json'))
    args = ap.parse_args()
    data = args.dll.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if sha != DLL_SHA256: raise ValueError('DLL hash differs; this analysis only covers pinned DLL')
    sections = pe_sections(data)
    constants = {
        'duration_seconds': (0x18024CD6C, '<f'),
        'extra_samples': (0x18024CDA4, '<f'),
        'threshold_abs': (0x18024C6C8, '<d'),
        'pre_FIR_taps': (0x18024CD80, '<f'),
        'post_FIR_taps_disk': (0x18024CDBC, '<f'),
        'post_FIR_taps_low': (0x18024CDA0, '<f'),
        'window_5_seconds': (0x18024CCD0, '<f'),
        'window_15_seconds': (0x18024CD34, '<f'),
        'window_20_seconds': (0x18024CD40, '<f'),
    }
    values = {k:pe_read(data, sections, va, fmt) for k,(va,fmt) in constants.items()}
    if args.cached_disasm:
        asm_lines = args.cached_disasm.read_text(errors='replace').splitlines()
    else:
        # Disassembly of bytes only: DLL is NEVER executed/loaded.
        result = subprocess.run(['objdump','-d','-M','intel','--no-show-raw-insn',
          '--start-address=0x18000f940','--stop-address=0x1800c0660',str(args.dll)],
          capture_output=True, text=True, check=True)
        asm_lines = result.stdout.splitlines()
    asm = lines_between(asm_lines, ENTRY, END)
    if len(asm) < 500: raise ValueError(f'expected hundreds of HTKPA instructions, got {len(asm)}')
    prelude = lines_between(asm_lines, 0x18000f940,0x18000fa50)
    setup = lines_between(asm_lines, 0x1800b5850,0x1800b5a20)
    def evidence(substr):
        matches=[x for x in asm if substr in x]
        if not matches: raise ValueError(f'missing evidence: {substr}')
        return matches
    checks = {
       'invocation': [x for x in prelude if 'call   0x1800be830' in x],
       'demean_loop': evidence('1800be92c:'),
       'detrend_slope': evidence('1800be9f2:'),
       'detrend_loop': evidence('1800bea30:'),
       'six_second_offset': evidence('1800bea61:'),
       'post6s_scan_600_samples': evidence('1800bea64:'),
       'window_23s': evidence('1800beb2b:'),
       'window_30s': evidence('1800beb4d:'),
       'window_50s': evidence('1800beb6f:'),
       'first_stage': evidence('call   0x1800bdbe0'),
       'second_stage': evidence('call   0x1800bd490'),
       'third_stage': evidence('call   0x1800bc6b0'),
       'fit_pass_function': evidence('call   0x1800bb210'),
       'fit_loop_three_passes': evidence('cmp    rbx,0x3'),
       'last_stage': evidence('call   0x1800b9b70'),
       'format_VTSI': evidence('0x49535456'),
       'container_8840': evidence('0x2288'),
       'body_8704': evidence('0x2200'),
       'crc': evidence('1800bf510:'),
    }
    if not checks['invocation']:raise ValueError('call edge from caller not found')
    if len(checks['fit_pass_function']) != 1:raise ValueError('unexpected fit pass call count')
    if len([x for x in asm if 'call   0x1800bb210' in x])!=1 or not checks['fit_loop_three_passes']:
        raise ValueError('3-pass control flow unverified')
    result={
      'dll_sha256':sha, 'pe':'PE32+ x64','main_entry_va':hex(ENTRY),
      'reference_constants':values, 'static_assembly_evidence':checks,
      'interpretation':{
       'zero_centered_linear_detrend':'applied in-place to +0x243e8 buffer',
       'work_length_formula':'N = 70 * sample_rate + 600 (buffer padded)',
       'discrete_onset_search':'start 6 * sample_rate; test <= 600 samples, abs(x)>0.01',
       'other_segment_offsets_sec':[23,30,50],
       'other_window_sizes_sec':[5,15,20],
       'fit':'0x1800bb210 called inside loop bounded by 3; pass arguments vary',
       'pack':'VTSI 8840 bytes; gains, FIR A, FIR B and CRC written',
       'limitations':'not decompiled fully; no claim of identical SONICLINK algorithm or exact DSP fit'
      }
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('PASS pinned DLL',sha[:16], 'constants:', values)
    print('PASS',len(checks),'static code features, assembly instructions:',len(asm))
    print('Evidence written:',args.out)

if __name__ == '__main__': main()
