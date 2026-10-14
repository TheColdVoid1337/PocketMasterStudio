# Stage48 — native post-fractional metadata and CLO completion gate

**State of research: METADATA_GUARD_PASS_CLO_STABLE (original DLL runtime observation and stable CLO CONFIRMED; binary sample parity still NOT TESTED). Managed GUI shutdown bug fixed in shared tools but awaits Windows rerun.**

Stage47 statically identified the original Sonicake native last-stage return site RVA `0x1190C` and templated fractional vtable RVA `0x245170`. An actual Stage48 Windows observation of the SHA-pinned original `5868USB.dll` produced the following evidence:

- One hook was attached at the expected address `0x7ff86267190c` for module base `0x7ff862660000`.
- Observation #1 was rejected for zero/out-of-bounds return count.
- Observation **#18**, thread `17632`, confirmed `metadata_hit valid=true`; actual vtable `0x7ff8628a5170`, which equals module base + `0x245170`; **114 f64 / 912 bytes** output span at `0x1fe13716b80`, mapped/readable.
- The previous Windows runner's **manifest falsely recorded `BLOCKED`, `hook_count=0`, `state={}`** after Ctrl+C, despite the independently retained `events.jsonl`. This is corrected research status, NOT native final-audio parity.
- No sound sample bytes were read and no new/changed stable CLO completion was demonstrated by that run.


## 2026-10-14 — full original native metadata and CLO completion PASS (user supplied archive)

The actual user completed a normal NAM→CLO conversion using the canonical universal `tools/FRIDA_WSL.sh` and stage-only `frida.json`:

- `--preflight`: real Windows EXE **exists** at `C:\\Program Files\\Sonicake\\Sonicake Manager\\Sonicake Manager.exe`, CLO folder **exists** at `C:\\Users\\TheColdVoid\\AppData\\Roaming\\Sonicake\\Sonicake Manager`, and universal WSL/Python self-tests all passed (**11/11** offline tests).
- Universal Frida spawned its OWN Sonicake Manager PID **4524** in suspended mode and then resumed it after attaching the observer. The real `5868USB.dll` SHA was verified before arming **one** guarded metadata hook.
- `metadata_hit` at observation **18**: dynamically recognized vtable `0x7ff85e6d5170` (module base `0x7ff85e490000` + RVA `0x245170`); one output block **114 f64 / 912 bytes**; result-pointer mapped/readable. No f64 audio samples read.
- Newly modified output `C:\\Users\\TheColdVoid\\AppData\\Roaming\\Sonicake\\Sonicake Manager\\clo\\clofile.clo` became stable: **8840 bytes**, not its actual content. The matching `manifest.json` from the user-provided private `frida_20261014_112002_862142.tar.gz` states `status=METADATA_GUARD_PASS_CLO_STABLE`, `completion_verified=true`, `hook_count=1`, `runtime_verified=true`.
- **Independent lifecycle bug:** After the observer succeeded, `process_cleanup_status=GRACEFUL_CLOSE_FAILED`, because `ctypes.WinDLL("user32").EnumWindows` was called with **one** argument despite `argtypes=(callback,LPARAM)`, yielding `this function takes 2 arguments (1 given)`. The universal runner exited **code 3** for failed requested automatic GUI shutdown, **not** for native metadata/CLO failure. The user reported having to close Manager manually.

**Universal fix:** `tools/frida_guarded.py` now calls `user32.EnumWindows(visit, 0)`, passing the required LPARAM, and `tools/test_frida_universal.py` adds a dedicated mocked-Win32 regression ensuring both parameters and PID-scoped `WM_CLOSE` (no unrelated window closed). Generic teardown now emits separate status messages for script unload, Frida session detach and GUI shutdown, so any future UI stall can be located. The fix does **not** add hooks, audio reads or change Stage48 JSON. **These code fixes have NOT YET been re-executed on the user's Windows host**, so successful automatic closure remains pending verification.

Importantly, Stage48 acceptance means only: actual vendor fractional processor executed and produced guarded output metadata during a conversion that created a stable CLO. It does **not** yet measure numerical values of the original 48-kHz post-fractional waveform or the full NAM fitting/serialization algorithm. Stage49 binary capture remains a distinct research decision, not implicit in this success.

## Stage48 is configuration and evidence ONLY

The canonical shared code is under `tools/`, not copied into this directory:

