# Sonicake HTKPA Stage 23D — NAM-derived native sample rate and WAV provenance

**12 October 2026 · source checkpoint, NOT completion of Stage23 or numerical vendor parity.** Original `5868USB.dll` is statically read only; SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. No device, firmware, production JS or CLO writes.

## Newly established export argument/data flow

The ordinary `namConvertCloData` export at `0x1800E1F70` records Win64 first argument (CLO result) at job `+0x200` (`0x1800E20C1`), the two WAV paths at `+0x208/+0x210` (`0x1800E20EA/0x1800E2134`) and its fourth model-path argument at `+0x218` (`0x1800E2157/0x1800E219C`). The export sets `+0x27C=0`, reaching the dynamic-rate worker, as already proved in Stage23B.

Worker `0x180061305/0x180061329/0x18006137D` forwards the WAV paths and the separate NAM descriptor (from job `+0x218` via `0x1800126E0`) to `0x180010E70`. This function invokes `0x18000E0E0` at `0x180010F7F` to obtain the target sample rate. Source strings in the exact original PE identify that routine: `[NAM] ========== getNamOutput start ==========` at `0x1802446D8`, `[NAM] namFile: ` at `0x180244708`, `[NAM] outputFile: ` at `0x180244730`, and **`[NAM] model sampleRate: ` at `0x180244800`**. `0x18000E65D/0x18000E698` convert/parse the model; `0x18000E855` reads its rate as a double from the decoded metadata object `[rbx+0x18]`; `0x18000E85B` narrows it to f32 and `0x18000E8A2` logs it. Fallback only when nonpositive is original PE `48000.0f` (`0x18000E9EA`); `0x18000F620` returns integer selected rate.

**Independent model-file inspection:** Both user-supplied model JSONs contain `sample_rate=48000` at their root and in both nested submodels:
- 2203 NAM SHA reference `29abbdbf982ee64b963d1d8de06848d1b06450a623bb08ba3ffefce146dfac42`
- SC20 NAM SHA reference `509ad3d6dc31cf0539afe4a264ff7386d6282ffe9d1e0de4b6cce514b1915b11`

This establishes **native nominal Fs=48,000 for these two standard model paths**, conditional on the documented successful export branch. This is stronger than the previously unproven assumption based solely on an output WAV header, though it is not a live memory dump of a running Manager instance.

## Correct direction and buffer roles

Actual captured DI `nam_input_wav.wav` is PCM16 stereo **44,100 Hz, 70 seconds**, while NAM reference `outputFile.wav` is PCM16 stereo **48,000 Hz, 70 seconds**; the DI WAV is byte-identical across the two sessions (SHA `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`).

In `0x180010E70` the first WAV path is passed via `r15` into `0x18000D4A0` (`0x180011019–0x180011021`) using model-selected Fs, and the converted first path plus unchanged second WAV are passed to `0x180010230` (`0x1800110AD`). Native rate initialization: `0x180010453/0x18001045D`. The first native audio loader `0x1800BF9F0` fills `context+0x243E0`, the second `0x1800BF5E0` fills reference `context+0x243E8`. Reader `0x1801421C0` selects first-channel buffer (`0x180142201/0x180142223`), followed by original 32-bit sample-word copies (`0x1800BFCA7/0x1800BFCAB`) without gain multiplication **in that copy loop**. Both captured stereo channels match, so the first-channel selection does not matter for these particular files. Native decoder PCM16→f32 scaling inside `0x180141680` and native multistage resampling are NOT YET reproduced.

**Critical correction:** the previously tested 48→44.1 target-resampling diagnostic assumed the wrong path. The standard source-confirmed direction is **DI 44.1→48k**, with 48k reference retained.

## Negative numerical control on the correct nominal Fs

A deliberately **NON-native** SciPy `resample_poly(160,147)` applied to DI, an approximate float64 OLS detrend of target, Stage22 onset selection, and the unchanged Stage21 23–28 second fitter yielded:

| Model | onset @48k | independent NON-native pmax | nmax | prate | nrate | official held-out pmax | nmax | prate | nrate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2203 | 0 | 0.15571578 | 0.15541093 | 0.97062504 | 0.79495490 | 0.05869761 | 0.06251806 | 425.438965 | 356.188354 |
| SC20 | 19 | 0.07492959 | 0.06844199 | 0.63143349 | 0.69999969 | 0.01061691 | 0.01269747 | 450.926178 | 253.910919 |

Official vendor gains were read **only after** the independent candidates. This negative control is not a reproduction of original `0x18000CE00`, its 2× FIR and 24-neighbor, 673-phase interpolation, its decoder, f32 OLS or other signal scaling. The enormous disagreement remains an OPEN source-trace problem; **do not tune a scaling factor or fit against official CLO values.**

## Reproducibility and strict gate

The original research-only Stage23D ZIP `Sonicake_HTKPA_DLL_RE_Stage23D_SOURCE_CHECKPOINT_v0_23d.zip` includes `stage23d_source_provenance.py`, `test_stage23d.py`, the explicit non-native diagnostic, repeatable evidence and report, excluding DLL, NAM, WAV and CLO. The local source-first verifier passed **42 address-specific assembly pins**, **5 PE log-string byte checks**, **48000.0f constant**, plus **5 pure metadata unit tests**. Two evidence runs were identical SHA256 `02ffe50f98ba53ade3b5ef4895f317c767ea288896f0920098d3f2dd1ec09ba5`. Stage21 (75/8/77) and Stage22 (43/7/53) were independently rerun and passed on the pinned DLL.

**Still OPEN**: exact `0x180141680` PCM decoder and scaling, `0x18000D4A0/0x18000CE00` FIR and fractional interpolation coefficient/dataflow parity, exact target processing, and both independently fitted four-gain sets. Stage23 remains open; no official-equivalent CLO has been generated.

**Next research target:** trace `0x180141680` decoding/sample scale and the resampler's buffer/state assignments **before** another gain attempt. Keep the production Void Mod and hardware-vetted 2203 v0.2C unchanged.
