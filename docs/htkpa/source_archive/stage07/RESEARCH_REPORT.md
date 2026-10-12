# Sonicake HTKPA — Stage 7: independent WaveNet-derived Post-FIR magnitude

**2026-10-12 · Offline experiment · Not a verified HTKPA reimplementation**

## Objective and experimental boundary

Determine whether a 512-tap **minimum-phase Post-FIR** can be built from the known reference-DI signal and independently rendered NAM WaveNet output, **without using an official Sonicake output WAV or CLO for fitting**. The input stage is provided by the baseline, already-working Void Mod CLO (128 Pre-FIR, four nonlinear parameters and DC blocker). This is an **isolated replacement Post-FIR experiment**, not a complete NAM→CLO converter. It does not rediscover the upstream Pre-FIR or four saturation coefficients.

Two distinct NAMs were used: JCM800 2203 Crunch SM57 and JCM800 SC20 Full Rig. Each source NAM was independently inferred over five fixed two-second training windows and five disjoint holdout windows. The saved sparse 44.1-kHz WaveNet predictions, derived from each original NAM, were passed to the fitter. The **official Windows Manager Post-FIR was never read during fitting**; official files were opened *afterwards* solely for evaluation. No SONICLINK mobile CLO was available for direct numerical comparison.

## Stage-7 algorithm (original offline approximation)

1. Resample the shared stereo DI from 44.1/48 kHz to **44.1 kHz**, if needed.
2. Pass it through the **baseline Void Mod's** existing 128-tap Pre-FIR, asymmetric exponential saturator, and 2nd-order DC blocker. This produces the known internal excitation `q[n]`.
3. On five predefined training regions, compute Welch cross power spectral density `S_qy(f)` and input PSD `S_qq(f)`, using a **4800-sample Hann window** with 50% overlap. 4800 is a deliberately chosen 0.1-second analysis support corresponding to the observed HTKPA window, *not proof that our ratio equation is Sonicake's*.
4. Estimate the nonnegative output-filter magnitude as `|S_qy(f)| / (S_qq(f) + 1e-6 · max(S_qq))`. Interpolate log magnitude to 32768 FFT points.
5. Synthesize a causal 512-sample approximation via **real-cepstrum minimum-phase spectral factorization**. Identify the overall polarity from *training windows only*, since taking `abs` of the cross spectrum loses sign.
6. If explicitly generating an A/B CLO, adjust fitted FIR RMS to the **baseline's** training-window level; never adjust to vendor loudness or reference CLO. Recompute VTSI CRC16 and keep the other fields untouched. **No experimental file was generated in the delivered Stage-7 package because the method regresses on SC20 and underperforms our positively auditioned v0.1/v0.2 results.**
7. Evaluate on five windows not used for fitting. The exact same 70-second test DI underlies both training and heldout windows: this is *not* independent-guitar-performance generalization.

Train (seconds): 5–7, 18–20, 30–32, 43–45, 58–60. Heldout: 13–15, 26–28, 39–41, 53–55, 65–67.

## Reproducible NAM-only results

Absolute Pearson correlation of the simulated profile output against independently rendered NAM WaveNet output after training-only fixed lag and signed-gain alignment; **not on-pedal measurements**:

| NAM | Baseline Void | Stage 7 cross-spectrum + minimum phase | Earlier v0.1 Post-FIR refit | Stage 6 phase-only C projection |
| --- | ---: | ---: | ---: | ---: |
| JCM800 2203 Crunch | 0.74867 | **0.82262** | **0.89487** | 0.81740 |
| SC20 Full Rig | 0.65815 | **0.52652 (regression)** | **0.76620** | — |

For the 2203, v0.2 C is **0.88947** on the same heldout segments and is the user's previously preferred *hardware audition*. The Stage 6 projection was numerically inferior to C on these heldout waveform tests but **has not yet been physically listened to**.

**Polarity correction:** Without using waveform phase, the initial minimum-phase spectrum for 2203 had a signed heldout correlation of **−0.82262** even though its magnitude-based correlation was positive. Training-only polarity selection flips the resulting Post-FIR and gives **+0.82262**, with the same absolute correlation. This makes absolute correlation inappropriate as the only quality gate.

## Independent NAM WaveNet vs vendor intermediate WAV

In a **comparison-only** rerun, the candidate magnitude was estimated from the **captured Sonicake Manager outputFile.wav** instead of our independently rendered WaveNet samples. The two resulting 512-tap coefficient vectors had *unsigned cosine similarity*:

