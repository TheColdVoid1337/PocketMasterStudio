# Stage43 — historical r8brain full FIR convolver against genuine vendor samples

**STATUS: PREPARED / NOT YET RUN.** Stage41 (v6.5–v7.2) and Stage42 (v7.2–v7.6) conclusively identify **v7.6 as the first tested public release producing different FIR spectra** for our two reference filters. All tested releases v6.5–v7.5 produce exactly the same packed FIR spectra **between public versions**, with joint RMS **1.3529207911675724e-19** relative to original Sonicake. Public v7.6 gives joint RMS **5.30608307059938e-15**. This does **not** uniquely date the vendor DLL's actual embedded source.

## New diagnostic question

The public FIR *spectrum* is only one part of the filter engine. The original Stage39 `CDSPBlockConvolver` benchmark, run with public r8brain v7.6, produced exactly **1972 f64** from the original **2680 f64**, with **max abs 2.402592014227878e-16, RMS 7.738254656116845e-17, bit-exact 0/1972**.

Stage43 compares the **same 2680 f64 real original input and 1972 f64 real original output**, but uses source-compiled r8brain from:

| Public version | Pin |
| --- | --- |
| v6.5 | `3c930bf6825c0cfea4a813210c83b1a650c820b5` |
| v7.0 | `a7d812d3153b0fda845db9fc0498e78d7337d0f0` |
| v7.1 | `1ad3b3707b9339a7144b301752318bbb902220d2` |
| v7.2 | `8fff6f3db26f14a8f5e8fb871000613673db5753` |
| v7.5 | `9e73d2dd59fd5b95108fdb4f590083e35758b45f` |
| v7.6 | `cb2abb9977efe2471979b380ed95daa56ab4fdb9` |

The first 2048 original inputs are checked *bit-for-bit* against Stage33; the 708-sample history against original Stage23W FFT snapshots; the 1972 original output f64 against the stable Stage35 single-hook capture. The original media buffers remain only in private, ignored paths.

The test **reuses Stage39's proven C++ benchmark source** and adapts ONLY its `getLPFilter` call at build time with a verified exact-string replacement:

- Five arguments for v6.5–v7.2.
- Six arguments for v7.5–v7.6.
- Legacy r8brain `r8bbase.cpp` linked where the upstream provides it.
- Upstream source hashes checked against Stage41 bare Git cache before build.

Both output count/geometry and numerical error/bit-equal count are recorded for each compiled release. Strict PASS means the public implementation matches original 1972-f64 output in count and within the inherited Stage39 1e-12 absolute tolerance; **bit parity is independently reported** and not required for numeric PASS.

## Run entirely offline relative to Sonicake

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python research/htkpa/stages/stage43/audit_convolver_versions.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --stage33-archive research/_LOCAL_FILES/frida_captures/frida_20261013_143414_395162.tar.gz \
  --stage35-archive research/_LOCAL_FILES/frida_captures/frida_20261013_144322_324693.tar.gz \
  --source-cache research/_LOCAL_FILES/stage41_r8brain_git \
  --out research/_LOCAL_FILES/stage43_convolver_versions_report.json
```

The public Git cache was downloaded during Stage41/42 and should already contain all required commits; the script retrieves missing public revisions only if needed. All C++ compiles and public calculations happen under deleted temporary directories; no Frida, Manager, network-to-vendor, or new original conversion.

**Expected useful result:** whether public v6.5 (and nearby legacy releases) matches genuine vendor *time-domain FIR output* more closely than v7.6. This may separate public generations based on convolution/FFT logic even if FIR spectra are identical. A closer numerical result remains a diagnostic, not proof of an exact original Sonicake version or complete 44.1→48 kHz parity.

## Scope and caveats

The same library can produce different bit patterns under Windows MSVC vs WSL GCC, including FMA use, FFT backend choice, floating-point rounding and compile options. A smaller RMS is a solid numeric observation only, and does not identify original vendor release uniquely. The Sonicake NAM-fitting algorithm, fractional resampler and final 48 kHz output are outside this gate. Never commit the raw original captures.
