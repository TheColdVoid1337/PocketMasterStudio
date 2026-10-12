# Sonicake HTKPA Stage 11 — Pre-FIR candidate synthesis: source-first pointer trace

**Date:** 2026-10-12  
**Source:** user-provided Windows Sonicake Manager `assets/5868USB.dll`, x64 PE image base `0x180000000`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.  
**Method:** read-only static `objdump` disassembly, pinned instruction assertions, independent tests of *isolated* proven equations, comparison with two matched official `.clo` files. **We never load/execute the DLL.**  
**Status:** partial candidate construction recovered; **not** a full NAM→CLO implementation or an exact FIR recovery from NAM/WAV.

## 1. Established caller-to-output pointer chain

This is the most important new direct finding.

| Address | Machine-code observation | Interpretation |
|---|---|---|
| `0x1800BF07C` | Loads pointer from `[context+0x24408]` | Current working **Pre-FIR** buffer |
| `0x1800BF083` | Stores Pre-FIR pointer at `[rsp+0x58]` | Fitter's Pre-FIR stack argument |
| `0x1800BF070` | Loads pointer from `[context+0x24410]` | Separate working **Post-FIR** buffer |
| `0x1800BF077` | Moves it to caller stack `[rsp+0x60]` | Post-FIR stack argument (separate from Pre-FIR) |
| `0x1800BF0C9` | Calls `0x1800BB210` | Joint optimizer |
| `0x1800BB821` | Loads `rdi=[rsp+0x1F8]` | **Pre-FIR**: callee stack offset maps to caller `+0x58` after adding 8-byte return address, 8 pushes (64 bytes) and `sub rsp,0x158` (344 bytes). Total delta `0x1A0`. |
| `0x1800BB831` | Stores `rdi` as outgoing fifth argument `[rsp+0x20]` | Destination for synthesis function |
| `0x1800BB836` | Calls `0x1800B68F0` | **Actual overwriting of current Pre-FIR candidate** |

This is **not inferred from a matching array size**. The source also sets both `r8d` and `r9d` from `context+0x20ed4` (the **128-tap Pre-FIR length**) at `0x1800BB817/0x1800BB81E`. It is an instruction-level trace of the actual pointer through the Windows x64 calling convention and both stack frames.

**Critical disambiguation:** An early scan confused callee stack `[rsp+0x1F8]` with caller stack `+0x60` by failing to include the pushed **8-byte return address**. The correct offset is `0x1F8 - (8 + 64 + 0x158) = 0x58` (**Pre-FIR**). This has been checked again against the separate 128/2048-tap length fields and is covered by a regression assertion.

## 2. The immediately preceding spectral candidate operations

Inside the loop of `0x1800BB210`:

- At `0x1800BB460..0x1800BB48C`, the function applies `powf` to per-element correction arrays and clips values to **[0.2, 5]**. The exponent-scale is reduced by a multiplier of **0.9** at `0x1800BB4BE`. Those bounds/decay were originally established in Stage 3; this stage validates where the subsequent routing occurs.
- Calls to **`0x1800B7670` occur three times**, at `0x1800BB4D9`, `0x1800BB4F8` and `0x1800BB812`, with different input/output pointer sets.
- Between those calls, actual SIMD multiply and divide operations occur at `0x1800BB575` and `0x1800BB6E1` on working arrays. Another filter conditioner `0x1800B6220` is called at `0x1800BB7E3`.
- Inside `0x1800B7670`, there are **two calls to Gaussian smoothing** (`0x1800B7E10`: `0x1800B7BBB`, `0x1800B7C12`) and **three calls to the already-proven piecewise-linear interpolator** (`0x1800B5D00`: `0x1800B7BF8`, `0x1800B7C4B`, `0x1800B7C8C`). Its earlier instructions transform frequency coordinates using logarithms/powers; *the exact composite mapping formula and every array's physical identity remain to be reconstructed.*

Thus source code confirms a sequence of **bounded power correction → repeated frequency-domain remapping / smoothing / interpolation → explicit Pre-FIR synthesis**. This is much more precise than attributing the effect to an arbitrary EQ shelf, but it is still not a complete candidate update equation.

## 3. `0x1800B68F0`: recovered output-array processing

The callee reads an input array of length `N` from `rdx` and an output destination from the fifth stack argument, with `r8d=N` and `r9d=M` (length of output FIR). Its operations can be separated into two categories. **This function writes the working Pre-FIR**, not Post-FIR; the distinct Post-FIR update still needs separate tracing:

**Verified scalar/array operations:**

