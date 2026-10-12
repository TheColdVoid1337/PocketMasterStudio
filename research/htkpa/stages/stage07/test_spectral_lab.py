import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
import spectral_lab as m

class SpectralResearchTests(unittest.TestCase):
 def test_minimum_phase_positive_spectrum(self):
  freq=np.linspace(0,m.FS/2,2401)
  reference=np.array([1.,.25,.1])
  mag=np.abs(np.fft.rfft(reference,4800))
  h=m.minimum_phase_from_spectrum(freq,mag)
  self.assertGreater(np.dot(reference,h[:3])/(np.linalg.norm(reference)*np.linalg.norm(h[:3])),.99)
 def test_spectrum_fitting_known_system(self):
  from scipy import signal
  rng=np.random.default_rng(401)
  q=rng.standard_normal(70*m.FS).astype('f8')*.1
  htrue=np.array([.8,.3,.06])
  y=signal.lfilter(htrue,[1.],q)
  fitted=m.fit(q,y)
  self.assertGreater(float(np.dot(fitted[:3],htrue)/(np.linalg.norm(fitted)*np.linalg.norm(htrue))),.99)
  wave=signal.lfilter(fitted,[1.],q)
  lag=m.lag_train(wave,y)
  self.assertGreater(m.metrics(wave,y,m.HOLDOUT,lag)['abs_correlation'],.99)
  with self.assertRaises(ValueError):m.spectral_cross(q,y[:100])
 def test_crc_container_without_sources(self):
  synthetic=bytearray(8840);synthetic[:4]=b'VTSI'
  import struct
  struct.pack_into('<I',synthetic,4,8840)
  struct.pack_into('<I',synthetic,132,2048)
  struct.pack_into('>H',synthetic,8,m.crc16(synthetic[12:]))
  with TemporaryDirectory() as d:
   p=Path(d)/'synthetic.clo';p.write_bytes(synthetic)
   self.assertEqual(len(m.read_clo(p)[0]),8840)
   m.save_candidate(synthetic,np.ones(512)*.0001,Path(d)/'new.clo')
   self.assertEqual((Path(d)/'new.clo').stat().st_size,8840)
 def test_train_holdout_disjoint(self):
  for a,b in m.TRAIN:
   for c,d in m.HOLDOUT:self.assertTrue(b<=c or d<=a)
 def test_minphase_no_vendor_data(self):
  import inspect
  src=inspect.getsource(m.fit)
  self.assertNotIn('vendor',src.lower())
  self.assertNotIn('official',src.lower())
if __name__=='__main__':unittest.main()
