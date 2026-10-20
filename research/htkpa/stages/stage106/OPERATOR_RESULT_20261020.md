# Stage106 — operator real metrics-only energy/error audit (2026-10-20 Bangkok)

**Result:** `STAGE106_PRIVATE_METRICS_ONLY_ENERGY_ASSOCIATION_COMPLETED`. The operator ran the committed Stage106 code in WSL following a clean fast-forward and **12/12 regression tests PASS**. This tool reads the existing private Stage105 6×200k / 60×20k metrics JSON; it **does not access original WAV, raw f64, model, the proprietary DLL or run inference**. Provenance is the operator-supplied console output, not assistant rehash of private JSON/raw audio.

| Stage106 report field | Value |
| --- | ---: |
| Early 4/6 coarse windows' share of **individually gain-fitted residual energy** | `0.9974831186627082` (99.7483119%) |
| Early 4/6 coarse windows' share of Manager WAV reference energy | `0.17209831560716993` (17.2098316%) |
| Pooled candidate DI RMS ratio, late 2 / early 4 | `431.5479130738116` |
| Early gain-fitted residual RMS in PCM16 LSB units | `7.578529494320367` |
| Late gain-fitted residual RMS in PCM16 LSB units | `0.5383671297658815` |
| Spearman rank: log candidate DI RMS vs log relative residual, **positive nonzero DI bins** | `-0.2173036606998871` |

**Not a global-gain statistic:** the 99.748% fraction sums residual squared energy **after independently selecting a gain per 200k block**. It does not equal the share of error after the single global Stage103 gain fit. PCM16 step counts are scale comparisons only; they do **not** establish quantization as the cause. Spearman `-0.2173` is only a weak descriptive monotonic association in a single structured reference DI, not evidence for a proportional law or statistical generalization; the tool excludes zero DI RMS from the correlation.

### Largest adjacent 20k-bin relative-error reduction

- Previous bin: `[1340000,1360000)`, relative gain-fitted RMS error `0.01706683266865577` (1.70668%), candidate DI RMS `0.17782119462369755`.
- Next bin: `[1360000,1380000)`, relative error `4.5855771179852703e-07` (0.000045856%), candidate DI RMS `0.0`.
- Bin boundary: index 1,359,999 → 1,360,000 (28.3333 seconds at 48kHz). Relative-error drop `log10(previous/next)=4.570758928884041` (~3.7×10^4), but this is a **comparison of two separately fitted 20k-bin aggregates**, not a measured instantaneous sample-to-sample DSP transition.

**Critical interpretation:** The apparent dramatic error reduction is **coincident with a transition from an active candidate DI bin to a bin with DI RMS zero**. It may reflect the reference DI's scripted silence/structure and differences in how the source rendering decays or is normalized, rather than a proprietary algorithmic mode change. Zero candidate DI RMS does not imply zero Manager WAV or zero NAM output. The output level of this silent bin was not included in the terminal summary; interpreting exact causality requires checking the already computed reference and open RMS for this and adjacent bins. The all-bins Spearman correlation cannot by itself attribute the residual to DI level.

The method does not establish vendor resampler identity, loaded NAM byte identity, origin of Manager's intermediate output buffer, native NAM parity, fitted CLO or hardware readback. Production remains unchanged.

**Next low-cost falsifiable step:** print **selected entries only** from existing `stage105_error_topology_private.json` and `stage106_metrics_audit_private.json`: top five bins by absolute (not relative) squared residual, candidate DI/reference/open RMS and fitted gain for bins around [1320000,1400000), plus zero-DI bin counts. No fresh NAM or DLL runs required.
