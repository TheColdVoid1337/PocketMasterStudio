# Stage109 — fixed `floor(0.31 × open_NAM × 32768)` residual topology

**Status:** `STAGE109_OFFLINE_FIXED_FLOOR_RESIDUAL_TOPOLOGY_COMPLETED` — **real WSL operator run accepted on 2026-10-21** after `git pull --ff-only` to `2d53dc00897e0cc03dcce86fb9330c75adb1670b` and **15/15 operator unit tests PASS**. Synthetic fixture testing remains documented separately. See [OPERATOR_RESULT_20261021.md](OPERATOR_RESULT_20261021.md) for the exact measured console results and limits.

## Why this experiment is warranted

The operator independently compared four explicit integer-output encoders (nearest-even, floor, truncation toward zero, ceiling) with the original SHA-pinned Stage97 Manager output PCM16. On **late active nonzero DI** [1,100,000–1,500,000) excluding 60,000 zero-DI frames, **floor** matched **98.60235%** of 340,000 frames, versus 55.10912% nearest-even. The floor RMS integer residual was 0.22370 LSB; mean signed 0.00022 LSB; by sign, exact rates were 98.80081% on positive open-output values and 98.37610% on negative ones. **Early active nonzero DI**, excluding 80,000 silent frames, only matched 10.48958% even with floor (RMS ~8.06338 LSB).

These figures originated in the real Stage108 floor follow-up and were **subsequently reproduced in the completed real Stage109 operator audit**. They support a **candidate quantization convention**, not proof of Sonicake's native implementation, model bytes, resampling, true internal buffer, FIR fitter, valid CLO or hardware behavior.

## Real WSL operator results (2026-10-21)

The existing SHA-gated Stage109 auditor completed **once** on the operator's private original data; its ignored `stage109_floor_residual_topology_private.json` now exists on the operator's WSL workstation, **not** in GitHub or this assistant's cloud sandbox. Stage108 nearest-even active exact counts were revalidated automatically. Full findings are in [OPERATOR_RESULT_20261021.md](OPERATOR_RESULT_20261021.md).

- **Late active, 340,000 frames:** floor exact **335,248/340,000 = 98.60235%**, nearest-even exact **187,371**; **4,752 floor mismatches**, with only **462** larger than 1 LSB. Floor RMS **0.223699 LSB**, mean signed **+0.000218 LSB**.
- **Early active, 720,000 frames:** floor exact **75,525/720,000 = 10.48958%**, nearest-even exact **72,991**; floor RMS **8.063378 LSB**.
- **Leading 20k residual hotspot:** `[1340000,1360000)` has **1,700/4,752** late errors (35.77%), **91.5%** exact within that window and maximum **27 LSB**. It immediately precedes the known `[1360000,1380000)` candidate-DI-zero bin; this is a localized association, **not a proven native transition or DSP mode switch**. Other high-count windows begin at 1,480,000 (810 errors) and 1,440,000 (561).
- **Post-run 17-bin read-only follow-up:** all **462** late residuals greater than 1 LSB occur in just two 20k windows: **429** in `[1340000,1360000)` (max 27 LSB), **33** in `[1480000,1500000)` (max 4 LSB). The other 15 late active bins are exact or differ by only ±1 LSB. The excluded zero-DI bins `[1360000,1420000)` are immediately followed by **20k/20k exact** in `[1420000,1440000)`; its actual DI RMS must still be checked from already-existing Stage105 metrics before calling it a true active-input match. Full table is in [OPERATOR_RESULT_20261021.md](OPERATOR_RESULT_20261021.md).
- Native model, vendor resampler, actual internal output buffer, final gain/quantizer implementation, proprietary FIR fitter, CLO parity and hardware readback **remain unverified**. The assistant saw the operator's terminal JSON, not the underlying private raw files.

## Stage109 checks

- Requires the existing private `stage108_fixed_gain_pcm16_private.json`, original Stage102/107 manifests, the SHA-checked Stage102 1.6M-frame open C++ NAM f64 output, and the SHA-pinned original Stage97 Manager 48-kHz stereo PCM16 output WAV. It enforces the Stage108→Stage102 source report SHA chain and ensures the original Stage97 ZIP is the expected artifact. **Does not call a NAM model or produce audio**.
- Compares fixed **0.31** gain + signed-PCM16 `floor` against the Stage108 fixed-0.31 `nearest_even` baseline on **every nonsilent 20,000-frame fit bin**, separating early/late and positive/negative open-output samples. All seven Stage107 exact-zero candidate-DI bins are excluded from *active-only* denominators.
- Records exact match/within-one-LSB, RMS/max/signed/absolute integer error, bounded integer error histograms and first/last mismatched late-active sample. Ranks eight late-active 20k bins by count of still-mismatched samples. The Stage108 nearest-even exact counts **must recompute exactly** after excluding the 140k previously identified silent frames, or the new run fails before writing.
- Writes exactly one **ignored** `stage109_floor_residual_topology_private.json` in the original Stage102 private run folder. Existing source reports, WAV, input and output f64 are **read-only**. Refuses to overwrite existing Stage109 results.

This audit answers whether the ~1.4% residual late-active mismatches cluster around specific signal transitions or are broadly distributed. Remaining early-stage waveform error is intentionally **not corrected** by fitting a gain or changing the original NAM/resampler. No new proprietary DLL/Frida, Sonicake Manager, NAM C++ inference, open resampling, FIR fitting, CLO generation or hardware I/O.

## Historical operator WSL command (already executed; do not rerun)

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

**Do not rerun Stage102–109 or overwrite the now-existing Stage109 private report.** The above one-time command remains solely to preserve reproducibility. Stage109 has real operator evidence, but no `vendor_*_parity_verified` flag is promoted based on matching integer samples. Next experiment has not yet been implemented.
