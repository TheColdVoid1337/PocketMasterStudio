# CODEX HANDOFF — PocketMaster / Sonicake HTKPA DLL Reverse Engineering

**Execution update:** Stage23D sources and original reports have now been restored, with a separate 14-file SHA manifest and fresh passing tests. See [restoration record](NAM_CLO_HTKPA_STAGE23D_RESTORATION_2026-10-12.md). The placeholder/source-gap statements below are the original task baseline, no longer the current repository state.

**Latest checkpoint: [Stage23E](NAM_CLO_HTKPA_DLL_RE_STAGE23E.md).** Ordinary PCM16 reader branch and reference pre-detrend padding are now source-pinned; an intermediate mono PCM24 writer boundary is newly identified. Native resampler/quantizer/detrend reconstruction and both real gain sets remain open. Resume at the Stage23E next-minimal-task section, preserving the scope and safety rules below.

**Hygiene completed:** [classified inventory and safe cache cleanup](NAM_CLO_HTKPA_HYGIENE_AUDIT_2026-10-12.md). Historical duplicates and all private inputs are preserved; no pending deletion approval.

**Date:** 2026-10-12  
**Repository:** `https://github.com/TheColdVoid1337/PocketMasterStudio`  
**Local WSL checkout:** `/mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod` (verify, do not assume it is the only clone)  
**Primary objective:** Continue **static disassembly and source-first reverse engineering of Sonicake's Windows x64 `5868USB.dll` NAM→CLO conversion path**.  
**Secondary objective:** Safely maintain and clean the RE research tree, documentation and local checkout without destroying data or changing production behavior.  
**Working language:** User-facing progress/reports in Russian; technical source comments, documentation and commit subjects may be English.

## 0. Scope — critical, read first

**This is NOT a general PocketMasterStudio refactor, UI project, new app feature, or redesign.** Focus strictly on the native `5868USB.dll` HTKPA algorithm: exported `namConvertCloData`, its audio loader/decoder, sample-rate selection, native resampler, four-gain saturator fitter, and ultimately native Pre128/Post2048 FIR reconstruction. The surrounding browser app exists as project context and a protected production baseline. Do **not** optimize, reorganize or rewrite it.

Source-first order is mandatory: **(A) actual x64 instructions and arguments → (B) independent Python mathematics → (C) real source WAV/NAM reproductions → (D) held-out official CLO comparisons → (E) optional future production/hardware integration only if separately authorized**. A source address pin is not proof of numeric end-to-end equivalence. No speculative signal processing, no coefficients selected to match vendor CLOs, no invented source findings.

**Never load or execute the vendor DLL.** Disassemble statically using `objdump`, PE parsing and owned reimplementations. Do not run the Sonicake Manager executable. Do not upload DLL/NAM/WAV/CLO/capture ZIPs, local device logs, private paths or full disassembly dumps to GitHub or remote services. Do not write to the physical PocketMaster device. Do not create a new vendor-like production CLO or modify `PocketMasterStudio.html`/its embedded converter without explicit separate approval. Protect the hardware-validated reference `JCM800_2203_v02_C_BRIGHT_PLUS.clo`.

## 1. Checkout and private local files

From the checkout root, verify branch and local changes before pulling:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
pwd
git status --short --branch
git remote -v
git rev-parse HEAD
# If the working tree is clean and no divergence needs resolution:
git pull --ff-only origin main
python3 research/htkpa/source_integrity.py
```

The separate archive **`POCKET_MASTER_HTKPA_CODEX_LOCAL_FILES_2026-10-12.zip`** contains only local research inputs and backs up originals. Unpack its **`research/_LOCAL_FILES/`** tree under the repository root; inspect any existing files and hashes before overwriting. The repository's root `.gitignore` explicitly excludes `/research/_LOCAL_FILES/` in its entirety, as of commit `8ea1dcbf665cc1a34045fc24dc270449689d46c4`. Check:

```bash
git check-ignore -v research/_LOCAL_FILES/vendor/5868USB.dll
git ls-files research/_LOCAL_FILES
# The latter MUST print nothing.
sha256sum research/_LOCAL_FILES/vendor/5868USB.dll
```

The DLL SHA256 must equal:

`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa` (size 2,902,016; image base `0x180000000`).

Suggested private filesystem layout (already provided in ZIP):

```text
research/_LOCAL_FILES/                     [IGNORED ENTIRELY]
  manifest.json                            per-file SHA256, provenance, sizes
  vendor/5868USB.dll                       exact original machine-code authority
  models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam
  models/Marshall JCM 800 SC20 Full Rig.nam
  captures/2203/{input_DI.wav,output_reference.wav,official_vendor.clo,tone_import.log}
  captures/SC20/{input_DI.wav,output_reference.wav,official_vendor.clo,tone_import.log}
  baselines/JCM800_2203_v02_C_BRIGHT_PLUS.clo    DO NOT ALTER
  archives/{Sonicake_Manager_original.zip,capture_2203_original.zip,capture_SC20_original.zip,
            Sonicake_HTKPA_DLL_RE_Stage23D_PLUS_DECODER_v0_23d.zip}
