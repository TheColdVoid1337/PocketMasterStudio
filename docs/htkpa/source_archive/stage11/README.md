# HTKPA DLL Reverse Engineering — Stage 11

Research-only, source-first static analysis of the user's Windows Sonicake `5868USB.dll`. The binary, vendor captures and original user NAM models are intentionally **not** bundled.

## Contents

- `verify_stage11.py`: read-only SHA-pinned disassembler verifier; original clean-room tests of the isolated caller stack rebase, mirror and DC/energy normalization math.
- `evidence.json`: successful machine-instruction checks and numeric comparison, with no raw capture or DLL data.
- `RESEARCH_REPORT.md`: confirmed Pre-FIR candidate pointer chain and mathematical boundaries.

## Run locally with the original DLL

```bash
python verify_stage11.py \
  --dll 'path/to/Sonicake Manager/assets/5868USB.dll' \
  --out evidence_local.json
```

Optional numerical comparisons: `--official-2203 official2203.clo --official-sc20 officialSC20.clo`. These are read-only inputs.

**Status:** isolated assembly-backed operations recovered. Full `0x1800B7670`, `0x1800B72E0` and `0x1800B47F0` math, and exact WAV→official-FIR reproduction, are **not** finished. No experimental CLO released and no device action.
