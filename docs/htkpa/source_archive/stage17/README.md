# HTKPA Stage 17 — Static Native Trace and Full-Iteration Gate

Read-only DLL-first Sonicake Manager HTKPA reverse engineering. **No full converter here.** The important Stage-16 pointer correction and the exact positive-domain `0x1800B6220` helper are source-checked; complete one-iteration fitting remains blocked by native curve conditioner / upstream initialization.

## Run native-instruction proof

```bash
python stage17_source_first.py --dll "/path/to/Sonicake Manager/assets/5868USB.dll" --out evidence.json
```

Only `objdump` is invoked against the DLL. The binary is NEVER executed. The script checks the pinned file SHA-256, 64 instruction addresses, five constants, and 23 synthetic tests.

## Run official-parity measurement only AFTER independent candidate calculation

```bash
python vendor_parity_gate.py --official-2203 ".../2203/cloFile.clo" --official-sc20 ".../SC20/cloFile.clo" --out vendor_report.json
```

With no independent candidate, the result deliberately says `NOT_TESTED`. When an actual independent converter produces two separate CLOs from NAM+probe, supply `--candidate-2203` and `--candidate-sc20`. This read-only gate will compare exact 128- and 2048-tap float32 arrays; it never optimizes against vendor filters.

## Contents

- `stage17_source_first.py` — pinned disassembly verifier and precise isolated positive-domain helper.
- `vendor_parity_gate.py` — post-hoc two-model vendor comparison gate, all claims source-labeled.
- `RESEARCH_REPORT.md` — address-backed findings, Stage-16 erratum and remaining blockers.
- `evidence.json` — reproducible static-machine-instruction and synthetic-test evidence.
- `vendor_reference_baseline.json` — **only statistical aggregates and hashes** for two official CLOs; neither original CLO nor coefficients included.

**No hardware operation. No firmware or production converter changes. No proprietary binaries/audio/CLOs included.**
