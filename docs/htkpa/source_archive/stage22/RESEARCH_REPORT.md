# HTKPA Stage 22 — exact saturation-fitting window and pre-fit reference conditioning

**2026-10-12 | Source-first | 5868USB.dll static inspection only**

The proprietary DLL was **never loaded or executed**. SHA256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, base VA `0x180000000`. No production changes, no new CLO or pedal writes.

## Critical correction to Stages 20–21

The fitted audio signals do **not** pass through the known 50-tap FIR and double-precision IIR helper `0x1800BD490` before the saturator fitting call. The order in `0x1800BE830` is unambiguous:

- `0x1800BEAF8` reads the **input** pointer from `context+0x243E0`, storing it in `r15`.
- `0x1800BEAFF` reads the **reference output** pointer from `context+0x243E8`. Its pointer is advanced by an onset offset, yielding `rbp`.
- `0x1800BEDD8`: `r9d = esi = trunc(float32(5 * Fs))`.
- `0x1800BEDDB`: `r8 = rbp` (**reference**); `0x1800BEDDE`: `rdx = r15` (**input**).
- `0x1800BEDE4`: **first** calls four-parameter `0x1800BDBE0` fitter.
- **Only later**, at `0x1800BEE25`, calls IIR helper `0x1800BD490` with **different** pointers `r12/r13` and outputs into a separate `rbp` buffer.

This does **not** mean the DLL arguments are identical to the stored PCM WAV bytes. Native loading and any external/native sample-rate conversion prior to these context buffers remain to be proven. However, the claim that `0x1800BD490` necessarily transforms the two inputs of `0x1800BDBE0` is **disproved** by call order.

## Source-proven window, padding and alignment

- `0x1800B5640` constructs two float32 buffers `+0x243E0/+0x243E8`, each with allocation capacity **4 × (70×Fs + 600)** bytes; constants at `0x18024CD6C=70.0f`, `0x18024CDA4=600.0f`, `0x18024CCB0=4.0f`. The loaders at `0x1800BF890` and `0x1800BFCA0` copy data into a staging buffer at `+0x243F0` before the buffers are populated elsewhere in the native import flow.
- `0x1800BE8E7..0x1800BE930`: mean removal performed **only on reference `context+0x243E8`**, over the allocated analysis support. Input pointer `+0x243E0` is not written in this section.
- `0x1800BE960..0x1800BEA34`: estimate the best-fit **linear trend** from reference sample index and amplitude (least squares, one-based sample index), then subtract it in-place from the reference. These are two consecutive operations, not an IIR filter.
- `0x1800BEA59..0x1800BEAD6`: scan the reference from **6×Fs** samples for up to **600 samples**. Detection is the first amplitude whose absolute value exceeds **0.01** (`0x18024C6C8`, double). If no threshold crossing, the native loop's 600-sample fallback applies. The observed shift is an integer from 0 to 600; behavior on nonfinite data not characterized.
- `0x1800BEB2B`: choose the **input start at 23×Fs**. `0x1800BEB1F` and `0x1800BEB41` add the measured offset to the reference pointers. `0x1800BEADA` loads **5.0f**, and `0x1800BEDBF` supplies its converted sample count to the fitter. So **the entire four-gain search runs on the 23–28-second segment**, not the full 70s.
- Other source-derived selector starts `6,30,50` seconds remain as traced in Stage 8. Their windowing is for different subsequent routines.

Thus a faithful end-to-end saturation fit needs **only two correctly loaded native-Fs float32 audio buffers** and the source-proven reference detrend, alignment and 23–28s selection; it does **not** require executing the later 50-tap/IIR filter first.

## Independent verification

A newly written read-only static-analysis script `stage22_pre_fit_trace.py` checks:

- **43 exact DLL instruction addresses**, **7 PE float/double constants**.
- **53 synthetic assertions** for window pointer arithmetic, buffer size, alignment threshold and affine detrending.
- Two independent runs of the script produced byte-identical evidence JSON with SHA-256 `d4c4edbd29674ddd3ab9a161192b579647bb9f58a441b00a8c52970a6faaedbb`.
- The affine detrending verifier deliberately uses double-precision vectorized NumPy operations and checks the **recovered equation**, *not* bitwise native `float32` accumulation ordering.

## Independent read-only checks on the two real Manager sessions

The saved WAVs are each 70s. Source DI: **44.1 kHz**, reference output WAV: **48 kHz**. Input DI bytes are identical for both Marshall models. Without using any official `.clo` parameters, the static formula applied **diagnostically** to the 48-kHz output PCM16 samples (and 600 appended zeros) found onset offsets:

| WAV capture | Diagnostic threshold crossing at 6s | Interpretation |
|---|---:|---|
| JCM800 2203 Crunch | 0 samples | Approximate diagnostic only |
| SC20 Full Rig | 19 samples | Approximate diagnostic only |

**These are not validated native offsets.** The external/loader handling of 44.1-kHz DI, 48-kHz output, PCM conversion, the DLL `Fs` context, f32 summation order and exact zero padding is still unresolved. The native code is not executed as an oracle; no accurate 5-second paired vectors are generated here. The 4-gain reconstruction from actual WAV remains `NOT_COMPUTED`, vendor coefficient parity remains `NOT_TESTED`.

## Immediate next source-first gate

Trace exactly how `namConvertCloData` or `appNamConvertCloData` populates `context+0x243E0/+0x243E8` at its selected `Fs`, including input resampling, output sample scaling, frame padding and memory representation. **Then** apply these Stage-22 corrections and the Stage-21 independent saturation fitter to the exact 23–28-second pair. Hold official positive/negative gains and rates for both Marshall CLOs *out of the fit* and compare them only after independent calculation. Only then proceed with full A/B and FIR. Do not substitute guessed interpolation or vendor coefficients.
