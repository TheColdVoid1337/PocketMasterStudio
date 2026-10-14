# Stage47 — static caller, output-pointer and buffer-capacity reconstruction

**Status: STATIC_LAST_STAGE_RETURN_SITE_VERIFIED (no runtime experiment).**

This is a direct offline analysis of the user's original PE64 `5868USB.dll`, exact SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, using LLVM 17.0.0 `llvm-objdump`. The identified function is r8brain-related native code, not a claim of vendor output parity or a validated safe Frida hook. Stage46's MSVC RTTI identified `r8b::CDSPFracInterpolator<...>::process` at `0x1800135C0`, with `r8b::CDSPResampler24::process` at `0x180011850`.

## Full last-stage call and output provenance

The constructor/processing code for the original `CDSPResampler24` uses virtual processor slots consistent with the original `CDSPProcessor` interface.

| VA | Exact role confirmed by disassembly |
| --- | --- |
| `0x18001185C` | Preserve caller's `double*& op0` address (`R9`) in `R15` |
| `0x180011892` | Pass `R9=&[RSP+0x40]` to intermediate stages |
| `0x1800118B1` | `call [vftable+0x30]` for intermediate stage `process` |
| `0x1800118BA–0x1800118C2` | Carry returned `EAX` count and output pointer `[RSP+0x40]` to next stage |
| `0x1800118CF` | Branch on presence of final-stage processor at `[RBX+0x50]` |
| `0x1800118EA` | Load candidate final output buffer from `[RBX+0x70]` |
| `0x1800118FA` | Set caller's output `*[R15]` to the actual selected buffer (or input fallback) |
| `0x1800118FD` | Load final processor instance `RCX=[RBX+0x50]` |
| `0x180011901` | Place final output pointer in the local `double*` stack slot |
| `0x180011909` | `call [vftable+0x30]`: virtual final processor `process` |
| **`0x18001190C`** | **First instruction after final process returns; `EAX` count and `*[R15]` proposed output buffer** |

This final call is **indirect**. Even when this path is reached, there is *no static guarantee* its receiver is the specific fractional interpolator we want on a particular conversion. A later runtime observation would have to validate the dynamic receiver's vftable against `0x180245170`.

## The native fractional processor's output semantics

Within exactly the bounded machine-code function `0x1800135C0..0x180013D28`, LLVM disassembly identifies:

- `0x1800135CB`: `R12 = *R9` — load original output-array pointer from reference.
- `0x1800135CE`: `R13 = R9` — preserve pointer-reference address.
- `0x180013C38`: `movsd [R12],XMM3` — write one output sample directly.
- `0x180013C3E`: `R12 += 8`.
- `0x180013D15..0x180013D1D`: return `(R12-*R13)/8` in `EAX` as output f64 count.

Across its **347 disassembled instructions**, this native function contains **no direct or indirect CALLs**. Its only explicit memory dereference through saved output-reference register `R13` is the read at `0x180013D15`. This makes pointer replacement **unlikely within this exact specialization**, but says nothing about the lifetime of the buffer after this call, other compiled specializations or wrapper behavior.

An independent caller-control exists in `CDSPResampler24::clear` at `0x180011A4F–0x180011A56`: it compares a processor vftable to **`0x180245170`**, the already Stage46-identified native specialized fractional interpolator vftable. The original resampler thus explicitly knows this class.

## How final-stage output capacity and memory are selected

At native initialization `0x180012213..0x180012267`:

1. `0x18001222A`: last-stage instance saved as `[RBX+0x50]`.
2. `0x180012237`: call its **virtual slot 4 `getMaxOutLen`**, then compare required output capacity.
3. Depending on buffer capacities and reuse:
   - reuse the intermediate allocation `[RBX+0x58]`;
   - select a fallback with `[RBX+0x70]=0`, so the process method may work directly on the original input buffer;
   - grow/reuse extra allocation through `[RBX+0x68]` and assign it to `[RBX+0x70]`.

**Therefore there is no universal fixed final-output address.** Both source and destination buffer ownership are conditional. The post-return `*[R15]` pointer can refer to resampler-owned scratch memory or a reused input region. It may be overwritten during the next call, so any capture would need to be read or copied immediately while the callback's stack/register context is valid. The maximum safe readable byte count has NOT yet been verified dynamically.

## Reproduce with zero vendor execution

`audit_static_return.py` reads the DLL as data and invokes local LLVM `llvm-objdump`. It hard-fails on a different DLL SHA or instruction signature. The byte-level PE executable is **not loaded as code**, and no raw proprietary instructions or audio are committed.

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
python research/htkpa/stages/stage47/audit_static_return.py \
  --dll research/_LOCAL_FILES/5868USB.dll \
  --out research/_LOCAL_FILES/stage47_static_return.json
```

Choose your actual private DLL path for `--dll`. An independent static anchor verification against the uploaded DLL was successfully executed here using LLVM 17.0.0 and Python (wrapper, setup, fraction, clear). This repo verifier is an additional portable local tool; it is not proof of hook stability.

## Stage48 gate: only if the user deliberately proceeds

`0x18001190C` is a **better-motivated candidate than hooking `0x1800135C0` or again pairing `0x18000C220` with `0x18000C838`**, because it executes after the fractional kernel completes rather than during input/multiply/output iterations. This remains a **hypothesis about operational safety**, not a demonstrated safe site.

**First runtime probe must be ONE HOOK, metadata only, one-shot, no f64 input/output reads**, gated by:
- exact loaded DLL SHA and module-relative site RVA `0x1190C`;
- runtime last-stage object's vftable `[*([RBX+0x50])]` equal to module base+`0x245170` (requires careful pointer safety);
- returned count `EAX` valid and bounded; output pointer `*R15` non-null/aligned; record only pointer addresses/length and event count (no waveform);
- real vendor conversion completes and yields new/changed **stable CLO**, else abort next phase;
- only after such a successful observation consider ONE HOOK **binary f64 capture** at this same post-return site, using Stage35's safe `f64_binary` path, not hex-encoded target-thread conversion and not a paired hook.

**Stage47 did not create/execute this Stage48 Frida runtime configuration.** If any invariant fails, stop rather than speculatively capturing memory. No production paths, fit algorithm or CLO serialization modified.

Stage45 vendor-first-FIR/public-fractional consistency remains a public-hybrid comparison; a live native post-fractional 48-kHz reference is **still missing**. Original r8brain upstream is MIT-licensed (Aleksey Vaneev / Voxengo).

## 2026-10-14 handoff update: Stage48 now uses the one universal /tools runner

After this static Stage47 gate, a real Windows Stage48 run **did observe** a valid post-fractional metadata event for 114 f64 at RVA `0x1190c` (dynamic fractional vtable RVA `0x245170`). That run did **not** prove a stable CLO or capture final vendor f64 samples. The former dedicated Stage48 Frida scripts were subsequently **removed from the current Git tree** by explicit project workflow decision. Canonical tools now live in `tools/frida_capture.py`, `tools/frida_guarded.py`, `tools/FRIDA_WSL.sh` and `tools/FRIDA.md`; the corresponding Stage48 parameter-only file is `research/htkpa/stages/stage48/frida.json`. For all future stages, extend shared /tools behavior and use a separate stage-local JSON, README and evidence rather than cloning a runner.
