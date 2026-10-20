# Stage107 — raw silence-floor verification on existing Stage102 output

**Status:** `STAGE107_SOURCE_AND_SYNTHETIC_TESTS_PASS_OPERATOR_RUN_PENDING`.

This is a **read-only, offline diagnostic** of seven 20,000-frame intervals with zero candidate DI reported by Stage105, plus the neighboring bins around 1.30–1.42M and Stage106's five largest **absolute** residual-error bins. It does **not** execute Sonicake Manager, vendor DLL, Frida, NAM C++ inference, the Dart resampler, FIR fitting, create CLO, access a device, or change production.

## Why

Stage106 real operator report found a 20k-window boundary at sample 1,360,000 (28.333s) where DI RMS goes from ~0.177821 to **zero** and per-bin optimized relative residual from 1.70668% to ~0.000045856%. Three subsequent zero-DI bins printed Manager PCM16 RMS ~0.000061035, open NAM Core RMS ~0.000204393 and a **locally fitted** multiplier ~0.298616879. The Manager RMS is numerically consistent with 2/32768 (two PCM16 steps), but neither the sample sign nor **constancy** can be inferred from RMS alone.

Stage106 showed **7/60 zero candidate-DI bins**; the five largest absolute gain-corrected RMS residuals were all in quieter **nonzero** candidate-DI bins near RMS 0.001, rather than in the zero-DI intervals. These operator observations are checkpointed in Stage106 `SILENCE_BIN_OPERATOR_FOLLOWUP_20261021.md` and RE_LOG. None of this is vendor resampler parity.

## What the tool actually checks

1. Read Stage102's **already existing** ignored `comparison_private.json`; require the accepted Stage102 status, 1.6M f64 frames and vendor-unverified input-resampler flags.
2. Read Stage105's `stage105_error_topology_private.json` and Stage106's `stage106_metrics_audit_private.json`; verify their statuses, Stage106's SHA256 of the exact Stage105 JSON, and all 60 20k windows' offsets and DI RMS values.
3. Rehash the original Stage102 open-resampled input f64le and prewarm-OFF upstream NAM C++ output f64le against the original SHA256 recorded by Stage102. Verify the Stage97 original ZIP's exact SHA / expected WAV layout via the existing Stage102 auditor. Original files are read-only.
4. For each zero-DI 20k bin, **verify all input f64 samples are numerically zero**. Calculate the Manager saved WAV's signed PCM16 histogram (top 5 counts), number of distinct PCM16 sample values, mean/std/RMS, and the open NAM Core output's mean/std/RMS/min/max.
5. Compare a locally fitted zero-lag scalar and **a separately reported fixed 0.31 multiplier** between the existing outputs. These fits are *diagnostic only*, not discovered proprietary parameters. Also inspect the six neighboring bins [1,300,000,1,420,000) and Stage106's top five absolute residual bins with the same measurement method. No lag/interpolation/DC fitting is secretly applied.
6. Save just one **private** report `research/_LOCAL_FILES/stage102/<private_run>/stage107_silence_floor_private.json`. Refuse overwrite. Terminal returns a bounded subset (zero-DI bin means/std/PCM16 histograms, selected active-bin residual percentages). Raw PCM/f64, model hashes or vendor files remain out of GitHub.

If Manager silence bins are truly near constant +2 PCM16 steps and open outputs nearly constant with a small nonzero level, a fitted scalar may artificially yield negligible RMS error despite that scalar differing from the **~0.31 in active windows**. The tool is deliberately meant to test that **hypothesis**, not assert it before the operator run. Strong similarity under zero DI does **not** establish vendor output parity or fitter correctness.

## Operator WSL

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python3 -m unittest discover -s tools -p 'test_htkpa_stage107.py' -q
python3 research/htkpa/stages/stage107/GO.py \
  --stage102-report 'research/_LOCAL_FILES/stage102/29abbdbf982ee64b_stage102_open_sonicmaster_di_resample_v1/comparison_private.json' \
  --stage97-zip 'research/_LOCAL_FILES/CLO_10-19-26-0253.zip'
```

If `stage107_silence_floor_private.json` already exists, the script refuses to overwrite; do not delete prior evidence merely to rerun. Test coverage: **13/13 synthetic local PASS**, including strict report SHA, fake end-to-end fixture, sample-index validation, signed PCM16 histogram, nonfinite guard, and no-overwrite. **Real operator results are PENDING**. Private report can be used for later hypothesis design; do not update Stage107 status based solely on synthetic results.
