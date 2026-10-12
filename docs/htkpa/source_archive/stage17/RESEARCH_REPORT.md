# HTKPA Stage 17 — Source-first fit-loop alias correction and low-index curve conditioning

2026-10-12. Original Windows Sonicake Manager `5868USB.dll` was statically disassembled, never loaded or executed. Expected SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. PE VA image base: `0x180000000`.

## Outcome relative to the Stage-16 plan

The goal was a **complete native-equivalent single iteration**, followed by native-equivalent selectors `2 → 1 → 3` and coefficient parity with the official 2203 and SC20 CLO files. **This acceptance gate remains open.** We did not fabricate a conditioner or compare a guessed model to official coefficients. However, a key Stage-16 wrong pointer assignment is now corrected, the previously unresolved native `0x1800B6220` is reconstructed mathematically in its ordinary positive-input domain, and a read-only two-model comparison harness is ready for genuinely independent candidates.

## 1. Correction: writes belong to two *caller-owned* arrays, not scratch V2

All three arrays are allocated **once** in the encompassing `0x1800BE830` before the outer selector loop: `r15` at `0x1800BEE33`, `r12` at `0x1800BEE3F`, and `r13` at `0x1800BEE4B`. The call at `0x1800BF0C9` passes them as Windows x64 stack arguments at caller `[rsp+0x40] = r15`, `[rsp+0x48] = r12`, `[rsp+0x50] = r13`.

The callee prologue pushes eight 8-byte registers and reserves `0x158` stack bytes. Its stack distance from caller is **8-byte return address + 8×8 pushes + 0x158 = 0x1A0**. Thus, inside `0x1800BB210`:

| Callee stack pointer | Caller original | Meaning |
|---|---|---|
| `[rsp+0x1E0]` | `[rsp+0x40]` | outer `r15` — independently allocated first mutable array (`A`) |
| `[rsp+0x1E8]` | `[rsp+0x48]` | outer `r12` — independently allocated second mutable array (`B`) |
| `[rsp+0x1F0]` | `[rsp+0x50]` | outer `r13` — frequency coordinate array (passed as `rbp` here) |

The callee starts with local `r12=V0`, `rdi=V2`, and `r13=B` (restored from `[rsp+0x1E8]` at `0x1800BB391`):

1. First frequency conditioning (`0x1800BB4D9`): source `V0`, output curve `V2`, output frequencies `V4`.
2. Second frequency conditioning (`0x1800BB4F8`): source `V2`, output curve `V0`, output frequencies in the caller's coordinate array.
3. The `mulps` in `0x1800BB575` **loads V0 and B, then writes into B**. The actual destination is based on `r13`, not scratch `V2`.
4. `0x1800BB66A` reads `A` from `[rsp+0x1E0]`. The `divps` at `0x1800BB6E1` **divides A by V0 and writes A**.
5. `0x1800BB7E3` then sends **A** into the newly reconstructed in-place conditioner `0x1800B6220`.
6. Third frequency conditioning (`0x1800BB812`): takes modified **A** and produces the spectral input for the 128-tap Pre-FIR synthesizer.

As long as `V0` is the conditioned positive curve and no boundary exceptions are triggered, the local algebra is:

```
B[i] = float32(B[i] * V0[i])
A[i] = float32(A[i] / V0[i])
A[:K] = low_index_native_geometric_conditioning(A[:K], using A[K] as lookahead)
```

**This is a concrete correction to Stage 16**, whose prose misleadingly described `V2 *= V0`. The Stage-16 pointer-layout verifier confirmed local scratch offsets but did not prove that vector multiply's destination was V2. The caller-owned buffers persist between the three outer fits. The **precise initialization of A/B by `0x1800BC6B0` and full native conditioner results still require reconstruction**.

## 2. Exact scalar mathematics of `0x1800B6220`

This helper was previously listed as an “unknown nonlinear conditioning” step. Exact instructions were recovered from `0x1800B6220..0x1800B638F` and its call site.

Its count is built as:

```
context+0x20EC4 = float32(0.5 * sample_rate)       [0x1800B5865..0x1800B587F]
context+0x20EC8 = float32(1.0 / (context+0x20EC4)) [0x1800B587B..0x1800B5887]
K = trunc(sqrtf(float32(float32(60.0 * context+0x20EC8) * L)))
```

The exact 60.0f is at `0x18024CD60`, passed in `xmm3` at `0x1800BB7D2`; in the callee, `0x1800B622A/0x1800B623D/0x1800B6244/0x1800B6249` multiply, sqrtf and convert/truncate. **There is no basis for replacing K with an arbitrary smoothing width**. At 48 kHz the same expression has approximate K values: L=1000 → 1 (no modification), L=2500 → 2, and L=10,000 → 5. Actual L is context-dependent and not assumed to equal the 512-point Mel objective width.

