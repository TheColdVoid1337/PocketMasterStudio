#!/usr/bin/env python3
"""Optional research CLO: phase-only Post-FIR experiment. Never touches device.

NOT proof of Sonicake bit-level reconstruction. Only first 512 transmitted
Post-FIR taps are changed, preserving their magnitude response approximately.
"""
from __future__ import annotations
import argparse,hashlib,struct
from pathlib import Path
import numpy as np
from scipy import fft
from minimum_phase import minimum_phase_from_magnitude

def crc16(data):
    x=65535
    for b in data:
        x ^= b
        for _ in range(8): x=(x>>1)^(0xA001 if x&1 else 0)
    return x

def main():
 p=argparse.ArgumentParser();p.add_argument('--baseline',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
 a=p.parse_args();raw=bytearray(a.baseline.read_bytes())
 assert len(raw)==8840 and raw[:4]==b'VTSI'
 assert crc16(raw[12:])==struct.unpack_from('>H',raw,8)[0]
 old=np.frombuffer(raw,dtype='<f4',count=512,offset=648).astype(float).copy()
 newer=minimum_phase_from_magnitude(old,nfft=16384).astype('<f4')
 mag0=np.abs(fft.rfft(old,32768));mag1=np.abs(fft.rfft(newer,32768))
 e=20*np.log10(np.maximum(mag0,1e-9)/np.maximum(mag1,1e-9))
 # Maximum deviation can be high at extremely deep notches even though perceptually insignificant.
 assert np.mean(abs(e)) < .015, f'Magnitude response changed too much: {np.mean(abs(e))}'
 raw[648:648+2048]=newer.tobytes()
 struct.pack_into('>H',raw,8,crc16(raw[12:]))
 assert crc16(raw[12:])==struct.unpack_from('>H',raw,8)[0]
 b=a.baseline.read_bytes();z=bytes(raw)
 assert b[:8]==z[:8] and b[10:648]==z[10:648] and b[2696:]==z[2696:]
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(z)
 print({'source_sha256':hashlib.sha256(b).hexdigest(),'candidate_sha256':hashlib.sha256(z).hexdigest(), 'bytes':len(z),'mean_magnitude_difference_db':float(np.mean(abs(e))), 'baseline_rms_taps':float(np.linalg.norm(old)),'candidate_rms_taps':float(np.linalg.norm(newer)),'crc':'valid', 'transmitted_taps_changed':512,'non_post_data_changed':'CRC16 only'})
if __name__=='__main__':main()
