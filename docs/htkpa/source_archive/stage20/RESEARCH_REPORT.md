# HTKPA Stage 20 — Native IIR coefficient constructor

**2026-10-12 · Source-first static research · No DLL execution, no new CLO, no production changes.**

Binary: user-provided `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. VA base: `0x180000000`.

## Decoded difference equation

The audio worker `0x1800BD490` uses **five float64 coefficients per second-order section**, stored at context offsets `+0x232D8…+0x232F8` (first) and `+0x23300…+0x23320` (second). The previous Stage-19 description mistakenly called them six doubles. Native loads `0x1800BD564/0x1800BD56F/0x1800BD591/0x1800BD599/0x1800BD5A1` prove `[b0,b1,b2,a1,a2]` order:

```
w[n] = (1000.0*float64(x_f32[n]) - a2*w[n-2]) - a1*w[n-1]
m[n] = float32((b1*w[n-1] + b2*w[n-2]) + b0*w[n])
y[n] = float32(float64(m[n])*0.001)
```

Double state `w[n−1],w[n−2]` begins zero. The intermediate float32 conversion is shown at `0x1800BD5BB/0x1800BD5BF`, final scaling at `0x1800BD5C2/0x1800BD5C6`. Summation order is deliberately retained in our Python reference.

## Exact source of the five coefficients

At initialization `0x1800C04B0–0x1800C05E5`, two five-double blocks are neutral `[1,0,0,0,0]`: `context+0x24338` and `+0x24360`. Two more (`+0x24388`, `+0x243B0`) start with hard-coded defaults close to Fs=44100 Hz.

The sample-rate constructor `0x1800BFF17–0x1800C0216` calculates **10 float64 context coefficients and 5 float64 static coefficients**. Our independent bounded interpreter performs **152 native scalar/SSE instructions**, reading only 32/64-bit constants from the PE and reproducing SSE float32 arithmetic, sign-bit XOR, float-to-double casts, and native store order. It is **not executing DLL instructions**, only modelling their documented semantics in Python.

At Fs=48000, the recovered five-double coefficient records are:

| Record | b0 | b1 | b2 | a1 | a2 |
|---|---:|---:|---:|---:|---:|
| `0x24388` | 0.996304393 | −1.992608786 | 0.996304393 | −1.992595077 | 0.992622495 |
| `0x243B0` | 0.998150527 | −1.996301055 | 0.998150527 | −1.996297717 | 0.996304393 |

They are Butterworth-like high-pass responses: the measured **digital −3 dB frequencies are ≈40 and 20 Hz respectively** at 44.1, 48, and 96 kHz. Constants `15791.452`, `177.716`, `3947.847`, `88.858` resemble 20/10-Hz analog frequency parameters, but native code uses `Fs` rather than `2*Fs` in the coefficient denominator. Calling the *digital* cutoffs 20 and 10 Hz would be wrong.

The independent constructor initialized at 44100 Hz reproduces the separate hard-coded native default records to within **1.07e−7** maximum absolute error. We do not claim native bit-identical CRT execution at every float32 edge case.

## Live mode selection

The native copy dispatcher at `0x1800BEC2B–0x1800BED11` selects:

| `context+0x232D0` | Live first section | Live second section |
|---:|---|---|
| 0 | `0x24360` (identity) | `0x24360` (identity) |
| 1 | `0x24338` (identity) | `0x24388` (≈40 Hz HP) |
| 2 | `0x24338` (identity) | `0x243B0` (≈20 Hz HP) |

Address pins: `0x1800BEC36`, `0x1800BEC59`, `0x1800BEC8F`, `0x1800BECB7`, `0x1800BECDF`. The immediately preceding `0x1800BEB C8…0x1800BEB EC` initialization (spaces removed: `0x1800BEBC8…0x1800BEBEC`) assigns mode 0 or 1 using `context+0x4`. Mode 2 exists in the selector but is **not proven reached** in the normal NAM path. The first audio IIR is **neutral** in all these traced modes; do not describe this pipeline as necessarily two active audio filters.

## Saturator fitter: limited additional DLL facts, not a working fitting copy

The next function `0x1800BDBE0` generates approximately 0.1-second audio envelope groups (`Fs * 0.1`, native double at `0x18024C7A0`); it then uses separate positive/negative exponential-error branches. At `0x1800BE480–0x1800BE63E` we traced two candidate sweeps starting with multiplier **0.8f**, incrementing it by **0.05** and comparing it to **1.2** (corresponding constants `0x18024C608`, `0x18024C748`, `0x18024C9A8`). Exponential calls at `0x1800BE4BA/0x1800BE4D5/0x1800BE5AE/0x1800BE5C9` resolve to imported **`expf`**. Four float32 parameter stores occur at `0x1800BE661`, `0x1800BE676`, `0x1800BE682`, `0x1800BE68F`.

**Not recovered:** the complete envelope aggregation/edge handling, initial parameter estimation, the full four-parameter native optimizer and actual fitted gain values from the original WAV. No guesses have been substituted.

## Verification and acceptance

`test_stage20.py`: **106 individual checks passed**, verifying three rates, 152 constructor opcode replay positions, 10 + 5 resulting native stores, PE constants, both cutoff responses, first/second live selection, coefficient order, isolated causal IIR and saturator-loop pins. Two independent outputs of `stage20_iir_source.py` give byte-identical `evidence.json` SHA-256 (recorded in the package). No vendor code, NAM, reference WAV or CLO is included.

**Strict gates:** Original initial A/B curves **NOT_COMPUTED**. Independently computed official Pre-FIR and Post-FIR **NOT_COMPUTED**. Exact equality on JCM800 2203 and SC20 **NOT_TESTED**. Production JS and pedal untouched.

**Stage 21:** finish native `0x1800BDBE0` saturation fitting using only the DLL source and the input/reference audio envelopes. Then recover native 44.1→48-kHz input/output alignment and the `0x1800B82B0` spectral buffer setup. Connect to Stage 18 A/B before attempting FIR parity.
