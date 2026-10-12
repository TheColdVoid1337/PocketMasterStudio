# POCKET_MASTER / PocketMasterStudio / HTKPA — CANONICAL HANDOFF

> **12 October 2026, Asia/Bangkok** · Русскоязычный handoff для непосредственной вставки в новый ChatGPT-чат.  
> **Repository:** https://github.com/TheColdVoid1337/PocketMasterStudio (branch **main**).  
> **Most recently verified scientific stage:** **Stage 22**. **Next: Stage 23.**  
> **Last pre-handoff GitHub HEAD:** \`f8c037776588666312e22ba1ef6c1004adda5dff\` (Stage 22). This hash is a **historical baseline**; publishing this handoff creates a newer HEAD.  
> **Primary research goal:** reverse-engineer Windows Sonicake Manager \`5868USB.dll\` **NAM → CLO** / HTKPA offline conversion and reproduce vendor Pre/Post FIR from independently obtained NAM/probe WAV, without relying on sonic estimates or proprietary coefficients as fit targets.  
> **THIS FILE IS SELF-CONTAINED AS CONTEXT:** it includes current instructions, precise architecture, tests, pitfalls, next actions and the verbatim repository reports for Stages 2–22 as appendices. Stage 1 was documented in the user-side research ZIP but does not have a matching \`docs/NAM_CLO_HTKPA_DLL_RE_STAGE1.md\` in GitHub.

## 0. ABSOLUTELY READ FIRST — actual stopping point

The visible previous chat appears to stop during Stage 21, but **Stage 21 and Stage 22 are already completed research deliverables** in both the local research artifacts and the GitHub repository.

**Stage 21:** source-first, algebraically complete *ordinary-domain* four-parameter saturator fitting routine \`0x1800BDBE0\`, including 0.1-second extrema, non-sorting mirrored/sign-adjusted expansion, initialization via slope regression, two sequential nine-candidate exponent-rate searches, final \`pmax/nmax/prate/nrate\`; 75 pinned instructions / 8 constants / 77 mathematical assertions, synthetic data only. **Official Marshall parameters from real capture: NOT_COMPUTED.**

**Stage 22:** corrects a major assumption. At \`0x1800BEDE4\`, the saturator fitter is called on the **23–28-second** pair from \`context+0x243E0\` (input) and \`+0x243E8\` (reference, shifted for onset alignment). The later \`0x1800BD490\` (50-tap/IIR) preprocessing is invoked **after** saturation fitting, on different pointers. Do **not** preprocess those sat-fit inputs through that IIR before fitting. The reference buffer first has its mean and a best-fit affine time trend removed; onset is found by scanning from 6s for 600 samples at threshold \`abs(y)>0.01\`. Two user-captured WAVs (same 44.1k DI, different 48k outputs) exist, but **exact native import/resampling into those context buffers remains unverified**. Stage 22 passed 43 instruction pins / 7 constants / 53 synthetic assertions. **Genuine four fitted Marshall gains still NOT_COMPUTED; FIR parity still NOT_TESTED.**

### Stage 23 is the next required investigation

Trace how exported \`namConvertCloData\` / \`appNamConvertCloData\` and their downstream loaders populate **\`context+0x243E0\` and \`context+0x243E8\`**: actual sample rate \`Fs\`, WAV import channel handling, input 44.1→working Fs resampling (if any), PCM16 scaling, reference 48k levels, output buffer padding \`70*Fs+600\`, device-independent numerical alignment and exact sample order. Do not assume \`Fs=44100\` or \`48000\` without tracing which native branch is active. Then perform native-equation reference detrending and onset detection, extract the **23–28s exact pair**, run the already written Stage-21 fitter independently for both Marshall captures, and **only then** compare four independently calculated floats against official CLO as a held-out check. Avoid guessing conversion factors, FIR coefficients, hardcoded gain corrections, or replacing DLL math with arbitrary Welch estimators.

## 1. Contract for assistant in new chat

- **Always speak Russian** to the user; technical reports and source comments may use English.
- User explicitly requires: **"не будем в гадания уходить ... находить инфу в DLL перед тем как начинать гадать"**. The sequence is **static instruction evidence → correct Win64 buffer aliasing → mathematical formula → clean-room independent code → synthetic tests → independent real-WAV measurement → optional held-out vendor comparison**.
- **Continue the project**; do not ask for facts already stated in this document. On user's "поехали", do not summarize all research again: directly attack Stage 23 and produce tested source/code/report/ZIP and a GitHub documentation commit, if legitimately achieved.
- User wants independent manual research; **do not suggest Codex** unless explicitly requested.
- User authorized **GitHub writes on \`TheColdVoid1337/PocketMasterStudio\` main** until \`#nowritegh\`. Research docs in \`docs/\` okay. No force push. Include authentic commit SHA and \`git pull --ff-only origin main\`.
- **Do not silently modify browser JS, live device firmware, User Profile slots or export new unvalidated hardware CLO**. The existing user-auditioned candidate JCM800 2203 \`v0.2 C\` must remain intact. Writing an actual pedal slot requires explicit consent.
- DLL analysis is **static**, e.g. \`objdump -d -M intel ...\` and PE binary inspection; do not execute/load proprietary DLL. Never redistribute the DLL or raw captured private WAV/NAM or official CLO in public GitHub.
- Distinguish **(A)** pinned disassembly facts from **(B)** independent mathematics, **(C)** numerical parity on actual WAV, **(D)** user's physical guitar/pedal listening, **(E)** production integration. Stage 22 is A/B; C vendor equivalence is NOT achieved for reconstructed FIR, and D is only documented for earlier subjective candidates.
- Do not assert Windows Manager == mobile SONICLINK. Do not present coefficient-vector cosine or magnitude-curve similarity as audio waveform equality.

## 2. Project and production baseline

**PocketMasterStudio** is a local browser-oriented studio/editor/library for the physical Sonicake Pocket Master pedal. User works with Windows/WSL, historically \`/mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod\` and local \`START.bat\` serving \`http://127.0.0.1:8765/PocketMasterStudio.html\`. Includes the modified PocketEdit UI, .prst Lab, preset library, logs, NAM/Clone and USB/BLE MIDI upload. Device upload has separate transport/ACK complexities and MUST NOT be conflated with the DSP converter.

Main source \`TheColdVoid1337/PocketMasterStudio\`. Reference independent open-source SonicMaster by \`Skyggedans/SonicMaster\`. Historically stable production JS from commit \`083a4e662c480ac73c56639065161123e2bcb75a\` uses the SonicMaster-style WaveNet/DSP fit (around ~2 min with five inference passes, compared with Manager ~14 s). All subsequent HTKPA research Stages 1–22 was docs/prototype work, **not integrated into production JS**. GitHub may have later separate commits: always fetch \`main\` when continuing rather than assuming old code hash is latest.

Physical user observations: original Void Marshall 2203 is somewhat quieter and tonally different; clean-room Post-FIR refit **v0.1** sounds substantially closer to SONICLINK; variants **v0.2 A/B/C** boosted output about +2.5 dB with high-shelf choices 0, +1.25, +2.25 dB; user provisionally prefers **v0.2 C**. This is D-level subjective evidence, not mathematically recovered proprietary HTKPA. Stage 6 minimum-phase-only candidate is **not physically validated** and should not supersede C. Do not accidentally compare different NAMs.

Waveform-validation Stage 7 disjoint-segment correlations (same reference DI, not independent playing): 2203 original Void 0.74867, custom v0.1 0.89487, v0.2C 0.88947, stage6 candidate 0.81740, source-independent spectral-only fit 0.82262. SC20 Void 0.65815, prior custom refit 0.76620, stage7 spectral-only fit 0.52652 **regression**. Stage7 WaveNet-derived fitted Post vs vendor-WAV-derived fit coefficient cosine 0.999999888 for 2203 and 0.999961099 for SC20: this is **agreement of two versions of our spectral method**, not official filter parity.

## 3. Primary artifacts, SHA-256, pairing, local research paths

The commercial 64-bit PE DLL in user installer:
\`/mnt/data/sonicake_manager_analysis/Sonicake Manager/assets/5868USB.dll\`
SHA256 \`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa\`, PE base \`0x180000000\`.

Input captures:
- \`/mnt/data/jcm2203_comparison/wavs/nam_input_wav.wav\`, \`outputFile.wav\`, and **official 2203 CLO** \`/mnt/data/jcm2203_comparison/clo/cloFile.clo\`; reference CLO SHA256 \`50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7\`.
- \`/mnt/data/sonicake_manager_session/nam_input_wav.wav\`, \`outputFile.wav\`, and **official SC20 CLO** \`/mnt/data/cloFile.clo\` or session-local \`cloFile.clo\`; SC20 reference CLO SHA256 \`2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a\`.
- \`/mnt/data/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam\` SHA256 \`29abbdbf982ee64b963d1d8de06848d1b06450a623bb08ba3ffefce146dfac42\`; separately \`/mnt/data/Marshall JCM 800 SC20 Full Rig.nam\`.
- Both Manager \`nam_input_wav.wav\` files are **byte-identical** SHA256 \`9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a\`, 70 seconds 44.1 kHz stereo PCM16, duplicate channels. Output WAVs: 70 seconds, 48 kHz stereo PCM16, duplicate channels. A WaveNet independent inference matches shape of Manager \`outputFile.wav\` extremely well but amplitudes differ by roughly 0.31 vendor/reference scaling; scaling not yet source-proven in loader.
- Existing per-stage local research: \`/mnt/data/HTKPA_DLL_RE_v0_1/\` … \`/mnt/data/HTKPA_DLL_RE_v0_22/\` and \`/mnt/data/Sonicake_HTKPA_DLL_RE_StageNN_v0_NN.zip\` (Stage 7 special name). **Sandbox paths are not portable across new chats**: the next chat should inspect Project/Library attachments, git/connector documents, or reattach the user's handoff ZIP and original vendor captures. NEVER invent availability of a path in a new runtime. Research ZIP deliberately omits the DLL and private media.
- Stage 21 independent fitter: \`/mnt/data/HTKPA_DLL_RE_v0_21/stage21_saturator_source.py\`, evidence + \`RESEARCH_REPORT.md\` and \`Sonicake_HTKPA_DLL_RE_Stage21_v0_21.zip\`.
- Stage 22 loader/detrend tracer: \`/mnt/data/HTKPA_DLL_RE_v0_22/stage22_pre_fit_trace.py\` plus Stage21 fitter copy, evidence and \`Sonicake_HTKPA_DLL_RE_Stage22_v0_22.zip\`.
- Older October 10 Studio/UX handoff lives in the user portable ZIP's **MAX** Markdown appendix; treat as historical (the HTKPA research here is newer).

\`\`\`bash
sha256sum "/mnt/data/sonicake_manager_analysis/Sonicake Manager/assets/5868USB.dll"
objdump -d -M intel --no-show-raw-insn --start-address=0x1800BDBE0 --stop-address=0x1800BE6F6 "/mnt/data/sonicake_manager_analysis/Sonicake Manager/assets/5868USB.dll"
python /mnt/data/HTKPA_DLL_RE_v0_21/stage21_saturator_source.py --help
python /mnt/data/HTKPA_DLL_RE_v0_22/stage22_pre_fit_trace.py --help
\`\`\`
These are **example inspection commands**, not guaranteed invocation contracts; check \`--help\`/source before using the research scripts.

## 4. Format and exact converter acceptance criteria

\`.clo\` is an 8840-byte \`VTSI\` container. CRC16-Modbus big-endian at byte offset **8**, covering byte **12 onward**. Four nonlinear float32 parameters at offset **104**; Pre-FIR **128 float32** at **136**; Post-FIR **2048 float32** at **648**. Several headers and additional material require care; the physical pedal is known to use only the first **512 Post-FIR taps** in upload mapping; do not assume every container field is transmitted unchanged. Typical official/old Void filter support after native 48→44.1-kHz resampling: **117 Pre nonzero + 11 zeros**, **1881 Post nonzero + 167 zeros**. This implies a native working-rate fit plus resampling/serialization; remains subject to exact-endpoint reconstruction.

Acceptance gate is explicitly strict:
1. Derive all math and buffer identities from native DLL, not target coefficients.
2. Build native-like audio preprocessing and generate initial 512-/~2401-point A/B curves from NAM DI + reference WAV, without reading official CLO gains/FIR as fit input.
3. Execute full optimization selectors **2,1,3** with correct state and iterations **3,2,5**, final correction, 48→44.1 rate conversion.
4. Independently emit a candidate and compare both official Marshall CLOs for CRC, parameter floats, 128 Pre and 2048 Post via max abs/relative L2/cosine and **exact float32 element matches** (after official retained as **held-out oracle**).
5. Validate audio on disjoint input windows, then optional user-controlled spare-slot physical audition before even discussing production integration. No hardware changes without user approval.
6. Never use a high coefficient-vector cosine as proof of acoustic or numeric equivalence.

## 5. Condensed and CORRECTED Stage 1–22 research history

| Stage | Source-proven outcome / caution |
|---|---|
| 1 | DLL inventory; exports \`namConvertCloData\` VA \`0x1800E1F70\`, \`appNamConvertCloData\` \`0x1800ABEB0\`; core \`0x1800BE830\`, iterative \`0x1800BB210\`, final \`0x1800B9B70\`. |
| 2 | Asymmetric exponential transfer: positive \`Pmax*(1-exp(-Prate*x))\`, negative \`Nmax*(exp(Nrate*x)-1)\`. |
| 3 | Optimizer: bounded power factor 0.2–5, anneal 0.9, basic rollback; Hamming support. |
| 4 | Context \`+0x24408\` Pre128 and \`+0x24410\` Post2048, 48→44.1 support and VTSI layout. |
| 5 | Gaussian smoothing \`0x1800B7E10\`, window ~0.1Fs in **one** specific stage; not blanket final-spectrum smoothing. |
| 6 | Vendor Post-FIR nearly own-minimum-phase (cosine 0.99856 2203, 0.999589 SC20); original Void Post strongly different; phase-projection alone not proven better sound. |
| 7 | NAM-only spectral Post fit cross-check; 2203 some improvement, SC20 big regression; **do not deploy**. |
| 8 | 3 fit selectors \`2→1→3\` with windows 23–28s(5s,3 iter), 6–21s(15s,2 iter), 30–50s(20s,5 iter), final 50–70s. Joint Pre/Post rollback, >1.2× score threshold. |
| 9 | \`0x1800B5D00\` piecewise-linear interpolation of spectral curve to 512 Mel-spaced 80–10000Hz queries; mean abs log loss. |
| 10 | \`0x1800B82B0\` cross-spectrum over generated and reference signals: \`|Σ A conj(B)|/(Σ|A|² + 2^-23)\`. **ERRATUM:** STFT hop is half **WINDOW SAMPLES**, not half a second. |
| 11 | \`0x1800B68F0\` outputs Pre128 with mirror 2N−2, spectral synth, DC mean subtraction and full-norm energy scaling. **Corrected Win64 stack pointer mapping**. |
| 12 | \`0x1800B72E0\` relative \`−100 dB\` floor (1e−5 maximum), log, complex exponent; \`0x1800B47F0\` inverse transform convention. |
| 13 | Full algebraic triplet \`B4A50→B6E30→B4F60\`: positive-phase normalized transform, parity-aware conjugate folding, negative-phase unnormalized transform; 111 synthetic tests. |
| 14 | Same \`0x1800B68F0\` writes **both Pre and Post** with different lengths. \`0x1800B7670\` Mel/dB/Gaussian conditioning. |
| 15 | Feedback spectral ratio \`1e6*A/(1e6*B+2^-23)\`; final \`0x1800B9B70\` calls \`0x1800B65A0\` to create 256-tap corrector, convolution/truncation/DC removal and final energy scaling. |
| 16 | Scratch SSA: contiguous 10×L temp curves, saved FIR states, rendered audio and scores. **ERRATUM Stage17:** \`0x1800BB575/6E1\` modify outer persistent arrays, NOT local \`V2\`. |
| 17 | Correct aliases: outer B *= V0; outer A /= V0; extra \`0x1800B6220\` sequential geometric low-index smoothing; Stage16 doc has explicit erratum. |
| 18 | Source-derived ordinary-domain \`0x1800B7670\` implementation; audio-seeded initial A/B with dual Gaussians and parabolic soft floor, still needs upstream audio preprocessing. |
| 19 | Hardcoded 50-tap FIR banks for 44.1/48/96kHz from PE; real DI independent FIR checkpoint. **ERRATUM:** STFT step 50% window, not 0.5s; Stage20 corrected coefficient count. |
| 20 | IIR coefficient constructor SSE interpreter: exactly **5 doubles per SOS** \`b0,b1,b2,a1,a2\`; identity alternative and ~40/~20Hz digital HP; both not always active. |
| 21 | Full *synthetic* four-parameter saturator optimizer; 75 pins / 8 constants / 77 assertions; actual WAV gains NOT_COMPUTED. |
| 22 | **MAJOR ORDER FIX:** saturation fit window **23–28s before IIR**; reference detrend, 600-sample onset scan, source buffer paths \`+0x243E0/+0x243E8\`; native import format still unresolved. |

## 6. Source-proven key mathematics and buffers (working summary)

- Core driver \`0x1800BE830\`: input/out references, threshold align, sat-rate prefit, later frontend audio preprocessing, then 3 iterative passes + final Post correction.
- Independent sat transfer: \`f(x)=Pmax*(1-exp(-Prate*x))\` if x≥0; \`Nmax*(exp(Nrate*x)-1)\` otherwise. Four context values at \`+0x243F8,+0x243FC,+0x24400,+0x24404\`.
- Stage21 fit: B blocks with \`floor(0.1*Fs)\` samples; \`X\` input block abs max, \`P\` output max, \`N\` output min; symmetric-mirror expand \`X'=[-X_{B-1},..,-X_0,X_0,..X_{B-1}]\`, \`Y'=[N_{B-1},..,N_0,P_0,..P_{B-1}]\`; derive initial rates via least-squares-half-height; sequential positive then negative exponent 9-candidate multipliers \`0.80,0.85,..,1.20\`, SSE float32 sum-of-square errors and native tie behavior. Consult full Stage21 report below before coding.
- Stage22 actual fit args at \`0x1800BEDD8..0x1800BEDE4\`: \`r9d=trunc(5*Fs)\`, \`rdx\` input \`context+0x243E0\` start at 23s, \`r8\` reference \`context+0x243E8\` start + onset shift. Reference has mean and linear-trend removed. Buffer allocation \`4*(70*Fs+600)\`. This order is **more authoritative than older Stage19 inference**.
- IIR native equations with five doubles \`b0,b1,b2,a1,a2\`: \`w[n]=1000*float64(x_f32[n])−a1*w[n-1]−a2*w[n-2]\`; \`m[n]=float32(b0*w[n]+b1*w[n-1]+b2*w[n-2])\`; \`y[n]=float32(0.001*float64(m[n]))\`. Stage20 isolated math verified but not precondition for sat-fit (Stage22).
- Conditioner \`0x1800B7670\` acts on linear Hz / positive magnitude, performs \`20log10\`, first Gaussian width \`trunc(.002*N)\`, Mel-Hz lin-interp, second width \`2*trunc(N/M)\`, remap to linear Hz, \`10^(dB/20)\`. Separate Stage18 init Gaussians widths \`trunc(.001N)\` and \`trunc(.005N)\`.
- Initial A/B quadratic soft floor \`T=.001*max(U)\`: \`B'=T+B^2/(4T)\` if \`B<2T\`, else \`B'=B\`; \`A=1e6*U/(1e6*B'+2^-23)\`.
- \`0x1800B82B0\` normalized cross-spectrum, Hamming window, **hop=floor(window_samples/2)**; score \`E=mean_512(abs(logf(R(mel)+2^-23)))\`; rollback >1.2 × old score; halved step. Spectral ratio corrections \`V2=1e6*V5/(1e6*V2+2^-23)\` but *earlier* outer persistent aliases are not \`V2\`.
- \`0x1800B6220\`: first \`K=trunc(sqrt(120L/Fs))\` low-index entries, geometric-like in-place propagation using nested \`sqrtf\`; edge cases remain native-specific.
- FIR synth shared \`0x1800B68F0\`; phase pipeline \`ifft(logmag) → fold-causal cepstrum (parity-specific) → fft → complex exp → inverse → mean removal / energy normalization\`, mirror one-sided semantics matter; do **not** substitute generic \`minimum_phase\` for native parity.
- Final \`0x1800B9B70\`: extra 256-tap correction FIR, causal convolution with current post and truncation to 2048, DC subtraction and output-energy ratio; 48→44.1kHz serialization left to verify.

## 7. Hard source corrections / do NOT repeat these past mistakes

1. Saturation fitting **before** 50-tap/IIR \`0x1800BD490\` (Stage22 corrects Stage19/20 implicit assumption).
2. \`0x1800B82B0\` STFT analysis hop **50% window**, not 0.5 seconds (Stage19 correction to Stage10).
3. \`0x1800BB575/0x1800BB6E1\` modify persistent outer A/B, **not** V2 (Stage17 correction to Stage16).
4. \`0x1800B68F0\` shared Pre/Post writer; Stage11 stack mapping must include return address.
5. IIR has **5** double coefficients per section, not 6. Two of the four coefficient banks are identity; Hz **digital** cutoff ~40 and ~20, not analog parameters 20/10 as final digital cutoffs.
6. Results \`0.999999888\` / \`0.999961\` are reproducibility of OUR two fitted candidate estimates, **not** coefficient match with Windows. Stage6 near-minimum-phase cosine does not imply better pedal sound.
7. Window Manager \`outputFile.wav\` vs independent NAM inference amplitude ~0.31 is a measured relationship, NOT an automatically transferable arbitrary gain knob.
8. Vendor CLO is **held-out oracle only**, not numerical fitting target. Never claim exact FIR parity before producing independently derived candidates and running comparison.
9. 50-tap native frontend filter arrays are not identical with exported 128-tap Pre-FIR.
10. Browser JS converter not changed by the research unless GitHub HEAD separately proves otherwise.

## 8. Exact Stage 23 execution checklist

**PRE-FLIGHT**
1. Query main HEAD and latest \`docs/NAM_CLO_HTKPA_DLL_RE_STAGE22.md\`. Validate pinned DLL SHA locally, or inspect user-uploaded installer archive if the current environment does not mount the prior path. Inspect Stage21 \`stage21_saturator_source.py\` and Stage22 \`stage22_pre_fit_trace.py\`. Never claim locally stored files exist without checking.
2. Verify two WAV sessions, sample rates, sample counts, channels and pairing SHA. Do not swap official SC20 and 2203 \`cloFile.clo\`.
3. Ensure output folders contain research only; do not modify production \`src/void_nam*\` or upload logic.

**SOURCE-FIRST TRACE**
4. Exports: \`namConvertCloData\` \`0x1800E1F70\`, \`appNamConvertCloData\` \`0x1800ABEB0\`. Trace path down to \`0x1800B5640\`, the native loader helpers \`0x1800BF890\` / \`0x1800BFCA0\`, and each write to \`context+0x243E0/+0x243E8\`.
5. Determine exactly \`Fs\`, mono/stereo channel handling, 44.1k DI / 48k vendor out resampling, reference output scaling, PCM16→f32 convention and any WAV padding to \`70*Fs+600\`. Confirm by matching actual sample windows or binary mathematics, not by guessing.
6. Reproduce native ref mean removal, least-squares one-index detrend and \`abs(sample)>0.01\` alignment scan up to 600 samples from \`6*Fs\`. Record expected ref offsets from precisely loaded native buffers; previous diagnostic raw-WAV values **0 for 2203, 19 for SC20** are *not* certified native offsets.
7. Extract 23–28s input/reference f32 segments at native Fs with correct offset. Check phase/time alignment and report exact source and indices.

**RECONSTRUCTION AND VALIDATION**
8. Run **Stage21 own-source sat fitter** on each exact pair; do not read vendor gains during fitting.
9. Evaluate four params **held-out** versus 4 float32 from corresponding official CLO only after calculation. Report max absolute, percent and float32 ULP error; if different, pinpoint first source-confirmed divergent step. Ensure no silent "calibration" to official target.
10. Independent synthetic and two-NAM read-only regression; release ZIP with verifier, evidence, Markdown report; no commercial binaries/audio and no guessed CLO.
11. GitHub docs Stage23 only after verification, commit actual SHA, provide \`git pull --ff-only origin main\`. If unclosed block remains, report exactly which native instruction/array is unknown.

**FURTHER ROADMAP** only after sat-fit parity: reconstructed real-WAV initial A/B through native front-end / \`B82B0\`; full three selector fits and final FIR; exact file output/resampling; physical listening comparison only after user consent.

## 9. Documentation, references, git continuity

For each existing stage detailed source-proof and corrections live at:
\`https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE{2..22}.md\`.
Stage1 is preserved only in original research archive. Current authoritative next-stage reports: [Stage21](https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE21.md) and [Stage22](https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE22.md). The baseline commit before creating this handoff is [\`f8c0377\`](https://github.com/TheColdVoid1337/PocketMasterStudio/commit/f8c037776588666312e22ba1ef6c1004adda5dff).

The user-facing **portable ZIP** is separate from GitHub, contains a more extensive 160KB legacy-inclusive local \`POCKET_MASTER_HANDOFF_2026-10-12_MAX.md\`, more paste-oriented 72KB \`..._PASTE.md\`, and Stage 1–22 research ZIPs. Do not add the proprietary DLL or captured WAVs to it. Original media will need to remain attached in new chat/Project or be supplied if unavailable.

---

# APPENDIX — MOST RECENT PROVEN PRIMARY REPORTS

The following are verbatim current GitHub stage reports, not rewritten optimistic summaries.


## Stage 21 — exact current GitHub report

# Sonicake HTKPA Stage 21 — Source-confirmed 4-parameter saturator fitter

**2026-10-12 · DLL-first, static, read-only research.** The native saturator-fitting routine `0x1800BDBE0` (end `0x1800BE6F6`) was reconstructed algebraically for ordinary finite/positive/negative, non-degenerate audio. Its **two preprocessed audio inputs from real capture WAV remain not reconstructed**, so the official four CLO nonlinear parameters **have not been independently computed**. No production JavaScript, pedal access, new CLO or commercial DLL execution.

Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; image base `0x180000000`. Original binary, NAM, captured WAVs and vendor CLOs are not committed.

## Inputs/outputs proven from calling code

At `0x1800BEDD8..0x1800BEDE4`, native calling convention: `rcx=context`, `rdx=first preprocessed audio/input`, `r8=second/reference audio`, `r9d=number_of_samples`. Fifth through eighth (Win64 outgoing stack) output pointers are `context+0x243F8`, `+0x243FC`, `+0x24400`, `+0x24404`, respectively. Four native stores at `0x1800BE661/0x1800BE676/0x1800BE682/0x1800BE68F` yield **pmax, nmax, prate, nrate**. The first two are observed reference amplitudes, not optimized jointly with the rates.

## The entire ordinary-domain local algorithm

1. Window length `S = float32(float64(float32(Fs)) × 0.1)`. Number of complete blocks `B = trunc(floorf(float32(float32(samples)/S)))`; start and end per block are `trunc(float32(i×S))`, `trunc(float32((i+1)×S))`. Native use of `floorf` established by `0x1800BDC66→0x18017E13A`, via the IAT.
2. For each block `i`, collect `X[i]=max(abs(input))`, `P[i]=max(0,max(reference))`, `N[i]=min(0,min(reference))`; let `pmax=max(P)`, `nmax=max(-N)`. Supported by `0x1800BDD80…0x1800BDECD`.
3. Allocate **4B float32 values** to form two arrays of length **2B** (`0x1800BDF12…0x1800BE16C`):

   ```text
   inputs_for_fit = [-X[B-1], ...,-X[0], X[0],...,X[B-1]]
   targets_for_fit = [N[B-1], ...,N[0], P[0],...,P[B-1]]
   ```

   The individual native stores in `0x1800BE011/0x1800BE01D/0x1800BE025/0x1800BE02E` and the scalar tail establish the array roles. The **separate symbolic pointer/address interpreter** supplied in the research ZIP traces the actual original DLL disassembly without executing it and proves the above permutation for **B=4,5,7,8,9,10,12**.
4. Find first, **one-based** `Kp` for which `P[Kp-1] >= pmax/2`; similarly `Kn` with `N[Kn-1] <= -nmax/2`. Determine initial slopes from the **earliest** `K` envelopes, with double-precision accumulators and float32 inputs:

   ```text
   slope_p = float32( Σ(i<Kp) P[i]*X[i] / Σ(i<Kp) X[i]^2 )
   slope_n = float32(-Σ(i<Kn) N[i]*X[i] / Σ(i<Kn) X[i]^2 )
   initial_prate = float32(slope_p/pmax)
   initial_nrate = float32(slope_n/nmax)
   ```

   Half-maximum tests `0x1800BE1A0/0x1800BE1E0`, OLS products/divisions `0x1800BE259…0x1800BE47A`.
5. Given the asymmetrical exponential model:

   ```text
   sat(x)=pmax*(1-expf(-prate*x)) if x>0
   sat(x)=nmax*(expf(nrate*x)-1) if x<=0
   ```

   Minimize `float32` accumulated SSE `Σ(target - sat(input))²`. Search **positive rate first** (negative rate fixed), then search **negative rate** (updated positive rate fixed). Each searches exactly nine f32 multipliers beginning with `f32(0.8)`, repeatedly `f32(float64(previous)+0.05)`, bounded by `1.2`: `0.8000000119, 0.8500000238, 0.9000000358, 0.9500000477, 1, 1.0499999523, 1.0999999046, 1.1499998569, 1.1999998093`. On equal scores the **later candidate wins**, as `comiss best,new; jb skip` only excludes strictly worse candidates. Native SSE instructions are pinned across `0x1800BE480…0x1800BE68F`.

The Python code is a **source-derived algebraic implementation**, not proven native bit parity: Windows CRT `expf` approximation, floating summation order at corner cases, zero envelopes, NAN/INF, degenerate denominators and sample alignment remain separately open.

## Tested synthetic end-to-end fitter

A 60-second **fully synthetic, already preprocessed signal pair**, Fs=1000, produces B=600 blocks, 1200-point signed paired fit. Normal-domain computed `(pmax,nmax,prate,nrate)`:

`(0.0639682636, 0.0686569139, 17.5292663574, 15.1124286652)`.

SSE falls **0.0926445648 → 0.0407116860**. The fitting parameters are *not supposed* to be identical to the synthetic signal generator's underlying asymptotic parameters: Sonicake derives the amplitudes from observed maxima, then searches only local rates.

## Independent proofs and real-source comparison gate

The source-pinned verifier passes **75 instruction predicates**, **eight original PE float/double constants** and **77 independent synthetic assertions**. Seven additional pointer/address trace tests cover array permutations. Two separate verifier runs yield byte-identical evidence JSON SHA-256 `fe1e9bcf8cc18ce8c94d260612960773ccf1c474d48ddd6d3c862854e7705658`. The ZIP integrity check passes. The DLL is only **statically disassembled** (never loaded or executed).

Two SHA-pinned official Windows Manager CLOs have been **read only** as future parity checks, not as fitter targets:

| Model | pmax | nmax | prate | nrate | Independently regenerated? |
|---|---:|---:|---:|---:|---|
| JCM800 2203 Crunch | 0.0586976074 | 0.0625180602 | 425.438965 | 356.188354 | **NO** |
| SC20 Full Rig | 0.0106169116 | 0.0126974732 | 450.926178 | 253.910919 | **NO** |

The official input DI captures are byte-identical 44.1kHz audio while Manager output captures are at 48kHz. **They cannot be fed directly into this routine as its actual inputs**: the native driver supplies two audio buffers previously processed by its own 50-tap FIR, IIR, sample-rate and alignment stages. Using the published official gains as initialization would contaminate the experiment and is forbidden by our strict gate.

**Research package**: `Sonicake_HTKPA_DLL_RE_Stage21_v0_21.zip` delivered in the conversation: `stage21_saturator_source.py`, `native_repack_trace.py`, `audit_official_reference.py`, read-only evidence, synthetic demonstration, README and full report. No DLL, NAM, WAV or CLO included.

**Stage 22 source-first gate:** independently reconstruct both **actual audio arguments** at native call `0x1800BEDE4` from captured WAV and native preprocessing (including alignment/resampling/IIR), then calculate the four real model parameters. Require held-out numerical comparison against **both** official Windows CLOs before building full Pre-FIR/Post-FIR. Do not make guessed sound tweaks or alter production JS. Preserve hardware-auditioned 2203 v0.2 C.


## Stage 22 call-order correction (2026-10-12)

Stage 21's end note claims that the two `0x1800BDBE0` audio buffers were already passed through **50-tap FIR / IIR**. **This was incorrect.** Direct register and call-site inspection in outer `0x1800BE830` proves `r15 = context+0x243E0` and `rbp = context+0x243E8 + detected_onset_offset`. The output buffer undergoes mean removal and linear-detrend *in place*; the fitter `0x1800BDBE0` is called at **`0x1800BEDE4`**, and the separate IIR helper `0x1800BD490` is called only **afterwards at `0x1800BEE25`**. The fitter receives exactly **`trunc(float32(5×Fs))`** samples beginning at **23×Fs** on the source and 23×Fs + delay on the reference. Onset delay is searched at 6×Fs within 600 sample positions using threshold 0.01, following target mean/trend removal. Native import/resampling of the 44.1-kHz source DI versus 48-kHz stored output WAV remains **NOT_PROVEN**; official Marshall gains remain **NOT_COMPUTED**. The Stage-21 envelope/regression/9×2 search mathematics itself is unaffected. See [Stage 22](NAM_CLO_HTKPA_DLL_RE_STAGE22.md) for native-address pins and negative test boundaries. This visible erratum is appended rather than silently altering historical claims.


## Stage 22 — exact current GitHub report

# Sonicake HTKPA Stage 22 — real fitter-window and pre-fit reference conditioning

**2026-10-12 · Source-first, read-only.** Native Windows `5868USB.dll`, SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, base `0x180000000`. Original DLL is statically disassembled but **never executed**. No production JS, CLO or pedal writes; proprietary source media not committed.

## Corrected execution order

`0x1800BE830` uses a 70s + 600 samples native-float32 input/reference capacity (allocated at `0x1800B5640`; constants `70.0f, 600.0f, 4.0f`). It **removes the mean and least-squares linear drift of the target/reference buffer** `context+0x243E8` at `0x1800BE8E7..0x1800BEA34`. The source input `context+0x243E0` is not modified in those two operations.

It searches a **600-sample** reference onset interval starting at **6×Fs** and triggers when `abs(reference)>0.01` (`0x1800BEA59..0x1800BEAD6`). It sets separate input/target pointers to **23×Fs** and **23×Fs + onset offset** (`0x1800BEB2B/0x1800BEB41`).

**Crucially, the nonlinear four-gain fitter is called first**, at `0x1800BEDE4`, with Win64 `RDX = r15` (input), `R8 = rbp` (shift-aligned reference) and `R9D=trunc(float32(5×Fs))`. Thus the Stage-21 four-gain fit consumes only the **23–28-second** source and target sections. The IIR helper `0x1800BD490` is called **later** at `0x1800BEE25` with other audio buffer pointers; it does not precede the four-parameter fit. Earlier documentation suggested FIR/IIR preprocessing must run before the gain fitter; **that hypothesis has been explicitly corrected** in [Stage 21](NAM_CLO_HTKPA_DLL_RE_STAGE21.md). Prior to this step, buffer loading and sample-rate conversions may of course occur: exact PCM-to-native-buffer provenance remains unproven.

### Pinned addresses

| Code | Direct evidence |
| --- | --- |
| `0x1800B56B5/0x1800B56F2` | allocations stored at `+0x243E0/+0x243E8` |
| `0x1800BE8E7/0x1800BE930` | target-only mean subtraction |
| `0x1800BE9F2/0x1800BEA01/0x1800BEA34` | OLS slope/intercept then target-only detrend |
| `0x1800BEA5D/0x1800BEA64/0x1800BEAB2` | 6×Fs, 600-sample search and threshold |
| `0x1800BEAF8/0x1800BEAFF` | source/input and target/ref pointers |
| `0x1800BEB2B/0x1800BEB41` | 23×Fs input and target+onset |
| `0x1800BEADA/0x1800BEDBF` | 5×Fs sample count |
| `0x1800BEDDB/0x1800BEDDE/0x1800BEDE4` | exact nonlinear fitting call and argument registers |
| `0x1800BEE25` | subsequent call to IIR helper, **after** nonlinear fit |

## Reproducibility

Separate user-facing `Sonicake_HTKPA_DLL_RE_Stage22_v0_22.zip` contains the independent analyzer `stage22_pre_fit_trace.py`, Stage-21 standalone fitter for reference, research report, README, JSON evidence and verification log. It excludes DLL, user WAV/NAM and vendor CLO.

- **43** exact machine-instruction pins verified; **7** binary float/double constants; **53** synthetic assertions for window addresses, duration, fixed buffer capacity, threshold and affine trend-removal.
- Two independent inspections of the pinned SHA DLL yielded identical evidence JSON SHA256 **`d4c4edbd29674ddd3ab9a161192b579647bb9f58a441b00a8c52970a6faaedbb`**.
- Original manager captures were read **only for diagnostic alignment**, not used to fit any model parameter. On the saved **48-kHz** output PCM16 arrays plus 600 zeros, approximate vectorized OLS gives 0 samples for JCM800 2203 and 19 samples for SC20. **These are not proven bit-exact/native offsets**. The source DI WAV is 44.1 kHz, making precise native input import and resampling an unresolved requirement.
- Native four-gain parity for either JCM800 and whole-FIR parity: **NOT_COMPUTED / NOT_TESTED**, not claimed by synthetic assertions.

## Next source-first acceptance gate

Trace manager ingestion and native float32 buffer population under `context+0x243E0/+0x243E8` (including resampling of the 44.1-kHz DI, sample scaling, delay and padding). Then generate the **actual two 23–28s arrays** and use Stage 21's already-derived saturation fitter; compare to official four gains only as a *held-out* numeric validation target. No guessed resample default or CLO fitting to the official target, no automatic gain/EQ fixes, no production changes. Existing hardware-tested JCM800 2203 v0.2 C remains the control.


---

# CHRONOLOGICAL SOURCE-PROOF APPENDICES — Stages 2–20

Below follow actual GitHub research documents; historical errata are overridden by the summary above and later Stage documents.


---

## COMPLETE PRIMARY SOURCE REPORT — Stage 2

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE2.md

# Sonicake HTKPA static reverse engineering — Stage 2 (2026-10-12)

**Scope:** user-supplied Windows `5868USB.dll`; PE disassembly and import table only. No execution of DLL, no changes to production JS-only converter, no pedal writes. Pinned SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. VAs assume PE base `0x180000000`.

## Confirmed findings

- **Exact saturator family** at `0x180028690`: when `x>0`, `Pmax*(1-exp(-Prate*x))`; otherwise `Nmax*(exp(Nrate*x)-1)`. `expf` is an import at IAT RVA `0x18B9A8` via thunk `0x18017E12E`. The actual DLL uses float32 operations in this scalar function. **Same mathematical function as our current SonicMaster-based implementation**, not necessarily same numerical fitting or rounding.
- **Four-gain fit routine** at `0x1800BDBE0`. The caller passes pointers to context `+0x243F8`, `+0x243FC`, `+0x24400`, `+0x24404`, which are the four nonlinear fields later packed into CLO. The routine bins signal amplitude statistics separately by polarity, computes nonlinear predictions and squared residuals, searches positive and negative rate scale factors over approximately **0.8–1.2 in 0.05 steps**, then writes four results (`0x1800BE661`, `0x1800BE676`, `0x1800BE682`, `0x1800BE68F`). Binning, normalization and exact optimizer are not fully reconstructed.
- **Recursive audio preprocessing** in `0x1800BD490`: two-state second-order filtering with feedback coefficient banks `+0x232F0/+0x232F8` and `+0x23318/+0x23320`, and feedforward banks `+0x232D8/+0x232E0/+0x232E8` and `+0x23300/+0x23308/+0x23310`. Arithmetic is consistent with two second-order direct-form-II sections. Their exact purpose is unknown; this is not evidence that the final CLO has IIR in place of FIR.
- **Sample-rate-specific coefficient tables** at `0x1800BC6B0`, checking 44100, 48000 and 96000 Hz. The type of filter/resampler/window represented by those tables is not yet known.
- **Three differently parameterized stages**, not necessarily coordinate-descent repetitions: at `0x1800BEE9F`, `0x1800BEEAA`, `0x1800BEEB5`, selector values **2 → 1 → 3** are stored. The dispatcher indexes distinct pointers/lengths and calls `0x1800BB210` three times. `0x1800B9B70` follows and participates in final filter construction.

## Matching reference pairs

For the **same** source models, measured nonlinear gains (little-endian float32 starting at CLO byte 104):

| NAM | Implementation | Pos Max | Neg Max | Pos Rate | Neg Rate |
| --- | --- | ---: | ---: | ---: | ---: |
| JCM800 2203 Crunch | Windows Sonicake Manager | 0.058698 | 0.062518 | 425.44 | 356.19 |
| JCM800 2203 Crunch | Void baseline | 0.207526 | 0.207998 | 764.80 | 764.80 |
| SC20 Full Rig | Windows Sonicake Manager | 0.010617 | 0.012697 | 450.93 | 253.91 |
| SC20 Full Rig | Void baseline | 0.054729 | 0.056443 | 877.18 | 1182.64 |

Gain values cannot be used alone to determine output loudness: FIR scaling and input drive differ. Mobile SONICLINK is **not proven** numerically identical to Windows Manager.

## Reproducibility / acceptance

Stage-2 standalone read-only Python verifier `verify_stage2.py` was run against the DLL both with live GNU `objdump` output and a cached disassembly. **30 static instruction checks plus expf import** passed. Evidence JSON was byte-identical in both runs. The full technical report, verifier, machine-readable evidence and gain comparison were distributed as `Sonicake_HTKPA_DLL_RE_Stage2_v0_2.zip` with the user. The proprietary DLL and captured WAV/CLO are excluded from this Git repository.

## Remaining work

Trace `0x1800BB210` (different selector-specific arrays), `0x1800B9B70` and `0x1800B82B0` until the concrete Pre-FIR/Post-FIR design equations can be independently reproduced from the matching input/output WAVs and checked against both official CLOs. Reconstruct all context coefficient initialization and exact gain-fitting normalization, then separately prototype a single-70s-probe **pure-JS opt-in** pipeline. The working JS converter and the positively auditioned JCM800 2203 v0.2 C remain untouched.

**No claim of bit-exact vendor CLO reconstruction or sound-quality equivalence.**



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 3

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE3.md

# Sonicake HTKPA reverse engineering — Stage 3 (2026-10-12)

**Static research only.** This work analyzes the user's Windows Sonicake Manager `5868USB.dll` (SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`) without executing it. Virtual addresses assume PE64 image base `0x180000000`. The binary, vendor WAV/CLO captures and proprietary inputs are **not distributed or committed**. Production JS-only Void Mod is **unchanged**.

