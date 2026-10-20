# Stage99 — source-first matched WaveNet inference: NAM Core vs SonicMaster

**Status:** `STAGE99_MATCHED_RAW_COMPARISON_HARNESS_TESTED_NATIVE_PAIR_PENDING`.

The operator has **already** compiled pinned public NeuralAmpModelerCore and run the
real JCM800 8192-frame Stage98 probe. Stage99's goal is a *falsifiable numerical
comparison of two independent implementations of the same WaveNet*, **not**
Sonicake's closed fitter, resampler, or hardware output.

## Why a special diagnostic worker is necessary

The existing production `src/assets/nam_dsp_worker.js` only accepts the
SonicMaster `probe`/`finish` workflow. That workflow **resamples** its fixed
44.1-kHz DI to 48 kHz, scales it through fit levels, computes long whole-track
WaveNet results, and runs FIR fitting. It cannot be compared sample-for-sample
against the Stage98 short mono f64le probe.

Stage99 compiles a **diagnostic-only** Dart worker from a private *copy* of the
actual existing MIT-licensed `tools/nam_js/clo_dsp.dart`, with one additive
public wrapper around its existing **private `_parseModel` / `_runWavenet`**
functions. No new WaveNet inference algorithm is written. Source anchors fail
closed if the underlying SonicMaster implementation changes. The worker accepts
exactly 8192 raw mono IEEE-754 float64 frames, with **no DI resampling, no
probe-level scaling, no FIR fitting, no CLO writing**. The existing production
Dart source, compiled production JavaScript, and production NAM→CLO converter
are unchanged.

The NAM Core C++ bridge also gets an **experimental Stage98 cold-start fix**:
`nam::DspLoadOptions.prewarm` now reflects `--prewarm` *at model-loading time*,
not only `SetPrewarmOnReset` before the explicit final Reset. This prevents
load-time prewarm contaminating a purported cold-start comparison. Because the
bridge changed, the earlier WSL Stage98 build-manifest hash **will fail closed**
until the operator explicitly reruns `GO.py build`. The original Stage98
operator-built binary SHA stays preserved in the old Stage98 report.

## Inputs / alignment contract

| Dimension | NAM Core | SonicMaster |
|---|---|---|
| Model | Exact same private `.nam` bytes | Exact same private `.nam` bytes |
| Selected model | `SlimmableContainer`: `--slim 1.0` selects final child; plain `WaveNet`: no slim | SonicMaster `_effectiveModel()` chooses highest-max child |
| Model rate | **48000** Hz, checked from model | Hardcoded 48000 Hz, zero resampling |
| Stimulus | Exactly Stage98's deterministic 8192-frame f64le input | Byte-identical input |
| Initial state | Explicit load/reset prewarm **off** | Whole-sequence causal zero padding, no prewarm |
| Processing | 64-frame chunks | Entire 8192-frame sequence |
| Output | Raw mono f64le | Raw mono f64le |
| Evaluation | sample index aligned, no lag optimization or compensating gain | same |

Different implementation state/streaming mechanics may still cause a measured
mismatch. Such a mismatch is valuable evidence **not an automatic bug in either
codebase**. Report RMS error, max abs, normalized RMS, mean error, RMS per output,
index of largest error and exact SHA hashes. Do not assert numerical equivalence
until a real paired result is independently inspected; do not infer proprietary
Sonicake DLL parity or CLO success from agreement between these two open engines.

The deterministic stimulus must have Stage98's real operator SHA256:
`f54ab8b3d61cd8d36fafa316f6542f18ede669febd88901b7c974b299de7745e`.

## Operator WSL commands

Dart SDK **3.10 or newer** is needed only to compile the *diagnostic*
SonicMaster worker; no Dart installation or network is performed by the scripts.
Use your existing `dart` if present (e.g. a Flutter SDK provides it). If it is
missing, install the current Dart SDK using official instructions:
https://dart.dev/get-dart . Prefer adding the official APT source or an existing
local SDK over an untrusted third-party installer. Check `dart --version` before
running `prepare`.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python3 -m unittest discover -s tools -p 'test_htkpa_stage98.py' -q
python3 -m unittest discover -s tools -p 'test_htkpa_stage99.py' -q
python3 research/htkpa/open_nam/GO.py doctor
# This REBUILDS the changed Stage98 loader and its new SHA manifest.
python3 research/htkpa/open_nam/GO.py build

dart --version
python3 research/htkpa/stages/stage99/GO.py prepare
python3 research/htkpa/stages/stage99/GO.py compare \
  --model 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam'
```

If `dart` is not available, finish at `dart --version`, install the SDK, and
resume from `prepare` (no need to repeat clone, full DLL reverse engineering,
Frida or the successful Stage98 source checkout). If CMake fails, inspect the
locally shown compiler error; `GO.py` only stores sanitized public evidence.

Results are **private** under
`research/_LOCAL_FILES/stage99/comparisons/<model-sha>_48k_cold_<mode>/`:
`stimulus.f64le`, `nam_core.f64le`, `sonicmaster.f64le`, C++ provenance, and
`comparison_private.json`. Runs refuse to overwrite any existing comparison.
Both the generated Dart worker and patched Dart source remain under ignored
`research/_LOCAL_FILES/stage99/sonicmaster_build/`, never vendored to GitHub.
A successful comparison CLI report may contain model SHA and output hashes;
**send it privately**, and do not publish raw model/audio content.

## Accepted evidence and limitations

- Source: [NeuralAmpModelerCore pinned
  `0b3d3c97...`](https://github.com/sdatkinson/NeuralAmpModelerCore/tree/0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842)
  and repository-owned SonicMaster Dart (`tools/nam_js/clo_dsp.dart`, MIT
  attribution at `docs/third_party/SONICMASTER_LICENSE.txt`).
- Stage98 operator: original 8192-frame upstream real inference has already
  completed, but **different settings** (default prewarm/on) may have been used.
  Stage99 intentionally executes a new matched no-prewarm pair.
- Test suite validates deterministic input SHA, model/child selection gates,
  metrics, strict no-overwrite, diagnostic-source anchors, and a **synthetic**
  Node worker. It cannot validate the real Dart compiled DSP or true numeric
  parity until the operator runs `dart compile js` on the source copy.
- Stage97 WAVs contain other processing and different channel/rate formatting;
  they are not direct numerical goldens for this experiment.
- No Frida hooks, vendor DLL, device calls, or Ghidra needed for this stage.
