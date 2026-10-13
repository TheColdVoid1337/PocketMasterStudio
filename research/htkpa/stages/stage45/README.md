# Stage45 — original Sonicake first FIR → public r8brain fractional interpolation

**COMPLETED — actual user WSL run verified, 2026-10-14.** Stage43 demonstrated source-compiled historical r8brain `CDSPBlockConvolver` reproduces the original first FIR output to max `8.673617379884035e-19` on 1972 f64; Stage44 tested the full PUBLIC 44100→48000 chain with 2680 original input f64. v6.5/v7.2 public full outputs were 1067 f64 and **byte-identical**, independent of source chunk size (64/512/2680). v7.6 differed by `9.377454325207313e-15` maximum absolute and `3.879522442760983e-16` RMS. None of this establishes native vendor fractional or final-output parity.

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

## Verified user WSL outcome (Stage45)

The actual user execution returned `PUBLIC_HYBRID_DIFFERENTIAL_MEASURED`, successfully compiled and ran all public C++ versions with genuine original Sonicake first FIR output. Each public fractional interpolator generated **1067 f64** from 1972 independently SHA-verified vendor first-stage FIR samples. All chunk sizes 64, 512 and 1972 yielded exactly the same 1067 f64 within each version, verified by identical SHA256. The original input and FIR SHA256 were checked against Stage33 and the stable successful Stage35 event.

| Version | Hybrid vs whole PUBLIC output max abs | RMS | Exact f64 |
| --- | ---: | ---: | ---: |
| v6.5 | `8.673617379884035e-19` | `2.3660543527888402e-19` | 199/1067 |
| v7.2 | `8.673617379884035e-19` | `2.3660543527888402e-19` | 199/1067 |
| v7.6 | `2.3809079707781677e-16` | `7.340605368424465e-17` | 0/1067 |

The hybrid outputs generated by pinned v6.5 and v7.2 are **bit-identical to each other across all 1067 f64**, SHA256 `a6db6a9720b3c9649fdca3f9002606d65ec5fbf4968f8d5c187514077e6a0750`; whole public outputs at v6.5 and v7.2 were also mutually bit-identical, with a *different* SHA (`d1e7fde902ba117da0536ecbe1d4a4fde0a4a8918e3d02883187a8a63f27e6e1`). Thus **199/1067**, not 1067/1067, match original-FIR→public-frac vs public-FIR→public-frac for the same release: the remaining tiny discrepancy is attributable to changing first FIR inputs under the fixed public fractional stage.

v7.6 hybrid output SHA256 `594dcfc83c7e1a3bd6841c2def1f8abfecd599a35c3123fad4278ce8f5ca74db`; v7.6 hybrid vs v6.5 hybrid has 15/1067 bit-exact and max abs `9.34978006475462e-15`, RMS `3.799624143507259e-16`.

**THIS DOES NOT TEST VENDOR FRACTIONAL INTERPOLATION.** No original post-fractional 48-kHz buffer has yet been recovered, so the native-vendor-to-public 48-kHz numerical result is `NOT_TESTED_NO_VENDOR_FINAL_REFERENCE`. Next step is a targeted **static-only inspection** of the original DLL and previous captures to localize the existing vendor fractional output buffer *without* assuming a usable hook, and without triggering another two-hook crash. Do not treat this completed hybrid stage as finished NAM→CLO conversion.
