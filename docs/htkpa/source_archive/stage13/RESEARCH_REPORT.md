# Sonicake HTKPA — Stage 13: Complex transform triplet

**Date:** 2026-10-12  
**Source:** user's Windows Sonicake Manager `5868USB.dll`, PE64, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.  
**Mode:** static disassembly via GNU `objdump`, **never native DLL execution**, no pedal I/O. The source DLL and proprietary NAM/WAV/CLO captures are intentionally excluded from deliverables.

## Executive result

Stage 12 had verified isolated scalar operations but not the *whole* consecutive complex-transform chain. Stage 13 reconstructs that **algebraic chain for arbitrary same-length nonnegative synthetic magnitude inputs**, with the special odd/even middle-operator cases. We can independently generate a **synthetic 128-tap Pre-FIR** using the already known Stage 11 DC/energy operations. We **cannot** generate the two official Pre-FIRs yet because the optimizer's real spectral curve and exact native floating point conventions are unknown.

## 1. Native import identities and shared trigonometric basis

`0x1800B52E0` computes `2π/N` from constant `0x18024CCF0` (`0x1800B530A`, `0x1800B5322`) and populates two tables using Windows imports:

- `0x1800B5421`: thunk `0x18017E15E` → import `sin`, first output table (`rdx`).
- `0x1800B5436`: thunk `0x18017E116` → import `cos`, second output table (`r8`).

These are *double* trigonometric imports, whose results are saved as float32; do not equate them with bit-perfect NumPy trigonometry. The helper includes vectorized and scalar paths.

## 2. `0x1800B4A50`: normalized positive-phase complex transform

When called by `0x1800B72E0` (`0x1800B754A`), the inputs are **real** `x[k]` and the trigonometric tables. For each `j` the routine writes interleaved float32 `(real, imaginary)`:

\[
C[j] = \frac{1}{N}\sum_{k=0}^{N-1} x[k]\bigl(\cos(2\pi jk/N)+i\sin(2\pi jk/N)\bigr).
\]

Direct evidence: cosine multiply `0x1800B4B68`, sine multiply `0x1800B4B75`, float32 division by N `0x1800B4A87`, scaling of both accumulators `0x1800B4C62/0x1800B4C6D`, consecutive real/imaginary stores `0x1800B4C7A/0x1800B4C83`.

Thus `C = ifft(x)` **algebraically**, not FFT. Earlier partial notes had not established the signs.

## 3. `0x1800B6E30`: conjugate-cepstrum folding, parity dependent

Take complex interleaved `C[0..N-1]` and create `P`:

- For `N=1,2`, the code tail-copies the array without the general folding procedure (`0x1800B6E3C` and jump to memcpy).
- Always `P[0]=C[0]` (`0x1800B6E69/0x1800B6E7A`).
- **Odd** `N=2m+1`: `P[k]=C[k]+conj(C[N-k])` for `1≤k≤m`, then set the last `m` values to zero.
- **Even** `N=2m`: identical pairing for `1≤k<m`; `P[m]=conj(C[m])`, then set the last `m-1` values to zero.

The real addition and imaginary subtraction are at `0x1800B6EDB` and `0x1800B6EEB`; the even-N path starts `0x1800B6FC1`; the special midpoint real copy / imaginary sign-bit flip are `0x1800B70F2` and `0x1800B710C`; the trailing zeroing jumps to imported `memset` at `0x1800B713A`. The different parity loops have separate bodies (not just a branchless generic FFT helper).

The `conj(C[m])` operation matters for **arbitrary complex test arrays**. It is indistinguishable from simply retaining that value only if it is known to be real.

## 4. `0x1800B4F60`: unnormalized negative-phase complex transform

The immediately following function (`0x1800B7590`) reads the folded interleaved complex array and writes:

\[
Z[j]=\sum_{k=0}^{N-1}P[k]\bigl(\cos(2\pi jk/N)-i\sin(2\pi jk/N)\bigr).
\]

