# POCKET_MASTER / HTKPA — CANONICAL CHAT ROLLOVER (2026-10-14)

> **CURRENT ENTRY POINT FOR THE NEXT CHAT.** This document supersedes the *stopping point* of every earlier handoff dated 2026-10-12 or 2026-10-13, including `docs/HTKPA_CANONICAL_HANDOFF_2026-10-13.md`. It does **not** overwrite historical evidence. This is the continuation of an active, deep reverse-engineering project, not permission to restart, redesign or guess missing numbers.
>
> **Repository:** https://github.com/TheColdVoid1337/PocketMasterStudio — default branch **main**.  
> **Main source of live technical truth:** [research/htkpa/RE_LOG.md](../../research/htkpa/RE_LOG.md), append-only; read the **latest** entries.  
> **Universal Frida contract:** [tools/FRIDA.md](../../tools/FRIDA.md).  
> **Latest accepted runtime milestone:** [Stage48](../../research/htkpa/stages/stage48/README.md) = **native fractional PROCESS METADATA + stable real CLO PASS**; separate **managed process graceful shutdown smoke PASS**.  
> **Next engineering milestone:** **Stage49**, *not yet implemented*: safely observe a limited amount of **actual native post-fractional output f64 audio** using the **single universal Frida framework**. Stage48 collected metadata only, **zero sample values**.
>
> **Temporal anchor:** 2026-10-14, Asia/Bangkok. As of the handoff preparation, main included user-verified Stage48 and shared lifecycle code. **Never hard-pin your checkout to a handoff commit**: read today's `main` HEAD using the GitHub connector, because publishing this handoff also advances HEAD.

---

## 0. Instructions to the next ChatGPT engineering chat

You are inheriting the real `POCKET_MASTER` / `PocketMasterStudio Void Mod` investigation. **Speak Russian with the user.** Internal comments, code identifiers, filenames, evidence schema and specialist source references remain in English. User expects exact, forensic/source-first engineering with GitHub commits, not abstract advice.

1. **Read this entire handoff before doing work**, then current `research/htkpa/RE_LOG.md` tail, `tools/FRIDA.md`, Stage48 README, `evidence.json` and `frida.json`. Access repository with the **GitHub connector directly** (discover `mcp__GitHub__fetch_file`, `mcp__GitHub__create_file`, `mcp__GitHub__update_file` via available tools). Avoid searching the web for private project files. If the connector is unavailable, state that limitation and use user-provided files, never imagine a completed GitHub write.
2. **GitHub WRITE authorization remains granted until user explicitly says `#nowritegh`.** Make precise commits to `main` for requested research/docs changes; give actual resulting commit SHA and exact WSL pull/test commands. Do not ask for renewed blanket authorization. **Do not use Codex unless the user requests it.**
3. **Never edit production Studio DSP, HTML, NAM/CLO conversion, hardware, firmware or pedal code** as part of HTKPA reverse engineering unless the user explicitly changes scope. Keep experiments in `research/htkpa/stages/`, evidence in per-stage README/JSON, and append-only findings in `research/htkpa/RE_LOG.md`. Utility changes in shared `tools/`.
4. Preserve the **UNIVERSAL FRIDA RULE**: **ONE source of implementation** under `tools/frida_capture.py`, `tools/frida_guarded.py`, `tools/FRIDA_WSL.sh`; each new Frida stage gets **only `frida.json`, README, evidence/report** under `research/htkpa/stages/stageNN/`. Do **not** create `stage49_capture.py`, `STAGE49_WSL.sh`, or copy the generic implementation into stages. New capability → shared validated /tools with regression tests and backward compatibility.
5. Distinguish **SOURCE-VERIFIED**, **PUBLIC NUMERICAL MATCH**, **NATIVE RUNTIME METADATA**, **ACTUAL NATIVE SAMPLES**, **FULL VENDOR OUTPUT PARITY**, and **NAM→CLO FIT/SERIALIZATION PARITY**. **Only** the first three milestones have meaningful demonstrated evidence here; Stage48 did NOT record the f64 contents of vendor 48-kHz output.
6. No private DLL / user NAM / original CLO / WAV, native f64 arrays, proprietary intermediate binaries, Frida binary captures or reverse-engineered full vendor code in Git. Allowed in Git: user's original SHA fingerprints, public source references, short symbolic addresses, procedural code, hashes, numerical error tables, and status metadata. Private files in ignored `research/_LOCAL_FILES/`; **do not** commit the local handoff ZIP.
7. If user supplies a test log, analyze it first; **do not repeat passing gates** or spin up another converter just to test something already resolved. When evidence is complete, update README/evidence/RE_LOG in GitHub and propose the **smallest** justified next gate. Single reproducible tests, not long script proliferations.
8. Avoid old crash-associated simultaneous hooks `0x18000C220` + `0x18000C838`. The Stage48 guarded **single-hook** at `module+0x1190C` succeeded; a sample-copy Stage49 requires new explicit guard/capacity/lifetime validation before allowing any binary read.
9. No background/asynchronous promises. Provide concise progress as work proceeds, then concrete commits, status and executable commands. Be explicit when a test has been prepared but **not run on the user's Windows**.

