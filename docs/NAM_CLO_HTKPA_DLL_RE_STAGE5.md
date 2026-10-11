# Sonicake HTKPA — Stage 5: Gaussian spectrum smoothing

**2026-10-12 · Static reverse engineering · Not a full vendor algorithm.**

This research continues Stage 4 on the user's Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. **The DLL was not executed or redistributed**; no physical device operations or production JS converter changes were performed. All addresses are virtual addresses relative to image base `0x180000000`.

## New confirmed data flow

In `0x1800B9B70`, the spectrum-magnitude ratio already found in Stage 3 is clamped to **[0.1,10]**, then passed to **`0x1800B7E10`** at `0x1800BAEF9`, followed by calls to `0x1800B65A0` and `0x1800B5A30`. The new function performs **Gaussian weighted averaging with boundary renormalization**.

With `N = ceil(0.1*sample_rate)`, the spectral array length is `B = trunc(0.5*N + 1)` and smoothing width is `W = trunc(0.1*B)`.

| Internal sample rate | N | B | W | Approximate Gaussian σ in frequency |
| ---: | ---: | ---: | ---: | ---: |
| 44,100 | 4410 | 2206 | 220 | ~440 Hz |
| 48,000 | 4800 | 2401 | 240 | ~480 Hz |
| 96,000 | 9600 | 4801 | 480 | ~960 Hz |

The independent mathematical kernel (unnormalized, indexing `k=1..W`), verified from double-precision constants and imported `exp`, is:

```
center = ceil(0.5*W)
weight[k] = exp(-0.5 * ((k-center)*5.0/W)**2)
```

- Addresses `0x1800B7E63`/`0x1800B7E85`: constant 5.0 divided by W.
- `0x1800B7E91`: `ceil` of half the window.
- `0x1800B7ECF`/`0x1800B7EDB`/`0x1800B7EDF`: squared, negative-half-scaled distance and `exp`.
- `0x1800B7EE8`: accumulate weights.
- `0x1800B7F02..0x1800B7FE1`: special even-W zero padding, reversed kernel, coefficients multiplied by `1e6/sum(weights)`.
- `0x1800B812F`: interior output multiplied by 1e-6; `0x1800B824C`: boundary output divided by sum of actually overlapping weights.
- `0x1800B8256`: final smoothing output stored in float32.

A **256-float (0x400-byte) work block** is also confirmed in `0x1800B65A0`, including a call to `0x1800B7670` with `0x100` and grouped processing of `0x20 × 8` samples. Its precise transform/overlap role and the relationship to final FIR taps require tracing; it is **not** evidence that a final FIR has 256 taps.

## Reproducible tests and caveats

Separate artifact `Sonicake_HTKPA_DLL_RE_Stage5_v0_5.zip` includes original, clean-room Python code (no proprietary program code), `verify_stage5.py`, `gaussian_spectrum.py`, seven passing unit tests, evidence JSON, optional visualizations, and `RESEARCH_REPORT.md`.

- **27 exact addresses**, **7 binary constants** and imported `exp`/`ceil` were checked against the pinned DLL. Two verifier runs generated identical JSON.
- Seven unit tests pass: 48k/44.1k/96k sizes, odd/even kernel, constant preservation including array edges, spike smoothing, finite/bounded step response.
- Illustrative Gaussian smoothing on the **ratio of finished 512-tap Post-FIR magnitudes** from the user-provided matched CLOs reduces adjacent-bin dB-slope variance by >95%. **This is intentionally *not* a reconstruction of internal Sonicake spectral inputs**, nor a test of auditory fidelity.
- Recovered isolated scalar math and even-window conventions are not bit-accurate end-to-end DLL reimplementation.

## Acceptance status and next targets

**Stage 4 FIR coefficient-level acceptance remains NOT MET.** We have located another processing stage, not recovered the exact 128/2048 final taps. Missing: the source/output spectral buffers, transform phase convention, `0x1800B65A0` → `0x1800B5A30` output mapping into `context+0x24408/+0x24410`, joint fitting and resampler interpolation.

The next scientific gate is unchanged: independently calculate a complete FIR using the same NAM/reference WAV, and numerically compare *all* nonzero coefficients with the matching official Windows Manager CLO on 2203 and/or SC20. Do **not** change production JS default, generalize a +2.5 dB boost, claim matching mobile SONICLINK or ship Gaussian processing from this isolated finding. The user-favored JCM800 2203 v0.2 C is retained as audible control.
