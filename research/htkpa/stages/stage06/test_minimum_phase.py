import unittest
import numpy as np
from scipy import fft
from minimum_phase import minimum_phase_from_magnitude, cosine

class MinimumPhaseTests(unittest.TestCase):
 def test_known_causal_minimum_phase(self):
  a=np.array([1.0,-0.4,-0.16,0.07],dtype=float)
  m=minimum_phase_from_magnitude(a)
  self.assertGreater(cosine(a,m),0.9999)
 def test_pure_delay_removed(self):
  a=np.zeros(32);a[7]=1.
  m=minimum_phase_from_magnitude(a)
  self.assertGreater(m[0],0.99999)
  self.assertLess(np.linalg.norm(m[1:]),1e-7)
 def test_magnitude_preserved(self):
  a=np.r_[np.zeros(8), [1.0,-0.35,0.15],np.zeros(30)]
  m=minimum_phase_from_magnitude(a)
  H=np.abs(fft.rfft(a,32768)); M=np.abs(fft.rfft(m,32768))
  self.assertLess(np.mean(np.abs(20*np.log10(np.maximum(H,1e-10)/np.maximum(M,1e-10)))),0.01)
 def test_raises_for_zero_and_non1d(self):
  with self.assertRaises(ValueError): minimum_phase_from_magnitude([0.,0.])
  with self.assertRaises(ValueError): minimum_phase_from_magnitude(np.ones((3,2)))
 def test_fft_grid_stability(self):
  a=np.array([1.,-.25,.1,.03]); out=[]
  for nfft in [8192,16384,32768,65536]: out.append(minimum_phase_from_magnitude(a,nfft=nfft))
  for q in out[1:]:self.assertLess(np.linalg.norm(q-out[0]),1e-5)

if __name__=='__main__':unittest.main()
