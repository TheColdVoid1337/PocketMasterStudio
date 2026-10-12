# HTKPA / NAM → CLO — current research status (Stage23O)

**13 October 2026 · DOCUMENTATION SYNC checkpoint · source-first reverse engineering.** This is the **current entry point** for Sonicake Windows Manager `5868USB.dll` research, updating the stopping point described by the older [Stage23C review](NAM_CLO_HTKPA_INTERIM_REVIEW_2026-10-12.md), [source recovery](NAM_CLO_HTKPA_SOURCE_RECOVERY_2026-10-12.md) and [historical handoff](POCKET_MASTER_HTKPA_HANDOFF_2026-10-12.md). Historical stage reports and their dated conclusions remain intact; read them as snapshots, not current acceptance claims.

**Original DLL identity:** 2,902,016-byte Windows x64 PE `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, image base `0x180000000`. Research uses static PE bytes and `objdump`, with small source-derived Python simulations. **The Windows vendor DLL has NOT been executed or sampled in RAM** for the current FIR/FFT reconstructions.

**Scope:** NAM→CLO normal export for two original captures, Marshall JCM800 2203 and Marshall SC20. The existing production Void Mod and its hardware-positive baseline have not been changed by these research checkpoints. No proprietary DLL, NAM model, WAV capture, original CLO, firmware, raw signal or large disassembly should be committed; private assets remain in ignored `research/_LOCAL_FILES/`.

## 1. The short verdict

We have the normal export route, the format-sensitive PCM16 read and PCM24 intermediate path, the geometry and scalar candidate for the two-stage 44.1→48 kHz resampler, the first FIR's **source-derived 1417-tap length**, startup counters, cyclic coefficient layout, and *individual* source-emulated FFT butterfly families. This is substantially beyond Stage23C's architectural outline.

**Not achieved:** native RAM comparison, full ordered FFT parity, complete 2× FIR streaming/overlap, 24-tap fractional interpolation output, exact sample alignment, both real 23–28s fitter input/reference arrays, independently computed official four gains, or original Pre128/Post2048 FIR parity. A near-machine-precision synthetic DFT comparison is **not** vendor-runtime numerical equivalence.

Evidence vocabulary used below:
- **Source-pinned:** instruction addresses, branches, PE constants or object fields checked against the SHA-pinned DLL.
- **Source-derived candidate:** numerical model following inspected instructions, but Windows CRT/SSE rounding, stream state or native output bytes not yet independently verified.
- **Synthetic check:** mathematical agreement on generated data, not a captured vendor process.
- **OPEN / NOT_COMPUTED:** no end-to-end parity claim.

## 2. Canonical export chain and important corrections

`namConvertCloData` `0x1800E1F70` stores NAM and WAV job fields, selects mode 0, and routes via async worker `0x180060F20` to dynamic sample-rate export `0x180010E70`, NOT the previously hypothesized fixed-44.1k diagnostic branch. NAM parsing under `0x18000E0E0` yields 48,000 Hz for **both** original NAM models (Stage23D). The normal path reads original stereo PCM16 44,100-Hz DI, selects channel zero, resamples it under `0x18000CE00`, writes an intermediate **mono PCM24 WAV** and reads it back for fitter preparation. The saved stereo 48,000-Hz reference is read separately.

Stage23E establishes `PCM16 / 32768` exactly for the two 16-bit stereo capture WAVs (all 65,536 possible signed codes tested), reader `0x18008BB70`, decoder `0x180091110`, normalization `0x1801417F0`, and conditional reconstructed reference **3,360,000 f32 samples plus 600 zero samples**. Capture-specific reference-buffer hashes are in [Stage23E](NAM_CLO_HTKPA_DLL_RE_STAGE23E.md). PCM24 writer/reader quantization is a separate boundary, not a free float32 pass-through.

Stage22's strict call-order correction remains in force: reference-only detrend/onset, then 23–28s input/reference segments → four-gain fitter `0x1800BDBE0` at `0x1800BEDE4`; the separate IIR helper follows at `0x1800BEE25`. Do **not** pass a post-IIR signal into Stage21.

## 3. Checkpoint register: Stage23F–O

All file links below are repository-relative; scripts are research-only. The stage letters remain incremental **research checkpoints**, not completed product releases.

| Stage | Evidence and reconstructed portion | Reproducible source | Gate still open |
| --- | --- | --- | --- |
| **23F PCM24** | Source-derived float32 → clipped signed int32 → 24-bit little-endian → float32 path, with IEEE nearest-even synthetic comparisons; writer `0x1801408C0` and encoder `0x18008E0E0`. | [PCM24](../research/htkpa/stages/stage23f/pcm24_source.py), [tests](../research/htkpa/stages/stage23f/test_pcm24.py), [evidence](../research/htkpa/stages/stage23f/pcm24_evidence.json) | Bit parity with running Windows DLL and full exported DI |
| **23F phase table** | 681 raw phase kernels, 24 taps; eight-neighbor stencil to 674 output rows containing `A,B,C`; 673 working fractional bins. Kaiser/Bessel/`I₀` raw-kernel model uses inspected constants. | [stencil](../research/htkpa/stages/stage23f/phase_table_stencil.py), [kernel candidate](../research/htkpa/stages/stage23f/phase_kernel_candidate.py) | Native RAM table bits; edge conditions and CRT parity |
| **23G** | FIR up=2/down=1 constructor/reset, initial fill/discard fields and a source-derived zero fractional phase for the traced successful 44.1→48 branch. | [startup contract](../research/htkpa/stages/stage23g/fir_startup_contract.py), [phase trace](../research/htkpa/stages/stage23f/fir_initial_phase_source.py) | First emitted sample, group delay vs discard, streaming flush |
| **23H** | Empirical `0x18000B0E0` filter-length branch: raw half-length `708.9209756461122`, `G=floor(...)=708`, `L=1417`. | [FIR length](../research/htkpa/stages/stage23h/native_fir_length.py) | Running-DLL observation of selected filter/cache state |
| **23I** | Candidate symmetric 1417-tap FIR, 4096-`double` cyclic/FFT layout, normalization with candidate sum ~`1/1024`; `0x180014810`, `0x180008FD0`, `0x18000B9C0`. | [coefficient generator](../research/htkpa/stages/stage23i/native_fir_coefficients.py) | Native coefficient bytes/CRT recurrence, FFT and audio output |
| **23J** | Real-FFT plan/call, `N=4096`, `0x1800094F0`, `0x1800099F0`, `0x180009EF0`, distinct DC/Nyquist combination. Caller passes mode=1. | [FFT dispatch](../research/htkpa/stages/stage23j/fft_dispatch_source.py) | Full spectrum, transform sign conventions across all stages |
| **23K** | `0x18000A850` radix-4 unity butterfly plus final `0x18000A0A0` radix-2 pair, synthetic DFT checks. | [butterflies](../research/htkpa/stages/stage23k/fft_butterfly_source.py) | Higher-stage twiddle-index arithmetic |
| **23L** | Twiddle/permutation anchors: 10-bit reversed indices, e.g. `0,512,256`; `π/8,π/4,3π/8` coefficients; sign/multiplication order. | [twiddle trace](../research/htkpa/stages/stage23l/fft_twiddle_permutation_source.py) | Complete permutation and native CRT trig bits |
| **23M** | `0x18000A370` first 8-complex special block as two rotated DFT-4s; **83** scalar SSE ops source-interpreted and synthetic-tested. | [first base block](../research/htkpa/stages/stage23m/fft_base8_source.py) | Entire complex transform |
| **23N** | `0x18000A550–0x18000A801`: all **255 general 8-complex base blocks** source-interpreted, 144 scalar SSE operations/block, **3060** DFT-4 synthetic tests, sign-bit `xorps` accounted for. | [general blocks](../research/htkpa/stages/stage23n/fft_general_blocks_source.py), [evidence](../research/htkpa/stages/stage23n/evidence.json) | Integrating blocks and higher FFT stages; native RAM parity |
| **23O** | `0x18000A850` representative special branches for rotations `π/4,π/8,3π/8`; 46+66+66 scalar SSE operations, **3096** synthetic cases total. | [radix-4 special branches](../research/htkpa/stages/stage23o/fft_radix4_special_source.py) | General higher-stage twiddle loop; all actual strides and complete FFT |

**Concrete first-stage numbers, conditional on the traced normal parameters** `cutoff=0.5`, `quality=2.0`, `attenuation=180.15`:

| Quantity | Value |
| --- | ---: |
| FIR half-length `G` | 708 |
| Nonzero symmetric FIR taps `2G+1` | 1417 |
| Working FFT/cyclic scalar buffer | 4096 doubles |
| Initial work-buffer fill | 2680 |
| Initial discard/skip counter | 3388 |
| Fractional phase passed from the first FIR stage | 0.0 on this traced branch |

These are **static code-derived values**, not independently captured vendor output. In particular, `1/1024` is the candidate's **pre-FFT stored coefficient sum with library scaling**, not a claim that the user-visible filter has 1/1024 passband amplitude. Do not substitute these calculations for a measured end-to-end waveform.

## 4. Two-model official comparison gate — still NOT_COMPUTED

Original vendor CLOs are read-only **held-out** references, not optimizer targets or seed values:

| Model | Official `pmax` | `nmax` | `prate` | `nrate` | Independently recreated? |
| --- | ---: | ---: | ---: | ---: | --- |
| Marshall JCM800 2203 | 0.0586976074 | 0.0625180602 | 425.438965 | 356.188354 | **NO** |
| Marshall SC20 Full Rig | 0.0106169116 | 0.0126974732 | 450.926178 | 253.910919 | **NO** |

The generic SciPy polyphase resampler experiment in historical Stage23A was a **negative control**, not vendor resampling. Neither model has a source-derived complete 23–28s fitter pair, independently matching four gains, or bit-verified 128-/2048-tap output. Do not generate purported official CLO files from synthetic-only parity.

## 5. Reproduction after fresh clone (WSL/Linux)

The following verifies checkpoint code using **your separate, ignored original DLL**; it does not execute the DLL. Required: Python 3, `objdump`, NumPy for PCM24/phase tests, and the dependencies listed in Stage23E for capture-array checks. Use your existing `.venv/bin/python` where applicable.

```bash
git pull --ff-only origin main
DLL=research/_LOCAL_FILES/vendor/5868USB.dll
sha256sum "$DLL"  # expected: fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa
.venv/bin/python research/htkpa/source_integrity.py
.venv/bin/python -m unittest discover -s research/htkpa/stages/stage23f -p test_pcm24.py
.venv/bin/python research/htkpa/stages/stage23f/pcm24_source.py --dll "$DLL" --out research/_LOCAL_FILES/scratch/stage23f_pcm24.json
.venv/bin/python research/htkpa/stages/stage23f/phase_table_stencil.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23f/phase_kernel_candidate.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23g/fir_startup_contract.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23h/native_fir_length.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23i/native_fir_coefficients.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23j/fft_dispatch_source.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23k/fft_butterfly_source.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23l/fft_twiddle_permutation_source.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23m/fft_base8_source.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23n/fft_general_blocks_source.py --dll "$DLL"
.venv/bin/python research/htkpa/stages/stage23o/fft_radix4_special_source.py --dll "$DLL"
```

For full PCM16 capture/reader acceptance, use the original [Stage23E test commands](NAM_CLO_HTKPA_DLL_RE_STAGE23E.md). Do not interpret `source_integrity.py`'s historical 144-file archive manifest as coverage of newly authored Stage23F–O scripts; Stage23D additionally has its [own restoration manifest](NAM_CLO_HTKPA_STAGE23D_RESTORATION_2026-10-12.md). Numerical checks and old JSON are evidence of their stated scope, **not** automatic proof of full native execution parity.

## 6. NEXT: Stage23P — narrow source-first work, not another documentation cycle

1. **Disassemble `0x18000AB50–0x18000AF17` general higher radix-4 twiddle loop** for arbitrary twiddle indices, including pointer arithmetic, special paths, signed-zero handling, and the exact register state for each of the four `0x18000A850` calls (scalar strides **8, 32, 128, 512**).
2. Join Stage23M/N base blocks with Stage23K/O higher stages; test one **complete 4096-double FFT input** against a separately coded transform and identify the first failing index. A mathematical agreement is a new synthetic acceptance level; **native FFT RAM parity remains open**.
3. Source-recreate the real-FFT packing and FIR spectral multiplication, streaming overlap, block boundaries and startup discard. Then feed the 24-tap/673-phase fractional stage with the exact PCM24 round trip. Confirm channel selection and emitted-sample timing.
4. Only after those gates, reconstruct both pre-fit source/reference regions, apply reference-only detrend/onset and unchanged Stage21 fitter, and compare the four independent gains with held-out 2203 and SC20 values. Subsequent Pre128/Post2048 integration is a separate gate.

**Work method: RE-FIRST + CHECKPOINT.** Prioritize disassembly and numerical experiments; store one compact code/evidence commit after a verified discovery or research session. Preserve historic docs verbatim between deliberate DOC-SYNC passes like this one. The user's standing `#writegh` permits research/docs commits until explicitly revoked; it does not authorize production changes, hardware operations, force-pushes or publication of private captures.
