# Stage113 — original 44.1-kHz source ↔ open 48-kHz candidate DI support boundaries

**Date:** 2026-10-21 Bangkok. **Real source run in assistant cloud sandbox:** `STAGE113_OFFLINE_SOURCE_INPUT_TRANSITION_SUPPORT_COMPLETED` (original Stage97 vendor-export 44.1-kHz *input* WAV + existing Stage102 source-derived open 48-kHz candidate DI). **17/17 synthetic unit tests PASS**. The standalone private JSON was created *once* after SHA/status/ZIP-allowlist checks. No new sample-rate conversion, NAM inference, proprietary Manager/DLL, native intermediate capture, closed fitter, CLO output or device interaction.

## Scope and key limitation

This experiment maps exact **nonzero support** across two **already existing** representations of the same historical input material: (a) the saved original 44.1-kHz stereo-duplicated signed PCM16 `wavs/nam_input_wav.wav` in the authentic, SHA-pinned Stage97 export, and (b) the *candidate* 48-kHz f64 signal generated previously by the open SonicMaster resampler in Stage102. The original input WAV is **not** a capture of Sonicake's internal 48-kHz NAM input. Time support alignment is **not** proof of native/proprietary resampler equivalence.

No sample values, private filenames beyond established project basenames, identifying original private file digests, full private reports or audio are committed publicly.

## Strict method

- SHA-gated Stage97 archive and Stage102, 105, 107, 108, 109 source-report chain, plus exact Stage102 1.6M f64 DI and NAM-output digests, through the existing Stage110 `read_inputs` function (authentication only; **no Stage110 analyze rerun**).
- Read original Stage97 *input* WAV; confirm fixed 44.1-kHz PCM16 stereo-duplicated metadata and complete sample-count. Validate existing Stage110–112 report statuses and immutable Stage111 input-boundary / GT1 count claims; no Stage110–112 algorithms rerun.
- Preselected scans: `[1342000,1350000)` to locate candidate end, `[1430000,1450000)` for next source re-entry, and the three pre-existing active 200-frame control/event intervals `[1487800,1488400)`.
- Map source sample indices to the 48-kHz time axis with the **exact rational** `source_index × 160/147` (no interpolation or estimation of the vendor resampler). Scan exact-zero bridges in both original source and 48-kHz open candidate; compute normalized RMS and nonzero counts for secondary controls.
- Write exactly one private ignored JSON and refuse overwrite. All inputs immutable/read-only; no fit/lag/gain/DC optimization.

## Genuine original-source observations

| Source-support event | Original 44.1-kHz input | Open 48-kHz candidate input | Observed 48-kHz boundary spread |
|---|---:|---:|---:|
| Final nonzero frame before silence | **1,234,799** | **1,344,016** | Candidate continues **17.088435374 frames** beyond time-mapped original sample |
| First nonzero frame after silence | **1,323,001** | **1,439,984** | Candidate begins **17.088435374 frames** before time-mapped original sample |

The last source frame maps to **1343998.911564626** on the 48-kHz grid. The next source first frame maps to **1440001.088435374**. Both offsets are about **0.3560 ms** at 48 kHz. Their equality in absolute frame time is **compatible with finite temporal support of the open candidate resampling filter**, but does **not** identify the proprietary resampling kernel, latency or internal 48-kHz input.

The intervening zero bridges contain **88,201** exact-zero original 44.1-kHz source frames and **95,967** exact-zero open 48-kHz frames. This is a categorical support test, not a bitwise numerical comparison of two different sample rates.

## Separate non-silence residual pocket

In all three Stage111 preselected 200-frame windows around the secondary `[1488000,1488200)` GT1 pocket, both the original source PCM16 and open candidate input are **continuously nonzero**:

| 48-kHz window | Original 44.1-kHz nonzero / total (covering source frames) | Candidate f64 nonzero / total | Source normalized RMS | Candidate f64 RMS |
|---|---:|---:|---:|---:|
| `[ 1487800, 1488000 )` | 184/184 | 200/200 | 0.010945069 | 0.010944033 |
| `[ 1488000, 1488200 )` | 184/184 | 200/200 | 0.004399145 | 0.004395779 |
| `[ 1488200, 1488400 )` | 185/185 | 200/200 | 0.010125999 | 0.010130670 |

This corroborates Stage111/112's **32 GT1** errors in the active 200-frame pocket without conflating them with the first hotspot's exact-zero candidate input after 1,344,016. Source RMS agreement between these two differently sampled waveforms is descriptive; it does **not** authenticate the closed Sonicake resampling/intermediate input.

## Falsifiability, privacy and next gate

- Stage111's **408** primary GT1 events after candidate-DI cessation remain true; Stage113 now independently anchors the 44.1-kHz source cessation, showing the additional **~17 open-resampler support frames** alone cannot explain >1-LSB discrepancies persisting >1,200 further frames. Such a claim would require a trusted source of vendor pre-NAM samples or deeper independently justified model-state analysis. It could reflect an unknown input path, convolutional/NN memory, PCM conversion or other processing.
- The two observed hotspots cannot be reduced to a single digital-silence cause because the secondary pocket has nonzero original 44.1-kHz PCM and candidate 48-kHz DI throughout.
- **Unverified:** actual vendor-loaded model bytes, actual Manager-internal 48-kHz DI/resampler output, original float/pre-quantized NAM output provenance, native gain/quantizer and fitter, generated CLO parity and hardware readback. Nothing changes production code.
- **Next decision (not built or run):** compare trustworthy **vendor-internal** 48-kHz DI / immediate NAM input against the pinned candidate, if a native capture can be specifically authorized and safely obtained. Without that independent evidence, do not claim source identity, redesign the resampler, or derive proprietary state changes from post-hoc output residuals.

Full source-boundary indexes and source-to-report digest checks are preserved only in the ignored private Stage113 JSON backed up to the user's designated `RE_HTKPA` Drive folder. The public evidence is an aggregate derived summary.