# Stage 23 — static source gate (preflight, **not a completed DLL reverse-engineering stage**)

The user handoff identifies `5868USB.dll` SHA-256
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.

This package does **not** bundle, execute, load, or redistribute the DLL, NAMs, WAVs, or
vendor CLOs. It does **not** calculate the four real gains or prove native sample rate,
scale, resampling, zero padding, or reference alignment.

## Run locally with the previously supplied ZIP files

```bash
python3 stage23_source_gate.py \
  --installer 'Sonicake Manager.zip' \
  --capture-2203 'Sonicake Manager Files.zip' \
  --capture-sc20 'Sonicake Manager(1).zip' \
  --nam-2203 'JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'Marshall JCM 800 SC20 Full Rig.nam' \
  --out stage23_evidence
python3 -m unittest -v test_stage23_source_gate.py
```

The tool will:
1. Strictly hash-check the pinned vendor DLL (wrong builds fail closed).
2. Validate ZIP CRC and verify matching official capture SHA when supplied.
3. Record PCM WAV **container** sample rates / channel identity without conflating them with `native Fs`.
4. Statically run `objdump` over named import/export/allocator/caller ranges and save machine-instruction listings and call/field index.
5. Keep all extracted vendor data under `stage23_evidence/_private_DO_NOT_COMMIT/`.
6. Write `stage23_evidence/gate.json` where parity and dataflow are explicitly **NOT_PROVEN**.

This tool is **evidence acquisition, not automatic symbolic dataflow or the Stage-21 fitter**.
A human or independently verified symbolic executor must trace the producer/consumer graph:

`namConvertCloData / appNamConvertCloData` → PCM/resampler → `0x1800BF890 / 0x1800BFCA0`
→ `context+0x243E0/+0x243E8` → mean/one-based OLS detrend of reference → 600-sample
onset at 6 s → 23–28 s paired buffers → `0x1800BDBE0`.

Only after that may the already-published Stage-21 fitter be invoked on native-buffer-equivalent
arrays. The four official CLO gains must remain **read-only held-out scores**. Stage 22 proves
`0x1800BEDE4` fit occurs **before** later IIR helper call `0x1800BEE25`.

**Do not commit `stage23_evidence/`, which contains licensed vendor binary/media.**

## Provenance in this chat

The current session could read uploaded handoff and GitHub Stage 21/22 text but
could not materialize prior user ZIPs from the Project Library. Consequently the
source tool and synthetic tests can be locally exercised, but native disassembly
and true four-gain parity could NOT be performed in this session. Do not report
Stage 23 as complete.
