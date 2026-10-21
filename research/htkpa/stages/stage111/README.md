# Stage111 — candidate-DI cessation and active-input GT1 event audit

**Status: `STAGE111_OFFLINE_EVENT_BOUNDARY_AUDIT_COMPLETED`**, real cloud assistant original-source audit (2026-10-21 Bangkok). Independent **12/12 synthetic tests PASS**; real Stage110 private 200-bin report independently rechecked against the SHA-validated original Stage97 Manager PCM16 and Stage102 NAM f64 + candidate resampled DI. No new NAM inference, resampling, native binary, proprietary fitter, export, or hardware access.

## One falsifiable question

Of the **429** Stage110 late `|predicted_floor − Manager_PCM16| >1 LSB` errors in the 20k parent bin `[1340000,1360000)`, how many occur **after** the final nonzero sample of the previously generated *candidate* 48-kHz DI? Does the other hotspot `[1480000,1500000)` also behave like an input-zero tail?

## Method

1. Read original Stage97 ZIP and exactly seven existing private Stage102–109 inputs through the **published Stage110 source SHA/status/member allowlist gate**. Read the **already completed private Stage110 200-bin report**; independently re-evaluate all 200 1k bins and require exact integer mismatch and GT1 counts and candidate DI-nonzero sample counts.
2. Quantize the original open-C++-NAM-f64 at fixed diagnostic `0.31` with signed-saturating `floor(x * 32768)`; compute signed `candidate − Manager` integers, not fitted gain, lag or DC.
3. Recheck original Stage110 parent hotspot totals **429** and **33** large errors. Verify the last nonzero candidate DI frame was **1,344,016** and the remainder of that parent 20k interval contains exact zero DI; distinguish error counts before and after it.
4. Aggregate 64-frame windows at both hotspots plus quiet/loud control phases; store individual >1 LSB sample coordinates only in the **ignored private** result. The public operator summary reports counts, windows and diagnostics only.
5. Write exclusively to caller-provided private result path; reject any existing output.

## Real observations

- Of the **429** `GT1` events in `[1340000,1360000)`, **21** precede or occur at the last nonzero DI frame **1,344,016** and **408** come **after** it, during *candidate-DI-exact-zero*. First/last event frame: **1,343,968 / 1,345,228**. The after-zero portion therefore spans **1,212 sample index steps ≈25.25 ms** from first zero frame to last large residual, although it is not continuously above threshold throughout.
- For **1,000 frames immediately after DI zero**, **392/1000** exceed 1 LSB, RMS **2.858146 LSB**, maximum **16 LSB**, and **0 nonzero candidate DI samples**. In the subsequent 1000 frames, **16/1000** exceed 1 LSB, RMS **0.723878 LSB**, max **2**. This is compatible with different zero-input response/tail evolution, not proof of vendor NAM state or resampler implementation.
- In a 200-frame second hotspot window `[1488000,1488200)`, **32** exceed 1 LSB (max **4**, RMS **1.151086 LSB**) with **200/200 nonzero DI samples**. Both adjacent `[1487800,1488000)` and `[1488200,1488400)` have **0** large errors despite fully nonzero DI. A separate single large event in the 20k parent was previously localized to frame **1,480,801**.
- Two 2,000-frame reference controls `[1300000,1302000)` and `[1460000,1462000)` have **zero** large residuals.

## Limits

The first hotspot is **associated with** cessation of the candidate source-resampled DI. This does not establish that proprietary Sonicake uses that exact resampler or input buffer, nor prove native NAM model bytes, state, output gain/quantizer, fitter, CLO or hardware parity. The second hotspot occurs under nonzero DI, so one single silence explanation is inadequate. 64-frame bin metrics and full event coordinates are retained privately; no original audio, vendor capture, model, f64 streams or private JSON on GitHub.

## Private run invocation (historical; result already exists)

```bash
python3 research/htkpa/stages/stage111/GO.py \
  --private-inputs /path/to/HTKPA_STAGE110_PRIVATE_INPUTS.zip \
  --stage97-zip /path/to/CLO_10-19-26-0253.zip \
  --stage110-report /private/path/stage110_micro_residual_private.json \
  --output /private/new/path/stage111_event_boundary_private.json
```

**Do not rerun completed Stage102–111 or overwrite existing private reports.** Next action is interpretation and an explicit independently falsifiable hypothesis, not a claim of numerical vendor parity.
