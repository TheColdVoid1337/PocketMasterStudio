# HTKPA research sources — verified relocation and new-chat recovery

> **CURRENT STATUS (2026-10-13, through Stage23O):** [HTKPA current research status](NAM_CLO_HTKPA_RESEARCH_STATUS_2026-10-13.md) supersedes this page as a *progress/handoff entry point*. This page preserves the dated **2026-10-12 source-recovery inventory and integrity procedures**. Its Stage23C/23D open-item lists and file counts refer to the historical archive, not all subsequently authored Stage23E–O checkpoints.

**Stage23D restoration update:** 14 additional original text files are now restored and separately manifested; the 144-file historical manifest below remains unchanged. See [restoration and fresh verification](NAM_CLO_HTKPA_STAGE23D_RESTORATION_2026-10-12.md). Stage23D establishes both models' nominal 48k rate; historical Stage23C open items below describe the earlier checkpoint.

**Archival date: 2026-10-12.** Canonical historical Stage reports stay in `docs/`. All newly recovered source code, executable tests, read-only JSON evidence and compact fixtures are in `research/htkpa/stages/`. **No proprietary DLL, Manager installer, NAM, WAV, CLO, firmware, full disassembly or personal capture was added to GitHub.** Production Void Mod remains unchanged.

## Exactly what was recovered

The original, user-supplied researcher ZIPs were reopened, CRC-tested and unpacked as text without editing the source code, test logic or saved evidence:
- `stage01`–`stage04`;
- `stage06`–`stage23`, including independent `stage21`/ `stage22`/ `stage23` (23A) folders;
- `stage23_preflight`, `stage23b`, `stage23c`.

**25 source checkpoints; 144 text files total, including 45 Python files.** Stage-specific Markdown `README.md`, `RESEARCH_REPORT.md` and the preflight Markdown report were kept under `docs/htkpa/source_archive/<stage>/`, NOT under `research/`. All original code filenames and relative data subfolders (including separate Stage7 2203/SC20 data) are retained. Non-Markdown safe data (`.json`, `.txt`, `requirements.txt`) live with code. Some checkers refer to absolute paths from their original historical execution: this is preserved exactly as evidence rather than silently refactored.

**Verified exclusion**: Stage 05 archive's Project Library entry was present, but its raw ZIP snapshot was unavailable/expired on 2026-10-12. **No original Stage05 scripts were recovered.** The historical public `docs/NAM_CLO_HTKPA_DLL_RE_STAGE5.md` survives; user should attach the original `Sonicake_HTKPA_DLL_RE_Stage5_v0_5.zip` to close this gap. Static plots (`.png`) were omitted as regenerable illustrations; Stage6 unvalidated candidate `.clo` was excluded. All other available text source files from Stage1–23C ZIPs are represented in the manifest.

## Source of truth and integrity checks

- `research/htkpa/source_archive_manifest.json`: per-file original ZIP member path, original ZIP filename, byte length and SHA-256, plus list of unrecovered stages.
- `research/htkpa/source_integrity.py`: self-contained Python 3 verification; runs on any clone without the DLL or numerical dependencies.
- `research/htkpa/stages/stageXX/`: original stage source, tests, JSON evidence and small fixtures.
- `docs/htkpa/source_archive/stageXX/`: original stage-specific reports/README, kept as documentation.
- `docs/NAM_CLO_HTKPA_DLL_RE_STAGE21.md`, `...STAGE22.md`, `...STAGE23.md`, `...STAGE23_CONTINUATION.md`, `...STAGE23C.md`: canonical conceptual records and errata.
- `docs/NAM_CLO_HTKPA_INTERIM_REVIEW_2026-10-12.md`: engineering review and measured, carefully qualified PE research footprint.
- `docs/POCKET_MASTER_HTKPA_HANDOFF_2026-10-12.md`: historical full handoff (read newer Stage23C and THIS document first).
- `research/htkpa/coverage_audit.py` + `coverage_snapshot_2026-10-12.json`: measured source-pin audit, not actual semantic DLL completion %.

### New chat / new machine quick start

