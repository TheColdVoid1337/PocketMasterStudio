# Conservative HTKPA research hygiene audit

2026-10-12. Dry-run inventory was taken at `ab63a8f75a9cbc0c0b9d556e5ef2a4c6ff07162f`, after the two research commits. Machine-readable inventory: `research/htkpa/hygiene_inventory_2026-10-12.json`. This was a research-tree audit, not a production refactor.

| Classification | Evidence | Disposition |
| --- | --- | --- |
| Nested checkouts/submodules | None found outside protected/dependency trees; `git submodule status` empty | No action |
| Nonignored untracked files before audit | None | No user files to relocate |
| Duplicate Python | One SHA-identical group: Stage21 solver copies in stages 21, 22, 23 | Keep all three historical snapshots |
| Duplicate JSON/text evidence | Five SHA-identical groups, paths and hashes in inventory | Keep repeatability records and historical checkpoints |
| Mislocated Markdown under `research/htkpa/` | None | Restored Stage23D originals correctly under `docs/` |
| Original ZIPs and private inputs | Private manifest 16/16 hashes and sizes verified | Preserve all; no archive deletion |
| Local current-run scratch | Disassembly and fresh verification evidence are ignored | Preserve for continuation; no publication of disassembly/audio |
| Research Python caches | Six ignored `.pyc`, 55,720 bytes, each SHA recorded before deletion | Back up, verify ZIP CRC and each extracted hash, then remove exact files |
| Other caches | Ignored `tests/__pycache__/`, `tools/__pycache__/` | Preserve outside research scope |
| Stale task claims | Stage23D placeholder/source gap and older Stage23C rate uncertainty | Add visible updates to canonical handoff/recovery; preserve historical report text |

## Completed safe cleanup

Only the six recorded research `.pyc` files were removed, followed by their empty `__pycache__` directories. Before unlinking, every resolved path was checked to remain within `research/htkpa/stages/`, to be an ignored untracked `.pyc`, and to match its recorded SHA. No recursive deletion was used.

A verified ZIP backup remains **outside the checkout**, SHA256 `9e5f3626a9f235b0b8b4f681fa3c0e9956da9139ee3c3bb7704bfc6be9536067`; the local locator is retained in ignored research scratch. The ZIP includes a per-file manifest. It was not uploaded and must not be cleared without permission. No tracked files, source snapshots, canonical JSON evidence, original ZIPs, models, audio, CLOs, private logs, configuration or protected hardware baseline were removed.

**PROPOSED_DELETE requiring approval: empty.** Ambiguous or historical duplicates were retained, so no approval request is needed. Tests can regenerate caches; use Python `-B` or `PYTHONDONTWRITEBYTECODE=1` when a cache-free research checkout is useful.

## Verification and limitations

Both source manifests remain valid (144/144 historical +14/14 Stage23D); all 16 private-manifest inputs, including the hardware-validated baseline, remain unchanged. `git diff --check` passes; no private input path is tracked. Changes since the task baseline are confined to `docs/` and `research/htkpa/`; production behavior is unchanged.

Protected input/config/log trees were checked for ignore/tracking safety and input hashes, not reorganized or exhaustively classified as user data. Dependency trees were excluded from nested-checkout scanning. Windows `git status --ignored` warned that it could not open the WSL `.venv/lib64` link; no attempt was made to repair or remove the environment. Stage05 original source is still unavailable. Both models' native gain/FIR parity remains open, as detailed in [Stage23E](NAM_CLO_HTKPA_DLL_RE_STAGE23E.md).

Research commits preceding this audit:

- `8355b236f46c03e2e96830810e8bfc7c6facffa1` — restore Stage23D verifiers/fixtures and original reports.
- `ab63a8f75a9cbc0c0b9d556e5ef2a4c6ff07162f` — PCM branch, reference buffer, resampler state and PCM24 writer boundary.

Both were pushed to `origin/main`. The audit report and inventory form a separate maintenance checkpoint. Start future work with the [canonical task handoff](CODEX_HTKPA_DLL_RE_HANDOFF_2026-10-12.md) and its Stage23E continuation link.
