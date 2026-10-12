# Sonicake HTKPA Reverse Engineering — Stage 14

**Date:** 2026-10-12. **Method:** static disassembly of user-supplied Windows Sonicake Manager `5868USB.dll` using `objdump`; pinned SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. Virtual addresses assume PE image base `0x180000000`.

**Scope:** Source-first trace of the previously unknown spectral curves feeding `0x1800B7670` and of the actual working Post-FIR write in `0x1800BB210`. The DLL was **never loaded/executed**. No NAM/CLO, vendor WAV or proprietary DLL is included in this package. No device or production converter changes.

## 1. Correction to Stage 11: One shared native FIR synthesizer, two outputs

The optimizer calls **the same `0x1800B68F0`** with different lengths and destination pointers. This is not a second, wholly different Post-FIR synthesizer.

| Call | Buffer from enclosing context | Source-length / output-length arguments | Confirmed write target |
| --- | --- | --- | --- |
| `0x1800BB836` | `context+0x24408`, forwarded from fitter stack `[rsp+0x1F8]` | `context+0x20ED4` = 128, for input and output | Working **Pre-FIR** |
| `0x1800BC35C` | `context+0x24410`, forwarded from fitter stack `[rsp+0x200]` | `r14d` spectral input length and `context+0x20ED8` = 2048 destination length | Working **Post-FIR** |

**Post proof:** `0x1800BC33D` first calls curve processor `0x1800B7670`; `0x1800BC342` fetches the Post-FIR pointer; `0x1800BC34D` loads `context+0x20ED8`; `0x1800BC354` places its prepared magnitude curve in `rdx`; `0x1800BC357` places the Post-FIR destination on stack as the fifth argument; `0x1800BC35C` calls the same synthesis function. `0x1800B68F0` itself reads the input array, input/output lengths and fifth output pointer. The updated Post-FIR is then passed at `0x1800BC372–0x1800BC381` to the DSP-audio rendering helper for another cross-spectral objective evaluation.

**Correct calling convention:** Windows x64: return-address adjustment must be included when interpreting callee stack offsets. This prevents the Stage-11 preliminary Pre/Post pointer confusion.

**Caveat:** Following the three selector optimizations, a *separate* final spectral function `0x1800B9B70` is still called (`0x1800BF11E`) and can further change the Post-FIR. The two uses of `0x1800B68F0` **do not** fully account for the final vendor file.

## 2. Source of the fitting curves: unity initialization and feedback from the audio

Two pointers are allocated in the HTKPA context at:

- `0x1800BEF5B`: `context+0x24328`;
- `0x1800BEF73`: `context+0x24330`.

The first `context+0x24328` array is filled with exact IEEE-754 float32 **1.0** (`0x3F800000`, `0x1800BEF97`), and then copied into the second at `0x1800BEFB6–0x1800BEFC4`. In the following setup, **a tail portion of the second array is modified** (`0x1800BEFF5–0x1800BF03B`), so neither should be casually described as a fixed all-ones spectrum for the whole fitting session.

At the beginning of `0x1800BB210` the current arrays are copied into workspace (`0x1800BB289–0x1800BB363`). The code builds a bounded power-law correction: `powf(x, exponent)` clipped to **[0.2, 5]** (`0x1800BB460–0x1800BB48C`) before the first series of frequency-curve resamplings.

The current DSP audio and the matching NAM probe audio then feed a true spectral-ratio estimator (`0x1800B82B0`, called at `0x1800BC055` and again for scoring at `0x1800BC3C5`, as independently reconstructed in Stage 10). The intermediate arrays are combined, divided / normalized (`0x1800BC210–0x1800BC316`) and passed through another `0x1800B7670` at `0x1800BC33D` before actual Post-FIR synthesis.

Thus the source path is **not an invented target EQ curve**: unity-seeded working curves are iteratively updated using cross-spectral feedback between modeled output and reference NAM output. **Still open:** precise identities of all scratch arrays and the complete cross-spectral correction equation (including native stabilizers and weighting) through `0x1800BC055–0x1800BC33D`.

## 3. `0x1800B7670` is a magnitude-curve conditioner, not a FIR transform

The callee receives a **linear-Hz abscissa vector** in `r8`, a **linear positive magnitude** vector in `rdx`, original count `r9d`, a target count as the fifth argument, and two output arrays as later stack arguments. This is supported by the following *live instruction sequence* (not by inferred names):

