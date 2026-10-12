#!/usr/bin/env python3
"""Read-only conditional PCM normalization research (never calls the DLL)."""
import argparse,hashlib,re,struct,subprocess,wave
from pathlib import Path
import numpy as np
from stage23d_source_provenance import pe_at,DLL_SHA
PINS={
 0x1801422B9:'[r14+0x24],0x0',
 0x1801422D1:'call   0x1801417f0',
 0x180141804:'0x18024c4c4',
 0x180141869:'cvtdq2ps xmm1,xmm0',
 0x18014186C:'mulps  xmm1,xmm2',
 0x18014186F:'movups xmmword ptr [rcx],xmm1',
 0x1801418EB:'cvtdq2ps xmm0,xmm0',
 0x1801418EE:'mulss  xmm0,xmm3',
 0x18014194F:'cvtdq2ps xmm0,xmm0',
 0x180141952:'mulss  xmm0,xmm3',
}
def static_check(dll):
 d=dll.read_bytes();assert hashlib.sha256(d).hexdigest()==DLL_SHA
 a='\n'.join(subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={lo}',f'--stop-address={hi}',str(dll)],text=True) for lo,hi in [(0x1801417f0,0x18014197e),(0x1801421c0,0x1801422e0)])
 ins={int(m[1],16):' '.join(m[2].lower().split()) for s in a.splitlines() if (m:=re.match(r'\s*(180[0-9a-f]+):\s+(.+)',s))}
 for k,v in PINS.items():
  if ' '.join(v.lower().split()) not in ins.get(k,''):raise AssertionError((hex(k),v,ins.get(k)))
 c=struct.unpack('<f',pe_at(d,0x18024c4c4,4))[0]
 assert c==2**-31
 return c

def pcm16_capture_check(wav_path,scale):
 with wave.open(str(wav_path),'rb') as f:
  assert f.getsampwidth()==2 and f.getnchannels()==2
  raw=f.readframes(f.getnframes())
 raw16=np.frombuffer(raw,'<i2').reshape(-1,2)
 intermediate=raw16[:,0].astype(np.int32)<<16
 converted=intermediate.astype(np.float32)*np.float32(scale)
 expected=(raw16[:,0].astype(np.float32)*np.float32(2**-15))
 assert np.array_equal(converted,expected)
 return len(converted),float(np.max(np.abs(converted-expected)))

def main():
 p=argparse.ArgumentParser();p.add_argument('--dll',type=Path,required=True);p.add_argument('--2203-capture',type=Path);p.add_argument('--sc20-capture',type=Path);a=p.parse_args()
 scale=static_check(a.dll)
 print('PINNED',len(PINS),'conditional decoder instructions; scale',scale)
 for name,d in [('2203',a.__dict__['2203_capture']),('SC20',a.sc20_capture)]:
  if not d:continue
  for n in ('nam_input_wav.wav','outputFile.wav'):
   print(name,n,pcm16_capture_check(d/n,scale))
 print('Strict: native decoder branch reachability and gain parity remain OPEN')
if __name__=='__main__':main()
