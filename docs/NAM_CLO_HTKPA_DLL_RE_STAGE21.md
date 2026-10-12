# Sonicake HTKPA Stage 21 — Source-confirmed 4-parameter saturator fitter

**2026-10-12 · DLL-first, static, read-only research.** The native saturator-fitting routine `0x1800BDBE0` (end `0x1800BE6F6`) was reconstructed algebraically for ordinary finite/positive/negative, non-degenerate audio. Its **two preprocessed audio inputs from real capture WAV remain not reconstructed**, so the official four CLO nonlinear parameters **have not been independently computed**. No production JavaScript, pedal access, new CLO or commercial DLL execution.

Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; image base `0x180000000`. Original binary, NAM, captured WAVs and vendor CLOs are not committed.

## Inputs/outputs proven from calling code

At `0x1800BEDD8..0x1800BEDE4`, native calling convention: `rcx=context`, `rdx=first preprocessed audio/input`, `r8=second/reference audio`, `r9d=number_of_samples`. Fifth through eighth (Win64 outgoing stack) output pointers are `context+0x243F8`, `+0x243FC`, `+0x24400`, `+0x24404`, respectively. Four native stores at `0x1800BE661/0x1800BE676/0x1800BE682/0x1800BE68F` yield **pmax, nmax, prate, nrate**. The first two are observed reference amplitudes, not optimized jointly with the rates.

## The entire ordinary-domain local algorithm

1. Window length `S = float32(float64(float32(Fs)) × 0.1)`. Number of complete blocks `B = trunc(floorf(float32(float32(samples)/S)))`; start and end per block are `trunc(float32(i×S))`, `trunc(float32((i+1)×S))`. Native use of `floorf` established by `0x1800BDC66→0x18017E13A`, via the IAT.
2. For each block `i`, collect `X[i]=max(abs(input))`, `P[i]=max(0,max(reference))`, `N[i]=min(0,min(reference))`; let `pmax=max(P)`, `nmax=max(-N)`. Supported by `0x1800BDD80…0x1800BDECD`.
3. Allocate **4B float32 values** to form two arrays of length **2B** (`0x1800BDF12…0x1800BE16C`):

   ```text
   inputs_for_fit = [-X[B-1], ...,-X[0], X[0],...,X[B-1]]
   targets_for_fit = [N[B-1], ...,N[0], P[0],...,P[B-1]]
   ```

   The individual native stores in `0x1800BE011/0x1800BE01D/0x1800BE025/0x1800BE02E` and the scalar tail establish the array roles. The **separate symbolic pointer/address interpreter** supplied in the research ZIP traces the actual original DLL disassembly without executing it and proves the above permutation for **B=4,5,7,8,9,10,12**.
4. Find first, **one-based** `Kp` for which `P[Kp-1] >= pmax/2`; similarly `Kn` with `N[Kn-1] <= -nmax/2`. Determine initial slopes from the **earliest** `K` envelopes, with double-precision accumulators and float32 inputs:

   ```text
   slope_p = float32( Σ(i<Kp) P[i]*X[i] / Σ(i<Kp) X[i]^2 )
   slope_n = float32(-Σ(i<Kn) N[i]*X[i] / Σ(i<Kn) X[i]^2 )
   initial_prate = float32(slope_p/pmax)
   initial_nrate = float32(slope_n/nmax)
   ```

   Half-maximum tests `0x1800BE1A0/0x1800BE1E0`, OLS products/divisions `0x1800BE259…0x1800BE47A`.
5. Given the asymmetrical exponential model:

   ```text
   sat(x)=pmax*(1-expf(-prate*x)) if x>0
   sat(x)=nmax*(expf(nrate*x)-1) if x<=0
   ```

   Minimize `float32` accumulated SSE `Σ(target - sat(input))²`. Search **positive rate first** (negative rate fixed), then search **negative rate** (updated positive rate fixed). Each searches exactly nine f32 multipliers beginning with `f32(0.8)`, repeatedly `f32(float64(previous)+0.05)`, bounded by `1.2`: `0.8000000119, 0.8500000238, 0.9000000358, 0.9500000477, 1, 1.0499999523, 1.0999999046, 1.1499998569, 1.1999998093`. On equal scores the **later candidate wins**, as `comiss best,new; jb skip` only excludes strictly worse candidates. Native SSE instructions are pinned across `0x1800BE480…0x1800BE68F`.

The Python code is a **source-derived algebraic implementation**, not proven native bit parity: Windows CRT `expf` approximation, floating summation order at corner cases, zero envelopes, NAN/INF, degenerate denominators and sample alignment remain separately open.

## Tested synthetic end-to-end fitter

A 60-second **fully synthetic, already preprocessed signal pair**, Fs=1000, produces B=600 blocks, 1200-point signed paired fit. Normal-domain computed `(pmax,nmax,prate,nrate)`:

`(0.0639682636, 0.0686569139, 17.5292663574, 15.1124286652)`.

SSE falls **0.0926445648 → 0.0407116860**. The fitting parameters are *not supposed* to be identical to the synthetic signal generator's underlying asymptotic parameters: Sonicake derives the amplitudes from observed maxima, then searches only local rates.

## Independent proofs and real-source comparison gate

The source-pinned verifier passes **75 instruction predicates**, **eight original PE float/double constants** and **77 independent synthetic assertions**. Seven additional pointer/address trace tests cover array permutations. Two separate verifier runs yield byte-identical evidence JSON SHA-256 `fe1e9bcf8cc18ce8c94d260612960773ccf1c474d48ddd6d3c862854e7705658`. The ZIP integrity check passes. The DLL is only **statically disassembled** (never loaded or executed).

Two SHA-pinned official Windows Manager CLOs have been **read only** as future parity checks, not as fitter targets:

| Model | pmax | nmax | prate | nrate | Independently regenerated? |
|---|---:|---:|---:|---:|---|
| JCM800 2203 Crunch | 0.0586976074 | 0.0625180602 | 425.438965 | 356.188354 | **NO** |
| SC20 Full Rig | 0.0106169116 | 0.0126974732 | 450.926178 | 253.910919 | **NO** |

The official input DI captures are byte-identical 44.1kHz audio while Manager output captures are at 48kHz. **They cannot be fed directly into this routine as its actual inputs**: the native driver supplies two audio buffers previously processed by its own 50-tap FIR, IIR, sample-rate and alignment stages. Using the published official gains as initialization would contaminate the experiment and is forbidden by our strict gate.

**Research package**: `Sonicake_HTKPA_DLL_RE_Stage21_v0_21.zip` delivered in the conversation: `stage21_saturator_source.py`, `native_repack_trace.py`, `audit_official_reference.py`, read-only evidence, synthetic demonstration, README and full report. No DLL, NAM, WAV or CLO included.

**Stage 22 source-first gate:** independently reconstruct both **actual audio arguments** at native call `0x1800BEDE4` from captured WAV and native preprocessing (including alignment/resampling/IIR), then calculate the four real model parameters. Require held-out numerical comparison against **both** official Windows CLOs before building full Pre-FIR/Post-FIR. Do not make guessed sound tweaks or alter production JS. Preserve hardware-auditioned 2203 v0.2 C.
