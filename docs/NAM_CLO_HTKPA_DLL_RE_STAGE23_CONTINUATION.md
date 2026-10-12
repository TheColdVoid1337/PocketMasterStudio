# HTKPA Stage 23 continuation — source-confirmed export branch and resampler checkpoint

**12 October 2026. This is Stage 23B, a source checkpoint, NOT a completed converter or end-to-end parity.** Proprietary DLL read statically, never loaded/executed. Original DLL SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. No production JS, CLO, hardware or firmware writes.

## Critical branch discovery: regular export uses the dynamic-Fs route

The previous [Stage 23](NAM_CLO_HTKPA_DLL_RE_STAGE23.md) identified both a fixed-44.1-kHz wrapper and a dynamic-Fs wrapper but did not prove which normally runs. The original PE permits a direct virtual-dispatch proof:

1. Export `namConvertCloData` initializes common global object (at `0x1802A71D8`) by storing its two file pointers at `+0x208/+0x210` (`0x1800E20EA/0x1800E2134`) and setting mode `+0x27C = 0` at `0x1800E2232` after clearing `r12d` at `0x1800E20AE`.
2. Object constructor at `0x180002244/0x18000224B` assigns its vtable VA `0x180248018`. Original PE pointers there are `0x180061610` (slot 0) and **`0x180060F20`** (slot 1).
3. Export calls thread starter `0x1801718A0` at `0x1800E2239`. The thread entry `0x180148810` is passed at `0x1801718F0`, then calls `0x18015A060` at `0x180148857`; at `0x18015A0CC/0x18015A0D2`, the worker executes `call [vtable+8]`. This resolves to **`0x180060F20`**.
4. At `0x18006109C` this worker tests `+0x27C == 1`. Mode 1 calls fixed-Fs route `0x18000FF40` (`0x1800611AF`). Mode 0 takes the other branch (`0x1800610A3 -> 0x18006125C`) and calls **dynamic-Fs `0x180010E70` at `0x18006137D`**. Matching object file fields are read at `0x180061305/0x180061329`.
5. Dynamic wrapper calls frequency detection `0x18000E0E0` (`0x180010F7F`), **resamples the first file-reference audio** through `0x18000D4A0` at `0x180011021`, and passes the selected Fs to fitting wrapper `0x180010230` (`0x1800110AD`). The latter initializes native context at `0x180010453/0x18001045D` then calls input/reference loaders/fitter at `0x180010489/0x1800104BD/0x1800104E1`.

**Correction to experimental interpretation:** Earlier Stage23 generic **reference** WAV 48→44.1 downsampling is a deliberately rejected diagnostic. It must not be treated as a model of this normal export route: native export uses dynamically selected Fs and resamples the **first file-reference stream**. This establishes normal exported code routing statically, not a runtime capture of individual Manager executions.

## Dynamic sample-rate selection

At `0x18000E855/0x18000E85B`, `0x18000E0E0` reads parsed object field `[rbx+0x18]` as `double`, rounds to `float32`. `0x18000E9B5–0x18000E9BC` tests positive. On non-positive, fallback is original PE **48000.0f** at `0x18024CDF4` loaded at `0x18000E9EA`. A special comparison to **44100.0f** from `0x18024CDF0` occurs at `0x18000EA01`. Successful result uses `cvttss2si ebx,xmm9` (`0x18000F620`) and returns `eax=ebx` (`0x18000F66B`); errors can return `-2` (`0x18000F900`).

The precise parsed metadata's producer and concrete native Fs for the two captured model sessions remain unproved. **48000.0f is a proven fallback, not necessarily the observed native Fs.**

## Resampler internals still open

`0x18000CE00` converts f32 samples to double and builds stages with `0x180011B60`; converter arguments include PE doubles **2.0** and **180.15** (`0x18000CF44/0x18000CF3C`). For 48k→44.1k in the first applicable constructor branch, the filter argument is `0.5*44100/48000=0.459375`; for 44.1k→48k it is `0.5`. These are *first-stage constructor parameters*, not independently reconstructed waveforms.

`0x18000BB80` is a 5-field filter descriptor cache. On miss it invokes `0x18000B0E0`, which allocates a coefficient array, generates and normalizes its taps (`0x18000B9C0/0x18000B9E3/0x18000BA02`); `0x18000BDF0` constructs a stage. Exact filter generation, multistage scheduling, boundary conventions, PCM-to-f32 scaling and actual target dataflow **remain open**. Stage22's important call-order correction remains valid: four-gain fitter executes before later IIR.

## Verification and acceptance gate

Research-only ZIP `Sonicake_HTKPA_DLL_RE_Stage23_CONTINUATION_v0_23b.zip` (provided separately) contains standalone verifier, evidence JSON, two prior-stage validation outputs and detailed report, without vendor DLL/user WAV/NAM/CLO. Tests on the SHA-pinned DLL: **125 specific instruction pins, 7 original PE constants, 2 vtable function pointers, 10 scalar branch assertions** passed. Two verifier runs yielded byte-identical `evidence.json`, SHA256 `36b5b4800f48ab47bb5eecc8ef1442fe2f83b988187045d9a109fda5b539c209`. Stage21 independently passed **75/8/77**; Stage22 **43/7/53**.

**Stage 23 remains OPEN; real vendor gain fit NOT_COMPUTED.** Next strict tasks: (1) resolve the metadata producer and native Fs for real sessions; (2) reconstruct `0x18000B0E0`, `0x180011B60` resampler and exact audio scaling/stream association; (3) source-recreate the two native float32 arrays, target detrend, onset and 23–28s region; (4) only then call unmodified Stage21 fitter and compare four independently derived gains to official 2203/SC20 held-out values. No speculative fitting or production integration.
