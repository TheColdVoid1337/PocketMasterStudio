# Universal Frida capture — one codebase for all research stages

## Canonical architecture

- **Single supported entrypoint:** `tools/frida_capture.py`
- **Single WSL → Windows x64 launcher:** `tools/FRIDA_WSL.sh`
- **One reusable library for narrowly defined guarded observations:** `tools/frida_guarded.py` (imported by the entrypoint; NOT a stage-specific runner)
- **All per-stage instructions and pins:** `research/htkpa/stages/<stage>/frida.json`, `README.md`, `evidence.json`.
- **All private execution outputs:** ignored `research/_LOCAL_FILES/frida_captures/frida_*.tar.gz`, not committed.

**Do not create `stageNN_capture.py`, `STAGEN_WSL.sh` or modified copies of `tools/frida_capture.py` for future stages.** New capabilities go into the generic `/tools` modules as opt-in, validated config features; existing stage configurations must remain backward-compatible whenever possible.

## Managed application lifecycle (configured per stage)

The same universal `tools/FRIDA_WSL.sh` / `tools/frida_capture.py` also supports **automatic GUI application startup and graceful shutdown** for `guarded_metadata` runs. The stage JSON, **not Python code**, selects the Windows EXE and the exact CLO output directory:

```json
"lifecycle": {
  "executable": "C:/Program Files/Sonicake/Sonicake Manager/Sonicake Manager.exe",
  "start": "fresh",
  "close": "if_launched",
  "close_timeout_seconds": 8
},
"completion": {
  "type": "changed_clo",
  "path": "C:/Users/TheColdVoid/AppData/Roaming/Sonicake/Sonicake Manager",
  "recursive": true,
  "stable_seconds": 3
}
```

The EXE path is the *previous generic fallback assumption* and **must be verified** against the user's actual installation. The original CLO directory above was explicitly supplied by the user. Missing configured paths are reported clearly, **before starting the process or installing any hook**. Use absolute forward-slash Windows paths in JSON.

