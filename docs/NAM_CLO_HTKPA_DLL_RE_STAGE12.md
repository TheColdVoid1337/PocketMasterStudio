# Sonicake HTKPA — Stage 12: Pre-FIR complex-log spectral pipeline

**2026-10-12 · DLL-first, static research only.** No proprietary code executed/distributed, no new CLO generated, no physical pedal writes, no production JS converter changes.

Pinned Windows `5868USB.dll` SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; VAs assume base `0x180000000`.

## Directly proven operations

Stage 11's **128-tap Pre-FIR writer** `0x1800B68F0` calls `0x1800B72E0` at `0x1800B6A16`, then `0x1800B52E0` at `0x1800B6A50` and `0x1800B47F0` at `0x1800B6A66`, before the previously traced mean subtraction and L2 energy normalization.

Inside `0x1800B72E0`:

1. `0x1800B733B`: the vector input passes through `0x1800B7150`. With **−100.0** at `0x18024CF38`, scale **0.05** at `0x18024C520` and double-precision base **10.0** at `0x18024CB30`, the guard floor is `max(abs(x)) * 10^(-100*0.05) = max(abs(x))*1e-5`. The guard replaces values whose absolute magnitudes fall below this floor with a **positive** floor; negative-valued and degenerate inputs have unresolved native semantics.
2. `0x1800B7380/0x1800B73BB`: add float32 `2^-23` (`0x18024C4D4`) and compute `logf`; the conditionally guarded and logged array feeds downstream transforms.
3. `0x1800B7416/0x1800B7433/0x1800B7450`: if source/target lengths differ, construct evenly spaced index coordinates and use the Stage-9-proven piecewise-linear interpolator `0x1800B5D00`.
4. `0x1800B7480..0x1800B74DD`: the first `floor(N/2)` bins are overwritten with bins `N−i−1` from the second half. **One-sided overwrite, not a generic FFT library's usual Hermitian mirroring.**
5. `0x1800B7534/0x1800B754A/0x1800B7569/0x1800B7590`: sine/cosine basis `0x1800B52E0`, first complex trigonometric transform `0x1800B4A50` (its loop includes **1/N** normalization at `0x1800B4C62/0x1800B4C6D`), conjugate-pair folding `0x1800B6E30`, then a second complex transform `0x1800B4F60`. At `0x1800B6EDB/0x1800B6EEB` paired real components are **added** and paired imaginary components are **subtracted**. There is a separate midpoint/conjugate handling at `0x1800B710C`.
6. `0x1800B75D5/0x1800B75E1/0x1800B75F4`: imported `expf`, `cosf`, `sinf` construct each complex bin as **`exp(a) × (cos(b) + i·sin(b))`**; real/imaginary floats are saved at `0x1800B75EA/0x1800B7601`.

The last transform `0x1800B47F0` uses a trigonometric basis with **2π/N** (`0x1800B530A/0x1800B5322`), products and a subtraction near `0x1800B48F9`, then **1/N** normalization at `0x1800B49E7` using the constant `1.0` at `0x18024C6A0`. For a given complex input `H[k]`, its isolated real output has algebraic form:

```text
h[n] = sum_k (Re(H[k])*cos(2πnk/N) − Im(H[k])*sin(2πnk/N)) / N
```

This equals `real(ifft(H))` mathematically (not necessarily bit-exact in float32/native summation order).

## How far this gets us

This is strong **source-level support** for a complex-log/cepstral spectral Pre-FIR synthesis stage, compatible with Stage 6's observed near-minimum-phase fingerprint in official filters. It **does not** prove that substituting an off-the-shelf `minimum_phase` library produces vendor-identical Pre-FIR taps. The intermediate array ordering, full first/second transform conventions, optimizer-provided spectral target, and the **separate Post-FIR writer** remain incomplete.

Stage-4 strict criterion **still unmet**: neither complete official Pre-FIR nor complete official Post-FIR has been independently computed from source NAM/WAV.

## Verification

Self-contained research archive `Sonicake_HTKPA_DLL_RE_Stage12_v0_12.zip` delivered separately in the conversation contains a **read-only** Python `verify_stage12.py`, evidence JSON, README, and full `RESEARCH_REPORT.md`; it **excludes** the DLL, source NAM, vendor WAV/CLO and does not produce/upload any CLO.

- **35 exact DLL instruction checks**, **six pinned numerical constants**, **13 synthetic isolated-operation tests**, all passing.
- Two independent verifier runs have the same evidence JSON SHA-256: `0daec7751e318b09f178cfa1f3d457c6d82195d3b6b3f1156348b994a1c9f0d7`.
- Synthetic inverse-transform calculation agrees with `real(numpy.fft.ifft)`; this tests **the recovered equation only**, not native DLL parity or the complete transformer.

**Next DLL-first gate (Stage 13):** reconstruct transform signs, odd/even frequency folding and exact float32 intermediate buffers across `0x1800B4A50 → 0x1800B6E30 → 0x1800B4F60` to make a complete spectral-curve→Pre-FIR synthetic test. Then resume source tracing of the *separate* Post-FIR update and optimizer input curves; do not guess frequency targets or alter the production converter.

Keep the user-accepted JCM800 2203 v0.2 C as a listening control.
