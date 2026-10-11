# HTKPA Stage 7 — NAM-only spectral Post-FIR reconstruction experiment

**2026-10-12 | Research-only | Production unchanged | Original HTKPA coefficient-reconstruction gate still NOT MET**

## Experimental objective

Estimate a 512-tap *minimum-phase* Post-FIR from the known 70-second input DI and **independently computed NAM WaveNet output**, retaining the baseline Void Mod **Pre-FIR / asymmetric saturator / DC blocker**. This is an original Python analysis experiment, **not** the complete official HTKPA, and **not** a standalone NAM-to-CLO converter: the baseline CLO and independent WaveNet predictions are required.

A separate user-delivered bundle `Sonicake_HTKPA_RE_Stage7_v0_7.zip` contains a CLI fitter, tests, per-model reports, numerical validation, and frequency-response plots. **No proprietary DLL, NAM, user WAV or official CLO file was committed.**

## Procedure

- Input is the shared stereo reference DI resampled to 44,100 Hz, with ten fixed two-second 44.1-kHz NAM WaveNet predictions.
- Apply baseline Void Mod 128-tap Pre-FIR, four exponential saturator coefficients and two-pole DC blocker.
- On five training windows (5–7, 18–20, 30–32, 43–45, 58–60 s), use a **4800-sample Hann window** and 50% overlap. Estimate `|S_qy| / (S_qq + 10^-6 × max(S_qq))`.
- Interpolate log magnitude to a 32768-point FFT, reconstruct a causal 512-tap minimum-phase response via the real cepstrum.
- Resolve overall sign/polarity from **training waveform only**. Magnitude alone lost this sign and initially produced **-0.823 signed correlation** for JCM800 2203; correct polarity is +0.823.
- For optional experimental CLO export only, preserve baseline training RMS and regenerate CRC16; research CLI **does not write a CLO without an explicit flag**.
- Validation windows are disjoint (13–15, 26–28, 39–41, 53–55, 65–67 s), but from the **same** 70-second DI; generalization to independent playing is unproven.

The shared 4800-sample support was motivated by Stage 5's verified 0.1-second spectral window. The above PSD ratio is **our hypothesis**, not a proven transcription of Sonicake HTKPA mathematics.

## Heldout results

Absolute signed-gain-aligned waveform Pearson correlation against **independent NAM WaveNet output**:

| Model | Baseline Void | Stage-7 independent WaveNet fit | Previously good v0.1 refit | User-preferred v0.2 C | Stage-6 projected C |
| --- | ---: | ---: | ---: | ---: | ---: |
| JCM800 2203 Crunch | 0.74867 | **0.82262** | **0.89487** | **0.88947** | 0.81740 |
| SC20 Full Rig | 0.65815 | **0.52652 — regression** | **0.76620** | n/a | n/a |

Stage-7 is **not suitable as a replacement**: it loses to the positively auditioned refit for 2203 and regresses on SC20.

## Crucial no-vendor-audio reproducibility check

After fitting, but **only for validation**, estimate the same candidate once more using the official Windows Manager `outputFile.wav` instead of our independent WaveNet. Shape similarity of the resulting 512-tap filters:

| NAM | Cosine: independent-WaveNet fitted Post-FIR vs vendor-WAV fitted Post-FIR | Post-FIR cosine to official Windows Manager (evaluation only) |
| --- | ---: | ---: |
| JCM800 2203 | **0.9999998881** | **0.92268** |
| SC20 | **0.9999610985** | **0.91527** |

The norm ratio of the WaveNet-fitted impulse vs vendor-WAV-fitted impulse is roughly **3.227**, matching the known official WAV `×0.31` scaling. Thus **the target audio no longer requires the official manager**, while the upstream chain *still* does not match HTKPA.

When the **already-known official Pre-FIR and nonlinear parameters** were substituted as diagnostic upstream coefficients (not independent or deployable), the candidate Post-FIR cosine rose to about **0.958 (2203) and 0.924 (SC20)**. This demonstrates that fitting upstream stages jointly remains necessary.

## Stage 5 Gaussian finding needs correct placement

Applying a naive **≈480-Hz Gaussian smoothing directly to the final estimated Post-FIR spectral ratio** degraded heldout waveform correlation:
- 2203: **0.823 → 0.429**;
- SC20: **0.527 → 0.169**.

This experiment **does not falsify** the recovered Sonicake Gaussian kernel. The vendor smooths a specific *intermediate*, not necessarily the final simplified transfer ratio. Array identities must be recovered before transplanting it.

## Acceptance, next work, and safety

**Stage 4's strict acceptance criterion remains unmet:** no full official FIR is yet generated from NAM/WAV and shown coefficient-exact against Windows Manager. Cosine similarity of Post-FIR vectors is not a waveform or listening-quality metric, and the Windows Manager output is not proven identical to mobile SONICLINK.

**Next:** recover the complete input/output buffer identities for HTKPA's selectors **2 → 1 → 3**, jointly identify **Pre-FIR and nonlinear gains**, locate the Gaussian smoother within that actual computation, then reevaluate the end-to-end 128/2048 taps on both NAMs. Do not add arbitrary per-model boosts, do not replace the production browser JS converter, and keep the JCM800 2203 v0.2 C audio-accepted reference intact. Stage 6's phase-only candidate also remains **unvalidated by hardware listening**.

No physical pedal operation occurred. Five standalone Stage-7 Python tests and both read-only NAM-only benchmark runs passed; output ZIP integrity was verified.