```

You have read/write access to the *local* private folder, but **not authorization to publish** any of its contents. `research/htkpa/stages/`, by contrast, is tracked and should contain only our original research source code, unit tests and nonprivate evidence. All Markdown research reports and historical READMEs belong to `docs/`, including `docs/htkpa/source_archive/`. Never move documentation wholesale into `research/`.

Check the private manifest with your own small SHA256 verifier. Model SHA256: 2203 `29abbdbf982ee64b963d1d8de06848d1b06450a623bb08ba3ffefce146dfac42`; SC20 `509ad3d6dc31cf0539afe4a264ff7386d6282ffe9d1e0de4b6cce514b1915b11`. Both original NAMs have `sample_rate=48000`, including two nested submodels. Both input DI captures are byte-identical with SHA256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`, PCM16 stereo, 70 s, 44,100 Hz. Both output/reference WAVs: PCM16 stereo, 70 s, 48,000 Hz. Official CLO files: 8,840-byte VTSI, 2203 SHA `50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7`; SC20 SHA `2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a`.

## 2. What is actually known — current Stage 23D (OPEN)

Read in this order:

1. `docs/NAM_CLO_HTKPA_SOURCE_RECOVERY_2026-10-12.md` — archived Stage1–23C sources and reproducibility.
2. `docs/NAM_CLO_HTKPA_INTERIM_REVIEW_2026-10-12.md` — measured scope and priority audit.
3. `docs/NAM_CLO_HTKPA_DLL_RE_STAGE23.md`, `docs/NAM_CLO_HTKPA_DLL_RE_STAGE23_CONTINUATION.md`, `docs/NAM_CLO_HTKPA_DLL_RE_STAGE23C.md` — audio-loader/resampler findings and corrections.
4. `docs/NAM_CLO_HTKPA_DLL_RE_STAGE23D.md` and `docs/NAM_CLO_HTKPA_DLL_RE_STAGE23D_DECODER_ADDENDUM.md` — latest native sample rate, WAV roles and conditional PCM decoder.
5. `docs/NAM_CLO_HTKPA_DLL_RE_STAGE21.md` and `docs/NAM_CLO_HTKPA_DLL_RE_STAGE22.md` — source-based saturator and critical call-order correction.
6. `docs/POCKET_MASTER_HTKPA_HANDOFF_2026-10-12.md` — broader historical handoff only as reference, not the newest instructions.

**Code:** `research/htkpa/stages/stage01` through `stage23c` (Stage05 original source unavailable), `research/htkpa/source_archive_manifest.json`, `research/htkpa/source_integrity.py`, `research/htkpa/coverage_audit.py`. The GitHub Stage23D directory currently contains only a `STAGE_STATUS.txt` placeholder; its **source code and evidence are in the private-local Stage23D ZIP** and should be rescued into the tracked research tree (see §3). No original commercial binary belongs in the tracked tree.

Verified source-level chain:

```text
namConvertCloData at 0x1800E1F70
  saves NAM path +0x218, WAV paths +0x208/+0x210 and mode +0x27C=0
  → async vtable call 0x180060F20 → normal dynamic-Fs wrapper 0x180010E70
  → 0x18000E0E0 parses NAM and obtains model sampleRate (48000 for both)
  → 0x18000D4A0 resamples 44.1k input DI to 48k
  → 0x18000CE00 → 0x180011B60 stages:
       first 2× FIR at 0x18000BDF0 (tap coefficients via 0x18000B0E0)
       then 24-neighbor/673-phase polynomial fractional interpolation at 0x1800135C0
       runtime phase-table initialization under 0x1800163FF..
  → 0x180010230 WAV loaders 0x1800BF9F0 and 0x1800BF5E0
       context+0x243E0 = first / input; +0x243E8 = reference
  → 0x1800BE830 target-only detrend and onset scan at 6×Fs (≤600 samples)
       source region 23–28 s, target region 23–28 s + detected onset offset
  → 0x1800BDBE0 four-gain saturator fitter (called at 0x1800BEDE4)
  → later 0x1800BD490 IIR helper (NOT before the four-gain fit)
```

