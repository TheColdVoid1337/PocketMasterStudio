# HTKPA Stage23E — PCM branch, loader buffers and resampler boundaries

> **Later checkpoint (2026-10-13):** [Current Stage23O status](NAM_CLO_HTKPA_RESEARCH_STATUS_2026-10-13.md) records the subsequent PCM24 source path, phase-table stencil, FIR `G=708` / 1417 taps, and incremental FFT reconstruction. In particular, Stage23G traces **zero fractional FIR-to-interpolator initial phase for the selected 44.1→48k branch**, superseding Stage23E's broader "not established as zero" uncertainty. This still does **not** prove exact first emitted sample, group delay, real DI array or native resampler parity. The historical Stage23E observations below remain intact.

2026-10-12. Static-only checkpoint on DLL SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. The DLL was never loaded or executed. Stage23E closes the ordinary PCM16 normalization branch under the successful WAV-reader path and reconstructs the saved reference WAV's **pre-detrend** context buffer. It does not reconstruct the native resampled DI, either final fitter pair, or official gains/FIRs.

## 1. Reader identity and format-dependent branch

The input/reference loaders obtain a reader through `0x1801423F0`. Format registration calls `0x1801434D0` at `0x180142509`; the WAV format constructor installs vtable `0x180249C10` at `0x180143512`. The factory dispatch at `0x18014247A/0x18014248E` uses slot `+0x50`, whose original PE pointer at `0x180249C60` is `0x180143310`. This factory calls the reader constructor **`0x18008BB70`** at `0x18014334A`. The DI conversion routine also calls this factory directly at `0x18000D5ED`.

The reader constructor clears `esi` at `0x18008BBE1` and writes `sil=0` to **reader+0x24** at `0x18008BBF1`. It installs reader vtable **`0x180249390`** at `0x18008BC56/5D`. It recognizes RIFF (`0x18008BD00`), WAVE (`0x18008BD46`) and fmt (`0x18008BE4D`); format tag is retained in `bx` at `0x18008BE68`. Channels, rate and bit depth go to `+0x20`, `+8` and `+0x10`; block size `(channels*bits)>>3` goes to `+0x80` at `0x18008BF04..12`.

For format tag 3, `0x18008BF18..22` sets `+0x24=1`. For ordinary PCM tag 1, the tag-3 and extensible-tag-0xFFFE cases are bypassed; `0x18008C17A/17E` accepts tag 1 and proceeds to the next chunk at `0x18008C442`, retaining **+0x24=0**. The data chunk sets its start at `+0x70` and derives frames at `+0x18` by dividing data bytes by frame bytes (`0x18008C1F1..20C`). The constructor also starts the alternate-reader flag `+0x85` at zero; the successful ordinary WAV factory branch is `0x18014335A/361 → 0x180143408`.

Fresh inspection of all four SHA-pinned capture files found exactly `JUNK` (52 bytes), `fmt ` (16 bytes) and `data`, starting at offsets 20, 80 and 104 respectively. Each fmt is **tag 1, two channels, 16 bits, block align 4**; DI is 44,100 Hz and reference 48,000 Hz. There is no extensible/float format ambiguity in these fixtures. Successful opening of these files through the identified WAV reader therefore reaches the integer normalization branch. This is a static branch proof conditional on file identity and successful I/O, not evidence that a particular historical process loaded these exact files.

## 2. Actual PCM16 words and float conversion

`0x180141680` is a generic read wrapper, not the PCM16 decoder itself. Its indirect call at `0x18014171C` uses reader vtable slot +0x20; the original PE pointer at **`0x1802493B0` is `0x18008D3E0`**.

That WAV reader processes at most `0x1680 / blockAlign` frames per read (`0x18008D4B7..C1`), i.e. 1440 stereo PCM16 frames. The 16-bit test at `0x18008D511/514` reaches **`0x180091110`** through `0x18008D58A`.

