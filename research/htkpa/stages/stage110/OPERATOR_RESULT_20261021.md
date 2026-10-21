# Stage110 — real cloud 1k PCM16 floor residual localization (2026-10-21 Bangkok)

**Status:** `STAGE110_OFFLINE_1K_GT1_TOPOLOGY_COMPLETED`. Independent **assistant cloud Python** execution on user's private, authenticated source files, **not** user WSL console and **not** a repeat of Stage109. Original Stage97 vendor ZIP fetched from the connected private `RE_HTKPA` Drive folder; exact Stage97 SHA verified against public Stage102. Seven-member uploaded Stage110 input ZIP contained the original Stage102 open NAM f64 output, resampled candidate DI, and completed Stage102/105/107/108/109 reports.

**Source gates passed:** Stage102 output f64 and candidate 48k DI SHA; Stage102→108→109 and Stage107→109 exact report chain; Stage97 archive identity and authentic WAV metadata; rescan of every Stage109 20k active window. Independently reobtained **75,525/720,000 early** floor exact, **335,248/340,000 late** exact, **4,752 late nonmatches**, and **462 late frames above 1 LSB**. Sample rate 48kHz, predicted-minus-Manager signed PCM16 errors. All SHA-256 identifiers for private reports and raw model/audio are intentionally omitted.

**Method:** Existing 1.6M-frame C++ NAM upstream `f64le` and authentic Stage97 48k PCM16 WAV compared with historical fixed diagnostic candidate `clamp_s16(floor(0.31 * f64 * 32768))`; no gain/lag/DC refit. Scanned 200 contiguous 1k bins in absolute sample interval `[1300000,1500000)`. Also read the original Stage102 candidate resampled DI f64, distinguishing mathematically zero vs nonzero input. No model inference, Dart resampling, closed Manager/DLL, Frida, fitter, CLO, hardware, or production code changes.

## Real 1k-window findings

| Absolute 1k window | Floor nonmatches | `abs(error)>1 LSB` | Max abs LSB | Nonzero candidate DI frames |
|---|---:|---:|---:|---:|
| [1343000,1344000) | 41 | 5 | 3 | 1,000 |
| **[1344000,1345000)** | **772** | **408** | **27** | **17** |
| [1345000,1346000) | 479 | 16 | 2 | **0** |
| [1480000,1481000) | 29 | 1 | 2 | 1,000 |
| **[1488000,1489000)** | **245** | **32** | **4** | **1,000** |

**All 462** late `abs(error)>1` frames fall into just these **five 1k bins**; all other 1k bins of the Stage110 200k scan have zero GT1. Two leading 1k bins alone account for **440/462 = 95.2381%** of late GT1. These two intervals comprise 2,000 frames, or **0.5882%** of Stage109's 340k late-active denominator; historical Stage109 denominators remain unchanged.

**End-of-input association:** in parent `[1340000,1360000)` only **4,017/20,000** resampled candidate DI samples are nonzero. Its **last nonzero DI sample is absolute index 1,344,016**. Parent-window GT1 residuals first occur at **1,343,968**, last at **1,345,228**, straddling the candidate input becoming exactly zero. This is a concrete, localized input-stop/tail association, **NOT evidence of the cause** (e.g. a proven vendor resampling kernel, state reset or model architecture).

**Independent active-input outlier:** `[1488000,1489000)` has **1,000/1,000 nonzero DI** frames and 32 GT1 residuals (max 4 LSB); a silence-only theory is therefore insufficient.

**Earlier near-idle clarification:** `[1420000,1440000)` has only **16/20,000 nonzero candidate DI frames**, all in `[1439984,1440000)`; the region is entirely PCM16-exact, but the 100% agreement is essentially an idle-floor observation, not active NAM parity. Its original Stage105 DI RMS (~5.8582e-08) was recomputed.

**Tests and software:** Cloud source-only Python tool with read-only hash/provenance checks, original output count reconciliation, and exclusive no-overwrite private report: **13/13 independent synthetic tests PASS**, and successful **real-data run**. The runnable public source, tests, README, evidence and this operator note were packaged for the user as `HTKPA_STAGE110_PUBLIC_TOOLS_AND_RESULTS.zip`, SHA-256 `6f72d5b0843eccaa48f7632177927fa3c498055eafe72876faafda4a6b0855bb`. This GitHub commit is the public *research result*; the supplied ZIP is the verified source distribution. Do not imply that code has been added under `stage110/GO.py` until it actually is.

**Evidence ceiling:** vendor loaded model bytes, 44.1→48k preprocessing, exact native output buffer, actual gain/PCM16 quantizer semantics, proprietary fitter, CLO numeric parity and hardware behavior remain **UNVERIFIED**. Follow-up may inspect input-boundary provenance near index 1,344,017 and the separate active-input outlier at ~1,488,000 using narrow source-first tests. Do not repeat Stages102–109 or overwrite their reports.
