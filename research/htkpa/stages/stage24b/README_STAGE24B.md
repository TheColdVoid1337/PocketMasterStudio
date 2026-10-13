# Stage24B — Windows one-click native FIR generator capture

**Status:** tracked launcher and Python source are now in `main`. **No new native Windows capture has been run by this ChatGPT session**; the next measured results must come from your PC.

## Quick start (Windows, not WSL)

1. From your normal WSL shell in the repo, run `git pull --ff-only origin main`. If you have pending local changes, commit/stash before pulling.
2. In **Windows Explorer**, open `research\htkpa\stages\stage24b\` inside this checkout and double-click **`STAGE24B_CAPTURE.bat`**. The BAT enters the repository root itself.
3. The launcher uses the already-installed Windows x64 Python + Frida environment at `research\_LOCAL_FILES\stage23w_native\.venv\Scripts\python.exe`. If missing, it tries `py -3` (which must have `frida` installed). Do not use the **Linux WSL `.venv`**.
4. At the optional **CLO output folder** prompt, enter the Windows folder that will receive an exported `.clo`. If unknown, press Enter to use **manual completion**.
5. Wait for `[READY]`. Perform **one ordinary NAM→CLO import** in Sonicake Manager, using your existing normal local files and app. If a changed nonempty CLO becomes stable for 5 seconds **and** real paired generator hooks fired, it finishes automatically. Otherwise **press Enter in the BAT window only when the Manager import has actually finished**.
6. Wait for `[ARCHIVE]` and `[RESULT]`. Even errors/timeouts produce a marked diagnostic `tar.gz` unless the very initial Python command fails before starting.
7. Attach **the generated `.tar.gz`** to the new ChatGPT research chat. It is enough; you do not need Codex.

Default archive location:

```text
research/_LOCAL_FILES/stage23w_native/stage24b_captures/stage24b_YYYYMMDD_HHMMSS.tar.gz
```

Successful status is `NATIVE_SCALARS_CAPTURED`. Status `BLOCKED`, `INCOMPLETE` or `INTERRUPTED` is **not a successful native trace**, but its diagnostic archive is still useful.

## What gets recorded

Two hooks only, both ASLR-safe by RVA:

- `0x18000BD12` / RVA `0xBD12`: filter object and f64 `cutoff`, `quality`, `attenuation`, `gain`.
- `0x18000B981` / RVA `0xB981`: same filter identity, generator `G_before_floor`, integer G, `theta`, `gamma`, index, Bessel `beta`, denominator and offset, with **exact IEEE-754 hexadecimal bits**.

The pinned original on-disk DLL SHA-256 and the hash of the **DLL actually loaded by Manager** are checked. Completion never means merely “hooks went quiet”; it requires observed matching filter↔generator events plus either an explicitly confirmed import or a newly changed stable CLO file. Manager remains running after the tool detaches. It does not patch original DLL bytes or issue device commands.

The archive contains **only**:

```text
stage24b/manifest.json
stage24b/native_events.jsonl
stage24b/STAGE24B_HANDOFF.md
stage24b/ready.json
```

No original DLL, NAM, WAV, CLO, RAM/FFT arrays, local account files or Python environment are included. All session material stays in Git-ignored `research/_LOCAL_FILES/`. The archive is re-opened and every allowlisted member's SHA-256 verified after writing.

## Extra options / troubleshooting

From **Windows PowerShell** in the repository root:

```powershell
research\_LOCAL_FILES\stage23w_native\.venv\Scripts\python.exe research\htkpa\stages\stage24b\one_click_capture.py --pid 12345 --watch-dir "D:\CLO Exports" --timeout 1200
```

Options: `--pid` for explicit existing Manager; `--exe "C:\...\Sonicake Manager.exe"` for a nondefault installed executable; `--dll "C:\...\5868USB.dll"` for a verified original; `--timeout` seconds (default 900, maximum 7200); `--stable-seconds` (default 5).

- **No generator events:** Manager may have instantiated the filter before attachment; close Manager, re-run BAT and let it launch a fresh Manager *before* importing.
- **DLL mismatch:** do not substitute a different DLL; check original `research/_LOCAL_FILES/vendor/5868USB.dll`, required SHA `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
- **Frida missing:** reuse or restore the existing private Windows Frida environment; don't install into WSL. From Windows Python use `python -m pip install frida==17.6.1` inside an isolated venv if required.
- **No auto-completion:** manually press Enter *after* import finishes; automatic detection is limited to changed `.clo` files inside the chosen folder.
- **Insufficient rights/Frida attach denied:** run the script under a Windows user with permission to debug their Manager process; do not disable security software or modify the DLL.

## Offline checks

These tests require **no** Frida and don't execute the DLL:

```powershell
py -3 research\htkpa\stages\stage24b\one_click_capture.py --self-test
py -3 research\htkpa\stages\stage24b\test_one_click_capture.py
```

They exercise completion detection, filter↔generator pairing, the archive allowlist, integrity hashes and exclusion of fixture `DLL/WAV` files. Actual hook/Manager behavior is not validated until a Windows run.

## Why this capture matters

Stage23Z corrected the original reconstruction's omitted `pow(window,gamma)`, reducing maximum coefficient error from `1.6025e-6` to `9.28255e-10`, still not exact. Stage24B aims to read **native source parameters**, distinguish the 1417- and 1543-tap instances and find the first error in the static coefficient generator. Do **not** tune theta/gamma to match the native coefficients. Do not claim four independently computed Marshall gains, complete resampler or CLO parity.

**Main handoff for the next chat:** [HTKPA_CANONICAL_HANDOFF_2026-10-13.md](../../../../docs/HTKPA_CANONICAL_HANDOFF_2026-10-13.md).
