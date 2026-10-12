# HTKPA Stage 15 — source-confirmed feedback and final Post-FIR correction

This package contains *independently authored* static verification, algebraic test helpers, and a technical report. It does **not** contain the proprietary Sonicake DLL, NAM, vendor audio/CLO, or device code.

## Usage

1. Have your legally obtained `5868USB.dll` available on your own computer (SHA256 is pinned by the verifier).
2. Install Python 3 with NumPy, and ensure GNU `objdump` is on PATH.
3. Run:

```bash
python verify_stage15.py --dll /path/to/5868USB.dll --out evidence_recomputed.json
```

Expected: 46 address/instruction checks, 8 binary constants, 13 synthetic mathematical tests. All read-only. The DLL is never executed. The evidence is deterministic for the same pinned binary and same toolchain.

## What is new

- Exact scaled/regularized quotient feeding the working Post-FIR frequency-curve conditioner.
- Final 256-tap correction synthesis, causal *truncated* convolution onto the current Post-FIR, DC subtraction, then energy gain alignment.

## Not yet accomplished

The complete native optimizer update equation and final vendor coefficient-level parity are not recovered. These scripts cannot generate a CLO, and no production source/device state was changed. See `RESEARCH_REPORT.md` for precise boundaries.