This stage follows `0x1800BB210` (the three-selector fitting dispatcher calls this repeatedly) and `0x1800B9B70`, plus helpers `0x1800B82B0`, `0x1800B4CF0`, and `0x1800B52E0`.

## Confirmed local mathematics

1. **Iterated power-law correction** in `0x1800BB210`. A call to imported `powf` at `0x1800BB46E` computes `powf(base[i], exponent_scale * q[i])` and clamps output to **[0.2, 5]** (`0x1800BB479`, `0x1800BB48C`). The scalar exponent scale is multiplied by **0.9** in the iteration (`0x1800BB4BE`; constant VA `0x18024C654`). The procedure multiplies/divides per-element arrays (`0x1800BB575`, `0x1800BB6E1`), invokes convolution/filter helpers, applies the original asymmetric exponential saturator `0x1800BE700` at `0x1800BBCC9`, and invokes `0x1800B82B0` **twice** (`0x1800BC055` and `0x1800BC3C5`). **Exact state-array identities and the complete update rule remain unresolved.**

2. **512-element logged metric** at `0x1800BC410..0x1800BC440`: `mean(abs(logf(v[i] + 2^-23)))` over 512 values. The bound `0x200`, `logf` import, absolute-value mask, and multiplier `1/512` (`0x18024C4F0`) are explicit. The *source* of this array has not been proven: its length matching the pedal's transmitted 512 Post-FIR taps is **not enough** to identify it with those taps.

