# Stage109 — real operator fixed-floor residual topology (2026-10-21 Bangkok)

**Status:** `STAGE109_OFFLINE_FIXED_FLOOR_RESIDUAL_TOPOLOGY_COMPLETED` from actual user's WSL console, not merely synthetic fixtures. Operator fast-forwarded `main` to `2d53dc00897e0cc03dcce86fb9330c75adb1670b`, ran `test_htkpa_stage109.py` (**15/15 PASS**), then ran the prepublished `stage109/GO.py` once with the original Stage108 private report and Stage97 ZIP. A new ignored `stage109_floor_residual_topology_private.json` was reported under the existing private Stage102 run directory. The assistant parsed the entire supplied console JSON, but has **not** independently read or rehashed the private report, original WAV or f64 bytes.

## Method, denominators and source gates

- Original Stage97 authentic Manager `outputFile.wav` 48-kHz signed stereo PCM16 versus the existing Stage102 pinned upstream NAM Core prewarm-OFF f64 output, with fixed `0.31` gain. Tested `clamp_s16(floor(0.31 * f64 * 32768))` against `clamp_s16(round_nearest_even(0.31 * f64 * 32768))`; **error sign = predicted integer minus Manager integer**.
- Fitter interval `[300000,1500000)` at 48 kHz. Seven candidate-DI-zero 20,000-frame bins are excluded from active denominators: four early bins (80k) and three late bins (60k), leaving **720k early active** and **340k late active**.
- Stage109 source checks SHA provenance for Stage102/107/108 and authentic original Stage97 bundle, compares original C++ output SHA/size and recomputes Stage108 nearest-even active exact counts. Successful script completion is the evidence that these program gates passed on the operator's machine; original private contents were not available to the assistant for independent verification.
- No fresh NAM inference, resampling, proprietary Manager or DLL/Frida execution, FIR fitting, CLO rendering or device I/O. All source assets and previous private reports were read-only; production code was unchanged.

## Real comparison: active frames only

| Region / polarity | Frames | Floor exact | Floor exact % | Nearest-even exact | Nearest-even exact % | Floor within ±1 LSB | Floor RMS (LSB) | Floor max abs (LSB) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Early active | 720,000 | 75,525 | 10.489583% | 72,991 | 10.137639% | 27.136389% | 8.063378 | 77 |
| Late active | 340,000 | 335,248 | **98.602353%** | 187,371 | 55.109118% | **99.864118%** | **0.223699** | 27 |
| Late open-output nonnegative | 181,123 | 178,951 | 98.800815% | 108,258 | 59.770432% | 99.904485% | 0.197431 | 27 |
| Late open-output negative | 158,877 | 156,297 | 98.376102% | 79,113 | 49.795125% | 99.818098% | 0.250304 | 27 |

**Late floor residual:** exactly **4,752 non-matching samples / 340,000**, of which **462** have absolute error greater than one PCM16 LSB and **4,290** have absolute error exactly one LSB. Late integer-error counts are balanced by sign (2,426 positive versus 2,326 negative frames), with signed mean **+0.0002176471 LSB**, absolute mean **0.0180176471 LSB**. Bounded signed histogram: `<-3:80; -3:49; -2:102; -1:2095; 0:335248; +1:2195; +2:90; +3:52; >3:89`.

**Early active floor** remains strongly mismatched: **75,525/720,000** exact, RMS **8.0633782 LSB**, maximum **77 LSB**, with **524,618** errors greater than 1 LSB. This discrepancy was not resolved by late-signal quantizer candidate agreement.

## Late mismatch localization — ranked 20k active windows

| Window start | Exclusive stop | Non-matches | Exact % in bin | RMS residual (LSB) | Max abs (LSB) |
|---:|---:|---:|---:|---:|---:|
| 1,340,000 | 1,360,000 | **1,700** | 91.500% | **0.830692** | **27** |
| 1,480,000 | 1,500,000 | 810 | 95.950% | 0.220341 | 4 |
| 1,440,000 | 1,460,000 | 561 | 97.195% | 0.167481 | 1 |
| 1,460,000 | 1,480,000 | 268 | 98.660% | 0.115758 | 1 |
| 1,100,000 | 1,120,000 | 222 | 98.890% | 0.105357 | 1 |
| 1,120,000 | 1,140,000 | 178 | 99.110% | 0.094340 | 1 |
| 1,160,000 | 1,180,000 | 154 | 99.230% | 0.087750 | 1 |
| 1,180,000 | 1,200,000 | 141 | 99.295% | 0.083964 | 1 |

The **first** late-active mismatched absolute sample index was `1104003`, the **last** was `1499952`. The top three windows contain **3,071/4,752 = 64.6254%** of late-active non-matches; the leading `[1340000,1360000)` bin alone holds **1,700/4,752 = 35.7744%**, even though it covers only 20k of 340k active frames. The top eight account for 4,034/4,752; the console did **not** print the remaining nine bin records. The full 20k-bin details are in the private ignored report, not in public GitHub.

## Interpretation and evidence ceiling

- Strong candidate floor+0.31 correspondence on later active signal is corroborated in a real SHA-gated audit; it **does not identify Sonicake's native output quantizer, gain, inference implementation or buffer provenance**.
- The leading residual hotspot `[1340000,1360000)` immediately precedes a previously identified zero-candidate-DI bin starting at 1,360,000. This is a **window-level association**, not proof of a sample-exact transition, DSP mode switching, model state decay, or any unique causal mechanism.
- Later hotspots `[1440000,1500000)` show the residual is not exclusive to the pre-silence window. The residual distribution and early-active non-parity warrant further provenance-sensitive analysis, not immediate DSP changes.
- Original 44.1-kHz DI equality has been shown in prior operator evidence, but **vendor 44.1→48-kHz resampler parity, exact proprietary loaded NAM bytes, Manager output-buffer origin, closed FIR fitter parity, generated CLO correctness and hardware readback remain unverified**.
- Next gate, **not yet implemented or run**: decide on a narrow, read-only test of transition-localized residuals and candidate-vs-vendor input provenance before any additional inference or private capture. Reuse the existing Stage109 private JSON; do **not** rerun Stage109 and do not overwrite its report.
