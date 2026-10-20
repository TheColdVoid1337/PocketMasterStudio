# Stage102 — candidate 44.1→48-kHz resampling, open NAM vs Manager WAV (no fitter)

**Status:** `STAGE102_SOURCE_BOUNDARY_HARNESS_PREPARED_OPERATOR_RUN_PENDING`.

Stage101's real operator test established that the entire reference 70-second DI from `src/assets/nam_reference_di_44100.f32.gz` directly quantizes to the *original Manager* `nam_input_wav.wav` as **3,087,000/3,087,000** identical 44.1-kHz PCM16 frames. This closes the input-file identity question, **not** Manager resampler or NAM inference equivalence.

Stage102 compares the first **1,600,000 samples at 48 kHz** of the **original** Manager `wavs/outputFile.wav` (Stage97 exact-ZIP SHA) against the pinned real upstream NeuralAmpModelerCore C++ rendering. To produce a 48-kHz NAM input, it takes an **experimental candidate** from the actual open SonicMaster Dart `_resampleDiTo48` implementation, compiled separately to a private Dart VM executable. The original `clo_dsp.dart`, production worker, native source, Stage97 ZIP and NAM model are untouched.

### Experiment controls

- Strict source checkout/manifest gates borrowed from Stage100 preflight; original Stage97 archive is SHA-pinned (`2f96dce1ae479a93975cf6247a88a4a08c11de7ae5cab41648faa0d7902e6f46`) and inspected for two exact-layout, sample-identical stereo PCM16 WAVs (44.1 kHz input, 48 kHz output, 70 s each).
- Re-check **all** 3,087,000 reference DI samples at **zero lag/unity gain** against the Manager original 44.1-kHz input PCM16, before trying the open resampler.
- Open SonicMaster code computes 48-kHz stimulus capped at 1,600,000 frames (its `_runLen`). Each frame is saved IEEE754 f64le. 1,600,000 open NAM samples are generated independently using upstream NeuralAmpModelerCore, 64-frame blocks, max slimmable `1.0`, and both `--prewarm off` and `--prewarm on` as **separate experiments**.
- Compare to the **first** 1,600,000 frames of the authentic 48-kHz Manager output; also report the [300,000, 1,500,000) fitting window. These comparisons apply **no** lag/gain fitting, trimming, or output resampling. Store RMS/max/norm error and zero-lag cosine separately. Any unexpected discrepancy must first be investigated as candidate-resampler, model selection or runtime-state differences, **not** immediately a NAM engine bug.
- `outputFile.wav` is a vendor intermediate-file candidate; no independent native buffer identity has been established. Similar names/timestamps do not prove this WAV is byte-for-byte native NAM output of the supplied model or that the 48-kHz input fed to the vendor NAM matches the open candidate.
- The Stage97 model's byte identity is not independently recoverable from the existing ZIP; the operator must supply the same original local private JCM800 NAM used in Stage99/100 and keep hash provenance private.

### Operator WSL (after GitHub update)

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python3 -m unittest discover -s tools -p 'test_htkpa_stage102.py' -q
python3 research/htkpa/stages/stage102/GO.py doctor \
  --model 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --stage97-zip 'research/_LOCAL_FILES/CLO_10-19-26-0253.zip'
python3 research/htkpa/stages/stage102/GO.py run \
  --model 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --stage97-zip 'research/_LOCAL_FILES/CLO_10-19-26-0253.zip'
```

`run` does a private Dart VM compile; installed Dart 3.13.6 is already available in the operator's WSL. Avoid rerunning on the same input/output folder: the tool refuses to overwrite the previous diagnostic. If it fails mid-experiment, preserve the partial `_LOCAL_FILES/stage102/` folder for investigation. Do not delete it automatically.

### Evidence acceptance gate

- Offline tests validate math, format and fail-closed invariants; they **do not** render real NAM, compile Dart or prove vendor behavior.
- **No Stage102 numerical result** is claimed until the operator supplies successful `doctor` + `run` output. Only private `comparison_private.json` contains the model hash and raw-output SHA; NEVER commit the ZIP, audio, NAM model, or private JSON into public GitHub.
- Before asserting fitter numerical parity, matched original model, matched actual NAM input after *vendor* resampler, vendor NAM output provenance and output quantization must all be established. Stage102 currently supplies a source-grounded **open** candidate resampler, not the proprietary preprocessor.
- No DLL execution, Frida, actual hardware, CLO generation, production changes or background tasks.