### Response and WSL formatting contract

For terminal commands, use **one clean, copy-pasteable fenced Bash block** (or the interface's editable `CodeBlock language="bash"`), with newline-separated commands, `set -e` where appropriate, no `$ ` prompts, a **single trailing backslash** for Bash line continuation, quoted paths with spaces/parentheses, and **no decorative text inside the command**. Under real user outputs, show brief measured statuses or a compact comparison table, mark **PASS vs PENDING**, link exact GitHub files/commits. Don't force repetitive questions when paths are known. Treat code's self-tests as offline gates, not proof of native Windows compatibility. Do not guess a user's terminal PID, file locations, executable existence or whether a GUI closed — user logs are proof.

Canonical checkout and baseline:

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
git status --short
```

The user sometimes starts at `~` or another project in the terminal, **always cd explicitly**. Their Windows environment is Windows x64 + WSL Ubuntu; user's timezone Asia/Bangkok.

---

## 1. Project context, scope and paths

**Repository:** `TheColdVoid1337/PocketMasterStudio`, branch `main`. Product is **PocketMaster Studio / Void Mod**, a browser-based editor/preset/guitar pedal environment for **Sonicake PocketMaster**. Current HTKPA task is specifically understanding the original **Windows Sonicake Manager `5868USB.dll` NAM→CLO** DSP chain to eventually match original vendor behavior.

**Production is separated** from research. Product files and hardware-facing code are not in scope. Earlier work addressed PRST, SonicMaster, NAM/WaveNet and Pre/Post FIR; keep those lines of research intact, but the *active next target* is native resampling output after fractional interpolation, **not** automatically implementing a converter.

Exact known paths:

| Purpose | Path |
| --- | --- |
| GitHub repo | `https://github.com/TheColdVoid1337/PocketMasterStudio` |
| User WSL checkout | `/mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod` |
| WSL venv | `.venv/bin/activate` in that checkout |
| Private local root, Git-ignored | `research/_LOCAL_FILES/` |
| Original vendor DLL, usual WSL path | `research/_LOCAL_FILES/vendor/5868USB.dll` (optional existing fallback `research/_LOCAL_FILES/5868USB.dll`) |
| Real Windows installed EXE (verified by user) | `C:\Program Files\Sonicake\Sonicake Manager\Sonicake Manager.exe` |
| Real Windows CLO watch directory (verified) | `C:\Users\TheColdVoid\AppData\Roaming\Sonicake\Sonicake Manager` |
| Converted CLO, observed relative path | `clo\clofile.clo` below watch dir; **8840 bytes** |
| Public pinned r8brain source cache, local | `research/_LOCAL_FILES/stage41_r8brain_git` (not committed; can be re-created) |
| Universal Frida CLI | `tools/frida_capture.py` |
| Universal Frida library | `tools/frida_guarded.py` |
| Universal Frida WSL entry | `tools/FRIDA_WSL.sh` |
| Universal Frida docs / test | `tools/FRIDA.md`, `tools/test_frida_universal.py` |
| Stage48 config | `research/htkpa/stages/stage48/frida.json` |
| Private Frida archive root | `research/_LOCAL_FILES/frida_captures/` |
| Canonical research timeline | `research/htkpa/RE_LOG.md` |
| **This handoff** | `docs/dev/HTKPA_CHAT_ROLLOVER_2026-10-14.md` |

**Original DLL identity:**
- Windows x64 PE+ `5868USB.dll`, size **2,902,016 bytes**.
- **SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`**. Do not proceed with a different DLL without revalidating addresses.
- PE image base `0x180000000`. PE header `TimeDateStamp` interpreted as **2026-07-29 12:09:35 UTC**, **NOT** authenticated actual build date. Distinguish RVA `0x1190C` from preferred VA `0x18001190C`, and from ASLR runtime VA.
- Original export symbols in older research: `namConvertCloData` RVA `0xE1F70`, `appNamConvertCloData` RVA `0xABEB0`. For broader fitter path, older Stage10–23 research, `docs/NAM_CLO_POSTFIR_RESEARCH.md` and old canonical handoffs provide background. Do not infer fitter equivalence from resampler.

---

## 2. Scientific chronology: what IS measured

### Stage38–40: original FFT, first FIR, spectrum format

- Stage38 and Stage39 studied actual Sonicake intermediate inverse-FFT and output blocks. Stage39 compared real original input **2680 f64** → real native first FIR output **1972 f64**, with publicly compiled r8brain v7.6 `CDSPBlockConvolver`. The native filter length is **1417 taps**, FFT length **4096**, correct output length/alignment **1972**. v7.6 public-vendor difference: max abs **`2.402592014227878e-16`**, RMS **`7.738254656116845e-17`**, exact **0/1972**.
- Stage40 discovered an invalid earlier comparison: native `coeff_post_fft` was a **raw Ooura FFT representation**, while public `CDSPFIRFilter::getKernelBlock()` was stored after **`convertToZP()`**. Corrected ZP alignment is mandatory. For v7.6 against true native 1417-/1543-tap spectra, max abs about **`7.65e-14`**, RMS about **`5.2e-15`**, 4/4096 bit-exact each. Do NOT reuse an unaligned ~0.0009765625 differential as a meaningful mismatch.

### Stage41–42: historical r8brain fingerprint

Public source originally from https://github.com/avaneev/r8brain-free-src (MIT). Pinned revisions:

| Public version | Commit |
| --- | --- |
| v6.5 (2023-12-07) | `3c930bf6825c0cfea4a813210c83b1a650c820b5` |
| v7.0 | `a7d812d3153b0fda845db9fc0498e78d7337d0f0` |
| v7.1 | `1ad3b3707b9339a7144b301752318bbb902220d2` |
| v7.2 | `8fff6f3db26f14a8f5e8fb871000613673db5753` |
| v7.3 | `901cfd827dc6881b45232676670efb54dee9378f` |
| v7.4 | `26f847bf05853fa9e69a90c088c51a2ee46f3c97` |
| v7.5 | `9e73d2dd59fd5b95108fdb4f590083e35758b45f` |
| v7.6 | `cb2abb9977efe2471979b380ed95daa56ab4fdb9` |

Under the pinned WSL test, **v6.5 through v7.5 produce public spectra byte-identical to EACH OTHER** on two tested filters; this does not mean byte-identical to Sonicake. Relative to original, pooled 8192 native spectral f64: legacy variants RMS **`1.3529207911675724e-19`**, max **`4.336808689942018e-19`**, exact **2511/8192**; v7.6 RMS **`5.30608307059938e-15`**, exact **8/8192**. First differing tested public revision: v7.6. Diff v7.5→7.6 includes changes in `r8bbase.h`, math/Bessel approximations **plausibly** responsible, not proven causal. **Exact version embedded in Sonicake NOT identified**. v6.5 is historically plausible/default public research baseline only.

### Stage43: true native first FIR output against historical public convolver

Actual WSL native-input-to-public C++ runs of v6.5, v7.0, v7.1, v7.2, v7.5 and v7.6 all built. For every pre-v7.6 version: **1972 f64** produced, max abs **`8.673617379884035e-19`**, RMS **`2.2951391745135605e-19`**, **380/1972** exact vs vendor. v7.6: max **`2.402592014227878e-16`**, RMS **`7.738254656116845e-17`**, **0/1972** exact. This is about **337×** RMS improvement vs v7.6 for native first FIR. Per-version equal metrics do not necessarily mean same output SHA; do not overclaim.

Private source SHA (2680 f64): `9519d98a65e88f0858819a2579202768c945f9b9604ae4cd9fc656162d173acf`. Private first FIR output SHA (1972 f64): `4e80e6e12343f2b1b618e351d2ecfe5e0851993af0ee10636149f7bd6a979cb6`.

### Stage44: complete **PUBLIC** 44,100→48,000 pipeline

Actual source C++ `CDSPResampler`, `ReqTransBand=2%`, `ReqAtten=180.15 dB`, linear phase, public structure first **2× FIR upsample 44100→88200** then fractional **88200→48000**. This is a tested **PUBLIC implementation hypothesis** of vendor downstream choices; vendor final output not yet available.

For input 2680 original f64 and no flush, public generated **1067 output f64**. Source chunk sizes 64, 512, 2680 gave **bit-identical per-version** outputs. Public v6.5 and v7.2 **byte-identical to EACH OTHER**, SHA `d1e7fde902ba117da0536ecbe1d4a4fde0a4a8918e3d02883187a8a63f27e6e1`; public v7.6 SHA `48f94de01225afd916e862061ed656b104ab1cb176790d84b526cd87e9aa466a`. v7.6 vs v6.5 max **`9.377454325207313e-15`**, RMS **`3.879522442760983e-16`**, exact 0/1067. **1067 is a short startup response, not complete-song length or flushed result.**

### Stage45: true **VENDOR FIR** → **PUBLIC FRACTIONAL**

Input to public `CDSPFracInterpolator`: exactly the vendor 1972-f64 first FIR block, source 88200→48000. Public hybrid result **1067 f64** (chunk sizes 64, 512, 1972 bit-exact across each version). Hybrid v6.5 and v7.2 byte-identical to EACH OTHER, SHA `a6db6a9720b3c9649fdca3f9002606d65ec5fbf4968f8d5c187514077e6a0750`. Each hybrid vs its entire public pipeline: **199/1067** bit-identical, max abs **`8.673617379884035e-19`**, RMS **`2.3660543527888402e-19`**. Hybrid v7.6 vs public v7.6 max **`2.3809079707781677e-16`**, RMS **`7.340605368424465e-17`**.

**Important: `VENDOR FIR → PUBLIC fractional` is NOT `VENDOR FIR → VENDOR fractional`.** No vendor 48k waveform values have been read yet. These metrics cannot prove downstream native parity.

### Stage46–47: real DLL RTTI, wrapper and buffer provenance

Static original DLL MSVC RTTI/vtable/disassembly gave:

| Item | Original native VA / RVA |
| --- | --- |
| `r8b::CDSPBlockConvolver::process` | VA **`0x18000C220`**, RVA `0xC220` |
| `r8b::CDSPFracInterpolator<...>::process` | VA **`0x1800135C0`**, RVA `0x135C0` |
| `r8b::CDSPResampler24::process` | VA **`0x180011850`**, RVA `0x11850` |
| Frac specialization **vtable** | RVA **`0x245170`** (runtime ASLR base + RVA) |
| Intermediate-stage `process` call | VA `0x1800118B1` |
| Last-stage indirect vtable call | VA **`0x180011909`** |
| **First instruction after last-stage return** | VA **`0x18001190C`**, RVA **`0x1190C`** |
| Last processor instance pointer | `[RBX+0x50]` (decimal +80) |
| Caller output pointer reference | **`R15`** (`double**`); `*R15` is actual array pointer |
| Output sample count after call | **`EAX`** low 32-bit of `RAX` |
| Fractional output sample write | VA `0x180013C38` (`movsd [R12],XMM3`), advance at `0x180013C3E` |
| Frac output count from pointer difference | VA `0x180013D15–0x180013D1D` |

The `CDSPResampler24` selects/reuses potential scratch allocations, sometimes input fallback, via virtual `getMaxOutLen` and fields including `[RBX+0x58]`, `[RBX+0x68]`, `[RBX+0x70]`. **No fixed output buffer address**. The specific fractional method loads `*R9` and writes f64 without an observed direct re-point of its saved output pointer. However address-space `r--` mapping **does not prove allocation capacity**, or that the pointer survives after the subsequent call. One must verify current count, effective actual pointer and lifetime at the current call site before copying binary.

The DLL RTTI uses `CDSPFracInterpolator<...>` a template specialization, unlike publicly exposed v6.5's non-template class. Never equate the DLL to an exact public git commit merely from FIR numerical compatibility.

### Stage48: **real native runtime METADATA + CLO completion accepted**

**First interrupted observation (old bespoke runner):**
- A single attach at module + `0x1190C`, first rejected count guard then valid **observation #18**, `114 f64` / `912 bytes`, original fractional vtable match.
- Old script incorrectly wrote `BLOCKED, hook_count=0` on user Ctrl+C even though `events.jsonl` proved one hook and valid event. Fixed by shared lossless event-journal recovery; historical erroneous manifest stays historical and recovered metadata kept separate.

**Canonical universal runner successful Windows run (user archive `frida_20261014_112002_862142.tar.gz`):**
- User verified installed Manager EXE and CLO folder. **13/13** updated universal Python regression tests later passed (0.193s).
- Frida spawned **its own** Manager **PID 4524**, attached module observer, resumed. Exact original DLL backing SHA checked prior to arming **one** metadata-only hook at RVA **`0x1190C`**.
- First return rejected for zero/over-bound count; **observation #18** matched native fractional vtable `0x7ff85e6d5170` = loaded module base `0x7ff85e490000` + `0x245170`.
- Actual metadata output: **114 f64 / 912 bytes**, pointer `0x12eb8d577a0`, mapping-readable verified. **NO `readDouble`, no sample bytes copied.**
- Real **new/changed and stable** CLO path: `C:\Users\TheColdVoid\AppData\Roaming\Sonicake\Sonicake Manager\clo\clofile.clo`, size **8840 bytes**. `METADATA_GUARD_PASS_CLO_STABLE`, `completion_verified=true`, `hook_count=1`, true Windows result. Archive contains ONLY `config.json`, `manifest.json`, `events.jsonl`, `HANDOFF.md`, **not** the CLO itself.
- **Independent GUI auto-close bug:** `GRACEFUL_CLOSE_FAILED`, process exit code 3 after positive native/CLO result, caused by `ctypes` `EnumWindows(visit)` missing mandatory second LPARAM. Do not retroactively call this run completely clean.
- **Fix subsequently verified on real Windows**: universal `--lifecycle-smoke` with Manager CLOSED, no native instrumentation or conversion, spawned **PID 20844**, resumed, waited 4 seconds, sent **`WM_CLOSE` to five windows belonging to PID 20844**, observed `Tool-launched application closed`, status **`LIFECYCLE_SMOKE_CLOSED_GRACEFULLY`**, exit **0**, **ZERO Frida hooks**. This establishes the fixed shared `EnumWindows(visit, 0)` auto-close behavior. Separate gate from earlier Stage48 native metadata+CLO PASS.

**Full native 48k audio numerical parity remains OPEN.** A native metadata block size of **114** cannot be compared to the **1067** samples of the short unflushed public startup result without reconstructing identical streaming chunk boundaries, ordering and initial state.

Exact stage evidence: [stage48/evidence.json](../../research/htkpa/stages/stage48/evidence.json), [stage48/README](../../research/htkpa/stages/stage48/README.md), [stage48/frida.json](../../research/htkpa/stages/stage48/frida.json).

---

## 3. Universal Frida framework (locked architectural decision)

**Canonical**:
- `tools/frida_capture.py` — config parser, one CLI, archive writer, per-run metadata, legacy scalar/f64 modes, new guarded dispatch.
- `tools/frida_guarded.py` — reusable SHA-gated guarded processor metadata callback, owned lifecycle spawn/close, CLO watcher, output pointer/count guards, event recovery, `--preflight`, `--lifecycle-smoke`.
- `tools/FRIDA_WSL.sh` — **only** WSL→Windows command launcher; automatically uses installed Windows Python Frida virtualenv from local private source, ANSI colors, prints `[TARGET]`, `[HOOK]`, `[META]`, `[CLO]`, `[WAIT]`, `[STATUS]`.
- `tools/test_frida_universal.py` — regression suite (13/13 user-confirmed on 2026-10-14). `.github/workflows/frida_universal.yml` runs offline checks. `tools/FRIDA.md` is detailed API contract.
- `research/htkpa/stages/stage48/frida.json` — stage-local parameters, *no separate Python/BAT file*.

Current guarded config essential fields:

```json
{
  "module": "5868USB.dll",
  "sha256": "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa",
  "mode": "guarded_metadata",
  "target": {"process_name_contains": "sonicake"},
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
  },
  "sites": [{
    "name": "post_fractional_output",
    "address": "0x1190c",
    "max_hits": 1,
    "required": true,
    "fields": [],
    "guard": {
      "kind": "processor_output",
      "owner_reg": "rbx",
      "owner_offset": 80,
      "vtable_rva": "0x245170",
      "output_ref_reg": "r15",
      "count_reg": "rax",
      "max_samples": 4096,
      "max_observations": 256
    }
  }]
}
```

Actual `frida.json` contains `image_base` additionally; read source file rather than copying this excerpt. The `guarded_metadata` mode **intentionally prohibits `fields`** (to prevent accidental raw audio read) and permits exactly **ONE required hook**. The shared core also retains **LEGACY** `f64_binary`, `f64_slice`, scalar captures, in unguarded legacy mode. When designing Stage49, NEVER simply add `f64_binary` under `guarded_metadata`: its validator rejects it, and bypassing this would remove safeguards. Extend the **shared tool** with a new explicitly approved, bounded, tested capture mode.

Guard conditions: process loaded original SHA; expected dynamic fractional vtable; current `EAX` count **1..4096**, `*R15` f64 alignment and readable mapped region; max 256 observation callbacks; for Stage48 only first qualifying hit emitted. Success also requires new/changed nonempty CLO stable **3 seconds**. Note: mapped-region test is not allocated buffer capacity or persistence proof.

Managed process policy:
- `start=fresh` refuses when a matching user-owned Manager is open, spawns its own suspended EXE via Frida, attaches its own observer, resumes PID.
- `start=if_missing` may attach to a running program but must never close a reused user-owned PID.
- `close=if_launched` calls `EnumWindows(callback,0)` / WM_CLOSE on windows with the **exact owned PID** and waits bounded time; never force-kill a running GUI, only a still-suspended own failed startup may be cancelled. Record `cleanup_status` and don't mistake cleanup failure for failed DSP.
- Stage48 `--lifecycle-smoke` real Windows confirmed correct WM_CLOSE to five owned windows without hook or conversion.

Useful verified WSL commands:

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python tools/frida_capture.py --self-test
python -m unittest discover -s tools -p 'test_frida_universal.py' -v
bash -n tools/FRIDA_WSL.sh

# Windows EXE, CLO path and private DLL SHA. NO process launch, NO hook.
bash tools/FRIDA_WSL.sh \
  --config research/htkpa/stages/stage48/frida.json \
  --preflight

# With Manager CLOSED: only exercise GUI launch/close, ZERO hooks.
bash tools/FRIDA_WSL.sh \
  --config research/htkpa/stages/stage48/frida.json \
  --lifecycle-smoke
```

