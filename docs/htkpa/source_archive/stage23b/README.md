# Stage 23B — Source-pinned native export branch/resampler checkpoint

This is an independently reproducible, **static-only read** of the user's original Sonicake `5868USB.dll`. It does not load/execute the vendor DLL, generate device CLO, or modify production. The code is intentionally **not** a standalone resampler and makes no native gain-parity claim.

## Run

Requires Python 3, NumPy (for the 10 scalar synthetic tests), GNU `objdump`, the original DLL with pinned SHA256.

```bash
python stage23_resampler_branch_source.py \
  --dll '/path/to/5868USB.dll' \
  --out evidence.json
```

Expected: `PASS 125 native code pins, 7 PE constants, 10 synthetic tests. Real native gains NOT_COMPUTED`.

The script also directly verifies the original DLL's worker vtable pointers. Its JSON evidence output is deterministic for this pinned DLL and these script bytes. See `RESEARCH_REPORT.md` for control flow, exact address observations and the remaining strict gates. It intentionally excludes the original DLL, original WAV, NAM, and vendor CLO. `stage21_check.json` and `stage22_check.json` were produced by their original checks on the original DLL but the implementation files are not redistributed here to avoid confusing this incomplete continuation with a new fitter.
