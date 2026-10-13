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

## Updated independent runnable checkpoint (2026-10-13)

The earlier Codex text described a ZIP containing a one-click launcher but **did not publish its Python source to GitHub**. To avoid another Codex run, a separately authored and offline-tested, self-contained package named `Stage24B_ONE_CLICK_CAPTURE.zip` is now supplied in the user conversation; its SHA-256 is `400f18f3f07bd78fce76a97273a3349c8517c8e580f9b007073cd818fa78d72d`. Its contents, extracted relative to the repo root, are `research/htkpa/stages/stage24b/{one_click_capture.py,STAGE24B_CAPTURE.bat,test_one_click_capture.py,README_STAGE24B.md}`. **These four files are not yet claimed as committed to GitHub.**

Use **Windows Explorer** to double-click `research/htkpa/stages/stage24b/STAGE24B_CAPTURE.bat`. It calls the already installed Windows x64 `research/_LOCAL_FILES/stage23w_native/.venv/Scripts/python.exe`, auto-attaches to the running Manager or spawns the default installed Manager, and asks for an optional CLO output directory. If provided, completion requires a *changed, stable* .clo and verified generator events; otherwise press Enter **after** the normal import has completed. Only two DLL hook sites are used: `0x18000BD12` (filter) and `0x18000B981` (generator). Preexisting original DLL and loaded DLL SHA-256 identities are checked; ASLR is computed from Frida's module base. Timeout, missing hooks or unconfirmed completion produce a clearly marked non-success diagnostic.

An archive `research/_LOCAL_FILES/stage23w_native/stage24b_captures/stage24b_<timestamp>.tar.gz` is automatically created and its whitelist/hashes verified. It contains **only** `stage24b/{manifest.private.json,native_events.private.jsonl,STAGE24B_HANDOFF.md}`. No WAV, NAM, CLO, vendor DLL, arbitrary logs, large RAM arrays or local venv files. The original Manager stays running when the helper detaches. Send the generated `tar.gz` to the RE chat; it is sufficient to compare exact IEEE754 `theta/gamma/cutoff/G` against the static reconstruction. 

Offline validation: four tests PASS (CLO-file stability, new CLO detection, strict archive allowlist/checksums including excluded test private blobs, and no false native-success claims), `py_compile` PASS and Frida JavaScript syntax (`node --check`) PASS. **Windows-native execution remains user-side and is not claimed here.**
