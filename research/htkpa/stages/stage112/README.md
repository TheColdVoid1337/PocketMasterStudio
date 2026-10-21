# Stage112 — signed PCM16 residual versus candidate output waveform morphology

**Status: `STAGE112_OFFLINE_WAVEFORM_MORPHOLOGY_COMPLETED`**, real original-data cloud run (2026-10-21 Bangkok). **17/17 Stage112 tests PASS; 42/42 combined Stage110–112 synthetic tests PASS.** Full results: [OPERATOR_RESULT_20261021.md](OPERATOR_RESULT_20261021.md). Machine-readable aggregate evidence: [evidence.json](evidence.json).

Stage112 reads the original Stage97 ZIP and user-authorized private Stage102–109 ZIP. The public Stage110 and Stage111 analyzers are imported and Stage111 is replayed to revalidate all 200 Stage110 1k bins and every originally listed GT1 event before a Stage112 report can be written. Stage110 and Stage111 private reports remain read-only.

## Question and method

The two Stage111 residual pockets are `[1,344,017,1,346,017)` (candidate DI exactly zero) and `[1,488,000,1,488,200)` (candidate DI nonzero). Compare a *fixed* candidate integer residual `floor(0.31 × open NAM f64 × 32768) − Manager PCM16` with its *fixed* open-output first difference (LSB/48-kHz frame), plus candidate-DI derivatives. The original Stage111 phase intervals and controls are reused without optimization.

Exact 1k/200-frame phase and 16-frame microbin summaries are stored in one private JSON. No original waveform samples or identifying private hashes appear in public results. Stage112 **does not generate new audio, infer NAM, run the Manager or DLL, resample, fit gain/lag/DC or output CLO**.

## Real outcome

- Primary zero-input tail GT1 decreases **392 → 16** across consecutive 1000-frame windows, alongside open output slope RMS **17.03 → 2.45 LSB/frame**.
- Secondary active-input 200-frame pocket: **32 GT1**, slope RMS **25.83 LSB/frame**, 9/32 GT1 frames among the top 20 slope frames.
- Predeclared controls are **more dynamic** (114 and 390 LSB/frame RMS) yet have no GT1. Thus slope by itself is not sufficient to explain these discrepancies.
- **No vendor-side parity established**: true model bytes/state, resampler, intermediate buffer, quantizer/gain, closed fitter, CLO and hardware remain unverified.

## Historical one-time cloud invocation (already executed, do not overwrite)

```bash
python3 research/htkpa/stages/stage112/GO.py \
  --private-inputs /PRIVATE/HTKPA_STAGE110_PRIVATE_INPUTS.zip \
  --stage97-zip /PRIVATE/CLO_10-19-26-0253.zip \
  --stage110-report /PRIVATE/stage110_micro_residual_private.json \
  --stage111-report /PRIVATE/stage111_event_boundary_private.json \
  --output /PRIVATE/stage112_waveform_morphology_private.json
```

**Private result:** Google Drive folder `RE_HTKPA`, filename `HTKPA_STAGE112_WAVEFORM_MORPHOLOGY_PRIVATE_20261021.json`. GitHub contains only public code, tests and safe aggregate findings. The script refuses to overwrite an existing private result.