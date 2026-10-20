# Post-Stage107 operator verification — 44.1-kHz float32 DI equals PCM16-decoded input

**Date:** 2026-10-21 Bangkok. **Evidence:** direct operator WSL console, independent 70-second sample-by-sample audit. The assistant did not independently access the operator's local ZIP or rerun this specific comparison on private data.

Original exact-SHA Stage97 ZIP: `2f96dce1ae479a93975cf6247a88a4a08c11de7ae5cab41648faa0d7902e6f46`. The script decompresses `src/assets/nam_reference_di_44100.f32.gz` as 3,087,000 little-endian float32 frames, reads the original `wavs/nam_input_wav.wav` as 3,087,000 stereo-same PCM16 frames at 44,100 Hz, and verifies for **each** frame:

1. `left_pcm16 == right_pcm16`.
2. `clamp(round(float32 * 32768), int16_range) == left_pcm16` (Stage101 direct-quantization recheck).
3. **NEW:** `float32 == left_pcm16 / 32768.0` by exact numerical equality after decoding.

| Window | Frames | Exact numeric equality fraction | RMS difference (PCM16 LSB) | Maximum difference (PCM16 LSB) | RMS difference / DI RMS |
|---|---:|---:|---:|---:|---:|
| Full 70s | 3,087,000 | **1.0** | **0** | **0** | **0** |
| Source-time window 6.25–22.92s, frames [275625,1010625) | 735,000 | **1.0** | **0** | **0** | **0** |
| Source-time window 22.92–31.25s, frames [1010625,1378125) | 367,500 | **1.0** | **0** | **0** | **0** |

**Conclusion (only at the 44.1-kHz source boundary):** The hypothesis that float32 DI source precision differs numerically from the original Manager input WAV once decoded as PCM16 is **rejected** for this exact sample and all 3,087,000 frames. Consequently applying PCM16 quantization to this already-quantized float32 DI cannot change the open resampler's inputs if the decoded values and downstream resampling implementation are otherwise unchanged. **Do not attribute Stage105 quiet-active residual to source float32-vs-PCM16 precision.**

**Unclosed issues:** Whether the proprietary Sonicake Manager **44.1→48-kHz resampling** matches the open SonicMaster Blackman-windowed sinc candidate remains unverified. So do exact vendor-loaded NAM model bytes, native output WAV buffer provenance, output gain and rounding, proprietary fitter numerical parity, CLO generation and device readback.

**Next bounded low-cost experiment (Stage108):** use only original authenticated 48-kHz Manager PCM16 *output* WAV and the **existing SHA-pinned open NAM Core f64 output** from Stage102 to test fixed candidate output gain `0.31` with explicit nearest-PCM16 clipping/rounding, counting exact PCM16 matches by quiet-active, loud-active and silence windows. Include a diagnostic global least-squares gain control, and distinguish integer PCM16 parity from float-domain gain-fit similarity. **No new NAM inference**; do not claim implementation-specific native output quantizer without evidence.
