# HTKPA Stage 23D — NAM metadata selects native Fs; source/target WAV roles pinned

**2026-10-12 · Source-first checkpoint; Stage 23 remains OPEN.** This does **not** represent an independent Sonicake NAM→CLO converter or native numerical parity. `5868USB.dll` statically examined, SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. No DLL execution, production JS changes, hardware upload, firmware writes or new device CLO.

## 1. Previously unresolved: where does native sample rate really come from?

The earlier Stage23B report showed an exported dynamic-Fs branch and a parsed object `[rbx+0x18]`, but did not prove that this was **NAM model metadata**. This stage traced the missing argument producer and recognized direct messages in the original PE.

- In `namConvertCloData` (`0x1800E1F70`) the Windows x64 fourth argument `r9` (retained in `r15`) is copied as a path/string at global job object `+0x218` (`0x1800E2157..0x1800E219C`). The second and third arguments are saved at `+0x208`/`+0x210`; the first argument is the output CLO buffer reference at `+0x200`.
- Export worker `0x180060F20` reads the input/reference WAV strings from `+0x208` and `+0x210` (`0x180061329` and `0x180061305`), obtains the model string from the `+0x218` job member via `0x1800126E0`, and passes this descriptor as the third argument to `0x180010E70` (`0x180061302/0x18006137D`). This is still the source-confirmed ordinary `+0x27C=0` branch.
- `0x180010E70` forwards the model descriptor to `0x18000E0E0` at `0x180010F7F` and separately forwards the two WAV paths (`0x180010F72/0x180010F77`). The second function is the model-output generation / model sample-rate detection path, identified by **original PE log strings** `[NAM] ========== getNamOutput start ==========`, `[NAM] namFile: `, `[NAM] outputFile: ` and `[NAM] model sampleRate: ` at `0x1802446D8`, `0x180244708`, `0x180244730`, `0x180244800`.
- `0x18000E65D` converts the model path to a wide string, `0x18000E698` invokes the upstream metadata reader, and at `0x18000E855` native code obtains **double model sampleRate** from parsed `[rbx+0x18]`, narrows to f32 (`0x18000E85B`). The result is logged with that exact `[NAM] model sampleRate: ` string at `0x18000E8A2`. If non-positive, the native fallback is `48000.0f` (PE `0x18024CDF4` at code `0x18000E9EA`). Native chosen Fs returns via `cvttss2si ebx,xmm9` at `0x18000F620`.

**New real-model observation**: both independent original user models have **root** `sample_rate=48000` and **both nested submodel** `sample_rate` values also `48000`. Their original hashes are pinned as 2203 `29abbdbf982ee64b963d1d8de06848d1b06450a623bb08ba3ffefce146dfac42` and SC20 `509ad3d6dc31cf0539afe4a264ff7386d6282ffe9d1e0de4b6cce514b1915b11`. Values were read from those user-provided NAM JSON sources, not inferred from WAV Fs or CLO parameters. The standalone verifier optionally checks original NAM SHA and metadata when run with local file paths.

**Therefore, under the source-confirmed usual successful export path, the nominal native Fs for both models is 48,000 Hz.** This inference depends on reaching the successful sample-rate return and model loader; it is stronger than treating 48k as merely a fallback or copying WAV header frequency, but it is not a recorded RAM dump of a specific Windows execution.

## 2. Exact source/target files and resample direction

