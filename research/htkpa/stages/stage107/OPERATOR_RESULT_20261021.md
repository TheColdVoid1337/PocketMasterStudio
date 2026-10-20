# Stage107 — real operator silence-floor sample verification (2026-10-21 Bangkok)

**Accepted operator WSL:** `STAGE107_SHA_GATED_SILENCE_FLOOR_INSPECTION_COMPLETED`. 13/13 regression tests passed. The source-grounded offline audit SHA-checked the original Stage97 ZIP and preexisting Stage102 C++ output / 48-kHz candidate input and consulted Stage105/106 reports. **No new NAM, resampler, DLL, Manager, Frida, fitter, CLO, or hardware run occurred.**

## All seven zero-input windows: byte-resolved observation

20,000-frame zero-DI input bins start at absolute 48-kHz frame indices:
`[1020000, 1040000, 1060000, 1080000, 1360000, 1380000, 1400000]`.

**For each of these seven bins, independently (140,000 frames total):**

| Measured item | Operator outcome |
|---|---:|
| Vendor Manager WAV, signed PCM16 unique values | **1** |
| Vendor PCM16 sample value | **+2**, all 20,000 frames in each bin |
| Vendor normalized signed mean | `0.00006103515625` |
| Vendor within-bin std | `0.0` |
| Open upstream NAM Core f64 mean | `0.00020439285435713828` |
| Open upstream NAM Core f64 reported std | `9.374415623260666e-11` |
| Fixed **0.31** open→vendor gain residual RMS | `2.326628600894295e-06` |
| Independent, locally fitted open→vendor silence scalar | approx. `0.298616879` (from previous Stage106 bins) |

The ~9.37e-11 reported open standard deviation is at the level of floating-point moment-subtraction roundoff, so do **not** assert genuine sample modulation without checking the separately stored `open_min`/`open_max` or direct word identity. In any case the open output is effectively constant at the printed precision. The `0.298616879` coefficient is the *ratio of two nonzero idle floors*, not credible evidence of a separate active-signal gain. A small **bin-specific fitted** error during silent DI is not evidence of proprietary NAM numerical parity.

Normalized residual for a **fixed** 0.31 multiplier on silence is 2.3266286e-6 full scale, about **0.0762 PCM16 LSB** (1/32768), rather than zero. The manager's +2 PCM16 PCM value may reflect rounding/quantization of a scaled model baseline; that mechanism is a **hypothesis**, not established native behavior.

### Active-window contrast

The user's printed selected active-window residuals (each independently gain-fitted) were:

| Start frame | Relative gain-fitted RMS residual |
|---:|---:|
| 340000 | 2.322171946% |
| 480000 | 2.517900961% |
| 580000 | 2.384221819% |
| 720000 | 2.409531644% |
| 960000 | 2.417743786% |
| 1300000 | 0.047464446% |
| 1320000 | 0.139771763% |
| 1340000 | 1.706683267% |

The discrepancy is substantially concentrated in quiet **nonzero** candidate DI, not idle silence. The Stage104 prewarm output was already bitwise identical on the entire fitter window, and Stage105 integer lag ±4/DC checks did not remove the early discrepancy.

## Next falsifiable low-cost hypothesis — PCM16 input conditioning

Stage101 established only that **directly quantizing** the public float32 44.1-kHz DI to PCM16 reproduces the input WAV from Manager exactly. Stage102 fed the **original float32 DI** through SonicMaster's open 44.1→48-kHz resampler. It is **not established** whether vendor inference receives the original float32 samples or PCM16-decoded values from its own WAV, or whether these float32 and PCM16-normalized samples already have identical values. Given much quieter nonzero DI in earlier windows, this is a source-controlled alternative to rewriting NAM itself, but **must be measured before claiming causality**.

**Next diagnostic**: read original exact-SHA Stage97 44.1-kHz input WAV and public float32 DI; compare `f32[i]` against `pcm16[i]/32768.0` at aligned indices (no interpolation, gain fitting, lag fitting, native inference or raw data publishing). Report full and relevant time-subset RMS difference, exact f32/f64 equality fraction, and fraction of float values deviating from decoded s16. If identical, reject this hypothesis; if not, evaluate source-conditioned resampling in a deliberately isolated subsequent stage.

**Limits:** Operator terminal transcript accepted as evidence; assistant has not retrieved private JSON/raw bytes independently. Original model loaded by proprietary Manager, vendor 44.1→48-kHz resampler, vendor output buffer provenance, proprietary fitter coefficients, generated CLO and device readback remain unverified. Source WAV/CLO/NAM/f64 stay in ignored private paths.
