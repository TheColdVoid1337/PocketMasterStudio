# Stage76 — static registry lookup before the virtual factory

**Source-only status (2026-10-15):**
`STATIC_STRING_KEYED_REGISTRY_CALLBACK_FACTORY_IDENTITY_UNPROVEN`.

The exact-SHA original Windows `5868USB.dll` was inspected locally as **inert
PE64 bytes**. Stage75 and its preceding source gates were rerun. GNU objdump
matched **62/62 new instruction anchors over eight exact `.pdata` owner
functions**. No vendor DLL execution, Frida, audio capture, new hook, DSP or
production changes; the original binary and full generated report remain in
the private ignored workspace.

## New observation: a second indirect boundary precedes `0xCAB81`

Stage74 traced an incoming f64 metadata rate into the factory's XMM3 argument,
and Stage75 verified four candidate vtables whose slot `+0x8` can construct an
object through common f64 writer `0xCA44B`. The missing link is the selection
of the **runtime factory object**, not the common constructor's field offset.

Original instruction anchors now show the selection path:

1. `0xCAA57`: call accessor `0x35DF0`, which lazily initializes a registry-like
   object at global RVA `0x2C74D0` (`0x35E76` calls `0x384F0`).
2. `0xCAA65`: pass a string-like metadata field **`[RBX+0x20]`** as R8 to
   `0x3F5C0` at `0xCAA76`. Additional R9 is `&[RBX+0x40]`; the f64 metadata
   from `[RBX+0x78]` is passed through the stack. The result is written
   through an output pointer `&[RBP-0x61]`.
3. `0x3F626–0x3F653`: the original registry lookup contains the exact FNV-1a
   64-bit seed `0xCBF29CE484222325`, prime `0x100000001B3`, byte-wise XOR,
   multiply and iteration over the key length `[R8+0x10]`. It accesses buckets
   from `[RSI+0x18]` with mask `[RSI+0x30]`.
4. **`0x3F731` is a virtual callback**, `CALL [R10+0x10]`: the registry node's
   `[RBX+0x68]` object supplies a vtable in R10 (`0x3F70F`, `0x3F71F`).
   The callback receives the output pointer and auxiliary metadata arguments.
5. `0xCAAA2/0xCAAAA`: the resulting pointer is transferred into
   `[RBP-0x69]`; `0xCAAB6` passes its address to `0xCAB10`. Only then does
   `0xCAB49–0xCAB81` load its own selected-object vtable slot `+0x8` and
   **`CALL R9`** (the Stage74/75 boundary).

There are therefore **two independently source-proven indirect calls**, and
both targets remain runtime-dependent. Exact FNV hashing does not identify a
specific key, registry entry, callback object or selected factory in the
Stage64 capture. This is a genuine positive topology result, not a proof of
the Stage64 reverse object's parent.

## Four candidate vtables are actually installed by native source

In addition to the Stage75 file-backed `+0x8` slots, Stage76 verifies
RIP-relative address loads and corresponding *native object-vtable writes*:

| Factory candidate | LEA of vtable VA | Store to object | Original PE vtable RVA |
|---|---|---|---|
| A | `0xC62FE` | `0xC6305` | `0x246FB0` |
| B | `0xCC6CE` | `0xCC6D5` | `0x247708` |
| C | `0xD02CD` | `0xD02D4` | `0x247BA8` |
| D | `0xDD2B6` | `0xDD2BD` | `0x247CC0` |

Source at `0xD01DC/0xD01E3` also shows a **conditional branch** in the
function that can construct D (`0xD0200`) or later C (`0xD02CD`), depending
on parsing/validation. The branch selected by a real Stage64 input is
unobserved. Neither these installations nor the Stage75 vtable method slots
prove that any corresponding object was registered under the Stage64 key.

## Reproduction

Offline source-contract tests (synthetic PE and mock disassembler only):

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage76.py' -v
```

Exact original-SHA PE audit (run independently by the researcher; file is
intentionally excluded from Git):

```bash
python research/htkpa/stages/stage76/audit_registry_selection.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage76_registry_selection.json
```

The auditor rereads Stage75, checks `.pdata` ownership, validates the exact
62 instructions and RIP-relative targets against Stage75 vtable RVAs. The
small FNV helper is used **only for offline synthetic vectors**, never as a
claim about a captured real key. Missing/mismatched native bytes, owners,
instructions or upstream claims fail closed. The original DLL cannot be the
report output path.

**Verification:** 8/8 new Stage76 tests passed; combined Stage70–76 regression
was run independently. The exact run summary and limits are in
`evidence.json`.

## Hard limits and next gate

- Neither registry callback `0x3F731` nor factory call `0xCAB81` has a
  statically resolved target for the *specific* Stage64 reverse call.
- Stage64 runtime registry key, entry state, parser branch, factory vtable,
  constructed-object alias and source rate remain unverified.
- A 48 kHz fallback exists in source (Stages73–74), but has not been shown
  to apply to that particular Stage64 object; whole-pipeline antialiasing
  and standalone lab equivalence are **not** established.

**Next only on `#next`:** source-first mapping of registry registration sites
and callback implementations keyed by architecture/string, preserving the
dynamic gap if selection still depends on runtime data. Any metadata-only
live observation needs a separate explicit decision. Do not add hooks, DSP
patches or production/Resampler Lab edits automatically.