For a real Stage48 capture (ALREADY ACCEPTED, do not unnecessarily repeat), with Manager CLOSED:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
bash tools/FRIDA_WSL.sh \
  --config research/htkpa/stages/stage48/frida.json
```

The user starts ONE normal NAM→CLO conversion only after a genuine `[HOOK]`; an actual new stable CLO is checked in the configured directory. The wrapper does **not** click GUI buttons, browse file dialogs or automatically load a NAM. **The old `research/htkpa/stages/stage48/metadata_probe.py` and `STAGE48_WSL.sh` were deleted from current main after migration; use Git history for old evidence, never resurrect them.**

Archive behavior: universal runner writes allowlisted private tar `research/_LOCAL_FILES/frida_captures/frida_YYYYMMDD_...tar.gz`, usually four metadata files, and any explicitly allowed legacy binary payloads. Never commit private tar or originals. Errors and Ctrl+C preserve journal via recovery; `METADATA_GUARD_PASS_CLO_STABLE` is the full **METADATA** gate, not a waveform test.

---

## 4. Private local rollover ZIP — contents and handling

**A private user-facing ZIP was generated in this conversation, NOT committed to GitHub.** Name:
`POCKET_MASTER_HTKPA_PRIVATE_ROLLOVER_2026-10-14.zip`

**SHA256 of ZIP: `5e363d0f9ac03388cf19f395a7d4f7fe50b6885e5802d5b7d8cb9f0a6ff161ec`**. Size **3,505,989 bytes**. It contains **31 files** from user-supplied session attachments, plus `PRIVATE_MANIFEST.json` (per-file SHA-256/size/mapping) and `PRIVATE_README.txt`. **The new chat must receive it as an ATTACHED FILE** if it needs to inspect original private contents; a GitHub link to this Markdown handoff does not grant access to any local ZIP. Once attached, verify the overall archive checksum and inner `PRIVATE_MANIFEST.json`.

Important ZIP content, mapped to intended user's ignored checkout structure under `research/_LOCAL_FILES/`:

| ZIP member inside `research/_LOCAL_FILES` | Purpose |
| --- | --- |
| `vendor/5868USB.dll` | Exact 2,902,016-byte SHA-pinned original PE64 binary for static analysis; **NEVER GitHub** |
| `stage23w_native(1).zip` | Actual original FFT / native FIR observations, ~115 internal items; used by Stage38–45 auditors |
| `stage40_native_fir_fixtures.zip` | Original 1417-/1543-tap native pre/post FFT spectra |
| `stage38/stage38_private_fft_fixtures.zip` | Private FFT reference fixtures |
| `frida_captures/frida_20261013_143414_395162.tar.gz` | Stage33 original native input/FFT frames; Stage43–45 require this |
| `frida_captures/frida_20261013_144322_324693.tar.gz` | Stage35 original first FIR output; Stage43–45 require this |
| `frida_captures/frida_20261014_112002_862142.tar.gz` | **Actual Stage48 universal runner acceptance**: manifest, events, config, handoff; no audio, 114-f64 metadata / 8840-byte stable CLO |
| Other `frida_captures/frida_20261013_*.tar.gz` | 2026-10-13 previous captured evidence/events; see per-file manifest |
| `stage48_manifest_recovered.json` and `rollover_aux/` | Historic interrupted/corrected manifests and further user-provided evidence (private, not necessary for every experiment) |

The ZIP **does not** embed the user’s full local WSL checkout, full proprietary NAM, actual output `clofile.clo` or the locally cached public git clone `stage41_r8brain_git` because those were not present as uploaded files here. Do not assert those files have been copied or synchronized; use the existing user WSL checkout for them. The public source can be fetched again by the source-cache scripts. If later stages need additional local artifacts, create **a supplementary private bundle** and attach it, never silently Git-add ignored files.

To extract this ZIP into user's checkout **locally only**, from the directory where the ZIP was downloaded:

```bash
python3 -m zipfile -e \
  POCKET_MASTER_HTKPA_PRIVATE_ROLLOVER_2026-10-14.zip \
  /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod

cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
git check-ignore -v research/_LOCAL_FILES/vendor/5868USB.dll
```

Only extract if needed (existing local files may already be present). The archive paths are correctly rooted at `research/_LOCAL_FILES`. Do not unzip into the repository root without checking this layout; don't overwrite newer private captures. The user may simply **attach the ZIP in the next chat** without extracting, which is the default desired usage.

The private ZIP is intentionally packaged from user-provided originals and may contain proprietary research data. Keep it private; **no public GitHub link exists or should be invented**.

---

## 5. Reproduce previous exact native/public WSL comparisons when justified

Already user-run/accepted: **do not rerun gratuitously**. These commands explain artifact relationships for later tests.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

# Stage43: genuine Sonicake first FIR vs pinned public versions.
python research/htkpa/stages/stage43/audit_convolver_versions.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --stage33-archive research/_LOCAL_FILES/frida_captures/frida_20261013_143414_395162.tar.gz \
  --stage35-archive research/_LOCAL_FILES/frida_captures/frida_20261013_144322_324693.tar.gz \
  --source-cache research/_LOCAL_FILES/stage41_r8brain_git \
  --out research/_LOCAL_FILES/stage43_convolver_version_report.json

# Stage44: PUBLIC full resampler.
python research/htkpa/stages/stage44/audit_pipeline.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --stage33-archive research/_LOCAL_FILES/frida_captures/frida_20261013_143414_395162.tar.gz \
  --stage35-archive research/_LOCAL_FILES/frida_captures/frida_20261013_144322_324693.tar.gz \
  --source-cache research/_LOCAL_FILES/stage41_r8brain_git \
  --out research/_LOCAL_FILES/stage44_public_pipeline_report.json

# Stage45: VENDOR first FIR -> PUBLIC fractional differential.
python research/htkpa/stages/stage45/audit_hybrid.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --stage33-archive research/_LOCAL_FILES/frida_captures/frida_20261013_143414_395162.tar.gz \
  --stage35-archive research/_LOCAL_FILES/frida_captures/frida_20261013_144322_324693.tar.gz \
  --source-cache research/_LOCAL_FILES/stage41_r8brain_git \
  --out research/_LOCAL_FILES/stage45_fractional_hybrid_report.json
```

