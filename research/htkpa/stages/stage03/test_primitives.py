import math
import unittest
from reproduce_primitives import *

class MathPrimitiveTests(unittest.TestCase):
 def test_hamming_symmetry_edges_and_center(self):
  x=hamming(129)
  self.assertAlmostEqual(x[0],0.08,places=12)
  self.assertAlmostEqual(x[-1],0.08,places=12)
  self.assertAlmostEqual(x[64],1.,places=12)
  self.assertLess(max(abs(x[i]-x[-1-i]) for i in range(len(x))),1e-12)
 def test_ratio_identity_clip(self):
  self.assertAlmostEqual(amplitude_ratio(0.5,1.),0.5,places=7)
  self.assertEqual(amplitude_ratio(100.,.1),10.)
  self.assertEqual(amplitude_ratio(.0001,1.),.1)
 def test_pow_bounds_decay(self):
  self.assertEqual(clamp_pow(100.,1.),5.)
  self.assertEqual(clamp_pow(0.001,1.),.2)
  self.assertEqual(successive_exponents(1.,4),[1.,.9,.81,.7290000000000001])
 def test_log_score(self):
  self.assertAlmostEqual(log_score_512([1.]*512),math.log(1+2**-23),places=10)
  self.assertGreater(log_score_512([.5]*512),0.69)
 def test_invalid_domain(self):
  with self.assertRaises(ValueError): hamming(1)
  with self.assertRaises(ValueError): amplitude_ratio(-1,2)
  with self.assertRaises(ValueError): log_score_512([0]*511)
  with self.assertRaises(ValueError): clamp_pow(-3,0.5)

if __name__=='__main__': unittest.main(verbosity=2)
