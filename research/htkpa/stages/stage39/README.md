# Stage39 — original r8brain CDSPBlockConvolver vs native Sonicake

**Prepared, not yet compiled or user-tested.** The Stage38 public r8brain `CDSPRealFFT` gate has **PASSED numerically** on 12,288 f64 values. Stage39 escalates to the full public `CDSPBlockConvolver` with a source-reconstructed, SHA-pinned 2680-sample real input and a source-verified 1972-sample native reference.

## New independent native facts (established offline)

The original FFT input snapshots in `stage38_private_fft_fixtures.zip` have 4096 doubles each, but the first 2048 positions contain the 1340 current input doubles followed by a 708-double *previous input* region. Remaining 2048 are zero padding.

- Frame 0: `[1340 NEW SAMPLES, 708 ZERO HISTORY, 2048 ZERO FFT PADDING]`.
- Frame 1: `[1340 NEXT SAMPLES, EXACT LAST 708 FROM FRAME0, 2048 ZERO FFT PADDING]`.
- Concatenated frame0+frame1 first 1340 inputs = **2680 real input f64**. Their first 2048 f64 are **bit-identical** to the independently captured Stage33 native input.
- This 2680-f64 reconstructed private input SHA256: `9519d98a65e88f0858819a2579202768c945f9b9604ae4cd9fc656162d173acf`.
- The first 1972 doubles of native inverse-FFT frame0 are **exactly** the successful Stage35 memcpy block (SHA256 `4e80e6e12343f2b1b618e351d2ecfe5e0851993af0ee10636149f7bd6a979cb6`).

## The experiment

`r8b_convolver_gate.cpp` uses the **actual public r8brain source**, pinned to `cb2abb9977efe2471979b380ed95daa56ab4fdb9`. It creates:

```cpp
r8b::CDSPFIRFilterCache::getLPFilter(0.5, 2.0, 180.15,
    r8b::fprLinearPhase, 2.0, 1);
r8b::CDSPBlockConvolver(filter, 2, 1, 0.0, true);
```

It then submits the full 2680-f64 input and checks output size, public FIR tap count/FFT length, bit exactness, max absolute error and RMS against the 1972-f64 verified native reference.

**Crucial:** the expected block alignment and latency consumption are hypotheses to test, not facts. A mismatch is an informative **differential result**; the audit reports it and does not claim r8brain numerical parity.

## Run offline in WSL

Requirements: Stage38 private FFT fixture, local Stage33 and Stage35 Frida archives, public source from Stage30 pinned locally, C++17 compiler, Python NumPy.

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python research/htkpa/stages/stage39/audit.py \
  --native-zip research/_LOCAL_FILES/stage38_private_fft_fixtures.zip \
  --stage33-archive research/_LOCAL_FILES/frida_captures/frida_20261013_143414_395162.tar.gz \
  --stage35-archive research/_LOCAL_FILES/frida_captures/frida_20261013_144322_324693.tar.gz \
  --upstream research/_LOCAL_FILES/r8brain_src \
  --out research/_LOCAL_FILES/stage39_numeric_report.json
```

Sample contents are extracted only into a Python temporary directory, then deleted. Original DLL, media, and native sample arrays are **never committed**. The repo contains code and numerical metadata only.

**Scopes NOT proven:** final 44.1→48k output, fractional interpolation, vendor historical version, and Sonicake NAM fitting.

Upstream credit: r8brain-free-src MIT © Aleksey Vaneev of Voxengo.
