# HTKPA Stage 11 — DLL-proven **Pre-FIR candidate synthesis**

**2026-10-12 · Strict source-first static research · No converter or device changes.**

DLL: user-provided Windows Sonicake Manager `assets/5868USB.dll`; SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. All addresses are image-base `0x180000000` virtual addresses. The proprietary DLL was never executed and is not committed.

This stage starts with the specified chain: `0x1800BB440` → `0x1800B7670` → `0x1800B68F0`. It establishes **which working FIR buffer is written** and recovers the end-of-synthesis normalization. **It does not generate an official CLO or implement the missing full spectral algorithm.**

## Critical pointer identity: **Pre-FIR**, not Post-FIR

The fitter caller at `0x1800BF07C` reads `context+0x24408` (**Pre-FIR**) and stores the pointer at stack `+0x58` (`0x1800BF083`). It separately reads `context+0x24410` (**Post-FIR**) at `0x1800BF070`, storing it at stack `+0x60` (`0x1800BF077`).

Inside `0x1800BB210`, `0x1800BB821` reads `[rsp+0x1F8]` and passes it to `0x1800B68F0` via the fifth Windows x64 argument at `0x1800BB831`; the actual call is `0x1800BB836`.

**Correct stack mapping** accounts for the *8-byte call return address*, 8 callee pushes (64 bytes) and the 0x158-byte local allocation:

```text
Callee stack offset 0x1F8 − (8 + 64 + 0x158) = Caller stack offset 0x58 = Pre-FIR
Callee stack offset 0x200 − (8 + 64 + 0x158) = Caller stack offset 0x60 = Post-FIR
```

A preliminary manual read omitted the return-address byte count and misidentified the destination as Post-FIR. This was **corrected before this release** and regression-tested. As an independent check, `0x1800BB817/0x1800BB81E` feed both length arguments from `context+0x20ED4`, corresponding to **128 Pre-FIR taps**, not the 2048 Post-FIR tap count.

## Stage 11 candidate pipeline: verified machine-code operations

- `0x1800BB460..0x1800BB48C`: per-element `powf` correction and clipping to **[0.2,5]**, with the exponent factor multiplied by **0.9** at `0x1800BB4BE`. These operations were first pinned in Stage 3.
- `0x1800B7670` invoked **three times** at `0x1800BB4D9`, `0x1800BB4F8`, `0x1800BB812` with different pointer arguments. Inside are two `0x1800B7E10` Gaussian smoothings (`0x1800B7BBB/0x1800B7C12`) and three `0x1800B5D00` piecewise-linear interpolations (`0x1800B7BF8/0x1800B7C4B/0x1800B7C8C`). Working arrays also undergo `mulps` / `divps` at `0x1800BB575/0x1800BB6E1` and separate conditioning `0x1800B6220` at `0x1800BB7E3`. The **complete composite update formula** and exact intermediate-buffer semantics remain unproven.
- `0x1800B68F0` is the identified **Pre-FIR synthesis output writer**. It performs:
  1. Mirror extension of an N-point array into **2N−2** samples, excluding duplicate endpoints: `[a,b,c,d] → [a,b,c,d,c,b]` (`0x1800B691F/0x1800B6925/0x1800B69A0`).
  2. Spectral preparation/transform via `0x1800B72E0`, `0x1800B52E0`, `0x1800B47F0` (`0x1800B6A16/0x1800B6A50/0x1800B6A66`). **Their exact composition has not been fully reconstructed.**
  3. Measure L2 energy of the **entire** 2N−2 transformed support (`0x1800B6B18`), then copy the first M output samples to the working Pre-FIR (`0x1800B6B39`).
  4. Subtract the mean of those M output samples (`0x1800B6B9D/0x1800B6BEB`) and restore the original full-support L2 by multiplying every output sample by `full_norm / centered_output_norm` (`0x1800B6D07/0x1800B6D0E/0x1800B6D52`). Degenerate zero-norm behavior is not yet characterized.

Thus the **independently implemented isolated scalar stage** is:

```python
mirror = x + x[-2:0:-1]
z = UNKNOWN_NATIVE_SPECTRAL_TRANSFORM(mirror)
target_norm = sqrt(sum(t*t for t in z))
h = z[:M]
h = [t - mean(h) for t in h]
h = [t * target_norm / sqrt(sum(v*v for v in h)) for t in h]
```

The unknown function is intentionally **not** replaced with a guessed FFT/minimum-phase method. This sketch does **not** produce real Pre-FIR coefficients yet.

## Cross-check on matched official CLOs

Both official Windows Manager CLOs exhibit near-zero DC sums in their **128-entry Pre-FIR field** (after 48k→44.1k support conversion, 117 active taps):

| Model | Pre-FIR sum | Pre-FIR L2 | abs(sum)/L2 |
| --- | ---: | ---: | ---: |
| JCM800 2203 Crunch | 0.014214161456 | 3.231613432 | 0.00439847 |
| SC20 Full Rig | 0.005174505462 | 2.496118188 | 0.00207302 |

This is an *independent compatibility check* with the identified mean removal, **not proof of bit-exact reconstruction**. No official FIR coefficients were used in parameter fitting.

## Reproducibility

Separate conversation package `Sonicake_HTKPA_DLL_RE_Stage11_v0_11.zip` contains `verify_stage11.py`, `RESEARCH_REPORT.md`, `README.md`, and `evidence.json`. The read-only verifier confirms **43 exact-address machine-code predicates**, SHA-256, and **9 isolated mathematical/stack-mapping tests**. Two runs produced byte-identical evidence JSON; ZIP integrity verified. The package excludes the commercial DLL, NAM, WAV and official CLOs.

**Remaining acceptance gap:** neither full 128-tap official Pre-FIR nor 2048-tap Post-FIR has been regenerated solely from the input/output NAM probe. Next DLL-first tasks are the exact mathematics of `0x1800B72E0` (including `0x1800B7150`) and `0x1800B47F0`, plus the **separate Post-FIR update path** carried at fitter stack `+0x200`. No new hardware test file and no production JavaScript change. Keep the user-auditioned JCM800 2203 v0.2 C as listening control.
