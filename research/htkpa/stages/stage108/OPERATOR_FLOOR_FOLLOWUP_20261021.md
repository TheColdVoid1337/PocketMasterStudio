# Stage108 floor-to-negative-infinity operator follow-up (2026-10-21 Bangkok)

**Operator provenance:** Real WSL console from the user's local SHA-gated original Stage97 48-kHz PCM16 WAV and the preexisting Stage102 NAM Core C++ f64 output. The assistant did not independently inspect the private raw f64/WAV. No new inference, Manager/DLL/Frida/resampling, fitter or device execution. This was a **read-only inline Python follow-up**, not Stage109 operator output.

**Candidate** `clamp_s16(floor(0.31 * open_nam_f64 * 32768))`; error sign is **predicted integer − original Manager integer**. Exactly seven known Stage107 silent 20k bins were excluded from active denominators.

| Active samples | Quantizer | Exact match | Within ±1 LSB | Signed mean LSB | Error RMS LSB |
|---|---|---:|---:|---:|---:|
| Quiet early (720k) | nearest | 10.13764% | 26.62278% | +0.50628 | 8.07876 |
| Quiet early (720k) | **floor** | **10.48958%** | 27.13639% | +0.01326 | 8.06338 |
| Quiet early (720k) | trunc | 10.13653% | 26.60236% | +0.50565 | 8.03972 |
| Quiet early (720k) | ceil | 8.23917% | 25.37222% | +1.01326 | 8.12678 |
| Loud late (340k) | nearest | 55.10912% | 99.83265% | +0.44769 | 0.69779 |
| Loud late (340k) | **floor** | **98.60235%** | **99.86412%** | **+0.00022** | **0.22370** |
| Loud late (340k) | trunc | 52.96471% | 99.54206% | +0.46750 | 0.71855 |
| Loud late (340k) | ceil | 0.61618% | 99.24853% | +1.00022 | 1.02493 |
| Late, open-output positive | **floor** | **98.80081%** | 99.90448% | +0.00136 | 0.19743 |
| Late, open-output negative | **floor** | **98.37610%** | 99.81810% | −0.00108 | 0.25030 |

**Late active floor** exact integers **335,248/340,000**, leaving **4,752 mismatched samples**. Improvement over nearest: **+43.493235 percentage points**. The reported whole late-active floor residual histogram begins: `0:335248; +1:2195; -1:2095; -2:102; +2:90; +3:52; -3:49; +4:35; -4:24`. Nearest, by contrast: `0:187371; +1:151829; -1:231; +2:216; -2:67; +3:66; +4:47; -3:36; +5:29`.

**Interpretation and limits:**
- The **sign-symmetric, ~98.6% exact** result at candidate floor+0.31 on later nonzero DI is powerful evidence that an output-floor-like integer mapping is worth testing; it is **not proof** of Sonicake's internal quantizer, true output gain or actual NAM sample identity.
- In earlier *active* 720k samples, floor still matches only ~10.49% and RMS ~8.06 LSB; the dominant discrepancy lies **upstream of or in addition to** final integer rounding.
- The tested float32 source DI and original decoded PCM16 44.1-kHz input were independently shown numerically equal for all 3,087,000 frames. Proprietary 44.1→48-kHz input resampling and actual Manager-loaded model/buffer identity are unverified.
- The nearly fully aligned late signal is not evidence of proprietary FIR fitter or CLO device equivalence. No production changes or private audio publication.

**Stage109 prepared:** read-only SHA-gated source-localizer of fixed-0.31 floor residual across every active 20k fitter-window bin, sign groups and the 4,752 remaining late-active mismatches. This follow-up does **not** count as a real Stage109 run. Await user WSL Stage109 terminal evidence before promoting its status.