3. **Exact Hamming window** in `0x1800B82B0`:
   `w[n] = 0.54 - 0.46*cos(2*pi*n/(N-1))`.
   Direct assembly: cosine `0x1800B83CA`, multiply by 0.46 `0x1800B83CF`, subtract from 0.54 `0x1800B83D8`. Coefficients at `0x18024C5B0` (0.46), `0x18024C5D4` (0.54), and `0x18024CCF0` (2π). It remains to be shown exactly how this taper feeds the final CLO filters.

4. **Spectral magnitudes and regularized ratio** inside `0x1800B9B70`. Consecutive `(re,im)` pairs are converted by `sqrtf(re² + im²)`, including `0x1800BA97B`. The ratio code near `0x1800BAC70..0x1800BAD2E` has local scalar form:
   `r[k] = 1e6 * M_a[k] / (1e6 * M_b[k] + 2^-23)`,
   explicitly clipped to **[0.1, 10]** (`0x1800BAEB3`, `0x1800BAEC6`). Exact assignments of `M_a` and `M_b` to full pipeline buffers, and their later normalization, **are not yet known**. Further output balancing computes RMS-like squared-energy ratios (`0x1800BB010..0x1800BB0E2`).

5. **Sample-rate-dependent temporary support** near `0x1800B9BCB` is `ceil(0.1*sample_rate)` (~4410 at 44.1kHz, 4800 at 48kHz). This does **not** identify a final output filter length. The routine also has cosine tapering near `0x1800BA820`, complex-data processing via `0x1800B4CF0`, and trigonometric basis generation in `0x1800B52E0`. The complex helper uses modulo indexing and real/imaginary cross-terms, consistent with circular complex convolution.

## Significance and limits

Stage 3 supports a **multi-stage adaptive, frequency-domain nonlinear fitting** interpretation of official Windows HTKPA, beyond a single linear Post-FIR refit. In particular, Sonicake's local DSP includes Hamming tapering, bounded spectral gain, a 512-element logged control/score, and exponent annealing. These are concrete new avenues for reproducing its sound in a clean original implementation.

**Not yet proven:** exact 128-tap Pre-FIR and 2048-tap Post-FIR design equations, transform scaling/order, intermediate buffer-to-CLO mapping, vendor-matched coefficients, bit-exact CLO output, equivalence to mobile SONICLINK, or improved sound on hardware. Do not put partial formulas into production. The well-received JCM800 2203 v0.2 C remains the controlled reference; v0.3 automatic shelf remains unvalidated on real hardware.

## Reproducibility

The separate conversation research artifact `Sonicake_HTKPA_DLL_RE_Stage3_v0_3.zip` contains `verify_stage3.py`, evidence JSON, standalone Python scalar primitive reproductions, **five passing unit tests**, and a detailed technical report. The verifier matched **31 exact assembly instruction locations**, four math imports (`powf`, `logf`, `sqrtf`, `cosf`) and eleven pinned constants. Independent consecutive invocations yielded identical evidence JSON; the ZIP integrity check passed.

Next: trace `0x1800B82B0` output pointers through `0x1800B5D00` and `0x1800B7E10` → `0x1800B65A0` → `0x1800B5A30` into the serializer; then numerically test predicted FIR coefficients against *both* existing matching official Windows Manager CLOs. Only after a numeric coefficient validation should a JS-only experimental pathway be considered.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 4

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE4.md

# Sonicake HTKPA — Stage 4: FIR output and resampling trace

