# HTKPA Stage 21 — complete ordinary-domain four-parameter saturator fitting

**Date:** 2026-10-12. **Scope:** source-first, read-only static RE of the user-provided Windows Sonicake Manager `5868USB.dll`. The proprietary library was **never executed**. No production JS/CLO/pedal operation.

- Pinned DLL SHA256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
- Native fitter VA: `0x1800BDBE0` to `0x1800BE6F6` (PE image base `0x180000000`).
- The **ordinary-domain math inside this specific fitting routine** is reconstructed and independently exercised. Full 48 kHz native preprocessing and four fitted coefficients **from the user's real NAM/WAV** are **NOT YET COMPUTED**.

## 1. Native function interface and four output fields

The enclosing conversion driver `0x1800BEDA3..0x1800BEDE4` passes:

| Win64 argument | Source | Meaning from operations |
|---|---|---|
| RCX | processing context | sample-rate float32 at `+0x20EC0` |
| RDX | outer register R15 | input signal for fitted nonlinearity |
| R8 | outer register RBP | reference/target signal |
| R9D | ESI | sample count |
| stack +0x20 | `context+0x243F8` | **positive output amplitude** |
| stack +0x28 | `context+0x243FC` | **negative output amplitude** |
| stack +0x30 | `context+0x24400` | **positive exponential rate** |
| stack +0x38 | `context+0x24404` | **negative exponential rate** |

All four final stores are verified at `0x1800BE661`, `0x1800BE676`, `0x1800BE682`, `0x1800BE68F`; the two rate outputs receive the winning multipliers first. This agrees with the four nonlinear float32 values serialized at offset 104 in the VTSI CLO.

## 2. Envelope extraction — **directly traced**

The native sample-rate period is `float32(float64(float32(Fs)) × 0.1)`, and native count is `trunc(floorf(float32(float32(number_of_samples) / period)))`. Loop boundaries are computed as `trunc(float32(float32(i) × period))`. For each of the B blocks, three zero-initialized float32 arrays are populated:

```
X[i] = max_t abs(input[t])
P[i] = max(0, max_t target[t])
N[i] = min(0, min_t target[t])
```

The input absolute maximum and target positive/negative extrema use the actual float32 compares at `0x1800BDD80…0x1800BDECD`. Global amplitudes are:

```
pmax = max_i P[i]
nmax = max_i -N[i]
```

**Subtlety:** the IAT target `0x18017E13A` is **floorf**, not ceilf. The last incomplete block is excluded by the full-bin count. We do not extrapolate native behavior when block count is zero or non-finite values occur.

## 3. The previously missing permutation — **recovered**

After the three B-element arrays, the DLL allocates **4B floats**, not 2B. The reordering loop `0x1800BDF47..0x1800BE16C` constructs exactly two new vectors, each length 2B:

```
input_curve  = [-X[B-1], ...,-X[0], X[0], ..., X[B-1]]
target_curve = [ N[B-1], ..., N[0], P[0], ..., P[B-1]]
```

This includes the negative side in reverse order, the positive side forward, and the required sign flip **only** on negative input magnitudes. The transformation has separate vectorized-four and scalar-tail paths; 16 source-address checks cover its allocations and stores. Synthetic odd/even lengths verify the expected ordering.

## 4. Independent least-squares initial-rate estimates — **recovered**

Find the first, **one-based** position in each original envelope array that crosses half the maximum magnitude:

```
Kpos = 1 + first index where P[i] >= 0.5*pmax
Kneg = 1 + first index where N[i] <= -0.5*nmax
```

In double-precision accumulators, with each `X/P/N` element first read as float32:

```
slope_pos = float32(sum_{i<Kpos} P[i]*X[i] / sum_{i<Kpos} X[i]^2)
slope_neg = float32(-sum_{i<Kneg} N[i]*X[i] / sum_{i<Kneg} X[i]^2)

initial_rate_pos = float32(slope_pos/pmax)
initial_rate_neg = float32(slope_neg/nmax)
```

Address proof: threshold comparison `0x1800BE1A0` and `0x1800BE1E0`; OLS numerator and square `0x1800BE259/0x1800BE25D/0x1800BE261/0x1800BE26C`; negative subtraction `0x1800BE361`; divisions and rates `0x1800BE30E/0x1800BE440/0x1800BE462/0x1800BE47A`.

## 5. Two **ordered** 9-candidate SSE searches — **recovered**

Apply the asymmetric saturator to the **2B-element rearranged curves**, not all millions of original samples:

```
sat(x) = pmax*(1-expf(-prate*x))  if x > 0
sat(x) = nmax*(expf(nrate*x)-1)   otherwise
loss = float32 running sum of float32 (target_curve - sat(input_curve))^2
```

Starting from native `float32(0.8)`, after each candidate update the DLL performs **double-precision +0.05, then converts back to float32**. The actual nine tested multipliers are:

