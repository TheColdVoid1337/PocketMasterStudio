# Sonicake HTKPA Stage 14 — source-first static investigation

This release contains clean-room notes and a **read-only** verifier of exact assembly pins for the **user-supplied** Windows Sonicake Manager `5868USB.dll`.

## Run locally

```bash
python verify_stage14.py --dll '/path/to/5868USB.dll' --output evidence.json
```

Requires Python 3.10+ and GNU `objdump`; no binary analysis modules, audio or network needed. The DLL must have SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.

**Contains no commercial DLL, captured NAM or vendor WAV/CLO.** Never executes the DLL, never uploads or writes to a physical device, and never generates new CLO. Code is a pinned instruction checker and scalar-primitives tester, not an independently functioning HTKPA converter.

## What changed relative to Stage 13

- Found **the Post-FIR output writer**: `0x1800BC35C` invokes **the same `0x1800B68F0`** as used for Pre-FIR, with `context+0x20ED8` and the Post-FIR pointer.
- Traced the **initial unity-seeded working correction buffers** and their early modifications.
- Recovered **Mel-domain, dB-domain, two-Gaussian resampling** inside `0x1800B7670` with exact constants and call order.
- Identified the **separate final Post-FIR stage** which remains to be fully reconstructed.

Acceptance remains open: no official FIR reproduced numerically from NAM/WAV. See `RESEARCH_REPORT.md`.
