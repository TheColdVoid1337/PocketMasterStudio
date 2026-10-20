# Stage100 — real operator matched scale/chunk sweep (2026-10-20 Bangkok)

**Evidence type:** operator-provided real WSL terminal transcript. These are not synthetic test outputs; the assistant has **not independently read or rehashed** the 16 raw audio results or the private `sweep_private.json`.

**Observed:** `STAGE100_PREFLIGHT_PASS`, then `STAGE100_OPERATOR_REAL_SWEEP_COMPLETED`, 12 pinned upstream NeuralAmpModelerCore C++ runs + 4 compiled SonicMaster Dart-to-JS runs; 8192 mono f64le frames at 48000 Hz for each run. One private Marshall SlimmableContainer model with highest-quality child `1.0`, no load/reset prewarm, no resampling, no fitting, no device or vendor DLL use. NAM Core block sizes 16, 64, 1024. Stage100 test suite ran **10/10 PASS** on operator WSL.

| Input condition | Scale | C++ vs SonicMaster RMS | Max absolute error | Normalized RMS | Core block outputs identical? |
|---|---:|---:|---:|---:|---|
| `quiet` | `0.1` | `9.24405732487544e-08` | `5.34527971447762e-07` | `1.47811597326655e-06` | yes (16=64=1024) |
| `reference` | `1` | `2.26965254842449e-08` | `1.54374861664752e-07` | `2.73382945126494e-07` | yes (16=64=1024) |
| `drive` | `2` | `1.81145930707784e-08` | `1.10960976639624e-07` | `2.19061877824059e-07` | yes (16=64=1024) |
| `inverted` | `-1` | `2.54518452131389e-08` | `2.74099154325136e-07` | `3.06802226428664e-07` | yes (16=64=1024) |

For each condition the error figures were **identical** for NAM Core block 16, 64 and 1024; compared directly, all three C++ outputs were **bitwise identical** (`rms_error=0`, `max_abs_error=0`, `bitwise_equal=true`). The C++ and SonicMaster outputs themselves are **not** claimed bitwise identical. Their maximum reported normalized RMS error across these conditions is `1.4781159732665519e-06` (quiet, about `0.000147812%` of Core output RMS). The 0.1-level normalized error is about 5.41× that at 1.0.

Reused SHA-pinned C++ executable: `ddcb3880286b7457896032309930d1385c4391c93dde3188d991f77beae07dad`.
Reused compiled Dart diagnostic worker: `a72b0abead39288f60c1ab4723d7b2c5b0f4e5e6e4a8b221e2cf60e9be04c0f7`.
The original reference input, private model identity/hash, scaled input and output file hashes and full per-run sample buffers are **not published**; the canonical private RE_HTKPA folder carries the console-derived detailed report. Original operator WSL `_LOCAL_FILES/stage100/sweeps/.../sweep_private.json` has **not** been independently checked in this assistant session.

## Scope boundary

This falsifies chunk-dependence for *these* 8192-frame mono stimuli/block sizes/model/mode. It does **not** establish general chunk invariance for any model or other initial-state handling, all input levels, all time horizons, low-noise behavior, or other architectures. Numerical closeness between two public WaveNet implementations does **not** prove matching the Sonicake `5868USB.dll` executable, internal fitter, CRC/HW state, or any true CLO conversion. All fields `vendor_dll_parity_verified=false` and `clo_generated=false` remain.

**Engineering decision:** no reason to rewrite SonicMaster's network numerical core for *these observed cases*; prioritize boundary between public NAM inference and proprietary Sonicake fitter. Widen independent test coverage selectively before modifying production, not by manufacturing equivalence claims.
