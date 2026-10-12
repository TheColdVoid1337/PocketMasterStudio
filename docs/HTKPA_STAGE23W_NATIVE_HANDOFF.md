# HTKPA Stage23W — Windows-native trace handoff

**Executive result:** **NATIVE_HIT / PARTIAL.** A real Manager import reaches `0x18000C5B0` (lane path), with `filter+0x34=1`, `state+0x34=4096`, 1417 taps and phase 11. For every packed pair `k>=1`, native output is exactly `y[2k]=x[2k]*h[2k]`, `y[2k+1]=x[2k+1]*h[2k]`; all 4096 captured doubles match bitwise. The old complex conclusion was invalid: it used a pre-repacking array and an incorrect lane oracle.

**Provenance:** 2026-10-13 Asia/Bangkok; Windows 11 x64, Sonicake Manager 1.0.1, Python 3.13 x64, Frida 17.6.1. DLL SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. Preferred base `0x180000000`; retained 120-second device-connected run base `0x7ff87e390000`; `live_va = base + (static_va - 0x180000000)`.

**How to reproduce:** install Frida only under `research/_LOCAL_FILES/stage23w_native/.venv`, verify the DLL SHA, then run `research/htkpa/stages/stage23w/native_trace.py` with Manager EXE, loaded DLL, ignored output directory and `--pid <Manager PID>`. It is read-only and captures 4096-f64 arrays only after range checks. Private retained manifest: `stage23w_native/20261013_device_conversion/manifest.private.json`; it contains no dumps.

**Chronological event table:** a second, JSONL-flushed import hit `B996`, `BAC1/BAC6`, `C468/C489`, `C56E`, `C5B0`, `C668/C689`. `C5F0` was not hit. `filter_A=0x215149be050`, `filter_A+0x50=0x215145ca020`; `state_A=0x2151432f900` alternated two work buffers.

**Filter/FFT state:** private block-0 arrays exist for coefficient/input pre/post FFT, post-multiply and post-inverse (4096 f64 each). The coefficient and input post-FFT arrays are paired with the product. The later `coeff_post_fft_01` is excluded from block-1 comparison because its timestamp is later.

Native `coeff_pre_fft` has exactly 1417 significant values: indices `0..708` and `3388..4095`; the 2680 positions between are zero and circular symmetry is exact. `coeff_post_fft` matches `conj(rfft(coeff_pre_fft))` in Stage23R packed order within `4.336808689942018e-19`. Its odd pair slots are residuals below `2.71e-19`; the lane loop deliberately applies the real even slot to both components of each pair.

For both captured blocks, `after_inverse` equals `2048 * irfft(conj(after_spectral_multiply))` after unpacking the Stage23R layout. Maximum absolute errors are `8.673617379884035e-19` and `1.1926223897340549e-18`; this is native confirmation of the Stage23U inverse sign and scale.

**Observed 1–4 block flow:** one numerically paired block is analyzed; hashes and result are in `research/htkpa/stages/stage23w/native_analysis.json`. Raw arrays remain private.

Native streaming is now observed too: first block emits zero doubles; second emits 1972; later blocks emit 2680. At `C689`, first/second `state+0x84` values are 3388/708; at `C6D2` they are 2680/0. `state+0x38=708`; `state+0x54=0`, selecting direct memcpy from `state+0x78` before `C85D` swaps the two work buffers. The `C759` decimation loop is not used.

**Hypothesis table:** Stage23S lane branch, Stage23T flag lineage, Stage23U inverse source, and Stage23V block flow are **NOT_OBSERVED**. Native DLL load is **CONFIRMED**. No synthetic conclusion is promoted to native evidence.

**Open questions and next static targets:** first observe a genuine Manager conversion at exports `0x1800E1F70`/`0x1800ABEB0`. Then record flag/pointer at `0x18000C56E` and snapshots before/after `BAC1`, `C484`, `C668`, `C684`. If normal conversion cannot be made observable, derive app.so `_namConvertCloData` FFI caller ABI plus MSVC string/result and async callback objects from `ABEB0–AC0CB` and `E1F70–E2298`; do not guess a direct call.

**Verification / limitations:** `python research/htkpa/stages/stage23w/validate_native_evidence.py` validates public fields. Manager initially reported `No Device Connected`; after connection it exposed Clone Manage, but Clone Import may write to hardware and was not driven blindly. No DLL/process-memory patch, device setting change, production change, private sample or RAM data was committed.

**Links and manifest:** tracer `research/htkpa/stages/stage23w/native_trace.py`; evidence `research/htkpa/stages/stage23w/native_evidence.json`; private manifest above; research commit pending.
