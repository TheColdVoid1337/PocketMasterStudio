# Sonicake Manager version-history binary audit (2026-10-14)

**Scope:** static-only comparison of user-provided local archive `Sonicake_Manager_Version_History.zip` against the already SHA-pinned Stage48 **Sonicake Manager V1.5.2 (Windows)** `5868USB.dll` (PE timestamp in 2026). No old DLL executed, no Frida attach, no vendor binaries uploaded. This is a version-history research lane, **not Stage49 native sample capture**.

## Provenance, limitations, official documentation

- Local-only archive SHA256: `bb849b1b501ba7243ac05c756b56441b57f87255c7c1a44cf22b63638e88eb79`. 489 ZIP entries, 229,720,872 total uncompressed bytes; **three** top-level software builds: 1.0.1, 1.1.1, 1.3.0. Their actual shipping installers are not part of this archive: these are extracted installation trees.
- Independently pinned Stage48 **Sonicake Manager V1.5.2 for Windows** original DLL SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa` is the **fourth comparator**, obtained only from the locally supplied PRIVATE_ROLLOVER bundle. It is **not** present in the version-history ZIP. **Identification provenance:** the user explicitly confirmed the original installed Manager is **V1.5.2** and supplied its official installer URL; the Sonicake Pocket Master downloads page labels exactly that URL `Sonicake Manager V1.5.2 for Windows`. The official download ZIP's internal DLL was **not independently hashed against our pinned private DLL** in this research run; label attribution is user-confirmed, while the precise binary identity continues to be pinned by SHA.
- Manufacturer's [Pocket Master historical software download page](https://www.sonicake.com/pages/pocket-master-software-firmware-download-qme-10) explicitly offers Windows **1.0.1, 1.1.1, 1.3.0**, plus newer 1.5.2.
- Manufacturer's [Pocket Master Release Note PDF](https://cdn.shopify.com/s/files/1/0100/1950/4185/files/Pocket_Master_Firmware_V1.3.3_Release_Note.pdf?v=1752654178), page 1: **Sonicake Manager 1.3.0 released in May 2025**, adds startup Anti Touch Protection switch and optimizes compatibility with new firmware. Page 2: **Pocket Master firmware 1.1.0 (Jan 2025)** adds Clone/NAM support and *Manager* preset/IR/Clone management; earlier firmware 1.0.1 initial release **10 Dec 2024**. **Do not mislabel firmware dates as exact Sonicake Manager release dates**: direct, day-level release dates for Manager 1.0.1/1.1.1 are not established by this PDF.
- All dates below in the PE column are raw COFF TimeDateStamp interpreted as UTC, **not authenticated build/release dates**. ZIP NTFS/file mtimes do not prove publication dates.

## DLL identity and NAM timeline

**Official V1.5.2 download identity:** https://sonicake.oss-accelerate.aliyuncs.com/res/9516K6KrD2/Ampcube_Sonicake_Manager_Setup_V1.5.2_for_Windows.zip (linked from https://www.sonicake.com/pages/pocket-master-software-firmware-download-qme-10 under *Latest Software*). Installer content was not fetched or hashed; do not infer installer↔local DLL byte equality merely from version naming. Sonicake lists support for NAM A2 for Manager V1.5.2. The **July 29 2026 timestamp belongs to the PE image header**, not an authenticated Manager release date.

| Installed software | DLL bytes | DLL SHA256 | DLL PE timestamp UTC | NAM-related PE exports |
|---|---:|---|---|---|
| 1.0.1 | 1,979,392 | `73a8652108f12d67158328d474a4ae005ca3f973f15fe953c3b7ed718558a767` | 2024-08-08 01:38:53 | **0** |
| 1.1.1 | 2,413,568 | `48c8c00585b6acfc39782a46151d57df618e3ab74e355998322487c449e3e4df` | 2025-01-22 07:16:47 | **4** |
| 1.3.0 | 2,437,120 | `1c1c55a5fbab4035fcc3197fc8b8340b0dba3ad24fb59798790d80403decd0ae` | 2025-03-31 06:13:19 | **4** |
| **1.5.2 / Stage48** (2026 PE timestamp) | 2,902,016 | `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa` | 2026-07-29 12:09:35 | same 4, plus new process/error APIs and NAM→NAMB |

**Bounded conclusion:** NAM→CLO exports were introduced somewhere *between available Manager 1.0.1 and 1.1.1*. Within this archive, **1.1.1 is the earliest version demonstrably containing native NAM→CLO conversion**; exact first intermediate build is unproven. Exports newly present in 1.1.1: `appNamConvertClo`, `appNamConvertCloData`, `namConvertClo`, `namConvertCloData`. In 1.0.1, absence of exports alone cannot exclude every possible unexported converter, but it is combined with absence of NAM-specific named runtime strings and absence of bundled `nam_input_wav.wav`.

**Binary export map (RVA, not ASLR VA):**

| Export | 1.1.1 RVA | 1.3.0 RVA | **1.5.2 / Stage48** RVA |
|---|---|---|---|
| `appNamConvertClo` | `0x73BB0` | `0x762F0` | `0xAC0E0` |
| `appNamConvertCloData` | `0x73990` | `0x760D0` | `0xABEB0` |
| `namConvertClo` | `0x90260` | `0x937F0` | `0xE22A0` |
| `namConvertCloData` | `0x90030` | `0x935F0` | `0xE1F70` |

PE x64 exception-directory `.pdata` entry length for `namConvertCloData`: **547 bytes (1.1.1)**, **493 bytes (1.3.0)**, **809 bytes (V1.5.2)**. Those exported function bodies differ; **a size change is not by itself evidence of any numerical DSP difference**. Differences may reflect compiler layout or logic. Other NAM conversion exports also differ (e.g. `namConvertClo` 665 → 668 → 913 bytes).

New exports from 1.1.1 to 1.3.0 are `getAppNormalWav` and `initWithWaveDicPathJson`; none of the four NAM exports disappears. Comparing 1.3.0 to the separate **V1.5.2 / Stage48** DLL: additional APIs include `appNamConvertCloDataWithProcess`, `namConvertCloDataWithProcess`, `appGetLastNamConvertCloError`, `getNamConvertCloErrorMessage`, `cloConvertSampleRate`, `convertNamToNamb`, `convertNamToNambAtPath`, `convertNamToNambWithSlim`, `getLastNamToNambError`. These are **concrete interface changes**, not proof of output parity/nonparity.

## Important: r8brain processing *predates* NAM→CLO and remains almost unchanged

All FOUR DLLs contain MSVC RTTI for `r8b::CDSPResampler24`, `r8b::CDSPBlockConvolver`, and `r8b::CDSPFracInterpolator<...>`. These class names exist **even in 1.0.1 without NAM conversion exports**. `NamConvertThread` and `AppNamConvertThread` RTTI appear from 1.1.1 onward.

Class type descriptor → MSVC x64 Complete Object Locator → vtable → seventh `process` method (independently cross-checked by PE data):

| DLL | Fractional vtable RVA | `CDSPFracInterpolator::process` RVA | `CDSPResampler24::process` RVA | `CDSPBlockConvolver::process` RVA |
|---|---|---|---|---|
| 1.0.1 | `0x1968E8` | `0x9150` | `0x81A0` | `0x72F0` |
| 1.1.1 | `0x1E8F60` | `0x2C000` | `0x2B3C0` | `0x2A240` |
| 1.3.0 | `0x1E9E68` | `0xBE80` | `0x9FF0` | `0x6FF0` |
| **1.5.2 (2026 PE)** | `0x245170` | `0x135C0` | `0x11850` | `0xC220` |

**Four-way direct .text binary comparison**: compare the **1904-byte / 0x770 region** from fractional `process` RVA to the next adjacent virtual method implementation in each build. Each pair 1.0.1→1.1.1, 1.1.1→1.3.0, 1.3.0→1.5.2 has **1895/1904 identical bytes (99.527%)**. The **ONLY nine different bytes** are in three 3-byte spans at relative offsets `+0x34..0x36`, `+0x50..0x52`, `+0x121..0x123`, corresponding to relocation-sensitive RIP-relative references; inspected disassembly maintains the same control flow/instruction layout. The shared `CDSPResampler24::process` **208-byte / 0xD0 region** is literally byte-identical across all four DLLs, SHA256 `650004c093248ebbb6a575302fa2da3edcc2245a7b52ffa9ef17427d43c6e5d8`.

This is **strong static evidence** that the core fractional processing instruction stream is unchanged from Aug 2024's DLL through the **V1.5.2** DLL (whose PE header timestamp is in 2026); **NOT proof** of same coefficients, host flags, buffer state, preprocessing, or original numerical 48-kHz vendor output. The different RIP references target version-specific relocated static/working storage; mapped/readable `*R15` in Stage48 still does **not prove allocated capacity or lifetime**, and does not relax Stage49 guards.

## Bundled calibration audio and packaging differences

- `data/flutter_assets/assets/wavs/nam_input_wav.wav` **absent** from 1.0.1, present in both 1.1.1 and 1.3.0 and **bit-identical** (SHA256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`). WAV decoded header: **PCM 16-bit, stereo (2ch), 44,100 Hz, 3,087,000 frames = exactly 70.0 seconds**, 12,348,104-byte RIFF file. This may provide a pinned calibration stimulus/provenance for future chain analysis; **not** automatically the 2680-f64 Stage38 capture or an observed native output.
- 1.3.0 bundles **two identical** `5868USB.dll` copies: `assets/5868USB.dll` and `data/flutter_assets/assets/5868USB.dll`; also introduces `data/flutter_assets/assets/5868USB.dylib` and icon assets. No duplicated DLL version conflict inside the provided 1.3.0 tree.
- Inventories: 1.0.1 = 74 regular files, 1.1.1 = 159, 1.3.0 = 163. 1.0.1→1.1.1 has 85 new files, 12 changed common files, 62 identical common files; 1.1.1→1.3.0 has **4 added, 11 changed and 148 identical files** (none deleted). `data/app.so` and native DLL both changed in both transitions. 1.1.1 first contains literal `namConvertCloData` in `data/app.so`, consistent with GUI→DLL bridge; static strings alone do not prove runtime invocation.
- 1.1.1 additionally exports `setNoFilterArray`, renames `pause/play/stop` to `pauseDrum/playDrum/stopDrum`. Manager 1.3.0 adds the two new exports above, consistent with API expansion rather than removal of NAM support.

## Relevance and next work

1. **No need to redo Stage38–48.** Preserve accepted Stage48 native metadata + stable CLO and separate lifecycle PASS.
2. The original **V1.5.2 / Stage48** DLL is still the **only approved runtime target** for Stage49; do not reuse its RVA or vtable pins with 2024/2025 DLLs. If cross-version Frida experiments are ever requested, each version needs an independent SHA/RVA contract, separate compatibility preflight and explicit safety gate.
3. Stage49 Gate A remains pointer provenance, allocation capacity and lifetime before opt-in bounded f64 copy. Identical fractional instructions may be useful for historical r8brain attribution, but do not equate them with a numerical parity result.
4. Promising separate follow-up: source-first **versioned NAM conversion call graph and fitter parameters** (1.1.1 vs 1.3.0 vs 1.5.2), using exports, RTTI and local WAV; distinguish compiler layout shifts from proven algorithm changes. This is a separate research lane, not a reason to delay the Stage49 safety gate.

**Privacy:** all DLLs, `app.so` files, WAV, binaries, original ZIP, and samples remain local. This report contains only public release references, names, numeric static observations and SHA hashes.
