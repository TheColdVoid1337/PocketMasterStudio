# Stage40 — source-generated FIR spectra vs native Sonicake spectra

**Status: prepared, WSL execution pending.** Stage39 already passed numerical comparison of the full open-source `CDSPBlockConvolver` with a native Sonicake FIR block: 1972 samples, max abs error 2.402592014227878e-16, RMS 7.738254656116845e-17, zero bit-exact samples. Stage40 asks whether the residual error originates in the publicly generated FIR filter spectrum or in FFT/convolution arithmetic.

## Scientific test

Build the real `CDSPFIRFilterCache::getLPFilter` for both documented native configurations using upstream pinned r8brain 7.6 `cb2abb9977efe2471979b380ed95daa56ab4fdb9`:

- Filter A: norm cutoff 0.5; 2.0% transition band; attenuation 180.15 dB; linear phase; gain 2.0; down factor 1; expected 1417 taps.
- Filter B: norm cutoff 0.459375; otherwise same; expected 1543 taps.
- Read each public filter's **actual packed frequency-domain kernel** by `getKernelBlock()`. Compare all 4096 `double` values with original native `coeff_post_fft_00/01.f64le.bin` in private `stage23w_native(1).zip` (group `20261013_overlap_capture/`).
- Verify original native time-domain and frequency-domain SHA-256 before comparing. Show peak scale, numerical error, exact f64 count, DC and Nyquist. Do not export any original spectrum/audio into GitHub.

## Run locally in WSL (no Sonicake Manager, no Frida)

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python research/htkpa/stages/stage40/audit.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --upstream research/_LOCAL_FILES/r8brain_src \
  --out research/_LOCAL_FILES/stage40_report.json
```

If `stage23w_native(1).zip` is not in your ignored local folder, use the same private archive previously uploaded in the conversation. Do NOT add the private file to Git.

The audit compiles `r8b_kernel_gate.cpp` from current Stage40 against the exact pinned upstream header source. It creates temporary public filter spectra then compares them to verified native captured spectra. The JSON output reports results and is safe as *numerical metadata* if no raw sample arrays are attached. This experiment does not in itself prove exact r8brain source revision, bit parity or final 44.1→48 kHz conversion.

**Gate status must remain `SPECTRAL_DIFFERENTIAL_MEASURED` until the WSL test is run.** A spectrum mismatch may arise from kernel-generation algorithm/version or FFT/compiler floating-point effects. Distinguish them with additional controls; do not assume the source version is known.

Upstream r8brain-free-src MIT © Aleksey Vaneev / Voxengo.

## If the full Stage23W ZIP is missing locally

This is exactly what happened in the user's first Stage40 WSL run: `FileNotFoundError` before comparisons started. Do **not** rerun the same missing path. Download the separately supplied private conversation artifact `stage40_native_fir_fixtures.zip` (36,435 bytes) into the Git-ignored `research/_LOCAL_FILES/`. It contains **only** the four 4096-f64 `coeff_pre_fft`/`coeff_post_fft` arrays required by this script, retaining the exact original archive member paths and their SHA256 hashes. Then:

```bash
python research/htkpa/stages/stage40/audit.py \
  --native-zip research/_LOCAL_FILES/stage40_native_fir_fixtures.zip \
  --upstream research/_LOCAL_FILES/r8brain_src \
  --out research/_LOCAL_FILES/stage40_report.json
```

For **historical vendor attribution**, also compare the pinned v6.5 source from Git commit `3c930bf6825c0cfea4a813210c83b1a650c820b5` (2023-12-07), not just the modern v7.6 source. The native DLL's PE COFF build timestamp is **2026-07-29**, so candidate v7.1 and v7.2 (released by that date) cannot be ruled out from timeline alone. Old v6.5 builds require compiling/linking `r8bbase.cpp`; this v7.6-only gate is **not yet** a multi-version historical fingerprint.
