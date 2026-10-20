# Stage105 real operator audit — gain, energy, DC, lag, residual topology

Date: 2026-10-20 (Bangkok). **Operator WSL, 11/11 regression tests PASS**, `STAGE105_OFFLINE_GAIN_ENERGY_LAG_TOPOLOGY_COMPLETED`. Existing SHA-gated Stage102–104 private data and Stage97 original 48-kHz Manager WAV were analyzed **without** re-running NAM, the Manager, the proprietary DLL or the fitter. This is operator-reported console evidence, not assistant independent rehash of private raw samples.

The six **disjoint equal-length 200,000-sample** windows of the [300000,1500000) fit region all had **best integer lag = 0** among [-4,+4] on a common trimmed domain. No meaningful reduction of the early error was achieved by adding a fitted DC offset.

| Fit interval [start,stop) | Candidate DI RMS, 48 kHz | Manager WAV RMS | Open→Manager gain (diagnostic) | Residual after gain / Manager RMS | Residual after gain and DC / Manager RMS | Absolute index of largest residual |
|---|---:|---:|---:|---:|---:|---:|
| [300000,500000) | 0.000779619 | 0.012087655 | 0.309054909 | 2.104113% | 2.100067% | 488301 |
| [500000,700000) | 0.000759941 | 0.011990297 | 0.309056473 | 2.034970% | 2.030723% | 679046 |
| [700000,900000) | 0.000752556 | 0.011898376 | 0.309093620 | 2.025485% | 2.021172% | 730965 |
| [900000,1100000) | 0.000539194 | 0.008596913 | 0.309062218 | 2.069548% | 2.066446% | 971808 |
| [1100000,1300000) | 0.393632226 | 0.043403779 | 0.309999645 | 0.040238% | 0.020581% | 1236750 |
| [1300000,1500000) | 0.187707846 | 0.023392267 | 0.310002676 | 0.065512% | 0.051909% | 1344005 |

Measured **0.9974831186627082 (99.7483%)** of the summed **separately gain-fitted** squared residual energy occurs in the first four equal-length windows; those windows contribute about **17.21%** of the Manager reference WAV squared energy. **Not** a statement about error distribution from a *single global* gain fit. The candidate DI RMS in later windows is hundreds of times larger than in earlier windows, while reference output RMS increases far less. This signal-content difference is consistent with amplitude-dependent or segment-dependent effects, but **does not establish a mode switch, which function changes or what the proprietary pipeline does**.

The five largest relative residual 20k bins from the operator summary:
- [480000,500000): residual 2.517901%, candidate DI RMS 0.001010930
- [960000,980000): 2.417744%, DI RMS 0.001014074
- [720000,740000): 2.409532%, DI RMS 0.001010588
- [920000,940000): 2.395888%, DI RMS 0.000929734
- [580000,600000): 2.384222%, DI RMS 0.001002797

**Quantization sanity:** residual absolute RMS in the six windows is about 0.00025434, 0.00024400, 0.00024100, 0.00017792, 0.00001746 and 0.00001532 in normalized PCM full scale. Early residuals correspond to ~5.83–8.33 PCM16 least-significant steps (1/32768); late residuals to ~0.50–0.57 steps. These are scale comparisons and do not prove particular quantizer noise behavior, clipping or any native resampling algorithm.

**Provenance boundary:** vendor Manager WAV is an independently validated saved artifact, but matching the exact vendor memory buffer/model, proprietary 44.1→48 kHz resampling, internal gain/normalization, and the proprietary FIR fitter is still **unverified**. The open NAM input uses the **SonicMaster candidate** resampler and a locally supplied model; no vendor DLL inference parity, CLO reconstruction, or hardware readback is claimed. No raw input/output PCM or proprietary files are in this public document.

**Next bounded gate:** use the existing private Stage105 60-bin report for an automatic **metrics-only** energy/error association and transition diagnostic, then only if needed investigate actual stage97 WAV vs open NAM residual spectral structure. Repeating Stage102/103/104/105 is unnecessary.
