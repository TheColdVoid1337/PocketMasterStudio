# Stage104 — prewarm ON/OFF bitwise difference localization (offline)

**Status:** `STAGE104_OFFLINE_PREWARM_LOCALIZER_TESTED_OPERATOR_RUN_PENDING`.

Stage103's **real WSL operator** report passed 9/9 regression tests, found least-squares zero-lag gain open NAM → Manager WAV `0.3098390026147448`, corrected RMS `0.0001907476759617998` (normalized `0.008622319096669185`), and a **0.3063457959701221%** gain spread across six consecutive 200k-frame segments. Prewarm ON/OFF gave **different full output SHA hashes**, despite identical Stage102 fit-window summary metrics. The **location, magnitude and duration of the prewarm difference have not yet been determined**.

The actual private sample outputs, Stage102 `comparison_private.json` and Stage103 `stage103_gain_audit_private.json` already exist. Stage104 reads these files **offline** and does not rerun Dart, upstream NAM inference, Frida, Manager, device or the fitter. It writes only one ignored private JSON file. Original model, ZIP, WAV, CLO and raw samples must not be committed to GitHub.

## Run in operator WSL

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python3 -m unittest discover -s tools -p 'test_htkpa_stage104.py' -q
python3 research/htkpa/stages/stage104/GO.py \
  --stage102-report 'research/_LOCAL_FILES/stage102/29abbdbf982ee64b_stage102_open_sonicmaster_di_resample_v1/comparison_private.json'
```

All existing Stage102/103 files are **read-only**. The stage checks the original Stage102 manifest's exact status, input provenance, both SHA256 values for `open_nam_prewarm_off.f64le` and `open_nam_prewarm_on.f64le`, and the Stage103 report's corresponding hashes and status before analysis. It refuses to overwrite `stage104_prewarm_diff_private.json`.

The CLI prints overall mismatch count, first/last absolute differing sample indices, rms/max signed amplitude difference, plus separate summaries for [0,300000), [300000,1500000) and [1500000,1600000). The private JSON additionally includes six contiguous 200k-frame windows in the fitting interval and signed-zero-only byte mismatches. This distinguishes *byte-level* difference from *numerical* difference. No gain or lag correction is applied to ON versus OFF outputs. F64 compare stays at the exact input frame alignment.

## Interpretation limits

- If all differing samples are before index 300000, this is evidence only that prewarm affects the early sequence of this **particular** C++ run; the fit-window data could be identical. It does not prove how Sonicake Manager resets its NAM model.
- If differences occur in the fit window, Stage102 ON/OFF equal printed statistics merely reflected rounding or very small error.
- Never generalize a single 1.6M-frame model run to vendor model equivalence, proprietary native resampler matching, closed FIR fitter, numeric CLO parity, hardware readback or complete source→device transformation.
- Unit tests: **11** isolated synthetic cases, including fake Stage102/103 reports, exact SHA enforcement, no-overwrite, nonfinite samples and signed zero. **Actual operator raw-data verification is pending**.