```bash
git clone https://github.com/TheColdVoid1337/PocketMasterStudio.git
cd PocketMasterStudio
python3 research/htkpa/source_integrity.py
python3 -m pip install numpy scipy soundfile
objdump --version
```

For an existing Windows/WSL checkout:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
git pull --ff-only origin main
python3 research/htkpa/source_integrity.py
```

To reproduce source verifier after separately extracting **your own** SHA-pinned DLL, do NOT execute the DLL:

```bash
DLL='/path/to/Sonicake Manager/assets/5868USB.dll'
sha256sum "$DLL"
python3 research/htkpa/stages/stage21/stage21_saturator_source.py --dll "$DLL" --output /tmp/htkpa_stage21.json
python3 research/htkpa/stages/stage22/stage22_pre_fit_trace.py --dll "$DLL" --out /tmp/htkpa_stage22.json
python3 research/htkpa/stages/stage23c/stage23_polyphase_source.py --dll "$DLL" --out /tmp/htkpa_stage23c.json
python3 -m unittest discover -s research/htkpa/stages/stage03 -p 'test_*.py' -v
python3 -m unittest discover -s research/htkpa/stages/stage23_preflight -p 'test_*.py' -v
```

**Original DLL SHA256**: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. Source scripts use static `objdump`, PE reading and independent Python math; do not load vendor DLL or attempt hardware upload. Original Stage19 and Stage20 tests have historical hard-coded `/mnt/data/htkpa_stage14_work/5868USB.dll` paths; they require a compatibility layout or explicit test maintenance before portable execution. Stage20 test additionally supports the environment variable `HTKPA_DLL_PATH`. Stage19's real WAV checks also expect the original capture ZIP paths in `/mnt/data`. Their source and evidence are preserved even if those paths do not exist on the new machine.

**Captured data is not in GitHub**. To independently compute held-out two-model parameter parity, restore exact original Manager installer and 2203/SC20 capture ZIPs, their SHA identities from the handoff, and their corresponding NAM models from the user. The archived JSON evidence cannot replace those proprietary inputs.

## Correct current scientific status

Stage23C is a **source-checkpoint**, not a working independent vendor converter. Mode-0 `namConvertCloData` routing to dynamic Fs is statically traced; the resampler's FIR stage followed by 24-tap, 673-phase polynomial interpolation is identified; the table is initialized at runtime and must be derived by analysis. Exact metadata Fs for the two sessions, native float32 sample scales, both full paired 23–28s arrays, four real fitted gains, and the complete vendor Pre128/Post2048 synthesis **remain OPEN**.

Follow source-first work: (1) select native Fs and map WAV channels/scale and export object pointers, (2) reconstruct native resampler's tap generator and 673-phase table with exact buffers, (3) reconstruct input and target audio for Stage21 sat fitter, (4) compare four independent gains for BOTH Marshall 2203 and SC20 to official CLO as **held-out only**, (5) reconstruct remaining initial A/B, optimizer and FIR finalizer, no production/hardware changes unless separately approved.

A useful handoff instruction to a new assistant is: **Read `docs/NAM_CLO_HTKPA_SOURCE_RECOVERY_2026-10-12.md`, `docs/NAM_CLO_HTKPA_INTERIM_REVIEW_2026-10-12.md`, `docs/NAM_CLO_HTKPA_DLL_RE_STAGE23C.md`, the Stage21/22 errata, then inspect `research/htkpa/stages/` and run `research/htkpa/source_integrity.py`. Do not restart reverse engineering from the beginning. Do not suggest Codex without a request.** Continue Stage23 source-first at the native Fs / buffer provenance gate.

### Limitations and preservation policy

`research/` stores runnable researcher-generated code and safe evidence, `docs/` stores the original and canonical research documentation. Avoid committing `.dll`, `.clo`, `.nam`, `.wav`, installer ZIPs, personal logs or huge original disassembly. Keep the original stage scripts unchanged; add separate improvements as new files with regression tests. Where a historical script hardcodes `/mnt/data`, document or wrap its assumptions. Always record source code SHA, primary DLL SHA and exact run commands.
