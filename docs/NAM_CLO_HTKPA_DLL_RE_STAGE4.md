# Sonicake HTKPA — Stage 4: FIR output and resampling trace

**2026-10-12 · Verified partial result, not a completed FIR reconstruction.** This stage statically examines the user-provided Windows Sonicake Manager `5868USB.dll` (SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`). No proprietary binary has been executed or redistributed, no hardware slot written, and the production browser-only JS converter remains unchanged.

## Newly established data flow

- **Working FIR pointers:** `context+0x24408` holds the 128-tap Pre-FIR input buffer; `context+0x24410` holds the 2048-tap Post-FIR input buffer. The latter is explicitly zeroed and initialized to a unit impulse `(1,0,0,...)` at `0x1800bed4a..0x1800bed5d` prior to fitting.
- **Fitting:** three differently configured calls to `0x1800bb210` (`0x1800bf0c9`), followed by the spectral finishing function `0x1800b9b70` (`0x1800bf11e`). Both working FIR pointers are provided to the optimizer; the spectral finalizer receives the post-FIR destination pointer.
- **Final buffer construction:** calls `0x1800c0d40` at `0x1800bf135` for Pre-FIR and `0x1800bf14f` for Post-FIR; later calls `0x18000ce00` at `0x1800bf364` and `0x1800bf47f` for sample-rate conversion.
- **Target sample rate** is **44,100 Hz** (float32 constant at `0x18024cdf0`). `0x18000d031..0x18000d043` calculates an integer output length by truncating `input_length × target_rate / source_rate`.
- **Packing:** destination tap regions are zero-initialized, and only the rate-converted values are copied into the declared 128/2048-tap VTSI/CLO. Final header and CRC are computed at `0x1800bf4df..0x1800bf542`.

The paired Sonicake Manager NAM-output WAV is 48 kHz. At **48 → 44.1 kHz**, the calculated output supports are **128 → 117** and **2048 → 1881** taps.

## Numerical comparison of actual source-matched CLOs

We verified both the official Windows Manager CLO and the baseline Void CLO, for both matching NAMs. **All four** contain 117 consecutive nonzero Pre-FIR samples followed by 11 zeros, and 1881 consecutive nonzero Post-FIR samples followed by 167 zeros. Thus **the production Void path already exhibits this resampling signature**. It cannot, by itself, account for the audible difference.

Cosine similarity of raw tap vectors (no delay, polarity or amplitude compensation):

| Same-NAM pair | Pre-FIR cosine | Post-FIR cosine |
| --- | ---: | ---: |
| JCM800 2203 Crunch | 0.0174 | -0.1932 |
| SC20 Full Rig | 0.7966 | -0.0311 |

These values are **not perceptual scores**; coefficient phase and latency can strongly affect raw cosine. They do establish that identical container layout and sample counts do **not** imply numerically matching filter taps.

## Acceptance status: **NOT MET**

The Stage 4 objective was to independently calculate at least one complete official FIR from NAM/WAV and match the vendor coefficients. **That has not been achieved**. We have proven the final memory-pointer chain, rate conversion, padding and serialization, not the complete upstream fitting equations or the exact interpolation kernel.

**Remaining concrete target:** trace the outputs of `0x1800b82b0` and the data passed to `0x1800b5d00`/ `0x1800b7e10` and `0x1800b9b70`; reconstruct the complex-spectrum phase convention, inverse transform and normalization into `context+0x24408/0x24410`; then independently generate every nonzero target coefficient (117 Pre or 1881 Post) from a matching reference pair. Matching zero padding or frequency-band averages alone does not satisfy this criterion. Also reconstruct the exact resampling interpolation if byte-level equality is necessary.

## Reproducible verification

The separate research bundle `Sonicake_HTKPA_DLL_RE_Stage4_v0_4.zip` contains:

- `verify_stage4.py`: read-only static verifier with **23 exact instruction checks**, DLL SHA256 pinning, float32 sample-rate constant, CLO VTSI/CRC16 checks, and both official/Void cross-comparisons.
- `static_validation.json`: recorded results for four user-supplied CLOs, with hashes and tap statistics (no proprietary audio or code).
- `RESEARCH_REPORT.md`: source addresses, methods, limitations and next trace targets.

The analyzer checks source CLOs without modifying them; ZIP integrity was verified. Neither the DLL, vendor intermediate audio nor commercial captures are included in the research archive or GitHub.

**Preserve the well-auditioned JCM800 2203 v0.2 C as a subjective hardware reference. Do not change default fitting or introduce generic +gain/HF boosts based on this finding.**