Stage23D additionally identifies `0x1801417F0` as a **conditional** signed-int32→float32 normalization routine multiplying by exactly `2^-31`, called via `0x1801422D1` if an audio reader flag permits it. That is not yet proof of the taken branch. For PCM16 left-justified into int32 this formula equals standard `PCM16 / 32768`; independent arithmetic checked all four capture WAVs exactly against SoundFile float32 output. **Do not infer hidden arbitrary gain, padding or interpolation from this alone.**

Stage21 ordinary-domain saturator algorithm has synthetic acceptance (not real-waveform parity): f32 envelopes in 0.1-s groups, signed mirrored curves, half-maximum OLS slopes, and sequential 9+9 multiplier searches (not a 9×9 grid), output fields `pmax,nmax,prate,nrate` at context `+0x243F8` through `+0x24404`. The two real model gain sets are not independently recovered; official values remain **held-out only**:

| Model | Official pmax | nmax | prate | nrate |
| --- | ---: | ---: | ---: | ---: |
| JCM800 2203 | 0.05869761 | 0.06251806 | 425.438965 | 356.188354 |
| SC20 | 0.01061691 | 0.01269747 | 450.926178 | 253.910919 |

A generic `scipy.signal.resample_poly` DI 44.1→48k diagnostic did **not** match vendor coefficients (e.g. 2203 pmax≈0.1557, prate≈0.9706), therefore it is only a **negative control**. Do not optimize against the official gains or claim generic SciPy is native resampling. Fitting Pre128 and Post2048 and end-to-end vendor CLO parity also remain open. Previous A/B transform, STFT hop, IIR constructor and optimizer state-alias errata in Stages 17–22 are mandatory regression constraints.

## 3. FIRST actual Codex work (prioritized, independent commits)

### A. Repo and local research preflight; preserve uncommitted user files

- Inventory root and nested Git status, tracked/untracked changes, branch/head and remote URLs. Record *before* state with no credentials or sensitive local paths in public logs.
- Verify `.gitignore` excludes private inputs and `git ls-files research/_LOCAL_FILES` is empty. If any private bytes are already tracked, **stop that portion and report**; do not rewrite Git history or force-push. Prepare a safe remediation plan for approval.
- Verify `source_integrity.py`, the exact original DLL hash, both NAM hashes, WAV length/rates and official CLO hashes. Re-check Stage21/Stage22 test commands and 23C evidence; capture precise commands, exit codes and gaps. If historical tests have `/mnt/data` hard-coded paths, run through a compatibility wrapper or document the limitation rather than silently editing originals.

### B. Complete the Stage23D source archival gap

- Inspect `research/_LOCAL_FILES/archives/Sonicake_HTKPA_DLL_RE_Stage23D_PLUS_DECODER_v0_23d.zip`; extract only original researcher-authored `.py`, `.json` and small text test fixtures to `research/htkpa/stages/stage23d/`. Preserve filenames and exact byte hashes where possible; add a verifiable Stage23D manifest. Do **not** import DLL, audio, NAM, CLO or private logs.
- Place original Stage23D `README.md` and `RESEARCH_REPORT.md` in `docs/htkpa/source_archive/stage23d/`, **not** in `research/`.
- Replace/retire misleading placeholder status only after verified source import; update canonical handoff references, not historical results retroactively.
- Run Stage23D verifier on the private DLL and its five tests. There are 42 source address pins, five original PE strings, independent evidence runs and PCM decoder addendum. Re-check all claims rather than simply trusting historical JSON.

### C. Continue **DLL reverse engineering**, not browser development

**Stage23E primary challenge:** trace actual WAV decoder branch, integer/float normalization, output buffer state, and 2× FIR + 24-neighbor polynomial resampler to reproduce the exact float32 arrays entering the fitter. Code targets: `0x180141680`, `0x1801417F0`, `0x1801421C0`, `0x18000D4A0`, `0x18000CE00`, `0x180011B60`, `0x18000B0E0`, `0x1800135C0`, and table initialization `0x1800163FF..`. Pin source instruction address, immediate constants, branch reachability, numeric cast/rounding and buffer offsets. Prefer a small direct experiment isolating the most uncertain branch before implementing the whole 673-phase generator.

