# Stage44 — first complete PUBLIC r8brain 44.1 kHz → 48 kHz pilot on original input

**PREPARED — not executed on user's WSL yet.**

## Why Stage44 rather than continuing to search r8brain release numbers?

The user ran Stage43 against six **source-compiled** public versions and provided complete evidence. Public v6.5, v7.0, v7.1, v7.2, and v7.5 each produced **1972 original FIR output samples** from **2680 original f64 input samples**, with identical metrics relative to vendor: **380/1972** samples bit-identical, maximum absolute error `8.673617379884035e-19`, RMS `2.2951391745135605e-19`. Public v7.6 instead gave **0/1972** bit-identical, max `2.402592014227878e-16`, RMS `7.738254656116845e-17`. All return codes were zero; geometry 1417-tap FIR and 4096-point FFT matched. See `../stage43/evidence.json`.

That makes pre-v7.6 source the correct **research baseline** for reconstruction. **v6.5** is the sensible historical default for 2024-era integration; the evidence cannot prove that specific embedded commit vs the numerically indistinguishable later releases. No production code is changed.

## Source-confirmed next part of public 44.1→48 pipeline

In the pinned public r8brain 6.5 `CDSPResampler.h` constructor:

- A 44100→48000 resample is neither one of the five special simple ratios, nor an integer power-of-two/three upscale.
- Since `48000 * 2 > 44100`, the public source enters the normal mixed fractional-upsampling path.
- For the stage43-matched parameters `ReqTransBand=2.0` percent, `ReqAtten=180.15` dB, `ReqPhase=fprLinearPhase`, the first processor is `CDSPBlockConvolver` **2x** (44100→88200).
- Source branching gives `c=0` for the intermediate-oversampling counter (first comparison `48000 < (44100/(1-0.0175*2))*2`); it therefore adds `CDSPFracInterpolator` (88200→48000) and no extra multirate interpolation processors.

**CAUTION:** that is the PUBLIC library pipeline for these assumed parameters, not direct proof of all embedded Sonicake code after its verified first FIR block. Capturing or comparing Sonicake's actual final 48000 Hz f64 output is still a missing reference. Reproducing public output is not vendor final-output parity.

## Offline diagnostic

`public_resampler.cpp` creates the real public `r8b::CDSPResampler(44100,48000,MaxInLen,2.0,180.15,fprLinearPhase)` and feeds the independently cross-checked original 2680-f64 input.

`audit_pipeline.py` checks input data against Stage33, original two FFT frames/history against Stage23W, first original FIR output against Stage35, and exact pinned Git revisions from Stage41. Then it builds source-compiled **v6.5, v7.2, v7.6** and evaluates their complete **PUBLIC** 44.1→48 pipeline using chunks of **64**, **512** and **2680** input f64. It only records output sample count, first-stage latency metadata, **SHA-256 of generated public output**, within-version chunking invariance and cross-version numerical differences. Temporary original/public wave buffers are deleted after each run. Output JSON has **NO sample arrays**.

## WSL command

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python research/htkpa/stages/stage44/audit_pipeline.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --stage33-archive research/_LOCAL_FILES/frida_captures/frida_20261013_143414_395162.tar.gz \
  --stage35-archive research/_LOCAL_FILES/frida_captures/frida_20261013_144322_324693.tar.gz \
  --source-cache research/_LOCAL_FILES/stage41_r8brain_git \
  --out research/_LOCAL_FILES/stage44_public_pipeline_report.json
```

**Acceptance:** `status=PUBLIC_PIPELINE_READY` means all three public C++ versions built, ran and produced numerically analyzable buffers; independently inspect `chunk_invariance` for exact or numerical equality. It does **NOT** say the final original Sonicake 48 kHz waveform was reproduced. Results will show which versions of public r8brain to adopt experimentally for reconstruction and whether chunking changes the outcome.

Avoid new two-hook Frida captures after confirmed Manager crashes. No new Sonicake execution required. All original data and public-generated audio remain only under the ignored local workspace.
