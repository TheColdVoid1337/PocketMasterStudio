# Stage48 — one-hook METADATA-ONLY native post-fractional validation

**Status: NATIVE FRACTIONAL RUNTIME METADATA OBSERVED (114 f64); STABLE CLO COMPLETION UNVERIFIED. Color/PID/state-loss fixes are committed but NOT YET re-tested on Windows.** Stage47 `STATIC_LAST_STAGE_RETURN_SITE_VERIFIED` identifies the original `r8b::CDSPResampler24::process()` last-stage return at RVA **`0x1190C`** (VA `0x18001190C` for preferred image base), with returned count in EAX and caller's output pointer in `*[R15]`. Previous RTTI validates the templated `CDSPFracInterpolator` vtable at RVA **`0x245170`**. Live reachability, memory lifetime, stability and final native 48-kHz samples are **NOT YET PROVEN**.

## Safety contract — do not reinterpret as a finished converter

`metadata_probe.py` is a dedicated **Windows x64 Frida** script that **never** reads or copies any f64 audio bytes. It never spawns or terminates the Sonicake Manager. It uses precisely **one** `Interceptor.attach()`, at original DLL RVA `0x1190C`. It does NOT install the historically crash-prone pair at `0xC220` and `0xC838`, and does not hook `0x135C0` directly.

It first attaches an inert module observer. **Before any hook**, the Windows host checks both the user-supplied original DLL and the *actual loaded module's backing file* SHA-256 against pinned digest:

`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`

Only after that check does it request the agent's `arm()` operation. At the first eligible post-call site, its guarded callback checks:

1. Last-stage processor at `[RBX+0x50]` and its vtable at `*[processor]` equals `module_base+0x245170`;
2. `EAX` output sample count is **1..4096**;
3. `R15` output pointer-reference and dereferenced `*R15` are safely mapped and readable; returned buffer pointer is 8-byte aligned; the **range is mapped** for `8*EAX` bytes (no data read);
4. Records just pointer address, count, vtable and site, plus observation index. It ignores further events after the first valid metadata observation and refuses to read audio.

Guard rejection, an oversized count, a missed call or unstable conversion is an incomplete diagnostic, **not numerical parity**. The callback does not know the true allocation capacity merely because a memory region is mapped.

The Windows host watches a previously existing user-selected CLO output directory. **PASS requires both** a valid post-fractional metadata event AND a **new/modified nonempty CLO stable for 3 seconds** compared with the pre-hook snapshot. No old CLO counts as a new conversion.

The script creates only a local `stage48_YYYYMMDD...` folder containing `events.jsonl` and `manifest.json` (addresses/metadata only) under the ignored `research/_LOCAL_FILES/frida_captures/`. No raw DLL, sample, full audio file, NAM or CLO contents are sent to the repo.

## Prerequisites

- Exactly one **already-running** Sonicake Manager, before launching this tool.
- Original user-owned DLL available in one of the existing ignored paths: `research/_LOCAL_FILES/vendor/5868USB.dll` or `research/_LOCAL_FILES/5868USB.dll`. If different, set `FRIDA_ORIGINAL_DLL`.
- Windows 64-bit Python with Frida at `research/_LOCAL_FILES/stage23w_native/.venv/Scripts/python.exe`, reused from earlier stages. If different, set `FRIDA_WINPY`.
- Actual **existing** Windows folder where the ordinary conversion writes its CLO, visible from WSL. Set `FRIDA_WATCH_CLO` to that exact WSL path, not a guessed directory.
- User explicitly performs exactly one normal NAM→CLO import/conversion **after** seeing `[HOOK]`. Do not run another in the same session.

## Source and DLL preflight (no Manager, no Frida)

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

# Point to whichever ignored original DLL copy is already available:
python research/htkpa/stages/stage48/metadata_probe.py \
  --self-test --dll research/_LOCAL_FILES/vendor/5868USB.dll

# Optional additional Stage47 static verification if llvm-objdump installed:
python research/htkpa/stages/stage47/audit_static_return.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage47_static_return.json
```

The self-test runs on WSL/Linux and verifies the one-hook/no-waveform source contract, and the exact original SHA. Stage47 independently verifies native disassembly anchors.

## One controlled Windows run through WSL

First open Sonicake Manager (one instance). In WSL:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod

# IMPORTANT: replace with the real existing output folder from YOUR installation.
export FRIDA_WATCH_CLO="/mnt/f/REPLACE_WITH_REAL_CLO_OUTPUT_FOLDER"

bash research/htkpa/stages/stage48/STAGE48_WSL.sh
```

