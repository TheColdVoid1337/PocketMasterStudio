# Stage74 — metadata-object ingress, f64 argument and exact 48k predicate

**Accepted source-only original-DLL result (2026-10-15):**
`STATIC_METADATA_TO_INDIRECT_FACTORY_BRIDGE_RUNTIME_FIELD_UNPROVEN`.

The researcher ran Stage74 **independently on the privately supplied
original `5868USB.dll`**, SHA-256
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`,
using GNU objdump Intel syntax. The Stage73 exact native SHA, 34 pins and
native constants were reverified before **47/47 new native instruction
anchors across six function owners** were accepted. No native DLL execution,
Frida hook, original audio/payload extraction or production DSP edit.

## The actual entry to the `0xE855` object read

In the `0xE0E0` helper, the checked path is:

1. `0xE17F` initializes nonvolatile R12 to zero; `0xE60C` initializes
   RBX from R12 (zero).
2. `0xE614` initializes the mode word at `[rsp+0x50]` to zero. At
   `0xE682` the same word becomes R8 for direct `0xE698 → 0xCC4E0`,
   which returns a pointer to an object slot in RAX.
3. At `0xE6A5`, an equal-to-local-slot branch skips ownership transfer.
   Otherwise, `0xE6A7` moves `[rax]` to RBX; `0xE6AA` clears the old
   slot and `0xE6AD` saves RBX to local `[rsp+0x38]`.
4. `0xE6CA` tests RBX; **`0xE6CD` branches to the `0xE855` f64 read only
   if RBX is nonzero**. The preceding block ends with unconditional
   `0xE850 → 0xE5CD` and cannot fall through to this read. The only
   *decoded direct* local jump to `0xE855` is `0xE6CD`.

This proves a non-null check and a concrete pointer-slot provenance **on
this decoded source path**, not the object's dynamic class, identity or
relationship to the specific Stage64 reverse fractional object. Indirect
branch entry and exceptional paths are not proved absent.

## f64 metadata travels through nested constructors

| Step | Original RVA anchors | Verified static transfer |
|---|---|---|
| Parser wrapper | `0xCC511`, `0xCC57C`, `0xCC58A` | Zero R8W from the caller becomes R9W for `0xCAE30` |
| Metadata marshaller | `0xCAE6D`, `0xCB026`, `0xCB02C`, `0xCB034–0xCB042` | Reads f64 `[r13+0x78]`; copies to `[rbp+0x108]`, passes pointer `[rbp+0x90]` and the zero mode to `0xCA760` |
| Zero-mode dispatch | `0xCA780–0xCA788` | High byte of zero mode is zero; direct call into `0xCA810` |
| Packet copy | `0xCA83D`, `0xCA8C5`, `0xCA8CA` | Callee's `rbx=rdx`; its `[rbx+0x78]` equals caller's `[rbp+0x108]`, copied to a new local `[rbp+0x7]` |
| Virtual factory bridge | `0xCAAAE`, `0xCAABD`, `0xCAB36`, `0xCAB4F`, `0xCAB53`, `0xCAB81` | Pointer to local `[rbp-0x19]` becomes R9/RBX; its `+0x20` equals `[rbp+0x7]`. f64 reaches XMM3; **`CALL R9` remains indirect** |

The arithmetic equalities are concrete within the respective call frames:
`0x108 − 0x90 = 0x78`, and `0x7 − (−0x19) = 0x20`.

`0xCAB4F` obtains the method pointer from a runtime vtable's `+0x8`
slot, and `0xCAB81` invokes it via `CALL R9`. **No static resolution of
the actual method and no verified assignment to the final object's
f64 `+0x18` field has yet been obtained.** That unresolved construction
gap must not be represented as a complete end-to-end f64 provenance proof.

## Exact fallback decision

`0xE9B5` zeroes XMM6; `0xE9B8` compares that **zero** to XMM9 using
`COMISS`; `0xE9BC` branches via `JB 0xE9F3`, skipping the `0xE9EA`
native 48 000.0 f32 load. Thus for **ordered floating-point values**:

| Metadata XMM9 value | `0.0 < XMM9` | Result |
|---|---|---|
| Positive (e.g. 44 100 or 48 000) | True, `JB` taken | Keep metadata value |
| Zero, including −0.0 | False | Replace with 48 000 |
| Negative | False | Replace with 48 000 |

On unordered NaN, `COMISS` can signal an invalid floating-point
exception; if masked, unordered comparison flags would take `JB`. This
audit does not assume an MXCSR state or an actual NaN execution path.
`0xEA01`'s later comparison to **44 100** is a separate decision and
does not establish the selected input rate.

## Verification / scope

The local complete report is Git-ignored at
`research/_LOCAL_FILES/stage74_metadata_bridge.json` and contains no
native f64 payload; the original DLL is likewise excluded from GitHub.
Offline synthetic tests require **no** vendor binary:

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage74.py' -v
```

The researcher additionally ran this exact-source audit on the original
PE, without the user needing to run it in WSL:

```bash
python research/htkpa/stages/stage74/audit_metadata_bridge.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage74_metadata_bridge.json
```

The tool detects GNU or LLVM objdump (or accepts `--objdump`), rejects
changed SHA/instruction anchors and unsafe DLL-overwriting output, and
fails closed if the preceding Stage73 source candidates change. On
2026-10-15, **8/8 Stage74 synthetic tests and 37/37 combined Stage70–74
tests passed**.

**Still unproven:** resolution of the `0xCAB81` virtual call; the writer
of the returned object's `+0x18` f64 field; any actual Stage64 runtime
branch, source rate or reverse parent; and complete native anti-aliasing.
No Frida, DSP, Resampler Lab, WASM or production code was changed.

**Next (only upon `#next`):** source-first enumerate/verify candidates for
the virtual factory's vtable `+0x8` method, then look for a concrete
constructor store to object `+0x18`. If this cannot be resolved safely,
evaluate a separately authorized *metadata-only* dynamic check. Do not
automatically hook or change DSP code.
