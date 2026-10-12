# Sonicake HTKPA Stage 16 — source-proven iteration workspace and feedback aliasing

**2026-10-12.** This is a static, read-only reverse engineering result from the **user-provided** Windows Sonicake Manager `5868USB.dll` (SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`). The DLL was never executed, nor is it distributed in this repository. **No production JS changes, new CLO or pedal writes.**

## Main new result

The optimizer `0x1800BB210` allocates **one contiguous float32 block** for its curves, temporary audio, backup FIR coefficients, and iteration scores. The byte allocation follows:

`4 * (10*L + 2*P + Q + T + I)`

where `L` is the working-curve length (derived from `context+0x20ecc`); `P=context+0x20ed4` is the Pre-FIR tap count; `Q=context+0x20ed8` is the Post-FIR tap count; `T` is the current audio sample count; and `I` is the optimizer iteration count. **Do not confuse L with the separate 512 Mel-spaced score queries.**

All offsets below are **relative float32 element offsets** from the allocation base `B`:

| Scratch segment | Offset | Machine-code origin / role |
| --- | --- | --- |
| `V0` | `0` | copied from `context+0x24328`, then modified by bounded power iteration |
| `V1` | `L` | copied from `context+0x24330` |
| `V2` | `2L` | copy of `V0`, working product, denominator and in-place destination of subsequent spectral feedback |
| `V3,V4,V5,V6,V7,V8` | `3L,4L,5L,6L,7L,8L` | temporary curve and spectrum buffers; importantly `V5` is the quotient's numerator source |
| `V9` | `9L` | copy of `V0`; part of candidate save/restore |
| Pre curve temporary | `10L` | `P` floats; synthesis input |
| Saved Pre-FIR | `10L+P` | `P` floats, saved/restored with optimizer decisions |
| Saved Post-FIR | `10L+2P` | `Q` floats, saved/restored with optimizer decisions |
| Rendered audio | `10L+2P+Q` | `T` floats; current-DSP output `r15` |
| Per-iteration score | `10L+2P+Q+T` | `I` floats |

Allocator and pointer pins: `0x1800BB255–0x1800BB33D`; context copy operations `0x1800BB342/0x1800BB347/0x1800BB35A/0x1800BB368`.

## Exact quotient-buffer provenance — Stage 15 refinement

The first spectral evaluator is called at `0x1800BC055`, writing through a `V5` output argument prepared at `0x1800BC01D/0x1800BC038`. The numerator reads are from `V5` (`0x1800BC081/0x1800BC0F3`). The denominator reads are from **`V2`** (`0x1800BC093/0x1800BC107`), and `0x1800BC12E` writes the resulting quotient **back into V2**. The scalar tail `0x1800BC210–0x1800BC316` agrees:

```text
V2[k] = float32(1e6*float32(V5[k]) /
                (1e6*float32(V2[k]) + 2^-23))
```

The `V2` denominator **is not simply the raw auto-spectrum of the generated audio**; `V2` began as a copy of `V0` and was subsequently transformed/elementwise-multiplied at `0x1800BB575`. The resulting quotient is then passed to `0x1800B7670` (`0x1800BC33D`) before the common Post-FIR synthesizer `0x1800B68F0` (`0x1800BC35C`). This resolves an important pointer-level ambiguity without inventing its physical DSP meaning.

## Confirmed order within one iteration

Bounded power and annealing (`0x1800BB460..0x1800BB4BE`) → three separate Mel/dB conditioning calls (`0x1800BB4D9/0x1800BB4F8/0x1800BB812`) and intermediate elementwise products/divisions (`0x1800BB575/0x1800BB6E1`) including auxiliary conditioning `0x1800B6220` → **Pre-FIR synthesis** (`0x1800BB836`) → render/saturate and spectrum evaluate (`0x1800BBB5B/0x1800BBCC9/0x1800BC055`) → quotient `V5/V2` → **Post-FIR synthesis** (`0x1800BC35C`) → second render/spectrum evaluation (`0x1800BC381/0x1800BC3C5`) → Mel score interpolation and `mean(abs(logf(v+2^-23)))` (`0x1800BC3F9..0x1800BC440`) → save/restore with `1.2×` threshold and `0.5×` step reduction (`0x1800BC459..0x1800BC5A9`).

At outer level, this executes three selectors `2→1→3` with counts `3→2→5` (proven in Stage 8), then exactly one final `0x1800B9B70` Post-FIR correction. The previous hardware-positive **JCM800 2203 v0.2 C** remains the control.

## Reproducibility and acceptance

A separate conversation artifact `Sonicake_HTKPA_DLL_RE_Stage16_v0_16.zip` includes independent read-only `verify_stage16.py`, full `RESEARCH_REPORT.md`, `README.md` and `evidence.json`. **74 exact instruction pins, 9 numeric constants and 22 structural/algebraic tests passed**, with two runs producing identical evidence JSON SHA-256 `bc778ec7ca5092b62f9f11a06a809821154fa289a9aa33d6fbb7ac22c39e5280`. It does not contain the DLL, user's audio/NAM, vendor CLO or full disassembly.

**Original acceptance gate is STILL NOT MET.** While memory provenance and the control-flow skeleton are now confirmed, native edge/alias semantics of the three conditioner calls and `0x1800B6220`, integrated rendering/STFT float32 equivalence, cross-selector state and final resampling all require more work before an independent **exact** vendor Pre-FIR/Post-FIR can be derived from the NAM/probe. No guessed fitting constants or production changes should be introduced until those blocks have source-grounded numerical tests.


## Stage 17 correction (2026-10-12): vector multiplication is NOT stored in V2

The Stage-16 prose descriptions `V2[k] ← V2[k] × V0[k]`, `V2 was ... altered by ... 0x1800BB575`, and the scratch-loop pseudocode `V2[k] ← V2[k] * V0[k]` are **incorrect**. Full Win64 caller-to-callee stack tracing shows that `0x1800BB575` writes to the **second caller-owned array**, outer `r12`, located in callee `r13=[rsp+0x1E8]`. The other vector operation at `0x1800BB6E1` writes to **the first caller-owned array**, outer `r15`, accessed through callee `rdi=[rsp+0x1E0]`. Both use the second conditioner output `V0`:

```text
outer_r12[k] *= V0[k]          # actual destination at 0x1800BB578
outer_r15[k] /= V0[k]          # actual destination at 0x1800BB6E9
0x1800B6220(outer_r15, L)   # in-place low-index geometric conditioning
```

The local `V2` scratch is still involved in the **separate** regularized feedback quotient `V2 ← 1e6*V5/(1e6*V2+2^-23)`, correctly identified later in this Stage-16 report. The two caller arrays are allocated once by the enclosing native function before all three selector calls, so the correction changes inter-pass state. See [Stage 17](NAM_CLO_HTKPA_DLL_RE_STAGE17.md) for pinned instructions, full operand-register proof and a tested isolated helper. This erratum is intentionally appended rather than silently rewriting historical observations.