Wait until `[HOOK] One module-SHA-verified metadata-only site armed`, then perform exactly one normal conversion in the Manager. Do not attempt the previously crashing two-hook recipe.

After a verified event and new/changed stable CLO, the tool detaches and prints `METADATA_GUARD_PASS_CLO_STABLE`. If the configured watch directory is absent, the wrapper fails *before running Frida*; never use an invented path. If no new CLO, no eligible fractional vtable, or attach/hook failure, preserve the incomplete `manifest.json` and `events.jsonl` for analysis. The program has a default 600-second timeout and does not kill the Manager.

## Acceptance

**`METADATA_GUARD_PASS_CLO_STABLE`** means a specific original DLL executed the native post-return site with the dynamically identified fractional specialization, a bounded, mapped output pointer/count was observed, and a distinct stable CLO appeared. This is **only a metadata/runtime reachability PASS**.

It does **not** validate:
- numerical values of the vendor's 48-kHz output (never sampled in Stage48);
- genuine allocated buffer *capacity* beyond mapped region bounds, lifetime on another invocation, or proven Frida stability across builds;
- exact r8brain release inside Sonicake or any NAM training/CLO-model equivalence.

Only after independently verifying the report and that Manager remained stable should a **separate future Stage49** propose a *single-hook bounded binary capture* at exactly this site, without collecting audio in this run.

**No Stage48 Windows or Frida capture has been performed by the assistant.** Read-only offline test and GitHub files do not constitute user execution evidence.

## 2026-10-14 first Windows attempt: BLOCKED before hooking — process not found

Actual user WSL run called `STAGE48_WSL.sh`; the offline self-test and original DLL SHA checks passed, and the user's CLO directory exists at `/mnt/c/Users/TheColdVoid/AppData/Roaming/Sonicake/Sonicake Manager`. The initial Windows process-discovery guard then raised `ValueError: Open exactly one Sonicake Manager before running, or supply --pid`. Original manifest timestamp **2026-10-14T10:03:09.550523+00:00**, `status=BLOCKED`, `hook_count=0`, `state={}`; no Frida session attached to Manager, no interceptor installed, no waveform captured. This is NOT a failed converter / crash or a native-output observation.

The script's original automatic discovery required **both** 'sonicake' and 'manager' in the executable name. This may not describe the installed application binary, or the Manager may simply have been closed. Do not invent a PID or relax the guard by attaching to an arbitrary process.

A no-hook process-discovery mode has now been added to `metadata_probe.py`:

```bash
# Start exactly one Manager instance FIRST, no conversion yet.
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
export FRIDA_WATCH_CLO="/mnt/c/Users/TheColdVoid/AppData/Roaming/Sonicake/Sonicake Manager"

# No Frida attach()/Interceptor.attach; just enumerate relevant Windows names/PIDs.
bash research/htkpa/stages/stage48/STAGE48_WSL.sh --list-processes
```

If this lists the true Sonicake Manager process, use its exact **PID** instead of relying on strict automatic matching:

```bash
bash research/htkpa/stages/stage48/STAGE48_WSL.sh --pid <ACTUAL_MANAGER_PID>
```

Replace the placeholder with the number actually observed and check that the application has the expected Windows executable path in Task Manager -> Details (or Windows PowerShell `Get-CimInstance Win32_Process`) before attaching. The `--pid` option was already supported; the new discovery command does not arm a hook or create a conversion manifest. If Frida lists no matching name, inspect actual Windows process names, ensure Manager is open, and **STOP** instead of targeting another process. Only after `[HOOK]` should one normal NAM→CLO operation start.

This initial attempt leaves Stage48 **PREPARED / RUNTIME NOT OBSERVED**, with process-name diagnosis open. Previous acceptance/security requirements remain unchanged.

## 2026-10-14 — Actual first ATTACHED run: confirmed fractional output metadata, but old manifest lied

The user supplied the **actual events.jsonl** and manifest from a native Windows run on the original DLL:

