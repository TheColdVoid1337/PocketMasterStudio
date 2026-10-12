# Sonicake HTKPA reverse engineering — Stage 10

Verified (source-first): `0x1800B82B0` calculates a windowed *cross-spectral transfer magnitude* `|S_AB|/(S_AA+2^-23)` and **linear-Hz** frequency knots, then `0x1800B5D00` interpolates onto the 512-point **Mel** frequency grid for the logarithmic score.

This **does not** derive Sonicake FIR coefficients. No heuristics, vendor executable redistribution, new `.clo`, device writes or changes to the production JS converter.

Use a local copy of the exact Windows `5868USB.dll`, plus Python 3 and GNU `objdump`:

```bash
python verify_stage10.py --dll /path/to/5868USB.dll --json evidence.json
```

Expected `SUCCESS 51 instruction pins 5 constants 8 tests` with the original SHA-256. `evidence.json` in this ZIP is a retained read-only verification result; the DLL itself is **not provided**. Read `RESEARCH_REPORT.md` for the exact assembly-address proof, correct interpretations and remaining limitations.
