# Development handoffs — current entry points

## HTKPA / Sonicake Manager NAM→CLO reverse engineering

**Canonical new-chat continuation (14 October 2026):** [POCKET_MASTER / HTKPA Chat Rollover 2026-10-14](HTKPA_CHAT_ROLLOVER_2026-10-14.md).

This file is the **current continuation contract** for the project, including exact WSL and Windows paths, original DLL SHA/RVAs, Stage38–48 numerical evidence, the single universal Frida framework, accepted `METADATA_GUARD_PASS_CLO_STABLE` plus `LIFECYCLE_SMOKE_CLOSED_GRACEFULLY`, current privacy rules, a locally packaged private ZIP, and the **Stage49 pending** research plan.

Read the canonical handoff **before** old root-level dated files, especially `docs/HTKPA_CANONICAL_HANDOFF_2026-10-13.md` (historical Stage24B), `docs/NAM_CLO_HTKPA_RESEARCH_STATUS_2026-10-13.md` (historical Stage23O), and `docs/POCKET_MASTER_HTKPA_HANDOFF_2026-10-12.md` (old Stage22/23).

Canonical evidence and workflow:
- [Append-only chronological RE log](../../research/htkpa/RE_LOG.md) — read the tail.
- [Stage48 measured runtime](../../research/htkpa/stages/stage48/README.md) / [Stage48 evidence](../../research/htkpa/stages/stage48/evidence.json).
- [Universal Frida contract](../../tools/FRIDA.md) — future stages use shared `/tools` and stage-local JSON.
- [Repository product README](../../README.md) — production Studio and HTKPA scope boundary.

## Privacy / local evidence

The handoff references **`POCKET_MASTER_HTKPA_PRIVATE_ROLLOVER_2026-10-14.zip`**, a separately generated **LOCAL-ONLY** private archive distributed in the originating ChatGPT conversation (31 user-provided evidence files plus two internal index/readme files; SHA-256 `5e363d0f9ac03388cf19f395a7d4f7fe50b6885e5802d5b7d8cb9f0a6ff161ec`). It includes the original private vendor DLL and captures and **must never be uploaded or committed to GitHub**. To use those originals in a new chat, the user must attach the ZIP separately. Public GitHub handoff does not contain private samples or the DLL.

## Workflow rule

Current HTKPA research progresses stage by stage, with evidence in `research/htkpa/stages/stageNN/`, append-only `RE_LOG.md` and universally reusable code in `tools/`. The last confirmed stage is **Stage48**. The next planned stage is **Stage49** (native post-fractional **audio sample** observation, not yet implemented). All source data and acceptance conditions are distinguished in the full handoff.
