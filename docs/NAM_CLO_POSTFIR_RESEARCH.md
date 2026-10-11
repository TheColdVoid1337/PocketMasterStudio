# NAM → CLO: Post-FIR refit research (2026-10-12)

**Research stage only. This is NOT a Sonicake HTKPA reproduction, and is NOT enabled in the production Void Mod converter.**

## Evidence and matching test files

Two distinct, user-provided NAM captures have been examined, each with:
- NAM `SlimmableContainer/WaveNet` input,
- baseline `PocketMasterStudio Void Mod .clo`,
- vendor `Sonicake Manager .clo`,
- vendor `nam_input_wav.wav` and `outputFile.wav` from the same conversion session.

| Case | NAM SHA-256 |
| --- | --- |
| JCM800 2203 Crunch / SM57 | `29abbdbf982ee64b963d1d8de06848d1b06450a623bb08ba3ffefce146dfac42` |
| JCM800 SC20 Full Rig | Separate model; do not substitute it for the 2203 case |

The independent WaveNet implementation reproduces the vendor intermediate WAV, up to an approximately constant ×0.3100 scaling, with correlations above 0.999999 on multiple non-silent intervals in both captures. This supports the conclusion that the main discrepancy in current CLO files is associated with the subsequent DSP parameter fit, rather than the general interpretation of the WaveNet weight layout.

The vendor Windows Manager and mobile SONICLINK converters have **not** been proven equivalent. No claim of exact hardware DSP emulation or subjective quality follows from the numerical test.

## Experimental refit procedure (offline, Python research harness)

- Start with a *valid baseline CLO* as produced by current JS-only Void Mod.
- Independently render the same reference DI through the full WaveNet for selected windows.
- Keep baseline **128-tap input FIR**, **four nonlinear saturator parameters**, and **DC-blocker** unchanged.
- Solve a regularized Toeplitz least-squares problem for exactly **512 post-FIR taps** (the number transferred to the pedal), with a fixed ridge of `0.1 × R[0]`.
- Normalize the new post-FIR to the **baseline train-region RMS**, not to the official CLO's louder reference level.
- Encode a valid 8,840-byte VTSI/CLO with recomputed CRC16 only for an explicitly requested experimental candidate. No MIDI/BLE/device commands.
- Evaluate on disjoint time windows and separately on multiple DI input gain levels.

Training regions (seconds): `5–7, 18–20, 30–32, 43–45, 58–60`.

Held-out regions (seconds): `13–15, 26–28, 39–41, 53–55, 65–67`.

The lag used for evaluation is estimated **only from training audio**. Absolute correlation after signed gain alignment measures waveform *shape*, not loudness or perceived timbre.

## Held-out correlation results

| NAM | Input multiplier | Existing Void | Experimental post-FIR | Windows Manager |
| --- | ---: | ---: | ---: | ---: |
| JCM800 2203 | 0.03 | 0.9113 | 0.9163 | 0.9191 |
| JCM800 2203 | 0.10 | 0.8775 | 0.9150 | 0.9312 |
| JCM800 2203 | 0.30 | 0.8481 | 0.9214 | 0.9304 |
| JCM800 2203 | 1.00 | 0.7487 | 0.8948 | 0.8930 |
| SC20 Full Rig | 0.03 | 0.7447 | **0.7387 (regression)** | 0.3117 |
| SC20 Full Rig | 0.10 | 0.7198 | 0.7464 | 0.4640 |
| SC20 Full Rig | 0.30 | 0.7365 | 0.8021 | 0.5796 |
| SC20 Full Rig | 1.00 | 0.6581 | 0.7662 | 0.5667 |

All numbers are from offline modeling of the assumed 44.1 kHz `pre-FIR → asymmetric saturator → post-FIR → DC filter` signal path. The vendor models may have different phase/group delay and optimize different perceptual objectives; **a higher correlation does not establish better sound**.

On SC20 at ×0.03, the refit **gets worse**. It must not replace the shipping converter based on these two models.

## Important limitations

1. This prototype **requires an existing baseline CLO**, so it has not replaced current 5-probe fitting or shortened end-to-end NAM conversion.
2. The independent reference-signal generator is Python/Numba used **only for research**. No production requirement for Python, Dart, Rust, or any proprietary DLL is introduced; the existing Void Mod browser converter stays JS-only.
3. A temporal holdout on one 70-second DI is not an independently captured guitar performance.
4. The prototype re-estimates *only* Post-FIR; differences in nonlinear asymmetry, Pre-FIR, gain staging and audible character remain unexplained.
5. Neither the experimental file nor the simulated outcomes have been accepted on real hardware.
6. Captured proprietary tools and WAV data are not committed to this repository.

## Next tests before any production implementation

1. Jointly refine Pre-FIR and nonlinear saturator as well as Post-FIR, with multi-level holdout validation and explicit constraints on gain and headroom.
2. Compare an independently recorded, level-matched DI reamp through hardware slots for Void, experimental, and official CLO, inspecting loudness, distortion, spectrum, and latency.
3. Benchmark runtime and evaluate a pure-JS/WebAssembly integration behind an **off-by-default experimental switch** only after objective and listening acceptance on several independent NAMs.
4. Maintain existing SonicMaster parity tests for the *default path*, and add new regression references without contaminating vendor outputs or user test files.

No production behavior was changed as part of this research checkpoint.
