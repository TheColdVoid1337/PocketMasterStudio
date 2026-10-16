# POCKET_MASTER / PocketMasterStudio — HTKPA engineering handoff after Stage91

**Rollover date:** 2026-10-17 (Asia/Bangkok)  
**Primary project:** `TheColdVoid1337/PocketMasterStudio`, branch `main`  
**Operator local checkout (WSL):** `/mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod`  
**Canonical private evidence:** [RE_HTKPA Drive folder](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK) — ID `1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK`.  
**Legacy Drive folder:** `1XeFLIwwHDXPmA74m0ttcHGgCQJG6BS0E`. This is the old location, **not** the canonical write destination.  
**Next command:** `#next` = independently select and execute the next narrowly scoped, evidence-driven stage; do not ask for redundant confirmation.  
**Current completed milestone:** Stage91. **Next stage number:** Stage92, only after verifying HEAD and latest RE_LOG.

## 0. Mandatory startup in next ChatGPT thread

1. Read **this entire handoff**, not only bootstrap text; inspect live repository `research/htkpa/RE_LOG.md`, `research/htkpa/stages/stage91/README.md`, `research/htkpa/stages/stage90/README.md`, current code/test/config and GitHub HEAD. Reconcile newer commits rather than assuming this snapshot is latest.
2. List canonical Drive folder; identify latest private HANDOFF/CHECKPOINT by actual filename, modification time and manifest. Read if relevant. **Do not publish** DLL, NAM, CLO, proprietary assets, binary Frida data, raw heap pointers or full Ghidra decompilation to public GitHub.
3. Preserve established staged reverse-engineering workflow, WSL shell formatting, exact SHA and proof limits. Operator has **explicitly permanently authorized GitHub and Google Drive writes in this chat until revoked**; do not re-request permission. Actual connector permissions still govern writes.
4. Do not substitute Codex for direct Github engineering, and do not prescribe a new Frida architecture: **universal Frida runner already exists**. Ask the operator for a new capture when runtime truth requires one, instead of accumulating irrelevant static speculation. Do not auto-run local Windows Manager from cloud.
5. Use Russian in conversation, straightforward technical style. Commands shown to user must be valid **WSL Bash**, never PowerShell or Windows CMD syntax. One complete paste-ready fenced `bash` block for each operator run; avoid fragmented commands.

## 1. Project objective and evidence discipline

We are reverse-engineering Sonicake Manager's HTKPA / `5868USB.dll` NAM → CLO audio/model conversion pathway, especially native resampling, to understand the original behavior and potentially reproduce it independently. The historical research is extensive (Stage1–Stage91): avoid rebooting the investigation or treating old hypotheses as new. `research/htkpa/RE_LOG.md` is the public cumulative ledger; `research/htkpa/stages/stageXX/` hosts documented, offline-reproducible stage artifacts; `tools/test_htkpa_stageXX.py` tests; `research/_LOCAL_FILES/` is ignored and holds original DLL/captures/private output **on user's Windows/WSL workstation**, not assumed available in cloud.

Three evidence tiers **must never be conflated**:
- **NATIVE CAPTURE / RUNTIME:** original SHA-guarded Frida journal, exact event chronology, pointers joined within *the same run*. Always distinguish observation, non-observation, crashing run, user testimony.
- **ORIGINAL PE / STATIC:** exact original `5868USB.dll` bytes, decoded instructions, `.pdata` ownership, export table, constants, call edges/vtables. Proves *possible compiled route*, not which condition was taken during any capture.
- **INFERENCE / GHIDRA / PUBLIC CODE:** decompiler interpretation and numerical matching (e.g. patched public r8brain), explicitly qualified; close numerical parity does not prove program ancestry or proprietary algorithm identity.

Original vendor DLL SHA256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. Original DLL is examined as **inert data** by offline Python audits. Ghidra Headless 12.1.4 used privately for whole-function decompilation. Preserve ASLR base/RVA distinction. No invented byte offsets, event fields, branch selections, WAV paths, hashes or completion.

## 2. Current verified technical baseline: Stage89–91