**2026-10-12 · Verified partial result, not a completed FIR reconstruction.** This stage statically examines the user-provided Windows Sonicake Manager `5868USB.dll` (SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`). No proprietary binary has been executed or redistributed, no hardware slot written, and the production browser-only JS converter remains unchanged.

## Newly established data flow

- **Working FIR pointers:** `context+0x24408` holds the 128-tap Pre-FIR input buffer; `context+0x24410` holds the 2048-tap Post-FIR input buffer. The latter is explicitly zeroed and initialized to a unit impulse `(1,0,0,...)` at `0x1800bed4a..0x1800bed5d` prior to fitting.
- **Fitting:** three differently configured calls to `0x1800bb210` (`0x1800bf0c9`), followed by the spectral finishing function `0x1800b9b70` (`0x1800bf11e`). Both working FIR pointers are provided to the optimizer; the spectral finalizer receives the post-FIR destination pointer.
- **Final buffer construction:** calls `0x1800c0d40` at `0x1800bf135` for Pre-FIR and `0x1800bf14f` for Post-FIR; later calls `0x18000ce00` at `0x1800bf364` and `0x1800bf47f` for sample-rate conversion.
- **Target sample rate** is **44,100 Hz** (float32 constant at `0x18024cdf0`). `0x18000d031..0x18000d043` calculates an integer output length by truncating `input_length × target_rate / source_rate`.
- **Packing:** destination tap regions are zero-initialized, and only the rate-converted values are copied into the declared 128/2048-tap VTSI/CLO. Final header and CRC are computed at `0x1800bf4df..0x1800bf542`.

The paired Sonicake Manager NAM-output WAV is 48 kHz. At **48 → 44.1 kHz**, the calculated output supports are **128 → 117** and **2048 → 1881** taps.

## Numerical comparison of actual source-matched CLOs

We verified both the official Windows Manager CLO and the baseline Void CLO, for both matching NAMs. **All four** contain 117 consecutive nonzero Pre-FIR samples followed by 11 zeros, and 1881 consecutive nonzero Post-FIR samples followed by 167 zeros. Thus **the production Void path already exhibits this resampling signature**. It cannot, by itself, account for the audible difference.

Cosine similarity of raw tap vectors (no delay, polarity or amplitude compensation):

| Same-NAM pair | Pre-FIR cosine | Post-FIR cosine |
| --- | ---: | ---: |
| JCM800 2203 Crunch | 0.0174 | -0.1932 |
| SC20 Full Rig | 0.7966 | -0.0311 |

These values are **not perceptual scores**; coefficient phase and latency can strongly affect raw cosine. They do establish that identical container layout and sample counts do **not** imply numerically matching filter taps.

## Acceptance status: **NOT MET**

The Stage 4 objective was to independently calculate at least one complete official FIR from NAM/WAV and match the vendor coefficients. **That has not been achieved**. We have proven the final memory-pointer chain, rate conversion, padding and serialization, not the complete upstream fitting equations or the exact interpolation kernel.

**Remaining concrete target:** trace the outputs of `0x1800b82b0` and the data passed to `0x1800b5d00`/ `0x1800b7e10` and `0x1800b9b70`; reconstruct the complex-spectrum phase convention, inverse transform and normalization into `context+0x24408/0x24410`; then independently generate every nonzero target coefficient (117 Pre or 1881 Post) from a matching reference pair. Matching zero padding or frequency-band averages alone does not satisfy this criterion. Also reconstruct the exact resampling interpolation if byte-level equality is necessary.

## Reproducible verification

The separate research bundle `Sonicake_HTKPA_DLL_RE_Stage4_v0_4.zip` contains:

- `verify_stage4.py`: read-only static verifier with **23 exact instruction checks**, DLL SHA256 pinning, float32 sample-rate constant, CLO VTSI/CRC16 checks, and both official/Void cross-comparisons.
- `static_validation.json`: recorded results for four user-supplied CLOs, with hashes and tap statistics (no proprietary audio or code).
- `RESEARCH_REPORT.md`: source addresses, methods, limitations and next trace targets.

The analyzer checks source CLOs without modifying them; ZIP integrity was verified. Neither the DLL, vendor intermediate audio nor commercial captures are included in the research archive or GitHub.

**Preserve the well-auditioned JCM800 2203 v0.2 C as a subjective hardware reference. Do not change default fitting or introduce generic +gain/HF boosts based on this finding.**



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 5

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE5.md

# Sonicake HTKPA — Stage 5: Gaussian spectrum smoothing

**2026-10-12 · Static reverse engineering · Not a full vendor algorithm.**

This research continues Stage 4 on the user's Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. **The DLL was not executed or redistributed**; no physical device operations or production JS converter changes were performed. All addresses are virtual addresses relative to image base `0x180000000`.

## New confirmed data flow

In `0x1800B9B70`, the spectrum-magnitude ratio already found in Stage 3 is clamped to **[0.1,10]**, then passed to **`0x1800B7E10`** at `0x1800BAEF9`, followed by calls to `0x1800B65A0` and `0x1800B5A30`. The new function performs **Gaussian weighted averaging with boundary renormalization**.

With `N = ceil(0.1*sample_rate)`, the spectral array length is `B = trunc(0.5*N + 1)` and smoothing width is `W = trunc(0.1*B)`.

| Internal sample rate | N | B | W | Approximate Gaussian σ in frequency |
| ---: | ---: | ---: | ---: | ---: |
| 44,100 | 4410 | 2206 | 220 | ~440 Hz |
| 48,000 | 4800 | 2401 | 240 | ~480 Hz |
| 96,000 | 9600 | 4801 | 480 | ~960 Hz |

The independent mathematical kernel (unnormalized, indexing `k=1..W`), verified from double-precision constants and imported `exp`, is:

```
center = ceil(0.5*W)
weight[k] = exp(-0.5 * ((k-center)*5.0/W)**2)
```

- Addresses `0x1800B7E63`/`0x1800B7E85`: constant 5.0 divided by W.
- `0x1800B7E91`: `ceil` of half the window.
- `0x1800B7ECF`/`0x1800B7EDB`/`0x1800B7EDF`: squared, negative-half-scaled distance and `exp`.
- `0x1800B7EE8`: accumulate weights.
- `0x1800B7F02..0x1800B7FE1`: special even-W zero padding, reversed kernel, coefficients multiplied by `1e6/sum(weights)`.
- `0x1800B812F`: interior output multiplied by 1e-6; `0x1800B824C`: boundary output divided by sum of actually overlapping weights.
- `0x1800B8256`: final smoothing output stored in float32.

A **256-float (0x400-byte) work block** is also confirmed in `0x1800B65A0`, including a call to `0x1800B7670` with `0x100` and grouped processing of `0x20 × 8` samples. Its precise transform/overlap role and the relationship to final FIR taps require tracing; it is **not** evidence that a final FIR has 256 taps.

## Reproducible tests and caveats

Separate artifact `Sonicake_HTKPA_DLL_RE_Stage5_v0_5.zip` includes original, clean-room Python code (no proprietary program code), `verify_stage5.py`, `gaussian_spectrum.py`, seven passing unit tests, evidence JSON, optional visualizations, and `RESEARCH_REPORT.md`.

- **27 exact addresses**, **7 binary constants** and imported `exp`/`ceil` were checked against the pinned DLL. Two verifier runs generated identical JSON.
- Seven unit tests pass: 48k/44.1k/96k sizes, odd/even kernel, constant preservation including array edges, spike smoothing, finite/bounded step response.
- Illustrative Gaussian smoothing on the **ratio of finished 512-tap Post-FIR magnitudes** from the user-provided matched CLOs reduces adjacent-bin dB-slope variance by >95%. **This is intentionally *not* a reconstruction of internal Sonicake spectral inputs**, nor a test of auditory fidelity.
- Recovered isolated scalar math and even-window conventions are not bit-accurate end-to-end DLL reimplementation.

## Acceptance status and next targets

**Stage 4 FIR coefficient-level acceptance remains NOT MET.** We have located another processing stage, not recovered the exact 128/2048 final taps. Missing: the source/output spectral buffers, transform phase convention, `0x1800B65A0` → `0x1800B5A30` output mapping into `context+0x24408/+0x24410`, joint fitting and resampler interpolation.

The next scientific gate is unchanged: independently calculate a complete FIR using the same NAM/reference WAV, and numerically compare *all* nonzero coefficients with the matching official Windows Manager CLO on 2203 and/or SC20. Do **not** change production JS default, generalize a +2.5 dB boost, claim matching mobile SONICLINK or ship Gaussian processing from this isolated finding. The user-favored JCM800 2203 v0.2 C is retained as audible control.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 6

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE6.md

# Sonicake HTKPA — Stage 6: complex spectral exponentiation and minimum-phase fingerprint

**Date: 2026-10-12. Research-only; no production change or hardware writes.**

## Key finding

On **two independently captured official Windows Sonicake Manager CLOs**, the full nonzero **1881-tap Post-FIR** almost exactly matches a minimum-phase impulse response independently reconstructed from **its own FFT magnitude**. This is **not** a direct reconstruction of the vendor Post-FIR from the source NAM/WAV.

| Same-NAM CLO | Cosine of Post-FIR vs its magnitude-derived minimum-phase projection | Relative L2 error |
| --- | ---: | ---: |
| Official JCM800 2203 Crunch | **0.998563** | 0.05360 |
| Official JCM800 SC20 Full Rig | **0.999589** | 0.02867 |
| Original Void JCM800 2203 | −0.243669 | 1.57713 |
| Original Void JCM800 SC20 | −0.040724 | 1.44272 |
| Positively auditioned JCM800 2203 v0.1 refit | −0.297339 | 1.61080 |
| User-favored JCM800 2203 v0.2 C | −0.226487 | 1.56620 |

The cosine uses the **raw, aligned coefficient vectors** with no offset, sign flip, gain adjustment or phase fitting. FFT=32768, relative spectrum floor 1e-8, hmin=real IFFT of the exponential of the causal real cepstrum. On FFT sizes 8192/16384/32768/65536 the **official 2203 cosine remains 0.998515–0.998766**, and SC20 **0.999544–0.999800**. This is strong evidence of a **minimum-phase output-filter design** in the Windows algorithm, even though the exact internal implementation is still incomplete. The Pre-FIR on all six tested CLOs already gives ≈1.0 cosine against its own minimum-phase projection.

## Pinned DLL observations

User-supplied Windows `5868USB.dll` SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; base `0x180000000`. The DLL was **only statically disassembled**, never loaded or executed.

- `0x1800B73BB`: imported `logf` in the spectral-processing path.
- `0x1800B7450`: calls spectral interpolator `0x1800B5D00`.
- `0x1800B748F`: reverse-bin lookup for symmetric spectrum construction.
- `0x1800B754A`, `0x1800B7569`, `0x1800B7590`: transform, conjugate-fold, transform helpers `0x1800B4A50 → 0x1800B6E30 → 0x1800B4F60`.
- `0x1800B6EDB` adds paired real components, while `0x1800B6EEB` subtracts paired imaginary components, consistent with Hermitian conjugate folding.
- `0x1800B75D5`, `0x1800B75E1`, `0x1800B75F4`: imported `expf`, `cosf`, `sinf`; nearby multiplies and stores confirm the local complex reconstruction **`exp(a)·(cos(b)+i·sin(b))`**.
- `0x1800B5B4B`: invokes `0x1800C0F60` within fixed 64-sample block processing; exact transform conventions not yet recovered.

Together, the pinned instructions and empirical FIR fingerprint strongly **support** (but do not prove every step of) complex-log / minimum-phase spectral synthesis. Twenty exact-instruction pins are verified by a reproducible read-only `objdump` harness.

## Cross-reference with official Post-FIR, JCM800 2203

Raw cosine of each 1881-tap Post-FIR against the official Windows 2203 Post-FIR, then the same filter after minimum-phase projection **without changing its original magnitude response**:

| Source | Original cosine | Projected cosine |
| --- | ---: | ---: |
| Void baseline | −0.1932 | **+0.9622** |
| v0.1 Post-FIR refit | −0.2847 | **+0.9473** |
| v0.2 C (user's preferred hardware sound) | −0.2916 | **+0.9367** |

**This is a coefficient-comparison result, not a simulated or measured sound-quality improvement.** It highlights a phase mismatch, but the amplitude response and nonlinear gain staging still differ.

## Carefully isolated A/B candidate — NOT hardware-validated

A separately distributed experimental file `JCM800_2203_v06_MIN_PHASE_FROM_C_UNVALIDATED.clo` projects **only the first 512 physically transmitted Post-FIR taps** of the user-favored **v0.2 C** to minimum phase. It changes no Pre-FIR, saturator, DC filter or other coefficients; only those first 512 float32 taps and the derived CRC16 differ. The original v0.2 C remains unchanged.

- Same 8840-byte VTSI with valid CRC16.
- Mean transmitted-tap magnitude-spectrum deviation from C: **0.000217 dB** on a 32768-point frequency grid.
- Tap L2 before/after ~**0.343812**.
- 512-tap cosine to official Windows 2203 changes from **−0.29471** to **+0.95036** (without gain/lag adjustment).
- **No on-device audition yet.** The altered phase can change attack, group delay and feel even if magnitude response is matched. Do not assume audible benefit. Compare only on a spare user slot at reduced monitoring volume, retaining C and official SONICLINK.

## Verification / unresolved acceptance

A separate private-conversation research ZIP `Sonicake_HTKPA_DLL_RE_Stage6_v0_6.zip` contains independently authored Python cepstrum code, pinned read-only DLL verifier, **five passing unit tests**, evidence JSON, impulse-response plots, exact candidate generator and unvalidated CLO. It **does not contain** the proprietary DLL, original NAM, official WAV or official CLO captures.

**The original Stage-4 acceptance gate remains NOT MET:** no complete vendor Pre/Post-FIR has been inferred from the *input/output WAV only*. Computing an official FIR's phase **from its known vendor magnitude** cannot be presented as end-to-end vendor fitting recovery.

**Next:** trace exact Fourier and conjugate/cepstral array semantics in `0x1800B4A50/0x1800B6E30/0x1800B4F60`; then independently fit a stabilized and smoothed amplitude-response target from the 70-second NAM input/output probe to the Pre-FIR+nonlinearity output, and combine it with phase reconstruction. Evaluate coefficient error on **both** source-matched Windows CLOs and listen on-device before any opt-in browser integration. Production JS-only converter and previous positively auditioned reference are not changed.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 7

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE7.md

# HTKPA Stage 7 — NAM-only spectral Post-FIR reconstruction experiment

**2026-10-12 | Research-only | Production unchanged | Original HTKPA coefficient-reconstruction gate still NOT MET**

## Experimental objective

Estimate a 512-tap *minimum-phase* Post-FIR from the known 70-second input DI and **independently computed NAM WaveNet output**, retaining the baseline Void Mod **Pre-FIR / asymmetric saturator / DC blocker**. This is an original Python analysis experiment, **not** the complete official HTKPA, and **not** a standalone NAM-to-CLO converter: the baseline CLO and independent WaveNet predictions are required.

A separate user-delivered bundle `Sonicake_HTKPA_RE_Stage7_v0_7.zip` contains a CLI fitter, tests, per-model reports, numerical validation, and frequency-response plots. **No proprietary DLL, NAM, user WAV or official CLO file was committed.**

## Procedure

- Input is the shared stereo reference DI resampled to 44,100 Hz, with ten fixed two-second 44.1-kHz NAM WaveNet predictions.
- Apply baseline Void Mod 128-tap Pre-FIR, four exponential saturator coefficients and two-pole DC blocker.
- On five training windows (5–7, 18–20, 30–32, 43–45, 58–60 s), use a **4800-sample Hann window** and 50% overlap. Estimate `|S_qy| / (S_qq + 10^-6 × max(S_qq))`.
- Interpolate log magnitude to a 32768-point FFT, reconstruct a causal 512-tap minimum-phase response via the real cepstrum.
- Resolve overall sign/polarity from **training waveform only**. Magnitude alone lost this sign and initially produced **-0.823 signed correlation** for JCM800 2203; correct polarity is +0.823.
- For optional experimental CLO export only, preserve baseline training RMS and regenerate CRC16; research CLI **does not write a CLO without an explicit flag**.
- Validation windows are disjoint (13–15, 26–28, 39–41, 53–55, 65–67 s), but from the **same** 70-second DI; generalization to independent playing is unproven.

The shared 4800-sample support was motivated by Stage 5's verified 0.1-second spectral window. The above PSD ratio is **our hypothesis**, not a proven transcription of Sonicake HTKPA mathematics.

## Heldout results

Absolute signed-gain-aligned waveform Pearson correlation against **independent NAM WaveNet output**:

| Model | Baseline Void | Stage-7 independent WaveNet fit | Previously good v0.1 refit | User-preferred v0.2 C | Stage-6 projected C |
| --- | ---: | ---: | ---: | ---: | ---: |
| JCM800 2203 Crunch | 0.74867 | **0.82262** | **0.89487** | **0.88947** | 0.81740 |
| SC20 Full Rig | 0.65815 | **0.52652 — regression** | **0.76620** | n/a | n/a |

Stage-7 is **not suitable as a replacement**: it loses to the positively auditioned refit for 2203 and regresses on SC20.

## Crucial no-vendor-audio reproducibility check

After fitting, but **only for validation**, estimate the same candidate once more using the official Windows Manager `outputFile.wav` instead of our independent WaveNet. Shape similarity of the resulting 512-tap filters:

| NAM | Cosine: independent-WaveNet fitted Post-FIR vs vendor-WAV fitted Post-FIR | Post-FIR cosine to official Windows Manager (evaluation only) |
| --- | ---: | ---: |
| JCM800 2203 | **0.9999998881** | **0.92268** |
| SC20 | **0.9999610985** | **0.91527** |

The norm ratio of the WaveNet-fitted impulse vs vendor-WAV-fitted impulse is roughly **3.227**, matching the known official WAV `×0.31` scaling. Thus **the target audio no longer requires the official manager**, while the upstream chain *still* does not match HTKPA.

When the **already-known official Pre-FIR and nonlinear parameters** were substituted as diagnostic upstream coefficients (not independent or deployable), the candidate Post-FIR cosine rose to about **0.958 (2203) and 0.924 (SC20)**. This demonstrates that fitting upstream stages jointly remains necessary.

## Stage 5 Gaussian finding needs correct placement

Applying a naive **≈480-Hz Gaussian smoothing directly to the final estimated Post-FIR spectral ratio** degraded heldout waveform correlation:
- 2203: **0.823 → 0.429**;
- SC20: **0.527 → 0.169**.

This experiment **does not falsify** the recovered Sonicake Gaussian kernel. The vendor smooths a specific *intermediate*, not necessarily the final simplified transfer ratio. Array identities must be recovered before transplanting it.

## Acceptance, next work, and safety

**Stage 4's strict acceptance criterion remains unmet:** no full official FIR is yet generated from NAM/WAV and shown coefficient-exact against Windows Manager. Cosine similarity of Post-FIR vectors is not a waveform or listening-quality metric, and the Windows Manager output is not proven identical to mobile SONICLINK.

**Next:** recover the complete input/output buffer identities for HTKPA's selectors **2 → 1 → 3**, jointly identify **Pre-FIR and nonlinear gains**, locate the Gaussian smoother within that actual computation, then reevaluate the end-to-end 128/2048 taps on both NAMs. Do not add arbitrary per-model boosts, do not replace the production browser JS converter, and keep the JCM800 2203 v0.2 C audio-accepted reference intact. Stage 6's phase-only candidate also remains **unvalidated by hardware listening**.

No physical pedal operation occurred. Five standalone Stage-7 Python tests and both read-only NAM-only benchmark runs passed; output ZIP integrity was verified.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 8

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE8.md

# Sonicake HTKPA Stage 8 — DLL-proven region dispatch and optimizer guard

**2026-10-12. Source-first, read-only static reverse engineering of the user's Windows Sonicake Manager 5868USB.dll. No guessed FIR fitter, no new CLO, no production code or device changes.**

Pinned DLL SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. PE image base: `0x180000000`. The proprietary DLL and captured vendor WAV/CLO are not included in the repository.

## Exact fit schedule — independently verified against machine code

The input probe and matching NAM output are grouped by byte pointers in `0x1800BE830`. The output pointers include a *detected sample-alignment offset* (search near 6s, maximum 600 samples), which must **not** be dropped when later reconstructing the numerical fit.

| Execution order | Selector | Input WAV window | Output WAV window | Inner iterations |
| ---: | ---: | --- | --- | ---: |
| 1 | 2 | 23–28 s (5s) | same window plus measured onset offset | 3 |
| 2 | 1 | 6–21 s (15s) | same window plus measured onset offset | 2 |
| 3 | 3 | 30–50 s (20s) | same window plus measured onset offset | 5 |
| Final spectral stage | n/a | 50–70 s (20s) | same window plus measured onset offset | separate function |

**Evidence, not inference:**
- Selector stores **2→1→3** at `0x1800BEE9F/0x1800BEEAA/0x1800BEEB5`. Dispatch and call to `0x1800BB210`: `0x1800BF050..0x1800BF0C9`; loop count three at `0x1800BF0D1`.
- The four-int table at `0x18024CFB0` is exactly **2,3,5,1**; selector-indexed count lookup at `0x1800BF0A3`. The extra 1 is never used by the three selected calls; its independent meaning is **not known**.
- Float32 window constants at `0x18024CCD0/0x18024CD34/0x18024CD40` are **5,15,20**. Length lookup at `0x1800BF0AE`. Input/output pointer lookups are `0x1800BF0BE/0x1800BF0B6`.
- Source starts are directly calculated via multipliers **6,23,30,50 × sample rate** at `0x1800BEA5D`, `0x1800BEB2B`, `0x1800BEB4D`, `0x1800BEB6F`; the output is offset by the detected onset alignment.
- After the three calls, `0x1800BF111/0x1800BF116` load the 50s output/input pair, and `0x1800BF11E` calls **`0x1800B9B70`**, *not* `0x1800BB210`.

**Do not relabel these as “clean”, “saturation”, or “EQ” passes without following their actual buffers and calculations.**

## Actual optimizer branch logic

The fitter at `0x1800BB210` gets its iteration count at `0x1800BB245` and loops back from `0x1800BC5C2`. Therefore the selected counts are actual optimizer iteration counts, not merely unrelated table entries.

The control score at `0x1800BC410..0x1800BC440` has direct scalar form:

`score = (1/512) * sum_{i=0..511} abs(logf(v[i] + 2^-23))`

This is backed by a 512-element loop, `logf` import, bitwise absolute mask and exact float32 constant 1/512. **The immediate producer of v is now known**: `0x1800BC3CA` loads its scratch pointer, `0x1800BC3E4` passes that same pointer as an output argument to `0x1800B5D00` (`0x1800BC3F9`), and the callee **reads that output pointer** at `0x1800B5FE3`, **writes its results** at `0x1800B60FE`; `0x1800BC410` then reads the same buffer in the score loop. Its **mathematical meaning remains unproven**; do not assume those values are physically transmitted FIR taps.

The branch condition at `0x1800BC459/0x1800BC469`, compared with `1.2` at `0x1800BC504/0x18024C9A8` and `0.5` at `0x1800BC59C/0x18024C880`:

```text
if new_score < previous_score:
    save candidate
else if new_score > 1.2 * previous_score:
    restore saved candidate
    exponent_step *= 0.5
else:
    keep current candidate
```

The two complete **Pre-FIR and Post-FIR coefficient arrays** are saved and restored together: live context pointers `+0x24408` and `+0x24410` are forwarded through the fitter, saved via `0x1800BC495/0x1800BC4B2` and restored via `0x1800BC53F/0x1800BC55C`. Meanwhile the exponential-power correction factor is annealed by **0.9 per iteration** at `0x1800BB4BE`.

**Observed:** paired-filter state tracking, iterative acceptance/rollback, score guard and schedule. **Unproven:** complete score-array provenance, candidate-generation equation, official FIR samples from the WAV. The score is not necessarily a perceptual or waveform error.

## Verification and acceptance

The separately delivered self-contained research archive `Sonicake_HTKPA_DLL_RE_Stage8_v0_8.zip` contains `verify_stage8.py`, `RESEARCH_REPORT.md`, `README.md` and machine-readable `evidence.json`; excludes vendor binaries/audio. The verifier checks **70 exact-address assembly predicates**, the PE SHA-256, four integer iteration constants, three window lengths and five optimization constants. Two independent runs produce the same JSON. **The DLL is never executed**.

**Gate still open:** We have **not** independently generated either complete official FIR from the original input/output WAV. This Stage 8 replaces earlier speculation about fitting order with checked machine-code facts; it does not claim a working official converter, sound quality equivalence or identical mobile SONICLINK behavior.

## Next source-first work

Trace the exact input, output and temporary arrays of `0x1800BB210`'s two `0x1800B82B0` calls (`0x1800BC055/0x1800BC3C5`) and two `0x1800B5A30` calls (`0x1800BBB5B/0x1800BC381`). Trace the input arguments and mathematical output of `0x1800B5D00`, now directly proven to produce the 512-element score buffer; then reproduce the actual candidate transform before trying WAV→FIR again. **No heuristic fitting or production changes without a source-confirmed equation and two-model numerical validation.**

Keep the positively hardware-auditioned JCM800 2203 v0.2 C as control; the main browser JS-only converter stays unchanged.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 9

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE9.md

# Sonicake HTKPA — Stage 9: source-confirmed Mel-spaced objective

**2026-10-12 · DLL-first RE · no production changes, device operations or new CLO.**

This stage recovers the exact scalar interpolation and query-frequency generation behind HTKPA's 512-point optimization score, rather than proposing any heuristic fitting. The user's Windows Sonicake Manager `5868USB.dll` is pinned by SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; all virtual addresses assume image base `0x180000000`. **The proprietary DLL was statically disassembled only; it was never executed or distributed.**

## Confirmed 512-point Mel-spaced frequency grid

Initializer `0x1800BFE2E..0x1800BFEEC` (last instruction at `0x1800BFEEC`) generates two float32 vectors in the context:

- `context+0x23328`: 512 **linearly spaced Mel coordinates**, generated by `0x180027DB0` from `2595*log10f(1+80/700)` to `2595*log10f(1+10000/700)`.
- `context+0x23B28`: 512 **Hz query frequencies** obtained with `700*(powf(10,mel[i]/2595)-1)`. First value is set directly to **80.0** at `0x1800BFEB0`; last value is set directly to **10000.0** at `0x1800BFEEC`.

Float32 constants recovered from the pinned DLL: 2595, 700, 10, 1, `1+80/700`, `1+10000/700`; the imported functions are `log10f` and `powf`. The mathematical Mel grid has 512 entries spaced increasingly apart in Hz (approximately 4.01 Hz first step and 54.69 Hz final step). This is a query grid, **not** a final FIR tap vector.

## Confirmed `0x1800B5D00` math

At `0x1800BC3D2..0x1800BC3F9` the fitter calls the interpolation routine with:

| Argument | DLL source | Proven usage |
| --- | --- | --- |
| `rdx` | `rbp` | input knot positions `a[i]` |
| `r8d` | `r14d` | knot count `n` |
| `r9` | `[rsp+0x1A0]` | knot ordinates `b[i]` |
| stack +0x20 | `context+0x23B28` | 512 Mel-spaced Hz queries `q[j]` |
| stack +0x28 | `0x200` | number of queries |
| stack +0x30 | `r13` | output array `v[j]` |

For adjacent knots it computes `s_i=(b[i+1]-b[i])/(a[i+1]-a[i])` and `c_i=b[i]-s_i*a[i]` (`0x1800B5DBB..0x1800B5DEB`). For each query, it chooses the knot with the **smallest nonnegative difference** `q-a[i]` (the nearest predecessor when knots are increasing), then calculates `v[j]=s_i*q[j]+c_i` (`0x1800B6040..0x1800B60FE`). The last slope is propagated for upper extrapolation. No eligible knot gives the sentinel `FLT_MAX`, `3.402823466e38` (constant at `0x18024CE08`), not zero. Nonmonotonic/repeated knot semantics need separate review.

The output pointer `r13` then feeds the known optimization score, immediately at `0x1800BC410..0x1800BC440`:

```
E = mean_{512 bins}(abs(logf(v[j] + 2^-23)))
```

This formula is minimized with Stage 8's proven joint Pre-FIR/Post-FIR save-and-rollback logic. The score's **mathematical** minimum is near a curve of ones, but the physical meaning of the input curve remains **unproven**.

## Outstanding DLL-only tracing

The interpolator receives `a[]` and `b[]` from buffers produced by earlier stages, notably `0x1800B82B0` (called immediately before at `0x1800BC3C5`). **We have not established whether `b[]` is a spectral transfer, filter magnitude, other normalization curve, or something else.** This is the next read-only data-flow target; no heuristic WAV-to-FIR matching should be attempted before resolving it. Official Pre-FIR and Post-FIR coefficients have **not** been reconstructed from the NAM/WAV.

## Reproducibility

The conversation research artifact `Sonicake_HTKPA_DLL_RE_Stage9_v0_9.zip` contains independently written `source_first_stage9.py`, a detailed `RESEARCH_REPORT.md`, a README and machine-readable `evidence.json`. The verifier checks **38 exact instruction addresses**, **9 PE float32 constants**, and **7 synthetic mathematical tests**; two independent runs yield identical evidence. It requires the original SHA-pinned DLL locally but does **not** load or execute it. No vendor DLL, original NAM, WAV, or CLO included.

**No hardware candidate and no changes to production Void Mod.** Retain the user-favored JCM800 2203 v0.2 C for eventual level-matched comparison after end-to-end coefficient validation.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 10

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE10.md

# Sonicake HTKPA — Stage 10: DLL-confirmed cross-spectral fitting score

**2026-10-12. Source-first reverse engineering only. Production NAM→CLO JS converter, device slots and previous experimental CLOs remain unchanged.**

## The now-confirmed meaning of Stage 9's unknown arrays

Stage 9 proved that `0x1800B5D00` linearly interpolates two input arrays onto **512 Mel-uniform frequencies from 80 to 10,000 Hz** and that `0x1800BB210` evaluates:

```text
E = mean_{j=0..511}(abs(logf(v[j] + 2^-23)))
```

Stage 10 traces the two array producers inside **`0x1800B82B0`**, using their caller/callee pointers and exact instructions. The arrays are:

- **Abscissa** `a[k] = (k / N) × sample_rate` in ordinary **linear Hz**.
- **Ordinate** `b[k] = abs(S_AB[k]) / (S_AA[k] + 2^-23)` — a normalized cross-spectral **transfer magnitude** between current generated waveform **A** and desired waveform **B**.

Here `S_AA[k] = Σ_t |A_t[k]|²` and `S_AB[k] = Σ_t A_t[k] × conj(B_t[k])` (or the conjugate, depending on FFT imaginary sign conventions; magnitude is unaffected). Their complex real and imaginary components are accumulated across windowed frames. The same DLL function calculates `sqrt(Re² + Im²)` and divides by the accumulated first-signal auto-spectrum plus the literal epsilon.

Thus **the optimizer's control score evaluates spectral transfer deviation from unity on a perceptual frequency grid, not the values of 512 transmitted FIR taps**. This distinction resolves the Stage 8/9 open buffer-identity question.

## Verified data flow: code addresses (PE image base 0x180000000)

| Operation | VA and evidence |
| --- | --- |
| Current generated waveform **A** | `0x1800BC368` passes `r15` as output of `0x1800B5A30` (call at `0x1800BC381`); `0x1800BC399` passes that `r15` as first argument audio to `0x1800B82B0`. Inside `0x1800B5A30`, `0x1800B5A87` preserves destination from `r9`, and `0x1800B5C11/0x1800B5C15` addresses/copies to that destination. |
| Reference waveform **B** | `0x1800BC391` passes fitter's saved third audio argument (`[rsp+0x1B0]`) as the **second** audio buffer. Upstream `0x1800BF0B6` selects the corresponding probe output WAV region. |
| First and second input work buffers | `0x1800B85A6` and `0x1800B85C2` read and copy the incoming source arrays before preprocessing. |
| Hamming analysis window | `0x1800B83CA..0x1800B83DC`: `0.54 - 0.46*cos(2*pi*n/(N-1))`; local mean removed before weighting. |
| **Half-second frame hop** | `0x1800B83F3` reads exact double **0.5** at `0x18024C880`; `0x1800B83FB` truncates `0.5 × Fs` to an integer. End-window clamping is separately handled and is **not** assumed equal to standard STFT padding. |
| Two FFT-style transforms | `0x1800B8E38` and `0x1800B8E55` invoke `0x1800289D0` with each windowed signal and separate real/imag output arrays. Exact native transform normalization remains unverified. |
| Accumulate `S_AA` | `0x1800B901E..0x1800B9030`: square first-signal complex channels, sum, and add into a persistent auto-power array. |
| Accumulate complex `S_AB` | `0x1800B903E..0x1800B9066`: products of the two signals' real/imag channels, sum real contributions, subtract imaginary contributions, accumulate both. |
| Magnitude `abs(S_AB)` | `0x1800B9548..0x1800B9551`: sum of squares and square root. |
| Divide by `S_AA + epsilon` | `0x1800B9554..0x1800B955F`: epsilon vector at `0x18024D110`, equal float32 `2^-23`. Scalar tail `0x1800B97EF..0x1800B9817` also checked. |
| Generate abscissa in Hz | `0x1800B9564..0x1800B957B`: `k*Fs/N`, `floor(N/2)+1` bins. Scalar tail `0x1800B981D..0x1800B9832`. |
| Interpolate and score | `0x1800BC3D2..0x1800BC3F9` calls `0x1800B5D00` with transfer magnitude knots and 512 Mel-Hz queries; `0x1800BC410..0x1800BC440` scores the interpolated ratios. |

## Validation and limits

Research bundle `Sonicake_HTKPA_DLL_RE_Stage10_v0_10.zip` was delivered separately as a conversation artifact and includes an independently authored read-only verifier, `RESEARCH_REPORT.md`, and JSON evidence. Against the user-supplied SHA-pinned `5868USB.dll` it passed **51 exact address/instruction predicates**, checked **five PE constants**, and passed **eight synthetic scalar tests**. Two runs yielded byte-identical JSON. The DLL was **not executed** or redistributed.

**Independent synthetic test**: if B is exactly 1.7×A, the cross-spectrum ratio tends to 1.7 on sufficiently excited bins; unity signals produce a near-zero logarithmic score. A pure phase shift can leave transfer magnitude unchanged. These are properties of the now-proven scalar formulas, **not** evidence of bit-exact reproduction of the DLL's complete transform, optimizer or fitted CLO.

### Remaining strict acceptance gate

We have **not** calculated an exact official Pre-FIR or Post-FIR directly from source NAM/probe WAV. The **objective is more precisely known** now, but the mechanism for changing Pre-FIR and Post-FIR remains to be recovered.

**Next source-first Stage 11 target**: trace `0x1800BB440..0x1800BBB5B`, both calls to `0x1800B7670` (`0x1800BB4D9`, `0x1800BB4F8`), and `0x1800B68F0`. Establish actual candidate update equations, buffer identities and normalization from machine code **before** writing a fitting implementation or exporting experimental CLOs. Retain the user-preferred JCM800 2203 v0.2 C as subjective control; production JS remains unchanged.

**The Windows Manager algorithm is not proven identical to mobile SONICLINK.**


## Erratum added during source-first Stage 19 (2026-10-12): STFT hop is **half a window**, not half a second

The Stage-10 text `Half-second frame hop` / `≈0.5-second hop` was mistaken. `0x1800B8373` assigns the **analysis window length** to `r14d`. `0x1800B83EA–0x1800B83FB` converts that same window length to double, multiplies by PE double `0.5` (`0x18024C880`), then truncates to an integer. Therefore the actual step is **`trunc(window_samples*0.5)`**, a 50%-window hop. For a 4,800-sample window at 48 kHz it is 2,400 samples or 0.05 seconds, **not 0.5 seconds**. Any synthetic STFT fitting code using the previous fixed duration must be corrected before a numerical A/B comparison. This is an evidence-backed correction, not a heuristic. See [Stage 19](NAM_CLO_HTKPA_DLL_RE_STAGE19.md).



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 11

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE11.md

# HTKPA Stage 11 — DLL-proven **Pre-FIR candidate synthesis**

**2026-10-12 · Strict source-first static research · No converter or device changes.**

DLL: user-provided Windows Sonicake Manager `assets/5868USB.dll`; SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. All addresses are image-base `0x180000000` virtual addresses. The proprietary DLL was never executed and is not committed.

This stage starts with the specified chain: `0x1800BB440` → `0x1800B7670` → `0x1800B68F0`. It establishes **which working FIR buffer is written** and recovers the end-of-synthesis normalization. **It does not generate an official CLO or implement the missing full spectral algorithm.**

## Critical pointer identity: **Pre-FIR**, not Post-FIR

The fitter caller at `0x1800BF07C` reads `context+0x24408` (**Pre-FIR**) and stores the pointer at stack `+0x58` (`0x1800BF083`). It separately reads `context+0x24410` (**Post-FIR**) at `0x1800BF070`, storing it at stack `+0x60` (`0x1800BF077`).

Inside `0x1800BB210`, `0x1800BB821` reads `[rsp+0x1F8]` and passes it to `0x1800B68F0` via the fifth Windows x64 argument at `0x1800BB831`; the actual call is `0x1800BB836`.

**Correct stack mapping** accounts for the *8-byte call return address*, 8 callee pushes (64 bytes) and the 0x158-byte local allocation:

```text
Callee stack offset 0x1F8 − (8 + 64 + 0x158) = Caller stack offset 0x58 = Pre-FIR
Callee stack offset 0x200 − (8 + 64 + 0x158) = Caller stack offset 0x60 = Post-FIR
```

A preliminary manual read omitted the return-address byte count and misidentified the destination as Post-FIR. This was **corrected before this release** and regression-tested. As an independent check, `0x1800BB817/0x1800BB81E` feed both length arguments from `context+0x20ED4`, corresponding to **128 Pre-FIR taps**, not the 2048 Post-FIR tap count.

## Stage 11 candidate pipeline: verified machine-code operations

- `0x1800BB460..0x1800BB48C`: per-element `powf` correction and clipping to **[0.2,5]**, with the exponent factor multiplied by **0.9** at `0x1800BB4BE`. These operations were first pinned in Stage 3.
- `0x1800B7670` invoked **three times** at `0x1800BB4D9`, `0x1800BB4F8`, `0x1800BB812` with different pointer arguments. Inside are two `0x1800B7E10` Gaussian smoothings (`0x1800B7BBB/0x1800B7C12`) and three `0x1800B5D00` piecewise-linear interpolations (`0x1800B7BF8/0x1800B7C4B/0x1800B7C8C`). Working arrays also undergo `mulps` / `divps` at `0x1800BB575/0x1800BB6E1` and separate conditioning `0x1800B6220` at `0x1800BB7E3`. The **complete composite update formula** and exact intermediate-buffer semantics remain unproven.
- `0x1800B68F0` is the identified **Pre-FIR synthesis output writer**. It performs:
  1. Mirror extension of an N-point array into **2N−2** samples, excluding duplicate endpoints: `[a,b,c,d] → [a,b,c,d,c,b]` (`0x1800B691F/0x1800B6925/0x1800B69A0`).
  2. Spectral preparation/transform via `0x1800B72E0`, `0x1800B52E0`, `0x1800B47F0` (`0x1800B6A16/0x1800B6A50/0x1800B6A66`). **Their exact composition has not been fully reconstructed.**
  3. Measure L2 energy of the **entire** 2N−2 transformed support (`0x1800B6B18`), then copy the first M output samples to the working Pre-FIR (`0x1800B6B39`).
  4. Subtract the mean of those M output samples (`0x1800B6B9D/0x1800B6BEB`) and restore the original full-support L2 by multiplying every output sample by `full_norm / centered_output_norm` (`0x1800B6D07/0x1800B6D0E/0x1800B6D52`). Degenerate zero-norm behavior is not yet characterized.

Thus the **independently implemented isolated scalar stage** is:

```python
mirror = x + x[-2:0:-1]
z = UNKNOWN_NATIVE_SPECTRAL_TRANSFORM(mirror)
target_norm = sqrt(sum(t*t for t in z))
h = z[:M]
h = [t - mean(h) for t in h]
h = [t * target_norm / sqrt(sum(v*v for v in h)) for t in h]
```

The unknown function is intentionally **not** replaced with a guessed FFT/minimum-phase method. This sketch does **not** produce real Pre-FIR coefficients yet.

## Cross-check on matched official CLOs

Both official Windows Manager CLOs exhibit near-zero DC sums in their **128-entry Pre-FIR field** (after 48k→44.1k support conversion, 117 active taps):

| Model | Pre-FIR sum | Pre-FIR L2 | abs(sum)/L2 |
| --- | ---: | ---: | ---: |
| JCM800 2203 Crunch | 0.014214161456 | 3.231613432 | 0.00439847 |
| SC20 Full Rig | 0.005174505462 | 2.496118188 | 0.00207302 |

This is an *independent compatibility check* with the identified mean removal, **not proof of bit-exact reconstruction**. No official FIR coefficients were used in parameter fitting.

## Reproducibility

Separate conversation package `Sonicake_HTKPA_DLL_RE_Stage11_v0_11.zip` contains `verify_stage11.py`, `RESEARCH_REPORT.md`, `README.md`, and `evidence.json`. The read-only verifier confirms **43 exact-address machine-code predicates**, SHA-256, and **9 isolated mathematical/stack-mapping tests**. Two runs produced byte-identical evidence JSON; ZIP integrity verified. The package excludes the commercial DLL, NAM, WAV and official CLOs.

**Remaining acceptance gap:** neither full 128-tap official Pre-FIR nor 2048-tap Post-FIR has been regenerated solely from the input/output NAM probe. Next DLL-first tasks are the exact mathematics of `0x1800B72E0` (including `0x1800B7150`) and `0x1800B47F0`, plus the **separate Post-FIR update path** carried at fitter stack `+0x200`. No new hardware test file and no production JavaScript change. Keep the user-auditioned JCM800 2203 v0.2 C as listening control.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 12

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE12.md

# Sonicake HTKPA — Stage 12: Pre-FIR complex-log spectral pipeline

**2026-10-12 · DLL-first, static research only.** No proprietary code executed/distributed, no new CLO generated, no physical pedal writes, no production JS converter changes.

Pinned Windows `5868USB.dll` SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; VAs assume base `0x180000000`.

## Directly proven operations

Stage 11's **128-tap Pre-FIR writer** `0x1800B68F0` calls `0x1800B72E0` at `0x1800B6A16`, then `0x1800B52E0` at `0x1800B6A50` and `0x1800B47F0` at `0x1800B6A66`, before the previously traced mean subtraction and L2 energy normalization.

Inside `0x1800B72E0`:

1. `0x1800B733B`: the vector input passes through `0x1800B7150`. With **−100.0** at `0x18024CF38`, scale **0.05** at `0x18024C520` and double-precision base **10.0** at `0x18024CB30`, the guard floor is `max(abs(x)) * 10^(-100*0.05) = max(abs(x))*1e-5`. The guard replaces values whose absolute magnitudes fall below this floor with a **positive** floor; negative-valued and degenerate inputs have unresolved native semantics.
2. `0x1800B7380/0x1800B73BB`: add float32 `2^-23` (`0x18024C4D4`) and compute `logf`; the conditionally guarded and logged array feeds downstream transforms.
3. `0x1800B7416/0x1800B7433/0x1800B7450`: if source/target lengths differ, construct evenly spaced index coordinates and use the Stage-9-proven piecewise-linear interpolator `0x1800B5D00`.
4. `0x1800B7480..0x1800B74DD`: the first `floor(N/2)` bins are overwritten with bins `N−i−1` from the second half. **One-sided overwrite, not a generic FFT library's usual Hermitian mirroring.**
5. `0x1800B7534/0x1800B754A/0x1800B7569/0x1800B7590`: sine/cosine basis `0x1800B52E0`, first complex trigonometric transform `0x1800B4A50` (its loop includes **1/N** normalization at `0x1800B4C62/0x1800B4C6D`), conjugate-pair folding `0x1800B6E30`, then a second complex transform `0x1800B4F60`. At `0x1800B6EDB/0x1800B6EEB` paired real components are **added** and paired imaginary components are **subtracted**. There is a separate midpoint/conjugate handling at `0x1800B710C`.
6. `0x1800B75D5/0x1800B75E1/0x1800B75F4`: imported `expf`, `cosf`, `sinf` construct each complex bin as **`exp(a) × (cos(b) + i·sin(b))`**; real/imaginary floats are saved at `0x1800B75EA/0x1800B7601`.

The last transform `0x1800B47F0` uses a trigonometric basis with **2π/N** (`0x1800B530A/0x1800B5322`), products and a subtraction near `0x1800B48F9`, then **1/N** normalization at `0x1800B49E7` using the constant `1.0` at `0x18024C6A0`. For a given complex input `H[k]`, its isolated real output has algebraic form:

```text
h[n] = sum_k (Re(H[k])*cos(2πnk/N) − Im(H[k])*sin(2πnk/N)) / N
```

This equals `real(ifft(H))` mathematically (not necessarily bit-exact in float32/native summation order).

## How far this gets us

This is strong **source-level support** for a complex-log/cepstral spectral Pre-FIR synthesis stage, compatible with Stage 6's observed near-minimum-phase fingerprint in official filters. It **does not** prove that substituting an off-the-shelf `minimum_phase` library produces vendor-identical Pre-FIR taps. The intermediate array ordering, full first/second transform conventions, optimizer-provided spectral target, and the **separate Post-FIR writer** remain incomplete.

Stage-4 strict criterion **still unmet**: neither complete official Pre-FIR nor complete official Post-FIR has been independently computed from source NAM/WAV.

## Verification

Self-contained research archive `Sonicake_HTKPA_DLL_RE_Stage12_v0_12.zip` delivered separately in the conversation contains a **read-only** Python `verify_stage12.py`, evidence JSON, README, and full `RESEARCH_REPORT.md`; it **excludes** the DLL, source NAM, vendor WAV/CLO and does not produce/upload any CLO.

- **35 exact DLL instruction checks**, **six pinned numerical constants**, **13 synthetic isolated-operation tests**, all passing.
- Two independent verifier runs have the same evidence JSON SHA-256: `0daec7751e318b09f178cfa1f3d457c6d82195d3b6b3f1156348b994a1c9f0d7`.
- Synthetic inverse-transform calculation agrees with `real(numpy.fft.ifft)`; this tests **the recovered equation only**, not native DLL parity or the complete transformer.

**Next DLL-first gate (Stage 13):** reconstruct transform signs, odd/even frequency folding and exact float32 intermediate buffers across `0x1800B4A50 → 0x1800B6E30 → 0x1800B4F60` to make a complete spectral-curve→Pre-FIR synthetic test. Then resume source tracing of the *separate* Post-FIR update and optimizer input curves; do not guess frequency targets or alter the production converter.

Keep the user-accepted JCM800 2203 v0.2 C as a listening control.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 13

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE13.md

# Sonicake HTKPA — Stage 13: complete algebraic spectral transform triplet

**2026-10-12 | Source-first static reverse engineering.** No Sonicake DLL execution, no new device CLO, no pedal writes, and **no changes to the production browser JS converter**.

## Scope and evidence

Windows Sonicake Manager `5868USB.dll` pinned SHA-256:
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
All listed VAs assume PE image base `0x180000000`.

Stage 12 recovered individual spectrum-processing instructions. Stage 13 resolves the **signs, normalization and odd/even pairing** across the complete call sequence
`0x1800B4A50 → 0x1800B6E30 → 0x1800B4F60`, with **41 exact instruction pins** and **111 passing synthetic math tests**. Direct slow trigonometric sums were independently compared against a NumPy FFT implementation for both parity classes. The validation is algebraic, not bit-exact native DLL output.

## Verified native formulas

`0x1800B52E0` generates sine and cosine tables for `θ_k = 2πk/N`, with imported `sin` at `0x1800B5421` (thunk `0x18017E15E`) and `cos` at `0x1800B5436` (thunk `0x18017E116`).

1. **Normalized positive-phase DFT** at `0x1800B4A50` (call `0x1800B754A`):
   `C[j] = (1/N) Σ_k x[k]·(cos(2πjk/N) + i·sin(2πjk/N))`.
   DLL proof: `0x1800B4B68` cosine products, `0x1800B4B75` sine products, `0x1800B4A87` computes `1/N`, `0x1800B4C62/0x1800B4C6D` normalize both real and imaginary.
   **Algebraic analog: `ifft(x)`**, not `fft(x)`.

2. **Conjugate cepstrum fold** at `0x1800B6E30` (call `0x1800B7569`). `P[0]=C[0]`. For all internal `1≤k<ceil(N/2)`, `P[k]=C[k]+conj(C[N-k])` (`0x1800B6EDB/0x1800B6EEB`). For even `N`, `P[N/2]=conj(C[N/2])` (real copy `0x1800B70F2`, imaginary sign change `0x1800B710C`). For odd `N=2m+1`, internal `1≤k≤m`. Unselected second-half bins are zeroed using `memset` (`0x1800B713A`), while lengths less than 3 are copied. **Odd/even behavior has separate native branches**.

3. **Unnormalized negative-phase complex DFT** at `0x1800B4F60` (call `0x1800B7590`):
   `Z[j] = Σ_k P[k]·(cos(2πjk/N) − i·sin(2πjk/N))`. Complex multiply is `(a·cos+b·sin) + i(b·cos−a·sin)`; supporting instructions include `0x1800B50E2`, `0x1800B511C`, `0x1800B5173`, `0x1800B5183`. **Algebraic analog: `fft(P)`**; no extra `1/N` at this step.

4. **Complex exponent** in `0x1800B72E0` at `0x1800B75D5/0x1800B75E1/0x1800B75F4`:
   `H[j]=exp(Re(Z[j]))·(cos(Im(Z[j]))+i·sin(Im(Z[j])))`.

Combining these with the earlier verified `−100 dB` relative floor, `log(x + 2^-23)` and exact **`N−1−i` first-half mirror**, we have a complete algebraic *equal-length nonnegative synthetic magnitude curve → complex spectrum* path with no undisclosed transform in the middle.

## Synthetic 128-tap Pre-FIR result

With an arbitrary positive curve of 128 points, Stage-11 even reflection produces 254 spectral samples. After the above transform and the already traced real inverse transform, zero-DC centering and energy normalization, the reference independently generates **128 finite taps**. One deterministic example has:

- Pre-FIR sum `−1.6653345369e−16`;
- L2 norm `0.9374846715`;
- first four taps `[0.89250108, 0.15651446, −0.06565826, −0.20002253]`.

**These are artificial test data, not a vendor or NAM model.** The 128-tap example does not establish that the unknown upstream curve or the complete numerical execution order matches Sonicake.

## Reproducibility

Private-conversation research archive `Sonicake_HTKPA_DLL_RE_Stage13_v0_13.zip` contains standalone `verify_stage13.py`, `make_example.py`, `README.md`, technical report, evidence JSON, a synthetic example JSON and plot. It excludes proprietary binaries and captured WAV/CLO.

Two independent runs against the SHA-pinned user DLL both returned:

- **41 exact machine instruction checks**
- **111 synthetic mathematical tests**
- identical evidence JSON, SHA-256 `8bfb6c6d109ee6c78b9d30c7e040fb597372845f8b1298cad33d9b07933caa3f`.

The scripts **only read the DLL** via `objdump`; no DLL execution or device interaction.

## Acceptance gate and next trace

**Achieved:** Complete algebraic spectrum-synthesis triplet with signs, parity and normalization for synthetic same-length input, validated by two independent implementations.

**Still not achieved:** Native float32/bit accuracy; native edge semantics for interpolation/negative inputs; optimizer-produced target curves through `0x1800B7670`; actual Post-FIR update; direct calculation of either official 128/2048 FIR from NAM/WAV; numerical or auditory equivalence with mobile SONICLINK.

**Stage 14 is source-first:** trace the source/meaning of the input spectral arrays used by `0x1800B7670` and identify the *separate Post-FIR writer* via `context+0x24410`, including cross-stage normalization. Only then attempt vendor-file coefficient comparison. Preserve the user-accepted JCM800 2203 v0.2 C as hardware reference; no production modifications based on this result.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 14

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE14.md

# Sonicake HTKPA Stage 14 — common Pre/Post FIR writer and Mel/dB conditioning

**2026-10-12 | source-first DLL research, not a converter change.**

All findings come from read-only static disassembly of the user-supplied Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. VAs below assume PE image base `0x180000000`. The DLL has not been executed or redistributed. No user NAM/WAV/vendor CLO or commercial code is committed; no pedal slots touched.

## Major finding: one shared synthesizer writes BOTH FIRs

The Stage 11 identified function `0x1800B68F0` is not exclusive to Pre-FIR. Within the three-selector optimizer `0x1800BB210` it is called twice:

| Purpose | Call VA | Destination | Output taps |
| --- | --- | --- | ---: |
| Pre-FIR | `0x1800BB836` | fitter stack `[rsp+0x1F8]`, i.e. `context+0x24408` | `context+0x20ED4` (128) |
| Post-FIR | `0x1800BC35C` | fitter stack `[rsp+0x200]`, i.e. `context+0x24410` | `context+0x20ED8` (2048) |

Post-FIR proof is specific: `0x1800BC33D` invokes frequency-curve conditioner `0x1800B7670`, `0x1800BC342` loads the Post-FIR pointer, `0x1800BC34D` loads its target length, `0x1800BC354` supplies the prepared curve, `0x1800BC357` supplies the destination as fifth Win64 argument, and `0x1800BC35C` calls **the same synthesizer**. The resulting Post-FIR is then used by the current-DSP rendering helper at `0x1800BC381` for another objective evaluation.

**Qualification:** a separate finishing function `0x1800B9B70` still runs at `0x1800BF11E`, after the three optimization stages. Its complete action on Post-FIR has not been reproduced. Thus the common writer is a confirmed **working**-filter path, not the complete final CLO algorithm.

## The unknown input curves have a concrete initialization

`0x1800BEF5B` and `0x1800BEF73` allocate the two correction arrays at `context+0x24328` and `context+0x24330`. The first is filled with float32 **1.0** (`0x3F800000`, `0x1800BEF97`) and copied to the second (`0x1800BEFB6..0x1800BEFC4`); **the tail of the second array is subsequently modified** in `0x1800BEFF5..0x1800BF03B`. Both arrays are copied into fitter workspaces at `0x1800BB289/0x1800BB347`. One working curve receives the bounded `powf` correction before being conditioned.

This is an initialized, iteratively adjusted correction-curve system, **not an independently inferred fixed EQ**. Further cross-spectrum feedback is computed through `0x1800B82B0` at `0x1800BC055` and `0x1800BC3C5`, and an intervening ratio/conditioning stage is visible at `0x1800BC210..0x1800BC316`. Full scratch-buffer provenance remains to be verified.

## New mathematics and purpose of `0x1800B7670`

`0x1800B7670` is a **magnitude-curve conditioner**. Its source arguments include **linear Hz frequency coordinates** (`r8`), **positive linear magnitude values** (`rdx`), source point count (`r9d`) and target count (fifth argument). It returns a target frequency grid and conditioned gain/magnitude curve. The input/output pointer roles are grounded by direct call register/stack tracing.

Confirmed native operations in order:

1. `0x1800B7771..0x1800B77D4`: transform Hz endpoints into Mel via `2595 log10(1+f/700)` and construct Mel-uniform grid; inverse map `700(10^(mel/2595)-1)` at `0x1800B7860..0x1800B78EC`.
2. `0x1800B7A95`: construct target **linearly spaced Hz** axis; output frequency-axis pointer at `0x1800B7A73`.
3. `0x1800B7B14/0x1800B7B19` and scalar `0x1800B7B75/0x1800B7B7A`: magnitude **to dB**, `20 log10(magnitude)`.
4. `0x1800B7BAB..0x1800B7BBB`: first Gaussian smoothing on the dB curve; width set to `trunc(0.002 × input_bin_count)`. Exact double constant **0.002** resides at `0x18024C640`. Do not conflate it with the smoothing width in other HTKPA functions.
5. `0x1800B7BF8`: piecewise-linear interpolation onto the Mel-spaced Hz working grid (Stage 9 function `0x1800B5D00`).
6. `0x1800B7C07..0x1800B7C12`: second Gaussian smoothing, width argument `2 × trunc(input_bin_count / target_bin_count)`. The zero-width edge case has not been independently reproduced.
7. `0x1800B7C4B` (conditional), `0x1800B7C8C`: final remappings onto target linear-Hz coordinates.
8. `0x1800B7CCE` vector and `0x1800B7D1C` scalar: return **dB to linear magnitude** via `10^(dB/20)`.

The curve may then feed the shared Stage-13 minimum-phase-like spectral FIR synthesizer `0x1800B68F0` for either 128 or 2048 taps. Source-first evidence establishes this *placement* of Gaussian operations: Stage 7's generic smoothing of the finished spectrum is **not** an implementation of this DLL path.

## Exact acceptance and limitations

Separate user-facing archive `Sonicake_HTKPA_DLL_RE_Stage14_v0_14.zip` contains a clean-room, read-only verifier and report, **50 pinned instruction addresses**, **7 embedded constants**, **16 isolated math tests**, and reproducible evidence JSON. The same SHA-pinned DLL yielded byte-identical evidence on two runs; the archive excludes the DLL and reference media. No live DLL execution.

**Still NOT achieved:** full Pre-FIR or Post-FIR coefficient parity from the reference NAM input/output WAV on either Marshall. No source-grounded complete equation for `0x1800BC055..0x1800BC33D` or the final `0x1800B9B70` post-FIR stage; full `0x1800B7670` buffer/index/float32 parity is also pending. No auditory claims, no experimental CLO and no changes to the production browser JS converter.

**Stage 15 source-first priorities:** trace every temporary in the feedback-to-Post-FIR ratio after `0x1800BC055`, validate both Gaussian passes on tiny positive synthetic arrays against the pinned native branches, and then reverse the final `0x1800B9B70` spectral correction. Only afterwards attempt two-model vendor FIR reconstruction. Retain the user-approved JCM800 2203 v0.2 C as hardware control.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 15

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE15.md

# Sonicake HTKPA Stage 15 — feedback ratio and final Post-FIR correction

**2026-10-12 · Source-first static research only. No production converter edits, DLL execution, new CLO, or device writes.**

Analyzed the user-supplied Windows Sonicake Manager `5868USB.dll` (SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`). All addresses are PE virtual addresses with image base `0x180000000`. The proprietary DLL and corresponding NAM/WAV/CLO captures are **not redistributed or committed**.

