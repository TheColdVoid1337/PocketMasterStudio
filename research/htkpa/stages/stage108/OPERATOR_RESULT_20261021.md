# Stage108 — real operator fixed 0.31 PCM16 comparison (2026-10-21 Bangkok)

**Real operator:** `STAGE108_OFFLINE_FIXED_GAIN_PCM16_OUTPUT_TEST_COMPLETED` after `git pull --ff-only` and **16/16 targeted unit tests PASS**. This is operator-terminal evidence from the SHA-gated original Stage97 Manager PCM16 WAV and existing Stage102 open NAM Core f64, no fresh NAM, Manager or proprietary DLL inference. The assistant inspected the public Stage108 comparator but has not independently read the original private WAV/f64 or full `stage108_fixed_gain_pcm16_private.json`.

## Fixed 0.31 then nearest-even signed PCM16

Per-sample candidate `clamp_s16(round(0.31 * open_f64 * 32768.0))`. Error sign in Stage108 implementation is **candidate_pcm16 − vendor_pcm16**; no sample lag, DC/gain adjustment or clipping observed.

| Group | Frames | Exact PCM16 | Within ±1 LSB | Mean abs error LSB | Mean signed error LSB | RMS error LSB | Max abs LSB |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full fitter [300k,1.5M) | 1,200,000 | 400,362 (33.3635%) | 55.92625% | 3.388025 | +0.430611667 | 6.268795 | 78 |
| Early [300k,1.1M) | 800,000 | 152,991 (19.123875%) | 33.9605% | 4.889345 | +0.4556475 | 7.664186 | 78 |
| Late [1.1M,1.5M) | 400,000 | 247,371 (61.84275%) | **99.85775%** | 0.385385 | **+0.38054** | 0.643331 | 27 |
| Seven zero-DI bins | 140,000 | **140,000 (100%)** | **100%** | 0 | 0 | 0 | 0 |

**Nonzero-DI correction:** four silent 20k bins (80,000 frames) are inside early and three (60,000 frames) inside late. Removing their exact matches, the early nonzero-candidate-DI group is **72,991/720,000 ≈10.1376389% exact**; late nonzero-candidate-DI is **187,371/340,000 ≈55.1091176% exact**. These percentages are derived from exact integer counts; they were not separately printed by Stage108.

Other controls on the **whole fitter window**:
- `gain=0.3098390026147448` **fitted from this very target** via Stage103 yielded **30.956833% exact**, worse than fixed 0.31's 33.3635%. Not independent gain evidence.
- Candidate rounding: `nearest_even=33.3635%`, `nearest_away=33.3635%`, `trunc_toward_zero=32.75525%`. Equal nearest variants do not distinguish midpoint behavior without samples at exact ties.
- `candidate_clipped_frames=0` in all printed groups. No final implementation/quantizer parity established.

**Strong sign-asymmetry clue:** Within the late group the predicted-minus-vendor **mean signed error +0.38054 LSB** almost equals the **mean absolute error 0.385385 LSB**. Per-sample integer-error algebra implies the total magnitudes of negative discrepancies sum to `(0.385385−0.38054)*400000/2 = 969` LSB over 400,000 frames, while positive discrepancy magnitudes sum to `(0.385385+0.38054)*400000/2 =153185` LSB. This is an association with a one-sided *candidate quantization* bias, not proof of a particular rounding algorithm. The Stage108 controls **did not test floor-to-negative-infinity (`math.floor`)**. Its inclusion is a higher-information next gate than rerendering NAM or changing DSP blindly. The near-all within-1-LSB late result should not be misread as exact bit parity.

**Provenance boundary:** Real vendor input DI float32 equals decoded original 44.1k PCM16 exactly, but Sonicake's proprietary resampler 44.1→48k, loaded model bytes, true origin of saved output WAV, gain implementation and PCM16 quantizer are unverified; proprietary FIR fitter numeric parity, device and generated CLO are not established. Production unchanged; raw/vendor data remain in ignored private paths.

**Next bounded test:** on the existing SHA-gated original 48-kHz Manager WAV and Stage102 f64 output, compare `floor(0.31*open*32768)` to nearest-even, truncation, and `ceil` in the **late nonzero-DI group**, independently for positive and negative signs. Print exact-match fraction, predicted-vendor integer residual sign histogram, and maximum error. A floor candidate could explain the predominantly positive nearest-even differences, but this is **unverified until tested**. Avoid assuming native gain 0.31 or that the vendor uses floor.
