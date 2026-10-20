# Stage103 follow-up — operator's six fit-window segments (2026-10-20 Bangkok)

**Real operator printed existing private `stage103_gain_audit_private.json` values, prewarm OFF**, after 9/9 tests and completed Stage103/104 gates. These six 200000-frame windows are within the 48-kHz interval [300000,1500000). Stage104 independently established that open NAM Core prewarm ON and OFF samples are **bitwise identical throughout this interval**. No new inference was performed. The assistant did **not** independently access the private source JSON or raw f64.

| Window (absolute, stop exclusive) | Time (s) | Least squares open→Manager gain, zero lag | Normalized RMS residual after gain | Zero-lag cosine |
|---|---|---:|---:|---:|
| [300000,500000) | 6.25–10.4167 | 0.309054908859 | 2.104113% | 0.999778610957 |
| [500000,700000) | 10.4167–14.5833 | 0.309056472615 | 2.034970% | 0.999792923327 |
| [700000,900000) | 14.5833–18.75 | 0.309093620076 | 2.025485% | 0.999794849542 |
| [900000,1100000) | 18.75–22.9167 | 0.309062217717 | 2.069548% | 0.999785825566 |
| [1100000,1300000) | 22.9167–27.0833 | 0.309999645467 | 0.040238% | 0.999999919045 |
| [1300000,1500000) | 27.0833–31.25 | 0.310002676142 | 0.065512% | 0.999999785410 |

Arithmetic means of **window gains only** (not energy-weighted fits): first 4 = `0.30906680481675`, last 2 = `0.3100011608045`; the latter exceeds the former by `0.00093435598775` (about **0.3023%** relative to first group). Errors in the first group remain ~2% even when each segment has its *own* optimized scalar, whereas last group has ~0.04–0.07%. The previously reported pooled Stage103 gain of `0.3098390026147448` is **energy-weighted** by sample content, and need not equal these simple means.

**Interpretation:** a distinct change in segment-level fitted gain and residual appears between windows 4 and 5, near sample 1,100,000 (~22.917 s). This is **a detection boundary at window granularity**, **not** proof of an actual discontinuity or mode switch at that sample. Potential causes include excitation spectrum/level variations, vendor input resampling, output scaling/quantization, alignment, or model/provenance differences. Segment energies have not been included in the operator's displayed output, so do not interpret the cause yet.

**Harmless Python KeyError:** `fit_block_gain_range` is the summary dictionary, which also starts with `fit_block_`; the assistant's original print loop incorrectly attempted to read per-block coefficient keys from it. All six actual fit-block lines printed *before* the exception and are valid. Correct by accepting only `name.startswith('fit_block_') and name[10:12].isdigit()` or checking the required key in each dict.

**Next bounded step:** read only the existing private Stage103 window metrics `manager_rms`, `open_rms`, `max_abs_error_after_gain_only` alongside gains, then decide whether finer subwindows/lag diagnostics warrant a Stage105 tool. No reason to rerun Stage102/103/104 or the proprietary DLL.

## Second operator readout: energies and maxima (same six Stage103 windows)

The operator read **additional fields from the existing private Stage103 JSON**, without rerunning inference, using a corrected filter that excludes the summary-only `fit_block_gain_range` key.

| 200k-frame window | Manager RMS | Open NAM RMS | Gain-only normalized residual | Maximum absolute gain-fitted residual |
| --- | ---: | ---: | ---: | ---: |
| 1 [300k,500k) | 0.01208766 | 0.03910302 | 2.1041% | 0.00226817 |
| 2 [500k,700k) | 0.01199030 | 0.03878843 | 2.0350% | 0.00204499 |
| 3 [700k,900k) | 0.01189838 | 0.03848651 | 2.0255% | 0.00231514 |
| 4 [900k,1100k) | 0.00859691 | 0.02781017 | 2.0695% | 0.00226306 |
| 5 [1100k,1300k) | 0.04340378 | 0.14001234 | 0.0402% | 0.00003328 |
| 6 [1300k,1500k) | 0.02339227 | 0.07545826 | 0.0655% | 0.00080958 |

**Derived, not an additional measured run:** multiplying each Manager RMS by its individual normalized residual gives absolute gain-fitted RMS ≈0.0002543, 0.0002440, 0.0002410, 0.0001779, 0.0000175, 0.0000153. Since all six windows contain equally many frames, their squared RMS residuals imply that windows 1–4 account for approximately **99.75% of the independently per-window gain-fitted residual energy**, although their Manager signal RMS-squared energy contribution is only ≈**17.2%**. This must **not** be confused with decomposition of Stage103's *single global-gain* error: each window here had its own optimal gain. The large max/RMS ratio in window 6 suggests sparse residual anomalies worth localizing, but does not prove a cause.

**Scope:** This is an operator-console readout of already existing private audio metrics, **not** assistant-independent access to raw buffers. Differential spectral content, nonlinearity, tiny timing shifts, resampling, model identity and Manager output save normalization are not independently determined. New Stage105 performs only targeted **offline** investigation on the existing private files, no DSP rewrite or vendor execution.