This stage addresses the two explicit Stage 14 unknown blocks: `0x1800BC055→0x1800BC33D` and final `0x1800B9B70`.

## 1. Cross-spectral feedback: regularized quotient and working Post-FIR synthesis

The optimizer at `0x1800BC055` invokes the previously traced cross-spectral evaluator `0x1800B82B0`. A vectorized double-precision path (`0x1800BC10D/0x1800BC114/0x1800BC118/0x1800BC11C`) and scalar equivalent (`0x1800BC222/0x1800BC226/0x1800BC22A/0x1800BC22F`) compute the following *local* quotient, storing float32:

```
Q[i] = float32(1_000_000.0 * float32(A[i]) /
               (1_000_000.0 * float32(B[i]) + 2**-23))
```

The multiplier `1000000.0` and epsilon `2^-23` are **double** constants at `0x18024D5A0` and `0x18024D1E0`, respectively. The effective unscaled denominator epsilon is approximately `1.19209e-13`. This is **not** the Stage 7 experiment's arbitrary adaptive Welch estimator regularizer.

The quotient output is passed through the source-confirmed Mel/dB/Gaussian curve conditioner `0x1800B7670` at `0x1800BC33D`, then the shared minimum-phase-like `0x1800B68F0` at `0x1800BC35C`, with destination `context+0x24410` (working **Post-FIR**) and the correct 2048 target length.

