# HTKPA Stage 17 — caller-buffer alias correction and source-verified auxiliary conditioner

**Date:** 2026-10-12. **Method:** static disassembly of the original user-supplied Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. No DLL execution, pedal operations, new CLO or production converter edits.

## Important Stage-16 erratum

Stage 16 misassigned the vector multiplication at `0x1800BB575` to local scratch `V2`. Full caller/callee Win64 stack tracing proves otherwise. The outer `0x1800BE830` allocates three arrays (outer `r15` at `0x1800BEE33`, `r12` at `0x1800BEE3F`, `r13` at `0x1800BEE4B`) before the three fitting calls. It passes them at caller stack `+0x40/+0x48/+0x50`, corresponding to callee `[rsp+0x1E0]/[rsp+0x1E8]/[rsp+0x1F0]` (accounting for the 8-byte return address, eight register pushes, and `0x158` frame bytes).

After initial curve-conditioning calls `0x1800BB4D9` and `0x1800BB4F8`, which write local `V2` then `V0` respectively, the **native vector instructions actually perform**:

```text
outer_r12[k] = float32(outer_r12[k] * V0[k])   # 0x1800BB575, stores at 0x1800BB578
outer_r15[k] = float32(outer_r15[k] / V0[k])   # 0x1800BB6E1, stores at 0x1800BB6E9
```

The subsequent `0x1800B6220` (call at `0x1800BB7E3`) modifies **outer_r15**. This updates caller-owned arrays carried between selectors **2→1→3**. It is incorrect to silently substitute a local scratch update. `V2` remains the correct **destination of the separate later feedback quotient**, as proven in Stage 16.

## Newly decoded `0x1800B6220`

The source-defined length of the low-index modifier is computed from the current audio sample rate `Fs` and spectral curve width `L`. Native context initialization at `0x1800B5865..0x1800B5887` stores `0.5*Fs` and its reciprocal at `context+0x20EC4/0x20EC8`. A fixed **60.0f** (`0x18024CD60`) is passed at the call site `0x1800BB7D2`.

```text
K = trunc(sqrtf(float32(float32(60.0f * (1.0f/(0.5f*Fs))) * float32(L))))
```

For regular positive finite arrays and `1 < K < L`, exact source-derived operation order is:

```python
a[0] = sqrtf(a[0] * sqrtf(a[0] * a[1]))
for i in range(1,K):
    a[i] = sqrtf(a[i] * sqrtf(a[i-1] * a[i+1]))
```

**All reads are in-place:** `a[i-1]` uses its *updated* value and `a[K]` is read as a lookahead. For `K<=1`, the DLL skips processing; unproven negative/NaN/`K>=L` cases are not guessed. `sqrtf` thunk `0x18017E170` resolves via imported `api-ms-win-crt-math-l1-1-0.dll` to `sqrtf` at IAT `0x18018BA38`.

Examples derived from the formula, **not claims about actual HTKPA L**: Fs=48k and L=1000 gives K=1; L=2500 gives K=2; L=10000 gives K=5. The 512-point Mel evaluation grid is a separate array and **must not be confused with L**.

This precisely closes one earlier unknown helper, without inventing the missing full curve conditioning.

## What Stage 17 actually tested

Standalone Python verifier `stage17_source_first.py` matches **64 exact native instruction addresses**, **5 binary constants**, and passes **23 synthetic math/alias tests**. Two independent runs of the verifier produced identical JSON evidence SHA-256 `9b0220696c674bca8a496d19a191a3e085bc352f886d882055baee5d57fd241b`. It uses `objdump` to read the file, **never loads or executes it**.

A separate **read-only two-model coefficient-parity gate** `vendor_parity_gate.py` checks VTSI length, CRC16-Modbus, pinned original Windows Manager SHA-256 and Pre/Post-FIR layout:

| Model | Official reference SHA-256 | Official pre sum | Official post sum | Independent synthesized candidate |
|---|---|---:|---:|---|
| JCM800 2203 Crunch | `50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7` | 0.014214 | 0.002959 | **not yet available** |
| JCM800 SC20 Full Rig | `2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a` | 0.005175 | 0.006035 | **not yet available** |

The gate therefore reports **`NOT_TESTED` for both exact coefficient comparisons**. It will measure max absolute error, relative L2 error, cosine similarity, and exact float32 equality separately for 128 Pre and 2048 Post taps, **only after an independently computed candidate exists**. It never uses vendor coefficients as fitter targets. Reference proprietary files are not distributed.

## Exact remaining blockers

The explicitly requested **complete single-pass native-equivalent fit, the combined 3→2→5 iteration schedule and exact coefficient parity with both Windows Manager CLOs are NOT achieved**. In particular:

- Initial shared caller arrays are prepared by **`0x1800BC6B0`**, still to be independently reconstructed.
- All buffer aliases, special Gaussian edge cases, knot ordering and float32 arithmetic of the three **`0x1800B7670`** frequency-conditioning calls have not been reproduced together on a native-equivalent synthetic input.
- Native DSP render, cross-spectrum normalization, score/rollback state transitions and 48→44.1-kHz tap rate conversion are not yet validated end-to-end.
- Windows Manager vs mobile SONICLINK identity remains unproven.

**Next Stage 18:** source-first reconstruct `0x1800BC6B0` and exact bounded `0x1800B7670` synthetic return arrays. Connect these to the now proven caller-array mutations and low-index conditioning, then proceed to the first whole Pre-FIR candidate. Do **not** introduce a guessed conditioner or false “bit-exact” assertions.

The self-contained user research ZIP `Sonicake_HTKPA_DLL_RE_Stage17_v0_17.zip` contains only new Python source, report, README and evidence; no original DLL, proprietary NAM/audio, or CLO. Existing user-auditioned JCM800 2203 v0.2 C remains untouched; production browser JS unchanged.
