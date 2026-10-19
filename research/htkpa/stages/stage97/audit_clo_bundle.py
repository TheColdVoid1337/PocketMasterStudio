#!/usr/bin/env python3
"""Stage97 private offline audit of Manager CLO/WAV/log bundle and Stage96 trace.

No native execution, network access, audio export, NAM parsing or hardware I/O.
Archive members and sizes are bounded. Never print private log lines/paths.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import json
import math
import re
import struct
import tarfile
import wave
import zipfile
from pathlib import Path

PINNED_STAGE96_SHA = '24340c1d00f44311376729a2ba8d2813cf774997f0240c8790a7ad6cfa4e0274'
PINNED_DLL_SHA = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
ZIP_FILES = {'clo/cloFile.clo', 'logs/tone_import.log',
             'wavs/nam_input_wav.wav', 'wavs/outputFile.wav'}
ZIP_DIRS = {'clo/', 'logs/', 'wavs/'}
TAR_FILES = {'frida_capture/config.json', 'frida_capture/manifest.json',
             'frida_capture/events.jsonl', 'frida_capture/HANDOFF.md'}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def crc16_modbus(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return crc & 0xFFFF


def inspect_clo(data):
    if len(data) != 8840 or data[:4] != b'VTSI':
        raise ValueError('CLO length or VTSI magic mismatch')
    if (struct.unpack_from('<I', data, 4)[0] != 8840
            or struct.unpack_from('<I', data, 20)[0] != 8704
            or tuple(struct.unpack_from('<III', data, 124)) != (128, 128, 2048)):
        raise ValueError('CLO declared sizes or FIR layout mismatch')
    stored_be = struct.unpack_from('>H', data, 8)[0]
    calculated = crc16_modbus(data[12:])
    if stored_be != calculated:
        raise ValueError('CLO CRC16-Modbus mismatch')
    for offset, fmt, n in ((64, '<d', 5), (104, '<f', 4),
                           (136, '<f', 128), (648, '<f', 2048)):
        width = struct.calcsize(fmt)
        for i in range(n):
            if not math.isfinite(struct.unpack_from(fmt, data, offset + i*width)[0]):
                raise ValueError('non-finite CLO coefficient')

    # Same structural transformation as src/void_clone_protocol.js,
    # but an independent Python implementation. Does not upload to device.
    low = bytearray(data[:2696])
    struct.pack_into('<I', low, 4, 2696)
    struct.pack_into('<I', low, 20, 2560)
    struct.pack_into('<I', low, 132, 512)
    struct.pack_into('>H', low, 8, crc16_modbus(low[12:]))
    return {'size': len(data), 'sha256': sha256(data), 'magic': 'VTSI',
            'header_size': struct.unpack_from('<I', data, 4)[0],
            'body_bytes': 8704, 'fir_taps': 2048,
            'crc_stored_be': stored_be, 'crc_calculated': calculated,
            'header_crc_raw_as_le': struct.unpack_from('<H', data, 8)[0],
            'finite_coefficients': True, 'low_model_bytes': len(low),
            'low_model_sha256': sha256(low),
            'low_model_crc16_be': struct.unpack_from('>H', low, 8)[0]}


def inspect_wav(data, rate):
    with wave.open(io.BytesIO(data), 'rb') as wav:
        channels, width = wav.getnchannels(), wav.getsampwidth()
        samplerate, frames = wav.getframerate(), wav.getnframes()
        if (wav.getcomptype() != 'NONE' or channels != 2 or width != 2
                or samplerate != rate or frames != 70 * rate):
            raise ValueError('unexpected WAV PCM/rate/channel/duration')
        pcm = wav.readframes(frames)
    if len(pcm) != frames * 4 or not any(pcm):
        raise ValueError('truncated or entirely silent WAV')
    return {'sha256': sha256(data), 'bytes': len(data),
            'rate_hz': rate, 'channels': 2, 'bits_per_sample': 16,
            'duration_s': frames / rate, 'frames': frames,
            'has_nonzero_sample_bytes': True}


def read_bundle(path):
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if (len(names) != 7 or set(names) != ZIP_FILES | ZIP_DIRS
                or len(names) != len(set(names))):
            raise ValueError('unexpected ZIP members')
        if sum(i.file_size for i in infos) > 26_100_000:
            raise ValueError('ZIP decompressed size exceeds cap')
        for item in infos:
            if item.flag_bits & 1 or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('encrypted or symlink ZIP entry')
            if item.is_dir() != (item.filename in ZIP_DIRS):
                raise ValueError('ZIP entry type mismatch')
        contents = {name: z.read(name) for name in ZIP_FILES}
        timestamps = {name: z.getinfo(name).date_time for name in ZIP_FILES}
    return contents, timestamps


def _log_time(line):
    m = re.match(r'^\[([0-9T:.\-]+)\]', line)
    return dt.datetime.fromisoformat(m.group(1)) if m else None


def inspect_log(data, prefix, clo):
    try:
        lines = data.decode('utf-8').splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError('invalid UTF-8 Manager log') from exc
    session = [line for line in lines if line.startswith('[' + prefix)]
    required = {
        'start': 'start import,',
        'native_result': 'native namConvertCloData returned 8840',
        'progress_100': 'process=3281, total=3281, percent=100',
        'native_progress_end': 'process=-1, total=-1, percent=100',
        'callback': 'native convert callback state=3',
        'conversion': 'convert finished, success=true, nativeDataSize=8840',
        'write': 'write clo file path=',
        'crc_log': 'calculatedCrc=',
        'crc_success': '[TcHelper.checkTcFile] check success',
        'low_model': 'low-model conversion success, resultLength=2696',
        'device_ack': 'received tcImportExport ack, status=0',
        'wait_success': 'wait importTC result=true',
    }
    found = {}
    positions = {}
    for label, token in required.items():
        matches = [(i, line) for i, line in enumerate(session) if token in line]
        if len(matches) != 1:
            raise ValueError('expected exactly one Manager event: ' + label)
        positions[label], found[label] = matches[0]
    if list(positions.values()) != sorted(positions.values()):
        raise ValueError('Manager event ordering invalid')
    if 'exists=true, size=8840' not in found['write']:
        raise ValueError('Manager CLO write size not confirmed')
    log_crc_raw = re.search(r'calculatedCrc=(\d+), fileCrc=(\d+)', found['crc_log'])
    if (not log_crc_raw or int(log_crc_raw.group(1)) != int(log_crc_raw.group(2))
            or int(log_crc_raw.group(1)) != clo['header_crc_raw_as_le']):
        raise ValueError('Manager CRC log does not match CLO raw CRC bytes')
    return {'evidence_flags': {key: True for key in required},
            'session_prefix': prefix,
            'native_start_local': _log_time(found['native_result']),
            'native_progress_end_local': _log_time(found['native_progress_end']),
            'manager_conversion_end_local': _log_time(found['conversion']),
            'device_ack_local': _log_time(found['device_ack']),
            'wait_success_local': _log_time(found['wait_success']),
            'reported_crc_raw_le': int(log_crc_raw.group(1))}


def read_frida(path):
    if sha256(Path(path).read_bytes()) != PINNED_STAGE96_SHA:
        raise ValueError('Stage96 archive is not the independently accepted original')
    with tarfile.open(path, 'r:gz') as tar:
        members = tar.getmembers()
        if len(members) != 4 or {m.name for m in members} != TAR_FILES:
            raise ValueError('Stage96 tar archive members changed')
        if any(not m.isfile() or m.size > 100_000 for m in members):
            raise ValueError('Stage96 tar member type/size invalid')
        manifest = json.loads(tar.extractfile('frida_capture/manifest.json').read())
        events = [json.loads(line) for line in tar.extractfile('frida_capture/events.jsonl').read().splitlines()]
    if (manifest.get('status') != 'CAPTURED_HOOKS_ONLY'
            or manifest.get('expected_sha256') != PINNED_DLL_SHA
            or manifest.get('completion_verified') is not False
            or not manifest.get('state', {}).get('runtime_verified')
            or manifest.get('state', {}).get('hook_errors') != 0):
        raise ValueError('Stage96 native capture gates mismatched')
    enter = [e for e in events if e.get('kind') == 'trace_enter' and e.get('site') == 'wrapper_10e70']
    if len(enter) != 1:
        raise ValueError('Stage96 wrapper invocation missing/ambiguous')
    leaves = [e for e in events if e.get('kind') == 'trace_leave' and e.get('id') == enter[0]['id']]
    if len(leaves) != 1 or leaves[0].get('thread') != enter[0].get('thread'):
        raise ValueError('Stage96 wrapper leave unmatched')
    return {'start_ms': enter[0]['timestamp_ms'], 'end_ms': leaves[0]['timestamp_ms'],
            'accepted_archive_sha256': PINNED_STAGE96_SHA}


def _public_time(t):
    return t.isoformat(timespec='milliseconds') if t else None


def audit(bundle, frida, session_prefix='2026-10-19T02:53:'):
    raw = Path(bundle).read_bytes()
    contents, timestamps = read_bundle(bundle)
    clo = inspect_clo(contents['clo/cloFile.clo'])
    wav_in = inspect_wav(contents['wavs/nam_input_wav.wav'], 44100)
    wav_out = inspect_wav(contents['wavs/outputFile.wav'], 48000)
    log = inspect_log(contents['logs/tone_import.log'], session_prefix, clo)
    native = read_frida(frida)
    bangkok = dt.timezone(dt.timedelta(hours=7))
    start = dt.datetime.fromtimestamp(native['start_ms']/1000, tz=bangkok).replace(tzinfo=None)
    end = dt.datetime.fromtimestamp(native['end_ms']/1000, tz=bangkok).replace(tzinfo=None)
    start_gap = abs((start-log['native_start_local']).total_seconds()*1000)
    end_gap = abs((end-log['native_progress_end_local']).total_seconds()*1000)
    if start_gap > 1000 or end_gap > 1000:
        raise ValueError('Stage96 Frida and Manager temporal anchors mismatch')
    if not all(tuple(timestamps[p][:5]) == (2026,10,19,2,53) for p in
               ('clo/cloFile.clo','wavs/nam_input_wav.wav','wavs/outputFile.wav')):
        raise ValueError('CLO/WAV ZIP member time is inconsistent with conversion')
    if not log['wait_success_local'] > log['device_ack_local'] > end:
        raise ValueError('Manager ACK chronology invalid')
    return {
        'stage': 97,
        'status': 'NEW_RUN_CLO_FORMAT_CRC_CONVERSION_AND_DEVICE_ACK_LOG_CORRELATED',
        'evidence_type': 'OPERATOR_CLO_BUNDLE_PLUS_INDEPENDENT_STAGE96_NATIVE_FRIDA_TIMING',
        'archive_sha256': sha256(raw),
        'stage96_capture_sha256': native['accepted_archive_sha256'],
        'clo': clo,
        'wav_input': wav_in,
        'wav_output': wav_out,
        'log_sha256': sha256(contents['logs/tone_import.log']),
        'manager_log_gates': log['evidence_flags'],
        'manager_crc_raw_little_endian_interpretation': log['reported_crc_raw_le'],
        'frida_wrapper_start_bangkok': _public_time(start),
        'frida_wrapper_end_bangkok': _public_time(end),
        'manager_start_gap_ms': round(start_gap,3),
        'manager_end_gap_ms': round(end_gap,3),
        'manager_conversion_end_bangkok': _public_time(log['manager_conversion_end_local']),
        'manager_device_ack_bangkok': _public_time(log['device_ack_local']),
        'hardware_readback_verified': False,
        'clo_device_payload_byte_identity_verified': False,
        'nam_file_contents_verified': False,
        'numerical_vendor_parity_verified': False,
        'time_zone_assumption': 'Windows Manager log wall time is Asia/Bangkok (UTC+07:00)',
        'limits': 'Manager log reports successful conversion/ACK; raw device state not independently read. Artifacts may be byte-identical to earlier conversions of the same NAM profile.'
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--frida', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--session-prefix', default='2026-10-19T02:53:')
    args = p.parse_args()
    report = audit(args.bundle, args.frida, args.session_prefix)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'stage': report['stage'], 'status': report['status'],
                      'clo_crc16_valid': True,
                      'manager_start_gap_ms': report['manager_start_gap_ms'],
                      'manager_end_gap_ms': report['manager_end_gap_ms'],
                      'hardware_readback_verified': False}))


if __name__ == '__main__':
    main()
