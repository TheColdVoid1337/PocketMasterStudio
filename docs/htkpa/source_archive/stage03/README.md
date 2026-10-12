# HTKPA DLL Reverse Engineering — Stage 3

Static, read-only analysis of two internal functions in the user-supplied Windows Sonicake Manager DLL: `0x1800BB210` and `0x1800B9B70`.

- `RESEARCH_REPORT.md`: instructions, formulas, confidence limits and next targets.
- `verify_stage3.py`: SHA-pinned PE/assembly verifier (31 checks, 11 constants, imported math functions); accepts *only* the user-supplied DLL as an argument.
- `evidence.json`: exact lines extracted from the real DLL in the current research session.
- `reproduce_primitives.py`: independently written scalar demonstrations of local DSP formulas. **Not a converter.**
- `test_primitives.py`: 5 portable regression tests.

Run:

```bash
python verify_stage3.py '/path/to/5868USB.dll' --out evidence.json
python -m unittest -v test_primitives.py
```

There are no vendor DLLs or proprietary test WAV files in this ZIP. No hardware or production-converter action is performed.