Read exact scripts on main before actual reuse in case CLI switches evolved. Existing source-cache depends on prior local preparation and public git fetch availability. Source code uses real pinned C++ rather than a generic resampler. No original f64 arrays may be committed.

---

## 6. Next Stage49 — desired research direction, NOT yet approved/runtime-executed code

**Goal:** acquire enough **actual vendor 48-kHz post-fractional f64 content** to numerically compare identical input/streaming conditions to the pinned **public** r8brain 44.1→48 chain. Existing data prove only native output pointer/size/type; no vendor sample value is yet available. This is not a request to start fitting all four CLO gains or modifying production.

**First research/design action in the next chat:** source-first inspect `tools/frida_guarded.py` and Stage47/48 evidence for safe bounded read, pointer lifecycle and streaming. Then plan and implement a strictly opt-in generic `guarded_f64_binary` (or similarly named) mode in the **UNIVERSAL `/tools`**, with Stage49 JSON selecting it, plus a dedicated offline/mock and Windows acceptance gate. Require user's normal single conversion only after offline QA passes. Do not silently escalate Stage48 to an audio capture.

Minimum Stage49 considerations:
- Exact loaded DLL SHA/version, original runtime RVA `0x1190C`; **one hook** at post-return, not `0x135C0` entry or a paired-hook scheme.
- Verify actual **processor vtable at `module+0x245170`**, count in EAX bounded, `*R15` aligned/readable. **Prove safe bounded per-callback sample length** independently of mapped region; first choose a small one-shot diagnostic or a bounded number of events. Stage48's `114 f64` was **one** block at observation 18; multiple callbacks and state may be required to rebuild 1067 public startup samples.
- **Use binary transport**, not target-thread hexadecimal/JSON serialization. Keep copying and data processing outside sensitive target callbacks as much as Frida permits; private temporary output only. Clip explicit maximum total bytes/events and surface a graceful abort on suspicious sizes.
- **Do not assume the same 2680-input / 1972-first-FIR / 1067-public output window** can be compared to an arbitrary 114-f64 vendor fragment. Need independent segmentation/start offset, chunk order, input identity, latency and normalization/no-flush conditions; compare only aligned samples. Do not manufacture alignment by searching arbitrary shifts.
- Accept only objective numeric results (counts, version pins, SHA, max abs, RMS, exact f64, error locations) and clearly label result `NATIVE_48K_SAMPLES_CAPTURED`, `NUMERIC_PARITY_TESTED` or `NOT_ALIGNED`, as appropriate.
- Stop immediately on target crash or loss of valid CLO. Never repeat the old dual-hook instability. Preserve on-disk journal truth under Ctrl+C and detect cleanup independently.
- Do not adopt "Stage49 complete" merely because a new config or wrapper compiles. Stage49 first prepared, then user WSL/offline QA, then user live Windows result, then GitHub README/evidence/RE_LOG.

