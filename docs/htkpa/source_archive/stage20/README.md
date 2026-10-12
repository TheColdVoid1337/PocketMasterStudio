# Sonicake HTKPA Stage 20 — Native IIR coefficient constructor

Read-only Python research: the original DLL is accessed as PE bytes and disassembled with `objdump`, **never loaded or executed**. No audio, commercial DLL, official CLO or NAM is redistributed. No device operations.

Run against your original SHA-pinned Sonicake Manager DLL:

```bash
python stage20_iir_source.py --dll /path/to/5868USB.dll --out evidence.json
HTKPA_DLL_PATH=/path/to/5868USB.dll python test_stage20.py
```

Python dependencies: NumPy, SciPy (SciPy is used only to cross-check the independent IIR math). `stage20_iir_source.py` models 152 verified scalar SSE operations and outputs 10+5 filter coefficient stores. `test_stage20.py` checks 106 algebraic, source-address and mode-selection facts. `RESEARCH_REPORT.md` gives addresses and the outstanding blockers.

This is **not** a full NAM→CLO conversion: reference-WAV initial A/B = `NOT_COMPUTED`; official FIR coefficient parity = `NOT_TESTED`.
