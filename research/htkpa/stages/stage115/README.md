# Stage115 — original-PE NAM worker float32 block / virtual-call static boundary

**Status:** `STAGE115_ORIGINAL_PE_FLOAT32_BLOCK_VIRTUAL_CALLSITE_STATIC_VERIFIED`. Genuine original 2,902,016-byte SHA-pinned `5868USB.dll` was analyzed as **inert static bytes** in the assistant cloud environment (2026-10-21 Bangkok). **17/17 synthetic PE/mutation tests PASS.** See [operator result](OPERATOR_RESULT_20261021.md) and [evidence](evidence.json).

## Question

Does the previously proven native `getNamOutput`-associated function (`0xE0E0`) contain a disassembler-verified local handoff of **float32 audio blocks** into a model-associated virtual processing method, closer to the pre-NAM input than the Stage90/96 function-level Frida traces?

## Genuine original-PE result

The fixed original `.pdata` function owner is **`[0xE0E0,0xF940)`**. The independent static auditor verifies **29** complete x64 instruction anchors, **two** relative direct calls, PE32+ AMD64 headers and a unique `.pdata` owner. Confirmed instruction relationships:

1. At **`0xE698`** a direct call goes to the previously established model/weights parser `0xCC4E0`. Its returned object is moved to a local pointer slot `[rsp+0x38]` at `0xE6AD`.
2. At **`0xEB1E`** a separate direct call goes to the known WAV/resampling worker `0xD4A0`. These direct edges belong to the same large original function but do **not** assert every run took the resampler branch.
3. At **`0xF123`** the earlier `[rsp+0x38]` model-object slot is reloaded into `RBX`; the candidate audio source vector is loaded separately from `[rsp+0x98]` into `R15`. The loop limits each processing chunk to **at most `0x400` (1024) elements**. It copies **32-bit sample values** from the source buffer into a stack scratch array around `[rsp+0x710]`.
4. At **`0xF21B–0xF231`**, the code loads the object's vtable, sets `RCX=object`, `RDX=&input_pointer_slot`, `R8=&output_pointer_slot`, and `R9D=chunk_count`, then calls **`qword ptr [vtable+0x10]` at RVA `0xF231`**.
5. Immediately afterward **`0xF284–0xF296`**, it reads scalar float32 values through the returned output pointer, multiplies by a local scalar (not presumed vendor gain `0.31`), and writes float32 values into the output vector.

**Confidence:** the source/copy/chunk/pointer preparation/virtual call/output-store and parser-object-slot chain are direct, SHA-pinned **static PE instructions**. Associating that method with the *effective* NAM inference is a well-supported **candidate** based on the owner/path, but the indirect target function, exact object type, original input sample rate and true buffer provenance are **not verified by this static audit**.

## Method and reproducibility

The stdlib-only `GO.py` verifies original SHA and size, original PE32+/AMD64 image base, section boundaries, unique `.pdata` owner, specific tiny opcode anchors, and the expected call destinations. It writes one private JSON with exclusive creation (`'x'`); no overwrite. The bundled tests use **artificial synthetic PE files only** and include failure cases for modified parser/worker edges, local model-object save/reload, float32 transfers, chunk limit, vtable slot, malformed `.pdata` and architecture, and no-overwrite. No compiler, disassembler, Python package install, Ghidra, or Windows process is required for the checked-in audit.

**Historical one-time cloud command (already executed; do not overwrite):**

```bash
python3 research/htkpa/stages/stage115/GO.py \
  --dll /PRIVATE/5868USB.dll \
  --out /PRIVATE/stage115_static_pre_nam_boundary_private.json
python3 -m unittest discover -s tools -p 'test_htkpa_stage115.py' -q
```

The real private Stage115 report and optional full original-PE disassembly are stored in the user-designated `RE_HTKPA` Drive folder, **not public GitHub**. The original DLL is already present there within `HTKPA_CORE_20261016_012322.zip` and is **not duplicated**.

## Evidence limit / next question

- **Not proved:** Stage97 or Stage96 runtime actually visited `0xF231`, actual vtable slot destination, effective native 48-kHz pre-NAM samples, SHA identity of loaded NAM, DSP numerical parity, vendor resampler, final quantizer, FIR fitter, CLO or device readback.
- **Stage116 candidate (NOT BUILT/RUN):** review whether a **one-site, metadata-only**, crash-aware Frida trace at `0xF231` can establish this candidate call's invocation in a conversion; inspect only bounded stack/pointer and count metadata, **zero audio data** first, and leave the old universal Frida runner architecture unchanged. This would be a *new* user-operated Windows event, not a reconstruction of Stage96 data. Do not start Manager or request an unsafe automatic conversion before an independent preflight and explicit capture scope.

**Stage115 requires no WSL action from the user.** Do not repeat Stage102–115.
