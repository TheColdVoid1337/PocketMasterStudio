# Stage72 — source-rate field provenance in the original PE

**Accepted original-DLL result (2026-10-15):**
`STATIC_CALLER_RATE_PROVENANCE_FOUND_RUNTIME_STAGE64_UNPROVEN`.

This stage was **run locally by the researcher against the original exact-SHA
vendor DLL**, extracted *privately* from the user-provided rollover archive.
GNU `objdump` produced **57/57 instruction anchor matches** and a conservative
intra-function branch analysis for both Stage69 source-rate loads. The DLL
was read as static bytes only: no Windows DLL execution, Frida, native audio
export, hook, model inference, DSP patch or browser/WASM change.

## Findings on original 5868USB.dll

### Candidate `0xE28F1` — decoded audio-object input rate

- `0xE27CB` calls helper `0x143310`; `0xE27D0` puts its RAX return in R14.
- The helper allocates an audio object and directly calls constructor
  `0x8BB70` (`0x14334A`), **but also has an alternate indirect object
  factory call at `0x1433BE`**. The latter is not dynamically resolved.
- In the original WAV `fmt ` branch at `0x8BE4D`, a vtable-backed 32-bit
  source integer is read at `0x8BE82`, converted to f64 at
  `0x8BE85/0x8BE89`, then stored to audio-object `+0x8` at `0x8BE8D`.
  This is a conditional **source-input metadata path**, not a hardcoded 48k.
- At `0xE28DC`, the caller loads f64 `[r14+0x8]`, converts to f32 at
  `0xE28E2`, and calls the shared resampler helper `0xCE00` at `0xE28F1`.

### Candidate `0xBF364` — context input-rate field

- `0xBE88B` assigns `R14=RCX`, the Windows x64 entry pointer argument.
  `0xBF358` reads float32 `[r14+0x20EC0]`; `0xBF364` calls helper `0xCE00`.
- Two specific **direct** incoming calls to owner `0xBE830` are independently
  verified: `0xFA41`, `0x104E1`. This does not exclude indirect callers.
- In caller `0xF940`, `0xF9A1` creates local context `[rbp+0x100]`;
  `0xF9A7` reads the PE float32 constant **44100.0 Hz** at `0x24CDF0`;
  `0xF9B6` passes it to initializer `0xBFE00`; `0xFA41` passes the same
  local context to `0xBE830`.
- In caller `0x10230`, `0x10287` reads an incoming stack float32 into
  XMM6 (`[rbp+0x27B20]`); `0x1044D` creates context `[rbp+0x150]`,
  `0x10453/0x1045D` pass that float via XMM1 to the same initializer,
  then `0x104E1` passes the context to `0xBE830`. No live value is known.
- Fresh context initializer `0xC04B0` clears `+0x27918` at `0xC0626`.
  Initializer `0xBFE00` copies XMM1 to XMM10 at `0xBFE1C`, tests that
  flag at `0xBFE20/0xBFE28`, and writes XMM10 to float32 context
  `+0x20EC0` at `0xBFEF9` or **conditionally** `0xC03AE`. Other paths,
  aliases and live runtime object identity are not exhaustively proven.

## Bounded local R14 control-flow check

An exact-source Intel disassembler parser supports **GNU objdump and LLVM
objdump**. A conservative instruction CFG considers both arms of conditional
jumps, detects direct branches, and records unresolved indirect branches.
Within the two verified `.pdata` function owners, all decoded reachable paths
to the respective rate-load instructions had one R14-origin label:

| Owner RVA | Load RVA | Unique *local* R14 origin | Explored instruction/state pairs | Unresolved local branch sites |
|---|---|---|---:|---:|
| `0xE2640` | `0xE28DC` | helper return from `0x143310` | 292 | 0 |
| `0xBE830` | `0xBF358` | entry RCX argument | 602 | 0 |

The CFG is **not** an interprocedural reaching-definition proof or runtime
trace. It assumes ordinary Windows x64 nonvolatile R14 call preservation,
over-approximates branch choices, and cannot resolve aliasing, indirect
factories, exception dispatch or the actual Stage64 object. GNU and LLVM
syntaxes are normalized for the pinned instructions only.

## Reproduce

Offline regression (requires no vendor binary):

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage72.py' -v
```

Optional independent original-PE verification on WSL:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python research/htkpa/stages/stage72/audit_rate_provenance.py \
  --dll "/mnt/c/Program Files/Sonicake/Sonicake Manager/assets/5868USB.dll" \
  --out research/_LOCAL_FILES/stage72_rate_provenance.json
```

In the assistant environment, the same exact DLL SHA was checked at
`research/_LOCAL_FILES/vendor/5868USB.dll`; the local complete report
`research/_LOCAL_FILES/stage72_rate_provenance.json` is Git-ignored.
Disassembler selection is automatic (LLVM first, GNU fallback), and
`--objdump` can select a specific installed tool.

## What is **not** established

- Neither candidate was linked to the specific dynamically observed
  Stage64 reverse fractional object (`96000→44100`).
- The source rate of that actual whole native resampler is **not proven
  to be 48000 Hz**; the general source-file reader can supply different
  header rates and one context caller takes a dynamic stack argument.
- The complete vendor 96→44.1k anti-alias filter performance is not
  measured. Stage69/70 constructor static reachability remains intact.
- Stage71's bounded negative direct NAM-export ancestry result is intact;
  Stage72 does not assert a new NAM-export runtime path.

**Next (only upon `#next`):** trace entry to the two caller functions and
remaining conditional branches with a small source-first scope, deciding
whether a metadata-only dynamic probe is actually needed. Do not modify
Resampler Lab, recovered DSP primitives, production or WASM by inference.
