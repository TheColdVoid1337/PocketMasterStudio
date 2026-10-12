# Sonicake HTKPA Stage 23C — exact resampler stage topology and 24-tap polynomial interpolation

**2026-10-12. SHA-pinned source checkpoint, NOT completed Stage23 or official audio numerical parity.** Original Windows x64 `5868USB.dll`: SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. Original PE bytes statically disassembled; no DLL execution, new vendor CLO, firmware or hardware action, or production Void Mod modification.

## Corrected model of native resampler for the common 44.1 ↔ 48 kHz pair

The routine `0x180011B60` takes the `2*target > source` branch for both 44.1→48 and 48→44.1 kHz. **The realized architecture is a 2:1 FIR intermediate stage followed by a separate fractional polynomial interpolation stage**, not one single filter with simple integer sample selection. This corrects an over-narrow statement in the Stage23B research discussion; that study identified only the first FIR filter descriptor construction.

1. At `0x180011CE3` the filter descriptor cache `0x18000BB80` is invoked; first-stage `0x18000BDF0` is constructed at `0x180011CFE` with `r8d=2` and `r9d=1` (`0x180011CEF/CF5`). The original PE vtable at `0x180244EA0` stores method pointers `[0x18000CC70,0x18000C100,0x18000C110,0x18000C120,0x18000C140,0x18000C160,0x18000C220]`. Its +0x20 sizing function `0x18000C140` implements `(p*N-1+phase+q)/q` using signed integer division. The stage initializes `phase=0` at `0x18000BF21`, so the first 2:1 stage allocates for `2*N` output samples.
2. The comparison at `0x180011D6E..0x180011D7C` leads through `0x180011F04/0x180011F1F` into `0x180012170`: allocate another object of size `0x1048` with **different vtable** VA `0x180245170`. `+0x1008` stores `2*source_Fs`, `+0x1010` stores `target_Fs`; its stage object is stored at `resampler+0x50` (see `0x18001222A`).
3. This second vtable contains `[0x180014320,0x180011AC0,0x180011B50,0x180013DC0,0x180013D90,0x180013D30,0x1800135C0]`. Capacity function `0x180013D90` returns **`ceil(N*target_Fs/intermediate_Fs)+1`**. `0x18017E10A` is the `ceil` import via `0x18018BA30`. This is **a capacity**, not evidence of extra PCM sample being emitted. For 70s source DI 3,087,000 frames @44.1kHz, the first capacity is 6,174,000 @88.2kHz and the second capacity 3,360,001 at target 48k; the saved capture WAV still has exactly 3,360,000 frames. For reverse 48k→44.1k, capacities are 6,720,000 and 3,087,001.

## Source-proven fractional interpolation layout

The second-stage process method `0x1800135C0` loads phase-polynomial table base `0x1802C7560` at `0x1800135F1`. PE `double` constant **673.0** at `0x18024CCB8` is loaded at `0x18001360C`, and the phase-bin selection `0x180013763–0x18001377B` calculates `bin=trunc(phase_fraction*673)`, with a local fractional remainder.

The table offset for each bin is **576 bytes** (24 sample positions × 3 `f64` coefficients per sample) at `0x18001376F–0x180013775`. The evaluator uses the local fraction and its square to evaluate three-coefficient polynomials and multiply the resulting weights by **24** neighboring `double` samples (offsets `+0x8` through `+0xC0`), accumulating them into one output double stored at `0x180013C38`. The next phase/index gets updated at `0x180013C49–0x180013CAD`. Total logical phase-table footprint = **673×24×3×8 = 387,648 bytes**.

**Critical detail:** the runtime phase table `0x1802C7560` has no direct original on-disk PE bytes. It is produced inside the binary: `0x1800163FF` references this global and `0x180016440..0x18001687B` performs arithmetic and in-place coefficient writes. It cannot safely be copied from static `.rdata`.

## First-stage FIR generation

At `0x18000B9A1`, the filter constructor calls FFT/buffer setup `0x18000AFA0`; `0x180014810` synthesizes symmetric oscillator/window-like tap data. Its radial window helper `0x180008FD0` computes a `sqrt(1-t*t)` term and calls `0x180008E90` (Bessel-style special function) with stored normalization. The source shape is compatible with a Kaiser/Bessel window, but **native coefficient values, exact special-function approximation, support length and boundary processing remain unverified**. Coefficient summation and normalization are proven at `0x18000B9C0` and `0x18000B9E3/0x18000BA02`.

## Reproducibility / strict open gate

Research-only `Sonicake_HTKPA_DLL_RE_Stage23C_SOURCE_CHECKPOINT_v0_23c.zip` includes standalone read-only `stage23_polyphase_source.py`, minimal `pe_bytes.py`, proof JSON (two runs), Stage21/22 check JSON, report, README, SHA256 sums. The original DLL, WAV/NAM captures, and official CLO are **excluded**.

Run: `python stage23_polyphase_source.py --dll /path/to/5868USB.dll --out evidence_new.json` (requires `objdump`, SciPy only for synthetic check). Verified **79 address-specific PE instructions, 14 vtable pointers, one PE phase-count constant and 10 independent synthetic math assertions**. Two runs produced identical evidence JSON SHA256 `16c9b523288bd3fda904439dc2671e5e9c3ec89a866deea52e1a1e07aec5ae83`; archive CRC passed. Stage21 and Stage22 original verifiers passed again: **75/8/77** and **43/7/53**.

Captured DI: common 70s PCM16 stereo 44.1kHz SHA256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`; output WAVs 70s PCM16 stereo 48k. Read-only CLO SHA256: 2203 `50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7`, SC20 `2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a`.

**Still OPEN:** exact numeric Bessel/FIR coefficients in `0x18000B0E0/0x180014810`; full dynamic polynomial table initialization and 24-tap evaluator from `0x1800161xx–0x18001687B`; metadata Fs selection for two real exports; native sample scale, target detrend and alignment; genuine independent Stage21 gain fit for both Marshall models. **Four vendor gains NOT_COMPUTED.** Do not substitute generic resampling or tune toward oracle CLO. Stage23 is not finished, and no production integration is authorized by this checkpoint.