For a sample `a+ib`, the sum is `(a cos + b sin) + i(b cos − a sin)`. The real additions and imaginary subtractions are observable at `0x1800B50E2`, `0x1800B511C`, `0x1800B5173`, `0x1800B5183`. **There is no final 1/N division** in this routine. Its algebraic counterpart is `fft(P)`.

The DLL then builds `H[j]=exp(Re(Z[j]))·(cos(Im(Z[j]))+i·sin(Im(Z[j])))` (`0x1800B75D5/0x1800B75E1/0x1800B75F4`). Thus the complete recovered kernel is:

```python
v = guarded_log_of_input_magnitude             # Stage 12; finite nonnegative input only
v = replace_first_half_by_reversed_second(v)   # EXACT N-1-i index
c = ifft(v)                                    # B4A50 (+ phase; 1/N)
p = fold_conjugate_pairs(c)                    # B6E30 odd/even / Nyquist
z = fft(p)                                     # B4F60 (- phase; no 1/N)
H = exp(z.real) * (cos(z.imag) + 1j*sin(z.imag))
```

For the previously traced Pre-FIR writer `0x1800B68F0`, the independent synthetic example uses the established even reflection of the input curve, final `real(ifft(H))`, take first `M=128`, remove mean/DC and normalize to the full intermediate output energy. **The real sonicake-optimizer target is unknown; this demonstration deliberately uses an artificial curve.** The variable-length interpolator (`0x1800B5D00`) is not exercised in this equal-length case, and no native float32 bit-parity is claimed.

## 5. Reproducibility tests

Read-only verifier `verify_stage13.py` checks **41 exact machine-code addresses** and import identities with the SHA-pinned DLL, then runs **111 synthetic tests**, including:

- Direct explicit trigonometric sums vs algebraic FFT equivalents, for odd/even N from 3 to 128.
- Independent O(N²) **whole-chain** trigonometric implementation vs NumPy FFT implementation on both odd and even N (up to 32).
- Conjugate pairing for arbitrary complex data including even-N Nyquist conjugation and exact zero tail; N=2 copy case.
- Constant magnitude → unity complex response; finite response for other positive curves.
- A synthetic **128-tap** Pre-FIR with zero mean and finite normalized energy; smaller odd-length synthetic cases as additional checks.

Two independent read-only runs produced byte-identical evidence JSON, SHA-256 `8bfb6c6d109ee6c78b9d30c7e040fb597372845f8b1298cad33d9b07933caa3f`.

Example for arbitrary curve: input 128 bins mirrored to 254 working samples; final synthetic output 128 taps; sum ≈ `−1.67×10⁻¹⁶`, L2 norm ≈ `0.93748`. First taps ≈ `[0.89250,0.15651,−0.06566,−0.20002,...]`. This **does not correspond to a user amp or vendor CLO**.

## 6. Strict limitations and next source-first target

**Achieved:** complete *algebraic* spectral triplet for controlled synthetic same-length input, direct DLL pointer/call verification, odd/even branch semantics and mathematically independent test. This closes the Stage 12 open mathematical-transform chain for this supported input class.

**Not achieved:** vendor-float32 exactness; interpolator end cases; degenerate/negative/nonfinite spectral magnitudes; actual fitted spectrum coming from `0x1800B7670`; optimizer pass reconciliation; actual Post-FIR writer; or a coefficient-matched official 128/2048 FIR from input/output WAV. This is **not** a complete clone converter and no experimental device-ready CLO is generated.

**Stage 14 priority:** first trace the two arrays and their roles through `0x1800B7670` and into the `0x1800B68F0` input. Then follow the *distinct* Post-FIR destination pointer (`context+0x24410`) within the three selector passes, from spectral correction to actual memory write. Only with **source-confirmed arrays and equations** try to calculate the official FIRs on both paired NAM sessions. Keep the user-auditioned JCM800 2203 v0.2 C as a control and leave production Void Mod unchanged.
