# Sonicake HTKPA Stage 23 — native WAV loader and resampler SOURCE CHECKPOINT

**12 October 2026 — research checkpoint, NOT the completion of Stage 23.** Original x64 Sonicake Manager `5868USB.dll`, SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, PE base `0x180000000`. Source bytes statically disassembled, never executed. No production JS changes, no pedal writes, no vendor CLO generation. Prior Stage21 (75 instruction pins, 8 constants, 77 math assertions) and Stage22 (43 pins, 7 constants, 53 assertions) were reverified on the original DLL.

## Main new machine-code evidence

**Native loader dataflow**: `0x1800BFA27` takes `context+0x243E0` (input) and `0x1800BF617` takes `context+0x243E8` (reference), each temporarily routed through `context+0x243F0`. The sample-copy loops are `0x1800BFCA0/0x1800BFCA7/0x1800BFCAB` and `0x1800BF890/0x1800BF897/0x1800BF89B`, respectively. These loops perform direct 32-bit stores of decoded samples: no interpolation, multiply or normalization *in those loops*. The WAV/audio decoder upstream remains relevant to precise input scale and format. Loader success bytes are `+0x243D9` / `+0x243DA`.

Both loaders check that decoded WAV sample rate (double) **equals** the active `float32(context+0x20EC0)` promoted to double. In particular `0x1800BFB02–0x1800BFB17` and `0x1800BF6F2–0x1800BF70D` contain `ucomisd` equality checks, not resampling.

**Two caller paths**:
- `0x18000F940` initializes native context Fs using PE `float32` at `0x18024CDF0` = **44,100.0** (`0x18000F9A7` → `0x18000F9B6`). It calls input loader at `0x18000F9E5`, reference loader at `0x18000FA1B`, then the optimizer at `0x18000FA41`.
- `0x180010230` instead passes its caller-supplied rate via `xmm6` at `0x180010453` → `0x18001045D`, then calls the same two loaders and optimizer at `0x180010489`, `0x1800104BD`, `0x1800104E1`. The actual rate and branch reachability of a particular Manager session must not be assumed.

**Upstream 44.1k conversion found**: one caller loads PE `double` at `0x18024CCF8` = **44,100.0** (`0x1800100DA`), calls `0x18000D4A0` at `0x1800100EB` to convert the target audio, then calls the fixed-rate `0x18000F940` at `0x18001016D`. Within `0x18000D4A0`, the actual native **audio resampler** `0x18000CE00` is called at `0x18000D786`, with the decoder rate from `[r14+8]` and desired rate from `xmm6` (`0x18000D775–0x18000D783`). `0x18000CE00` promotes input f32 samples to doubles (`0x18000CF9B/0x18000CFA0`), calls multistage resampler-state constructor `0x180011B60` at `0x18000CFF3`, and stores output doubles as float32 (`0x18000D16B/0x18000D17F`). Its output count uses native cast/truncation of `N * targetFs / sourceFs` at `0x18000D031–0x18000D043`. The precise filter generation and boundary behavior under `0x180011B60`, `0x18000BB80` and `0x18000BDF0` remain OPEN.

The confirmed call order from Stage22 still holds: `0x1800BEDE4` nonlinear four-gain fitter executes **before** the separate IIR helper at `0x1800BEE25`.

## Capture identity and independent negative control

Both 70-second stereo PCM16 DI WAVs are byte-identical: SHA256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`, Fs **44,100**; output WAVs are **48,000**. Corresponding read-only official vendor CLO SHA: 2203 `50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7`, SC20 `2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a`.

A deliberately **NON-native-parity** diagnostic used generic SciPy polyphase downsampling of 48k target WAV to 44.1k, diagnostic float64-OLS detrend, 600-sample alignment and the unchanged Stage21 fitter on the 23–28-second region:

| Model | Diagnostic 44.1k onset | Diagnostic (pmax,nmax,prate,nrate) | Official read-only (pmax,nmax,prate,nrate) |
| --- | ---: | --- | --- |
| JCM800 2203 | 0 | (0.15556006, 0.15544409, 0.97216874, 0.79531199) | (0.05869761, 0.06251806, 425.438965, 356.188354) |
| SC20 | 18 | (0.07493999, 0.06842918, 0.63178551, 0.70063668) | (0.01061691, 0.01269747, 450.926178, 253.910919) |

This **fails grossly** and MUST NOT be mislabeled an independent calculation of vendor gains. The diagnostic does not reproduce the actual `0x18000CE00` resampler, native f32 trend arithmetic, full upstream audio scale or branch choice. Official CLO parameters were read only **after** the candidate fit and never used to fit/tune it.

## Reproducibility and open strict gate

Research-only ZIP `Sonicake_HTKPA_DLL_RE_Stage23_SOURCE_CHECKPOINT_v0_23.zip` provides `stage23_loader_source_trace.py`, `stage23_readonly_diagnostic.py`, unchanged Stage21 fitter, JSON evidence and detailed source report, excluding vendor DLL/WAV/CLO. **40 new address-specific instruction pins**, two original PE rate constants and five lightweight synthetic tests verified; a second run produced byte-identical `evidence.json` SHA256 `37eaf5cce083481322560fe7848bd0b92abebe5fb4006c38e63cf270f2e3469d`.

**Stage23 remains OPEN**: (1) prove which wrapper path is reached by the normal `namConvertCloData` sessions, (2) reconstruct `0x180011B60` / `0x18000BB80` / `0x18000BDF0` numerical resampler, (3) trace actual decoded native audio gain/scaling and reference preparation, and (4) only then compute genuine Stage21 four gains independently for **both** models and compare against the held-out official CLO. No production or hardware changes.
