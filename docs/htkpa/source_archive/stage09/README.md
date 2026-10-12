# HTKPA Stage 9 — Source-first Mel-grid interpolation proof

This research package contains an independent Python reconstruction of a **limited mathematical component** of Sonicake HTKPA and a read-only verification script for **your own copy** of `5868USB.dll`. It intentionally excludes the vendor DLL, original NAM, audio, and CLO captures.

```bash
python source_first_stage9.py '/path/to/5868USB.dll' --out evidence.json
```

The verifier fails if the DLL SHA-256, any of 38 exact-address assembly predicates, or any of 9 pinned constants differ. It also runs seven independent synthetic tests. Expected result: `38 address pins, 9 constants, 7 synthetic mathematical tests passed`.

**Main result:** Sonicake constructs 512 Mel-spaced frequency queries from 80 to 10000 Hz, performs piecewise-linear interpolation of an unknown intermediate curve using `0x1800B5D00`, and scores the interpolated values as average `abs(log(v + 2^-23))`.

**Still unknown:** where the two intermediate source arrays originate mathematically and the full vendor FIR generation. No new experimental CLO, no production JS changes, and no DLL execution.
