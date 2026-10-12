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

