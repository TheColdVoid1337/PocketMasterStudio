# Stage71 — NAM→CLO export ancestry and input-rate field provenance

**Status:** local original-DLL source audit pending. The original Stage70
direct-call gate was accepted in user WSL: both 44.1-kHz callsites reach
helper RVA `0xCE00`, and the helper calls `CDSPResampler24` constructor
RVA `0x11B60` directly at `0xCFF3`. The *runtime* parent of the observed
Stage64 `96000→44100` fractional stage remains **UNPROVEN**.

## Research questions

1. Can a bounded source graph of **direct calls** from the DLL's NAM→CLO
   exports reach the function containing either of the two known 44.1-kHz
   callsites (`0xE28F1` in owner `0xE2640`, `0xBF364` in owner `0xBE830`)?
2. What input sample-rate fields are read immediately before those calls?
   Can the nearby assembly narrow down the origin of the `r14` object
   without claiming dynamic ownership or the actual numerical rate?

`audit_nam_ancestry.py` independently parses the PE64 export table and
strictly checks the four original V1.5.2 names and RVAs:

| Original named export | Exact RVA |
|---|---|
| `namConvertCloData` | `0xE1F70` |
| `namConvertClo` | `0xE22A0` |
| `appNamConvertCloData` | `0xABEB0` |
| `appNamConvertClo` | `0xAC0E0` |

It reuses the Stage70 SHA-gated PE `.pdata` owner and bounded LLVM disassembly
reader, then follows at most five direct-call steps and 128 export-root/function
pairs. Named roots without a unique `.pdata` owner, indirect calls, thunks,
virtual dispatch, control-flow decisions, and unexamined paths are explicitly
unresolved. A hit proves only **compiled static reachability**. A bounded
miss is not evidence that a source connection is absent.

The following original load instructions are also verified:

- RVA `0xE28DC`: `movsd xmm1, qword ptr [r14 + 0x8]` — Float64 source rate.
- RVA `0xBF358`: `movss xmm1, dword ptr [r14 + 0x20ec0]` — Float32 source rate.

For each owner, the script lists prior syntactic assignments to `r14` by RVA
and operand category only. **They are not reaching-definition or data-flow
proofs**: linear code order cannot determine which branch executed or what
the object contained. No real source sample rate is assumed to be 48 kHz.

## Run in WSL

Requires only the original installed exact-SHA DLL, the already accepted
private Stage70 local JSON, Python and your existing LLVM 21.1.8.

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python -m unittest discover -s tools -p 'test_htkpa_stage71.py' -v

python research/htkpa/stages/stage71/audit_nam_ancestry.py \
  --dll "/mnt/c/Program Files/Sonicake/Sonicake Manager/assets/5868USB.dll" \
  --stage70 research/_LOCAL_FILES/stage70_parent_calls.json \
  --out research/_LOCAL_FILES/stage71_nam_ancestry.json
```

The terminal output is compact. The full bounded RVA-only graph is written
inside the Git-ignored local research folder. Do not upload original DLL,
local JSON reports, archived Stage64 capture, disassembly text or audio.
No native process, Frida, NAM→CLO conversion, network access, external
package, WASM, or production/Resampler Lab edit is part of this stage.

## Acceptance and interpretation

- All named export anchors and rate-field instructions must match exactly.
- A direct compiled ancestry path to either/both target owners is positive
  static evidence only; it does NOT identify the dynamically chosen Stage64
  parent or original input-signal sample rate.
- Any missing/indirect/oversized path leaves ancestry unverified; it does
  NOT justify guessing a 48k source or automatically launching Frida.
- Stage71's next decision is whether to analyze a specific source object
  and caller branch further, or, if source-first work is exhausted, design
  a separate tightly guarded *metadata-only* parent probe for approval.

The existing Stage66 numerical references, forward/reverse Resampler Lab,
production NAM/CLO converter, and WebAssembly work are unchanged.
