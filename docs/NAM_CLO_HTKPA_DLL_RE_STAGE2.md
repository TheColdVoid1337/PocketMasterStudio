# Sonicake HTKPA static reverse engineering — Stage 2 (2026-10-12)

**Scope:** user-supplied Windows `5868USB.dll`; PE disassembly and import table only. No execution of DLL, no changes to production JS-only converter, no pedal writes. Pinned SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. VAs assume PE base `0x180000000`.

## Confirmed findings

- **Exact saturator family** at `0x180028690`: when `x>0`, `Pmax*(1-exp(-Prate*x))`; otherwise `Nmax*(exp(Nrate*x)-1)`. `expf` is an import at IAT RVA `0x18B9A8` via thunk `0x18017E12E`. The actual DLL uses float32 operations in this scalar function. **Same mathematical function as our current SonicMaster-based implementation**, not necessarily same numerical fitting or rounding.
- **Four-gain fit routine** at `0x1800BDBE0`. The caller passes pointers to context `+0x243F8`, `+0x243FC`, `+0x24400`, `+0x24404`, which are the four nonlinear fields later packed into CLO. The routine bins signal amplitude statistics separately by polarity, computes nonlinear predictions and squared residuals, searches positive and negative rate scale factors over approximately **0.8–1.2 in 0.05 steps**, then writes four results (`0x1800BE661`, `0x1800BE676`, `0x1800BE682`, `0x1800BE68F`). Binning, normalization and exact optimizer are not fully reconstructed.
- **Recursive audio preprocessing** in `0x1800BD490`: two-state second-order filtering with feedback coefficient banks `+0x232F0/+0x232F8` and `+0x23318/+0x23320`, and feedforward banks `+0x232D8/+0x232E0/+0x232E8` and `+0x23300/+0x23308/+0x23310`. Arithmetic is consistent with two second-order direct-form-II sections. Their exact purpose is unknown; this is not evidence that the final CLO has IIR in place of FIR.
- **Sample-rate-specific coefficient tables** at `0x1800BC6B0`, checking 44100, 48000 and 96000 Hz. The type of filter/resampler/window represented by those tables is not yet known.
- **Three differently parameterized stages**, not necessarily coordinate-descent repetitions: at `0x1800BEE9F`, `0x1800BEEAA`, `0x1800BEEB5`, selector values **2 → 1 → 3** are stored. The dispatcher indexes distinct pointers/lengths and calls `0x1800BB210` three times. `0x1800B9B70` follows and participates in final filter construction.

## Matching reference pairs

For the **same** source models, measured nonlinear gains (little-endian float32 starting at CLO byte 104):

| NAM | Implementation | Pos Max | Neg Max | Pos Rate | Neg Rate |
| --- | --- | ---: | ---: | ---: | ---: |
| JCM800 2203 Crunch | Windows Sonicake Manager | 0.058698 | 0.062518 | 425.44 | 356.19 |
| JCM800 2203 Crunch | Void baseline | 0.207526 | 0.207998 | 764.80 | 764.80 |
| SC20 Full Rig | Windows Sonicake Manager | 0.010617 | 0.012697 | 450.93 | 253.91 |
| SC20 Full Rig | Void baseline | 0.054729 | 0.056443 | 877.18 | 1182.64 |

Gain values cannot be used alone to determine output loudness: FIR scaling and input drive differ. Mobile SONICLINK is **not proven** numerically identical to Windows Manager.

## Reproducibility / acceptance

Stage-2 standalone read-only Python verifier `verify_stage2.py` was run against the DLL both with live GNU `objdump` output and a cached disassembly. **30 static instruction checks plus expf import** passed. Evidence JSON was byte-identical in both runs. The full technical report, verifier, machine-readable evidence and gain comparison were distributed as `Sonicake_HTKPA_DLL_RE_Stage2_v0_2.zip` with the user. The proprietary DLL and captured WAV/CLO are excluded from this Git repository.

## Remaining work

Trace `0x1800BB210` (different selector-specific arrays), `0x1800B9B70` and `0x1800B82B0` until the concrete Pre-FIR/Post-FIR design equations can be independently reproduced from the matching input/output WAVs and checked against both official CLOs. Reconstruct all context coefficient initialization and exact gain-fitting normalization, then separately prototype a single-70s-probe **pure-JS opt-in** pipeline. The working JS converter and the positively auditioned JCM800 2203 v0.2 C remain untouched.

**No claim of bit-exact vendor CLO reconstruction or sound-quality equivalence.**
