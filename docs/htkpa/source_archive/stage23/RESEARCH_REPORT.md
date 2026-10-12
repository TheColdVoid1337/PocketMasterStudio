# Sonicake HTKPA — Stage 23 SOURCE CHECKPOINT

**12 October 2026 · STATIC DLL RE, read-only WAV audit; not an independently reproduced vendor converter.**

## Scope and pinned identity

The original Windows `5868USB.dll` SHA-256 **`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`** was extracted from the user's original Sonicake Manager installer and inspected as PE machine code, **never executed**. Local matching captures were verified: 2203 vendor CLO SHA `50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7`; SC20 vendor CLO SHA `2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a`; both source DI captures SHA `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`. These captures have 70 s / two identical stereo channels / PCM16: DI 44,100 Hz, output 48,000 Hz.

Prior Stage 21 and Stage 22 source verifiers were re-run on the authentic DLL. **Stage 21: 75 instruction checks, 8 constants, 77 math assertions PASSED**. **Stage 22: 43 instruction checks, 7 constants, 53 synthetic assertions PASSED**. The Stage 22 erratum remains decisive: the four-gain fitter executes **before**, not after, the separate IIR helper.

## New direct machine-code findings (40 source-pinned instructions)

### 1. Real loader mapping, no internal sample-rate conversion in either loader

- `0x1800BFA27`: input/native source pointer `context+0x243E0` is put into staging `+0x243F0`.
- `0x1800BF617`: target/reference pointer `context+0x243E8` is put into staging `+0x243F0`.
- `0x1800BFB02–0x1800BFB17` and `0x1800BF6F2–0x1800BF70D`: both require the decoded source file sampling rate (double) to **equal** `float32(context+0x20EC0)` converted to double. A mismatch follows an error branch. The check is an exact `ucomisd`, not a sample-rate converter.
- `0x1800BFCA0/0x1800BFCA7/0x1800BFCAB` (input) and `0x1800BF890/0x1800BF897/0x1800BF89B` (target) take the decoded first-channel 32-bit sample word and store it directly into the native float32 work array. Neither loop has `mulss`, `divss` or any interpolation, so **these loops themselves do not rescale or resample**. The precise upstream WAV decoder's PCM16-to-f32 convention remains a separate dependency.
- `0x1800BFCCE` and `0x1800BF8BE` mark individual loader success bytes `context+0x243D9/+0x243DA`; these are required by the guarded entry of `0x1800BE830`.

### 2. Both callers of the native loaders identified, with their different Fs provenance

**Fixed Fs path:** `0x18000F940` initializes the context at `0x18000F99A`/`0x18000F9B6` using PE float32 at `0x18024CDF0` = **44,100.0f**, then calls `0x1800BF9F0` (input), `0x1800BF5E0` (reference) and `0x1800BE830` (fit/optimization) in this order at `0x18000F9E5`, `0x18000FA1B`, `0x18000FA41`.

**Caller-configurable Fs path:** `0x180010230`, at `0x180010453`, passes the caller's `xmm6` rate to the same `0x1800BFE00` context constructor, then calls the identical two loaders and `0x1800BE830` at `0x180010489`, `0x1800104BD`, `0x1800104E1`. Thus the DLL supports a second path whose actual Fs must be traced through its own callers; do **not** assume all conversion uses 44,100 Hz solely because the first path exists.

### 3. Upstream sample-rate conversion does exist, in separate functions

At `0x1800100DA`, the caller of `0x18000F940` loads PE double `0x18024CCF8` = **44,100.0** into `xmm2` and calls `0x18000D4A0` at `0x1800100EB` before calling the fixed-rate fitter wrapper at `0x18001016D`. This creates a resampled version of the reference WAV path before the native loader. The input DI is already the matching 44,100-Hz recording.

