# HTKPA Stage 23C — fractional resampler architecture (source checkpoint)

**Research-only / NOT production / NOT a native-parity converter.** This is a continued Stage 23 investigation of `5868USB.dll`. Static PE disassembly and byte reading only; the proprietary DLL is **never loaded or executed**. No hardware, vendor CLO generation or production JS changes.

## What is included

- `stage23_polyphase_source.py` — independently verifies 79 exact native instruction pins, 14 original vtable function pointers, PE constant 673.0, and 10 synthetic arithmetic checks. Includes a **capacity-only** model for one FIR stage plus interpolation stage, and a synthetic Bessel/Kaiser window analogue that is **not native numerical parity**.
- `pe_bytes.py` — minimal self-contained PE byte mapper, no third-party PE library.
- `evidence.json`, `evidence_repeat.json` — two byte-identical verifier runs.
- `stage21_reverified.json`, `stage22_reverified.json` — repeat evidence using their earlier source-verifier scripts (scripts available in Stage21/22 releases).
- `RESEARCH_REPORT.md` — address-level evidence and open questions.

**NOT included:** original DLL, NAM/WAV captures, official or candidate CLO, proprietary filter coefficients. Required to independently reproduce: Windows x64 DLL with exact SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa` supplied by its owner.

## Reproduce

```bash
python -m pip install scipy
python stage23_polyphase_source.py --dll '/path/to/5868USB.dll' --out evidence_new.json
sha256sum evidence_new.json evidence.json
```

Requires Python 3.10+, `objdump`, SciPy (synthetic math checks). No DLL invocation.

## Gate

**Real, independently calculated Marshall four saturation gains: NOT_COMPUTED.** The exact native FIR kernel, runtime interpolation lookup table, audio sample scaling and buffer preparation remain open. Do not use `capacity_contract` to render WAV or infer sample-accurate native output.
