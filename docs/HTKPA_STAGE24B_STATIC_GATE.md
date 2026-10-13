# HTKPA Stage24B — generator arguments: static gate + bounded native probe

**Date:** 2026-10-13  
**Status:** **SOURCE/STATIC VERIFIED**, native argument capture **NOT YET RUN**.

## What is proven

- Original `5868USB.dll` SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, 44 source instruction pins and five original PE constants verified.
- Caller `0x18000CFF3` passes sample rates converted from **float32 to float64** at `0x18000CFD3/0x18000CFDB`. Source `0x180011C83–0x180011C99` selects either half-band `cutoff=0.5` or rate-dependent `cutoff=0.5*rate2/rate1`.
- Constructor `0x18000BD12` sees filter object in `RCX` with f64 `+0` cutoff, `+8` quality, `+0x10` attenuation, `+0x20` gain.
- Immediately before `0x18000B981`, `RCX` points to generated stack parameter structure (`RSP+0x30`), and `RDI` to the matching filter: `G_before_floor` f64 at `+0`, `G` uint32 at `+0xC`, `theta` f64 at `+0x18`, `gamma` f64 at `+0x20`, `index` uint32 at `+0x58`, `beta` f64 at `+0xC0`, `I0(beta)` f64 at `+0xC8`, offset f64 at `+0xD0`.
- Original DLL literal defaults are attenuation **180.15**, quality **2**, half cutoff **0.5**, beta **125**, pi **3.141592653589793**.
- **Independent static/native geometry match:** Stage23H original source-derived `G_before_floor=708.9209756461122` at cutoff `0.5` → floor `708` → 1417 taps. Same source-derived width with cutoff `0.5*44100/48000=0.459375` → `G_before_floor=771.614667369918` → floor `771` → 1543 taps. Those are exactly the two native Stage23W coefficient lengths.
- Original native private archive contains two distinct 4096-double pre-FFT buffers, stable **byte-identically** across `20261013_overlap_capture` and `20261013_flag_capture_restart`: 1417-tap `649adeb70df4bb17f73ca09c0e4bc8bd3511271fa388d989bb2094ead22b0770`, 1543-tap `ccb1dcb24dc73dfa5b273a22f96d6093713f52518cadf26e595e94ff9ee6b9cc`; both strictly circularly symmetric and sum approximately `1/1024`.

**Do not overclaim:** The source-predicted G pair agrees with native lengths, but **we have not directly read the live cutoff for each filter**; the runtime-to-source association remains an inference. Stage23Z residual coefficient error remains about `9.28255e-10`. No native generator field values from this cycle, no bitwise tap parity and no fitted Marshall gains/CLO parity.

## How to reproduce source-only gate

From repository root with the original DLL in ignored `research/_LOCAL_FILES/vendor/`:

```bash
.venv/bin/python research/htkpa/stages/stage24b/generator_gate.py --dll research/_LOCAL_FILES/vendor/5868USB.dll
```

Expected: 44 pins, the five literal defaults and `STATIC_VERIFIED_NO_NEW_NATIVE_RUN`.

## Short native probe — once, on user-owned Windows PC

The reusable Frida tracer is `research/htkpa/stages/stage24b/native_generator_trace.py`. It attaches to an **already-running, authorized, 64-bit** Sonicake Manager. Requires **Windows x64 Python with Frida** (e.g. the private Stage23W environment); **not** the Linux WSL `.venv`. Open the manager first, find its process ID, and run:

```powershell
<WINDOWS_X64_PYTHON> research\htkpa\stages\stage24b\native_generator_trace.py --pid <MANAGER_PID> --dll research\_LOCAL_FILES\vendor\5868USB.dll --out research\_LOCAL_FILES\stage24b_native\run1 --seconds 30
```

Wait for `ready.private.json` and then trigger **one** normal local import while the tracer is running. Ideally start with a fresh Manager process, because existing cached filter instances may bypass the constructors. The tracer records at most four hits per site; it reads only source-initialized scalar fields and their exact f64 bit patterns, not WAV/audio or 4096-double buffers. Its private files are:

- `research/_LOCAL_FILES/stage24b_native/run1/generator_arguments.private.jsonl`
- `research/_LOCAL_FILES/stage24b_native/run1/summary.private.json`
- `research/_LOCAL_FILES/stage24b_native/run1/ready.private.json`

Confirm `summary.private.json` has `NATIVE_SCALARS_CAPTURED`, correct runtime DLL SHA, and at least one `filter_arguments` and `generator_arguments` event referring to the **same filter pointer**. If a hook does not fire, record that negative result; do not manufacture gamma/theta values.

## Next *static* RE continuation after the small capture

Compare **actual f64 bit patterns** of cutoff/quality/attenuation and generator `G,theta,gamma,beta` for the 1417-tap filter with Stage23H/Stage23Z computations. Find the first differing field *before* changing any formula, then trace the exact instruction sequence that computes it (chiefly `0x18000B2B8–0x18000B844` and `0x180008FD0–0x180009023`). If all generator fields agree, examine oscillator recurrence and native CRT math call ordering; no brute-force coefficient fitting.

**Private material** stays inside `research/_LOCAL_FILES/`. This report, the verifier, bounded tracer and sanitized evidence are safe for the repository.