- `start=fresh`: refuse if another matching Manager process is running (never silently close someone else's app), otherwise use `frida.get_local_device().spawn([EXE])` suspended; attach the script and its module observer, then `resume(PID)`. Delayed **actual loaded DLL SHA validation** still happens before the one guarded hook is armed.
- `start=if_missing`: reuse a single running Manager without taking ownership, or spawn a new one. **Only a spawned/owned instance is auto-closed.**
- `start=attach_only`: legacy attach-only guarded behavior.
- `close=if_launched`: after result or interruption, unload/detach the one Frida hook, then request normal Windows **`WM_CLOSE`** for top-level windows of exactly the PID spawned by this invocation; wait at most `close_timeout_seconds`. If normal GUI shutdown fails, **leave the app open and flag cleanup_status**, without force-killing an active GUI or claiming cleanup worked. A failed startup before resume can cancel **only that tool-owned suspended PID**.
- `close=never`: leave even a newly launched process running after detaching.

The initial `--pid` option cannot be mixed with `start=fresh` or `start=if_missing` to avoid bypassing lifecycle ownership rules. All lifecycle metadata (`launched_by_tool`, `target_pid`, `target_resumed`, `cleanup_status`) is preserved in `manifest.json`.

Stage48 currently uses `start=fresh`, so **Manager should be closed before running the command below**; the tool will open and attempt to close its own instance. The conversion inside the GUI still needs to be performed by the user after `[HOOK]`: application startup/exit automation is **not** automatic NAM importing or mouse clicking.

## Usage — Stage48 (guarded metadata, no audio)

**Close** any existing Sonicake Manager first. The Stage48 JSON now starts its own suspended instance and closes it after the run.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

# Optional local dry-run (no Frida, no app attach):
python tools/frida_capture.py --self-test
python -m unittest discover -s tools -p 'test_frida_universal.py'
bash -n tools/FRIDA_WSL.sh

# One universal wrapper, stage specified only by its JSON:
bash tools/FRIDA_WSL.sh --config research/htkpa/stages/stage48/frida.json
```

The wrapper uses the existing Windows Python Frida venv and checks original `5868USB.dll` SHA. For Stage48 `start=fresh` it verifies Manager is closed, launches the configured EXE under Frida, and closes **only its own** PID gracefully after the run. No PID is needed. In `attach_only` mode it instead discovers one running target.

For `mode=guarded_metadata` the Windows host derives the CLO watch directory from the **Windows** `APPDATA` environment plus config `completion.appdata_subdir`. The Stage48 value is `Sonicake/Sonicake Manager`. Set `FRIDA_WATCH_CLO=/mnt/c/...` only for an override; in this case WSL checks it exists.

Wait for a confirmed **`[HOOK]`** and then perform ONE normal NAM→CLO conversion. Colored events `[TARGET]`, `[HOOK]`, `[META]`, `[CLO]`, `[WAIT]`, `[STATUS]` report what happened. A normal guarded success is **`METADATA_GUARD_PASS_CLO_STABLE`**, which requires (a) original DLL file and actual runtime module SHA matching the pinned SHA; (b) exactly one Frida hook at the declared RVA; (c) live last-stage vtable matching the declared vtable RVA; (d) a positive mapped/bounded output pointer/count without reading sample values; (e) a NEW/CHANGED CLO stable for three seconds. This is **not a native audio parity claim**.

If Ctrl+C interrupts the observer or Windows Manager disappears, on-disk events and mutable state are preserved into manifest; never discard a valid `metadata_hit` merely because the session did not complete.

## Configuration modes and backward compatibility

**Legacy default** (old configs without `mode`): any existing supported `sites[].fields` type `f64`, `f64_binary`, `reg_ptr`, etc. remains parsed in `tools/frida_capture.py`. For these older experiments the wrapper still supports `FRIDA_CONFIG=filename.json`, defaults to `tools/frida_examples/htkpa_stage24c_stack.json`, and retains the existing `FRIDA_AUTO_QUIET` behavior. Historical capture semantics are not retroactively reclassified as native final parity.

**`guarded_metadata`** is opt-in and deliberately narrower. It permits exactly **one** required site, **no `fields`**, and a predefined `processor_output` guard containing:

- `owner_reg`, `owner_offset`: register/offset holding processor pointer
- `vtable_rva`: expected processor RTTI vtable in the SHA-pinned module
- `count_reg`, `max_samples`: bounded 32-bit output sample count
- `output_ref_reg`: pointer to f64 output pointer
- `max_observations`: capped number of guarded callback opportunities

Only address/length/vtable/region metadata is recorded. The guard checks a *mapped readable region*, not allocated capacity or buffer lifetime, and never makes `readByteArray`, `readDouble` or `readFloat` calls. The guarded JS is generated from a strictly validated data schema; **raw JavaScript in JSON is forbidden**.

The `completion` object is `type=changed_clo`, exactly one of `path` (absolute Windows directory) or `appdata_subdir` (relative to Windows APPDATA), `recursive`, and `stable_seconds`. The CLI `--completion-dir` still overrides it. A completed CLO without valid metadata, or valid metadata without a stable CLO, does **not** constitute successful guarded validation.

## Diagnostics, logs and privacy

```bash
# Safe discovery: enumerate likely target processes, ZERO hooks
bash tools/FRIDA_WSL.sh --config research/htkpa/stages/stage48/frida.json --list-processes
```

Every run creates a fresh `frida_YYYYMMDD_.../` folder and a `frida_YYYYMMDD_....tar.gz` in `research/_LOCAL_FILES/frida_captures/`. The allowlisted archive includes normalized `config.json`, `events.jsonl`, `manifest.json`, `HANDOFF.md` and any explicitly permitted legacy `block_*.bin` captures. Guarded metadata mode emits **no binary payloads or audio arrays**.

Expected exception/timeout statuses include `METADATA_OBSERVED_OPERATOR_INTERRUPTED`, `METADATA_OBSERVED_CLO_UNVERIFIED_TIMEOUT`, `BLOCKED_TARGET_EXITED`, `BLOCKED_AGENT_ERROR`, `INCOMPLETE_TIMEOUT`. Only `METADATA_GUARD_PASS_CLO_STABLE` is a guarded full metadata+completion PASS.

### Offline contract tests

`python tools/frida_capture.py --self-test` and `python -m unittest discover -s tools -p test_frida_universal.py` exercise both legacy fields and Stage48 guarded mode, exact config pins, single-hook/no-audio guarantees, target PID selection, nested CLO metadata listing, and recovery of the real **114 f64 / 912 byte** Stage48 interrupted event pattern. If Node is installed, the suite syntax-checks the generated JavaScript.

No original DLL, audio, NAM or CLO files may enter Git; exact original DLL hashes and evidence/metrics alone are allowed.
