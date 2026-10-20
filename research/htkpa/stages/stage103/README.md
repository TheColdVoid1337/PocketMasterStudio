# Stage103 — offline Stage102 gain/residual window audit

**Status:** `STAGE103_OPERATOR_REAL_GAIN_WINDOW_DIAGNOSTIC_COMPLETED` (operator WSL transcript, 9/9 tests; see `OPERATOR_RESULT_20261020.md`). This stage **does not re-run NAM inference**, Sonicake Manager, resamplers or the fitter, and **does not generate CLO**. It analyzes existing **private** Stage102 numeric outputs against the exact-SHA original Stage97 Manager output WAV.

Stage102 operator supplied real WSL data: fit-window (samples 300,000–1,500,000 of first 1,600,000 at 48 kHz) `RMS(vendor)=0.02212254891326`, `RMS(open)=0.07139748826850241`, `RMS error (unadjusted)=0.049276130906865154`, cosine=0.9999628271157859 with no gain/lag fit, both prewarm conditions same aggregates. The high cosine suggests a simple amplitude-scale difference is worth testing before changing NAM DSP or claiming its native equivalence. From those rounded aggregates alone, the expected optimum single scalar at zero lag is about `0.309839002615` and expected post-fit RMS about `0.000190747676` (0.86223% of vendor RMS). **Those are only algebraic projections, not measured Stage103 output.**

## Run after checkout

Requires the **preexisting, unmodified** Stage102 directory and the original ZIP. The script checks Stage102 private manifest and SHA256 of the candidate resampled input and both C++ output files; it separately verifies the original Stage97 ZIP SHA/allowlisted WAVs through Stage102's `authentic_wavs` function. It refuses to overwrite prior Stage103 results and constrains reads/writes to the ignored `research/_LOCAL_FILES/stage102/` tree.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python3 -m unittest discover -s tools -p 'test_htkpa_stage103.py' -q
python3 research/htkpa/stages/stage103/GO.py \
  --stage102-report 'research/_LOCAL_FILES/stage102/29abbdbf982ee64b_stage102_open_sonicmaster_di_resample_v1/comparison_private.json' \
  --stage97-zip 'research/_LOCAL_FILES/CLO_10-19-26-0253.zip'
```

For both prewarm modes, it reports a **single zero-lag least-squares multiplier** (`Manager ≈ k × open`) and RMS/max residual after applying it, on the initial 300k frames, the full fitting window (1.2M), six consecutive fit-window chunks (200k frames each), and the remaining 100k frames. The spread of chunk multipliers tests whether the scale is stationary. It also compares whole-file SHA hashes of the two C++ outputs: **identical metrics do not imply identical bytes**.

The entire detailed output goes in the ignored Stage102 run folder as `stage103_gain_audit_private.json`. Terminal summary exposes only fitted gain, normalized residual, prewarm byte identity and gain range. Raw f64 or vendor WAV/model values never go to public GitHub. Existing report and audio are read-only; no repository production files change.

## Interpretation limits

Fitting a single gain is purely **diagnostic**; it does not establish an internal Manager gain, a proven vendor resampler, shared vendor model bytes, matched NAM internal state, the causal identity of `outputFile.wav`, exact output parity, closed Sonicake fitter behavior, CLO correctness, or hardware readback. Stable fitted gain would prioritize the amplitude/normalization boundary; unstable gain calls for segmentation, signal-dependent level, source/resampler, timing or unknown processing investigation. Investigate those before claiming any proprietary DSP equivalence. No sample lag or DC offset is optimized in this phase.

Offline unit regression (`tools/test_htkpa_stage103.py`) uses synthetic signals only and provides **no real Stage103 numeric evidence** until the operator reports the private run.

## Accepted real operator checkpoint

Real Stage103 WSL output confirms fitted gain `0.3098390026147448`, post-gain RMS `0.0001907476759617998` (0.8622319% normalized), and 0.3063457959701221% fitted gain spread across six 200k-frame windows. ON/OFF files are NOT bitwise equal. Their differing index ranges and numeric RMS remain unreported. See `OPERATOR_RESULT_20261020.md` for precise provenance. Stage104 provides a bounded, SHA-gated offline localization step without re-running the original model or proprietary software. The sample-alignment and source-vs-vendor provenance disclaimers above remain fully applicable.
