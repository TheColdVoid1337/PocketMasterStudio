# HTKPA DLL Reverse Engineering — Stage 18

This ZIP is a **read-only, source-first research checkpoint**, not a NAM→CLO converter.

## What is new

- Identified original `0x1800BC6B0` as an **audio-preprocessing + spectral curve initialization** function, called before all selector stages, rather than a simple array initializer.
- Recovered **double Gaussian smoothing → parabolic positive floor → regularized ratio** at the end of `0x1800BC6B0`.
- Implemented the complete **ordinary finite-positive/monotone-domain algebraic** pipeline of `0x1800B7670`, with Mel grids, dB transformations, two Gaussian passes, and interpolations.
- Passed **59 exact DLL instruction checks, 12 constants, 49 synthetic math tests** and produced a separate 128/2048-point synthetic curve demo.

## Run verification

Requires Python 3, `numpy` and native GNU `objdump`. Supply **your own original** Windows Sonicake Manager DLL:

```bash
python stage18_source_first.py --dll /path/to/5868USB.dll --out evidence.json
python demo_stage18.py --out synthetic_demo.json
```

The checker requires original DLL SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, **never loads or executes** it, and does not write any CLO or device data. All sample data are artificial.

## What is not ready

- Native bit-exact `float32` equivalence or all interpolation edge cases.
- Audio preprocessing and cross-spectral arrays feeding the initializer from real WAV.
- Native-equivalent three-pass (`2→1→3`) fitting and vendor Pre/Post FIR coefficient parity.
- Conversion to a new hardware-ready CLO.

Read `RESEARCH_REPORT.md` for exact instruction addresses and the remaining data-flow blockers. Nothing in the production PocketMasterStudio converter was changed.
