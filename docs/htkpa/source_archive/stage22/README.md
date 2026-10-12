# HTKPA Stage 22 — input pointers, detrend and timing before saturation

Source-first static disassembly, read-only. Confirms that **saturator fitting runs before the 50-tap/IIR audio filter**, on the **23–28-second** input/reference pair with **0…600 sample** reference alignment after mean/linear-trend subtraction.

## Files

- `stage22_pre_fit_trace.py` — checks pinned DLL bytes/instructions and synthetic pointer/detrend/onset cases. `--root` adds read-only WAV timing diagnostics; does **not** compute or output native saturation coefficients.
- `evidence.json` — one reproducible verification run.
- `RESEARCH_REPORT.md` — all call addresses and exact limitations.
- `stage21_saturator_source.py` — unchanged previous-stage math module, **for reference only**; it needs actual native input arrays before vendor use.

## Usage

```bash
python stage22_pre_fit_trace.py --dll /path/to/5868USB.dll --out evidence.json
python stage22_pre_fit_trace.py --dll /path/to/5868USB.dll --root /folder/with/user-captured-zips --out evidence_with_wav.json
```

Both modes only **read** user files. DLL is statically checked, **never loaded or executed**. The ZIP intentionally does not include the original Sonicake DLL, captured audio, NAMs, or vendor CLOs.

**Status:** Native gain parity for both 2203 and SC20 **NOT_COMPUTED**; no new CLO, no hardware or production changes.
