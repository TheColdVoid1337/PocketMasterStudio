# HTKPA / NAM→CLO — Stage 23 continuation: definitive export branch and partial native resampler trace

**12 October 2026 · SOURCE CHECKPOINT B, NOT final Stage 23.** The user-supplied original `5868USB.dll` (Windows x64 PE image base `0x180000000`; SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`) was **read statically only**, not executed. Source-first static address pins and native PE data constants are reproducible with `stage23_resampler_branch_source.py`.

## Critical finding: the standard export dispatches the **dynamic-sample-rate** branch

The preceding Stage23 checkpoint found `0x18000F940` (fixed 44,100 Hz) and `0x180010230` (configurable Fs) but could not prove which one was called. We have now source-traced the normal exported job through its worker's **actual PE vtable**:

1. Export `namConvertCloData` at `0x1800E20AE` sets `r12d=0`, stores input/output references in common global object (pointer `0x1802A71D8`) `+0x208`/`+0x210` at `0x1800E20EA`/`0x1800E2134`, and writes `+0x27C = 0` at `0x1800E2232`.
2. The object is constructed with vtable **VA `0x180248018`** at `0x180002244/0x18000224B`. The original on-disk PE, at `0x180248018`, contains first 64-bit function pointer `0x180061610` and second at `0x180248020` contains **`0x180060F20`**.
3. Export starts the worker object at `0x1800E2239 -> 0x1801718A0`; the latter passes Windows thread entry `0x180148810` to `CreateThread`-like IAT at `0x1801718F0/0x1801718FF`. Thread entry calls `0x18015A060` at `0x180148857`; it loads the object's vtable at `0x18015A0CC` and performs a virtual call **`[vtable+8]`** at `0x18015A0D2`. Its pointed-to method is **`0x180060F20`**, the same worker whose argument object contains `+0x208/+0x210/+0x27C`.
4. Worker at `0x18006109C` checks `+0x27C == 1` for the **fixed-Fs** path (`0x1800611AF -> 0x18000FF40`). The export-initialized **zero** branches at `0x1800610A3 -> 0x18006125C`, then calls **dynamic-Fs** wrapper `0x180010E70` at `0x18006137D`.
5. Dynamic wrapper `0x180010F7F -> 0x18000E0E0` obtains an integer native rate. It sends that rate to `0x18000D4A0` via `xmm2` at `0x180011016/0x180011021` to resample the **first** file-reference pointer (`context global +0x208`, forwarded via `r15`), then invokes rate-parametrized native fitting wrapper `0x180010230` at `0x1800110AD`. Native context init uses this rate (`0x180010453/0x18001045D`) before loaders/fitter (`0x180010489/0x1800104BD/0x1800104E1`).

**Consequence:** Running the Stage23 earlier, *hypothetical fixed 44.1k* resampling of the reference WAV is NOT a test of the source-confirmed usual export route. The source-confirmed branch instead resamples the first audio file to a dynamically determined rate. This identifies a real wrong-path assumption before attempting numerical parity. Note the routine is shared by normal exported jobs; this is a **static code-path proof**, not a runtime trace of the two particular captured Manager sessions.

## Native rate detection in `0x18000E0E0`

- `0x18000E855` reads a **double** from parsed object `[rbx+0x18]`, rounds it to `float32` at `0x18000E85B`; the object is produced through an upstream parser (`0x180008B80`/`0x1800CC4E0` around `0x18000E65D/0x18000E698`). Semantics of the complete metadata object remain to be proven. Do not simply assert it equals a particular captured WAV's Fs.
- `0x18000E9B5–0x18000E9BC` tests whether that value is strictly positive; otherwise the fallback is **`48000.0f`** loaded from PE `0x18024CDF4` at `0x18000E9EA`. This is *not* the fixed caller's `44100.0f` constant.
- `0x18000EA01` explicitly checks selected native Fs against **`44100.0f`** from PE `0x18024CDF0` and takes a different path for exactly equal samples.
- Successful result is `cvttss2si ebx,xmm9` at `0x18000F620` and returns via `eax=ebx` at `0x18000F66B`. A failure path returns signed **-2** at `0x18000F900` and is guarded in the dynamic wrapper against PE double `-2.0` at `0x180010F8C`.

The hypothesis that the normal captured run used Fs=48000 is plausible, because the vendor target WAV is 48k and the fallback is 48k, **but NOT yet proven**: the parsed sample-rate object's contents for the two session files require a complete producer/consumer mapping.

## Native audio-resampler structure: what is and is not computed

`0x18000CE00` turns decoded `float32` samples to `double`, invokes multi-stage constructor `0x180011B60` at `0x18000CFF3`, processes stages through a virtual method at `0x18000D0F7/0x18000D10E`, then casts output double back to float32 at `0x18000D16B`.

- `0x18000CF3C/0x18000CF44` pass **`180.15` and `2.0`** as double constructor arguments (original PE bytes) besides actual rate pair.
- In the `2*targetFs > sourceFs` branch at `0x180011C67`, first filter ratio is `targetFs * 0.5 / sourceFs` when downsampling. At 48k→44.1k this gives `0.459375`. When 44.1k→48k, the first filter argument becomes `0.5` in the same branch. These values are **individual constructor arguments**, not proof of an entire sample waveform.
- `0x18000BB80` is a **filter descriptor cache**, comparing 5 fields and forwarding cache misses to `0x18000B0E0`. It is not the entire filter algorithm. `0x18000B0E0` derives filter extent, calls frequency/window helpers, accumulates coefficient sum `0x18000B9C0` and normalizes (`0x18000B9E3/0x18000BA02`). The exact coefficient math has not been independently rebuilt, especially its original math-library dispatch, cutoff selection, polyphase stage order and boundary modes.
- `0x18000BDF0` creates stage object referencing that filter descriptor.
- Previous Stage23 proof remains: actual loaders require exact sample-rate equality with context Fs and directly copy decoded 32-bit samples to `context+0x243E0/+0x243E8`; the four fitted fields are copied directly into CLO sat fields at `0x1800BF238..0x1800BF25D` without post-fit gain transforms.

## Reproducibility & evidence gate

The standalone verifier pins **125 native instruction addresses/operands**, **7 original PE float/double constants**, and separately reads/checks the **two original worker vtable addresses**. There are **10 lightweight synthetic scalar-branch assertions**. Two separate verification runs produced identical evidence JSON SHA256 **`36b5b4800f48ab47bb5eecc8ef1442fe2f83b988187045d9a109fda5b539c209`**. Earlier Stage21 fitter was independently re-run: **75 instruction predicates / 8 constants / 77 mathematical assertions passed**. Earlier Stage22 trace independently re-run: **43 instruction pins / 7 constants / 53 assertions passed**. No original proprietary DLL, NAM, WAV or CLO is distributed in this package.

**Important:** 125 code pins and 10 scalar tests prove address-specific findings and a *small portion* of branch algebra; they do **NOT** establish full resampler waveform equivalence. No new full-native four gains were generated or compared. Prior very-wrong generic 48→44.1 target-resampling diagnostic stands only as a rejected shortcut, not as source-proven output.

## Open strict gates

1. Reconstruct `0x18000E0E0` parser input object at `[rbx+0x18]`: identify whose file sample-rate the dynamic export actually selects, then verify 2203 and SC20 native Fs without guessing from WAV headers.
2. Rebuild `0x18000B0E0` + helper math and the complete stage scheduling of `0x180011B60`; match 44.1k→48k audio output using code-derived taps and test impulse, DC and truncation/boundary rules before using real audio.
3. Establish exact audio stream identities (the global `+0x208`, `+0x210` strings), decoder float32 PCM normalization, NAM inference output scaling, and the native loaded signal pair. Confirm target detrend/600-sample onset and true 23–28s data.
4. Feed source-confirmed inputs into the **unchanged Stage21 standalone fitter**. Compare its four independently computed gains to the held-out 2203 and SC20 official CLO **only after fitting**.
5. Only then move toward first native FIR/A-B initialization. No changes to production JS, firmware, device, or the favored hardware-auditioned v0.2C.

**Strict current status**: dynamic export dispatch = **SOURCE_PROVEN**; resampler full numerical parity = **OPEN**; real independent 4 gains = **NOT_COMPUTED**; official/independent CLO parity = **NOT_TESTED**.