Potential follow-on after successful 48k parity: true last 48k-to-fitter PCM conversion/quantizer/detrend, alignment with full trainer source, extracted four gains and FIR parity, and held-out two original NAM→CLO cases. All remain distinct and unproven. The early `docs/NAM_CLO_POSTFIR_RESEARCH.md` describes a separate experimental refit, **not proof of Sonicake's actual fitter**.

**If user has not yet instructed "Stage49 now":** after reading the handoff and private ZIP, respond with a brief current-state summary and offer Stage49 preparation rather than automatically launching Sonicake.

---

## 7. Durable documentation and handoff hierarchy

1. **This document** `docs/dev/HTKPA_CHAT_ROLLOVER_2026-10-14.md` — new-chat instructions and 2026-10-14 current state.
2. `research/htkpa/RE_LOG.md` — append-only factual running log, read **from the end**. Old false starts and failures intentionally retained.
3. Per-stage `research/htkpa/stages/stage38..48/{README.md,evidence.json}` — exact verified data and sources. Some stage documentation contains earlier "next" text, which is historical relative to subsequent stages; do not take a Stage44 "Next Stage45" sentence as the live plan.
4. `tools/FRIDA.md` and shared code/tests — canonical application lifecycle, JSON schema, SHA guards, process ownership and metadata/legacy capture modes.
5. `docs/NAM_CLO_HTKPA_RESEARCH_STATUS_2026-10-13.md`, `docs/HTKPA_CANONICAL_HANDOFF_2026-10-13.md`, `docs/POCKET_MASTER_HTKPA_HANDOFF_2026-10-12.md`, `docs/NAM_CLO_POSTFIR_RESEARCH.md` — **historical background**, still valuable for Stage1–23 training and fitting work but stale on current milestone.
6. Repo top-level `README.md` — description of production app and narrow link into HTKPA research.