| Purpose | Canonical path |
| --- | --- |
| Universal Frida CLI | `tools/frida_capture.py` |
| Universal WSL → Windows launcher | `tools/FRIDA_WSL.sh` |
| Generic, strictly configured guarded-metadata library | `tools/frida_guarded.py` |
| Shared documentation and rules | `tools/FRIDA.md` |
| **This stage's only executable parameters** | **`research/htkpa/stages/stage48/frida.json`** |
| Measured evidence (no proprietary data) | `research/htkpa/stages/stage48/evidence.json` |
| Private run output (ignored) | `research/_LOCAL_FILES/frida_captures/frida_*.tar.gz` |

No `metadata_probe.py`, `STAGE48_WSL.sh` or other stage-specific Frida implementation is maintained after migration. To add features for future stages, extend the shared validated `tools/` library/CLI, update offline regression tests, and select different values in a new stage-local `frida.json`.

## Offline sanity checks

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python tools/frida_capture.py --self-test
python -m unittest discover -s tools -p 'test_frida_universal.py'
bash -n tools/FRIDA_WSL.sh
```

All these commands are offline; they do not import Sonicake DLL as executable code, attach Frida or run conversion.

## Windows path preflight and actual guarded run (Manager auto-starts / auto-closes)

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod

# Validate actual Windows EXE and exact CLO folder before any hook or spawn.
bash tools/FRIDA_WSL.sh --config research/htkpa/stages/stage48/frida.json --preflight

# Once preflight PASSES, ensure Manager is CLOSED and start one managed experiment:
bash tools/FRIDA_WSL.sh --config research/htkpa/stages/stage48/frida.json
```

**Close any existing Sonicake Manager first.** The canonical `frida.json` now contains these explicit Windows paths:

- `lifecycle.executable`: `C:/Program Files/Sonicake/Sonicake Manager/Sonicake Manager.exe` — the previous default installation path used by the universal tool, **not yet verified against this user's actual Windows installation**. If missing, change this one JSON field to the actual installed EXE path.
- `completion.path`: `C:/Users/TheColdVoid/AppData/Roaming/Sonicake/Sonicake Manager` — the user-confirmed folder where CLO outputs are expected.

`lifecycle.start=fresh` refuses to close or attach an existing process; with Manager closed it uses **Frida spawn** to start its own suspended process, attaches the one guarded observer, and then resumes the app. The normal callback still checks SHA of the actually loaded DLL before arming the hook. The wrapper does not ask for PID, and no CLO folder needs to be typed.

On conclusion, `lifecycle.close=if_launched` **attempts graceful WM_CLOSE only for the PID it spawned**, waits up to 8 seconds and records `state.cleanup_status`. It never force-kills a resumed GUI; if no window responds or closure fails, the app may remain open and the manifest reports this. A suspended process owned by the tool can be cancelled if startup failed before resume. Automatic startup/shutdown does not click buttons or import a NAM: after `[HOOK]`, manually perform ONE conversion.

After the first **`[HOOK]`**, perform ONE normal NAM→CLO operation. The `[META]` event confirms a native fractional output pointer/count **but never reads audio**. Only if a new/changed nonempty CLO is also stable for three seconds does the status become `METADATA_GUARD_PASS_CLO_STABLE`. A Ctrl+C leaves `METADATA_OBSERVED_OPERATOR_INTERRUPTED` if an event was already logged, and preserves the event journal and truthful manifest. A Manager exit or timeout remains diagnostic, not PASS.

The user needs to share **manifest.json and events.jsonl** (or console output) from the new private archive. No NAM/CLO/DLL/audio content should be included.

## Invariants and limits

- One hook only, at RVA `0x1190C`; dynamic processor vtable must equal `module+0x245170`.
- Positive `EAX` count 1..4096; output double-pointer from `R15` must be mapped/readable; up to 256 observations until first valid metadata event.
- Valid address-space mapping is **not** proof of heap allocation capacity, long-term pointer lifetime, or numerical contents.
- Do not repeat the crash-associated two-hook setup `0xC220` + `0xC838`.
- **No vendor 48-kHz f64 audio bytes have yet been captured or compared** with the historical public r8brain output; Stage44/45 public and hybrid results do not establish final Sonicake parity.
- Stage48 migrated to the universal toolset in Git; **the new shared guarded implementation has not yet been user-run on Windows**. Treat static/self-test success separately from actual runtime completion.

## Historical source provenance

The former `research/htkpa/stages/stage48/metadata_probe.py` and `STAGE48_WSL.sh` are not maintained or used. Their original source and incremental fixes remain accessible through Git history. The original `events.jsonl` and false `manifest.json` continue to be local private inputs, and the correct research findings remain recorded in `evidence.json` and append-only `research/htkpa/RE_LOG.md`.