The actual two saved capture pairs contain a 70s stereo PCM16 input at **44,100** Hz (`nam_input_wav.wav`) and a 70s stereo PCM16 generated output at **48,000** Hz (`outputFile.wav`). The DI WAV files for both models are byte-identical, SHA256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`.

`0x180010E70` receives the **DI input WAV** as its first file argument (`r15=rcx`), the reference **output WAV** as its second (`r12=rdx`), and the model descriptor as its third (`r13=r8`). It converts the first file with `0x18000D4A0` (`0x180011019..0x180011021`) to the selected model rate, then passes the newly converted first WAV and unchanged reference WAV to `0x180010230` (`0x1800110AD`). The native context is configured with `xmm6` at `0x180010453/0x18001045D`. Loader `0x1800BF9F0` populates first audio buffer `context+0x243E0`; `0x1800BF5E0` populates reference buffer `context+0x243E8`.

The native audio reader at `0x1801421C0` chooses the first audio-channel pointer (`0x180142201/0x180142223`); the final input copy loop at `0x1800BFCA7/0x1800BFCAB` transfers 32-bit sample words without multiplication **at that specific final copy loop**. Actual PCM16→decoded-float normalization inside `0x180141680`, and full `0x18000D4A0` resampling coefficients/boundaries, are **not yet recovered**. Matching original capture WAV channels happen to be identical; for these two fixtures a first-channel selection does not create disagreement between left/right. No general channel-mixing policy is claimed for nonidentical-channel WAV.

**Correct source direction: DI 44100→48000, reference remains 48000.** Stage23A's hypothesis of reference 48000→44100 with native Fs44100 was a wrong-path diagnostic and remains rejected, not corrected by retuning.

## 3. Honest negative control at the now-established sample rate

Read-only independent calculation: generic `scipy.signal.resample_poly` on **DI input** (160/147), original reference at 48k, approximate **non-native float64 detrend**, Stage22-style 600-sample reference onset scan, and the **unchanged Stage21** four-gain fitter on **23–28 s, 240,000 samples**. This is **NOT the original Sonicake resampler** and **NOT f32-exact native mean/detrend**. Official CLO gains are loaded **only after** candidate fitting for held-out reporting.

| model | diagnostic onset | independent NON-NATIVE candidate pmax | nmax | prate | nrate | official held-out pmax | nmax | prate | nrate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JCM800 2203 | 0 | 0.15571578 | 0.15541093 | 0.97062504 | 0.79495490 | 0.05869761 | 0.06251806 | 425.438965 | 356.188354 |
| SC20 | 19 | 0.07492959 | 0.06844199 | 0.63143349 | 0.69999969 | 0.01061691 | 0.01269747 | 450.926178 | 253.910919 |

**Disagreement remains enormous.** This negative control does NOT establish why, precisely; viable missing differences include audio decoder normalization, native 2× FIR + 24-sample polynomial resampler, target capture identity/processing, or other native buffer transformations. It forbids treating resampling direction alone as the solution. No oracle-gain optimization was performed and no generated CLO is supplied.

## 4. Verified reproducibility

`stage23d_source_provenance.py` performs **42 exact address/operand pins**, five real PE logging-string byte comparisons and one 48000.0f original PE constant comparison, plus capture WAV metadata when provided. Two runs against same SHA DLL gave identical SHA256 for `evidence.json`: `02ffe50f98ba53ade3b5ef4895f317c767ea288896f0920098d3f2dd1ec09ba5`. A separate five-test pure metadata suite passes; original Stage21 (75/8/77) and Stage22 (43/7/53) source-verifiers were independently rerun and passed. `stage23d_rate_diagnostic.py` requires SciPy/NumPy/SoundFile and archived `research/htkpa/stages/stage21/` as sibling of Stage23D in the cloned repository. It explicitly labels all output **NON_NATIVE_PARITY_NEGATIVE_CONTROL**.

All source code and safe JSON evidence are to be committed in `research/htkpa/stages/stage23d/`, with this primary report in `docs/NAM_CLO_HTKPA_DLL_RE_STAGE23D.md`. The ZIP package may include a README and report for reproducibility; the GitHub documentation remains under `docs/` as requested. No original Sonicake DLL, NAM/WAV/CLO captures or vendor audio is committed.

## 5. Next strict research gate

1. Trace `0x180141680` PCM16/WAV→decoded float conversion and `0x18000D4A0` source sample scaling and delay; distinguish saved 48k target file from any in-memory NAM inference response. Verify sample pairs at offsets 23–28 and onset using source-derived instructions, **not** a guessed 0.4×/0.001× scale.
2. Numerically reimplement native 2× FIR kernel + 673-phase/24-neighbor polynomial interpolation and boundary rules (`0x18000B0E0/0x180011B60/0x1800135C0`). The original table is generated at runtime, not a static PE array.
3. Only with native-equivalent paired buffers compute four Stage21 gains for both models; compare to official CLO strictly held-out. Then start audio-seeded A/B, Pre/Post and finalizer numerical reconstruction. No changes to production Void Mod or physical pedal.

**Gate: source Fs and file roles PROVEN; real native four gains NOT_COMPUTED; full Stage23 remains OPEN.**

## 6. Follow-up: conditional PCM decoder scale (`0x1801417F0`)

A further static read-only trace pins ten instructions in the decoder path.
`0x180141804` loads the PE float32 constant at `0x18024C4C4`, equal to
`4.656612873077393e-10` or `2**-31`. The SIMD/scalar loops use
`cvtdq2ps` followed by `mulps`/`mulss` to normalize signed int32 audio data.
The caller checks `[r14+0x24]` at `0x1801422B9` before a *conditional*
call at `0x1801422D1`; actual branch reachability for these specific WAVs
is not established by static disassembly alone.

With all four original PCM16 WAVs, `float32(int32(int16) << 16) * 2**-31`
exactly equals normalized PCM16 as f32 for every checked sample; maximum
sample difference is zero. This validates that exact arithmetic route but
**does not prove native buffer parity**, resampler output, target preprocessing,
or official four sat gains. Source implementation:
`stage23d_pcm_decoder_branch.py`.