Verify channel selection, PCM16 decode layout, native sample rates, frame counts, 70s+600-sample padding, interpolation phase and edge policy, the integer-to-f32 branch state, and the reference preprocessing at **exact 48k**. Feed only reconstructed, independently justified native input/reference 23–28-second windows into the **unchanged Stage21 solver**. Compare all four independently computed values for **both** models to held-out CLO *after* computation. If actual native pair reconstruction is not achieved, publish precisely what remains unknown rather than numeric guesses. Keep the DLL static/read-only.

### D. Safe repo + local checkout cleanup (separate from science)

Carry out a **dry-run and classified cleanup**; the task is useful, but preserving user work overrides tidiness.

1. Detect duplicate researcher scripts, obsolete byte-identical temporary outputs, old archived ZIPs that have verified copies, stale misleading handoff claims, unused generated artifacts and mislocated documentation; build a small inventory with path, tracked/ignored status, SHA if relevant, and disposition.
2. **Safe automatic cleanup** is limited to provable regenerable scratch, caches (`__pycache__`, `.pyc`) and truly duplicated untracked temporary outputs, after taking backups/checksums. Keep canonical JSON evidence and all source-stage archives; don't delete source code just because it is in multiple stages—the snapshots preserve research history. If unclear whether a file contains user changes, preserve it.
3. DO NOT run `git clean -fd`, `git clean -fdx`, `git reset --hard`, mass `rm -rf`, force pushes, or recursive deletions of ignored trees. Even `git clean -ndX` may list the private research pack: **inspection only**, never follow it by bulk deletion. Do not remove ignored `/config/`, `/logs/`, `/research/_LOCAL_FILES/`, original NAM, WAV, CLO, pedal captures or the hardware-validated v0.2C control.
4. For suspicious or nontrivial files, make an explicit **PROPOSED_DELETE** list and get user approval before deleting. Prefer moving duplicated local data into a timestamped backup/quarantine outside the repository with a manifest, and do not clear that backup without permission.
5. For tracked repository cleanup, make focused changes only when no behavior is affected and the purpose is proven; keep canonical reports in `docs/`. Review diff, run tests, record exactly what was changed. Avoid broad app reformatting or restructuring. If an existing tracked file looks like user production data, do not delete without approval.

### E. Checkpoint, docs, commits and push discipline

- New research code: `research/htkpa/stages/stage23e/` or new targeted helpers under `research/htkpa/`. Tests alongside code. Canonical full reports in `docs/`, historical doc continuity preserved. Never place user-specific binaries in GitHub.
- Before every commit: `git diff --check`, relevant Python tests, `research/htkpa/source_integrity.py`, `git status`, inspect staged filenames, confirm no tracked paths under `research/_LOCAL_FILES` and no proprietary binary is staged. Do not accidentally commit executable/DLL/archives. Respect existing working-tree edits.
- Match existing short English imperative conventional-ish subjects from Git history. Use **`research:`** for source/code/evidence, **`docs:`** for source reports/handoffs, **`chore:`** for maintenance; older history also contains `docs(void-mod):`, but avoid adopting a new incompatible scheme. Examples:
  - `research: restore HTKPA Stage23D verifiers and fixtures`
  - `research: trace PCM decoder normalization and sample state`
  - `docs: record Stage23E native audio provenance findings`
  - `chore: exclude redundant HTKPA scratch outputs`
- Prefer 1 logical topic per commit. No amend/rebase/force-push of existing main history. If main is behind, use `git pull --ff-only` when clean. If diverged or ambiguous, preserve both and create a separate branch or ask rather than overwriting. Local commits and push of validated, scoped research/docs/maintenance changes are authorized, but production/device-facing changes still require explicit approval. Report final commit SHAs, remote branch, `git pull --ff-only origin main` command when applicable, and verification summary.

## 4. Deliverables / acceptance criteria

Your work is only considered a meaningful handoff if it produces:

