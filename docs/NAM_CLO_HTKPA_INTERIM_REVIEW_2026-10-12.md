# HTKPA / NAM→CLO — Interim engineering review after Stage 23C

**2026-10-12 · REVIEW checkpoint, not Stage 24.** Baseline: GitHub docs Stages 2–23C, the comprehensive Stage 1–22 handoff, native source-verifier files from Stages 21–23C, matching user capture ZIPs, and the SHA-pinned original x64 `5868USB.dll`. Stage 1's original GitHub filename is not assumed to follow the Stage2–23 naming convention. No vendor DLL execution, new CLO production, firmware changes, or pedal writes.

## Executive verdict

We have **most major HTKPA pipeline components identified** (export dispatch, native WAV loaders and resampler stages, four-gain saturator algebra, initial A/B spectral fitting, Pre128/Post2048 synthesis skeleton, optimizer loops, correction/finalization, coefficient conversion and VTSI packaging), but **do not have a complete and independently tested numerical implementation for real captured audio**. The main blocker is provenance/scale/sample alignment of the two native float32 buffers entering the 23–28-second four-gain fitter. No independent full official-parameter `(Pre128,gains4,Post2048)` output exists for either 2203 or SC20.

**Non-metric planning assessment**: about **65–75% of architectural understanding** and **25–40% of reproducible end-to-end numerical work**, subject to potentially substantial rework when component boundaries are integrated. These are *judgment calls*, not counts or engineering completion claims. Full two-model parity: **not attained**. Stage21 mathematical parity is only on ordinary/synthetic input domain; Stage23C has no numerical resampler output.

## DLL coverage: reproducible denominator and limitations

PE SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; full file **2,902,016 B**, PE `.text` virtual section **1,613,400 B**. The `.pdata` unwind table contains **5,575 valid function intervals**. This excludes some leaf methods/thunks and is not synonymous with a count of semantic program features.

A source AST audit of *only five available PIN-dictionary verifiers* (Stage21 75, Stage22 43, Stage23A 40, Stage23B 125, Stage23C 79) finds **335 distinct instruction-pin addresses** (362 listed pins before deduplication). Of those, 329 fall into `.pdata` intervals corresponding to **28 unique functions**, or **0.50% of the 5,575 unwind intervals**. The *full containing function spans* together total **37,203 B = 2.31% of `.text`**. Including extra addresses cited in the historical handoff gives **48 distinct function spans, 58,813 B = 3.65% of `.text`** (48/5575 = 0.86% of unwind intervals).

**These are not percentages of instruction coverage or percentage of the DLL already understood.** A pin represents one source claim within a function, not a full reconstruction of the function. The handoff does not contain every Stage1–20 primary pin. The measures include many unrelated functions in the denominator (USB, application plumbing, CRT) and do not convey progress toward fitting. They are a deliberately conservative reproducible *research footprint snapshot*. Audit script: `research/htkpa/coverage_audit.py`; machine-readable measurements: `research/htkpa/coverage_snapshot_2026-10-12.json`.

## Capability audit: established vs remaining

| Workstream | Best verified status | Critical open requirement |
| --- | --- | --- |
| Export job and wrapper selection | Source-proven mode 0 and virtual async dispatch to dynamic-Fs `0x180010E70` (23B) | Actual session metadata contents and selected `Fs` |
| Loader and WAV ingestion | Source-proven pointer fields `+0x243E0/+0x243E8`, rate-equality checks, decoded 32-bit copies (23A) | Original file-role provenance, channel handling, PCM→float normalization, WAV generation/export identity |
| Resampling | Stage23C proves FIR upsample 2:1 **followed by** 24-sample, 673-phase polynomial interpolation | Native FIR tap synthesis, runtime table initialization, phase/ring buffers, boundaries, streaming arithmetic |
| Saturator | Complete ordinary-domain algorithm on synthetic arrays: 0.1s extrema, permutation, half-max OLS, sequential 9+9 rate searches (21) | Genuine source-derived 23–28s paired arrays, float32 rounding/CRT `expf`, held-out real gains for two models |
| Pre-fit conditioning | Reference-only detrend, 600-sample onset, 23–28s, fitter **before** the separate IIR (22) | Exact native input/reference from upstream importer, session-dependent alignment |
| Audio-derived A/B | Conditioner, 50-tap banks, IIR constructor, spectral ratios and curve initializers partially reproduced (18–20) | Native real audio stream seed, state alignment and fully integrated FFT pipeline |
| 2→1→3 optimizer | Source-confirmed iterations 3/2/5, persistent caller arrays, rollback and regularized objective (8–17) | Integrated deterministic reproduction across ten iterations for real audio |
| FIR synthesis/finalizer | Minimum-phase algebra, 128/2048 lengths, 256-tap Post correction and energy match (11–15) | Exact float/stft/FFT/gaussian state and real per-tap agreement |
| Output serialization | 8840-byte VTSI fields, native gains copied without late transform, 48→44.1 FIR packing (4, 23A/B) | Full independently generated model; preserve 117/1881 active tap behavior and CRC |
| Auditory/device evidence | Independently auditioned 2203 Post-FIR v0.1, v0.2C positive control | No claim of end-to-end official HTKPA or mobile SONICLINK equivalence |

## Overlooked issues and methodological risks

