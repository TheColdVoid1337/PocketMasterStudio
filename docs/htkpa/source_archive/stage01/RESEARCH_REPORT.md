# Sonicake 5868USB.dll — HTKPA static reverse engineering, stage 1

**Date:** 2026-10-12  
**Project:** PocketMasterStudio Void Mod  
**Scope:** read-only static reverse engineering and reference-WAV verification; **no DLL execution, no hardware operations, no edits to production converter**.

## 1. Traceable binary baseline

- Source: user-uploaded installed Windows Sonicake Manager.
- Binary: `assets/5868USB.dll` (Windows x64, PE32+).
- SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
- Exported `namConvertCloData` RVA `0xE1F70` (VA `0x1800E1F70`) and `appNamConvertCloData` RVA `0xABEB0`.
- Concrete internal call: routine at **`0x18000F940`** invokes processing routine **`0x1800BE830`** via `call` at **`0x18000FA41`**, after loading its two audio inputs.
- `0x1800BE830` is therefore a **confirmed part of the WAV-to-CLO processing path**. Calling it the entire HTKPA algorithm would be imprecise: it delegates to several large subroutines.

## 2. Verified DSP steps in the assembly

### 2.1. Output-buffer preprocessing

At `0x1800BE8BB` through `0x1800BEA55` the function uses a sample-rate field at `context+0x20EC0`, and the buffer at `context+0x243E8`.

1. Computes **`N = round(70 * sample_rate + 600)`** from literal float constants 70 and 600; the buffer allocator in `0x1800B5640` also accounts for the extra samples.
2. Computes the mean of the first `N` float32 samples and subtracts it **in-place** (assembly around `0x1800BE8F0` and `0x1800BE920`).
3. Computes the ordinary least-squares slope and intercept from sums of `i`, `y[i]`, `i*y[i]`, and `i²` (`0x1800BE990`–`0x1800BEA05`), then subtracts the fitted straight line in-place (`0x1800BEA10`–`0x1800BEA55`).

The precise internal resampling kernel, handling of padded samples and arithmetic rounding still need reproducing for bit-exact preprocessing.

### 2.2. Fixed timing and onset search

The code establishes:

- **6 × sample_rate** at `0x1800BEA5D`–`0x1800BEA64` (shift/LEA multiplication by six);
- searches up to **600 samples** after that point (`0x1800BEA64`–`0x1800BEAD6`), looking for the first sample whose **absolute value exceeds `0.01`**. The `0.01` literal is IEEE754 double at `0x18024C6C8`;
- **23 × sample_rate** at `0x1800BEB2B`;
- **30 × sample_rate** at `0x1800BEB4D`;
- **50 × sample_rate** at `0x1800BEB6F`;
- additional **5-, 15-, 20-second** window parameters from float constants at `0x18024CCD0`, `0x18024CD34`, `0x18024CD40`.

This is direct evidence that the predesigned 70-second WAV is **segmented according to known temporal regions**. It is not a generic undifferentiated white-noise probe.

### 2.3. Internal processing and final CLO packing

Confirmed **call sequence** inside `0x1800BE830` (VAs):

```text
0x1800BDBE0        first preprocessing / fit stage
0x1800BD490        second processing stage
0x1800BC6B0        third processing stage
0x1800BB210  ×3    three calls, via a loop with index < 3
0x1800B9B70        final processing stage
0x1800C0D40        sample/filter processing utility (reused)
0x18000CE00        two calls to a filter-processing routine
```

**Caution:** three invocations of `0x1800BB210` receive *different arguments* and may handle different signal regions or filters; it is **not yet proven** that these correspond to three coordinate-descent fitting iterations. Likewise, naming the first three stage functions by filter or saturation role would be premature.

Packing is directly visible:

- `0x1800BF1C4`: allocate **8840 bytes** (`0x2288`).
- `0x1800BF1E5`: set body length **8704 bytes** (`0x2200`).
- `0x1800BF238`–`0x1800BF25D`: write the four final float32 parameters to offsets 104–119.
- `0x1800BF263`–`0x1800BF281`: write FIR offsets/lengths.
- `0x1800BF4DF`: write ASCII **`VTSI`** magic.
- `0x1800BF510`–`0x1800BF542`: checksum calculation using lookup tables and store at offset 8.
- Initialized/used filter lengths include **128** input FIR and **2048** output FIR. The upload-low variant uses **512** output taps, matching the transport behavior seen elsewhere.

