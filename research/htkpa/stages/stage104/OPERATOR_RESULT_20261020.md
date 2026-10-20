# Stage104 — real operator prewarm ON/OFF difference localized (2026-10-20 Bangkok)

**Status:** `STAGE104_OFFLINE_PREWARM_DIFFERENCE_LOCALIZED`. Genuine operator WSL terminal; **11/11 offline regression tests PASS**. The Stage104 SHA-gated tool read the two existing private Stage102 open NAM Core f64le outputs and the Stage103 provenance reports, without rerunning any NAM inference, proprietary DLL, resampler or fitter.

## Operator-reported exact result

| Interval | Frames | Different 64-bit words | Bitwise equal | RMS difference | Maximum absolute difference |
|---|---:|---:|---|---:|---:|
| All [0, 1600000) | 1,600,000 | **5,485** | No | `0.0009560180605001499` | `0.13375134021043777` |
| Startup [0, 300000) | 300,000 | **5,485** | No | `0.002207829138319622` | `0.13375134021043777` |
| Fitter [300000, 1500000) | 1,200,000 | **0** | **Yes** | **0** | **0** |
| Tail [1500000, 1600000) | 100,000 | **0** | **Yes** | **0** | **0** |

Absolute first different zero-based index: **0**. Absolute last different zero-based index: **5983**. All frames in **[5984,1600000)** were byte-identical in the two measured f64 outputs. Index 5984 corresponds to **124.667 ms** at 48,000 Hz. None of the different words were numerically equal while bitwise different; `numerically_equal_but_bitwise_different_count=0`. All six individually reported fitter 200k windows also had zero differences (`fit_subwindows_differing=[]`).

**Conclusion bounded to this experiment:** Core prewarm ON versus OFF affects the **startup transient only**, and specifically does not account for Stage103's **0.8622319%** amplitude-gain-corrected discrepancy against the Manager WAV over the fitter interval, where both Core outputs are exactly the same. This is one model, one input, and a first-1.6M-frame analysis. It does not establish that proprietary Manager uses either prewarm mode, or that its input 48-kHz resampler, loaded model, or outputFile.wav are identical to these open NAM Core data.

## Source and privacy boundary

The figures above are copied from the operator's real Stage104 WSL CLI after 11 unit tests. Assistant inspected the checked-in Stage104 SHA validation and bitwise comparison implementation, **but did not independently read the original private f64 raw outputs or private Stage104 JSON**. Vendor WAV/model/CLO, original SHA values for private outputs, and detailed raw data remain in ignored `research/_LOCAL_FILES` and are not committed. No vendor numerical parity, fitter restoration, CLO synthesis, or device readback is claimed.

**Next low-cost gate:** read only the already computed 9 Stage103 gain-window summary objects from `stage103_gain_audit_private.json` and compare six fitted coefficients and normalized residuals; compare them with an open-side input gain versus output scaling hypothesis before any new native capture or DSP rewrite.
