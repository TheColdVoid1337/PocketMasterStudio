# HTKPA — targeted public-source crosscheck after Stage93 (2026-10-19 Bangkok)

**Status:** `PUBLIC_SOURCE_CANDIDATES_IDENTIFIED_BINARY_PROVENANCE_NOT_REVERIFIED`.

This is a **public-code/source investigation**, not a new vendor-DLL audit,
Frida run, completed NAM→CLO conversion, or proof of code ancestry. Stage93's
original SHA-pinned static and Stage92's actual Frida facts remain the current
accepted binary/runtime gates. Do not claim a future or current upstream
release equals the proprietary vendor build without byte/ABI evidence.

## What turned up and how strongly it applies

| Source (pinned source or project) | What is actually public | Relation to existing HTKPA evidence | Strict limit |
|---|---|---|---|
| [r8brain-free-src `CDSPResampler.h`](https://github.com/avaneev/r8brain-free-src/blob/master/CDSPResampler.h) | Full open DSP resampler, fractional interpolator, convolution and multistage logic | Already investigated in Stage63–66; narrowly measured near-machine-precision native/public prefix parity with a transient public-source patch | Does not establish identical embedded upstream revision or full NAM→CLO algorithm |
| [NeuralAmpModelerCore `NAM/get_dsp.cpp`](https://github.com/sdatkinson/NeuralAmpModelerCore/blob/0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842/NAM/get_dsp.cpp) and [`NAM/container.cpp`](https://github.com/sdatkinson/NeuralAmpModelerCore/blob/0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842/NAM/container.cpp) | `.nam` JSON, weights, sample-rate parsing, real DSP constructors; named `SlimmableContainer` registration and nested-model construction | Original Windows DLL Stage77–85 verified the corresponding architecture vocabulary, factory/registry and nested-model routes; independent ARM64 `5868USB.dylib` research describes `getNamOutput` parsing NAM and running its inference | An exact distinctive error string (below) was confirmed in **public NAM Core and third-party ARM64 analysis**, **not freshly rescanned in our Windows DLL** during this lookup |
| [JUCE `juce_WavAudioFormat.cpp`](https://github.com/juce-framework/JUCE/blob/454fe891acc8204f99f4ef1e3a28c84b1a4da145/modules/juce_audio_formats/codecs/juce_WavAudioFormat.cpp) | WAV reader implementation in original JUCE repository | Stage90 Ghidra already resolves `juce::WavAudioFormat` construction/reader capability in `0xD4A0`; Stage93 original PE pins conditional entry calls | Library-family correspondence, not the exact Sonicake WAV conversion wrapper or executed file/rate |
| [Valeton GP-50 `REFIT_FINDINGS.md`](https://github.com/drewmerc302/valeton-gp50/blob/aadcf9b7a2f051d8bce50b8654a6a935a07a06b0/re/REFIT_FINDINGS.md) | Independent Ghidra-derived notes on **ARM64 `5868USB.dylib`**: `AppNamConvertThread`, `getConvertNormalWav`, `getNamOutput`, `startClone`; claims NAM inference followed by proprietary compact refit | Highly relevant parallel investigation, especially post-NAM fitting after WAV excitation | Its `startClone` algorithm is **not** publicly reimplemented there; ARM64 Valeton binary/2.7 KB SnapTone ≠ authenticated Windows DLL/8,840-byte CLO; all cross-device statements are third-party inference |
| [Sonicake Preset Manager `nam2clo.c`](https://github.com/andreaalcaini/sonicake-preset-manager/blob/d82a8f055b145bbbda66f8b719b58aeab97612e9/server/nam2clo/nam2clo.c) and [`server.py`](https://github.com/andreaalcaini/sonicake-preset-manager/blob/d82a8f055b145bbbda66f8b719b58aeab97612e9/server/server.py) | Public code for calling vendor `namConvertCloDataWithProcess` asynchronously, checking an 8,840-byte CLO, calculating a CLO CRC and truncating/repacking one CLO as a **2,696-byte Low Model** | Actual vendor API/ABI call hypothesis and adjacent post-CLO format code to compare against our Stage1–23 VTSI/CRC research | **Not** an independent NAM→CLO inference/refit algorithm: actual conversion still runs inside proprietary DLL / Android `.so`; wrapper not independently validated on our exact DLL or our operator machine |

Additional primary source: [official `NeuralAmpModelerCore` activation implementation](https://github.com/sdatkinson/NeuralAmpModelerCore/blob/0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842/NAM/activations.cpp)
defines `nam::activations::Activation::using_fast_tanh`. The independent
Valeton ARM64 report identifies the same symbol/family. This confirms a
specific **public implementation candidate** for that named NAM component,
not its precise compiled revision in Windows.

## Exact-source fingerprint worth testing next

The distinctive diagnostic
`Corrupted model file is missing weights.` appears verbatim in public
NeuralAmpModelerCore `NAM/get_dsp.cpp`, in `GetWeights`' missing-key error.
The independent Valeton ARM64 analysis also reports this string in the
NAM-loading path. It would be a stronger, falsifiable direct link if the
same string and related callsite could be found in our **SHA256-pinned Windows
`5868USB.dll`** by a new bounded read-only static audit. That direct
Windows byte check has **not** been performed in this public lookup;
Stage77–85's original architecture/registry findings are independently
accepted and are not a substitute for this exact-string check.

The Sonicake repository publicly lists `server/5868USB.dll` at **2,902,016
bytes**, equal to the historical pinned Windows DLL's length. No SHA256
of that *external repository blob* was independently computed here, so this
is **not** a byte-identity claim. Do not download or publish vendor binaries
as a substitute for the canonical private original.

## Search negatives and next gate

- Queries for the **exact** `getAppNormalWav`, `startClone` implementation,
  and the diagnostic `failed to convert input WAV to NAM sample rate` did
  not reveal a separate public implementation of the proprietary conversion
  wrapper. Search-index absence is not proof that source does not exist.
- The standout **fully public postprocessing** candidate is
  `server.py::convert_clo_to_low`: edits VTSI length, packed-region size,
  a field at `0x84`, and recalculates CRC16. It converts a previously
  generated valid CLO; it does **not** create the original CLO from NAM.
- Concrete next low-risk test: an **offline original-PE fingerprint scan**
  for the NAM Core `GetWeights` error string and related diagnostic/xref
  cluster, with pinned DLL SHA, no vendor DLL execution. Only if positive,
  inspect whether the decoded local error/dispatch code corresponds to the
  official `NAM/get_dsp.cpp` version(s). This could justify a future narrow
  stage, but no new Stage94 result is yet claimed.
- If the objective is independent full NAM→CLO, focus later on the
  **post-inference compact fitting/`startClone` gap**; public NAM Core,
  JUCE and r8brain alone do not reconstruct it.

**Evidence boundaries:** Public-source code and third-party Ghidra notes
are leads. Neither proves an executed Stage89/92 wrapper branch, a same-
invocation Stage92 stack, a new native sample rate, successful CLO output,
or an exact common binary across Windows/Android/Valeton builds.
