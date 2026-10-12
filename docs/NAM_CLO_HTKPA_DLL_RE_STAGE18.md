# Sonicake HTKPA Stage 18 — source-derived initial spectral curves and B7670 conditioner

**2026-10-12 · Source-first, read-only research · No device/production changes.**

Analyzed user's Windows Sonicake Manager `5868USB.dll`, pinned SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. The commercial DLL was never executed, modified or committed. A separate research ZIP **`Sonicake_HTKPA_DLL_RE_Stage18_v0_18.zip`** is available in the originating conversation; it bundles `stage18_source_first.py`, `demo_stage18.py`, evidence JSON, detailed report and README — no DLL/NAM/WAV/CLO files.

## Source correction: `0x1800BC6B0` is NOT a trivial fixed-curve initializer

Stage 17 correctly located the call, but underestimated the audio preprocessing it performs. The outer fit driver `0x1800BE830`:

1. Calls audio-preprocess helper `0x1800BD490` at `0x1800BEE25`.
2. Allocates persistent caller-owned correction arrays **A, B, F** at `0x1800BEE33/0x1800BEE3F/0x1800BEE4B`.
3. Passes their pointers via outgoing Win64 stack slots and calls `0x1800BC6B0` at `0x1800BEE89` **before** the selectors `2→1→3`.

The latter function **prepares the initial A/B spectral curves from the audio**, not by filling fixed arrays. Observed native operations include sample-rate-specific coefficient-table selection (`0x1800BC753..0x1800BC940`), a 50-point helper call to `0x1800B5A30` (`0x1800BC96D`), two recursive second-order filters, `0x1800BE700` nonlinear processing (`0x1800BCC79`), and cross-spectral analysis `0x1800B82B0` (`0x1800BCFF2`).

**Do not mistake this for a standalone spectrum-vs-spectrum initialization.** Full real-WAV reproduction still requires independently implementing its two audio-preprocess paths and the exact FFT/STFT buffers.

## New exact tail formulas and proven call order

`0x1800BD01F` and `0x1800BD03D` call Gaussian `0x1800B7E10` in succession with widths `trunc(0.001*N)` and `trunc(0.005*N)`, where N is the spectral curve's native length. Pinned doubles: `0x18024C618 = 0.001`, `0x18024C688 = 0.005`.

After the Gaussian passes, the DLL computes a **quadratic soft floor** on working B:

```text
T     = float32(max(auxiliary_U) * 0.001)
limit = float32(2*T)
alpha = float32((limit-T)/(limit*limit))

B[k] = float32(T + alpha*B_raw[k]*B_raw[k])  if B_raw[k] < limit
       B_raw[k]                              otherwise

A[k] = float32((1e6*float64(U[k])) / (1e6*float64(B[k]) + 2^-23))
```

Native proof of floor and compare: `0x1800BD0B7..0x1800BD119`; ratio: `0x1800BD230..0x1800BD2E5` and scalar `0x1800BD350..0x1800BD441`. Pinned constants `1e6` at `0x18024CD28`, epsilon `2^-23` at `0x18024C588`. The parabola joins the unchanged branch at `2T` with both *value* and *first derivative* continuous, for T>0. Its scalar formula, source-ordered float32 approximations and branch conditions have independent tests.

The **physical meaning of U's exact audio-derived buffer is not fully reconstructed**; it is wrong to assume that it is a raw Welch power spectrum merely because it feeds the floor. The original source WAV and reference audio have not yet been converted into the native U/B spectrum arrays by this prototype.

## Implemented ordinary-domain `0x1800B7670`

`conditioned_curve(freq,mag,m)` now executes the **complete source-grounded sequence of stages** for finite positive magnitude gains and strictly increasing frequency coordinates, source length `N>=501`, `2<=m<=N`:

- 2595·log10(1+Hz/700) **Mel endpoint conversion**, Mel linspace of N and m coordinates and inverse mapping to Hz;
- separate float32 repeated-addition `0x180027DB0` linear-Hz output grid, enforcing exact last endpoint;
- gain to `20log10(gain)` in dB;
- first Gaussian, width `trunc(0.002*N)`;
- **interpolate source Hz→N Mel-spaced Hz** with `0x1800B5D00`;
- second Gaussian, width `2*trunc(N/m)`;
- **interpolate N Mel→m Mel** (skip when equal);
- **interpolate m Mel-spaced Hz→m linear Hz** and convert back `10**(dB/20)`.

Proof of three conditional interpolators: `0x1800B7BF8/0x1800B7C4B/0x1800B7C8C`; two Gaussian calls: `0x1800B7BBB/0x1800B7C12`; final gain: `0x1800B7D1C`. Gaussian `0x1800B7E10` uses native-shaped, double-precision, reversed window coefficients and cropped-boundary normalization; window width<=0 remains deliberately rejected. **This is algebraic and synthetic domain parity, not bit-identical Windows CRT/SSE execution.**

The native `0x180027DB0` **repeated-addition** linspace implementation is included rather than silently using a generic NumPy linspace. Native interpolation undefined/nonmonotone/duplicate-knot variants remain excluded. No guessed regularization, generic SciPy smoothing or vendor CLO coefficients were used.

## Test facts and demonstration

The standalone read-only verifier passed:

| Gate | Verified |
|---|---:|
| Exact DLL address/instruction pins | **59 / 59** |
| Exact PE numerical constants | **12 / 12** |
| Synthetic algebraic/structural tests | **49 / 49** |
| Two independent evidence JSON runs | **Byte-identical** |

Evidence SHA-256 `c334edaaede0db5200c6d60b8010e10519028ee3261729190861dc6dea7c1775`.

Synthetic fixture: **2401 source frequency bins**, two intentionally artificial positive curves. Two Gaussian initialization passes give widths **2,12**. Source-conditioned A and B can be mapped to **128-point** and **2048-point** spectra; for the conditioner itself, widths are respectively **4,36** and **4,2**. Both outputs are finite, positive, and preserve the expected Hz range. **These are not FIR taps, not output audio, and not a new CLO.**

## Remaining source-first blockers

**Vendor coefficient parity remains `NOT_TESTED` for both 2203 and SC20** because no independently derived real-NAM FIR candidate was generated. The core remaining native path is the audio preprocessing of `0x1800BD490` and `0x1800BC6B0` including the sample-rate-specific second-order sections, output of `0x1800BE700`, and spectral output mapping of `0x1800B82B0`, followed by end-to-end exact numeric fits and the final 44.1-kHz serialization. A complete 3-pass converter is NOT established.

**Stage 19:** reverse these exact audio/preprocessing/STFT buffers first, produce independently generated **initial A/B curves from the original user probe WAV**, and then connect to the known fitter skeleton. Only compare produced FIRs with official 2203/SC20 as a held-out oracle; no guessing missing math from the vendor target.

Keep existing hardware-auditioned JCM800 2203 v0.2 C and production PocketMasterStudio JS converter untouched. Windows Manager vs mobile SONICLINK identity is still unproven.
