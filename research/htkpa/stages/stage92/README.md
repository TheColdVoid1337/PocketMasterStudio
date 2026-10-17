# Stage92 — bounded native outer-caller capture (new-run observations)

**Status:** `NEW_RUN_TEMPORAL_SEQUENCES_ORIGINAL_PE_AUDIT_VERIFIED`.

Stage90 established a real Stage89 `0xD4A0 → 0xCE00` downstream call,
with same-run resampler object joins. Stage91 enumerated four *possible*
decoded direct callers into `0xD4A0`. Neither stage measured which of the
four upstream callsites was active in Stage89. Static branch reading cannot
retroactively supply the missing return address.

Stage92 supplied a **new** and deliberately small native gate. The operator
subsequently supplied a genuine Frida archive, analyzed below. The previous
import reportedly crashed Manager and the Windows exception cause remains
unknown. This stage neither changes native code nor executes Sonicake Manager
in the build environment.

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

## Original operator gate (WSL Bash only; already captured)

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

## New private journal delivered (2026-10-16 UTC)

Private capture basename: `frida_20261016_212623_230331_8g348j9d.tar.gz`;
archive SHA256 `7bb4025c05eecdda6cd5012299a0a765194eeed9d1f599b0bddc3af82c642456`.
The canonical RE_HTKPA folder contains the complete raw archive. Its registers,
ASLR addresses and event payload **must not** be committed to GitHub.

**NATIVE (new run, journal only):** manifest `CAPTURED_HOOKS_ONLY`,
`completion_verified=false`, `launched_by_tool=false`; runtime module SHA
matches the pinned original; both expected hooks are attached and ready;
zero hook/field errors; six hits (two at `0xD4A0`, four at `0xCE00`), all
on one thread. Computed from captured return addresses minus same-run
ASLR base and five-byte call length, the journal contains:

| Temporal sequence | Outer `0xD4A0` entry return-call RVA | Inner `0xCE00` entry return-call RVA | Entry timestamp gap |
|---|---|---|---:|
| A | `0xEB1E` | `0xD786` | 11 ms |
| B | `0x11021` | `0xD786` | 10 ms |

Also measured were two separate `0xCE00` entry call RVAs, `0xBF364` and
`0xBF47F`, not preceded by an eligible `0xD4A0` entry in this capture.

**STATIC (prior Stage88/91 original-DLL audit; freshly rechecked by Stage92):**
`0xEB1E` belongs to `0xE0E0`, `0x11021` belongs to `0x10E70`, and each
direct `E8` targets `0xD4A0`. `0xD786` is owned by `0xD4A0` and calls
`0xCE00`; both `0xBF364` and `0xBF47F` belong to `0xBE830`. On
2026-10-17 the operator's WSL run of the published Stage92 auditor returned
`NEW_RUN_DIRECT_OUTER_AND_INNER_CALLS_SAME_THREAD_SEQUENCE_OBSERVED`.
Independently, the analyst retrieved the original `5868USB.dll` from
private `HTKPA_CORE_20261016_012322.zip`, measured the pinned SHA256 and
reran the **same published** auditor against the exact private archive:
identical 6 hits / 2 paired callsites / 11 ms and 10 ms; exit 0. Thus
original PE `E8 rel32`, `.pdata` owners and ASLR checks are **PASS** for
this bounded, new-run temporal result.

**LIMIT:** two separate same-thread time windows are not two proven complete
call-stack identities. The manifest does not establish whether Manager
completed an import, crashed, or wrote a CLO; `launched_by_tool=false`
specifically does not establish a `--fresh` launch by the runner. This new
run cannot identify the external caller of the *older* Stage89 run or the
historical Stage64 instance.

## Offline acceptance after operator delivery

`audit_outer_caller_capture.py` reads the private tarball and original DLL
as inert data. It requires both hooks, original-runtime SHA, correct ASLR
PCs, bounded counts, clean field/hook reads and pinned caller `E8 rel32`
bytes plus `.pdata` owner. For each recognized outer caller followed within
2,000 ms on the same thread by the known `0xD786 → 0xCE00` inner edge,
it emits a **sanitized, new-run temporal-sequence** conclusion. Separate
nonambiguous windows can coexist; multiple eligible prior outer hits for
one inner hit, unknown/indirect return addresses, missing inner hits,
or cross-thread events remain `UNBOUND` instead of inventing ancestry.

This is still **not an exact same-invocation stack identity** without
additional stack/exit evidence, and cannot retroactively identify the
Stage89 or historical Stage64 path. No exact WAV pathname, rates, NAM
hash, successful CLO or crash diagnosis is claimed.

The **original-PE recheck gate is closed** by the operator run and an
independent repeat in the analysis sandbox. For reproducibility only,
the exact operator WSL command was:

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python research/htkpa/stages/stage92/audit_outer_caller_capture.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --capture research/_LOCAL_FILES/frida_captures/frida_20261016_212623_230331_8g348j9d.tar.gz \
  --out research/_LOCAL_FILES/stage92_outer_caller_private_report.json
```

The full sanitized report and private verification checkpoint were inspected
and stored in the canonical RE_HTKPA folder. No extra Frida capture is
required for Stage92; do not repeat an import to satisfy the offline gate.

Ghidra 12.1.4 was also restored from four pieces in that same private folder,
with a SHA-verified portable JDK 21. Headless import, auto-analysis and
project save of this exact original DLL all returned **PASS**. That verifies
the PE can be analyzed in a restored Ghidra environment; **a fresh Ghidra
decompilation claim is not needed** to accept the Stage92 PE-byte auditor.

## Current offline gates

- Stage92 protocol/synthetic negative controls: **32/32 PASS**.
- All `test_htkpa_stage*.py` tests: **354/354 PASS**.
- Universal runner offline self-test: PASS.
- Original DLL SHA256 measured independently from private CORE ZIP: **PASS**.
- Exact Stage92 auditor against real DLL + real tarball: **PASS twice**
  (operator WSL and independent sandbox run).
- Original DLL Stage91 static findings remain the accepted upstream
  direct-call inventory; Stage92 independently rechecks the observed subset.
- Restored Ghidra 12.1.4 original-DLL headless import/analysis/save: **PASS**.
- **New-run temporal callsite evidence is accepted**; full invocation stack,
  historical Stage89 caller, Manager outcome and completed CLO remain unproven.

The original DLL, original NAM file, all Frida archives and full Ghidra
decompilation remain in the canonical private
[RE_HTKPA](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK)
workflow, not in the public repository.

The [private Stage92 handoff](https://drive.google.com/file/d/1KcxkYG5OvL7bGtj2VsKHm4O04KYYuTsA/view)
is maintained in RE_HTKPA. The raw native archive and
`HTKPA_STAGE92_ORIGINAL_PE_AUDIT_VERIFIED_20261017.json` stay private.
`HTKPA_STAGE92_PRIVATE_VERIFIED_CHECKPOINT_20261017.zip` contains the
re-imported private Ghidra project, headless log and sanitized auditor report;
its ZIP integrity passed. The Stage90 checkpoint remains available.