For separate source/destination memory, `0x1800911D0` reads an unsigned little-endian word, `0x1800911D7` shifts it left by 16, and `0x1800911E1` stores the resulting dword. The source stride is `2*sourceChannels`; the outer loop advances source channel by 2 bytes and destination pointer by 8 bytes (`0x1800911FB/1FF`). The dword is subsequently interpreted as **signed** by `cvtdq2ps`, preserving negative PCM16 values. This is deinterleaving, not averaging stereo.

After generic read at `0x18014228D`, `0x1801422B9/2BE` skips normalization only for a nonzero +0x24. Thus these ordinary PCM16 fixtures reach `0x1801417F0` at `0x1801422D1`. The helper's original f32 constant is exactly **2^-31**. Every signed PCM16 value shifted into the high 16 bits is exactly representable in binary32; multiplication by 2^-31 gives exact **PCM16 / 32768**. This conclusion covers the fixture PCM16 route, not arbitrary int32 audio under arbitrary rounding modes.

The new mathematical test covers **all 65,536 PCM16 codes**, signed extrema, separate nonidentical stereo channels and endian-sensitive words. Fresh full-array decoding of all four capture WAVs, both channels, matches independent `soundfile.read(dtype='float32')` with maximum error **0.0**. Both channels in each real fixture are identical. No amplitude correction was guessed.

## 3. What is now reproducible about the context buffers

The loader selects decoded channel zero (`0x1800BFC2C` input; `0x1800BF81C` reference). It clears `(70*Fs+600)*4` destination bytes before the copy (`0x1800BFC75`, `0x1800BF865`); `0x1800A504E` resolves to the PE **memset** import at `0x18018B6A8`. The copy loop transfers the first `70*Fs` sample words unchanged. Thus, at exact 48k, the pre-detrend reference has **3,360,000 samples + 600 positive-zero float32 samples**, total **3,360,600**. No resampler output has been substituted here.

SHA256s of reconstructed little-endian f32 reference buffers including the zero tail:

| Model | Pre-detrend context SHA256 |
| --- | --- |
| 2203 | `712d5b3cdea38067fbfa44b1e792a7e62bc0d48dc1b37ed8a19ad2d93aa4337d` |
| SC20 | `2481b54f5806694c1a16509abfbb5d0d1b2ff0d64e30bf93e8943f4d5eaf97a3` |

These are independently constructed buffers **conditional on loading the saved reference WAVs**. Neither a RAM dump nor exact native f32 detrend/onset has been obtained. Raw arrays and audio remain local; only metadata and hashes are published.

## 4. Resampler: counts, ring state, and an intermediate 24-bit WAV

The initial DI decode occurs at `0x18000D76D`, then `0x18000D786` calls `0x18000CE00`. Input f32 samples are promoted to f64 at `0x18000CFA0`. Output length uses **binary32 at each step**: `int(f32(f32(f32(N)*targetFs)/sourceFs))` at `0x18000D036..43`. It is 3,360,000 for the actual 70-second DI. It must not be replaced by rational floor: for N=3,086,014 the binary32 route gives 3,358,927 versus rational floor 3,358,926; for N=3,086,073 it gives 3,358,990 versus 3,358,991. Both examples are regression tests.

`0x18000D090..D1A8` shows further calls with zero-filled f64 input after the initial block, with output count clipping and f64→f32 stores. The interaction of returned counts, copy bounds and repeated calls has **not** been fully reproduced; it is not safe to equate the stage capacity with emitted samples or append one arbitrary zero tail.

Additional fractional-stage state is pinned:

| Field / source | Observed role |
| --- | --- |
| `+8`, mirror `+0x800` further | mirrored ring storage, 256 doubles per half; writes at `0x180013690..704` |
| `+0x1020`, `+0x1024` | available-sample count and write position; low-byte wrap at `0x18001372A` |
| `+0x1028` | read position, initialized to 245 (`0xF5`) |
| reset `0x180013D50..5D` | zeros 0x58 bytes beginning at object+0x7B0: ring positions 245..255, 11 doubles |
| `0x18001373E` | interpolation waits for available count >=13, consistent with 11 history +13 incoming =24 neighbors |
| `+0x1038`, `+0x1040` | current phase fraction and epoch base; reset copies initial `+0x1018` into both |
| `0x180013C49..CAD` | output counter × intermediateFs / targetFs + epoch base, truncate integer advance, retain fractional remainder; ring position wraps to 8 bits |
| `0x180013CE5..D0A` | after a process call, if output counter >1000, rebase phase and zero the two dwords at +0x102C/+0x1030 |