**Stage89 (user-operated Frida):** real original Windows Manager observation. Stage89 archive local path (as displayed by operator): `research/_LOCAL_FILES/frida_captures/frida_20261016_181158_278441_bmdlbv64.tar.gz`. Journal says `OPERATOR_INTERRUPTED`, no proven stable CLO or successful conversion. Manager reportedly crashed when operator imported NAM; no verified WER/Event 1000/1001 cause (the log query itself worked but returned nothing). Don't claim observed exception type. Stage89 used `FRIDA_AUTO_QUIET=300 bash tools/FRIDA_WSL.sh --config research/htkpa/stages/stage89/frida.json --fresh --timeout 900`; this configuration is historical, **not** an automatically safe repeat.

**Stage90 (authentic same-run link):** Frida: 4/4 hooks; six native hits on one thread over 287 ms, 0 hook exceptions. Resampler group `0xCE00` actual caller return address resolves (accounting ASLR and call length) to original PE `E8` call at RVA `0xD786`, owner `0xD4A0`. Same-capture object matching: group input `0xCE00 → 0xD018`; parent allocated and processed via `0x118FD`; its selected fractional child receives `0x135C0`. Original PE and Ghidra show `0xD4A0` WAV-reader and file-processing capability (JUCE `WavAudioFormat`). Two XMM field-read errors left source and target rates **unknown**; no opened WAV pathname captured. Stage64 *historical* parent identity remains **unbound**.

**Stage91 (static original PE, completed):** status `STATIC_NAM_WAV_ENTRY_FAMILIES_AND_EXPORTED_WRAPPER_VERIFIED_STAGE89_UPSTREAM_UNBOUND`. Four **decoded direct callers into** `0xD4A0`, exhaustive for **decoded direct E8 rel32** calls, not indirect:
- `0xEB1E` in `0xE0E0`: NAM-associated `getNamOutput`/input WAV preprocessing path, conditional conversion toward NAM sample rate.
- `0x100EB` in `0xFF40`: calls `0xE0E0` at `0x10043`, checks `-2.0` error sentinel, guarded WAV conversion with literal `44100.0` Hz.
- `0x11021` in `0x10E70`: calls `0xE0E0` at `0x10F7F`, checks sentinel; guarded WAV conversion with NAM-worker returned rate.
- `0xAD5E9` in exported `getAppNormalWav` wrapper `0xAD5D0` (export ordinal 19): forwards caller's target rate.

Verified: seven `E8` links including Stage89 inner `0xD786 → 0xCE00`; 40 instruction anchors, `.pdata` owners, NAM/WAV strings, float/double 44100 and double -2 sentinel, export table; full private Ghidra corroboration. **25/25 Stage91 controls** and **268/268 Stage70–91 tests** passed, plus audit on real original DLL. No new Frida and no Windows execution in Stage91.

**Crucial unproven point:** Stage89 measured only `0xD4A0 → 0xCE00`, **not which of the four upstream callers entered** `0xD4A0`. Do not attribute Stage89 execution to `0xE0E0`, `0xFF40`, `0x10E70`, or `getAppNormalWav` without a new specific capture. NAM import attempt is operator report, not capture-proven model/path identity; no same-run NAM and CLO hashes. **User attests ALL their Frida NAM-imports always used** `JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`; this is high-quality operator testimony but not a hash embedded in Stage64/89. Do not question this statement again without actual contradictory native data. It is present in the private Drive folder.

Related earlier important result (Stage63–66): transient source-patched public r8brain v6.5 / poly673, beta 12.55262798, power 1.51553897 achieved forward 1067 f64 RMS ~2.87e-19 and reverse 114 f64 RMS ~7.24e-17 versus native Stage64, with chunked-vs-whole public bit equality. **Near-machine-precision parity does not establish native runtime provenance** or successful CLO. See logged Stage65/66 test and private archives.

## 3. What to do at #next

