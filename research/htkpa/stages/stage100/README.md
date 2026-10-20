# Stage100 — source-first signal-level × chunk-boundary sweep

**Status:** `STAGE100_CONTROLLED_LEVEL_AND_CHUNK_SWEEP_HARNESS_TESTED_OPERATOR_RUN_PENDING`.
No vendor DLL, CLO fitter, browser production or actual hardware is accessed.

## Why

Stage99 produced an **operator-reported** real paired NeuralAmpModelerCore vs
existing SonicMaster Dart WaveNet result for the same private Marshall model,
8192-frame stimulus, model rate 48000 Hz, load/reset prewarm off, max slimmable
child. RMS error `2.2696525484244864e-08`, normalized RMS `2.733829451264937e-07`,
max abs `1.5437486166475223e-07`. **Not bitwise equal**, not vendor DLL parity.
One level with 64-frame native blocks does not establish robustness to nonlinear
drive or streaming boundary conditions.

Stage100 runs the **same compiled real upstream C++ and the same compiled
SonicMaster diagnostic worker** as Stage99 — no additional DSP algorithm,
private model, vendor capture, resampler, or fitter. Inputs are deterministically
scaled from the Stage99 known SHA source, with no gain correction when comparing
outputs. All four level sets use the exact same 8192-frame mono f64le timeline.

| Level name | Input scale | Meaning |
|---|---:|---|
| `quiet` | `0.1` | Small-signal operating point |
| `reference` | `1.0` | Reproduce Stage99 nominal amplitude |
| `drive` | `2.0` | Larger-signal nonlinear response |
| `inverted` | `-1.0` | Asymmetric amp response / sign reversal |

For each level SonicMaster processes one whole 8192-frame causal sequence;
NAM Core processes the same input with block sizes **16, 64, 1024** (all
load/reset prewarm off, max slimmable selection `--slim 1.0`). **12 real NAM
Core runs + 4 SonicMaster runs**. The report includes RMS, max absolute and
normalized RMS error for each pair, plus reference block64 ↔ block16/block1024
chunk-boundary invariance. No lag alignment, best-fit gain, resampling or
normalization is applied to either output. The initial-state algorithms remain
distinct; any differences must be interpreted, not automatically labeled bugs.

## WSL operator commands

Use the existing Dart SDK 3.13.6, Node v24 and real Stage98 binary; the Stage99
worker is already compiled in ignored `_LOCAL_FILES`:

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python3 -m unittest discover -s tools -p 'test_htkpa_stage100.py' -q
python3 research/htkpa/stages/stage100/GO.py doctor \
  --model 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam'
python3 research/htkpa/stages/stage100/GO.py run \
  --model 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam'
```

The run writes original raw inputs, 16 outputs and `sweep_private.json` into
ignored `research/_LOCAL_FILES/stage100/sweeps/<model-hash-prefix>_48k_scale_block_v1_<mode>/`.
Send the **terminal summary** for interpretation; optionally upload the full
private JSON to canonical Google Drive `RE_HTKPA`, **never commit** the `.nam`,
original `.clo`, raw `.f64le`, or full private report to public GitHub.

`doctor` is read-only. `run` refuses to overwrite a previous sweep, verifies
both pinned build manifests, original upstream checkout and private Dart worker
SHA, and writes an `IN_PROGRESS` marker until all 16 runs finish. If any real
C++/Dart operation fails, leave that directory intact for investigation — do
not delete outputs automatically or claim successful parity. A final
`COMPLETED` marker and JSON summary mean both engines ran, **not** numerical
agreement or Sonicake DLL equivalence.

If node/Dart/backend or original model changes, re-check the Stage99 and Stage98
build manifests before proceeding. Stage99 model gating requires a 48-kHz
`WaveNet` or specifically ordered max-slimmable WaveNet container. Other NAM
architectures are not silently coerced.

## Evidence boundaries

- Stage99 real comparison is operator console evidence; raw sample bytes have
  not been independently rehashed by the assistant.
- Synthetic Stage100 tests validate orchestration/math/pinning only, not
  compiled native/Dart numeric parity. No real Stage100 sweep claimed until
  operator WSL results arrive.
- No vendor numeric parity, no reverse-engineered Sonicake fitter, no
  generated CLO, no device-state readback.
