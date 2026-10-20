# Stage105 — source-grounded gain / energy / integer-lag topology of existing outputs

**Status:** `STAGE105_OFFLINE_SOURCE_AUDIT_TESTED_REAL_OPERATOR_PENDING`. This is an **offline-only** diagnostic: it reads the pinned Stage97 original ZIP and existing SHA-gated ignored Stage102–104 outputs and does **not** perform new NAM inference, vendor processing, resampling, audio generation, or CLO fitting.

## Why this stage exists

Stage101 established 3,087,000/3,087,000 PCM16 match between the 44.1-kHz Manager DI and public SonicMaster reference DI. Stage102 generated a **candidate, vendor-unverified** 48-kHz resampler input with SonicMaster and compared a full-size NAM Core model's 1.6M output against Manager's 48-kHz PCM16 WAV. Stage103 showed a global diagnostic gain of ≈0.309839 and a gain-only residual of 0.862% in the fitter window. Stage104 established full prewarm ON/OFF **bitwise identity** across all fit-window frames. The user's six Stage103 windows now reveal a potentially meaningful *segment-dependent discrepancy*:

- Windows 1–4 ([300k,1100k) at 48kHz): gains ~0.309055–0.309094, relative residuals ~2.0–2.1%, Manager RMS ~0.00860–0.01209.
- Windows 5–6 ([1100k,1500k)): gains ~0.310000–0.310003, relative residuals ~0.040–0.066%, Manager RMS ~0.02339–0.04340.
- Based on the operator's rounded six individual window measurements, **~99.75% of total per-window gain-fitted residual energy comes from windows 1–4**, while these hold only ~17.2% of the reference signal energy. These are *within-window fitted-error* contributions, not a statement about global-gain-fitted residual decomposition.

These data do not prove a vendor mode switch, timing shift, different model, native resampler equivalence, noise floor, or fitter behaviour.

## Explicit diagnostic question

Is residual structure explained by: (1) input level/content; (2) differing DC baseline; (3) a small integer lag; (4) a handful of local discontinuities; or (5) none of these? This implementation deliberately does **not** choose the answer in advance.

## Checks and outputs

1. Import original Stage102 `comparison_private.json` in ignored folder, Stage103 gain JSON and Stage104 prewarm-diff JSON; confirm required statuses. Verify 48-kHz candidate input and open prewarm-OFF output against original Stage102 SHA-256, and cross-check Stage103/104 off-output identities.
2. Verify the **exact SHA-pinned original Stage97 ZIP**, read original 70s 48kHz Manager WAV, and use the first 1.6M samples (L=R checked by Stage102). No user-private raw sample bytes enter public repo or CLI.
3. On six coarse **200k-frame** blocks, report zero-lag fit gain, reference/open/input candidate RMS, residual after gain, DC+gain residual (diagnostic only), and max residual sample index. Cross-check calculated coarse gain against original Stage103 fit-block gain with tolerance 5e-9.
4. On **60 fine 20k-frame** bins, calculate local gain, manager/input energy and residual. This resolves the coarse transition only as far as fixed 20k bins allow.
5. Across every coarse block, scan integer lags **[-4, +4] samples** on the **same trimmed central 199,992 samples** for fair comparison; report whether another integer lag beats lag zero after best scalar fit. A positive lag means compare Manager sample `y[i]` to later open sample `x[i+lag]`. This is a diagnostic, not a validated native lag.
6. Never fit lag and gain silently to claim parity; all fitted values are labeled diagnostic. Never overwrite existing Stage105 JSON.

No numpy, scipy or additional dependencies; pure Python 3.11+. Script confines full private results to existing Stage102 directory and writes `stage105_error_topology_private.json` once. The terminal gives a bounded summary, not audio or original vendor model hashes.

## Operator WSL

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python3 -m unittest discover -s tools -p 'test_htkpa_stage105.py' -q
python3 research/htkpa/stages/stage105/GO.py \
  --stage102-report 'research/_LOCAL_FILES/stage102/29abbdbf982ee64b_stage102_open_sonicmaster_di_resample_v1/comparison_private.json' \
  --stage97-zip 'research/_LOCAL_FILES/CLO_10-19-26-0253.zip'
```

## Acceptance boundary

Offline synthetic tests are **not** Stage105 real evidence. No vendor NAM buffer identity, closed resampler or FIR fitting equivalence, model byte parity, produced CLO or device readback is claimed; source hash gates can verify only the artifacts they cover. Interpret the first real WSL output before planning further experiments. Do not rerun Stage102–104 or run Frida for this step.
