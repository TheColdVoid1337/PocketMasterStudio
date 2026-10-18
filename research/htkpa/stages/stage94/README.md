# Stage94 — original-DLL static crosscheck against public NAM, JUCE and r8brain sources

**Status:** `ORIGINAL_PE_PUBLIC_NAM_FINGERPRINTS_AND_SELECTED_XREFS_VERIFIED_STATIC_ONLY`.

This stage continues the public-source map from
[`HTKPA_PUBLIC_SOURCE_CANDIDATES_20261019.md`](../../../../docs/dev/HTKPA_PUBLIC_SOURCE_CANDIDATES_20261019.md)
and does **not** repeat Stage89–93 or change their original Frida/static gates.

## Original private input and acceptance gate

- Canonical Drive folder: `RE_HTKPA` (`1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK`).
- Canonical source ZIP: `HTKPA_CORE_20261016_012322.zip` (35,028,083 B).
- Extracted original `research/_LOCAL_FILES/vendor/5868USB.dll`: 2,902,016 B.
- Required SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.

The auditor fails closed if SHA, size, AMD64 PE headers, section mapping,
the unique fingerprint locations or any pinned RIP-relative reference differ.
Only exact-SHA original PE bytes were actually analyzed in this stage.

## Accepted compiled facts, not observed execution

The original PE has exactly **12 selected byte fingerprints** at pinned PE RVAs:

| Static source-family fingerprint | PE RVA | Public candidate |
|---|---:|---|
| Seven consecutive diagnostics from version parsing, support checks, and missing weights | `0x18F708`–`0x18F840` | [`NeuralAmpModelerCore/NAM/get_dsp.cpp`](https://github.com/sdatkinson/NeuralAmpModelerCore/blob/0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842/NAM/get_dsp.cpp) |
| MSVC `ActivationFastTanh@activations@nam` RTTI | `0x2A1A28` | [`NAM/activations.cpp`](https://github.com/sdatkinson/NeuralAmpModelerCore/blob/0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842/NAM/activations.cpp) |
| MSVC `WavAudioFormatReader@juce` RTTI | `0x2A5268` | [`JUCE/juce_WavAudioFormat.cpp`](https://github.com/juce-framework/JUCE/blob/454fe891acc8204f99f4ef1e3a28c84b1a4da145/modules/juce_audio_formats/codecs/juce_WavAudioFormat.cpp) |
| MSVC `CDSPResampler24@r8b` RTTI | `0x2A0E50` | [`r8brain-free-src`](https://github.com/avaneev/r8brain-free-src/blob/master/CDSPResampler.h) |
| Vendor `getNamOutput` start diagnostic | `0x2446D8` | Proprietary wrapper; public Valeton research is **third-party**, not vendor source |
| Vendor warning about NAM model `'head'` config | `0x18CFE0` | Proprietary wrapper; no public vendor algorithm asserted |

Seven get_dsp strings include the exact literal `Corrupted model file is missing weights.`
at `0x18F7F8`, plus diagnostics for invalid/out-of-range/negative versions,
unsupported and partially-supported versions, and null version-support checker.
`NAM/get_dsp.cpp` defines `GetWeights` and the version-support helpers with
these same literals. This substantially narrows the source-family candidate,
but **does not pin the exact compiled upstream commit** or prove any specific
source line was executed during Stage92.

The auditor also verified these exact **selected** instructions from the
compiled original `.text` (`LEA RDX,[RIP+disp32]`):

| Instruction PE RVA | Computed target PE RVA | Interpretation |
|---|---|---|
| `0xCB681` | `0x18F7F8` | first missing-weights error-use site |
| `0xCB863` | `0x18F7F8` | second missing-weights error-use site |
| `0xE2A0` | `0x2446D8` | vendor `getNamOutput` log string use |
| `0xAF353` | `0x18CFE0` | vendor NAM `'head'` warning use |

These are verified **compiled code references**, not dynamic coverage or
exhaustive cross-references. The first two can be cold/error paths.
The Stage90–93 WAV workers and Stage92's 11 ms / 10 ms same-thread Frida
sequences remain separate, and **no CLO completion is evidenced**.

## Reproduction in the existing operator WSL Bash workflow

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python -m unittest discover -s tools -p 'test_htkpa_stage94.py' -v

python research/htkpa/stages/stage94/audit_public_source_fingerprints.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage94_public_source_fingerprints.json
```

The auditor is Python-stdlib-only; neither Ghidra nor Frida is needed for
this narrow PE string/RIP-relative instruction check. Original binaries,
raw captures and complete private JSON reports remain Git-ignored in local
`research/_LOCAL_FILES/` / private `RE_HTKPA` Google Drive.

## Explicit negative boundaries

- Public [`sonicake-preset-manager/nam2clo.c`](https://github.com/andreaalcaini/sonicake-preset-manager/blob/d82a8f055b145bbbda66f8b719b58aeab97612e9/server/nam2clo/nam2clo.c)
  is a `lib5868USB.so` wrapper, not an open source reimplementation of vendor
  NAM→CLO fitting. Its low-model packing is a distinct later operation.
- No full source-equivalence proof of `getNamOutput` or `startClone` is claimed.
- No original DLL was executed and no Frida hook was installed in Stage94.
- No Stage92 same-stack/same-invocation or historical Stage89 caller proof
  follows from these source fingerprints.
- No production DSP, NAM/CLO encoder, WASM or Resampler Lab code was changed.
