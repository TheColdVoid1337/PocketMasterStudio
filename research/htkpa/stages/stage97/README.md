# Stage97 — original Manager CLO bundle + Stage96 native timing correlation

**Accepted 2026-10-19 Bangkok status:**
`NEW_RUN_CLO_FORMAT_CRC_CONVERSION_AND_DEVICE_ACK_LOG_CORRELATED`.
This adds a **real operator-produced output artifact and an application-level
success/ACK log**, without changing Stage96's narrower Frida claim or claiming
independent device readback and numerical vendor equivalence.

## Provenance and evidence split

1. **OPERATOR ARTIFACT (private):**
   `CLO_10-19-26-0253.zip` (12,740,792 bytes), SHA-256
   `2f96dce1ae479a93975cf6247a88a4a08c11de7ae5cab41648faa0d7902e6f46`.
   The allowlisted archive contains one `clo/` member, two PCM `wavs/` members,
   and a Manager `logs/` member. Archive integrity test passes. Exact audio,
   original CLO and log remain only in the canonical private RE_HTKPA Drive.
2. **DIRECT BYTE/FORMAT AUDIT (offline Python, on original `.clo`):** 8,840
   bytes, `VTSI` magic, declared size 8,840, data-region field 8,704,
   2,048 finite FIR taps, CRC16-Modbus over bytes `[12:]` with init `0xffff`
   and polynomial `0xa001`, big-endian stored CRC `0xBA7D`, matching calculation.
   This independently agrees with the existing `src/void_clone_protocol.js`
   `validateFile()` on a plain `Uint8Array`. Its Low Model projection is 2,696
   bytes and 512 taps, with a newly recalculated CRC. This is a local format
   transformation, **not** proof the hardware received either payload.
3. **OPERATOR AUDIO ARTIFACTS (private):** input 70 seconds, signed 16-bit
   stereo PCM at 44,100 Hz, 3,087,000 frames; output 70 seconds at 48,000 Hz,
   3,360,000 frames, same PCM/channel format. Independently parsed and checked
   for nonzero sample data. These file labels do **not** prove numerical or
   causal input/output DSP parity.
4. **MANAGER APPLICATION LOG (private):** final 02:53 session reports native
   `namConvertCloData` returned 8,840, progress 100%, success callback,
   8,840-byte file written, CRC check success, 2,696-byte Low Model conversion,
   device `tcImportExport` ACK `status=0`, then `wait importTC result=true`.
   The log's decimal CRC `32186` is the **little-endian interpretation** of
   the stored two bytes `BA 7D` (rather than contradictory CRC data).
   This is the **application's self-report**; no USB payload capture or
   independent hardware readback has been obtained.
5. **NATIVE Frida, distinct origin:** independently accepted exact Stage96
   private tar.gz SHA-256
   `24340c1d00f44311376729a2ba8d2813cf774997f0240c8790a7ad6cfa4e0274`
   contains one `0x10E70` entry at 2026-10-19 02:53:31.621 and leave at
   02:53:42.740 Bangkok time. Those differ from the Manager log's native
   conversion start and progress-end anchors by **0.539 ms** and **0.945 ms**
   respectively, *assuming Windows wall clock uses UTC+07:00*. Stage96 itself
   proves one observed wrapper invocation's nested NAM/fitter calls, **not**
   CLO object identity, buffer identity or final conversion status.

Evidence labels must remain separate: `REAL FRIDA INVOCATION`, `OPERATOR
FILE`, `MANAGER LOG`, `OFFLINE FORMAT AUDIT`, and `SYNTHETIC TEST`. The latest
result is a **strong cross-artifact temporal association and Manager-reported
success**, not a trace of individual model/WAV/CLO buffer flow.

## Reproduce without exposing private data

Use the exact files available privately from canonical Drive folder
`1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK`. Never commit the raw ZIP, unredacted
Manager log, audio/model names, device/session paths, Frida event journal,
binary DLL, full private report or host-specific data. No native code is
executed by this auditor; Ghidra is not needed for this post-capture gate.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python -m unittest discover -s tools -p 'test_htkpa_stage97.py' -q

python research/htkpa/stages/stage97/audit_clo_bundle.py \
  --bundle research/_LOCAL_FILES/CLO_10-19-26-0253.zip \
  --frida research/_LOCAL_FILES/frida_captures/frida_20261018_195315_795910_3s0kasuh.tar.gz \
  --out research/_LOCAL_FILES/stage97_clo_private_report.json
```

The command only reads archived files, writes one private JSON report and
prints a redacted status. The archived Frida SHA is an independent identity
gate; any substitute archive fails. The 12-event Manager ordering/CRC,
allowlisted ZIP members, WAV properties and timestamp correlation also fail
closed. Tests create synthetic `.clo`/log fixtures; they **never** substitute
for the accepted original package.

## Not established / precise next evidence gate

- No hardware independent post-import readback of actual CLO/slot contents;
  ACK alone is not a readback or verified payload byte identity.
- No proof this particular source NAM's bytes were the input to that exact
  native wrapper instance, nor numeric reproduction of vendor filters;
  the Manager log mentions a model name but is not a byte-level NAM trace.
- A repeated import of the same profile may create the same bytes as an
  earlier session; do not call its content new or uniquely identified.
- Stage96 Frida manifest correctly remains `CAPTURED_HOOKS_ONLY` with
  `completion_verified=false`; Stage97 uses **independent** Manager/artifact
  sources for its stronger *application-level* claim.

**Next, only if hardware parity matters:** a read-only retrieval of the
stored slot's CLO bytes through an independently verified device mechanism,
comparing their hash with the saved output and documenting any container/
transport transformations. No unsolicited device writes or fresh Frida run.
