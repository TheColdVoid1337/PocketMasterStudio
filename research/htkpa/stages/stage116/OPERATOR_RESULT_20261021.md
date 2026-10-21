# Stage116 — original-PE single-callsite register probe READY, Windows runtime PENDING

2026-10-21 Bangkok. **Static original-DLL preflight performed:** the authentic original `5868USB.dll` (2,902,016 bytes) was extracted *privately* from the previously accepted CORE archive, SHA-gated and inspected **as inert bytes** with the original Stage115 29-instruction and 2 direct-call checks. Stage116 exact config gate passed. **20/20 synthetic Stage116 tests PASS; 37/37 combined Stage115+116 PASS**. No Manager, native Frida, NAM inference, new resampling, fitted gain/lag/DC, FIR, CLO or device operation.

## Question and designed evidence boundary

A runtime invocation of the **specific** original instruction at RVA `0xF231`, compiled inside `getNamOutput`-associated owner `[0xE0E0,0xF940)`, would be a more discriminating next observation than prior Frida caller nesting alone. The original instruction is `call [rax+0x10]` after compiler-proven float32 chunk assembly from a candidate source vector. The observed **caller register values** would help establish whether that compiled site runs at all in a future actual conversion. They do not establish contents or data provenance.

The existing **legacy scalar universal Frida runner** is used, with ONE site (RVA `0xF231`) and maximum **8 recorded hits**. Required direct register fields: `RCX`, `RDX`, `R8`, `R9`. `RCX` is model-object-associated, `RDX`/`R8` designate local pointer slots and `R9D` carries the count clamped by compiler to at most **1024** elements. The prepared Frida configuration **never requests dereferencing** those pointers or copying any bytes.

Stage116 offers `GO.py preflight` and a strict `GO.py audit` of a **future** capture. The second mode authenticates original loaded-module SHA, the exact normalized config, single hook readiness, hit counts/PC ASLR and four register fields; rejects binary payloads and all runtime/field errors; it returns public-safe counts but not raw pointers. Synthetic positive/negative TAR fixtures verify fail-closed behavior. This does **not** implement a custom Frida launcher or run the Manager.

## Real current outcome

`STAGE116_STATIC_PINNED_ONE_SITE_METADATA_PROBE_READY_RUNTIME_PENDING`

- Original SHA + PE32+/AMD64 metadata and Stage115 29 instruction pins: **PASS** (real original DLL, offline).
- Exact single-site four-direct-register config: **PASS**.
- Source/test regression suite Stage116: **20/20 PASS**; Stage115+116: **37/37 PASS**.
- Actual Windows Frida hook attached at `0xF231`: **NOT ATTEMPTED**.
- Any native `0xF231` hit or chunk-size observation: **NOT OBSERVED**.
- Vendor 48-kHz pre-NAM sample contents, vtable target, actual model bytes, Stage97 invocation identity, resampler/quantizer/fitter/CLO/device parity: **NOT VERIFIED**.

**Next legitimate gate:** one consciously supervised Windows capture with the existing universal Frida runner *after* separate no-attach preflight. Because previous NAM import runs have included a crash, avoid automatic retries and preserve any interrupted archive. Raw private files belong exclusively in `RE_HTKPA`; keep the public ledger restricted to source-validated static facts and any later sanitized run outcome.
