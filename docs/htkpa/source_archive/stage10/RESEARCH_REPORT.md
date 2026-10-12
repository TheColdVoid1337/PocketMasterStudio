# Sonicake HTKPA — Stage 10: source-confirmed cross-spectral objective

**Date:** 2026-10-12. **Method:** static disassembly of user-provided `5868USB.dll` only. The library is **never executed**. SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, x64 image base `0x180000000`. No changes to the original NAM files, proprietary WAVs, the existing browser converter or any physical Pocket Master slot.

## Central result: meaning of the mystery 512-point score is now identified

Stage 9 had proved that the 512 values were interpolated onto a **80–10,000 Hz Mel-uniform query grid** and assessed via

`E = (1/512) ∑_{j=0..511} abs(logf(v[j] + 2^-23))`.

It did **not** identify the two source curves passed to `0x1800B5D00`. Stage 10 traces both source outputs of the immediately preceding `0x1800B82B0`, including the calling convention, DSP operands, FFT-style complex accumulation and final arrays. They are:

1. `a[k] = k × sample_rate / N` — **linear frequency knots**, in Hz (not Mel; only the following *interpolator's queries* are on the Mel scale).
2. `b[k] ≈ |S_AB[k]| / (S_AA[k] + 2^-23)` — **cross-spectral transfer magnitude** between two audio buffers A and B, normalized by the auto-spectrum of the **first** signal A. Here `S_AA = Σ_w (A_re² + A_im²)`, and `S_AB = Σ_w FFT(A) × conj(FFT(B))` or its complex conjugate; the sign convention for the imaginary part does not affect the magnitude. `Σ_w` runs over the function's windowed work frames.

`0x1800B5D00` then evaluates `b(a)` at the 512 Mel-distributed Hz queries to obtain `v[j]`. The 512-element score therefore measures the logarithmic deviation of a **frequency-domain transfer ratio from unity**. It does **not** directly score 512 FIR taps.

This is not a guess based on output CLO timbre: the division, complex products, square root, frequency generation and pointer transfer are all visible in the supplied DLL.

## Operand provenance from exact machine addresses

| Meaning | DLL virtual address and code evidence |
| --- | --- |
| First input A | `0x1800BC399`: `rdx = r15`, the fitter's current generated audio. `0x1800BC368`/`0x1800BC381` invoke `0x1800B5A30` with `r9=r15` as destination beforehand. Inside `0x1800B5A30`, `0x1800B5A87` saves destination `r9`; `0x1800B5C11..0x1800B5C15` forwards that destination through the copy helper. |
| Second input B | `0x1800BC391`: `r8 = [rsp+0x1B0]`, the fitter's original third argument. The HTKPA dispatcher at `0x1800BF0B6/0x1800BF0C9` selected that signal from the paired captured reference window. The exact modeling of onset-alignment offsets was already documented in Stage 8. |
| Spectral estimator call | `0x1800BC3BB..0x1800BC3C5`: prepares sample rate, sample length and separate pointers for frequency `a[]` and transfer magnitude `b[]`, then calls `0x1800B82B0`. |
| Hamming weighting | `0x1800B83CA..0x1800B83DC`: `0.54 − 0.46 cos(2πn/(N−1))`, applied after local mean removal. |
| Frame hop | `0x1800B83F3..0x1800B83FB`: integerized `0.5 × Fs` — **about 0.5 seconds** between work-frame starts. Last-window clamping uses a separate termination guard; not assumed to be a plain default STFT. |
| Frame FFT-style transform | `0x1800B8E38` and `0x1800B8E55`: separate calls to `0x1800289D0` for the two windowed input buffers, producing real/imaginary arrays. The precise library transform normalization/rounding is not reconstructed. |
| Auto power `S_AA` | `0x1800B901E..0x1800B9030`: multiply two real/imag arrays by themselves, add, accumulate into auto-power array. |
| Cross spectrum `S_AB` | `0x1800B903E..0x1800B9066`: multiply first/second real/imag arrays; add components for real, subtract components for imaginary; accumulate both into separate complex arrays. |
| Absolute cross spectrum | `0x1800B9548..0x1800B9551` and scalar tail `0x1800B97EF..0x1800B9805`: `sqrt(C_re²+C_im²)`. |
| Divide by auto power | `0x1800B9554..0x1800B955F` (and scalar tail `0x1800B980F..0x1800B9817`): `|C|/(P+epsilon)` stored to ordinate output. Epsilon is an explicit float32 `2^-23` at `0x18024D110` / `0x18024C4D4`. |
| Frequency knots | `0x1800B9564..0x1800B957B` and `0x1800B981D..0x1800B9832`: `k/N × Fs` stored to abscissa output, `N/2+1` bins. |
| Mel interpolation | `0x1800BC3D2..0x1800BC3F9` calls previously proven `0x1800B5D00` with knot arrays and context's 512 Mel-spaced Hz queries. |
| Score on predicted ratio | `0x1800BC410..0x1800BC440`: read output of interpolation and accumulate `mean(abs(logf(value+2^-23)))`. |

**Important distinction:** `0x1800B82B0` uses *linear frequency bins*. Only `0x1800B5D00` resamples that curve onto the **Mel query grid** discovered in Stage 9. The input curve `b[k]` is a transfer estimate using a complex cross spectrum (coherence-sensitive), not an arbitrary power-spectrum or direct ratio of amplitudes.

## Consequence of this specific objective

For a *synthetic* broadband input A where B is exactly `g×A`, the cross-spectral transfer ratio tends toward `abs(g)` at well-energized bins and the score is lowest when `g≈1`. A pure *phase delay* can leave the magnitude nearly unchanged while shifting the impulse response; this objective alone does **not** establish waveform phase or perceptual timbre equality. Nor does a true cross-spectrum quotient always equal the spectrum magnitude quotient in noisy/nonlinear regions.

This clarifies why Stage 9's optimization control prefers a curve near one: **the current emulated output is being compared with the target output by a frequency-dependent transfer ratio**. Exactly how the optimizer changes Pre-FIR, Post-FIR and the nonlinear parameters to reduce this score is the next missing part.

## Verification

The Python script `verify_stage10.py` is read-only and SHA-pinned. It checks **51 exact instruction addresses** across the call chain, **five literal PE constants**, and **eight standalone synthetic tests** of Hamming symmetry, work-frame spacing, frequency knot count, amplitude gain, cyclic phase shift and log score. The verifier was run **twice against the original DLL** with byte-identical `evidence.json` outputs. These tests show that the clean-room *scalar equations are internally consistent*; they do **not** show bit-exact reproduction of the native FFT estimator or any official FIR. Captured NAM/WAV/CLO, proprietary binaries and existing research files are intentionally omitted from the release ZIP.

## Acceptance / future strict source-first work

**Not yet met:** generating a complete Sonicake Pre-FIR or Post-FIR coefficient vector from the original input/output NAM pair. This Stage 10 identifies the actual **score function inputs and signal roles**, but not the candidate filter update equations.

**Next Stage 11 target:** static trace of `0x1800BB440..0x1800BBB5B` and the two `0x1800B7670` invocations at `0x1800BB4D9/0x1800BB4F8`, as well as `0x1800B68F0`, determining where power-law corrections are applied and how both FIR buffers change. Confirm the exact buffer and mathematical semantics *before* coding an optimizer or exporting a CLO. Keep `JCM800 2203 v0.2 C` as a user-accepted audio reference; no changes to default Void Mod until tested on multiple NAMs.
