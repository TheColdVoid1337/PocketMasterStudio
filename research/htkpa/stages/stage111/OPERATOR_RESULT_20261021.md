# Stage111 — real cloud-run GT1 residual events near DI cessation and during active input

**Date:** 2026-10-21 Bangkok. **Operator:** independent assistant Python cloud sandbox. **Real result:** `STAGE111_OFFLINE_EVENT_BOUNDARY_AUDIT_COMPLETED`. Stage110 input bundle and Stage97 original manager output were opened directly and source/SHA/status gates passed. Original 200 1k Stage110 mismatch/GT1/nonzero-DI counts were remeasured from the source f64/PCM16 and reconciled. **12/12 separate synthetic unit tests PASS**. The private full result is uploaded to the user-designated restricted Drive folder `RE_HTKPA` after the real run. No new device/DLL/Manager, inference, resampling, FIR fitting, gain/lag/DC fitting or CLO generation. Public report is sanitized aggregates only.

## Exact boundary accounting

The authenticated *open candidate* DI ends with its last nonzero f64 sample at **1,344,016**; candidate DI is exactly zero from **1,344,017 through 1,359,999**. This describes **open-source candidate DI**, not established vendor-side DI. Define GT1 as `abs(clamp_s16(floor(0.31 × openNAM_f64 × 32768)) − original_Manager_s16) > 1`.

| Parent hotspot | GT1 total | Before or at final nonzero candidate DI sample | After DI becomes exactly zero | Earliest/last GT1 |
|---|---:|---:|---:|---|
| `[1340000,1360000)` | **429** | **21** | **408** | 1,343,968–1,345,228 |
| `[1480000,1500000)` | **33** | Not an input-zero event | Not an input-zero event | 1,480,801–1,488,103 |

For the first parent hotspot, **408/429 = 95.1049%** of large residual events occur **after** the final nonzero candidate-DI sample. Error indices after zero onset are not asserted to be continuously over threshold. The residual persisted as isolated GT1 events through frame 1,345,228, over 1,200 sample positions after zero onset.

## Phase-localized measurements

| Region (absolute 48k frames) | DI-nonzero frames | GT1 | All PCM16 nonmatches | Error RMS LSB | Max abs LSB |
|---|---:|---:|---:|---:|---:|
| `[1343000,1344017)` before/at last nonzero DI | 1,017 / 1,017 | **21** | 58 | 2.150438 | **27** |
| `[1344017,1345017)` zero-DI first 1000 | 0 / 1000 | **392** | 761 | **2.858146** | 16 |
| `[1345017,1346017)` zero-DI next 1000 | 0 / 1000 | **16** | 476 | 0.723878 | 2 |
| `[1487800,1488000)` preceding active | 200 / 200 | 0 | 5 | 0.158114 | 1 |
| `[1488000,1488200)` active hotspot | 200 / 200 | **32** | 107 | **1.151086** | 4 |
| `[1488200,1488400)` following active | 200 / 200 | 0 | 61 | 0.552268 | 1 |
| `[1300000,1302000)` control | 2000 / 2000 | 0 | 10 | 0.070711 | 1 |
| `[1460000,1462000)` control | 2000 / 2000 | 0 | 24 | 0.109545 | 1 |

Stage111's 64-sample local audit further localized the first dense burst in `[1343992,1344056)` and neighboring subwindows, with **52 GT1** in each of `[1343992,1344056)`, `[1344056,1344120)` and `[1344184,1344248)` (disjoint windows) despite candidate DI going exactly zero during the first window. The second burst is concentrated in `[1487992,1488120)`, 32 GT1 in total; all 200 tested center-window samples retain nonzero DI.

## Conclusion, not over-interpretation

The first hotspot is strongly associated with **input cessation and the subsequent candidate-NAM/output PCM16 tail**; this is consistent with differing processing state, input resampling tail or PCM conversion, but these mechanisms are **not separately identified** by current data. The second hotspot represents an independent nonzero-DI discrepancy, so a universal zero-input explanation is contradicted. This experiment does not establish native vendor gain or `floor` quantizer implementation, vendor model identity, vendor resampler parity, actual output buffers, proprietary fitter, CLO bytes or device equivalence.

**Next falsifiable study (not yet built/run):** Compare signed temporal shapes of the two high-error pockets with their input waveforms (amplitude and local derivative, without fitting the observed output), and distinguish isolated transient correlation from broad sustained mismatch. Require pre-specified controls. No production converter change.