For finite positive arrays and normal support `1 < K < L`, the helper mutates the first K samples **in place**:

```
A[0] = sqrtf(A[0] * sqrtf(A[0] * A[1]))
for i = 1, ..., K-1:
    A[i] = sqrtf(A[i] * sqrtf(A[i-1] * A[i+1]))
```

All multiplications and sqrtf results round to float32. A critical implementation detail is that **A[i-1] is already modified when computing A[i]**. This is *not* a symmetric three-sample filter calculated from an immutable copy. Also, `A[K]` is needed for the last look-ahead. `K<=1` exits without changes. Negative, NaN, and `K>=L` native behavior is intentionally not claimed in the independent reimplementation; this tool rejects unproven edge cases rather than inventing them.

The scalar reference agrees with separately derived fourth-root expressions on synthetic positive input. The DLL has a four-at-a-time unrolled path for K≥5; the source-checked operations match the same sequential dependency.

This is **local mathematical reproduction only**, not full native bit parity of the entire fitter.

## 3. Fit-loop structure and what still blocks a complete synthetic iteration

**Already source-supported:** per-element bounded power proposal, context curve initialization, 3 outer selections with 3/2/5 iterations, 2× curve conditioning and caller-state changes, the above special conditioner, third curve conditioning, Pre-FIR synthesis, audio rendering + asymmetric saturator, spectral feedback and regularized division, Post-FIR synthesis, Mel-spectrum score, accept/reject rollback, and once-only final Post-FIR correction.

**Still missing for native-equivalent execution:** precise initial A/B produced by `0x1800BC6B0`, the whole return-array behavior of `0x1800B7670` (including duplicate interpolant knots and Gaussian edge bins), exact float32/native rounding within audio render / spectral analysis / synthesized FIR composition, and full multi-selector state tracking under every candidate accept/reject branch. Substituting ad-hoc approximations would violate our source-first research constraint.

We therefore supply a limited executable **structural fixture** that accepts the second conditioner output as an explicit external synthetic input solely to test alias writes. The fixture is not represented as a working HTKPA pass. It does not fit, pack, or export CLOs.

## 4. Two-model Windows Manager CLO oracle: independently prepared, NOT fitted

`vendor_parity_gate.py` recognizes the specific captured Windows Manager files by pinned SHA-256, verifies 8840-byte VTSI format and CRC16/Modbus, and reads the 128 Pre-FIR and 2048 Post-FIR float32 fields. **No official coefficients are fed into any experimental fitter.**

| Model | Official CLO SHA-256 | Pre-FIR sum / L2 | Post-FIR sum / L2 | Independent replacement present? |
|---|---|---|---|---|
| 2203 Crunch | `50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7` | 0.014214 / 3.231613 | 0.002959 / 1.170528 | **No** |
| SC20 Full Rig | `2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a` | 0.005175 / 2.496118 | 0.006035 / 1.922987 | **No** |

When a *genuinely independent* model is eventually provided, the gate calculates max absolute tap error, normalized L2 error, cosine and float32 exact equality, independently for both filters and both NAMs. Its current **explicit output is `NOT_TESTED` for both**, not a false claim of successful coefficient matching. Windows Manager fidelity also does not establish mobile SONICLINK identity.

## Reproducibility

- Verifier: **64 pinned machine-code instructions, 5 embedded constants, 23 synthetic tests**, all passing.
- Two independent runs on the original pinned DLL: identical evidence SHA-256 `9b0220696c674bca8a496d19a191a3e085bc352f886d882055baee5d57fd241b`.
- Both original vendor CLO references validated, using them **only** for post-hoc format/statistics; both actual FIR reconstruction statuses `NOT_TESTED`.
- The ZIP contains ONLY independent Python source, synthetic evidence, user-facing reports and README. Proprietary DLL, NAM, official WAVs, and CLOs are excluded.

## Strict gate for Stage 18

Trace `0x1800BC6B0` (initial A/B curves) and write a native-exact bounded synthetic implementation of **`0x1800B7670`** including both Gaussian calls, interp edge cases and array aliases. Verify what its three successive callers pass without using vendor CLO coefficients for fitting. Then connect first Pre-FIR candidate + first spectral feedback, and only after that commit to complete 3× iterative fitting. Keep production JS and existing user-auditioned JCM800 2203 v0.2 C unchanged.
