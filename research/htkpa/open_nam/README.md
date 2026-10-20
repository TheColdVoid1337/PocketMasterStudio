# Stage98 — real upstream NeuralAmpModelerCore C++ integration (experimental)

**Status:** `OPEN_NAM_NATIVE_SOURCE_ADAPTER_PREPARED_OFFLINE_TESTED__UPSTREAM_REAL_BUILD_NOT_YET_RUN`.
**Production NAM→CLO is unchanged.** This stage integrates the *public* NAM model
loader and actual C++ DSP rather than recreating its network classes from PE
assembly. It does not implement Sonicake's private `startClone`/CLO fitter.

## Source provenance / license

- Exactly pinned GitHub source: `sdatkinson/NeuralAmpModelerCore`
  commit `0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842` (project docs Stage94).
- Required pinned Eigen gitlink: `bc3b39870ecb690a623a3f49149a358b95c5781d`.
- Uses upstream `nam::get_dsp()` for parsing/constructing models and upstream
  `model->process()` for inference, with optional upstream `SlimmableModel`.
- No dependency/vendor binary is added to the repository. Preserve upstream
  NAM Core MIT LICENSE, Eigen and bundled nlohmann notices when distributing
  compiled output. NAM Core source commit is a **reproducible reference**; it
  is not proven identical to the stripped code in `5868USB.dll`.
- Builds exclusively to ignored `research/_LOCAL_FILES/`, never a production
  JS/WebWorker/HTML auto-integration or hardware action.

## WSL: checkout + real build (network only for explicit Git bootstrap)

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python -m unittest discover -s tools -p 'test_htkpa_stage98.py' -v

# Explicit one-time acquisition of public source and pinned dependencies:
mkdir -p research/_LOCAL_FILES/public_sources
if [ ! -d research/_LOCAL_FILES/public_sources/NeuralAmpModelerCore/.git ]; then
  git clone --no-checkout https://github.com/sdatkinson/NeuralAmpModelerCore.git \
    research/_LOCAL_FILES/public_sources/NeuralAmpModelerCore
fi
cd research/_LOCAL_FILES/public_sources/NeuralAmpModelerCore
git fetch origin 0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842
git checkout --detach 0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842
git submodule update --init Dependencies/eigen
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod

python research/htkpa/open_nam/GO.py doctor
python research/htkpa/open_nam/GO.py build
```

`doctor` refuses the wrong revision, changed tracked NAM/JSON source, missing
MIT license, wrong Eigen gitlink or incomplete checkout. No automatic network
clone occurs from `GO.py`; `build` compiles original upstream C++ directly.
The build produces `htkpa_nam_probe` and a private SHA manifest.

## First real NAM inference smoke test (requires completed upstream build)

Use an existing private `.nam` on your machine (for example a verified local
copy of the JCM800 profile), without committing its contents. One command
reads **its actual `sample_rate`** and generates an 8,192-frame deterministic
mono f64le excitation and output in ignored `research/_LOCAL_FILES/stage98_smoke/`:

```bash
python research/htkpa/open_nam/GO.py smoke \
  --model 'research/_LOCAL_FILES/vendor/YOUR_REAL_MODEL.nam'
```

`smoke` refuses an unknown training rate unless explicitly specified with
`--sample-rate`, a mismatched rate, missing compiled manifest, and any existing
output path. It prints SHA and frame count; a private `.provenance.json`
records exact source binary/model/input/output identities.

For controlled existing raw input, `GO.py run` also accepts `--input-f64le`,
`--output-f64le`, `--sample-rate`, `--block`, `--prewarm on|off`, and optional
`--slim 1.0` for models implementing `SlimmableModel`. **Do not feed WAV files
into `--input-f64le`** and do not infer a sample rate from file names.

## Comparison contract / next gate

1. First verify real pinned upstream **build + one NAM load/inference** on WSL,
   and report generated private manifest/sample hashes.
2. Never directly feed the Stage97 **stereo PCM16 44.1-kHz** WAV into this
   **mono f64le** tool. Its channel policy and the model's sample rate must
   first be resolved; later a separately validated r8brain bridge can prepare
   explicit 44.1→NAM-rate input. Do not relabel or fake-resample a WAV.
3. Compare native open-source inference against SonicMaster/Stage97 separately,
   holding input signal, reset/prewarm, model slimming, chunking and timebase
   constant. Stage97 output WAV may already contain private resampling/fitting
   and cannot be treated as an unprocessed NAM golden response.
4. Stage66/67 r8brain WASM is **not automatically included** in this probe;
   its present adapter is a fractional primitive, not yet a validated full
   antialiasing 44.1↔48-kHz native chain.

No Ghidra or new Frida capture is necessary for this first source integration.
