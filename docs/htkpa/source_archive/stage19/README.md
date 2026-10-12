# HTKPA Stage 19 — DLL source-first audio-path checkpoint

**Not a full NAM→CLO converter. A/B-from-real-WAV: NOT COMPUTED.**

What this package does:
- Verifies the SHA-256 of the original *local* Sonicake Manager `5868USB.dll`, then statically disassembles selected functions using `objdump`. It **never executes the DLL**.
- Recovers the complete 50-tap, float32 input FIR coefficient table **for each** 44.1 / 48 / 96 kHz native branch directly from the PE constant section.
- As a purely isolated mathematical check, convolves the *actual* 44.1-kHz user DI (identical in two user-captured session ZIPs) with the corresponding native 44.1-kHz 50-tap bank, then saves only numerical summaries in `evidence.json`.
- Demonstrates real input WAV provenance and maintains vendor output WAVs solely as untouched references. Does not read vendor FIR vectors during generation.
- Traces the downstream **two IIR + saturator + STFT** path but does not invent missing values.
- Corrects the Stage-10 misstatement: STFT hop = half-window in samples, not half a second.

To repeat locally (paths are examples; use your own original captures):

```bash
python stage19_source_first.py --dll /path/to/5868USB.dll --zip-2203 '/path/to/Sonicake Manager Files.zip' --zip-sc20 '/path/to/Sonicake Manager(1).zip' --out evidence-recheck.json
python -m unittest test_stage19.py -v
```

Requires Python 3, numpy, scipy, and `objdump` (plus matplotlib only to redraw the plot). The standalone tests use local original paths recorded in the project research environment; adjust them if you relocate inputs. The bundled report and evidence remain readable without the DLL.

No WAV/NAM/vendor CLO/DLL is packed in the release ZIP. **Do not use this partial mathematical FIR as a pedal asset.**
