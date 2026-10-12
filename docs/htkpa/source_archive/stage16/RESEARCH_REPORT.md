# HTKPA Stage 16 — workspace SSA and exact fit-loop wiring

**12 October 2026. Source-first investigation of the user's Windows Sonicake Manager `5868USB.dll`.** Read-only static disassembly. No vendor DLL execution, no NAM/CLO generation, no device operations, and no edits to the production JS converter.

## Outcome

**Confirmed:** the internal `0x1800BB210` fit function allocates a single float32 workspace, copies two context curves into it, runs the Pre-FIR and Post-FIR synthesis and rendering procedures in one fixed order, calculates an in-place regularized feedback ratio between **identified scratch arrays**, and accepts/rejects candidate changes using the previously proven Mel-spaced cross-spectral loss. Both FIR backups and the working curves are part of this state machine.

**Not achieved:** exact computation of either vendor FIR from the original NAM/WAV. This stage resolves *pointer provenance and scheduling*, not the numerical internals of every called helper. Previous claims of “almost finished” must be interpreted accordingly.

## Static baseline

- DLL SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
- All virtual addresses below use `0x180000000` PE image base. Never interpret them as raw file offsets.
- Source: native GNU `objdump -d -M intel --no-show-raw-insn`; **DLL never loaded/executed**.
- The independently authored verifier pins **74 exact assembly instructions**, **9 numeric constants** and runs **22 synthetic structural/algebraic tests**. It is rerunnable with the user's own DLL at the pinned hash.

## Allocator and temporary-memory map

Let `L` be `int(context+0x20ecc)`, obtained through float conversion and truncation in this function; `P=int(context+0x20ed4)` (**Pre-FIR length**); `Q=int(context+0x20ed8)` (**Post-FIR length**); `T` the caller-provided audio-frame count; and `I` the caller-provided iteration count. The allocation arithmetic at `0x1800BB255–0x1800BB271` is:

```
float_count = 10*L + 2*P + Q + T + I
byte_count  = 4*float_count
```

All offsets below are **float32 element offsets** from the contiguous allocated base `B`, not context offsets:

| Relative offset | Region | Proven source / use |
| --- | --- | --- |
| `0…L−1` | `V0` | initial copy of `context+0x24328` (`0x1800BB289/0x1800BB342`), then bounded power update |
| `L…2L−1` | `V1` | initial copy of `context+0x24330` (`0x1800BB347`) |
| `2L…3L−1` | `V2` | copy of `V0` (`0x1800BB35A–0x1800BB363`); then curve processing and product; later denominator and in-place destination of the feedback quotient |
| `3L…4L−1` | `V3` | allocated; precise lifecycle not fully proved |
| `4L…5L−1` | `V4` | curve-conditioning output |
| `5L…6L−1` | `V5` | input data to spectral-feedback quotient; first spectral estimator receives this as an output pointer |
| `6L…7L−1` | `V6` | temporary array later passed to the interpolation/score calls |
| `7L…8L−1` | `V7` | allocated; exact writer unresolved |
| `8L…9L−1` | `V8` | allocated; exact writer unresolved |
| `9L…10L−1` | `V9` | copy of `V0` (`0x1800BB368–0x1800BB379`), then used in acceptance bookkeeping |
| `10L…10L+P−1` | temporary Pre-FIR curve | input of Pre-FIR synthesis |
| `10L+P…10L+2P−1` | saved Pre-FIR | `0x1800BB319`, `0x1800BC495/0x1800BC53F` |
| `10L+2P…10L+2P+Q−1` | saved Post-FIR | `0x1800BB325`, `0x1800BC4B2/0x1800BC55C` |
| next `T` | rendered audio | `r15` at `0x1800BB32A`; used for cross-spectral evaluation |
| final `I` | per-iteration scores | pointer at `0x1800BB33D`, written at `0x1800BC45C` |

**Important distinction:** `L` (spectrum/working-curve width) is **not automatically 512**. The **separate, 512-element Mel query array** exists in `context+0x23b28`, used at `0x1800BC3D2–0x1800BC3F9`. The included synthetic tests deliberately use arbitrary `L` values to catch accidental conflation. They are **not** measurements of the actual native runtime's spectrum width.

## Source-grounded one-iteration wiring