**Precision boundary:** The arithmetic and several source/destination pointers are directly established. Exact origin and aliasing of **every** intermediate scratch array `A/B` and the full pre/post update equation are not yet recovered. Naming A and B does not identify them with raw STFT power arrays in isolation.

## 2. Once-only final Post-FIR spectral correction

After three calls to the main fitter, `0x1800BF100` passes `context+0x24410` and `0x1800BF11E` calls `0x1800B9B70`.

The finalizer:

1. Uses a support of `ceil(0.1*sample_rate)` (`0x1800B9BCB–0x1800B9BD5`) — 4800 samples at 48 kHz.
2. Builds rendered/reference audio spectra, using two transforms (`0x1800BA8A3`, `0x1800BA8BB`) and `sqrtf(re²+im²)` (`0x1800BA97B`). The complete upstream complex-array orientation is not yet byte-exact.
3. Forms the same class of `1e6 * numerator/(1e6 * denominator+2^-23)` ratio (`0x1800BAC70–0x1800BAD2E`), clamps it to **[0.1, 10]** (`0x1800BAEB3/0x1800BAEC6`), and Gaussian smooths via `0x1800B7E10` (`0x1800BAEF9`).
4. Calls `0x1800B65A0` at `0x1800BAF88` to create and apply a **256-tap corrective filter to the existing Post-FIR**.
5. Rerenders audio through the corrected Post-FIR (`0x1800BAFAB`) and obtains a **ratio of square-root summed energies** (`0x1800BB0C0/0x1800BB0CB/0x1800BB0E2`). It multiplies the Post-FIR by that factor (`0x1800BB12F`).

