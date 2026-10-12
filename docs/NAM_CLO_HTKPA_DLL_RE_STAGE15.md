# Sonicake HTKPA Stage 15 — feedback ratio and final Post-FIR correction

**2026-10-12 · Source-first static research only. No production converter edits, DLL execution, new CLO, or device writes.**

Analyzed the user-supplied Windows Sonicake Manager `5868USB.dll` (SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`). All addresses are PE virtual addresses with image base `0x180000000`. The proprietary DLL and corresponding NAM/WAV/CLO captures are **not redistributed or committed**.

This stage addresses the two explicit Stage 14 unknown blocks: `0x1800BC055→0x1800BC33D` and final `0x1800B9B70`.

## 1. Cross-spectral feedback: regularized quotient and working Post-FIR synthesis

The optimizer at `0x1800BC055` invokes the previously traced cross-spectral evaluator `0x1800B82B0`. A vectorized double-precision path (`0x1800BC10D/0x1800BC114/0x1800BC118/0x1800BC11C`) and scalar equivalent (`0x1800BC222/0x1800BC226/0x1800BC22A/0x1800BC22F`) compute the following *local* quotient, storing float32:

```
Q[i] = float32(1_000_000.0 * float32(A[i]) /
               (1_000_000.0 * float32(B[i]) + 2**-23))
```

The multiplier `1000000.0` and epsilon `2^-23` are **double** constants at `0x18024D5A0` and `0x18024D1E0`, respectively. The effective unscaled denominator epsilon is approximately `1.19209e-13`. This is **not** the Stage 7 experiment's arbitrary adaptive Welch estimator regularizer.

The quotient output is passed through the source-confirmed Mel/dB/Gaussian curve conditioner `0x1800B7670` at `0x1800BC33D`, then the shared minimum-phase-like `0x1800B68F0` at `0x1800BC35C`, with destination `context+0x24410` (working **Post-FIR**) and the correct 2048 target length.

**Precision boundary:** The arithmetic and several source/destination pointers are directly established. Exact origin and aliasing of **every** intermediate scratch array `A/B` and the full pre/post update equation are not yet recovered. Naming A and B does not identify them with raw STFT power arrays in isolation.

## 2. Once-only final Post-FIR spectral correction

After three calls to the main fitter, `0x1800BF100` passes `context+0x24410` and `0x1800BF11E` calls `0x1800B9B70`.

The finalizer:

1. Uses a support of `ceil(0.1*sample_rate)` (`0x1800B9BCB–0x1800B9BD5`) — 4800 samples at 48 kHz.
2. Builds rendered/reference audio spectra, using two transforms (`0x1800BA8A3`, `0x1800BA8BB`) and `sqrtf(re²+im²)` (`0x1800BA97B`). The complete upstream complex-array orientation is not yet byte-exact.
3. Forms the same class of `1e6 * numerator/(1e6 * denominator+2^-23)` ratio (`0x1800BAC70–0x1800BAD2E`), clamps it to **[0.1, 10]** (`0x1800BAEB3/0x1800BAEC6`), and Gaussian smooths via `0x1800B7E10` (`0x1800BAEF9`).
4. Calls `0x1800B65A0` at `0x1800BAF88` to create and apply a **256-tap corrective filter to the existing Post-FIR**.
5. Rerenders audio through the corrected Post-FIR (`0x1800BAFAB`) and obtains a **ratio of square-root summed energies** (`0x1800BB0C0/0x1800BB0CB/0x1800BB0E2`). It multiplies the Post-FIR by that factor (`0x1800BB12F`).

## 3. Exact structure of `0x1800B65A0`: causal convolution, cropping and DC subtraction

- Allocates two **256-float** scratch arrays (`0x1800B65B8/0x1800B65CC`).
- Conditions the transfer curve to 256 bins (`0x1800B65FD`) and synthesizes a **256-tap FIR** via `0x1800B68F0` (`0x1800B6621`).
- Allocates `PostFirLength + 255` floats, initializes them to zero and performs a nested multiplication/accumulation loop (`0x1800B6690–0x1800B675D`) consisting of **256 inner taps per old Post-FIR tap**.
- Copies **only the first PostFirLength** convolution outputs back into the existing Post-FIR (`0x1800B6771`) and subtracts their mean (`0x1800B67EA/0x1800B682B/0x1800B68B0`).

Independent *algebraic* model for normal non-degenerate arrays:

```python
corrector = synthesize_256(conditioned_spectral_curve)
full = causal_convolution(working_post_fir, corrector)
working_post_fir[:] = full[:len(working_post_fir)]
working_post_fir -= mean(working_post_fir)
# Outer function subsequently applies energy ratio
```

This is **not** a direct 2048-tap recomputation: it corrects the already fitted filter by convolution, and then output-energy calibration. Exact float32 summation order and all native edge cases remain unverified.

## Independent file consistency check (not parameter fitting)

The user-provided official Windows Manager CLOs have **near-zero** sums of their 2048 Post-FIR coefficients, consistent with the identified DC subtraction prior to 48k→44.1k conversion:

| Model | Official Post-FIR sum | L2 norm |
|---|---:|---:|
| JCM800 2203 Crunch | 0.002959 | 1.170528 |
| JCM800 SC20 Full Rig | 0.006035 | 1.922987 |

## Verification and original acceptance gate

The separately supplied `Sonicake_HTKPA_DLL_RE_Stage15_v0_15.zip` includes independently authored `verify_stage15.py`, this stage's full research report, README and JSON evidence. The verifier statically checks **46 exact machine-code addresses, eight binary constants, and 13 synthetic mathematical tests** covering regularized quotient, causal/truncated convolution, DC and energy gain. Two runs yield identical JSON: SHA-256 `5c5f236c0bc6ec5fad5b9e6418d36aafa00b7845c05c4070faeddc3d6c7c4802`. Zip integrity passed.

**Two Stage 14 blocks now have verified core operations and data flow, but the original strict objective — calculating official 128-tap Pre-FIR / 2048-tap Post-FIR from only the NAM and probe WAV, with numerical coefficient parity — is STILL NOT MET.** In particular, optimizer `0x1800BB210` scratch-buffer provenance / three-stage update, entire native DSP fit loop, transform numeric parity and exact rate conversion remain unfinished.

**Next source-first gate:** full register/stack SSA of `0x1800BB210` covering the `2→1→3` loops and `0x1800BC055` feedback buffer identities, then a self-contained synthetic input-to-working-Pre/Post-fit test, and *only then* a two-model coefficient match. No guess-based CLO production or unconditional +gain/brightness.

Keep the user-auditioned JCM800 2203 v0.2 C as hardware control. Mobile SONICLINK vs Windows Manager exact parity remains unproven.
