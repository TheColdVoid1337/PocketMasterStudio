# Sonicake HTKPA Stage 18 — Audio-conditioned initialization and complete ordinary-domain frequency-curve conditioner

**2026-10-12 | Source-first static analysis and independent synthetic tests | Research only.**

Original PE: user-supplied `5868USB.dll`, pinned SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. All disassembly addresses use image base `0x180000000`. The DLL was **never loaded/executed**. No proprietary binaries or reference NAM/WAV/CLO files are included. No pedal operations, new CLO, or edits to production PocketMasterStudio JavaScript took place.

## Core correction to Stage 17: `0x1800BC6B0` initializes A/B from **audio**

Stage 17 correctly located the function called by the outer driver at `0x1800BEE89`, but its brief description as a mere initializer obscured substantial processing. The source makes the following sequence explicit:

- At `0x1800BEE25`, outer `0x1800BE830` calls **`0x1800BD490`**, which produces an independently preprocessed float32 audio buffer.
- At `0x1800BEE33/0x1800BEE3F/0x1800BEE4B`, it allocates the persistent **A**, **B**, and frequency coordinate arrays, respectively. Their output pointer arguments are set at `0x1800BEE58/0x1800BEE53/0x1800BEE4E`.
- At `0x1800BEE89` it calls **`0x1800BC6B0`** to fill them, *before* selectors `2→1→3` run. `0x1800BC6B0` conditionally loads sample-rate-dependent coefficient arrays from the PE at `0x1800BC753...0x1800BC940`, processes a 50-point group via `0x1800B5A30` (`0x1800BC96D`), runs **two second-order filter sections** with state in context fields `+0x20/+0x28/+0x30` and `+0x20c98/+0x20ca0/+0x20ca8`, and applies a scalar nonlinear map `0x1800BE700` at `0x1800BCC79`.
- The processed audio enters the already recovered cross-spectral evaluator **`0x1800B82B0`**, at `0x1800BCFF2`, which writes the working spectral curve and coordinate array.
- Two successive Gaussian operations are called at **`0x1800BD01F`** and **`0x1800BD03D`**, with exact widths:

  ```text
  width_1 = trunc(spectral_length * 0.001)
  width_2 = trunc(spectral_length * 0.005)
  ```

  The constants `0.001` and `0.005` are doubles at `0x18024C618` and `0x18024C688`. The first smoothing writes a temporary array, and the second writes the B curve.

### Exact final part: parabolic spectral floor and A/B initialization

Let `U` be the already-prepared auxiliary array and `Braw` the spectrum after the two Gaussian calls. The DLL computes (ordinary finite/nonnegative domain):

```text
T      = float32(max(U) * 0.001)
cap    = float32(2*T)
alpha  = float32((cap-T) / (cap*cap))   # = 1/(4*T), ignoring float32 rounding

for k in range(spectral_length):
    B[k] = float32(T + Braw[k]*Braw[k]*alpha) if Braw[k] < cap else Braw[k]
    A[k] = float32((1e6 * float64(U[k])) / (1e6 * float64(B[k]) + 2**-23))
```

- Source for threshold and quadratic: `0x1800BD0B7..0x1800BD119` and vector/scalar siblings, especially compare `0x1800BD105`, quadratic `0x1800BD10D/0x1800BD111` and write `0x1800BD119`.
- Ratio: `0x1800BD230..0x1800BD2E5` vector and `0x1800BD350..0x1800BD441` scalar; double constants `1e6` and `2^-23` at `0x18024CD28` and `0x18024C588`.
- Mathematical invariant **independently tested**: at `Braw=0`, B becomes T; at `Braw=2T`, the parabola yields 2T and joins the identity with slope 1. The result is a *smooth spectral floor*, not a hard clamp, when T>0.

**What is NOT yet traced:** full data provenance and native numerical results from both audio preprocessing paths (`0x1800BD490`, `0x1800B5A30`, `0x1800BE700`, and `0x1800B82B0`) for a real input/reference WAV. Do not assume the auxiliary curve `U` is a raw simple Welch power spectrum. Although A/B destinations are known, the two preprocessed audio paths must be reproduced to obtain the correct arrays from the user's real WAV.

## Complete algebraic ordinary-domain `0x1800B7670` pipeline