1. **The two concrete export WAVs are not proven byte-identical to the native float32 paired arrays.** They are PCM16/stereo, DI 44.1k and target 48k, whereas the loader consumes decoded 32-bit data at selected native Fs. The actual audio decoder, sign, channel selection, scaling, target generation, padding and timing must be traced from the export filenames and parser to `context+0x243E0/+0x243E8`.
2. **The normal export path was misidentified in the first Stage23 diagnostic.** Stage23B source-proved mode 0 → dynamic Fs; naive 48→44.1 target resampling tested the wrong hypothesis. The huge rate error (e.g. 2203 `0.972` against held-out `425.439`) is evidence of an invalid assumed path, **not** evidence the Sonicake algorithm is unrecoverable. Do not optimize to the oracle.
3. **Determine `[rbx+0x18]` in rate selector `0x18000E0E0` before building expensive waveform experiments.** 48k is source-confirmed fallback, not proven per-session Fs. Source roles of export object `+0x208/+0x210` and `outputFile.wav` are equally important.
4. **Two distinct sample-rate conversion questions must not be conflated.** WAV import resampling in `0x18000CE00` is upstream of fitting; the later **48→44.1 kHz coefficient packing** is a different stage with different array lengths. The 673-phase table is runtime generated, not a static payload from DLL `.rdata`.
5. **A plausible `Kaiser/Bessel` formula and ten synthetic arithmetic checks are not native numerical parity.** Table generator at `0x180016080`, filter helpers under `0x18000B0E0`, window approximation, FFT scaling, f32/f64 cast points, streaming startup/tail state and 24-tap polynomial accumulator all remain unverified numerically.
6. **Independent NAM WaveNet vs manager WAV ≈0.31 amplitude scale** is a validated warning from prior analysis, not a universal gain correction: the two official models' ref maxima and saved CLO pmax do not support guessing one scalar. Native input/output scale must be established independently.
7. **Persistent buffers and precision matter after gains.** Stage17 corrected optimizer caller-owned aliases; Stage19 corrected STFT hop to half the window; Stage20 corrected five-coefficient biquad; Stage22 corrected fitter/IIR order. Consolidated code must encode these errata as regression tests, or old assumptions may quietly return.
8. **Current testing is fragmented.** Source address pins verify selected machine instructions; synthetic FFT, FIR and optimizer checks verify separate formulas; neither is a single reproducible real-audio calculation. Introduce a compact fixed-input fixture harness with provenance, exact sample counts/rates, float dtype/casts, deterministic hashes, and explicit acceptance levels before attempting a full optimizer.
9. **One 70-second DI and two NAMs are a narrow validation corpus.** Both cases must pass independently before calling the solver correct. A later third model/DI is useful against overfitting; current Windows Manager and mobile SONICLINK equivalence remains unproven.
10. **Be careful with logs and capture identity.** Manager has asynchronous conversion callbacks and reused WAV/CLO filenames. SHA-pinned captured files and model matching are necessary, but not sufficient to prove every intermediate buffer from a specific callback.

## Recommended research order (change from immediately solving the hardest polynomial table)

**Gate A — minimal source-backed input provenance:** From `namConvertCloData` and dynamic worker, map the two exported pathname fields to actual loaded signal roles; decode metadata `[rbx+0x18]` to native Fs; inspect PCM/channel-to-f32 scaling and target-generation path. Publish an explicit graph with source addresses. No assumed 44.1/48 Fs.

**Gate B — reproducible resampler:** Recreate runtime coefficient-table generator and 2× FIR + fractional 24-tap pipeline with native per-stage counts, phase/ring initialization, source-derived constants, tail handling and boundary rules. Independently test impulse, silence/DC, short and full-length signals. Do not substitute `scipy.signal.resample_poly` as a claimed equivalent.

**Gate C — four-gain milestone:** Reconstruct both native 23–28 s arrays and Stage22 reference-only detrend/onset, feed unchanged Stage21 solver, *then* compare `pmax,nmax,prate,nrate` with both held-out 2203 and SC20 CLOs. This is the first decisive real-data numerical milestone. If it fails, inspect input origin, sample scales, Fs, alignment and precision in that order, not manual gain tuning.

**Gate D — full FIR milestone:** Recreate audio-seeded A/B (Stages18–20), 2→1→3 optimizer, shared Pre/Post minimum phase and Stage15 final 256-tap correction. Compare all 128+4+2048 parameters on both models; report per-field errors and time-domain holdouts, with no device deployment until a separate user decision.

## Research tree policy

Keep **all canonical research documentation** (stage reports, review notes, instructions/errata) in `docs/`, unchanged in location. Root `research/` is for executable Python verification/reproduction tools and safe machine-readable fixtures or manifests only; no installer, DLL, captured WAV/NAM/CLO, full proprietary disassembly dumps, generated audio or user device state. Initial contents: `research/htkpa/coverage_audit.py`, `research/htkpa/coverage_snapshot_2026-10-12.json`, `research/.gitignore`. Historical Stage1–23C ZIPs remain reproducible external research packages; **their tools have not silently been transplanted or declared integrated into the repo**. Future sourced standalones can be added to `research/htkpa/` with imports/tests adjusted as needed, without changing production browser code.

**Result:** Interim review recorded; Stage23 stays OPEN. Next most efficient task is source proving Fs/file roles/decoder-scale before expanding FIR/polyphase numerical emulation. No change to hardware-tested 2203 v0.2C or working Void Mod.
