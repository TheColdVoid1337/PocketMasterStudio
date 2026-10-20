# Stage103 — real operator gain-window audit (2026-10-20 Bangkok)

**Operator outcome:** `STAGE103_OFFLINE_GAIN_WINDOW_DIAGNOSTIC_COMPLETED`; 9/9 test cases passed. Independent numerical calculations on existing private Stage102 raw C++ inference outputs and original Stage97 vendor WAV. No new inference or proprietary DLL run.

| Metric (fit window 300000–1500000 at 48 kHz) | Operator WSL result |
| --- | ---: |
| Zero-lag least-squares gain, open→Manager | `0.3098390026147448` |
| RMS residual after single gain | `0.0001907476759617998` |
| Normalized residual RMS | `0.008622319096669185` (0.8622319%) |
| Six 200k-frame gain coefficients' min-to-max spread / absolute mean | `0.3063457959701221%` |
| Prewarm ON/OFF full-output SHA-256 bitwise equal | **false** |

Stage102 had unadjusted RMS mismatch `0.049276130906865154` in the same fit window, and Stage103 demonstrates that a single diagnostic gain dramatically reduces it. There is a small but nonzero gain spread across six windows. **The fitted gain is not a discovered Sonicake converter gain parameter**, and no source code has been changed to bake it into production.

**Prewarm output SHA difference is real operator-reported evidence of non-identical full f64 files.** Stage102 identical printed per-fit-window aggregates did not prove bitwise identity. The Stage103 terminal summary did not expose the location, duration or size of the differences; no claim is made yet about whether they occur in the first 300k frames, the fitter interval, or the tail.

**Scope / provenance:** User-provided WSL terminal report. Assistant has not independently read/hashed the local private source WAV or raw f64 samples. Source-anchored experimental DI resampler may differ from Manager; vendor exact model bytes, intermediate output buffer identity, proprietary fitter numerical agreement, CLO generation and device readback remain unverified. Private originals and full Stage103 detailed report remain in ignored `research/_LOCAL_FILES`/RE_HTKPA, not public GitHub.

**Next:** offline Stage104 bitwise-difference localization between the two existing prewarm raw output files (SHA-pinned to Stage102), including first/last differing sample, chunk counts and RMS, without generating new audio.
