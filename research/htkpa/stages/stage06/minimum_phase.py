#!/usr/bin/env python3
"""Independent real-cepstrum minimum-phase projection (research, not HTKPA reimplementation).

Uses only the magnitude of a supplied FIR. Neither vendor DLL nor native binary
is invoked. An output similarity to a vendor FIR is evidence of minimum-phase
structure, NOT proof of the exact vendor algorithm or its interpolation details.
"""
from __future__ import annotations
import numpy as np
from scipy import fft


def minimum_phase_from_magnitude(taps, nfft=32768, floor_relative=1e-8):
    h = np.asarray(taps, dtype=np.float64)
    if h.ndim != 1 or h.size == 0 or nfft <= 2 * len(h):
        raise ValueError('Need nonempty 1-D FIR and nfft > 2*length')
    if nfft % 2: raise ValueError('Even FFT size required')
    H = fft.fft(h, nfft)
    amplitude = np.abs(H)
    maximum = float(amplitude.max())
    if maximum == 0: raise ValueError('Cannot project a zero filter')
    log_magnitude = np.log(np.maximum(amplitude, maximum*floor_relative))
    real_cepstrum = fft.ifft(log_magnitude).real
    min_cepstrum = np.zeros_like(real_cepstrum)
    min_cepstrum[0] = real_cepstrum[0]
    min_cepstrum[1:nfft//2] = 2 * real_cepstrum[1:nfft//2]
    min_cepstrum[nfft//2] = real_cepstrum[nfft//2]
    minimum_phase_spectrum = np.exp(fft.fft(min_cepstrum))
    reconstructed = fft.ifft(minimum_phase_spectrum).real
    return reconstructed[:h.size].copy()


def cosine(a,b):
    a=np.asarray(a,dtype=float); b=np.asarray(b,dtype=float)
    return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)))


def relative_error(a,b):
    a=np.asarray(a,dtype=float); b=np.asarray(b,dtype=float)
    return float(np.linalg.norm(a-b)/np.linalg.norm(a))