This stage now provides `conditioned_curve(freq,mag,target_count)` in `stage18_source_first.py`. It implements *all visible mathematical stages* of the frequency-curve conditioner for finite positive gains and strictly increasing input frequencies with `source_count >= 501`, `2 <= target_count <= source_count`. It is a **source-directed algebraic reconstruction, not yet native float32/bit-exact**. The exclusions are deliberate; unproven zero-width and repeated-knot paths are not guessed.

1. Convert source endpoints Hz→Mel using the PE's 700, 2595, 10 and `log10f`, then create **Mel-uniform arrays** at the original and target counts with `0x180027DB0` (source locations `0x1800B77D4` and `0x1800B7917`). Its float32 `linspace` repeatedly adds the step and **overwrites the last element with the requested endpoint** (`0x180027E4E`).
2. Invert Mel to Hz for both arrays (`0x1800B7860/0x1800B78D0`) and explicitly restore frequency endpoints for the source grid (`0x1800B7909/0x1800B7912`). Construct a separate *linearly spaced Hz* target array (`0x1800B7A95`).
3. Convert the source magnitudes to **`20*log10f(g)`**, then apply **Gaussian pass 1**, width `trunc(0.002*source_count)` (`0x1800B7BAB`, `0x1800B7BBB`).
4. Interpolate source linear-Hz curve onto source-count Mel-Hz grid using `0x1800B5D00` (`0x1800B7BF8`). Apply **Gaussian pass 2**, width `2*trunc(source_count/target_count)` (`0x1800B7C07/0x1800B7C12`).
5. When target count differs, interpolate across Mel coordinates from source-count to target-count (`0x1800B7C4B`); otherwise directly copy (`0x1800B7C52..0x1800B7C5B`).
6. Interpolate target-count Mel-Hz ordinates onto final linearly spaced Hz axis (`0x1800B7C8C`), then convert **`g=10**(dB/20)`** (`0x1800B7CCE/0x1800B7D1C`).

The Gaussian helper `0x1800B7E10` uses weights `exp(-0.5*((i-ceil(W/2))*5/W)**2)` on `i=1..W`, scales/reverses them with total `1e6`, adds a padded zero for even widths and renormalizes truncated boundary windows. This stage tests odd and even kernels, preservation of constant inputs, and the native-style repeated-addition frequency grid. Its intermediate arrays and rounding should **not** be conflated with a byte-exact port: native CRT, SSE vector math, and interpolation edge semantics remain to be compared.

### Practical synthetic test: 2401 input bins → 128 and 2048 output values

`demo_stage18.py` produces two distinct **synthetic** positive arrays and passes them through the source-directed double-Gaussian initialization and complete conditioner.

| Test output | Target length | Conditioner Gaussian widths | Result |
|---|---:|---:|---|
| Synthetic A→Pre frequency curve | 128 | `4,36` | finite, positive 128-element float32 output |
| Synthetic B→Post frequency curve | 2048 | `4,2` | finite, positive 2048-element float32 output |

These are *spectral curves*, **NOT 128/2048 FIR tap coefficients and NOT converted NAM models**. In addition to these integration exercises, a flat unit gain curve passes through both target sizes with no meaningful alteration; knotwise affine interpolation and symmetric/asymmetric odd/even Gaussian cases are tested independently.

## Verification, exact constraints, and next gate

- **59 pinned DLL instruction locations**, **12 binary constants**, **49 standalone mathematical tests** passed on the original SHA-pinned DLL. Two verification runs produced **byte-identical evidence** with SHA-256 `c334edaaede0db5200c6d60b8010e10519028ee3261729190861dc6dea7c1775`.
- Generated synthetic example has been validated for 128 and 2048 outputs; the test code does not write a CLO, does not reuse vendor Post/Pre taps, and does not execute or bundle the DLL.
- The user-provided official 2203/SC20 CLO files remain **validation-only**; we deliberately return **`NOT_TESTED` for coefficient parity** because no correct independent real-NAM Pre/Post candidate has been produced.

**Stage 19 should start inside `0x1800BC6B0`:** trace native audio preprocessing and second-order filters, complete the output buffer attribution of `0x1800B82B0` and its two source waveforms, and reconstruct the sample-rate-dependent coefficient selection using the tables at `0x18024D...`. Then feed a source-valid initialized `A/B` into the already mapped three-pass optimizer. **Only after the first complete candidate passes a two-NAM numerical FIR comparison should we create a pedal CLO or modify production JS.**

There is no claim that Windows Sonicake Manager output exactly equals mobile SONICLINK. Preserve the user-hardware-liked JCM800 2203 v0.2 C reference.
