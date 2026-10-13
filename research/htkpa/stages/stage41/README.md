# Stage41 — historical r8brain version fingerprint (offline Sonicake)

**Status: PREPARED; actual 5-version native comparison NOT RUN YET.** User-completed Stage40 has established public r8brain v7.6 FIR spectra after matching zero-phase storage format to native Sonicake: 1417 taps max abs **7.635184802110007e-14**, RMS **5.418108913456421e-15**, bit-exact **4/4096**; 1543 taps max abs **7.650661788122237e-14**, RMS **5.191640483135054e-15**, bit-exact **4/4096**. The previous unaligned ~0.0009765625 Stage40 comparison is **invalid for source-version identification**.

## Why historical versions?

Pocket Master debuted by late November 2024, and NAM/Clone support appeared around January 2025. Thus the then-current **r8brain v6.5 (7 Dec 2023)** is a prime candidate for initially imported source. However our exact original DLL PE header `TimeDateStamp` points to **29 July 2026** (not an independently authenticated compile date), when **v7.2 (27 July 2026)** had already released. v7.0 and v7.1 are also chronologically plausible if source was refreshed; do not assume v6.5 from the product launch alone.

The previous Stage39 full public convolver matched a genuine native 1972-f64 output numerically at maximum error 2.402592014227878e-16 but 0/1972 exact. A version comparison is a diagnostic, not a solved provenance problem.

## Exact pinned source revisions

| Tested release | First release | Git commit | API |
| --- | --- | --- | --- |
| v6.5 | 2023-12-07 | `3c930bf6825c0cfea4a813210c83b1a650c820b5` | `getLPFilter` 5 arguments; old `r8bbase.cpp` linkage |
| v7.0 | 2025-12-18 | `a7d812d3153b0fda845db9fc0498e78d7337d0f0` | 5 arguments |
| v7.1 | 2025-12-28 | `1ad3b3707b9339a7144b301752318bbb902220d2` | 5 arguments |
| v7.2 | 2026-07-27 | `8fff6f3db26f14a8f5e8fb871000613673db5753` | 5 arguments |
| v7.6 | 2026-09-30 | `cb2abb9977efe2471979b380ed95daa56ab4fdb9` | 6 arguments |

The version-adaptive probe calls **real open-source** `CDSPFIRFilterCache::getLPFilter()` to generate and read each public `getKernelBlock()`. The packed public values have been passed through `convertToZP()`; private original raw `coeff_post_fft` spectrum is converted to exactly this same representation before comparison. Both 1417/1543-tap configurations are independently checked (4096 f64 each).

## Run on WSL — NO new Sonicake Manager or Frida

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python research/htkpa/stages/stage41/audit_versions.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --source-cache research/_LOCAL_FILES/stage41_r8brain_git \
  --out research/_LOCAL_FILES/stage41_historical_fir_report.json
```

The script initially downloads public r8brain Git history once into an **ignored, bare source-cache repo** (so first run requires internet). Exact commit SHA checks are mandatory, then sources are extracted only into temporary folders and compiled via C++17 `-O2 -fno-fast-math`. Builds of older releases also link `r8bbase.cpp` where present. Re-running reuses source cache. Original native FIR arrays stay only in ignored local ZIP and temporary memory, never in Git.

If you prefer the smaller private ZIP, replace the `--native-zip` value with `research/_LOCAL_FILES/stage40_native_fir_fixtures.zip`. Both have previously been verified to contain exactly the same native data.

## Acceptance and how to read results

Expected output records the filter geometry and per-version **max error, RMS, 8192 total f64 bit-equal count**, hashes of generated *public* spectra, and a numerical ranking. `COMPLETED` requires that all five historical versions build and both filters are comparable.

Do **not** infer original vendor revision merely because one Linux-compiled candidate has the smallest RMS; different FFT backends, compiler optimizations, source modifications or portability revisions can all produce differences. If the early v6.5 coefficients become substantially closer than v7.6 with stable FFT conventions, investigate source changes and build settings next. If differences are all similar or identical, chronological evidence remains stronger than numerical fingerprinting.

The MIT-licensed original source is https://github.com/avaneev/r8brain-free-src (Aleksey Vaneev / Voxengo). No proprietary DLL or native buffer data included in this commit.
