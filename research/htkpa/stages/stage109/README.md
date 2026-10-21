# Stage109 — fixed `floor(0.31 × open_NAM × 32768)` residual topology

**Status:** `STAGE109_OFFLINE_FLOOR_TOPOLOGY_TESTED_OPERATOR_PENDING`. **15/15 local synthetic Python tests PASS in the restored assistant container**, including a fake integrated original-report SHA gate and no-overwrite check. Real operator Stage109 execution is still pending.

## Why this experiment is warranted

The operator independently compared four explicit integer-output encoders (nearest-even, floor, truncation toward zero, ceiling) with the original SHA-pinned Stage97 Manager output PCM16. On **late active nonzero DI** [1,100,000–1,500,000) excluding 60,000 zero-DI frames, **floor** matched **98.60235%** of 340,000 frames, versus 55.10912% nearest-even. The floor RMS integer residual was 0.22370 LSB; mean signed 0.00022 LSB; by sign, exact rates were 98.80081% on positive open-output values and 98.37610% on negative ones. **Early active nonzero DI**, excluding 80,000 silent frames, only matched 10.48958% even with floor (RMS ~8.06338 LSB).

These numbers are **real WSL operator console observations**, not yet Stage109 results. They support a **candidate quantization convention**, not proof of Sonicake's native implementation, model bytes, resampling, true internal buffer, FIR fitter, valid CLO or hardware behavior.

## Stage109 checks

- Requires the existing private `stage108_fixed_gain_pcm16_private.json`, original Stage102/107 manifests, the SHA-checked Stage102 1.6M-frame open C++ NAM f64 output, and the SHA-pinned original Stage97 Manager 48-kHz stereo PCM16 output WAV. It enforces the Stage108→Stage102 source report SHA chain and ensures the original Stage97 ZIP is the expected artifact. **Does not call a NAM model or produce audio**.
- Compares fixed **0.31** gain + signed-PCM16 `floor` against the Stage108 fixed-0.31 `nearest_even` baseline on **every nonsilent 20,000-frame fit bin**, separating early/late and positive/negative open-output samples. All seven Stage107 exact-zero candidate-DI bins are excluded from *active-only* denominators.
- Records exact match/within-one-LSB, RMS/max/signed/absolute integer error, bounded integer error histograms and first/last mismatched late-active sample. Ranks eight late-active 20k bins by count of still-mismatched samples. The Stage108 nearest-even exact counts **must recompute exactly** after excluding the 140k previously identified silent frames, or the new run fails before writing.
- Writes exactly one **ignored** `stage109_floor_residual_topology_private.json` in the original Stage102 private run folder. Existing source reports, WAV, input and output f64 are **read-only**. Refuses to overwrite existing Stage109 results.

This audit answers whether the ~1.4% residual late-active mismatches cluster around specific signal transitions or are broadly distributed. Remaining early-stage waveform error is intentionally **not corrected** by fitting a gain or changing the original NAM/resampler. No new proprietary DLL/Frida, Sonicake Manager, NAM C++ inference, open resampling, FIR fitting, CLO generation or hardware I/O.

## Run in operator WSL

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python3 -m unittest discover -s tools -p 'test_htkpa_stage109.py' -q
python3 research/htkpa/stages/stage109/GO.py \
  --stage108-report 'research/_LOCAL_FILES/stage102/29abbdbf982ee64b_stage102_open_sonicmaster_di_resample_v1/stage108_fixed_gain_pcm16_private.json' \
  --stage97-zip 'research/_LOCAL_FILES/CLO_10-19-26-0253.zip'
```

**Do not rerun Stage102–108**. The Stage109 tool is verified only on synthetic fixtures until the operator runs it locally and reports the output. Every fit performed in earlier stages remains explicitly diagnostic; no `vendor_*_parity_verified` flag is promoted based on matching integer samples.
