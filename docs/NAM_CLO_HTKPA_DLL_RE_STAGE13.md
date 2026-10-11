# Sonicake HTKPA — Stage 13: complete algebraic spectral transform triplet

**2026-10-12 | Source-first static reverse engineering.** No Sonicake DLL execution, no new device CLO, no pedal writes, and **no changes to the production browser JS converter**.

## Scope and evidence

Windows Sonicake Manager `5868USB.dll` pinned SHA-256:
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
All listed VAs assume PE image base `0x180000000`.

Stage 12 recovered individual spectrum-processing instructions. Stage 13 resolves the **signs, normalization and odd/even pairing** across the complete call sequence
`0x1800B4A50 → 0x1800B6E30 → 0x1800B4F60`, with **41 exact instruction pins** and **111 passing synthetic math tests**. Direct slow trigonometric sums were independently compared against a NumPy FFT implementation for both parity classes. The validation is algebraic, not bit-exact native DLL output.

## Verified native formulas

`0x1800B52E0` generates sine and cosine tables for `θ_k = 2πk/N`, with imported `sin` at `0x1800B5421` (thunk `0x18017E15E`) and `cos` at `0x1800B5436` (thunk `0x18017E116`).

1. **Normalized positive-phase DFT** at `0x1800B4A50` (call `0x1800B754A`):
   `C[j] = (1/N) Σ_k x[k]·(cos(2πjk/N) + i·sin(2πjk/N))`.
   DLL proof: `0x1800B4B68` cosine products, `0x1800B4B75` sine products, `0x1800B4A87` computes `1/N`, `0x1800B4C62/0x1800B4C6D` normalize both real and imaginary.
   **Algebraic analog: `ifft(x)`**, not `fft(x)`.

2. **Conjugate cepstrum fold** at `0x1800B6E30` (call `0x1800B7569`). `P[0]=C[0]`. For all internal `1≤k<ceil(N/2)`, `P[k]=C[k]+conj(C[N-k])` (`0x1800B6EDB/0x1800B6EEB`). For even `N`, `P[N/2]=conj(C[N/2])` (real copy `0x1800B70F2`, imaginary sign change `0x1800B710C`). For odd `N=2m+1`, internal `1≤k≤m`. Unselected second-half bins are zeroed using `memset` (`0x1800B713A`), while lengths less than 3 are copied. **Odd/even behavior has separate native branches**.

3. **Unnormalized negative-phase complex DFT** at `0x1800B4F60` (call `0x1800B7590`):
   `Z[j] = Σ_k P[k]·(cos(2πjk/N) − i·sin(2πjk/N))`. Complex multiply is `(a·cos+b·sin) + i(b·cos−a·sin)`; supporting instructions include `0x1800B50E2`, `0x1800B511C`, `0x1800B5173`, `0x1800B5183`. **Algebraic analog: `fft(P)`**; no extra `1/N` at this step.

4. **Complex exponent** in `0x1800B72E0` at `0x1800B75D5/0x1800B75E1/0x1800B75F4`:
   `H[j]=exp(Re(Z[j]))·(cos(Im(Z[j]))+i·sin(Im(Z[j])))`.

Combining these with the earlier verified `−100 dB` relative floor, `log(x + 2^-23)` and exact **`N−1−i` first-half mirror**, we have a complete algebraic *equal-length nonnegative synthetic magnitude curve → complex spectrum* path with no undisclosed transform in the middle.

## Synthetic 128-tap Pre-FIR result

With an arbitrary positive curve of 128 points, Stage-11 even reflection produces 254 spectral samples. After the above transform and the already traced real inverse transform, zero-DC centering and energy normalization, the reference independently generates **128 finite taps**. One deterministic example has:

- Pre-FIR sum `−1.6653345369e−16`;
- L2 norm `0.9374846715`;
- first four taps `[0.89250108, 0.15651446, −0.06565826, −0.20002253]`.

**These are artificial test data, not a vendor or NAM model.** The 128-tap example does not establish that the unknown upstream curve or the complete numerical execution order matches Sonicake.

## Reproducibility

Private-conversation research archive `Sonicake_HTKPA_DLL_RE_Stage13_v0_13.zip` contains standalone `verify_stage13.py`, `make_example.py`, `README.md`, technical report, evidence JSON, a synthetic example JSON and plot. It excludes proprietary binaries and captured WAV/CLO.

Two independent runs against the SHA-pinned user DLL both returned:

- **41 exact machine instruction checks**
- **111 synthetic mathematical tests**
- identical evidence JSON, SHA-256 `8bfb6c6d109ee6c78b9d30c7e040fb597372845f8b1298cad33d9b07933caa3f`.

The scripts **only read the DLL** via `objdump`; no DLL execution or device interaction.

## Acceptance gate and next trace

**Achieved:** Complete algebraic spectrum-synthesis triplet with signs, parity and normalization for synthetic same-length input, validated by two independent implementations.

**Still not achieved:** Native float32/bit accuracy; native edge semantics for interpolation/negative inputs; optimizer-produced target curves through `0x1800B7670`; actual Post-FIR update; direct calculation of either official 128/2048 FIR from NAM/WAV; numerical or auditory equivalence with mobile SONICLINK.

**Stage 14 is source-first:** trace the source/meaning of the input spectral arrays used by `0x1800B7670` and identify the *separate Post-FIR writer* via `context+0x24410`, including cross-stage normalization. Only then attempt vendor-file coefficient comparison. Preserve the user-accepted JCM800 2203 v0.2 C as hardware reference; no production modifications based on this result.