- Module loaded: `5868USB.dll` base `0x7ff862660000`; `hook_attached` at `0x7ff86267190c` (RVA **`0x1190c`**, precisely as source predicted).
- First return was rejected as `returned EAX count zero or over defensive bound` (observed index 1). This is just a guard rejection, **not proof of native error**.
- **Observed index 18 succeeded:** event `metadata_hit valid=true`, thread `17632`, last-stage vtable `0x7ff8628a5170` (module base plus RVA **`0x245170`**); pointer `0x1fe13716b80`, **`114 f64` = `912 bytes`** and buffer-mapped-range check `true`.
- **No actual audio samples were read. No stable CLO was verified.** The user interrupted waiting with Ctrl+C.

The former Stage48 host had an instrumentation/reporting bug: `execute()` held state locally, and a `KeyboardInterrupt` unwound it before returning; `main()` wrote `state={}`, `hook_count=0`, `status=BLOCKED`, although persisted events prove **1 hook and a genuine valid native fractional metadata observation**. **Do not use that stale manifest to invalidate the event journal.** The correct research status is `NATIVE_FRACTIONAL_METADATA_OBSERVED_CLO_UNVERIFIED`, not an established full NAM→CLO PASS and not a failed resampler.

### UX restoration / regression fix (code changed, native rerun not yet performed)

- **Automatic Manager PID discovery restored:** start one Manager first; Stage48 now selects the unique Frida process whose executable name contains `Sonicake`, without requiring a manually typed PID. Explicit `--pid` remains as a fallback; ambiguous/non-Sonicake targets are rejected.
- **Colorful console restored:** colored `[TARGET]`, `[HOOK]`, `[META]`, `[CLO]`, `[WAIT]` and `[STATUS]`; immediate success notification shows 114-f64-like result instead of waiting silently; an update appears every ~15 seconds.
- **CLO watcher improved:** scans nested `*.clo` folders by stat metadata, detects new/changed nonempty files, and requires 3-second stability. It never reads CLO contents.
- **Windows APPDATA autodiscovery:** WSL shell wrapper calculates the current actual Windows user's `%APPDATA%\Sonicake\Sonicake Manager` through the Windows Python interpreter; manual `FRIDA_WATCH_CLO` overrides it when desired. No hardcoded user names in shell source.
- **Operator Ctrl+C is now lossless:** shared state is preserved and `events.jsonl` is re-read before writing the manifest. If hook and metadata happened but CLO was not verified, manifest says `METADATA_OBSERVED_OPERATOR_INTERRUPTED`, `hook_count=1` and contains the last valid metadata. No false full PASS.
- **Regressions:** local `--self-test` now includes synthetic replay of the user's exact sequence (module_found, hook_attached, first rejection, valid 114-f64 metadata) and a nested fake CLO directory test. Running this self-test does NOT load Frida or the vendor DLL.

**New preferred command — Manager already open, no PID required:**

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

# Optional: omit this line; WSL wrapper now automatically detects
# the actual Windows user's APPDATA\Sonicake\Sonicake Manager directory.
export FRIDA_WATCH_CLO="/mnt/c/Users/TheColdVoid/AppData/Roaming/Sonicake/Sonicake Manager"

bash research/htkpa/stages/stage48/STAGE48_WSL.sh
```

Wait for `[HOOK]`, then one normal conversion. The console should print a `[META]` event upon observing actual returned f64 count. A new/changed stable CLO plus valid metadata is still mandatory for `METADATA_GUARD_PASS_CLO_STABLE`. Otherwise the runner preserves a truthful partial result on timeout or Ctrl+C. The **fix is in GitHub but has not been verified on the user's Windows session**; run the WSL offline `--self-test` before hooking. Never escalate to dual input/output Frida hooks after a crash.

### Later safety refinement: stop if Manager disappears

The restored Windows host checks the selected PID approximately every 3 seconds using process enumeration only (no additional Frida hooks or native memory operations). If Manager exits unexpectedly, Stage48 returns `BLOCKED_MANAGER_EXITED` or `BLOCKED_MANAGER_EXITED_AFTER_METADATA`, preserving the already logged event journal and recovered metadata. This avoids silent waiting until timeout after a genuine process exit; an interrupted operator session and a process crash are kept distinct.

**Current engineering validation:** read-only review of the source, structural invariants and V8 compilation of the embedded Frida JS were checked in the assistant environment; the updated Python/WSL files still require the user-side `--self-test` and first controlled Windows run. Do not report the UX fix as Windows-verified until those results arrive.
