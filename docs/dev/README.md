# Development handoffs — current entry points

## Current authoritative new-chat handoff (2026-10-21)

**PocketMasterStudio / HTKPA:** [`HTKPA_HANDOFF_STAGE109_20261021.json`](HTKPA_HANDOFF_STAGE109_20261021.json) — the current **machine-readable** handoff for the Sonicake Manager NAM→CLO investigation. This is the required bootstrap entry for the next chat, together with **live** GitHub `main`, the tail of [`research/htkpa/RE_LOG.md`](../../research/htkpa/RE_LOG.md), [Stage108](../../research/htkpa/stages/stage108/README.md) and [Stage109](../../research/htkpa/stages/stage109/README.md).

**Checkpoint:** Stage108 is complete; a read-only, real operator floor-quantizer follow-up established **335248/340000 (98.60235%) exact PCM16** on later **active** frames using `floor(0.31 * open_NAM_f64 * 32768)`, but only ~10.49% exact on early active frames. The separate Stage109 source/tests **15/15 pass on synthetic fixtures**, while **real Stage109 WSL run remains PENDING** as of the handoff. Do not claim proprietary Sonicake quantizer, model, resampler, fitter or hardware parity.

**Canonical private Drive:** [`RE_HTKPA`](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK). The original Stage97 ZIP, NAM model, vendor Manager archives, private historical backups and Stage109 tools ZIP have already been listed and verified there. The ignored workstation `research/_LOCAL_FILES/stage102/` numerical outputs/reports are not assumed available in the assistant's cloud sandbox. Do not upload private model/WAV/CLO/vendor captures or their identifying raw hashes to GitHub.

**Current operator WSL checkout:** `/mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod`. Use `source .venv/bin/activate`, `git pull --ff-only origin main`, targeted `python3 -m unittest discover -s tools -p 'test_htkpa_stage109.py' -q`. The canonical Stage109 command is in its README. Do not rerun Stage102–108 or overwrite their private reports.

## Prior historical handoffs — read for history, not as current stages

- [`HTKPA_HANDOFF_AFTER_STAGE91_20261017.md`](HTKPA_HANDOFF_AFTER_STAGE91_20261017.md) — extensive tooling, private/local Windows paths, provenance discipline and stage history through Stage91.
- [`HTKPA_CHAT_ROLLOVER_2026-10-14.md`](HTKPA_CHAT_ROLLOVER_2026-10-14.md) — historical Stage48/49 rollover and universal Frida architecture.
- [`HTKPA_PUBLIC_SOURCE_CANDIDATES_20261019.md`](HTKPA_PUBLIC_SOURCE_CANDIDATES_20261019.md) — open-source candidate provenance.
- [`tools/FRIDA.md`](../../tools/FRIDA.md) — universal Frida runner and safety protocol (only for specifically warranted future native captures).
- [Product README](../../README.md) — production Studio scope and usage.

**Rules:** stage-local `README.md`, `evidence.json`, auditor, tests; append-only `RE_LOG.md`; strict distinction real vendor observation / open public numeric match / fitted diagnostic / hypothesis; no unsolicited Codex or production refactor. Direct GitHub/Drive writes are authorized until the operator revokes them, subject to connector permissions. Reply in Russian and give one paste-ready WSL **Bash** code block per operator step.

The 2026-10-14 handoff is **not current** despite older headings which once called it canonical.