| NAM | Cosine of WAV-derived candidate vs NAM-derived candidate | Cosine of NAM-derived candidate vs official Windows Manager 512-tap Post-FIR (evaluation only) |
| --- | ---: | ---: |
| JCM800 2203 Crunch | **0.9999998881** | **0.92268** |
| SC20 Full Rig | **0.9999610985** | **0.91527** |

Their raw magnitude norms differ by approximately ×3.227, reflecting the known **0.31** intermediate-WAV scaling. The user-supplied vendor file was NOT needed for the Stage-7 Post-FIR calculation. This corroborates the previous finding that our WaveNet output is valid as the fitting target, **not** that the fitted Post-FIR matches Sonicake.

**Diagnostic upper bound involving official upstream coefficients:** If we *give the estimator* the already-known **vendor** Pre-FIR and four nonlinear gains (not deployable or independent!), the 4800-sample cross-spectrum estimate attains Post-FIR cosine **0.958 (2203)** and **0.924 (SC20)** relative to the official Post-FIR. That strong numerical result confirms upstream parameter coupling; it is not a NAM-only solution.

## Why applying the Stage-5 Gaussian directly is incorrect

Our exploratory test of smoothing the **final** spectral transfer magnitude with an approximately 480-Hz Gaussian (an *interpretation*, not a byte-exact reproduction of the DLL routine) caused major regression. With Void upstream and a 4800-sample window, the heldout correlations changed:

| NAM | No final-ratio smoothing | ≈480-Hz final-ratio Gaussian |
| --- | ---: | ---: |
| JCM800 2203 | 0.823 | 0.429 |
| SC20 | 0.527 | 0.169 |

**Implication:** The DLL's Gaussian smooths a *particular internal ratio/intermediate*, not necessarily the final Post-FIR magnitude estimated by our simplified linear cross-spectrum formula. Do not transplant the Stage-5 smoothing into a different signal path without tracing its array identities. The code/pinned Stage-5 finding itself remains valid.

## Additional observations

The magnitude response of Stage-7 Post-FIR approaches the official magnitude response (especially for 2203). However, **coefficient similarity, magnitude similarity and actual amplifier-output correlation are different tests**. Even a spectrally close 512-tap FIR is not a substitute for the correct Pre-FIR, asymmetric nonlinear stage, reference DI segmentation, phase/gain conventions, and joint fitting.

Files `freq_2203.png` and `freq_sc20.png` plot the normalized magnitude spectra of Stage-7 and baseline Void Post-FIRs with vendor coefficients shown **only as a post-fit comparison**. The curves are normalized at 400 Hz–2 kHz for *shape* comparison and do not indicate equal gain or loudness.

## Scientific verdict / next target

**Partial success, not acceptance.** We now have a working original procedure for obtaining a Post-FIR from **independent NAM WaveNet** plus the baseline Void upstream stage; it improves the default Void on 2203, but seriously regresses on SC20 and is worse than the already positively auditioned v0.1/v0.2 refit. The **Stage-4 original criterion — reconstruct official FIR coefficients from NAM/WAV — remains unmet**.

**Next needed step:** jointly identify **Pre-FIR and four nonlinear saturator coefficients**, tracking how the official HTKPA assigns its 6/23/30/50-second probe regions to optimization stages. In particular, reverse the input and output array identities in the three `0x1800BB210` selector calls and trace exactly where its Gaussian smoother sits. Test the joint fitter on disjoint NAM models *before* any JS production path or physical pedal trial. Preserve the current successful v0.2 C unchanged.

## Files / safety

- `spectral_lab.py` is self-contained and read-only **by default**, except writing JSON into an explicitly supplied output folder. It requires baseline CLO, reference WAV and **independent NAM output NPZ**; neither vendor software nor a vendor output WAV is an input. An experimental CLO can only be written with an explicit `--write-experimental-clo` flag and is labeled UNVALIDATED.
- `test_spectral_lab.py`: **5 passing tests**, including known minimum-phase 3-tap response, CRC16, disjoint windows and absence of vendor-input dependency in the spectral fit routine.
- `nam_only_validation.json`, `native_window_metrics.json`, `phase_candidate_holdout.json`, `2203_experiment/fitting_report.json`, `sc20_experiment/fitting_report.json`: research results with no source audio, full official FIR or private binary distributed.
- `freq_2203.png`, `freq_sc20.png`: purely derived spectrum comparison images.
- **Not included:** commercial Sonicake DLL, reference WAV, original NAM or their full proprietary CLO captures. No pedal commands; production JS converter unchanged.
