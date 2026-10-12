# HTKPA Stage 12 — source-first Pre-FIR spectral tracing

Only original Python code, a read-only DLL instruction verifier, synthetic unit tests, and a technical report. The user's proprietary 5868USB.dll must remain outside this package.

## Run

```bash
python -m pip install numpy
python verify_stage12.py --dll "/path/to/5868USB.dll" --output evidence.json
```

Requirements: Python 3, NumPy, GNU binutils `objdump` (PE-x86-64 support). The tool **does not execute/load the DLL**. Results are pinned to a specific DLL SHA-256. It emits no `.clo` and does not connect to any device.

**Stage result:** Confirmed log-spectrum guard, inter-bucket interpolation call, one-sided mirror, complex exponential, conjugate folding, and real inverse-transform formula. **Not yet reconstructed:** exact whole spectral transform pipeline, pre-FIR fitting input, vendor-exact taps, Post-FIR writer.
