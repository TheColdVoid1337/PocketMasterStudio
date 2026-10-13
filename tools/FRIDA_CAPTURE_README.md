# Universal Frida scalar capture (Windows x64)

Independent reusable observer for authorized local reverse engineering. No stage-specific logic. It uses Frida, does not patch bytes, and only records **bounded scalar field reads** at module-relative addresses; not a general raw memory dump. Field access is limited to supported x64 GPRs, typed reads and offsets ±4096. Maximum 64 sites, 16 fields/site and 10,000 hits/site (default 8). Never inject arbitrary JavaScript from config.

## Quick start

In WSL, `git pull --ff-only origin main`. In Windows PowerShell, at repository root:

```powershell
research\_LOCAL_FILES\stage23w_native\.venv\Scripts\python.exe tools\frida_capture.py --self-test
research\_LOCAL_FILES\stage23w_native\.venv\Scripts\python.exe tools\frida_capture.py --config tools\frida_examples\htkpa_stage24b.json --pid 12345 --module-file research\_LOCAL_FILES\vendor\5868USB.dll
```

Or run from Windows Explorer: double-click `tools\FRIDA_CAPTURE.bat` in a terminal with arguments, e.g. `tools\FRIDA_CAPTURE.bat --config tools\frida_examples\htkpa_stage24b.json --pid 12345`. Without arguments the launcher reports missing configuration (rather than silently picking probes). `--pid` attaches to a running process; `--exe PATH` spawns the specified app (and leaves it open). Prefer spawning when you need early constructor hits. **Use Windows Python with Frida installed; WSL Python cannot attach.**

After hooks are installed, perform the local action and press **Enter after completion**. Success requires target module hooks installed, runtime-loaded module SHA verified, at least one hit, and no Frida hook errors. Silence/timeout or pressing Enter early does not count as success. The observer does not attempt to decide whether a NAM→CLO conversion or other application task actually completed: it merely records the operator's completion signal.

Results go to ignored `research/_LOCAL_FILES/frida_captures/frida_<UTC timestamp>.tar.gz`, containing exactly `frida_capture/config.json`, `events.jsonl`, `manifest.json`, `HANDOFF.md`. Archive files are verified by hash on readback. **Review JSON configs and event contents before sharing**: scalar registers, pointers and chosen fields can still reveal application data. Private originals (DLL/WAV/NAM/CLO/FFT/RAM) are never automatically included.

## JSON schema

`module`: exact loaded basename, `sha256`: REQUIRED expected 64-digit SHA256 of the module, `image_base`: static PE base used when translating absolute VA into RVA (default `0x180000000`), `sites`: nonempty list of `{name,address,max_hits,fields}`. Addresses can be e.g. `0x18000B981` (static VA) or `0xB981` (RVA). Each field is `{name,type,reg,offset}`, with type `f64|f32|u8|u16|u32|u64|i32|ptr`, register one of `rax/rbx/rcx/rdx/rsi/rdi/rbp/rsp/r8..r15`, byte offset -4096..4096. f64/f32 include exact hexadecimal IEEE bit representation. Unsupported entries are rejected rather than guessed. Static addresses are ASLR-corrected against the actual loaded module base.

Full example: `tools/frida_examples/htkpa_stage24b.json`.

## CLI-only example (without JSON)

```powershell
python tools\frida_capture.py --module 5868USB.dll --sha256 fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa --site filter:0x18000BD12 --field filter:cutoff:f64:rcx:0 --field filter:quality:f64:rcx:8 --pid 12345
```

Use multiple `--site` and `--field` arguments. `--field` explicitly names its site so argument order does not matter. `--config` accepts a JSON base, and extra CLI sites/fields extend it. `--module-file` optionally verifies a local original DLL hash before attaching; the loaded module hash is always checked. `--timeout` defaults to 900s (max 7200). `--out` overrides ignored output path; **do not choose a tracked Git directory for native logs**.

### Research discipline

A hook's instruction boundary matters: `onEnter` captures registers before executing the instruction at that address. Confirm that the register contains a valid object at that exact site, and that memory contents are initialized. Correlate same-call objects by pointers/session; two adjacent traces are not automatically related. Results marked CAPTURED mean **valid observational session**, not parity or verification of the user's wider task. Keep Stage24B's earlier dedicated runner unchanged for the historical reproducer; this tool is its independent reusable successor.
