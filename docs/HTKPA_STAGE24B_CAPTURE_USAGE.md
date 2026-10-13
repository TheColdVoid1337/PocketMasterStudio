# Stage24B — one-click Windows generator capture

## Environment

Use the user's already-installed Windows x64 Python + Frida at `research/_LOCAL_FILES/stage23w_native/.venv/Scripts/python.exe`. Do **not** install a second Windows venv or Frida. Linux `.venv` is activated in WSL for reproducible shell setup only; it cannot load the Windows PE DLL.

Source and offline tests are supplied in the private handoff package `Stage24B_WINDOWS_CAPTURE_CHECKPOINT.zip` for extraction to:
- `research/htkpa/stages/stage24b/one_click_capture.py`
- `research/htkpa/stages/stage24b/test_one_click_capture.py`
- `docs/HTKPA_STAGE24B_CAPTURE_USAGE.md` (this usage document is also included in the ZIP).

**Source delivery state:** script ZIP available to the user; Python source is **not claimed present in GitHub until the user unpacks and pushes**.

## How it operates

Windows Python attaches to an existing Sonicake Manager or spawns `C:\Program Files\Sonicake\Sonicake Manager\Sonicake Manager.exe`. The Frida module observer handles loaded or lazy-loaded vendor DLL. Hooks at RVA `0xBD12` and `0xB981` (from preferred `0x180000000`) collect selected generator/filter scalar fields, exact IEEE-754 hex bits and stable per-session filter object pointers. Both pinned vendor SHA256 and runtime-loaded DLL SHA256 must match `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa` before reporting verified results.

Operator performs one ordinary authorized NAM→CLO import. Termination requires either (a) a changed CLO file in a user-selected output directory stable for several seconds, **plus observed generator hits**, or (b) the operator pressing Enter **after import completes**. Hook silence never implies completion. The Manager remains open; the Frida session detaches.

A strict archive allowlist protects private assets. The `tar.gz` contains only session `manifest.private.json`, `native_events.private.jsonl`, `STAGE24B_HANDOFF.md` and optionally `ready.private.json`. No vendor DLL, NAM, WAV, CLO, memory/audio arrays or venv files are included. Outputs are placed in ignored `research/_LOCAL_FILES/stage23w_native/stage24b_captures/`. ANSI log tags `SETUP`, `HOOK`, `DLL`, `CAPTURE`, `WAIT`, `DONE`, `WARN`, `ERROR` have distinct colors.

## Validation and limits

Portable offline tests validate changed-CLO detection, archive roundtrip/hash, strict allowlist, and no leakage of test DLL/WAV/CLO. Native Windows Frida execution **cannot** be verified until the user runs it. The new capture is intended to resolve the Stage23Z coefficient-generator parameter mismatch and does not itself prove exact native FIR coefficient parity, full resampler, or four Marshall gains.