```
0.8000000119  0.8500000238  0.9000000358
0.9500000477  1.0000000000  1.0499999523
1.0999999046  1.1499998569  1.1999998093
```

First sweep varies **positive rate only**, keeping negative at its initial estimate. The winning positive rate is then fixed, and the second sweep varies **negative rate only**. A new candidate **replaces the best on equality**, as native comparison is `comiss best,new; jb skip`. The DLL uses `expf` at `0x1800BE4BA/0x1800BE4D5/0x1800BE5AE/0x1800BE5C9`; grid updates at `0x1800BE529/0x1800BE631`. Output parameters are `(pmax,nmax,prate,nrate)`.

**Precision:** the Python implementation explicitly stores rate arithmetic and accumulated error as float32 but uses `math.exp` rounded to float32 as an analog for Windows CRT `expf`; it is an algebraic reconstruction, **not proven bit-exact**. NaN/Inf/zero-denominator and unusual tie cases are outside the accepted ordinary domain.

## 6. Actual synthetic whole-fitter demonstration

Using **two 60-second preprocessed synthetic arrays at 1000 Hz** (purposefully not official WAVs): 600 groups, 1200 rearranged envelope points. Complete real-valued fitter output:

| quantity | observed |
|---|---:|
| positive output amplitude | 0.06396826 |
| negative output amplitude | 0.06865691 |
| positive rate | 17.52926636 |
| negative rate | 15.11242867 |
| score before two sweeps | 0.09264456 |
| score after two sweeps | **0.04071169** |

These fitted numbers do not reproduce the original synthetic generator's coefficients (which used `(0.075,0.09,16,12)`), because the native algorithm sets the asymptotic amplitudes to the **recording's observed maxima** and only searches a ±20% neighborhood around initial slopes. **This is not a claim that the fitting code learns the original neural transfer perfectly**, nor a physical Sonicake listening result.

## 7. Held-out real vendor captures, strictly NOT fitter targets

Read-only independent SHA-pinned references:

| Manager source | official CLO hash prefix | Official-only `(pmax,nmax,prate,nrate)` | From raw NAM/WAV? |
|---|---|---|---|
| JCM800 2203 Crunch | `50f362c39362` | `(0.05869761, 0.06251806, 425.438965, 356.188354)` | **NOT COMPUTED** |
| SC20 Full Rig | `2834c9d3c2dc` | `(0.01061691, 0.01269747, 450.926178, 253.910919)` | **NOT COMPUTED** |

The 70-second source DI is byte-identical between captures. Input DI WAV is 44.1 kHz and output WAV 48 kHz. **The pair passed to `0x1800BDBE0` is not simply raw input and raw vendor output**: it is created by the preceding native preprocessing, sample-rate handling and filtering. Therefore these reference gains were never supplied to the fitter or used to choose formulas. They are only held-out diagnostic targets to evaluate after the input-pair path is implemented.

## 8. Verification, reproducibility, outstanding steps

- Standalone **75** pinned exact native instruction checks, **8** double/float PE constants.
- **77** independent synthetic assertions (envelope extrema, index boundaries, permutation for B=1…12, half-maximum OLS, exp models, candidate ordering, 2×9 searches and whole synthetic fitter).
- Two independent runs produce **byte-identical evidence JSON**.
- ZIP excludes vendor DLL, all real WAV/NAM/CLO captures. The verifier reads but never executes the DLL.

**Precisely closed:** the ordinary finite positive/negative audio-domain *mathematics of `0x1800BDBE0`*, with synthetic end-to-end output.

**Not closed:** (a) generating the **exact two sample-aligned, resampled, filtered audio arguments** supplied at the `0x1800BEDE4` call from the captured DI and NAM output; (b) Windows CRT/SSE bit-parity, certain native degenerate cases, (c) four gains calculated for real 2203 and SC20, (d) full official 128/2048 FIR.

**Next Stage 22:** reconstruct the upstream `0x1800BD490` audio preprocessing/call pointer identities, alignment and rate conversion to build *actual* `rdx`/`r8` argument waveforms, then run this already-recovered fitter. Compare the four **independently computed** gain values against both official CLOs as a strict gate. Do not guess arbitrary rate conversions or inject official coefficients.

### Additional machine-address permutation check

`native_repack_trace.py` independently **interprets only integer pointer arithmetic, loop branches, loads/stores and sign-mask writes from the original disassembly**, using symbolic input tags rather than audio. It derives the 4B-float permutation from native addresses rather than assuming the proposed array formula. The reconstructed destination layout matches the Python fitter for **B=4,5,7,8,9,10,12**, including both non-multiples of four and the unrolled four-at-a-time path. This extra verification is separate from the 75 pinned instruction predicates / 77 ordinary mathematical assertions.
