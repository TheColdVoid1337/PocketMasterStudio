# Stage102 — real operator NAM output boundary comparison (2026-10-20 Bangkok)

**Gate:** `SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED` — completed on operator WSL, **not vendor NAM numerical parity**.

Operator ran Stage102 after `git pull --ff-only` and **7/7 offline regression PASS**. `doctor` returned `STAGE102_PREFLIGHT_PASS`, real Dart 48-kHz candidate DI preparation and both pinned upstream NeuralAmpModelerCore runs completed, and the authentic original Manager 70-s output WAV was compared for 1,600,000 initial frames at 48 kHz. The **published measurements** below are for the [300,000, 1,500,000) fitting window (1,200,000 frames), with no gain or lag fitting.

| Metric | Prewarm OFF | Prewarm ON |
| --- | ---: | ---: |
| Error RMS | 0.049276130906865154 | 0.049276130906865154 |
| Maximum abs error | 0.34653806686401367 | 0.34653806686401367 |
| Manager WAV RMS (reference) | 0.02212254891326 | 0.02212254891326 |
| Open NAM Core RMS | 0.07139748826850241 | 0.07139748826850241 |
| Normalized RMS error | 2.227416519681853 | 2.227416519681853 |
| Zero-lag cosine similarity | **0.9999628271157859** | **0.9999628271157859** |

**Interpretation:** The waveform is almost collinear at zero lag, while the open C++ output RMS is about **3.22736×** the saved Manager WAV RMS. The similarity and magnitude discrepancy are consistent with an amplitude-scale difference, but no mechanism or numerical vendor parity has yet been proved. Because the two warmup settings report identical aggregates, **it is not yet known whether the two raw outputs are bitwise identical**.

**Analytical-only single-gain projection (not executed on audio):** deriving a least-squares multiplier `k = cosine * reference_rms / open_rms` from the printed aggregates yields **k≈0.309839002615** (open→Manager). Corresponding ideal minimized error RMS under *one global gain, zero lag, no DC offset* is **≈0.000190747676**, i.e. **≈0.86223%** of Manager reference RMS. This is a calculation from summary values only, **not actual normalized-output evidence**, an established Manager gain setting, or a correction to a verified shared signal path.

**Provenance boundaries:**
- Stage101 exact input-file PCM16 equivalence is reproduced (`same_di_pcm16=true`), but the **44.1→48-kHz open SonicMaster resampler remains an unverified stand-in** for proprietary Manager preprocessing.
- The exact NAM source bytes used by the vendor and the native code's link to the captured output WAV are **not** independently proved.
- The observed strong near-zero-lag shape association is suggestive, not proof of the identical implementation; neither proprietary FIR fitter, numeric CLO, device output nor hardware parity is verified.
- The underlying private `comparison_private.json`, original ZIP, model bytes and f64 files **remain off GitHub**. User-supplied WSL console report is the evidence; assistant did not independently rehash these private outputs.

**Next falsifiable test:** offline post-analysis of the existing ignored Stage102 private run: record SHA equality ON vs OFF, fit gain separately by time window, signed residual RMS after unity-lag single-gain fit, and identify whether gain is stable. Do **not** rerun Stage102 (existing-folder overwrite guard). This test can precede invasive resampler tracing or a new Manager execution.
