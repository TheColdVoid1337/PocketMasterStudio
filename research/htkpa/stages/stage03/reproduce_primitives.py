#!/usr/bin/env python3
"""Standalone reference equations inferred from short, proven DLL assembly fragments.

This module is not a complete HTKPA reimplementation and does not load DLLs.
The following formulas reproduce *local* DSP primitives, not their full call graph.
"""
import math

HAMMING_A = 0.54
HAMMING_B = 0.46
ITER_EXPONENT_MULTIPLIER = 0.9
ITER_MIN = 0.2
ITER_MAX = 5.0
SPECTRAL_NUMERATOR_SCALE = 1_000_000.0
SPECTRAL_DENOMINATOR_FLOOR = 2**-23
SPECTRAL_MIN = 0.1
SPECTRAL_MAX = 10.0
LOG_EPSILON = 2**-23


def hamming(n):
    """One exact scalar form of the cosine window in 0x1800b82b0; n>1."""
    if n < 2:
        raise ValueError('window length must be >= 2')
    return [HAMMING_A - HAMMING_B * math.cos(2*math.pi*i/(n-1)) for i in range(n)]


def clamp_pow(base, exponent):
    """Bounded power primitive from 0x1800bb460..0x1800bb492 (positive inputs)."""
    if base <= 0:
        raise ValueError('research-only primitive requires positive base')
    return max(ITER_MIN, min(ITER_MAX, math.pow(base,exponent)))


def amplitude_ratio(numerator, denominator):
    """Magnitude-only scalar ratio in 0x1800bac70..0x1800bad2e.

    The choice of which full-pipeline buffer is the numerator vs denominator
    remains under analysis; this function only reproduces the local arithmetic.
    """
    if numerator < 0 or denominator < 0:
        raise ValueError('spectral magnitudes must be nonnegative')
    r=(SPECTRAL_NUMERATOR_SCALE*numerator) / (SPECTRAL_NUMERATOR_SCALE*denominator+SPECTRAL_DENOMINATOR_FLOOR)
    return max(SPECTRAL_MIN, min(SPECTRAL_MAX, r))


def log_score_512(values):
    """Partial 512-entry metric in 0x1800bc410..0x1800bc440.

    It is NOT proven which upstream spectral array constitutes `values`.
    """
    if len(values) != 512 or any(v < 0 for v in values):
        raise ValueError('expected 512 nonnegative values')
    return sum(abs(math.log(v + LOG_EPSILON)) for v in values) / 512


def successive_exponents(initial, steps):
    return [initial*ITER_EXPONENT_MULTIPLIER**k for k in range(steps)]

if __name__ == '__main__':
    for name,v in [('Hamming 8', hamming(8)), ('Power exponent steps',successive_exponents(1,5)),
                    ('Spectral ratio example', amplitude_ratio(0.4,0.8)),
                    ('Log score of unity vector',log_score_512([1.0]*512))]:
        print(name,':',v)
