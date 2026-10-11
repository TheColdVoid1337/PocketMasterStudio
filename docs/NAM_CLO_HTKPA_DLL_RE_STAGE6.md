# Sonicake HTKPA — Stage 6: complex spectral exponentiation and minimum-phase fingerprint

**Date: 2026-10-12. Research-only; no production change or hardware writes.**

## Key finding

On **two independently captured official Windows Sonicake Manager CLOs**, the full nonzero **1881-tap Post-FIR** almost exactly matches a minimum-phase impulse response independently reconstructed from **its own FFT magnitude**. This is **not** a direct reconstruction of the vendor Post-FIR from the source NAM/WAV.

| Same-NAM CLO | Cosine of Post-FIR vs its magnitude-derived minimum-phase projection | Relative L2 error |
| --- | ---: | ---: |
| Official JCM800 2203 Crunch | **0.998563** | 0.05360 |
| Official JCM800 SC20 Full Rig | **0.999589** | 0.02867 |
| Original Void JCM800 2203 | −0.243669 | 1.57713 |
| Original Void JCM800 SC20 | −0.040724 | 1.44272 |
| Positively auditioned JCM800 2203 v0.1 refit | −0.297339 | 1.61080 |
| User-favored JCM800 2203 v0.2 C | −0.226487 | 1.56620 |

The cosine uses the **raw, aligned coefficient vectors** with no offset, sign flip, gain adjustment or phase fitting. FFT=32768, relative spectrum floor 1e-8, hmin=real IFFT of the exponential of the causal real cepstrum. On FFT sizes 8192/16384/32768/65536 the **official 2203 cosine remains 0.998515–0.998766**, and SC20 **0.999544–0.999800**. This is strong evidence of a **minimum-phase output-filter design** in the Windows algorithm, even though the exact internal implementation is still incomplete. The Pre-FIR on all six tested CLOs already gives ≈1.0 cosine against its own minimum-phase projection.

## Pinned DLL observations

User-supplied Windows `5868USB.dll` SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; base `0x180000000`. The DLL was **only statically disassembled**, never loaded or executed.

- `0x1800B73BB`: imported `logf` in the spectral-processing path.
- `0x1800B7450`: calls spectral interpolator `0x1800B5D00`.
- `0x1800B748F`: reverse-bin lookup for symmetric spectrum construction.
- `0x1800B754A`, `0x1800B7569`, `0x1800B7590`: transform, conjugate-fold, transform helpers `0x1800B4A50 → 0x1800B6E30 → 0x1800B4F60`.
- `0x1800B6EDB` adds paired real components, while `0x1800B6EEB` subtracts paired imaginary components, consistent with Hermitian conjugate folding.
- `0x1800B75D5`, `0x1800B75E1`, `0x1800B75F4`: imported `expf`, `cosf`, `sinf`; nearby multiplies and stores confirm the local complex reconstruction **`exp(a)·(cos(b)+i·sin(b))`**.
- `0x1800B5B4B`: invokes `0x1800C0F60` within fixed 64-sample block processing; exact transform conventions not yet recovered.

Together, the pinned instructions and empirical FIR fingerprint strongly **support** (but do not prove every step of) complex-log / minimum-phase spectral synthesis. Twenty exact-instruction pins are verified by a reproducible read-only `objdump` harness.

## Cross-reference with official Post-FIR, JCM800 2203

Raw cosine of each 1881-tap Post-FIR against the official Windows 2203 Post-FIR, then the same filter after minimum-phase projection **without changing its original magnitude response**:

| Source | Original cosine | Projected cosine |
| --- | ---: | ---: |
| Void baseline | −0.1932 | **+0.9622** |
| v0.1 Post-FIR refit | −0.2847 | **+0.9473** |
| v0.2 C (user's preferred hardware sound) | −0.2916 | **+0.9367** |

**This is a coefficient-comparison result, not a simulated or measured sound-quality improvement.** It highlights a phase mismatch, but the amplitude response and nonlinear gain staging still differ.

## Carefully isolated A/B candidate — NOT hardware-validated

A separately distributed experimental file `JCM800_2203_v06_MIN_PHASE_FROM_C_UNVALIDATED.clo` projects **only the first 512 physically transmitted Post-FIR taps** of the user-favored **v0.2 C** to minimum phase. It changes no Pre-FIR, saturator, DC filter or other coefficients; only those first 512 float32 taps and the derived CRC16 differ. The original v0.2 C remains unchanged.

- Same 8840-byte VTSI with valid CRC16.
- Mean transmitted-tap magnitude-spectrum deviation from C: **0.000217 dB** on a 32768-point frequency grid.
- Tap L2 before/after ~**0.343812**.
- 512-tap cosine to official Windows 2203 changes from **−0.29471** to **+0.95036** (without gain/lag adjustment).
- **No on-device audition yet.** The altered phase can change attack, group delay and feel even if magnitude response is matched. Do not assume audible benefit. Compare only on a spare user slot at reduced monitoring volume, retaining C and official SONICLINK.

## Verification / unresolved acceptance

A separate private-conversation research ZIP `Sonicake_HTKPA_DLL_RE_Stage6_v0_6.zip` contains independently authored Python cepstrum code, pinned read-only DLL verifier, **five passing unit tests**, evidence JSON, impulse-response plots, exact candidate generator and unvalidated CLO. It **does not contain** the proprietary DLL, original NAM, official WAV or official CLO captures.

**The original Stage-4 acceptance gate remains NOT MET:** no complete vendor Pre/Post-FIR has been inferred from the *input/output WAV only*. Computing an official FIR's phase **from its known vendor magnitude** cannot be presented as end-to-end vendor fitting recovery.

**Next:** trace exact Fourier and conjugate/cepstral array semantics in `0x1800B4A50/0x1800B6E30/0x1800B4F60`; then independently fit a stabilized and smoothed amplitude-response target from the 70-second NAM input/output probe to the Pre-FIR+nonlinearity output, and combine it with phase reconstruction. Evaluate coefficient error on **both** source-matched Windows CLOs and listen on-device before any opt-in browser integration. Production JS-only converter and previous positively auditioned reference are not changed.