## 3. Exact structure of `0x1800B65A0`: causal convolution, cropping and DC subtraction

- Allocates two **256-float** scratch arrays (`0x1800B65B8/0x1800B65CC`).
- Conditions the transfer curve to 256 bins (`0x1800B65FD`) and synthesizes a **256-tap FIR** via `0x1800B68F0` (`0x1800B6621`).
- Allocates `PostFirLength + 255` floats, initializes them to zero and performs a nested multiplication/accumulation loop (`0x1800B6690–0x1800B675D`) consisting of **256 inner taps per old Post-FIR tap**.
- Copies **only the first PostFirLength** convolution outputs back into the existing Post-FIR (`0x1800B6771`) and subtracts their mean (`0x1800B67EA/0x1800B682B/0x1800B68B0`).

Independent *algebraic* model for normal non-degenerate arrays:

```python
corrector = synthesize_256(conditioned_spectral_curve)
full = causal_convolution(working_post_fir, corrector)
working_post_fir[:] = full[:len(working_post_fir)]
working_post_fir -= mean(working_post_fir)
# Outer function subsequently applies energy ratio
```

This is **not** a direct 2048-tap recomputation: it corrects the already fitted filter by convolution, and then output-energy calibration. Exact float32 summation order and all native edge cases remain unverified.

## Independent file consistency check (not parameter fitting)

The user-provided official Windows Manager CLOs have **near-zero** sums of their 2048 Post-FIR coefficients, consistent with the identified DC subtraction prior to 48k→44.1k conversion:

| Model | Official Post-FIR sum | L2 norm |
|---|---:|---:|
| JCM800 2203 Crunch | 0.002959 | 1.170528 |
| JCM800 SC20 Full Rig | 0.006035 | 1.922987 |

## Verification and original acceptance gate

The separately supplied `Sonicake_HTKPA_DLL_RE_Stage15_v0_15.zip` includes independently authored `verify_stage15.py`, this stage's full research report, README and JSON evidence. The verifier statically checks **46 exact machine-code addresses, eight binary constants, and 13 synthetic mathematical tests** covering regularized quotient, causal/truncated convolution, DC and energy gain. Two runs yield identical JSON: SHA-256 `5c5f236c0bc6ec5fad5b9e6418d36aafa00b7845c05c4070faeddc3d6c7c4802`. Zip integrity passed.

**Two Stage 14 blocks now have verified core operations and data flow, but the original strict objective — calculating official 128-tap Pre-FIR / 2048-tap Post-FIR from only the NAM and probe WAV, with numerical coefficient parity — is STILL NOT MET.** In particular, optimizer `0x1800BB210` scratch-buffer provenance / three-stage update, entire native DSP fit loop, transform numeric parity and exact rate conversion remain unfinished.

**Next source-first gate:** full register/stack SSA of `0x1800BB210` covering the `2→1→3` loops and `0x1800BC055` feedback buffer identities, then a self-contained synthetic input-to-working-Pre/Post-fit test, and *only then* a two-model coefficient match. No guess-based CLO production or unconditional +gain/brightness.

Keep the user-auditioned JCM800 2203 v0.2 C as hardware control. Mobile SONICLINK vs Windows Manager exact parity remains unproven.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 16

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE16.md

# Sonicake HTKPA Stage 16 — source-proven iteration workspace and feedback aliasing

