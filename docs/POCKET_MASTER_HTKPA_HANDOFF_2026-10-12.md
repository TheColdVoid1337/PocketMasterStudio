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