Within `0x18000D4A0`: audio is decoded using `0x1801421C0` at `0x18000D76D`; input rate is loaded from decoder structure `[r14+8]` at `0x18000D779`, desired rate is passed from `xmm6` via `0x18000D775`, and the actual native resampler `0x18000CE00` is called at **`0x18000D786`**. The resampler copies decoded float32 samples into double arrays at `0x18000CF9B/0x18000CFA0`, constructs multistage state at `0x18000CFF3 → 0x180011B60`, computes output-length expression `trunc(float32(N*targetFs/sourceFs))` at `0x18000D031..0x18000D043`, and casts output samples double→float32 at `0x18000D16B/0x18000D17F`. This strongly identifies the precise upstream conversion location and representations. **Its numerical filter coefficient generation, boundary convention, temporal support, and saved WAV encoding are not yet proven in full.** The filter construction branches in `0x180011B60` and descendants `0x18000BB80`/`0x18000BDF0` are the next concrete disassembly target.

### 4. What this corrects

The Stage 22 statement that native sample-rate conversion was unlocated is now superseded: **actual conversion call site, two rate arguments, resampler entry and native byte-copy loops are found.** However, this is **NOT** enough to claim the exact floats fed to the fitter. The upstream audio path still requires more than just rate alignment. Also the second caller's live conversion-path reachability must be established.

## Read-only 2203/SC20 diagnostic, NOT native fit

For an explicit rejected shortcut, independently use `scipy.signal.resample_poly` on the captured 48k target to 44.1k, diagnostic float64-OLS detrend, Stage22 600-sample threshold search, and Stage21 *unchanged* standalone four-parameter fitter on 23–28 seconds. This uses **no official CLO inputs**; read official gains **only after fitting**. It is a deliberately non-native control, not source-proven CE00 output.

| Model | Fit shift (44.1k sample) | Diagnostic pmax | Diagnostic nmax | Diagnostic prate | Diagnostic nrate |
|---|---:|---:|---:|---:|---:|
| 2203 | 0 | 0.15556006 | 0.15544409 | 0.97216874 | 0.79531199 |
| SC20 | 18 | 0.07493999 | 0.06842918 | 0.63178551 | 0.70063668 |

| Model | Official pmax | Official nmax | Official prate | Official nrate |
|---|---:|---:|---:|---:|
| 2203 | 0.05869761 | 0.06251806 | 425.438965 | 356.188354 |
| SC20 | 0.01061691 | 0.01269747 | 450.926178 | 253.910919 |

The naive WAV→fitter mismatch is **very large**, including ~99.7–99.9% relative rate error. This does not isolate the root cause: the test mixes an unproven resampler, unproven captured-vs-native scale, and diagnostic non-native trend precision. Crucially, it **does rule out claiming the raw capture + generic polyphase resampling reproduces native gains.** Do not force fitted values toward held-out official parameters.

## Reproduction

```bash
python stage21_saturator_source.py --dll /path/5868USB.dll --output stage21.json
python stage23_loader_source_trace.py --dll /path/5868USB.dll \
  --capture2203 '/path/Sonicake Manager Files.zip' \
  --capture-sc20 '/path/Sonicake Manager(1).zip' --out evidence.json

# ONLY a deliberately non-native counterexample, requiring extracted WAVs/CLOs:
OPENBLAS_NUM_THREADS=1 python stage23_readonly_diagnostic.py \
  --2203 '/path/extracted/2203' --sc20 '/path/extracted/SC20' \
  --output readonly_diagnostic.json
```

40 fresh machine-instruction matches, two original PE rate constants, 5 lightweight synthetic assertions; both official capture archive hashes checked. `evidence.json` and `readonly_diagnostic.json` are included, but not the proprietary installer/DLL, user's WAV, or vendor CLO. Static instructions are short verifier needles, not redistribution of executable.

## Open gate and next operations — Stage 23 NOT COMPLETE

1. Determine from export thread/task wiring which of `0x18000F940` or `0x180010230` was actually followed for `namConvertCloData` with the two saved Manager sessions. The first explicitly 44.1 kHz; second is parameterized.
2. Finish the native resampler `0x180011B60 → 0x18000BB80/0x18000BDF0` math, including sample normalization/boundary modes, and identify the WAV representation saved then decoded by the later native loader.
3. Trace upstream reference-generation scaling and decoder PCM16 normalization, and establish why the saved `outputFile.wav` contains reference peaks that do not reproduce official four gains when passed through the simplified path.
4. Only after the two exact native arrays are source-confirmed, perform Stage21 fits on both 23–28 s real intervals, report independently computed four values and their held-out errors.
5. No claim of vendor coefficient parity, no new hardware CLO, no production UI/DSP change.
