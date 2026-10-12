# Sonicake HTKPA — Stage 4: FIR-output data flow and sample-rate conversion

**12 October 2026 · static investigation of the user-provided Windows Sonicake Manager `5868USB.dll` · no vendor code executed.**

## Executive finding

**The final FIR packing path is now confirmed by an end-to-end pointer trace.** Sonicake generates working Pre-FIR and Post-FIR arrays at context offsets `+0x24408` and `+0x24410`, converts them through its generic audio-array/resampling implementation, then copies the results into the VTSI payload with zero-filled unused portions. The target rate is **44,100 Hz**. The internal NAM-output WAV for the matching captures is **48,000 Hz**.

The sample count follows the DLL's float32 calculation at `0x18000d031..0x18000d043`:

`out_length = trunc_toward_zero(float32(in_length) × fs_target / fs_source)`

With 48 kHz → 44.1 kHz, `128 → 117` and `2048 → 1881`. Both official CLOs have **117** and **1881** consecutive nonzero taps with 11 and 167 trailing exact zeros. This matches all four files from our two NAM cases, including **both baseline Void Mod CLOs**. Therefore **resampling cannot, by itself, explain the observed timbral mismatch** between Void and Sonicake. The old code already preserves the same output-tap support.

**Original Stage 4 acceptance criterion (independently compute an official FIR by NAM/WAV and match its numerical nonzero coefficients) was NOT met.** The result is a proven output-stage data flow, length formula and sharply narrowed upstream unknown, **not** a full HTKPA clone or source-independent solution for the fitted filter.

## 1. Exact code-level chain

All addresses below are PE virtual addresses with image base `0x180000000`, **not file offsets**. Static verifier pins SHA-256 to `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa` and confirms 23 exact instruction addresses.

### 1.1 Post-FIR initialization and optimization

1. At `0x1800bed4a..0x1800bed5d`, the buffer pointed to by `[context+0x24410]` is cleared, and its first float32 sample is set to `0x3f800000` (**1.0f**), yielding an initial unit impulse `(1,0,0,...)`.
2. `0x1800bed63..0x1800bed78` passes that array to `0x1800c0d40`, a reusable signal-object construction routine.
3. `0x1800bf050..0x1800bf0d5` dispatches three differently configured `0x1800bb210` optimization steps, which receive **both** FIR pointers via stack arguments.
4. `0x1800bf100..0x1800bf11e` invokes `0x1800b9b70`, the spectral/magnitude finishing function, passing `[context+0x24410]` as a destination argument. Prior Stage 3 identified bounded ratios and RMS correction inside it.

### 1.2 Two filter conversion objects

- `0x1800bf123..0x1800bf135`: construct / refresh filter object at `context+0x38` from **Pre-FIR** source pointer `[context+0x24408]`, raw length `[context+0x20ed4]` (128).
- `0x1800bf13a..0x1800bf14f`: construct / refresh filter object at `context+0x10668` from **Post-FIR** pointer `[context+0x24410]`, raw length `[context+0x20ed8]` (2048).
- `0x1800bf1c4..0x1800bf29b`: allocate and initialize an **8,840-byte VTSI container**; its two nominal tap counts are 128/2048.
- `0x1800bf320..0x1800bf364` and `0x1800bf440..0x1800bf47f`: each raw array is copied to the audio-array abstraction and passed to **`0x18000ce00`** with input rate from `[context+0x20ec0]` and target rate **44100.0f** (literal at `0x18024cdf0`).
- `0x18000d031..0x18000d043`: output count is computed by multiplying original length by target frequency and dividing by source frequency, truncating to an integer (not rounding).
- `0x1800bf37a..0x1800bf3b6` and `0x1800bf49b..0x1800bf4da`: entire allocated serialized FIR regions are zeroed first; only the converted number of samples is copied.
- `0x1800bf4df..0x1800bf542`: write `VTSI`, declared byte length and CRC. Actual transmitted device profile has fewer Post-FIR taps; **the full 2048-tap file and 512-tap upload should not be conflated**.

The deeper resampling interpolation/phase convention implemented behind `0x18000ce00` → `0x180012340` has **not** been reconstructed. Exact zero-padding alone is insufficient to predict coefficient values.

## 2. Numerical cross-check on the two NAMs

The verifier accepts the **four real 8,840-byte CLOs** (official Windows Manager and original Void Mod, both SC20 and 2203) and checks CRC16, filter support and pairwise tap-vector cosine.

| Case | Filter | Official nonzero / nominal | Void nonzero / nominal | Cosine similarity between taps |
| --- | --- | ---: | ---: | ---: |
| JCM800 2203 Crunch | Pre-FIR | 117 / 128 | 117 / 128 | **0.0174** |
| JCM800 2203 Crunch | Post-FIR | 1881 / 2048 | 1881 / 2048 | **−0.1932** |
| SC20 Full Rig | Pre-FIR | 117 / 128 | 117 / 128 | **0.7966** |
| SC20 Full Rig | Post-FIR | 1881 / 2048 | 1881 / 2048 | **−0.0311** |

The cosines are **tapwise comparisons without time alignment, deconvolution or gain compensation**. They are evidence of different coefficient shapes, **not** a perceptual audio score; phase/delay differences alone can strongly lower a tapwise cosine.

These figures show the true remaining gap clearly: **the source waveforms and packed tap counts are already understood, but the two fitting optimizers construct very different FIR coefficient values.**

## 3. Precisely what remains unsolved

- Derive the complete update equations and destination writes of **`0x1800bb210`**, including the two `0x1800b82b0`0 Hamming-based operations.
- Determine the upstream filtered/saturated reference buffers and their alignment into the bounded spectral ratio in **`0x1800b9b70`**.
- Recover complex transform phase convention, inverse transform, normalization and truncation upstream of the 44.1 kHz conversion.
- Recover *exact* interpolation/phase behavior of the output resampler if coefficient-level equality is the target.
- Test a independently implemented **Pre-FIR or Post-FIR shape** against both official reference CLOs, with normalized error metrics and coefficient-level comparison. This must be completed before claiming an equivalent algorithm.

A valid next milestone: generate a 48 kHz internal FIR *only from the NAM and known probe WAV* and map it through an independently implemented 44.1 kHz converter, showing low numerical error against **all 117/1881 nonzero official samples on at least one case**. Matching only the trailing zeros or aggregate frequency-band curves does **not** satisfy this.

## 4. Reproducibility

Run `verify_stage4.py` with the user's own paths to the DLL and the four CLOs:

```bash
python verify_stage4.py \
  --dll "/path/to/5868USB.dll" \
  --official-2203 "/path/to/2203_official.clo" \
  --void-2203 "/path/to/2203_void.clo" \
  --official-sc20 "/path/to/sc20_official.clo" \
  --void-sc20 "/path/to/sc20_void.clo" \
  --out static_validation.json
```

Requires Python3 and GNU `objdump`; built-in Python libraries only. The script never invokes, loads, or redistributes the original DLL. It verifies **23 pinned instructions**, pinned binary SHA, target-rate constant, 48→44.1 support predictions, full CLO CRC16 and shapes for both cases.

**Research only.** No files were uploaded to the pedal, no new CLOs were generated, and no production JavaScript functionality was modified. The user-accepted JCM800 2203 **v0.2 C** remains the preferred audible reference until further testing.