The initial phase at +0x1018 is supplied by the upstream stage; **it is not established as zero**. These pins do not reconstruct the runtime 673-phase coefficients or all 2× FIR delay behavior.

**New required boundary:** the normal wrapper sets channel count to 1 at `0x180010F22`, passes it at `0x180011013`, and places **0x18 (24)** as the fifth argument of `0x18000D4A0` at `0x18001100B`. D4A0 forwards this to the WAV writer at `0x18000D840..858`; `0x180142942` and `0x180142A14..24` carry it into writer constructor `0x18008DCA0`, which stores it as writer+0x14 at `0x18008DD09/0C`. The f32 resampler result is sent through `0x180142000 → 0x1801408C0` for writing. The returned file path is then used by the downstream fitter wrapper (Stage23D).

Therefore, reconstructing only the f32 output of CE00 is insufficient: the ordinary path requests a **mono, 24-bit intermediate WAV**. The writer's float→integer rounding/clipping, 24-bit packing and subsequent PCM24 decode must be traced and reproduced. Inspection of `0x1801409E0..A1B` already shows f32→f64 conversion, clipping branches and multiply/add/bit extraction, but Stage23E deliberately does not implement an unverified quantizer or write a WAV/CLO.

## 5. Reproduction and test outcomes

From repository root in WSL/Linux (Python + objdump + NumPy + SoundFile):

```sh
.venv/bin/python -m unittest discover -s research/htkpa/stages/stage23e -p 'test_stage23e.py' -v
.venv/bin/python research/htkpa/stages/stage23e/stage23e_audio_source.py --dll research/_LOCAL_FILES/vendor/5868USB.dll --private-root research/_LOCAL_FILES --out research/_LOCAL_FILES/scratch/stage23e/evidence.json
.venv/bin/python research/htkpa/source_integrity.py
.venv/bin/python research/htkpa/source_integrity.py --manifest research/htkpa/stage23d_archive_manifest.json
```

Final results: **110 selected instruction pins, 2 original vtable pointers, 4 PE constants, memset import, all four WAV identities and arithmetic comparisons; 9/9 unit tests**. Two independent evidence runs are byte-identical, SHA256 **`bbf45a1a1e0b6431fd06c5b17c90d379368b2ec9d19b9cba066e3c986a864679`**. Safe metadata evidence is committed beside the code. An initial test used an incorrect assumed rounding-boundary example (N=3,086,999); it failed, and was replaced by the two measured counterexamples above. Production and all archived source bytes remain unchanged.

## 6. Strict outcome and next minimal task

| Model | Native fitter pair | Four independently computed gains | Full FIR parity |
| --- | --- | --- | --- |
| 2203 | NOT_RECONSTRUCTED | NOT_COMPUTED | NOT_TESTED |
| SC20 | NOT_RECONSTRUCTED | NOT_COMPUTED | NOT_TESTED |

No Stage21 solver call is made by this stage: the required native DI and post-detrend reference pair is absent. Official CLO values were not used as numerical inputs. No generic SciPy resampling, coefficient tuning or speculative gain correction was attempted.

Next minimal source experiment: resolve writer vtable `0x1802496A8` slot +8 and `0x1801408C0` PE constants, prove exact float→PCM24→float rounding on synthetic edge values; do this before claiming a native DI buffer. Then reconstruct first-stage FIR delay, the inherited fractional phase, runtime table at `0x1800163FF..`, and CE00 streaming copy bounds. Independently reproduce target detrend at exact 48k with the proven zero tail and then onset/window selection. Only after these gates feed the unchanged Stage21 solver and compare both models to held-out CLOs.
