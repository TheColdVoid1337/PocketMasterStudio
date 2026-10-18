# Stage96 — bounded native function invocation identity probe

**Accepted runtime status (2026-10-19 Bangkok):** `RUNTIME_SAME_WRAPPER_INVOCATION_NAM_THEN_FITTER_OBSERVED`.
**Historical preparation state:** `STAGE96_NATIVE_INVOCATION_PROBE_READY_AWAITING_OPERATOR_CAPTURE` (superseded by the audited operator archive below).

The exact 2,902,016-byte original `5868USB.dll` is pinned by SHA-256
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
Previous stages are not restarted. Stage95's original-PE static `E8`/return
sites and Stage92's same-thread timing pairs are the inputs to this targeted
follow-up. See `research/htkpa/stages/stage95/README.md` for the static anchors.

## Question and proof boundary

Stage92 observed `0xEB1E → 0xD4A0 → 0xD786` and
`0x11021 → 0xD4A0 → 0xD786` in one thread, without proving a shared
outer function invocation. Stage95 identified two static wrappers, `0xFF40`
and `0x10E70`, that can call a NAM worker and a shared fitter.

Stage96 adds *optional* `mode: invocation_trace` to the universal scalar
Frida runner. It captures native `Interceptor.attach` function `onEnter` **and**
`onLeave` events, with Frida's per-invocation `this` state, a monotonic local
invocation ID, a same-thread active-parent ID, and module-relative return RVA.
There is no Stalker, code replacement, argument dereference, string/audio/model
read, memory mutation, or callback inside vendor code. The older scalar and
guarded modes remain unchanged.

Exactly eight reviewed original-PE **function entry** RVAs are allowed:

| Hook | RVA | Static role | Required to auto-quiet? |
|---|---:|---|---|
| `wrapper_ff40` | `0xFF40` | optional compiled wrapper | no |
| `wrapper_10e70` | `0x10E70` | wrapper of the Stage92 `0x11021` site | no |
| `nam_worker_e0e0` | `0xE0E0` | NAM/`getNamOutput` worker | yes |
| `wav_fitter_d4a0` | `0xD4A0` | Stage92 shared WAV/fitter function | yes |
| `clone_f940` | `0xF940` | compiled clone helper | no |
| `clone_10230` | `0x10230` | alternate clone helper | no |
| `resample_be830` | `0xBE830` | shared compiled resampler branch | no |
| `resample_ce00` | `0xCE00` | Stage92 resampler call destination | no |

Site limits: **4 entries per hook**, **96 event messages**, and **12 active
instrumented invocations per thread**. Exceeding any bound emits a trace-limit
marker, which permanently invalidates *proof promotion* for that capture.
Unpaired returns, wrong threads, non-LIFO nesting, missing hooks, mismatched
runtime DLL SHA, hook errors, changed config, or wrong exact return RVAs also
fail closed. Auto-quiet requires NAM and fitter entries, zero errors and
balanced recorded enter/leave counts. It is not a completion verifier.

## What the private auditor can prove

`audit_invocation_trace.py` reads only the allowlisted private
`frida_capture/*.json*` + `HANDOFF.md` files from the tarball and independently
SHA-checks the original DLL. All hooks and Frida runtime SHA must be verified.
The parser demands per-thread LIFO enter/leave pairing. A route is promoted
only when one **completed** `0xFF40` or `0x10E70` invocation has:

1. A direct child `0xE0E0` call with Stage95-pinned return RVA (respectively
   `0x10048` or `0x10F84`), fully returned;
2. A subsequent, direct child `0xD4A0` call with pinned return RVA
   (`0x100F0` or `0x11026`), fully returned;
3. Both children nested inside the **same** completed outer invocation.

Optional deeper evidence: `F940`/`10230` child and `BE830` grandchild with
pinned return RVAs, plus nested `CE00` at either return RVA `0xBF369` or
`0xBF484`. Each is reported separately. This identifies instrumented native
stack ancestry; it does **not** establish that the model/WAV/CLO is the same
data object, a particular result from the `-2.0` gate, startClone success,
correct DSP, or completed/importable `.clo`. No inter-thread causal identity
is implied.

## One WSL operator run (not run in the sandbox)

Close Sonicake Manager before `--fresh`. Use the canonical private original
DLL, then do **one** ordinary conversion after all `[HOOK]` messages; do not
automatically retry after a crash. The runner detaches after 15 s of quiet
once its minimal hook gates are met, or at 240 s timeout. A timeout/error
still preserves its bounded private journal. Operator can abort with Ctrl+C;
do not declare a clean conversion based solely on hooks.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python -m unittest discover -s tools -p 'test_htkpa_stage96.py' -q

