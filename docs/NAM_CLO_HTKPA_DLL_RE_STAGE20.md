# Sonicake HTKPA Stage 20 — DLL-derived IIR coefficient constructor

**2026-10-12 | Static source-first research.** No proprietary DLL execution, no device changes, no new CLO, and no production JS modification.

Pinned Windows Sonicake Manager `5868USB.dll` SHA-256:
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
Base VA `0x180000000`.

## What is proven

The actual IIR audio section in `0x1800BD490` is **five** double-precision coefficients, not six: `[b0,b1,b2,a1,a2]`. Loads are pinned at `0x1800BD599`, `0x1800BD591`, `0x1800BD5A1`, `0x1800BD564`, `0x1800BD56F`. Each section uses:

```
w[n] = (1000*float64(input_f32[n]) - a2*w[n-2]) - a1*w[n-1]
m[n] = float32((b1*w[n-1] + b2*w[n-2]) + b0*w[n])
y[n] = float32(float64(m[n])*0.001)
```

The native context constructor `0x1800C04B0` initializes two 5-double banks `context+0x24338` and `context+0x24360` to **[1,0,0,0,0] (identity)**, and two other banks near 44.1-kHz high-pass coefficients. The later sample-rate dependent initializer `0x1800BFF17…0x1800C0216` dynamically replaces the latter two banks (`+0x24388`, `+0x243B0`) using its `float32(Fs)` value at `context+0x20EC0`. There are **ten direct context double writes and five global double writes**.

A standalone Python **interpreter of exactly 152 SSE/scalar instructions** (not a DLL loader) reads the same PE constant bytes and reconstructs the ten native context values at Fs 44,100, 48,000 and 96,000 Hz, including `float32` intermediates, sign-mask `xorps`, and `cvtps2pd` / `cvtss2sd` conversion. The 44.1-kHz emulated coefficients agree with the separate hard-coded default initializer to within `1.07×10⁻⁷` in absolute error.

### Numeric coefficient proof, Fs 48,000 Hz

| Source bank | b0 | b1 | b2 | a1 | a2 | Measured digital −3 dB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0x24388` | 0.996304393 | −1.992608786 | 0.996304393 | −1.992595077 | 0.992622495 | ≈40 Hz |
| `0x243B0` | 0.998150527 | −1.996301055 | 0.998150527 | −1.996297717 | 0.996304393 | ≈20 Hz |

**Important frequency caveat:** Native analog-like PE constants suggest 20/10-Hz design parameters, but the constructor divides by expressions based on **Fs** rather than `2*Fs`. The actual discrete transfer cutoffs are therefore about 40 and 20 Hz. A SciPy `freqz` computation on the independently emulated coefficients verifies this at all three supported rates.

### Live IIR mode selection

Function `0x1800BEC2B–0x1800BED11` copies bank pointers into the two live sections:

| mode (`context+0x232D0`) | first live FIR/IIR section | second section |
|---:|---|---|
| 0 | `+0x24360` (identity) | `+0x24360` (identity) |
| 1 | `+0x24338` (identity) | `+0x24388` (≈40 Hz HP) |
| 2 | `+0x24338` (identity) | `+0x243B0` (≈20 Hz HP) |

Selector instruction pins `0x1800BEC36/0x1800BEC59/0x1800BEC8F/0x1800BECB7/0x1800BECDF`. The **actual mode assignment within the earlier path sets 0 or 1** using `context+0x4`. Mode 2 has a handler but its regular NAM conversion reachability is **not proven**. The first section is identity for the observed branches; it is wrong to assume *two active frequency-altering IIRs*.

## Adjacent saturator-fitting function: narrower proven findings

`0x1800BDBE0` uses a 0.1-second block-size factor (`Fs × 0.1`, PE double `0x18024C7A0`) to prepare audio envelope groups. The two scalar optimization sweeps in `0x1800BE480…0x1800BE63E` use the sign-separated exponential model (`expf` imports at `0x1800BE4BA/0x1800BE4D5/0x1800BE5AE/0x1800BE5C9`) and source-pinned candidate multiplier `0.8f`, addition by `0.05`, upper bound `1.2`. Four resulting `float32` values are written at `0x1800BE661/0x1800BE676/0x1800BE682/0x1800BE68F`. This is **not** a complete reimplementation of the four-parameter optimizer: exact envelope extraction, fit initialization, numerical tie-breaking and real fitted values remain unresolved.

## Reproducibility and original acceptance gate

Research-only ZIP `Sonicake_HTKPA_DLL_RE_Stage20_v0_20.zip` delivered in the originating conversation bundles `stage20_iir_source.py`, `test_stage20.py`, `RESEARCH_REPORT.md`, `README.md`, `test_stdout.txt`, `evidence.json`. It contains no vendor DLL, proprietary media or CLO. **106 individual assertions pass**, and two independent evidence runs are byte-identical (SHA-256 `ad19bd408c788f80f90cf140899c56e6ce5e6db6cf884e2627fefc11500226d0`). The source never loads or executes the DLL; it reads PE bytes and tests independent Python math.

**Still NOT achieved:** complete four nonlinear gains from the reference WAV; initial vendor A/B curves; real-WAV native-signal-path equivalence; independently reconstructed official 128/2048 FIR and heldout equality on both Marshall 2203 and SC20. All retain statuses **NOT_COMPUTED** / **NOT_TESTED**. No hardware operation, product conversion or production source modification.

**Next Stage 21:** source-first complete `0x1800BDBE0` saturation parameter optimizer, then native audio preprocessing and `0x1800B82B0` STFT alignment to form genuine initial A/B curves. Avoid inserting defaults from official CLO or arbitrary numerical fitting. Keep the user-auditioned 2203 v0.2 C as reference.

Historical [Stage 19](NAM_CLO_HTKPA_DLL_RE_STAGE19.md) has an explicit correction of the five-coefficient count, active IIR count and digital cutoff interpretation.