**Documentation policy:** Treat old long technical texts as historical evidence, add visible pointer to this handoff/current status rather than rewriting individual old observations. New experimental result: commit exact `evidence.json`, per-stage README, **append RE_LOG**. Update the canonical handoff/status deliberately on next significant rollover instead of appending contradictory current-state fragments forever. No silent rewrite of append-only RE_LOG and no production modifications.

---

## 8. Bootstrap protocol for the new chat (what should happen after the small user prompt)

The new chat should:

1. Read the GitHub handoff URL and all its linked canonical current files using its GitHub connector, fetch `main` HEAD, state exactly which committed docs it read. **Prefer connector reads** of project files; ordinary public browser search only if connector read impossible.
2. If the user attached the **PRIVATE_LOCAL ZIP**, inspect `PRIVATE_README.txt` / `PRIVATE_MANIFEST.json` first; verify archive overall SHA256 `5e363d0f9ac03388cf19f395a7d4f7fe50b6885e5802d5b7d8cb9f0a6ff161ec` and original DLL SHA. Never upload private archive to GitHub or request that user publish it.
3. Confirm **Stage48 COMPLETE for native metadata + stable CLO**, **universal Manager auto-close independently PASS**, **Stage49 PENDING**. Repeat the measured f64 limits precisely: native **114-f64 metadata only**, first native FIR **1972**, short public/full-hybrid **1067** — these are different units/positions, not equivalent buffers.
4. Respect implicit user authorization to write research/docs/tool changes to `main` until explicit `#nowritegh`. Do not claim GitHub changes until tools report actual commit IDs.
5. Preserve Russian engineering dialogue, **copy/paste WSL blocks**, color/auto-run Frida via shared `tools`, stage JSON-only configs, clean private evidence boundary. **No Codex** unless requested.
6. Ask no questions whose answers are in the handoff; proceed from the **specific next task** the user gives. In absence of any task, give a short recap and state that Stage49 is the next gate.

### Explicitly rejected interpretations

- Stage48 = full vendor resampler numerical parity — **FALSE** (no native 48k sample values).
- v6.5 is definitely the DLL's r8brain version — **UNPROVEN**.
- 1067 public outputs equal the vendor's 114-sample native block — **FALSE**, unrelated stream-length/offset conditions until proven.
- Stage48 full native conversion failed because its first GUI auto-close failed — **FALSE** (CLO was stable and the subsequent owned GUI smoke passed).
- All private files are on GitHub — **FALSE**. They are in the attached local-only ZIP or the user's existing ignored WSL directory.
- Every future stage needs new Python/SH wrapper — **FALSE**. Only generic `/tools` evolves.
- Native FIR matching implies NAM fitting/final CLO matching — **FALSE**.
- Re-run old dual-hook Frida captures to get a full WAV — **UNSAFE/UNJUSTIFIED** given previous Manager crashes.

**END OF CANONICAL HANDOFF — HTKPA Chat Rollover 2026-10-14.**
