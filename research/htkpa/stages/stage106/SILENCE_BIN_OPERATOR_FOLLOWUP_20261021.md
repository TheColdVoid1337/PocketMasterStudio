# Stage106 follow-up — silence-bin output inspection (operator WSL)

**Date recorded:** 2026-10-21 Bangkok. The operator printed selected rows from the **already generated** private Stage105 and Stage106 numerical JSON reports. No new DSP run or native capture. Results below are *operator console*, not assistant independent access to raw WAV/f64 or the full private JSON.

Of 60 equal 20k-frame fitter-region windows, **7 have candidate 48-kHz DI RMS exactly zero** according to Stage105's existing per-bin metrics.

| Bin start (20k frames) | Candidate DI RMS | Manager WAV RMS | Open NAM Core RMS | Diagnostic fitted gain open→Manager | Relative residual after individual gain |
|---:|---:|---:|---:|---:|---:|
| 1,300,000 | 0.397624030 | 0.037077045 | 0.119602426 | 0.310002417 | 0.047464% |
| 1,320,000 | 0.397628785 | 0.012454138 | 0.040166970 | 0.310058881 | 0.139772% |
| 1,340,000 | 0.177821195 | 0.001605077 | 0.005181132 | 0.309747623 | 1.706683% |
| 1,360,000 | **0** | **0.000061035** | **0.000204393** | **0.298616879** | **0.000046%** |
| 1,380,000 | **0** | **0.000061035** | **0.000204393** | **0.298616879** | **0.000046%** |
| 1,400,000 | **0** | **0.000061035** | **0.000204393** | **0.298616879** | **0.000046%** |

For context, `2 / 32768 = 0.00006103515625`, matching the **rounded RMS** displayed for the vendor silence bins. **This does not by itself prove each PCM16 sample equals +2**, nor prove the open output is a constant DC offset: RMS alone has no sign or within-bin variance information. An independently optimized scalar on an almost constant pair of signals can make the relative residual arbitrarily small without establishing equivalence for active DI.

**Top 5 bins by absolute individually gain-fitted residual RMS** (all candidate DI RMS near `0.001`):

| Bin [start,stop) | Absolute residual RMS | DI RMS | Relative residual |
|---|---:|---:|---:|
| [480000,500000) | 0.0003532015557144475 | 0.00101093029346955 | 2.517900960990324% |
| [960000,980000) | 0.0003392726876393398 | 0.0010140741292895307 | 2.417743785911433% |
| [720000,740000) | 0.00033722011999739874 | 0.0010105876065393212 | 2.4095316438494344% |
| [340000,360000) | 0.00033004985781037163 | 0.0010104439384259634 | 2.322171946044755% |
| [580000,600000) | 0.0003276963134930861 | 0.0010027971654273473 | 2.3842218187072495% |

**Interpretation:** quiet but **nonzero** DI windows show substantially greater absolute residual error after gain correction than silence windows. At the [1359999,1360000] boundary, the Stage106 enormous *ratio of two separately fitted relative residuals* coincides with the transition to a zero-DI bin and does **not** prove an instantaneous DSP mode switch. The tentative "silence DC floor" explanation remains unverified until raw sample means, standard deviations and PCM16 value histograms are inspected.

**Next:** Stage107 offline SHA-checked *read-only* silence-floor audit using existing Stage102 input/open f64 files and original Stage97 ZIP; no NAM inference, no changes to production, no CLO fitter or hardware parity claims.
