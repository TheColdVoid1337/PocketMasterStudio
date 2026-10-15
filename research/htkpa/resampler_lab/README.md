# HTKPA Resampler Lab — independent Python + C++ tool

A deliberately small offline utility for testing **the two specific Sonicake
audio resampling paths** reconstructed in research Stages 58–66. This is *not*
NAM inference, FIR fitting, CLO writing, or the entire NAM→CLO converter.
Production browser code and the experimental WASM integration are untouched.

## Verified modes

| Mode | DSP | Original Sonicake numerical evidence |
|---|---|---|
| `reverse` / `96000-to-44100` | Fractional 96,000 → 44,100 Hz | 114 native Float64 output samples, Stage66 |
| `forward` / `44100-to-48000` | FIR + fractional 44,100 → 48,000 Hz | 1067 native Float64 output samples, Stage66 |

Underlying code: MIT r8brain v6.5 pinned commit
`3c930bf6825c0cfea4a813210c83b1a650c820b5`, exact
original DLL-derived **Kaiser Beta 12.55262798 / Power 1.51553897**,
24 taps and 673-position quadratic fractional interpolation.
Stage66 independently verified the C++ bridge's native sample accuracy,
chunk invariance, and bit-identical reset replay. These 1181 samples do NOT
establish numerical parity for arbitrary rates, WAV durations or the full CLO.

## Quick start in Linux/WSL

Requires Python 3, Git, and `c++` / g++, plus the already existing local
Stage41 r8brain git cache. No new pip dependencies, no Emscripten, no Frida.

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
python -m unittest discover -s tools -p 'test_htkpa_resampler_lab.py' -v
cd research/htkpa/resampler_lab
python GO.py build
python GO.py status
```

`build` extracts an exact SHA-pinned MIT source commit into a **temporary**
directory, applies the already validated Stage63 constructor parameters,
compiles Stage66's C++ library, checks its ABI and produces:
`research/_LOCAL_FILES/resampler_lab/libhtkpa_native_frac.so` and `build.json`.
Both are Git-ignored; no proprietary binaries or captured audio are copied.
If necessary: `python GO.py build --source-cache /path/to/your/stage41_r8brain_git`.

### A WAV you can listen to

```bash
python GO.py convert \
  --input /path/to/mono_44100.wav \
  --mode 44100-to-48000 \
  --output /path/to/result_48000.wav \
  --report /path/to/result_48000.json
```

`--mode auto` is the default and accepts only 44,100 or 96,000 Hz input.
Input: uncompressed PCM WAV **8/16/24/32 bit**, mono/stereo.
Output: PCM **24-bit** WAV with reported quantization/clipping count.
IEEE-float WAV is NOT supported; convert it to PCM WAV or raw f64le first.
Existing output files are never overwritten without `--overwrite`.

### Raw Float64 and exact-index comparison

```bash
python GO.py convert \
  --input /path/to/input_96000.f64le \
  --rate 96000 --channels 1 --chunk 256 \
  --mode 96000-to-44100 \
  --output /path/to/result_44100.f64le

python GO.py compare \
  --actual /path/to/result_44100.f64le \
  --reference /path/to/native_44100.f64le \
  --max-rms 1e-14 \
  --report /path/to/comparison.json
```

`.f64le` is **raw interleaved little-endian IEEE754 double**, with no header.
`compare` requires the same number of f64 samples in both files; it **never
auto-aligns**, shifts, normalizes, or modifies them. It reports RMS, peak
absolute error, relative RMS, SHA256 and exact 8-byte matches. Use only
same-input, same-index references. Exit code 3 means the optional RMS
limit was exceeded; exit code 2 signals an error.

Chunk sizes may be `1..2680` input frames. Each stereo channel owns its own
independent C++ state. WAV rates/channels come from its header; raw input
requires explicit `--rate` and `--channels`.

### Latency and the end of the file

This Lab intentionally performs **no implicit FIR latency compensation or
tail flushing**. Short WAVs can produce fewer output samples than the nominal
rate ratio because the FIR filter accumulates inputs first. For an explicit
test you can append known zero samples:

```bash
python GO.py convert --input test_44100.wav --output padded_48000.wav \
  --pad-input 4096
```

This adds actual input zeros and records the count; it does NOT trim them or
prove Sonicake's final-file flush policy. For strict native comparisons,
prefer unpadded f64le and the original call geometry.

## Files and isolation

- `GO.py`: `build` / `status` / `convert` / `compare`.
- `build.py`: pinned MIT source cache, transient compilation, SHA/ABI manifest.
- `resampler.py`: streaming PCM/Float64 I/O, per-channel state, exact comparison.
- `tools/test_htkpa_resampler_lab.py`: offline synthetic tests.
- Existing C++ source: `research/htkpa/native_compat/htkpa_native_frac_bridge.cpp`.
- Native numerical evidence: Stage66 `audit_bridge.py` and its private reports.

Keep all generated binaries, captured samples, local source caches and outputs
PRIVATE, preferably inside the ignored `research/_LOCAL_FILES/` tree.