1. `0x1800B7771–0x1800B77D4`: apply the Mel transform `2595 log10(1+f/700)` to source Hz endpoints and form a uniformly spaced Mel grid; `0x1800B7860–0x1800B78EC` converts it back to an Hz grid via `700 (10^(Mel/2595)−1)`.
2. `0x1800B7917–0x1800B7A95`: construct a second grid with linearly spaced Hz coordinates; it is used as the *final output frequency axis* via the output pointer loaded at `0x1800B7A73`.
3. `0x1800B7B10–0x1800B7B87`: convert positive input magnitudes to decibels, `20 log10(magnitude)`. The vector and scalar code paths are both present.
4. `0x1800B7BAB–0x1800B7BBB`: run the already identified Gaussian smoother (`0x1800B7E10`) on these **dB values**, with the width argument computed from **`trunc(0.002 × input_bin_count)`**. Importantly, this `0.002` differs from the width used in another Stage-5 Gaussian call path; the two operations must not be conflated.
5. `0x1800B7BF8`: interpolate the smoothed curve onto a Mel-spaced frequency grid through the Stage-9 `0x1800B5D00` interpolator.
6. `0x1800B7C07–0x1800B7C12`: apply a **second Gaussian** to that curve. Its width argument is `2 × trunc(input_bin_count / target_bin_count)`. The native behavior when this evaluates to zero is not yet validated; do not assume there is a fallback to an arbitrary nonzero width.
7. `0x1800B7C4B` (conditional) and `0x1800B7C8C`: remap the curve via the interpolator, finally onto the linearly spaced Hz output axis.
8. `0x1800B7CC0–0x1800B7D26`: convert the resulting decibels to linear magnitude with `10^(dB/20)`, in vector and scalar paths. The output-magnitude pointer is read at `0x1800B7C70`; the output-frequency pointer is used at `0x1800B7A73` and `0x1800B7C65`.

**This establishes the role of the earlier unknown frequency-curve arrays:** their processor performs Mel-aware resampling, *Gaussian filtering in the dB domain*, and re-mapping to the output filter's working frequency grid before using the Stage-13 complex-log FIR synthesizer. It does not produce FIR taps directly.

### Why this matters

A Gaussian applied to **dB-domain** (log magnitude) correction before a minimum-phase spectral synthesis is not equivalent to smoothing the final FIR or its final spectrum post hoc. This source-confirmed placement explains why the arbitrary Gaussian post-processing experiment of Stage 7 was not a valid test of the original DLL formula.

## 4. Recovered structural call chain

```text
HTKPA reference WAV + current modeled signal
             |               context initializes curve buffers to unity
             |                (with second curve tail later modified)
             v
  bounded power-law curve proposal (0x1800BB460)
             |
  Mel-Hz/dB/Gaussian/resampling processing (0x1800B7670, repeated)
             |
  Stage-13 complex-log spectral synthesis (0x1800B68F0)
             |                     --> Pre-FIR (128)
  render current model (0x1800B5A30)
             |
  cross-spectrum of current vs NAM target (0x1800B82B0)
             |
  additional ratio/conditioning --> 0x1800B7670
             |
  same complex-log spectral synthesis (0x1800B68F0)
             |                     --> Post-FIR (2048)
  render + Mel-based spectral score; accept or rollback *both* filters
             |
  final Post-FIR spectral processing (0x1800B9B70)
             |
  48k -> 44.1k resampling and VTSI/CLO packing (Stage 4)
```

The boxes contain only established calls and local operations. The compact arrows omit numerous scratch buffers, and *some intermediate assignments/normalizations remain unknown*. No end-to-end vendor numerical parity is claimed.

## 5. Reproducible verification and acceptance

Self-contained `verify_stage14.py` reads the SHA-pinned DLL, runs `objdump` over selected instruction ranges and checks **50 exact-address predicates** plus **seven embedded numerical constants**. It includes **16 independent elementary tests** of Mel/dB scalar transformations and window-size arithmetic. Two runs generate byte-identical evidence JSON. **Tests of elementary transformations are not tests of the full algorithm.** The DLL is never loaded or executed.

**Stage-4 strict acceptance still NOT MET:** we have not computed the full vendor Pre-FIR or Post-FIR from the original input/output WAV. No experimental CLO was produced: this stage is about actual native data flow, not parameter guessing. No automatic production changes.

### Next source-first target (Stage 15)

1. Annotate *every* scratch buffer produced between `0x1800BC055` and `0x1800BC33D`. Recover the exact cross-spectrum-to-correction equation, including `0x1800B6220` and constants, with precise buffer identities and clipping.
2. Reconstruct `0x1800B7670` in a bounded synthetic case with its **two Gaussian passes in the correct dB/Mel order**, and verify buffer boundaries and native float32 conventions.
3. Analyze final `0x1800B9B70`, because it modifies the Post-FIR again after the shared synthesizer. Only then attempt full FIR coefficient reconstruction from two paired NAM/probe sessions.

Preserve the previously hardware-auditioned JCM800 2203 v0.2 C. Do not ship or inject partially reconstructed mathematics into the browser JS-only converter.