python tools/frida_capture.py \
  --config research/htkpa/stages/stage96/frida.json \
  --module-file research/_LOCAL_FILES/vendor/5868USB.dll \
  --preflight --timeout 240

FRIDA_AUTO_QUIET=15 bash tools/FRIDA_WSL.sh \
  --config research/htkpa/stages/stage96/frida.json \
  --fresh --timeout 240
```

The archive is written to `research/_LOCAL_FILES/frida_captures/frida_*.tar.gz`;
it must stay private. Place the complete archive in the canonical private
Google Drive `RE_HTKPA` folder
`1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK` and share its filename. **Do not put
the raw archive, process details, event log, pointer addresses, model, or
audio in GitHub.**

For a local offline audit, substitute the actual created archive filename:

```bash
python research/htkpa/stages/stage96/audit_invocation_trace.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --capture research/_LOCAL_FILES/frida_captures/ACTUAL_STAGE96_ARCHIVE.tar.gz \
  --out research/_LOCAL_FILES/stage96_invocation_private_report.json
```

Store that report privately in `RE_HTKPA` too. The auditor emits a compact
public-safe outcome, while the full private report remains private. A local
synthetic positive unit test or JS mock is **not** runtime evidence.

## Offline verification completed for instrument construction

- Stage96-specific contract, negative fixtures and generated Frida-JS
  behavior tested with Node.js mock runtime, with no native target process.
- Original DLL SHA-256 and no-attach preflight verified in the sandbox.
- Universal runner regression suite passed independently.
- No Ghidra restart is required for this already pinned entry/return-site
  follow-up; static callsite gates are inherited from Stage95, not invented.

**Accepted Stage96 state remains “probe ready / runtime pending” until a
real Windows Frida archive is audited.**


## Accepted Stage96 operator capture — 2026-10-19 Bangkok

The operator-supplied **real Windows Frida** archive (SHA-256 `24340c1d00f44311376729a2ba8d2813cf774997f0240c8790a7ad6cfa4e0274`,
four allowlisted archive members) was independently audited with the published
`audit_invocation_trace.py` on the exact 2,902,016-byte original DLL
recovered again from the canonical private CORE ZIP. The SHA is
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`
for both that original PE and the Frida-reported loaded module.
Outcome: **`RUNTIME_SAME_WRAPPER_INVOCATION_NAM_THEN_FITTER_OBSERVED`**,
zero auditor reasons, all eight hooks installed, no Frida/field errors,
10 invocation entries paired with 10 leaves, no trace limits or LIFO errors.

**Direct stack-invocation relationship proved in this NEW run:**

- One `0x10E70` wrapper invocation contained `0xE0E0` direct child,
  return RVA `0x10F84`; within it, `0xD4A0` direct child, return RVA
  `0xEB23`, itself calling `0xCE00` with return RVA `0xD78B`.
- After `0xE0E0` returned, **that very same `0x10E70` instance** invoked
  a second direct child `0xD4A0`, return RVA `0x11026`, which called
  `0xCE00` again with return RVA `0xD78B`.
- Still inside that wrapper, a direct `0x10230` child (return RVA
  `0x110B2`) invoked `0xBE830` (return RVA `0x104E6`), which in turn
  invoked `0xCE00` at **both** static Stage95 callsites (return RVAs
  `0xBF369` and `0xBF484`). Every entered instance returned and all
  relationships were one thread's actual nested Frida invocation IDs.

**Evidence boundary:** This supports execution of these **function-call
relationships in a single observed outer invocation**, rather than merely
Stage92's separate temporal windows. It does not retroactively prove the
Stage92 windows shared a stack. The log does not observe branch values,
model/WAV object identity, success of vendor `startClone`, a completed or
loadable CLO, or numerical DSP parity. The runner reports
`CAPTURED_HOOKS_ONLY` and `completion_verified=false`; these flags are
preserved exactly. `launched_by_tool=false` is also preserved (no invented
process-launch claim). The raw tar and full private auditor JSON are stored
only in canonical private Drive `RE_HTKPA`; see public-safe
`runtime_evidence.json` for details.

**Next independent gate:** inspect a real output CLO artifact and its
provenance/hash if one exists from this operator run; do not infer CLO success
from function stack identity and do not request an automatic Frida rerun.