- First inspect GitHub HEAD, the end of `RE_LOG.md`, Stage90/Stage91 docs/auditors/tests, and private folder's latest checkpoint. If Stage92 already exists, do **not** overwrite it; continue next real stage.
- Prioritize a useful, bounded investigation of the **upstream branch guards and ownership** of `0xD4A0`. Test genuine original instructions and write a falsifiable audit rather than re-label static routes as runtime routes.
- If resolving the **actual Stage89 upstream caller** requires native observation, **stop claiming progress based on static code**, explicitly request a user-run **safe Frida capture via existing universal runner**, with new SHA-checked single-site/bounded config, preflight, risk note and crash-aware protocol. Because last NAM import crashed Manager, no blind rerun. Prefer a crash-safe tiny metadata-only trace before any sample reads, and never pretend absence of Windows WER means no crash.
- User asks `#next` to proceed autonomously within the current verified scope; do work, commit public-safe code/docs and tests, archive newly important private evidence on Drive, and report actual SHA, links, tests, proof limits and exactly formatted WSL commands. If native intervention blocks decisive claim, ask user rather than spin many stages.
- No unrelated feature work, no blind production DSP rewrites, no uncontrolled installation or binary execution.

## 4. Files and private Drive source map

GitHub:
- `research/htkpa/RE_LOG.md` — authoritative chronological research.
- `research/htkpa/stages/stage90/{README.md,evidence.json,audit_stage89_runtime_chain.py}`, `tools/test_htkpa_stage90.py`.
- `research/htkpa/stages/stage91/{README.md,evidence.json,audit_upstream_wav_callers.py}`, `tools/test_htkpa_stage91.py`.
- `tools/FRIDA_WSL.sh`, `tools/frida_capture.py`, `tools/frida_guarded.py`, `tools/research_run.py`, and their regression tests.
- `docs/dev/HTKPA_HANDOFF_AFTER_STAGE91_20261017.md` (this handoff).

