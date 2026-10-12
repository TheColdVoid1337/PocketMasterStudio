# Sonicake HTKPA DLL — Stage 8 (source-first)

**What's new:** exact source/output probe-region dispatch, 2→1→3 selector order, 3/2/5 iteration schedule, and adaptive score/rollback decision verified directly from the supplied Windows DLL. No hypothesis-based filter fitter was written.

Read `RESEARCH_REPORT.md` for the full trace and limitations. Evidence is stored in `evidence.json` (instruction addresses and locally authored interpretations; no proprietary code or input captures).

## Verify on the original DLL

```bash
python verify_stage8.py "/path/to/Sonicake Manager/assets/5868USB.dll" --out evidence_checked.json
```

Requires Python 3 and GNU `objdump`. Pins exact DLL SHA-256; cannot silently validate a different vendor version. Never executes the DLL, never modifies the device, and does not generate CLO files.

**Results:** 70 exact-instruction matches, pinned float/double/integer constants and deterministic three-pass schedule. The main unsolved block remains the per-iteration state-buffer transformation into Pre/Post FIRs.