1. **Even mirror extension excluding endpoints.** Compute transformed-array support length `L=2*N−2` (`0x1800B691F`, `0x1800B6925`). Copy the first `N` float32 values and append values in reverse from `input[N−2]` down to `input[1]` (reversed-copy loop around `0x1800B69A0`). For example, `[a,b,c,d] → [a,b,c,d,c,b]`.
2. **Spectral operations.** Call `0x1800B72E0` (`0x1800B6A16`), prepare trigonometric basis via `0x1800B52E0` (`0x1800B6A50`), and call a complex-transform helper `0x1800B47F0` (`0x1800B6A66`). Those helpers are *not* treated as fully recovered here. Stage 6 separately found minimum-phase fingerprints in official post-FIRs.
3. **Measure energy of the full transformed support.** Sum squares over **`L`** elements and take square root (`0x1800B6A85..0x1800B6B18`). Denote the norm `E_full = sqrt(sum_{k=0}^{L−1} z[k]^2)`.
4. **Truncate/copy the output** to the declared destination length **`M`** (`0x1800B6B39`): `h[k] = z[k]`, for `k < M`.
5. **Remove DC:** compute mean `μ=(1/M) sum_{k<M} h[k]` (`0x1800B6B60..0x1800B6B9D`) and subtract it from *every* output value (`0x1800B6BEB`, scalar tail also present).
6. **Restore full-support energy:** measure centered norm `E_centered=sqrt(sum_{k<M}(h[k]−μ)^2)` (`0x1800B6CA0..0x1800B6D07`), calculate `scale=E_full/E_centered` (`0x1800B6D0E`), and multiply output taps by it (`0x1800B6D52`; scalar/tail code near `0x1800B6DB8`). This assumes `E_centered` is nonzero; DLL's behavior with degenerate zero-energy arrays was not established.

The last two steps make the **internal (pre-resampling) Pre-FIR DC sum approximately zero** and restore the full spectral-work-buffer L2 norm on its shorter FIR support. They are actual operations, not hypothesized optimizations.

### Clean-room scalar sketch (NOT the whole function)

```python
L = 2*N - 2
x_mirror = x + x[-2:0:-1]
z = UNKNOWN_COMPLEX_SPECTRAL_PIPELINE(x_mirror)  # still needs native helper trace
E_full = sqrt(sum(z[k]**2 for k in range(L)))
h = z[:M]
mean = sum(h) / M
h = [v-mean for v in h]
E_centered = sqrt(sum(v*v for v in h))
h = [v*(E_full/E_centered) for v in h]
```

**DO NOT substitute a guessed FFT or minimum-phase operator for the unknown middle line** and claim exact Sonicake reconstruction.

## 4. Independent cross-check against captured Sonicake CLOs

Official Windows Manager **Pre-FIR** fields (float32 at byte offset **136**; 128 entries with 117 active samples after 48 kHz → 44.1 kHz support change):

| Same-NAM vendor file | Sum of Pre-FIR taps | Pre-FIR L2 norm | Absolute sum / L2 |
|---|---:|---:|---:|
| JCM800 2203 Crunch | `0.014214161456` | `3.231613432` | `0.00439847` |
| SC20 Full Rig | `0.005174505462` | `2.496118188` | `0.00207302` |

Both have very small DC sums, consistent with the source-confirmed subtraction of the mean and a later resampling process. **The numbers do not independently prove bit-exact mean subtraction**, because gain normalization, resampling and final serialization intervene.

## 5. Verification, limitations and next concrete source targets

- `verify_stage11.py` checks the exact SHA-256, verifies **43 pinned machine-instruction addresses**, and runs **nine self-contained scalar mathematical checks** (caller/callee stack-offset mapping, mirror length and edge convention, mean removal and energy restoration on nondegenerate arrays). The source check was run against the original DLL; it **does not run** the DLL.
- The source test was repeated; evidence JSON was identical.
- The package excludes the proprietary Windows DLL, user NAM, official WAV and official CLO captures.
- **NOT achieved:** reproduction of all output coefficients of either official Pre-FIR from NAM/WAV; the Post-FIR update and joint nonlinear-fit parameters remain separately unresolved. No new test CLO has been generated, and existing production JS code remains unchanged.

**Next DLL-first targets:** trace the argument semantics and exact operations of `0x1800B72E0` (including the invoked `0x1800B7150`), `0x1800B47F0` and the intermediate buffer transformations inside `0x1800B7670`, then independently calculate its `z[]` support for a simple synthetic curve. **The separate Post-FIR writer/update path must also be traced** (live pointer at `[context+0x24410]`, fitter stack argument `+0x200`). Only then join these equations to the native auto/cross-spectral loss from Stage 10 and demand coefficient-by-coefficient matching against both official CLOs.
