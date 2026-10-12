# Sonicake 5868USB.dll — HTKPA Stage 9

**2026-10-12 · Source-first proof · No vendor DLL execution · No production changes**

## Scope and result

We statically disassembled the **user-provided Windows Sonicake Manager DLL**, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, targeting `0x1800B5D00`, the producer of the 512 float32 values scored inside `0x1800BB210`. This report distinguishes **assembly-proven math** from interpretation. All VAs assume image base `0x180000000`. The DLL itself was never loaded or run.

**Main finding:** the score buffer comes from **piecewise-linear curve interpolation onto a fixed 512-point perceptual / Mel-like frequency grid from 80 to 10,000 Hz**. The grid and interpolation formulas are recovered independently of Sonicake files. This is **not** a reconstruction of its final FIR coefficients.

## Finding A — exact provenance of the 512 query frequencies

The initializer around `0x1800BFE2E..0x1800BFEF3` generates two arrays of 512 float32 values:

1. `context+0x23328` — **linearly spaced Mel-coordinate** values, via helper `0x180027DB0`. At `0x1800BFE50` / `0x1800BFE6C`, DLL calls imported `log10f` on arguments **`1 + 10000/700`** and **`1 + 80/700`**, multiplying results by **2595**. The lower/upper Mel endpoints are approximately **121.956 and 3073.221**.
2. `context+0x23B28` — corresponding **Hz** query array. Its first float is set directly to `80.0` (`0x1800BFEB0`). For indexes 1..510, the DLL calculates `700 * (powf(10, mel[i]/2595) - 1)` (`0x1800BFEC0..0x1800BFEEA`). The last float (`context+0x24324`, 511th index) is set to **10000.0** (`0x1800BFEEC`). Constants 700.0, 2595.0, 10.0 and 1.0 are read from the DLL `.rdata`.

The grid is 512 bins **Mel-uniform**, not Hz-uniform. A clean independent double-precision reference implementation yields first bins 80, 84.0075, 88.0356 Hz; bin 256 ≈2196.36 Hz; final bin 10000 Hz. End-to-end DLL generation uses float32 and repeated additions, so the reference values should not be described as bit-exact reproductions.

Call `0x180027DB0` (`0x1800BFE85`) is a linear-array filler: start, end and n arguments; it sets the first/last explicitly and fills intervening values by repeated float32 addition. This is confirmed by `0x180027DBE`, `0x180027DCA`, `0x180027E4E`.

## Finding B — exact source of the score values

At the call site `0x1800BC3D2..0x1800BC3F9` in `0x1800BB210`:

| Argument | DLL register / stack | Meaning proven by callee |
| --- | --- | --- |
| `rcx` | `rbx` | context pointer (not consumed by this interpolation routine) |
| `rdx` | `rbp` | source **abscissa** float32 array `a[]` |
| `r8d` | `r14d` | number of source points `n` |
| `r9` | `[rsp+0x1A0]` | source **ordinate** float32 array `b[]` |
| arg5 | `context+0x23B28` | **512 Mel-spaced Hz queries** `q[]` |
| arg6 | `0x200` | number of query points: 512 |
| arg7 | `r13` | destination float32 array `v[512]` |

The previous operation at `0x1800BC3C5` calls `0x1800B82B0` and forwards output pointers later supplied as `a[]` and `b[]`. **Exactly which physical/spectral quantity `a` and `b` represent has not been proven** and remains the next source-tracing target.

`0x1800B5D00` allocates a pair of temporary float arrays, then for consecutive source knots builds:

\[
 s_i = \frac{b_{i+1}-b_i}{a_{i+1}-a_i}, \qquad c_i = b_i - s_i a_i .
\]

The last slope is copied from the preceding segment. For each `q[j]`, it scans input knots and selects the **smallest nonnegative residual** `q[j]-a[i]` (`0x1800B6040..0x1800B60DF`). For increasing knots this is the **greatest a[i] not exceeding the query**. If such a knot exists, the output is

\[
 v[j] = s_i q[j] + c_i.
\]

If no source abscissa is less than or equal to the query, the function writes the sentinel **FLT_MAX ≈3.4028235e38** (`0x18024CE08`), not a measured input value. This is confirmed by `0x1800B5FEB` and `0x1800B60FB..0x1800B60FE`. Out-of-range queries greater than the final knot are handled by **extrapolation using the last slope**, not clamping. Zero-width / nonmonotonic source knot handling is *not* validated in the clean-room replica; the source routine does not visibly guard division by zero.

The compiled function is manually unrolled over four entries; the equation above reproduces the visible scalar operations for valid increasing knots. This does **not** imply bit-exact float32 matching on edge cases.

## Finding C — score and optimization meaning

Immediately after `0x1800B5D00`, `0x1800BC410..0x1800BC440` calculates:

\[
 E = \frac{1}{512} \sum_{j=0}^{511} \left| \ln(v[j]+2^{-23}) \right|.
\]

This makes the **mathematical preference for a value of approximately 1** clear, provided `v` is finite and positive: `ln(1)`=0. It is reasonable to call it a *unit-response deviation score*, but **not yet demonstrated** that `v` is a direct filter magnitude, transfer function ratio or pre/post filter cascade response. Its ultimate physical meaning depends on tracing the `a[]` and `b[]` values from `0x1800B82B0`.

Stage 8 already proved the save/revert control flow: strict score improvement saves both Pre-FIR and Post-FIR; worsening exceeding 20% rolls both back and halves the exponent update. This stage now supplies the missing **interpolated, Mel-spaced source of that score**. It does not establish the complete candidate-generation equations.

## Reproducibility

The original Python verifier `source_first_stage9.py` performs **38 exact machine-instruction address checks**, extracts **9 literal float32 constants** from their pinned PE VAs, and runs **7 isolated synthetic mathematics checks**. The DLL hash is fail-closed. Two repeated runs produce identical evidence JSON. The research ZIP excludes proprietary binaries, audio captures and vendor CLO.

Representative independent grid values (not asserted bit-exact to DLL):

| Mel-grid index | Approximate frequency, Hz |
| ---: | ---: |
| 0 | 80.000 |
| 1 | 84.008 |
| 10 | 121.014 |
| 100 | 602.135 |
| 256 | 2196.36 |
| 511 | 10000.000 |

The printed values can be regenerated by the contained script. Do not use the table as evidence about Sonicake *output amplitude*—it describes **query frequencies only**.

## What remains unknown — strict acceptance gate still open

- The exact source and interpretation of abscissa `a[]` (`rbp`) and ordinate `b[]` (`[rsp+0x1A0]`) provided by the immediately prior `0x1800B82B0` call.
- The mathematical identities of the intermediate curves adjusted at selectors 2→1→3, and how the filter-tap arrays influence them.
- A complete, clean numerical reconstruction of either vendor Pre-FIR or Post-FIR solely from the matching input/output probe WAVs.
- Equivalence of Windows Sonicake Manager to mobile SONICLINK.

**Next:** instrument static pointer-flow from the outputs of `0x1800B82B0` back to `0x1800B5A30` and the spectral operations in `0x1800BB210`, establishing precise `a[]`/`b[]` array semantics before attempting any new fitting. **No speculative CLO candidate was created; production Void Mod and the user-preferred 2203 v0.2 C are unchanged.**
