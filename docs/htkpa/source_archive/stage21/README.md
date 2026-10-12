# HTKPA Stage 21 — 4-parameter Saturator Fitter

This read-only reverse-engineering package reconstructs the complete ordinary-domain mathematics of `5868USB.dll` function `0x1800BDBE0`. The **upstream signal preprocessing** that supplies its two input buffers is not yet reproduced, so **the real Sonicake four gains for either Marshall have not been computed**. The separate original vendor references are used only for read-only validation.

## Contents

- `stage21_saturator_source.py`: source-pinned disassembly verifier; independent B-block signed envelope extraction, native 4B-float paired-array permutation, two half-maximum linear regressions, nine-candidate positive and negative `float32` error searches, standalone tests.
- `native_repack_trace.py`: separate symbolic memory-address interpreter for 7 array lengths, proving permutation from original DLL store addresses (handles vectorized and scalar-tail paths).
- `audit_official_reference.py`: **read-only oracle audit** (uses original ZIPs only if already present locally, does not fit from them or redistribute media).
- `evidence.json`: verification run, native grid, pass/fail scope.
- `reference_audit.json`: hashes, audio metadata, and **read-only** official parameter values.
- `synthetic_full_fit.json`: 60-second entirely artificial paired audio regression result.
- `RESEARCH_REPORT.md`: detailed native addresses, reconstructed equations, validation boundaries and next steps.

## Commands

```bash
python stage21_saturator_source.py --dll /path/to/original/5868USB.dll --output evidence.json
python audit_official_reference.py --root /path/to/local/user-captures --output reference_audit.json
```

A missing or SHA-mismatched DLL is refused. No proprietary binary is loaded or executed. No audio files or CLO are written. All code is independent research code.

**Strict gate:** native preprocessing from captured 44.1/48-kHz WAV → four fitted gains **NOT_COMPUTED**. No production JavaScript changes, device communication or candidate CLO.
