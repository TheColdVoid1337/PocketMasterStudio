# Sonicake HTKPA reverse engineering — Stage 13

**Read-only, source-first, clean-room mathematical analysis.** Nothing is executed from Sonicake; no NAM, audio, CLO or commercial binary is included.

## What Stage 13 adds

- Verified exact DFT directions and normalizations for `0x1800B4A50` and `0x1800B4F60`.
- Verified special parity handling and zeroing in `0x1800B6E30`.
- Composed a previously missing complete algebraic spectral-synthesis chain from an arbitrary finite, nonnegative *same-length* magnitude curve to a complex response, then generated one synthetic 128-tap Pre-FIR example using previously established DC/energy processing.
- 41 pinned instruction checks and 111 synthetic mathematical tests passed; two independent verification runs generated identical JSON.

**Not achieved:** reproducibility of DLL float32 output, actual optimizer-produced magnitude curves or exact vendor FIR coefficients from NAM/WAV. This is not a new sound-quality claim and is not a new device-ready CLO.

## Local verification

```bash
python verify_stage13.py --dll "/path/to/Sonicake Manager/assets/5868USB.dll" --out evidence.json
python make_example.py
```

Dependencies: Python 3 and NumPy; GNU `objdump` for static DLL verification. `matplotlib` optional for the synthetic plot. The DLL path must match the pinned SHA-256. No execution of DLL occurs.

See `RESEARCH_REPORT.md` for the source addresses, recovered equations and limitations.
