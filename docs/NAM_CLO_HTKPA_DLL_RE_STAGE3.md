# Sonicake HTKPA reverse engineering — Stage 3 (2026-10-12)

**Static research only.** This work analyzes the user's Windows Sonicake Manager `5868USB.dll` (SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`) without executing it. Virtual addresses assume PE64 image base `0x180000000`. The binary, vendor WAV/CLO captures and proprietary inputs are **not distributed or committed**. Production JS-only Void Mod is **unchanged**.

This stage follows `0x1800BB210` (the three-selector fitting dispatcher calls this repeatedly) and `0x1800B9B70`, plus helpers `0x1800B82B0`, `0x1800B4CF0`, and `0x1800B52E0`.

## Confirmed local mathematics

1. **Iterated power-law correction** in `0x1800BB210`. A call to imported `powf` at `0x1800BB46E` computes `powf(base[i], exponent_scale * q[i])` and clamps output to **[0.2, 5]** (`0x1800BB479`, `0x1800BB48C`). The scalar exponent scale is multiplied by **0.9** in the iteration (`0x1800BB4BE`; constant VA `0x18024C654`). The procedure multiplies/divides per-element arrays (`0x1800BB575`, `0x1800BB6E1`), invokes convolution/filter helpers, applies the original asymmetric exponential saturator `0x1800BE700` at `0x1800BBCC9`, and invokes `0x1800B82B0` **twice** (`0x1800BC055` and `0x1800BC3C5`). **Exact state-array identities and the complete update rule remain unresolved.**

2. **512-element logged metric** at `0x1800BC410..0x1800BC440`: `mean(abs(logf(v[i] + 2^-23)))` over 512 values. The bound `0x200`, `logf` import, absolute-value mask, and multiplier `1/512` (`0x18024C4F0`) are explicit. The *source* of this array has not been proven: its length matching the pedal's transmitted 512 Post-FIR taps is **not enough** to identify it with those taps.

3. **Exact Hamming window** in `0x1800B82B0`:
   `w[n] = 0.54 - 0.46*cos(2*pi*n/(N-1))`.
   Direct assembly: cosine `0x1800B83CA`, multiply by 0.46 `0x1800B83CF`, subtract from 0.54 `0x1800B83D8`. Coefficients at `0x18024C5B0` (0.46), `0x18024C5D4` (0.54), and `0x18024CCF0` (2π). It remains to be shown exactly how this taper feeds the final CLO filters.

4. **Spectral magnitudes and regularized ratio** inside `0x1800B9B70`. Consecutive `(re,im)` pairs are converted by `sqrtf(re² + im²)`, including `0x1800BA97B`. The ratio code near `0x1800BAC70..0x1800BAD2E` has local scalar form:
   `r[k] = 1e6 * M_a[k] / (1e6 * M_b[k] + 2^-23)`,
   explicitly clipped to **[0.1, 10]** (`0x1800BAEB3`, `0x1800BAEC6`). Exact assignments of `M_a` and `M_b` to full pipeline buffers, and their later normalization, **are not yet known**. Further output balancing computes RMS-like squared-energy ratios (`0x1800BB010..0x1800BB0E2`).

5. **Sample-rate-dependent temporary support** near `0x1800B9BCB` is `ceil(0.1*sample_rate)` (~4410 at 44.1kHz, 4800 at 48kHz). This does **not** identify a final output filter length. The routine also has cosine tapering near `0x1800BA820`, complex-data processing via `0x1800B4CF0`, and trigonometric basis generation in `0x1800B52E0`. The complex helper uses modulo indexing and real/imaginary cross-terms, consistent with circular complex convolution.

## Significance and limits

Stage 3 supports a **multi-stage adaptive, frequency-domain nonlinear fitting** interpretation of official Windows HTKPA, beyond a single linear Post-FIR refit. In particular, Sonicake's local DSP includes Hamming tapering, bounded spectral gain, a 512-element logged control/score, and exponent annealing. These are concrete new avenues for reproducing its sound in a clean original implementation.

**Not yet proven:** exact 128-tap Pre-FIR and 2048-tap Post-FIR design equations, transform scaling/order, intermediate buffer-to-CLO mapping, vendor-matched coefficients, bit-exact CLO output, equivalence to mobile SONICLINK, or improved sound on hardware. Do not put partial formulas into production. The well-received JCM800 2203 v0.2 C remains the controlled reference; v0.3 automatic shelf remains unvalidated on real hardware.

## Reproducibility

The separate conversation research artifact `Sonicake_HTKPA_DLL_RE_Stage3_v0_3.zip` contains `verify_stage3.py`, evidence JSON, standalone Python scalar primitive reproductions, **five passing unit tests**, and a detailed technical report. The verifier matched **31 exact assembly instruction locations**, four math imports (`powf`, `logf`, `sqrtf`, `cosf`) and eleven pinned constants. Independent consecutive invocations yielded identical evidence JSON; the ZIP integrity check passed.

Next: trace `0x1800B82B0` output pointers through `0x1800B5D00` and `0x1800B7E10` → `0x1800B65A0` → `0x1800B5A30` into the serializer; then numerically test predicted FIR coefficients against *both* existing matching official Windows Manager CLOs. Only after a numeric coefficient validation should a JS-only experimental pathway be considered.
