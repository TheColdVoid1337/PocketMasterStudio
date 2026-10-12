# HTKPA DLL RE Stage23 — source checkpoint (not completed full stage)

**Status:** native file-loader pointer provenance, sample-rate equality gates, fixed-44100 call path and upstream sample-rate-converter dispatch are **source-confirmed**. Exact native resampler/output scaling, real native 4 sat gains and held-out parity are **OPEN**.

Included:
- `stage23_loader_source_trace.py` — SHA-pinned PE static address verifier, two archive metadata checks; no DLL execution.
- `stage23_readonly_diagnostic.py` — explicitly **NOT native parity**, demonstrates generic polyphase resampling + Stage21 fails heldout reference.
- `stage21_saturator_source.py` — unchanged prior Stage21 standalone source used for the diagnostic.
- `evidence.json`, `readonly_diagnostic.json`, `RESEARCH_REPORT.md`.

No proprietary DLL, user WAV/NAM, official CLO, or generated hardware CLO included. Nothing deployed to pedal/production.

Requirements: `objdump`, Python 3, `numpy` for Stage21; optional `scipy`, `soundfile` for diagnostic. Reproduction commands in `RESEARCH_REPORT.md`.