## 3. Confirmation from actual probe WAVs

Two official Windows Manager sessions from user captures were examined: Marshall SC20 Full Rig and JCM800 2203 Crunch. Their input `nam_input_wav.wav` files have the **same SHA-256**:

`9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`

Both are exactly 70 seconds, 44.1 kHz, PCM 16-bit stereo with equal channels. Both official `outputFile.wav` are exactly 70 seconds at 48 kHz; the network outputs differ according to the NAM.

The following input RMS values are measured on the actual 70-second file (not inferred from assembly):

| Region | Input RMS dBFS | Interpretation (tentative) |
| --- | ---: | --- |
| 0–5 s | −12.38 | initial level sequence |
| 6–21 s | −54.34 | quiet signal region |
| 23–28 s | −8.01 | strong stimulus |
| 30–50 s | −26.43 | changing-level stimulus |
| 50–70 s | −16.95 | dynamic stimulus |

Gaps at 5–6, 21–23 and 28–30 seconds in the input have near-zero/zero sections; these are real boundaries, not invented categories.

As a cross-check, the approximate output resampled to 44.1 kHz crosses |sample| > 0.01 within the first 600 samples after 6 s for **both** captures: first crossing at approximately 18 samples (SC20) and 0 samples (2203). The approximation uses SciPy polyphase resampling and mean/linear detrending, **not** the DLL's exact algorithm, so the specific crossing index is **not** claimed as bit-exact.

See `probe_regions.png`, `probe_wav_regions.json` and the two verification scripts in this package.

## 4. Concrete architectural implication

A plausible interpretation, supported by the captured one-pass output WAV, fixed regions, and the assembly control flow, is:

```text
Purpose-built 70s test WAV (several distinct regions)
                  │
                  ▼
            NAM forward pass
                  │
                  ▼
       70s NAM-output WAV
                  │
                  ▼
   resample / center / detrend
                  │
                  ▼
 fixed-window, onset-aligned extraction
                  │
                  ▼
  multiple vendor DSP fit functions
                  │
                  ▼
    128 FIR-A + 4 NL + 2048 FIR-B
                  │
                  ▼
       8,840-byte VTSI / CLO
                  │
                  ▼
    upload variant: 512 post taps
```

The official path therefore **likely** does not need five *separate* full WaveNet runs for this capture: different stimulus regions are already combined in a single 70-second DI file. This helps explain speed differences, but optimized native implementation and independent DSP-fitting cost could also contribute. The available code does **not** prove all future app paths always use exactly one network run.

**Do not yet claim:** full source recovery, exact numerical reproduction of vendor CLO, equal sound quality, or identical behavior of mobile SONICLINK and Windows Manager.

## 5. Next reverse-engineering target (precise)

1. Decompile `0x1800BDBE0`, `0x1800BD490`, `0x1800BC6B0` and recover each function's input/output vectors, time regions and filter formulas.
2. Decompile the three-pass dispatch of `0x1800BB210` and distinguish stage-specific passes from iterations.
3. Recover the four nonlinear parameters by tracing writes to `context + 0x243F8` through `+0x24404` and the final packing at `0x1800BF238`.
4. Trace output coefficients through `context + 0x24408` and `+0x24410` and their conversions to the 128/2048 FIRs.
5. Build a **standalone single-70s-probe JS experiment** only after enough formula recovery, preserving the current browser converter as default. Compare both official CLO goldens and both original WaveNet outputs on held-out input regions.

Do not execute unsigned DLLs or make hardware writes as part of these steps.

## Reproducing the static checks

```bash
python inspect_htkpa_static.py /path/to/5868USB.dll --out static_evidence.json
python inspect_probe_wav.py /path/to/nam_input_wav.wav /path/to/outputFile.wav --directory .
```

The first script requires GNU `objdump`, standard Python, and the **exact pinned DLL**; the second requires NumPy/SciPy/Matplotlib and the captured session WAVs. Original vendor binaries/WAVs are intentionally **not redistributed** in this package. Both scripts are **read-only** and never load the DLL as executable code.