```
V0 ← context.curve_A
V1 ← context.curve_B
V2 ← copy(V0)
V9 ← copy(V0)

FOR each of I iterations:
    V0[k] ← clip(powf(V0[k], step * V1[k]), 0.2, 5)
    step ← step * 0.9

    CALL 0x1800B7670     # conditioned curve 1: source V0, output V2/V4
    CALL 0x1800B7670     # conditioned curve 2: source V2/V4, output V0/other buffer
    V2[k] ← V2[k] * V0[k]
    [caller-provided working array][k] /= V0[k]
    CALL 0x1800B6220     # extra nonlinear in-place conditioning: not substituted
    CALL 0x1800B7670     # conditioned curve 3
    CALL 0x1800B68F0     # synthesize working Pre-FIR (128 taps)

    CALL 0x1800B5A30     # render through current filter chain
    CALL 0x1800BE700     # asymmetric saturator
    CALL 0x1800B82B0     # cross-spectral estimator, writing result into V5

    V2[k] ← float32((1e6 * float32(V5[k])) /
                      (1e6 * float32(V2[k]) + 2^-23))
    CALL 0x1800B7670     # condition the computed feedback curve
    CALL 0x1800B68F0     # synthesize working Post-FIR (2048 taps)

    CALL 0x1800B5A30     # render updated chain
    CALL 0x1800B82B0     # evaluate against actual reference waveform
    CALL 0x1800B5D00     # interpolate onto 512 Mel-spaced Hz values
    E = mean(abs(logf(value + 2^-23)))

    if E < previous_best: save candidate work curves + both FIRs
    elif E > 1.2 * previous_best: restore saved curves + both FIRs; step *= 0.5
    else: continue without restoring

CALL 0x1800B9B70         # once after selectors 2 → 1 → 3, final Post-FIR correction
```

This is a **source-constrained control-flow reconstruction**, not runnable end-to-end DSP pseudocode: a few source/output argument roles of the **three** `0x1800B7670` calls and their overlapping scratch aliases remain partially unresolved, and the full internal computation of `0x1800B6220`, exact original source sample processing and native transforms have not been validated as one whole. In particular the division's **caller-provided working array** has not yet been assigned a physical DSP label.

### Newly pinned quotient array identities

Previous Stages 10/15 correctly established the local regularized quotient but labelled its operands `A/B`. Stage 16 traces **physical buffers**:

- In the first estimation call at `0x1800BC055`, `[rsp+0x38]` receives `rdi = V5` from `0x1800BC01D`; this pointer is passed to `0x1800B82B0`.
- `0x1800BC081` and `0x1800BC0F3` read numerator entries from `rdi = V5`.
- `0x1800BC093` loads `r10 = V2` from `[rsp+0x1D8]`; `r13 = V2` is the surviving earlier base; `0x1800BC107` loads denominator from `V2`.
- `0x1800BC12E` stores the quotient **back into the same `V2` buffer**. The scalar path at `0x1800BC210–0x1800BC316` confirms the same source/destination aliasing.
- The immediately following call at `0x1800BC33D` is the already recovered Mel/dB curve conditioner.

**Concrete correction:** the denominator is **not simply “raw auto-spectrum of waveform A”**. It is the current working array `V2`, which was initialized from `V0` and altered by prior conditioning and elementwise multiplication. No claim is made that it is a native Welch PSD. The estimator's output in `V5` is likewise not necessarily a raw complex STFT buffer.

### Source-grounded behavior of the acceptance control

Before looping, the previous score is loaded as **100.0** at `0x1800BB2A1`. The control at `0x1800BC459–0x1800BC59C` compares `E` to the saved score:

- Improved `E` → copy latest correction curve(s) and Pre/Post-FIR to saved locations.
- Worse than **1.2×** score → restore saved work curves and both FIRs and halve step.
- Otherwise → retain current candidate.

This does not assert that the optimizer's score is equivalent to sample-wise RMS error. It is the Stage-9/10 **Mel-spaced log-cross-spectrum** criterion.

## Tests, reproducibility and remaining blocker

`verify_stage16.py` executes `objdump` on the pinned DLL but **never loads it**. It checks 74 anchored instructions, 9 binary values, and 22 synthetic algebraic/memory-layout controls. The captured evidence JSON is reproducible and contains no proprietary DLL bytes or full disassembly. All tests passed on the original DLL.

**The strict previous acceptance criterion remains unmet:** no full official Pre-FIR/Post-FIR has yet been numerically reconstructed from the 70-second NAM probe. Before an end-to-end candidate can be trusted, we must resolve (a) complete argument aliasing of the 3× frequency conditioner and `0x1800B6220`, (b) native intermediate rounding and exact spectral estimators/rendering, (c) coupling between successive selector passes, and (d) final 48→44.1 kHz tap conversion. **No speculative replacement formula, no new CLO, no production changes.**
