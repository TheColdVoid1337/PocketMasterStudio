# HTKPA Reverse Engineering — Stage 12

**2026-10-12 | DLL-first, static only | VERIFIED PARTIAL spectral synthesis**

## Outcome

We traced the 128-tap Pre-FIR synthesis subpipeline from the previous stage, namely:

```
0x1800B68F0 (destination: 128-tap working Pre-FIR)
  → 0x1800B72E0 (spectral conditioning and complex spectral synthesis)
      → 0x1800B7150 (relative magnitude floor, preceding log)
      → 0x1800B5D00 (only when input/output lengths differ)
      → 0x1800B52E0 (sin/cos angular basis)
      → 0x1800B4A50 (complex transform with 1/N coefficient)
      → 0x1800B6E30 (conjugate-pair fold)
      → 0x1800B4F60 (second complex transform)
      → imported expf/cosf/sinf (complex spectral reconstruction)
  → 0x1800B52E0 (trigonometric basis)
  → 0x1800B47F0 (real output of complex inverse transform, 1/N)
  → select 128 taps, remove DC, restore energy
```

**This is a call graph whose individual listed operations are backed by assembly. The full exact float32 output of the composition is NOT reproduced here.**

## 1. Input magnitude guard recovered, including exact threshold

`0x1800B72E0` calls `0x1800B7150`, passing the float32 control `-100.0` from PE VA `0x18024CF38`.

`0x1800B7150` computes the absolute maximum of an input vector. If the control is negative it multiplies by PE float32 constant **0.05** (`0x18024C520`), calls `pow` with double **10.0** (`0x18024CB30`), and multiplies by this maximum. The resulting floor is:

```
floor = max(abs(x)) * pow(10, -100 * 0.05)
      = max(abs(x)) * 1e-5
```

At `0x1800B729F..0x1800B72A7` elements with absolute magnitude below this threshold are replaced with the positive floor. The subsequent `0x1800B72E0` vector/scalar loops add **2^-23** (`0x18024C4D4`) and call logarithm instructions / `logf` at `0x1800B73BB`.

This threshold is **−100 dB in amplitude** relative to the largest input element. This is a specific vendor numerical stability guard; it is not a guessed ridge parameter. The behavior for negative values with magnitude ABOVE threshold, NaNs, infinities, and zero-length vectors is **not established**; our tests model nonnegative, finite spectral magnitudes only.

## 2. Variable-length interpolation and mirror convention

`0x1800B72E0` takes an input array and input length (`rdx`, `r8d`), a target spectral length (`r9d`), and complex output pointer (stack argument). If `input_len != target_len`, it calls **the existing Stage-9-confirmed linear interpolator `0x1800B5D00`** after generating evenly spaced index coordinates via `0x180027DB0` (`0x1800B7416/0x1800B7433`). No statement of the interpolator's *complete* endpoint/extrapolation numerical parity is made yet.

The code at `0x1800B7480..0x1800B74DD` has a specific, unusual mirror convention:

```
for i in range(floor(N/2)):
    curve[i] = curve[N-1-i]
```

This is a **one-sided overwrite**, not the more common direct Hermitian fill `X[N-i]=conj(X[i])`. The exact order and bins matter; a generic `numpy.fft` minimum-phase helper does not automatically reproduce this convention.

## 3. Complex-log operations and transform directions

Direct addresses:

- `0x1800B754A`: call to `0x1800B4A50`, which contains explicit modular trigonometric convolution sums and multiply by **1/N** (`0x1800B4C62/0x1800B4C6D`).
- `0x1800B7569`: call to `0x1800B6E30`; scalar body combines paired real parts by addition (`0x1800B6EDB`) and imaginary parts by subtraction (`0x1800B6EEB`), then handles the midpoint/conjugation (`0x1800B710C`). It is consistent with a causal/one-sided cepstral projection, but its exact behavior for all short/even/odd lengths and intermediate buffer orientation is not yet reproduced bit-exactly.
- `0x1800B7590`: call to the second complex transform `0x1800B4F60`.
- `0x1800B75D5`, `0x1800B75E1`, `0x1800B75F4`: **`expf`, `cosf`, `sinf`** imports. The code stores `exp(real) * cos(imag)` and `exp(real) * sin(imag)` as consecutive float32 components (`0x1800B75EA/0x1800B7601`).

This strongly supports complex cepstral / log-spectrum synthesis in the Windows converter and is consistent with Stage 6's **independent minimum-phase fingerprints** in two official Post-FIRs. However, no proof of exact native coefficient reproduction or the *same* phase convention for both FIRs follows from this alone.

## 4. Real inverse transform in `0x1800B47F0`

The generator's last transform, called from `0x1800B68F0` at `0x1800B6A66`, has explicit trigonometric products with **real*cos − imaginary*sin** (`0x1800B48D3..0x1800B491D`, notably subtraction at `0x1800B48F9`), and normalization by **1/N** (`0x1800B49E7`, using PE constant `1.0` at `0x18024C6A0`). The trigonometric basis uses **2π/N** (`0x1800B530A/0x1800B5322`) with native sine/cosine calls (`0x1800B5421/0x1800B5436`). Thus, for already known complex input bins `H[k]`, the isolated output operation is:

```
h[n] = (1/N) sum_{k=0..N-1} (
    Re(H[k])*cos(2*pi*n*k/N) - Im(H[k])*sin(2*pi*n*k/N)
)
```

For arbitrary complex spectra, this equals `real(ifft(H))`. We independently verified that equality on synthetic complex arrays without calling Sonicake code. **The native floating-point accumulation order and trigonometric library implementations are different, so this is an algebraic equivalence, not a bit-exact numerical comparison.**

The parent `0x1800B68F0` subsequently performs the already source-confirmed **DC mean removal and energy normalization** for the working **Pre-FIR**, not the Post-FIR. There is no new Pre-FIR candidate emitted in this stage because the *preceding fitted frequency-response curve* and the exact first/second transforms are still missing.

## 5. Reproducible checks

`verify_stage12.py` statically reads the original PE DLL and calls GNU `objdump` only. It enforces the exact SHA-256:

`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`

Checks: **35 pinned assembly addresses**, **six PE-resident numerical constants**, **13 synthetic mathematical tests**. Twice-run evidence JSON SHA-256:

`0daec7751e318b09f178cfa1f3d457c6d82195d3b6b3f1156348b994a1c9f0d7`

The original DLL and source NAM, vendor WAV/CLO are omitted from the research ZIP. No file is written into the device or main converter. Four limitations still block official conversion parity:

1. Exact numerical semantics and input/output bin orientation across `0x1800B4A50`, `0x1800B6E30`, and `0x1800B4F60` are **not yet validated against a native reference**. Do not simply substitute an FFT package and call the port exact.
2. Input spectrum and gains created by `0x1800B7670` / the 2→1→3 fitting optimizer have not been independently generated from WAV.
3. The separate **Post-FIR update** remains to be source-traced.
4. Neither matching official Pre-FIR nor Post-FIR has been regenerated coefficient-by-coefficient from input/output audio.

## Stage 13 source-first target

First finish the exact complex transform conventions for `0x1800B4A50 → 0x1800B6E30 → 0x1800B4F60`, including parity, signs and normalization, and derive a synthetic spectral-input-to-Pre-FIR test with no unknown middle operations. Then trace the optimizer's frequency-ratio array and exact Post-FIR writer, preferably before any further hardware tests. Do **not** change production JS or assume the mobile SONICLINK converter matches Windows Manager.
