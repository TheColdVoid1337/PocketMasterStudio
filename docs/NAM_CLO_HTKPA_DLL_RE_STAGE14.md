# Sonicake HTKPA Stage 14 — common Pre/Post FIR writer and Mel/dB conditioning

**2026-10-12 | source-first DLL research, not a converter change.**

All findings come from read-only static disassembly of the user-supplied Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. VAs below assume PE image base `0x180000000`. The DLL has not been executed or redistributed. No user NAM/WAV/vendor CLO or commercial code is committed; no pedal slots touched.

## Major finding: one shared synthesizer writes BOTH FIRs

The Stage 11 identified function `0x1800B68F0` is not exclusive to Pre-FIR. Within the three-selector optimizer `0x1800BB210` it is called twice:

| Purpose | Call VA | Destination | Output taps |
| --- | --- | --- | ---: |
| Pre-FIR | `0x1800BB836` | fitter stack `[rsp+0x1F8]`, i.e. `context+0x24408` | `context+0x20ED4` (128) |
| Post-FIR | `0x1800BC35C` | fitter stack `[rsp+0x200]`, i.e. `context+0x24410` | `context+0x20ED8` (2048) |

Post-FIR proof is specific: `0x1800BC33D` invokes frequency-curve conditioner `0x1800B7670`, `0x1800BC342` loads the Post-FIR pointer, `0x1800BC34D` loads its target length, `0x1800BC354` supplies the prepared curve, `0x1800BC357` supplies the destination as fifth Win64 argument, and `0x1800BC35C` calls **the same synthesizer**. The resulting Post-FIR is then used by the current-DSP rendering helper at `0x1800BC381` for another objective evaluation.

**Qualification:** a separate finishing function `0x1800B9B70` still runs at `0x1800BF11E`, after the three optimization stages. Its complete action on Post-FIR has not been reproduced. Thus the common writer is a confirmed **working**-filter path, not the complete final CLO algorithm.

## The unknown input curves have a concrete initialization

`0x1800BEF5B` and `0x1800BEF73` allocate the two correction arrays at `context+0x24328` and `context+0x24330`. The first is filled with float32 **1.0** (`0x3F800000`, `0x1800BEF97`) and copied to the second (`0x1800BEFB6..0x1800BEFC4`); **the tail of the second array is subsequently modified** in `0x1800BEFF5..0x1800BF03B`. Both arrays are copied into fitter workspaces at `0x1800BB289/0x1800BB347`. One working curve receives the bounded `powf` correction before being conditioned.

This is an initialized, iteratively adjusted correction-curve system, **not an independently inferred fixed EQ**. Further cross-spectrum feedback is computed through `0x1800B82B0` at `0x1800BC055` and `0x1800BC3C5`, and an intervening ratio/conditioning stage is visible at `0x1800BC210..0x1800BC316`. Full scratch-buffer provenance remains to be verified.

## New mathematics and purpose of `0x1800B7670`

`0x1800B7670` is a **magnitude-curve conditioner**. Its source arguments include **linear Hz frequency coordinates** (`r8`), **positive linear magnitude values** (`rdx`), source point count (`r9d`) and target count (fifth argument). It returns a target frequency grid and conditioned gain/magnitude curve. The input/output pointer roles are grounded by direct call register/stack tracing.

Confirmed native operations in order:

1. `0x1800B7771..0x1800B77D4`: transform Hz endpoints into Mel via `2595 log10(1+f/700)` and construct Mel-uniform grid; inverse map `700(10^(mel/2595)-1)` at `0x1800B7860..0x1800B78EC`.
2. `0x1800B7A95`: construct target **linearly spaced Hz** axis; output frequency-axis pointer at `0x1800B7A73`.
3. `0x1800B7B14/0x1800B7B19` and scalar `0x1800B7B75/0x1800B7B7A`: magnitude **to dB**, `20 log10(magnitude)`.
4. `0x1800B7BAB..0x1800B7BBB`: first Gaussian smoothing on the dB curve; width set to `trunc(0.002 × input_bin_count)`. Exact double constant **0.002** resides at `0x18024C640`. Do not conflate it with the smoothing width in other HTKPA functions.
5. `0x1800B7BF8`: piecewise-linear interpolation onto the Mel-spaced Hz working grid (Stage 9 function `0x1800B5D00`).
6. `0x1800B7C07..0x1800B7C12`: second Gaussian smoothing, width argument `2 × trunc(input_bin_count / target_bin_count)`. The zero-width edge case has not been independently reproduced.
7. `0x1800B7C4B` (conditional), `0x1800B7C8C`: final remappings onto target linear-Hz coordinates.
8. `0x1800B7CCE` vector and `0x1800B7D1C` scalar: return **dB to linear magnitude** via `10^(dB/20)`.

The curve may then feed the shared Stage-13 minimum-phase-like spectral FIR synthesizer `0x1800B68F0` for either 128 or 2048 taps. Source-first evidence establishes this *placement* of Gaussian operations: Stage 7's generic smoothing of the finished spectrum is **not** an implementation of this DLL path.

## Exact acceptance and limitations

Separate user-facing archive `Sonicake_HTKPA_DLL_RE_Stage14_v0_14.zip` contains a clean-room, read-only verifier and report, **50 pinned instruction addresses**, **7 embedded constants**, **16 isolated math tests**, and reproducible evidence JSON. The same SHA-pinned DLL yielded byte-identical evidence on two runs; the archive excludes the DLL and reference media. No live DLL execution.

**Still NOT achieved:** full Pre-FIR or Post-FIR coefficient parity from the reference NAM input/output WAV on either Marshall. No source-grounded complete equation for `0x1800BC055..0x1800BC33D` or the final `0x1800B9B70` post-FIR stage; full `0x1800B7670` buffer/index/float32 parity is also pending. No auditory claims, no experimental CLO and no changes to the production browser JS converter.

**Stage 15 source-first priorities:** trace every temporary in the feedback-to-Post-FIR ratio after `0x1800BC055`, validate both Gaussian passes on tiny positive synthetic arrays against the pinned native branches, and then reverse the final `0x1800B9B70` spectral correction. Only afterwards attempt two-model vendor FIR reconstruction. Retain the user-approved JCM800 2203 v0.2 C as hardware control.
