# Stage45 — original Sonicake first FIR → public r8brain fractional interpolation

**PREPARED, NOT YET USER-RUN.** Stage43 demonstrated source-compiled historical r8brain `CDSPBlockConvolver` reproduces the original first FIR output to max `8.673617379884035e-19` on 1972 f64; Stage44 tested the full PUBLIC 44100→48000 chain with 2680 original input f64. v6.5/v7.2 public full outputs were 1067 f64 and **byte-identical**, independent of source chunk size (64/512/2680). v7.6 differed by `9.377454325207313e-15` maximum absolute and `3.879522442760983e-16` RMS. None of this establishes native vendor fractional or final-output parity.

## Why this gate?

Now that we know the first native FIR output independently, we can give exactly those **1972 vendor-produced f64 samples** to the real public r8brain `CDSPFracInterpolator` and see how different the completed 48-kHz *PUBLIC* samples become compared with feeding the original 2680 input samples to the public FULL resampler.

This is the narrowest useful next offline experiment before attempting any new original DLL capture. It separates `PUBLIC FIR -> PUBLIC fractional` from `VENDOR FIR -> PUBLIC fractional` while holding the public fractional implementation fixed. It measures propagation of upstream FIR rounding differences through the next stage. It **DOES NOT** directly compare against `VENDOR FIR -> VENDOR fractional`, because a corresponding real vendor final 48-kHz buffer has not been found in prior captured archives.

Stage45 compiles pinned MIT source versions **v6.5**, **v7.2**, **v7.6** with two independent C++ executables:

1. Existing Stage44 `public_resampler.cpp`: public `CDSPResampler(44100.0, 48000.0, 2680, 2.0, 180.15, linear_phase)`, 2680 f64 source, one complete call.
2. Stage45 `hybrid_fractional.cpp`: public `CDSPFracInterpolator(88200.0, 48000.0, 180.15, false, 0.0)`, exactly 1972 original native FIR f64, processed in chunks **64**, **512**, **1972**.

Stage45 computes output lengths, chunk invariance, SHA-256 and max/RMS/bit-equal comparison for hybrid versus public full output and among versions. It refuses unverifiable vendor input: source FFT history and Stage33 first 2048 f64 must match, and native FIR output must match the successful Stage35 capture bytewise. Raw original/public generated audio is transient inside a temporary directory and is never committed.

## WSL command (offline relative to Sonicake)

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python research/htkpa/stages/stage45/audit_hybrid.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --stage33-archive research/_LOCAL_FILES/frida_captures/frida_20261013_143414_395162.tar.gz \
  --stage35-archive research/_LOCAL_FILES/frida_captures/frida_20261013_144322_324693.tar.gz \
  --source-cache research/_LOCAL_FILES/stage41_r8brain_git \
  --out research/_LOCAL_FILES/stage45_fractional_hybrid_report.json
```

This reuses the bare pinned public source cache created at Stage41 and existing private reference archives. No Manager, Frida, new original conversion, or production changes required.

## Source/validation boundaries

Existing user-supplied `stage23w_native(1).zip` contains 4096-f64 intermediate FFT buffers and native first-FIR snapshots, but not a separately verified original vendor post-fractional 48-kHz waveform. Other available Frida archives observed so far capture first-stage FIR input/copy and small engineering metadata. **Absence means 'not found among the inspected known captures', not proof that the DLL cannot produce it.**

Interpretation:

- If output counts disagree, investigate streaming initial state/latency and do not align by searching for arbitrary shifts.
- If hybrid and full public match numerically, first-FIR differences are small enough to propagate harmlessly under *public* fractional interpolation; this does not establish native fractional equality.
- Exact or near-exact hybrid v6.5-v7.2 equality supports the pre-v7.6 public reconstruction baseline, but cannot date embedded vendor source.
- If any compile or fixture integrity check fails, report it rather than declaring parity.
- Full Sonicake NAM→CLO matching still requires its original NAM fitting and CLO model serialization; audio resampling is just one part.

Public r8brain copyright Aleksey Vaneev / Voxengo, MIT. No proprietary DLL, NAM, CLO or original waveform attached to Git commits.