1. **Stage23D source actually on GitHub** under `research/htkpa/stages/stage23d/` plus original Stage23D reports in `docs/` and verified runnable tests.
2. A new source-pinned Stage23E research report or, if not resolved, a precise negative result with address evidence, tested assumptions, errors, and next minimal task.
3. A truthful status for **both** 2203 and SC20 numerical gain parity; do not use official parameters as fitting input.
4. Dry-run cleanup inventory and completed **only-safe** cleanup; explicitly list any deletion deferred for approval.
5. Small, meaningful commits with actual SHAs and no proprietary private files staged.
6. A concise **Russian** end-of-run report: discovered addresses, tested numerical facts, checks passed/failed, files changed, Git commits, open blockers and next RE work. Update canonical docs so any future ChatGPT/Codex session can continue with the repository alone (plus the separately supplied private pack).

**IMPORTANT:** do not turn the assignment into an entire-product audit, Electron/web app overhaul, plugin management, frontend work, refactor, feature implementation or exploratory “cleanup everything” campaign.

## 5. Model budget for Codex

Use a **small/fast Codex model or low reasoning effort** for file inventory, SHA256 verification, ZIP extraction, `.gitignore` checks, source relocation, syntax/test runs, formatting, and mechanical safe cleanup. Use the **strongest available Codex model with high reasoning effort** for Win64 calling-convention analysis, alias and branch tracing, precision-sensitive DSP reconstruction, native polyphase filter mathematics, decoding state and any proof of real-WAV numerical parity. Do not burn high-effort model calls on repetitive listing; do not use low-effort modeling to invent DSP behavior.

## 6. User-facing short task to paste into Codex

> Read `docs/CODEX_HTKPA_DLL_RE_HANDOFF_2026-10-12.md` in full and carry out its staged instructions. This assignment is **exclusively HTKPA `5868USB.dll` static disassembly/reverse engineering**, plus safe research-tree and local-checkout maintenance; **not PocketMasterStudio feature work**. My private research inputs are already in ignored `research/_LOCAL_FILES/`. Start with verification and Stage23D source archival, then trace decoder/resampler native audio buffers. Preserve docs under `docs/`, commit small source-backed changes using existing commit prefixes, avoid destructive cleanup, and report SHA/commands/results in Russian.

## WSL handoff recovery: verified CRLF-only checkout problem (2026-10-12)

On a Windows-mounted WSL checkout the local integrity check reported **0/144**, with many tracked `docs/` and `research/` files marked modified. This was diagnosed, **not corruption of committed source bytes**: the observed local SHA-256s exactly matched original archive files after `LF -> CRLF` conversion; GitHub blobs matched original ZIP source bytes and SHA-256 manifest. Original `git pull --ff-only` succeeded; `git check-ignore -v research/_LOCAL_FILES/vendor/5868USB.dll` passed; `unzip` was unavailable.

Root `.gitattributes` now enforces LF for Markdown under `docs/` and text sources under `research/`. Two safe, standard-library-only utilities are committed:

- `research/htkpa/repair_checkout_line_endings.py`: **dry-run by default**; with `--apply`, only converts CRLF files to LF when the normalized bytes exactly equal `git show HEAD:<path>`. It **never overwrites genuine edits or untracked/private files**.
- `research/htkpa/extract_local_archive.py`: ZIP CRC check, no overwrites, path confinement to `research/_LOCAL_FILES/`, SHA256 validation against the private package manifest; no dependency on OS `unzip`.

Safe WSL recovery sequence:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
git status --short
git config --local core.autocrlf false
git pull --ff-only origin main
python3 research/htkpa/repair_checkout_line_endings.py
python3 research/htkpa/repair_checkout_line_endings.py --apply
python3 research/htkpa/source_integrity.py
python3 research/htkpa/extract_local_archive.py --archive research/_LOCAL_FILES/POCKET_MASTER_HTKPA_CODEX_LOCAL_FILES_2026-10-12.zip
git check-ignore -v research/_LOCAL_FILES/vendor/5868USB.dll
git status --short
```

Before `--apply`, inspect its dry-run report. The tool corrects only files whose sole difference is line endings, and preserves any other modifications. If an unexpected file remains modified, inspect `git diff -- <path>` and **do not** indiscriminately run `git reset --hard`, `git restore .`, `git clean -fdx`, or `git add -A`. Do not assume a list of 144 source mismatches means GitHub archive loss. Only use `git add` for the exact intended paths, with `research/_LOCAL_FILES/` fully ignored. This recovery is subordinate to the primary mission: static reverse engineering of original `5868USB.dll` NAM→CLO pipeline.
