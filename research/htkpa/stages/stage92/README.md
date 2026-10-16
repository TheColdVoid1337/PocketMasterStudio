# Stage92 — bounded native outer-caller capture gate (prepared, not observed)

**Status:** `CAPTURE_PROTOCOL_READY_NATIVE_OBSERVATION_PENDING`.

Stage90 established a real Stage89 `0xD4A0 → 0xCE00` downstream call,
with same-run resampler object joins. Stage91 enumerated four *possible*
decoded direct callers into `0xD4A0`. Neither stage measured which of the
four upstream callsites was active in Stage89. Static branch reading cannot
retroactively supply the missing return address.

Stage92 therefore prepares a **new** and deliberately small native gate,
without claiming it has run. The operator must decide when to perform one
controlled NAM import: the previous import reportedly crashed Manager and
the Windows exception cause remains unknown. This stage neither changes
native code nor executes Sonicake Manager in the build environment.

## Instrumentation boundary

The checked-in `frida.json` is for the **existing universal runner**
`tools/FRIDA_WSL.sh` and its scalar mode, not a new Frida agent.

| Hook / original PE RVA | Max hits | Captured field |
|---|---:|---|
| `wav_worker_d4a0_entry` (`0xD4A0`) | 4 | saved return address, read as one pointer from `[RSP]` |
| `resampler_ce00_entry` (`0xCE00`) | 4 | saved return address, read as one pointer from `[RSP]` |

Both hooks are required for auto-quiet success; config pins the original
`5868USB.dll` SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
No XMM fields, sample data, WAV buffers, NAM/CLO contents or arbitrary
heap reads are configured. The universal scalar agent **also emits four
register values for each hit**, so the complete journal is private.
Maximum configured hit payload: eight stack return-address reads (one
pointer per hit); instrumentation can still perturb/crash a native process.

## Operator gate (WSL Bash only)

First close all existing Sonicake Manager instances **normally**. Save
unsaved work elsewhere. Run one block in WSL; `--preflight` is no-attach
and checks the original DLL SHA. `--fresh` launches one Manager process;
wait for two `[FRIDA] hook_attached` messages and `[FRIDA] ready`, then import exactly one known NAM file
(`JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`) **once**. Do not loop
imports or force any CLO action. An `INCOMPLETE` or `OPERATOR_INTERRUPTED`
archive is useful, but it is **not** successful conversion. If Manager
crashes or hangs, do not retry blindly; press Ctrl+C once to preserve the
journal, retain the archive and describe what happened.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python tools/frida_capture.py \
  --config research/htkpa/stages/stage92/frida.json \
  --module-file research/_LOCAL_FILES/vendor/5868USB.dll \
  --preflight --timeout 240
FRIDA_AUTO_QUIET=15 bash tools/FRIDA_WSL.sh \
  --config research/htkpa/stages/stage92/frida.json \
  --fresh --timeout 240
```

Capture archive: `research/_LOCAL_FILES/frida_captures/frida_*.tar.gz`.
Keep the **exact newly printed basename and SHA**. Do not publish this
archive to GitHub or paste raw event addresses into a public issue.

## Offline acceptance after operator delivery

`audit_outer_caller_capture.py` reads the private tarball and original DLL
as inert data. It requires both hooks, original-runtime SHA, correct ASLR
PCs, bounded counts, clean field/hook reads and pinned caller `E8 rel32`
bytes plus `.pdata` owner. For a recognized outer caller followed within
2,000 ms on the same thread by the known `0xD786 → 0xCE00` inner edge,
it emits a **sanitized, new-run temporal-sequence** conclusion. Multiple
prior outer hits, unknown/indirect return addresses, missing inner hits,
or cross-thread events remain `UNBOUND` instead of inventing ancestry.

This is still **not an exact same-invocation stack identity** without
additional stack/exit evidence, and cannot retroactively identify the
Stage89 or historical Stage64 path. No exact WAV pathname, rates, NAM
hash, successful CLO or crash diagnosis is claimed.

After receiving the real archive filename, run this audit with that
**exact** path, not an old Stage89 capture:

```bash
python research/htkpa/stages/stage92/audit_outer_caller_capture.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --capture research/_LOCAL_FILES/frida_captures/REPLACE_WITH_NEW_STAGE92_ARCHIVE.tar.gz \
  --out research/_LOCAL_FILES/stage92_outer_caller_private_report.json
```

The replaceable archive argument is deliberate: no new native run has
occurred at publication. A real report must be inspected before Stage92
runtime acceptance or any further GitHub status update.

## Current offline gates

- Stage92 protocol/synthetic negative controls: **30/30 PASS**.
- All `test_htkpa_stage*.py` tests: **352/352 PASS**.
- Universal runner offline self-test: PASS.
- Scalar config preflight without the private DLL in cloud: PASS for
  schema/runner; **original-file SHA preflight pending on operator WSL**.
- Original DLL Stage91 static findings remain the accepted upstream
  direct-call inventory; **no new original DLL static audit** is claimed.
- **No Stage92 Frida observation yet**; the actual runtime gate is pending.

The original DLL, original NAM file, all Frida archives and full Ghidra
decompilation remain in the canonical private
[RE_HTKPA](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK)
workflow, not in the public repository.
