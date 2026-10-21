# Development handoffs — current entry points

## Current authoritative new-chat handoff (2026-10-21)

**PocketMasterStudio / HTKPA:** [`HTKPA_HANDOFF_STAGE109_20261021.json`](HTKPA_HANDOFF_STAGE109_20261021.json) — the current **machine-readable** handoff for the Sonicake Manager NAM→CLO investigation. This is the required bootstrap entry for the next chat, together with **live** GitHub `main`, the tail of [`research/htkpa/RE_LOG.md`](../../research/htkpa/RE_LOG.md), [Stage108](../../research/htkpa/stages/stage108/README.md) and [Stage109](../../research/htkpa/stages/stage109/README.md).

**Historical handoff checkpoint versus current live status:** This 2026-10-21 handoff JSON was authored while Stage109 was **PENDING**, and remains an immutable creation-time snapshot. **Stage109 has since completed a genuine WSL operator run on 2026-10-21 (15/15 operator tests PASS)**; see [Stage109 operator findings](../../research/htkpa/stages/stage109/OPERATOR_RESULT_20261021.md) and the **append-only live** [RE_LOG](../../research/htkpa/RE_LOG.md). Fixed candidate `floor(0.31 * open_NAM_f64 * 32768)` has **335,248/340,000 late active exact PCM16 frames**, 4,752 late nonmatches; the top 20k hotspot [1,340,000, 1,360,000) has 1,700 nonmatches. Early active remains 75,525/720,000 exact. **No native quantizer, gain, resampler, model, fitter, CLO or device parity is proven.**

**Live status as of 2026-10-21 Bangkok:** Stage110, Stage111 and **Stage112** were completed as authenticated **real assistant cloud original-source offline experiments**. Stage112 **17/17** independent synthetic tests PASS; Stage110–112 together **42/42**. See [Stage112 operator report](../../research/htkpa/stages/stage112/OPERATOR_RESULT_20261021.md) and [Stage112 README](../../research/htkpa/stages/stage112/README.md), plus the append-only [RE_LOG](../../research/htkpa/RE_LOG.md). The 2026-10-21 Stage109 handoff JSON remains **historical**, not a current-stage status authority. No Sonicake vendor resampler, model/gain/quantizer, fitter, CLO or hardware parity is claimed.

**Canonical private Drive:** [`RE_HTKPA`](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK). The original Stage97 ZIP, NAM model, vendor Manager archives, private historical backups and Stage109 tools ZIP have already been listed and verified there. User-provided private Stage110 inputs and original Stage97 ZIP **are now available in the current assistant cloud sandbox**. Existing private Stage110–112 reports are separately backed up in this designated Drive folder; do not assume a new isolated session has the same local mount. Do not upload private model/WAV/CLO/vendor captures or their identifying raw hashes to GitHub.

**Operator WSL checkout:** `/mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod`. Stage109 has been executed; its canonical command in Stage109 README is historical. **Do not rerun Stage102–112 or overwrite any existing private reports.** New diagnostic commands, if needed, must be read-only and narrowly justified.

## Prior historical handoffs — read for history, not as current stages

- [`HTKPA_HANDOFF_AFTER_STAGE91_20261017.md`](HTKPA_HANDOFF_AFTER_STAGE91_20261017.md) — extensive tooling, private/local Windows paths, provenance discipline and stage history through Stage91.
- [`HTKPA_CHAT_ROLLOVER_2026-10-14.md`](HTKPA_CHAT_ROLLOVER_2026-10-14.md) — historical Stage48/49 rollover and universal Frida architecture.
- [`HTKPA_PUBLIC_SOURCE_CANDIDATES_20261019.md`](HTKPA_PUBLIC_SOURCE_CANDIDATES_20261019.md) — open-source candidate provenance.
- [`tools/FRIDA.md`](../../tools/FRIDA.md) — universal Frida runner and safety protocol (only for specifically warranted future native captures).
- [Product README](../../README.md) — production Studio scope and usage.

**Rules:** stage-local `README.md`, `evidence.json`, auditor, tests; append-only `RE_LOG.md`; strict distinction real vendor observation / open public numeric match / fitted diagnostic / hypothesis; no unsolicited Codex or production refactor. Direct GitHub/Drive writes are authorized until the operator revokes them, subject to connector permissions. Reply in Russian and give one paste-ready WSL **Bash** code block per operator step.

The 2026-10-14 handoff is **not current** despite older headings which once called it canonical.