**2026-10-12.** This is a static, read-only reverse engineering result from the **user-provided** Windows Sonicake Manager `5868USB.dll` (SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`). The DLL was never executed, nor is it distributed in this repository. **No production JS changes, new CLO or pedal writes.**

## Main new result

The optimizer `0x1800BB210` allocates **one contiguous float32 block** for its curves, temporary audio, backup FIR coefficients, and iteration scores. The byte allocation follows:

`4 * (10*L + 2*P + Q + T + I)`

where `L` is the working-curve length (derived from `context+0x20ecc`); `P=context+0x20ed4` is the Pre-FIR tap count; `Q=context+0x20ed8` is the Post-FIR tap count; `T` is the current audio sample count; and `I` is the optimizer iteration count. **Do not confuse L with the separate 512 Mel-spaced score queries.**

All offsets below are **relative float32 element offsets** from the allocation base `B`:

| Scratch segment | Offset | Machine-code origin / role |
| --- | --- | --- |
| `V0` | `0` | copied from `context+0x24328`, then modified by bounded power iteration |
| `V1` | `L` | copied from `context+0x24330` |
| `V2` | `2L` | copy of `V0`, working product, denominator and in-place destination of subsequent spectral feedback |
| `V3,V4,V5,V6,V7,V8` | `3L,4L,5L,6L,7L,8L` | temporary curve and spectrum buffers; importantly `V5` is the quotient's numerator source |
| `V9` | `9L` | copy of `V0`; part of candidate save/restore |
| Pre curve temporary | `10L` | `P` floats; synthesis input |
| Saved Pre-FIR | `10L+P` | `P` floats, saved/restored with optimizer decisions |
| Saved Post-FIR | `10L+2P` | `Q` floats, saved/restored with optimizer decisions |
| Rendered audio | `10L+2P+Q` | `T` floats; current-DSP output `r15` |
| Per-iteration score | `10L+2P+Q+T` | `I` floats |

Allocator and pointer pins: `0x1800BB255–0x1800BB33D`; context copy operations `0x1800BB342/0x1800BB347/0x1800BB35A/0x1800BB368`.

## Exact quotient-buffer provenance — Stage 15 refinement

The first spectral evaluator is called at `0x1800BC055`, writing through a `V5` output argument prepared at `0x1800BC01D/0x1800BC038`. The numerator reads are from `V5` (`0x1800BC081/0x1800BC0F3`). The denominator reads are from **`V2`** (`0x1800BC093/0x1800BC107`), and `0x1800BC12E` writes the resulting quotient **back into V2**. The scalar tail `0x1800BC210–0x1800BC316` agrees:

```text
V2[k] = float32(1e6*float32(V5[k]) /
                (1e6*float32(V2[k]) + 2^-23))
```

The `V2` denominator **is not simply the raw auto-spectrum of the generated audio**; `V2` began as a copy of `V0` and was subsequently transformed/elementwise-multiplied at `0x1800BB575`. The resulting quotient is then passed to `0x1800B7670` (`0x1800BC33D`) before the common Post-FIR synthesizer `0x1800B68F0` (`0x1800BC35C`). This resolves an important pointer-level ambiguity without inventing its physical DSP meaning.

## Confirmed order within one iteration

Bounded power and annealing (`0x1800BB460..0x1800BB4BE`) → three separate Mel/dB conditioning calls (`0x1800BB4D9/0x1800BB4F8/0x1800BB812`) and intermediate elementwise products/divisions (`0x1800BB575/0x1800BB6E1`) including auxiliary conditioning `0x1800B6220` → **Pre-FIR synthesis** (`0x1800BB836`) → render/saturate and spectrum evaluate (`0x1800BBB5B/0x1800BBCC9/0x1800BC055`) → quotient `V5/V2` → **Post-FIR synthesis** (`0x1800BC35C`) → second render/spectrum evaluation (`0x1800BC381/0x1800BC3C5`) → Mel score interpolation and `mean(abs(logf(v+2^-23)))` (`0x1800BC3F9..0x1800BC440`) → save/restore with `1.2×` threshold and `0.5×` step reduction (`0x1800BC459..0x1800BC5A9`).

At outer level, this executes three selectors `2→1→3` with counts `3→2→5` (proven in Stage 8), then exactly one final `0x1800B9B70` Post-FIR correction. The previous hardware-positive **JCM800 2203 v0.2 C** remains the control.

## Reproducibility and acceptance

A separate conversation artifact `Sonicake_HTKPA_DLL_RE_Stage16_v0_16.zip` includes independent read-only `verify_stage16.py`, full `RESEARCH_REPORT.md`, `README.md` and `evidence.json`. **74 exact instruction pins, 9 numeric constants and 22 structural/algebraic tests passed**, with two runs producing identical evidence JSON SHA-256 `bc778ec7ca5092b62f9f11a06a809821154fa289a9aa33d6fbb7ac22c39e5280`. It does not contain the DLL, user's audio/NAM, vendor CLO or full disassembly.

**Original acceptance gate is STILL NOT MET.** While memory provenance and the control-flow skeleton are now confirmed, native edge/alias semantics of the three conditioner calls and `0x1800B6220`, integrated rendering/STFT float32 equivalence, cross-selector state and final resampling all require more work before an independent **exact** vendor Pre-FIR/Post-FIR can be derived from the NAM/probe. No guessed fitting constants or production changes should be introduced until those blocks have source-grounded numerical tests.


## Stage 17 correction (2026-10-12): vector multiplication is NOT stored in V2

The Stage-16 prose descriptions `V2[k] ← V2[k] × V0[k]`, `V2 was ... altered by ... 0x1800BB575`, and the scratch-loop pseudocode `V2[k] ← V2[k] * V0[k]` are **incorrect**. Full Win64 caller-to-callee stack tracing shows that `0x1800BB575` writes to the **second caller-owned array**, outer `r12`, located in callee `r13=[rsp+0x1E8]`. The other vector operation at `0x1800BB6E1` writes to **the first caller-owned array**, outer `r15`, accessed through callee `rdi=[rsp+0x1E0]`. Both use the second conditioner output `V0`:

```text
outer_r12[k] *= V0[k]          # actual destination at 0x1800BB578
outer_r15[k] /= V0[k]          # actual destination at 0x1800BB6E9
0x1800B6220(outer_r15, L)   # in-place low-index geometric conditioning
```

The local `V2` scratch is still involved in the **separate** regularized feedback quotient `V2 ← 1e6*V5/(1e6*V2+2^-23)`, correctly identified later in this Stage-16 report. The two caller arrays are allocated once by the enclosing native function before all three selector calls, so the correction changes inter-pass state. See [Stage 17](NAM_CLO_HTKPA_DLL_RE_STAGE17.md) for pinned instructions, full operand-register proof and a tested isolated helper. This erratum is intentionally appended rather than silently rewriting historical observations.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 17

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE17.md

# HTKPA Stage 17 — caller-buffer alias correction and source-verified auxiliary conditioner

**Date:** 2026-10-12. **Method:** static disassembly of the original user-supplied Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. No DLL execution, pedal operations, new CLO or production converter edits.

## Important Stage-16 erratum

Stage 16 misassigned the vector multiplication at `0x1800BB575` to local scratch `V2`. Full caller/callee Win64 stack tracing proves otherwise. The outer `0x1800BE830` allocates three arrays (outer `r15` at `0x1800BEE33`, `r12` at `0x1800BEE3F`, `r13` at `0x1800BEE4B`) before the three fitting calls. It passes them at caller stack `+0x40/+0x48/+0x50`, corresponding to callee `[rsp+0x1E0]/[rsp+0x1E8]/[rsp+0x1F0]` (accounting for the 8-byte return address, eight register pushes, and `0x158` frame bytes).

After initial curve-conditioning calls `0x1800BB4D9` and `0x1800BB4F8`, which write local `V2` then `V0` respectively, the **native vector instructions actually perform**:

```text
outer_r12[k] = float32(outer_r12[k] * V0[k])   # 0x1800BB575, stores at 0x1800BB578
outer_r15[k] = float32(outer_r15[k] / V0[k])   # 0x1800BB6E1, stores at 0x1800BB6E9
```

The subsequent `0x1800B6220` (call at `0x1800BB7E3`) modifies **outer_r15**. This updates caller-owned arrays carried between selectors **2→1→3**. It is incorrect to silently substitute a local scratch update. `V2` remains the correct **destination of the separate later feedback quotient**, as proven in Stage 16.

## Newly decoded `0x1800B6220`

The source-defined length of the low-index modifier is computed from the current audio sample rate `Fs` and spectral curve width `L`. Native context initialization at `0x1800B5865..0x1800B5887` stores `0.5*Fs` and its reciprocal at `context+0x20EC4/0x20EC8`. A fixed **60.0f** (`0x18024CD60`) is passed at the call site `0x1800BB7D2`.

```text
K = trunc(sqrtf(float32(float32(60.0f * (1.0f/(0.5f*Fs))) * float32(L))))
```

For regular positive finite arrays and `1 < K < L`, exact source-derived operation order is:

```python
a[0] = sqrtf(a[0] * sqrtf(a[0] * a[1]))
for i in range(1,K):
    a[i] = sqrtf(a[i] * sqrtf(a[i-1] * a[i+1]))
```

**All reads are in-place:** `a[i-1]` uses its *updated* value and `a[K]` is read as a lookahead. For `K<=1`, the DLL skips processing; unproven negative/NaN/`K>=L` cases are not guessed. `sqrtf` thunk `0x18017E170` resolves via imported `api-ms-win-crt-math-l1-1-0.dll` to `sqrtf` at IAT `0x18018BA38`.

Examples derived from the formula, **not claims about actual HTKPA L**: Fs=48k and L=1000 gives K=1; L=2500 gives K=2; L=10000 gives K=5. The 512-point Mel evaluation grid is a separate array and **must not be confused with L**.

This precisely closes one earlier unknown helper, without inventing the missing full curve conditioning.

## What Stage 17 actually tested

Standalone Python verifier `stage17_source_first.py` matches **64 exact native instruction addresses**, **5 binary constants**, and passes **23 synthetic math/alias tests**. Two independent runs of the verifier produced identical JSON evidence SHA-256 `9b0220696c674bca8a496d19a191a3e085bc352f886d882055baee5d57fd241b`. It uses `objdump` to read the file, **never loads or executes it**.

A separate **read-only two-model coefficient-parity gate** `vendor_parity_gate.py` checks VTSI length, CRC16-Modbus, pinned original Windows Manager SHA-256 and Pre/Post-FIR layout:

| Model | Official reference SHA-256 | Official pre sum | Official post sum | Independent synthesized candidate |
|---|---|---:|---:|---|
| JCM800 2203 Crunch | `50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7` | 0.014214 | 0.002959 | **not yet available** |
| JCM800 SC20 Full Rig | `2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a` | 0.005175 | 0.006035 | **not yet available** |

The gate therefore reports **`NOT_TESTED` for both exact coefficient comparisons**. It will measure max absolute error, relative L2 error, cosine similarity, and exact float32 equality separately for 128 Pre and 2048 Post taps, **only after an independently computed candidate exists**. It never uses vendor coefficients as fitter targets. Reference proprietary files are not distributed.

## Exact remaining blockers

The explicitly requested **complete single-pass native-equivalent fit, the combined 3→2→5 iteration schedule and exact coefficient parity with both Windows Manager CLOs are NOT achieved**. In particular:

- Initial shared caller arrays are prepared by **`0x1800BC6B0`**, still to be independently reconstructed.
- All buffer aliases, special Gaussian edge cases, knot ordering and float32 arithmetic of the three **`0x1800B7670`** frequency-conditioning calls have not been reproduced together on a native-equivalent synthetic input.
- Native DSP render, cross-spectrum normalization, score/rollback state transitions and 48→44.1-kHz tap rate conversion are not yet validated end-to-end.
- Windows Manager vs mobile SONICLINK identity remains unproven.

**Next Stage 18:** source-first reconstruct `0x1800BC6B0` and exact bounded `0x1800B7670` synthetic return arrays. Connect these to the now proven caller-array mutations and low-index conditioning, then proceed to the first whole Pre-FIR candidate. Do **not** introduce a guessed conditioner or false “bit-exact” assertions.

The self-contained user research ZIP `Sonicake_HTKPA_DLL_RE_Stage17_v0_17.zip` contains only new Python source, report, README and evidence; no original DLL, proprietary NAM/audio, or CLO. Existing user-auditioned JCM800 2203 v0.2 C remains untouched; production browser JS unchanged.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 18

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE18.md

# Sonicake HTKPA Stage 18 — source-derived initial spectral curves and B7670 conditioner

**2026-10-12 · Source-first, read-only research · No device/production changes.**

Analyzed user's Windows Sonicake Manager `5868USB.dll`, pinned SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. The commercial DLL was never executed, modified or committed. A separate research ZIP **`Sonicake_HTKPA_DLL_RE_Stage18_v0_18.zip`** is available in the originating conversation; it bundles `stage18_source_first.py`, `demo_stage18.py`, evidence JSON, detailed report and README — no DLL/NAM/WAV/CLO files.

## Source correction: `0x1800BC6B0` is NOT a trivial fixed-curve initializer

Stage 17 correctly located the call, but underestimated the audio preprocessing it performs. The outer fit driver `0x1800BE830`:

1. Calls audio-preprocess helper `0x1800BD490` at `0x1800BEE25`.
2. Allocates persistent caller-owned correction arrays **A, B, F** at `0x1800BEE33/0x1800BEE3F/0x1800BEE4B`.
3. Passes their pointers via outgoing Win64 stack slots and calls `0x1800BC6B0` at `0x1800BEE89` **before** the selectors `2→1→3`.

The latter function **prepares the initial A/B spectral curves from the audio**, not by filling fixed arrays. Observed native operations include sample-rate-specific coefficient-table selection (`0x1800BC753..0x1800BC940`), a 50-point helper call to `0x1800B5A30` (`0x1800BC96D`), two recursive second-order filters, `0x1800BE700` nonlinear processing (`0x1800BCC79`), and cross-spectral analysis `0x1800B82B0` (`0x1800BCFF2`).

**Do not mistake this for a standalone spectrum-vs-spectrum initialization.** Full real-WAV reproduction still requires independently implementing its two audio-preprocess paths and the exact FFT/STFT buffers.

## New exact tail formulas and proven call order

`0x1800BD01F` and `0x1800BD03D` call Gaussian `0x1800B7E10` in succession with widths `trunc(0.001*N)` and `trunc(0.005*N)`, where N is the spectral curve's native length. Pinned doubles: `0x18024C618 = 0.001`, `0x18024C688 = 0.005`.

After the Gaussian passes, the DLL computes a **quadratic soft floor** on working B:

```text
T     = float32(max(auxiliary_U) * 0.001)
limit = float32(2*T)
alpha = float32((limit-T)/(limit*limit))

B[k] = float32(T + alpha*B_raw[k]*B_raw[k])  if B_raw[k] < limit
       B_raw[k]                              otherwise

A[k] = float32((1e6*float64(U[k])) / (1e6*float64(B[k]) + 2^-23))
```

Native proof of floor and compare: `0x1800BD0B7..0x1800BD119`; ratio: `0x1800BD230..0x1800BD2E5` and scalar `0x1800BD350..0x1800BD441`. Pinned constants `1e6` at `0x18024CD28`, epsilon `2^-23` at `0x18024C588`. The parabola joins the unchanged branch at `2T` with both *value* and *first derivative* continuous, for T>0. Its scalar formula, source-ordered float32 approximations and branch conditions have independent tests.

The **physical meaning of U's exact audio-derived buffer is not fully reconstructed**; it is wrong to assume that it is a raw Welch power spectrum merely because it feeds the floor. The original source WAV and reference audio have not yet been converted into the native U/B spectrum arrays by this prototype.

## Implemented ordinary-domain `0x1800B7670`

`conditioned_curve(freq,mag,m)` now executes the **complete source-grounded sequence of stages** for finite positive magnitude gains and strictly increasing frequency coordinates, source length `N>=501`, `2<=m<=N`:

- 2595·log10(1+Hz/700) **Mel endpoint conversion**, Mel linspace of N and m coordinates and inverse mapping to Hz;
- separate float32 repeated-addition `0x180027DB0` linear-Hz output grid, enforcing exact last endpoint;
- gain to `20log10(gain)` in dB;
- first Gaussian, width `trunc(0.002*N)`;
- **interpolate source Hz→N Mel-spaced Hz** with `0x1800B5D00`;
- second Gaussian, width `2*trunc(N/m)`;
- **interpolate N Mel→m Mel** (skip when equal);
- **interpolate m Mel-spaced Hz→m linear Hz** and convert back `10**(dB/20)`.

Proof of three conditional interpolators: `0x1800B7BF8/0x1800B7C4B/0x1800B7C8C`; two Gaussian calls: `0x1800B7BBB/0x1800B7C12`; final gain: `0x1800B7D1C`. Gaussian `0x1800B7E10` uses native-shaped, double-precision, reversed window coefficients and cropped-boundary normalization; window width<=0 remains deliberately rejected. **This is algebraic and synthetic domain parity, not bit-identical Windows CRT/SSE execution.**

The native `0x180027DB0` **repeated-addition** linspace implementation is included rather than silently using a generic NumPy linspace. Native interpolation undefined/nonmonotone/duplicate-knot variants remain excluded. No guessed regularization, generic SciPy smoothing or vendor CLO coefficients were used.

## Test facts and demonstration

The standalone read-only verifier passed:

| Gate | Verified |
|---|---:|
| Exact DLL address/instruction pins | **59 / 59** |
| Exact PE numerical constants | **12 / 12** |
| Synthetic algebraic/structural tests | **49 / 49** |
| Two independent evidence JSON runs | **Byte-identical** |

Evidence SHA-256 `c334edaaede0db5200c6d60b8010e10519028ee3261729190861dc6dea7c1775`.

Synthetic fixture: **2401 source frequency bins**, two intentionally artificial positive curves. Two Gaussian initialization passes give widths **2,12**. Source-conditioned A and B can be mapped to **128-point** and **2048-point** spectra; for the conditioner itself, widths are respectively **4,36** and **4,2**. Both outputs are finite, positive, and preserve the expected Hz range. **These are not FIR taps, not output audio, and not a new CLO.**

## Remaining source-first blockers

**Vendor coefficient parity remains `NOT_TESTED` for both 2203 and SC20** because no independently derived real-NAM FIR candidate was generated. The core remaining native path is the audio preprocessing of `0x1800BD490` and `0x1800BC6B0` including the sample-rate-specific second-order sections, output of `0x1800BE700`, and spectral output mapping of `0x1800B82B0`, followed by end-to-end exact numeric fits and the final 44.1-kHz serialization. A complete 3-pass converter is NOT established.

**Stage 19:** reverse these exact audio/preprocessing/STFT buffers first, produce independently generated **initial A/B curves from the original user probe WAV**, and then connect to the known fitter skeleton. Only compare produced FIRs with official 2203/SC20 as a held-out oracle; no guessing missing math from the vendor target.

Keep existing hardware-auditioned JCM800 2203 v0.2 C and production PocketMasterStudio JS converter untouched. Windows Manager vs mobile SONICLINK identity is still unproven.



---

## COMPLETE PRIMARY SOURCE REPORT — Stage 19

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE19.md

# Sonicake HTKPA Stage 19 — source-pinned 50-tap audio-preprocessing FIR and real WAV gate

**2026-10-12. STRICT STATUS: original initial A/B from real WAV still NOT COMPUTED.** This stage makes a verified upstream checkpoint, not a complete NAM→CLO implementation. No production JS, experimental CLO, or pedal writes.

Source: the user-supplied Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. DLL examined statically only with Python PE section parsing and `objdump`, never executed or redistributed.

## Actual recovered native 50-coefficient input FIR

At `0x1800BC739`, `0x1800BC7EF`, and `0x1800BC89E`, `0x1800BC6B0` selects three **different, hard-coded float32 50-tap coefficient banks** by native sample rate **44,100 / 48,000 / 96,000 Hz**. Branch starts are `0x1800BC753`, `0x1800BC802`, and `0x1800BC8B1`. For each branch, the DLL loads exactly **twelve 4-float SSE vectors plus two scalar floats** into one contiguous 50-element stack array.

At `0x1800BC94D` this array is passed as the second argument; `0x1800BC95A` sets the coefficient count to `0x32` (50), and `0x1800BC96D` invokes **`0x1800B5A30`**, the partitioned-convolution helper, to process source audio. Its body uses `0x1800C0F60` with 64-sample blocks. The complete float32 partition/rounding implementation is not yet rebuilt, so a simple reference causal FIR convolution must **not** be called bit-exact vendor processing.

The three actual PE tables are independently decoded in the Stage-19 research script; there are **70 exact address/operand pins**, comprising 42 original PE-source coefficient-reference instructions and 28 call/dataflow control pins. Source-derived table diagnostics (not fitted):

| Native branch | first three coefficients | sum | L2 norm |
| --- | --- | ---: | ---: |
| 44.1 kHz | 2.368210, 3.574280, 3.095710 | −0.0868914 | 7.695335 |
| 48 kHz | 2.369809, 3.532199, 3.386006 | −0.0252041 | 8.024002 |
| 96 kHz | 2.369809, 3.144882, 3.532199 | −0.9660231 | 11.273363 |

The proprietary coefficient arrays are **not committed**. The user can reextract and verify them from the original local SHA-pinned DLL.

## Real-WAV input audit

Two independent user-captured official Manager sessions were read, **not fitted**:

| Model | Input DI WAV | Reference output WAV |
| --- | --- | --- |
| JCM800 2203 Crunch | 70 seconds stereo PCM16, 44.1 kHz | 70 seconds stereo PCM16, 48 kHz |
| SC20 Full Rig | 70 seconds stereo PCM16, 44.1 kHz | 70 seconds stereo PCM16, 48 kHz |

Both input DI WAVs are **byte-identical**, SHA-256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`. Both channel pairs are identical, but the output WAVs differ (2203 RMS ≈0.03403, SC20 RMS ≈0.01028).

A **separate mathematical audit**, not a claim about the complete native preprocessing, applies the DLL-derived **44.1-kHz 50-tap FIR** by simple causal convolution to the actual unresampled 44.1-kHz DI. Its RMS is ≈**0.82734** and peak ≈**8.962** before IIR/nonlinear processing. This must **not** be compared as a vendor sound output, since the actual HTKPA 44.1→48-kHz input conditioning, subsequent gain mapping and further DSP stages have not been implemented. The evidence records only hashes, RMS, peaks, four section measurements and eight example float32 output samples, never full input WAV data. Vendor Pre/Post FIR coefficient arrays were not accessed for fitting.

## Two additional tracing results

After the native 50-tap input FIR, `0x1800BC6B0` executes first and second recursive second-order sections bracketing `0x1800BE700` (the known four-parameter nonlinear saturator), then spectral analyzer `0x1800B82B0`, after which Stage 18's two Gaussians / quadratic spectral floor / A/B quotient become applicable.

For the sections, state buffers and coefficient pointers are confirmed: `context+0x20/+0x28/+0x30` with `context+0x232D8..0x232F8`, and `context+0x20C98/+0x20CA0/+0x20CA8` with `context+0x23300..0x23320`. The **actual coefficient constructor** was located at `0x1800BFF17..0x1800C0216`, with selection into live filter fields at `0x1800BEC36..0x1800BED00`. These source-specific coefficients and native numerical behavior are not yet reproduced.

**Stage-10 correction:** `0x1800B8373` uses `r14d` as the STFT analysis window length; `0x1800B83EA–0x1800B83FB` computes **`trunc(0.5 × window_length_samples)`** as the hop. It is a **50% window hop**, **not a fixed half-second hop** as the old report mistakenly stated. An explicit erratum has been added to [Stage 10](NAM_CLO_HTKPA_DLL_RE_STAGE10.md).

## Verification and strict acceptance gate

Separate user-facing package `Sonicake_HTKPA_DLL_RE_Stage19_v0_19.zip` contains `stage19_source_first.py`, **12 successful independent tests**, full `RESEARCH_REPORT.md`, `evidence.json`, `plot_stage19.py`, figure of the three extracted frequency responses, and README. **70 pinned native instructions and all three coefficient banks pass.** Source-side code reads the local DLL as bytes and never executes it. ZIP integrity checked; no proprietary DLL, capture media or commercial CLO in the archive.

**Still not achieved:** initial real-WAV **A/B arrays**, full optimizer 2→1→3, or coefficient comparison of new independent vendor Pre/Post FIR. The gate remains `NOT_COMPUTED` for A/B and `NOT_TESTED` for official FIR parity — no CLO emitted. Next source-first steps must reproduce the **biquad coefficient constructor**, the four-gain audio fitting procedure `0x1800BDBE0`, native resampling/alignment and the STFT buffer conventions in `0x1800B82B0`, then connect to the working Stage-18 A/B function. Do **not** substitute a generic Welch fit or secretly use official CLO coefficients as fit targets.

The user-auditioned JCM800 2203 v0.2 C and production PocketMasterStudio Void Mod converter remain unchanged.


## Stage 20 IIR correction — coefficient count, native cutoffs and live selectors (2026-10-12)

Stage 19's phrase *"six consecutive double coefficients"* (and any implication of two *non-neutral* biquads) was too broad. Static source trace of `0x1800BD490` proves exactly **five** doubles per section: `[b0,b1,b2,a1,a2]`, with live offsets `context+0x232D8…0x232F8` (first) and `+0x23300…0x23320` (second). The native context initializer sets two alternative filter banks to identity `[1,0,0,0,0]`. The sample-rate constructor `0x1800BFF17–0x1800C0216` computes two **other**, non-identity banks, whose measured *discrete* −3 dB cutoff frequencies are **approximately 40 and 20 Hz**, not 20 and 10 Hz. In the traced native selection modes, the **first IIR section is neutral** and the second is either neutral or the 40/20-Hz section. Mode-2's branch exists but its reachability during normal NAM conversion is not shown.

The independent Stage-20 bounded SSE interpreter reproduces all **ten native context coefficient stores** for 44.1/48/96 kHz; 106 isolated tests pass. See [Stage 20](NAM_CLO_HTKPA_DLL_RE_STAGE20.md) for code proof, coefficient table, sample-rounding rules and strict non-parity caveats. The remaining four-gain saturator fitting and real-WAV A/B generation are **NOT COMPUTED**.




---

## COMPLETE PRIMARY SOURCE REPORT — Stage 20

Source: https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/NAM_CLO_HTKPA_DLL_RE_STAGE20.md

# Sonicake HTKPA Stage 20 — DLL-derived IIR coefficient constructor

**2026-10-12 | Static source-first research.** No proprietary DLL execution, no device changes, no new CLO, and no production JS modification.

Pinned Windows Sonicake Manager `5868USB.dll` SHA-256:
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
Base VA `0x180000000`.

## What is proven

The actual IIR audio section in `0x1800BD490` is **five** double-precision coefficients, not six: `[b0,b1,b2,a1,a2]`. Loads are pinned at `0x1800BD599`, `0x1800BD591`, `0x1800BD5A1`, `0x1800BD564`, `0x1800BD56F`. Each section uses:

```
w[n] = (1000*float64(input_f32[n]) - a2*w[n-2]) - a1*w[n-1]
m[n] = float32((b1*w[n-1] + b2*w[n-2]) + b0*w[n])
y[n] = float32(float64(m[n])*0.001)
```

The native context constructor `0x1800C04B0` initializes two 5-double banks `context+0x24338` and `context+0x24360` to **[1,0,0,0,0] (identity)**, and two other banks near 44.1-kHz high-pass coefficients. The later sample-rate dependent initializer `0x1800BFF17…0x1800C0216` dynamically replaces the latter two banks (`+0x24388`, `+0x243B0`) using its `float32(Fs)` value at `context+0x20EC0`. There are **ten direct context double writes and five global double writes**.

A standalone Python **interpreter of exactly 152 SSE/scalar instructions** (not a DLL loader) reads the same PE constant bytes and reconstructs the ten native context values at Fs 44,100, 48,000 and 96,000 Hz, including `float32` intermediates, sign-mask `xorps`, and `cvtps2pd` / `cvtss2sd` conversion. The 44.1-kHz emulated coefficients agree with the separate hard-coded default initializer to within `1.07×10⁻⁷` in absolute error.

### Numeric coefficient proof, Fs 48,000 Hz

| Source bank | b0 | b1 | b2 | a1 | a2 | Measured digital −3 dB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `0x24388` | 0.996304393 | −1.992608786 | 0.996304393 | −1.992595077 | 0.992622495 | ≈40 Hz |
| `0x243B0` | 0.998150527 | −1.996301055 | 0.998150527 | −1.996297717 | 0.996304393 | ≈20 Hz |

**Important frequency caveat:** Native analog-like PE constants suggest 20/10-Hz design parameters, but the constructor divides by expressions based on **Fs** rather than `2*Fs`. The actual discrete transfer cutoffs are therefore about 40 and 20 Hz. A SciPy `freqz` computation on the independently emulated coefficients verifies this at all three supported rates.

### Live IIR mode selection

Function `0x1800BEC2B–0x1800BED11` copies bank pointers into the two live sections:

| mode (`context+0x232D0`) | first live FIR/IIR section | second section |
|---:|---|---|
| 0 | `+0x24360` (identity) | `+0x24360` (identity) |
| 1 | `+0x24338` (identity) | `+0x24388` (≈40 Hz HP) |
| 2 | `+0x24338` (identity) | `+0x243B0` (≈20 Hz HP) |

Selector instruction pins `0x1800BEC36/0x1800BEC59/0x1800BEC8F/0x1800BECB7/0x1800BECDF`. The **actual mode assignment within the earlier path sets 0 or 1** using `context+0x4`. Mode 2 has a handler but its regular NAM conversion reachability is **not proven**. The first section is identity for the observed branches; it is wrong to assume *two active frequency-altering IIRs*.

## Adjacent saturator-fitting function: narrower proven findings

`0x1800BDBE0` uses a 0.1-second block-size factor (`Fs × 0.1`, PE double `0x18024C7A0`) to prepare audio envelope groups. The two scalar optimization sweeps in `0x1800BE480…0x1800BE63E` use the sign-separated exponential model (`expf` imports at `0x1800BE4BA/0x1800BE4D5/0x1800BE5AE/0x1800BE5C9`) and source-pinned candidate multiplier `0.8f`, addition by `0.05`, upper bound `1.2`. Four resulting `float32` values are written at `0x1800BE661/0x1800BE676/0x1800BE682/0x1800BE68F`. This is **not** a complete reimplementation of the four-parameter optimizer: exact envelope extraction, fit initialization, numerical tie-breaking and real fitted values remain unresolved.

## Reproducibility and original acceptance gate

Research-only ZIP `Sonicake_HTKPA_DLL_RE_Stage20_v0_20.zip` delivered in the originating conversation bundles `stage20_iir_source.py`, `test_stage20.py`, `RESEARCH_REPORT.md`, `README.md`, `test_stdout.txt`, `evidence.json`. It contains no vendor DLL, proprietary media or CLO. **106 individual assertions pass**, and two independent evidence runs are byte-identical (SHA-256 `ad19bd408c788f80f90cf140899c56e6ce5e6db6cf884e2627fefc11500226d0`). The source never loads or executes the DLL; it reads PE bytes and tests independent Python math.

**Still NOT achieved:** complete four nonlinear gains from the reference WAV; initial vendor A/B curves; real-WAV native-signal-path equivalence; independently reconstructed official 128/2048 FIR and heldout equality on both Marshall 2203 and SC20. All retain statuses **NOT_COMPUTED** / **NOT_TESTED**. No hardware operation, product conversion or production source modification.

**Next Stage 21:** source-first complete `0x1800BDBE0` saturation parameter optimizer, then native audio preprocessing and `0x1800B82B0` STFT alignment to form genuine initial A/B curves. Avoid inserting defaults from official CLO or arbitrary numerical fitting. Keep the user-auditioned 2203 v0.2 C as reference.

Historical [Stage 19](NAM_CLO_HTKPA_DLL_RE_STAGE19.md) has an explicit correction of the five-coefficient count, active IIR count and digital cutoff interpretation.

