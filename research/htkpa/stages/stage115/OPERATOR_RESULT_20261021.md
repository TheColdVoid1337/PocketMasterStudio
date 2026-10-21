# Stage115 — original DLL static float32 block handoff into a virtual method

**Real result, 2026-10-21 Bangkok:** `STAGE115_ORIGINAL_PE_FLOAT32_BLOCK_VIRTUAL_CALLSITE_STATIC_VERIFIED`. The assistant retrieved `HTKPA_CORE_20261016_012322.zip` from private RE_HTKPA Drive, extracted the original `5868USB.dll` privately, checked **size 2,902,016** and its previously established original SHA256, and decoded instruction contexts using locally available LLVM objdump. A separate published stdlib-only Python auditor then verified the original PE32+ image, `.pdata`, **29 byte-exact instruction anchors** and **two E8 rel32 destinations**. **17/17 independent synthetic PE/mutation tests passed**. No Windows execution/Frida or source WAV/NAM inference was performed.

## Static chain newly pinned

| RVA / interval | Native instruction observation | Interpretation ceiling |
|---|---|---|
| `0xE698 → 0xCC4E0` | Original direct model/weights parser call (`E8`) | Prior NAM-associated parser link; no actual model-byte identity |
| `0xE6AD` | Returned pointer from parser stored to `[rsp+0x38]` | Local model-object slot, not a runtime pointer capture |
| `0xEB1E → 0xD4A0` | Prior WAV/resampling direct call in the same owner | Conditional compiled path, not guaranteed branch taken |
| `0xF123` | `[rsp+0x38]` loaded into `RBX` | Same local slot reused for object dispatch |
| `0xF128` | `[rsp+0x98]` loaded into `R15` | Candidate float32 source-vector holder; rate/provenance unknown |
| `0xF130–0xF14F` | Each chunk bounded to at most `0x400` elements | Computed block bound; not a proven externally observed block length |
| `0xF1B0–0xF20C` | Reads 32-bit source words from `[R15]` vector, copies into stack scratch at `[rsp+0x710]` | 32-bit transfer, later scalar float32 operations in output path; not native sample capture |
| `0xF21B–0xF231` | `RCX=RBX`, `RDX=&[rsp+0x248]`, `R8=&[rsp+0x78]`, `R9D=chunk_count`, `call qword ptr [vtable+0x10]` | Strong local input/output block-processing callsite **candidate** |
| `0xF284–0xF296` | Reads float32 from returned output reference, `mulss` by local scalar, stores float32 | Processing after virtual call; scalar **not** proven to equal open diagnostic `0.31` |

All anchors and calls have the original `.pdata` owner `[0xE0E0,0xF940)` and were checked against the authentic original PE on disk. The parser-save → model-slot-reload and input-copy → vtable-call → output-read structure is stronger static evidence than prior generic Frida entry/exit logs.

## Relationship to previously accepted Stage96

Stage96 truly observed in its **own** Frida run one `0x10E70` wrapper invocation with a nested `0xE0E0` NAM-associated worker and subsequent fitter/resampler activity. However its instrumented function entry/exit event schema **did not observe `0xF231` nor record any pre-inference input float32 sample buffer**. New static instructions cannot retroactively add observations to that archive. Stage97's authentic input WAV is an exported 44.1-kHz source, not a direct native pre-NAM 48k capture.

## What the result does NOT establish

This is a strictly static, SHA-guarded original-DLL audit, not a debugger trace. It does **not** yet resolve `[vtable+0x10]`'s actual callable address or establish the type of the object, the runtime rate (including whether the block is 48k), the origin of the pointer in `[rsp+0x98]`, sample values or model state, or matching between this specific call and the successfully exported Stage97 WAV/CLO. The narrowest next legitimate experiment is a new **metadata-only**, one-site runtime probe at `0xF231`, *only after* instrument contract/preflight testing and explicit risk acceptance; do not attempt an unconstrained bulk audio read or silently rerun a historic capture. The original DLL, disassembly and private detailed report remain in restricted Drive, never public GitHub.