Private folder (confirmed listing, files individually in place; do not publish binaries):
- Stage90 checkpoint ZIP: [HTKPA_STAGE90_PRIVATE_CHECKPOINT_20261016.zip](https://drive.google.com/file/d/13yEwDi1-ZIg7NKrCa6q73a5KguSk0j7q/view).
- Stage90 private handoff: [HTKPA_PRIVATE_HANDOFF_STAGE90_20261016.md](https://drive.google.com/file/d/1Ol4Dzs0xelurm1oeYOFkhjHTIz_0tKLk/view).
- Stage90 Ghidra audit: [ghidra_stage90_static_audit.txt](https://drive.google.com/file/d/1j3qVpJ0cxsOJp4ctQE6dOWT5u_MXkt-D/view).
- Stage89 Ghidra audit: [ghidra_stage89_static_audit.txt](https://drive.google.com/file/d/11w8dhAisFFEigJJ984QkoPKQxTEjzIJ2/view).
- Ghidra Headless handoff: [GHIDRA_HEADLESS_HANDOFF_2026-10-16.md](https://drive.google.com/file/d/1hfA49AY4JH1DtZUZ2nGqj4016Vbp0ZxY/view).
- Ghidra 12.1.4 split ZIP parts: `.001` ID `1dA-uaLuKIWZELTgdCl-HoFTZOcrgTBhg`; `.002` ID `1DgVKX0QeilR_ZGvZ48KMgc5C8FeLzlnz`; `.003` ID `12I5VMGGwWvRXQRH5kvSV2P2PlVX9WrBz`; `.004` ID `194gesr8UjDCQuieR2wCq0S5aRaU2vOWp`. No need to re-upload huge Ghidra bundle.
- Source NAM: [JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam](https://drive.google.com/file/d/11TLcyp58tH9fjRU18M3tLpKVysnxWmZe/view).
- Old private comprehensive `HTKPA_CORE_20261016_012322.zip` and `HTKPA_HISTORY_20261016_012322.zip` already reside in the folder; older stage checkpoints also remain.
- **No new duplicate ZIP required for the handoff**: existing private Stage90 checkpoint and Ghidra artifacts supply non-GitHub evidence, while complete Stage91 public-safe code and state are in GitHub. If a future private Stage91 artifact exists after rollover, discover/verify it rather than assuming absent.

Local WSL paths (operator PC only):
- Checkout `/mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod`.
- Python venv `.venv/bin/activate`.
- Vendor DLL `research/_LOCAL_FILES/vendor/5868USB.dll`.
- Frida captures `research/_LOCAL_FILES/frida_captures/frida_*.tar.gz`.
- Research archive outputs `research/_LOCAL_FILES/research_runs/*.tar.gz`.
- WAV `/mnt/c/Program Files/Sonicake/Sonicake Manager/data/flutter_assets/assets/wavs/nam_input_wav.wav`.
- Manager `C:\Program Files\Sonicake\Sonicake Manager\Sonicake Manager.exe`; relevant CLO directory `C:\Users\TheColdVoid\AppData\Roaming\Sonicake\Sonicake Manager`.
Never assume those Windows paths exist in connected cloud runtime.

## 5. Shell / response contract (VERY IMPORTANT)

All instructions to operator must be **genuine WSL Bash** and immediately pasteable, e.g.:

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
git status --short

python -m unittest discover \
  -s tools -p 'test_htkpa_stage91.py' -v
python -m unittest discover \
  -s tools -p 'test_htkpa_stage*.py' -q
```

For a stage offline audit:
```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
python research/htkpa/stages/stage91/audit_upstream_wav_callers.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage91_upstream_wav_route_private_report.json
```

For Frida **only after new config is prepared and user explicitly asked to run the capture**: always deliver one two-step WSL block with `--preflight` first, then reviewed `bash tools/FRIDA_WSL.sh --config ...` (and flags appropriate to verified config). Don't embed PowerShell `$env:`, `Get-WinEvent`, Windows path as bash executable, or claim WSL `find` / `wevtutil` catches all crashes. `wevtutil.exe gli Application` returned exit 0 and logs exist, but query for 1000/1001 had no output.

When reporting a completed stage:
1. In Russian, concise summary of **what is directly verified** vs **still unknown**.
2. GitHub commit SHA/message, modified files and current status.
3. Test counts and exact commands.
4. Drive private checkpoint/handoff URLs where actually uploaded; do not invent them.
5. One complete fenced `bash` block to pull and reproduce.
6. Next narrow falsifiable goal, or ask directly for Frida capture if runtime evidence is the blocker.

## 6. GitHub / Drive publication rules

Public `docs/dev/`: durable handoff; public `research/htkpa/RE_LOG.md`: evidence ledger. Every significant stage has a narrowly scoped `README.md`, `evidence.json`, auditor and isolated tests; avoid invented metrics. Private evidence is recorded via relative local path and private Drive **links only**; never upload proprietary DLL, model or raw binary memory to GitHub. Archive relevant critical non-GH evidence in **canonical** private folder, not legacy one. Update handoff with canonical folder URL **every rollover**. On GitHub writes use direct connector and cite actual commit SHA. On Drive uploads verify listing/readback. New file creation ≠ verified upload.

## 7. Last-action verification

As of this handoff, repository `RE_LOG.md` already contains completed Stage91 evidence and Stage91 README exists. The privately listed canonical Drive folder includes Stage90 critical ZIP and prior handoff, original proprietary sample and Ghidra reports; no necessity to redundantly bundle those for this transition. **This document itself** is the new definitive chat bootstrap reference. Any newer direct connector observations supersede it, and disagreements should be transparently resolved with SHA/date.

### Recommended bootstrap

“Continue POCKET_MASTER / PocketMasterStudio HTKPA immediately from [this handoff](https://github.com/TheColdVoid1337/PocketMasterStudio/blob/main/docs/dev/HTKPA_HANDOFF_AFTER_STAGE91_20261017.md). Read it completely, then live GitHub RE_LOG + Stage91 and [private RE_HTKPA](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK) (Stage90 checkpoint/HANDOFF/Ghidra as needed). Retain all WSL Bash block formats, engineering/evidence/Frida workflows and existing write authorization. Do not confuse Stage91 static potential callers with Stage89 real runtime caller. Start at #next.”
