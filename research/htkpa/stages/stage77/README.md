# Stage77 — named registry registrations and the fifth factory family

**Original-DLL source-only status (2026-10-15):**
`FOUR_NAMED_STATIC_REGISTRATIONS_CALLBACK_BRIDGE_RUNTIME_KEY_UNPROVEN`.

The independent auditor read the private, exact-SHA native `5868USB.dll` as
**inert original PE64 bytes**, reran Stage76 and its previous source gates,
and verified **100/100 new instruction anchors across 10 `.pdata` functions**,
**four original PE-backed name literals**, and **two PE-backed 64-bit vtable
method slots**. GNU objdump Intel syntax was used. No DLL execution, Frida,
metadata/audio capture, production or Resampler Lab change, or user WSL
dependency was involved.

## Four exact named registration sites

The DLL contains four directly observable, matching registration sequences.
Each sets up a polymorphic wrapper with the **same native wrapper vtable
RVA `0x246EF0`** and a different function pointer in wrapper slot `+0x8`.
It passes a string literal and that wrapper to registry-insertion function
`0x35EE0` after obtaining the registry from `0x35DF0`.

| File-backed name | Registration function | String RVA | Registered builder RVA |
|---|---|---|---|
| `SlimmableContainer` | `0x19F0` | `0x18F488` | `0xC5610` |
| `ConvNet` | `0x1B50` | `0x18F578` | `0xC62B0` |
| `LSTM` | `0x1D30` | `0x18FA24` | `0xCC690` |
| `WaveNet` | `0x1F50` | `0x190C38` | `0xD01A0` |

Every wrapper vtable load, builder-function LEA, string length, string
pointer LEA, string-construction call, registry accessor call,
holder-transfer call, and insertion call is independently pinned.
String bytes are verified in the **original file**, including the exact
termination byte. These are **four positive static registration sites**,
not evidence that the complete runtime registry has only four entries.

## The bridge back to Stage76's callback

Native `0x35EE0` uses the same FNV-1a 64-bit hash as the Stage76 lookup:
its seed/multiplier and byte loop at `0x35F3D–0x35F72` are source verified.
The `0x36035/0x36038` branch can exit the normal insertion route, so mere
existence of a registration function does not prove which entries are live.

When the positive insertion path is followed:

1. `0x3604B` inserts/obtains the new hash-table node through `0x38160`.
2. `0x36050` loads the node; `0x36055` advances to `node+0x30`;
   `0x36081` calls `0x69A0` to copy the callback holder.
3. `0x69C7` or `0x69F3` stores the holder into destination offset `+0x38`,
   giving `node+0x30+0x38 = node+0x68`. This matches the Stage76 lookup's
   **`0x3F70F [node+0x68]`**.
4. The wrapper vtable's **file-backed slot `+0x10`** (`0x246F00`)
   points exactly to native `0x38540`. When selected, the Stage76 indirect
   `0x3F731` dispatch can therefore reach this method.
5. `0x3854A` reads the rate argument as f64 into XMM2; `0x3855D` calls
   **`[wrapper+0x8]`** — the per-name builder pointer registered above.
   `0x3856A` transfers the resulting object pointer to the caller's output.

This provides a **source-backed possible mapping** from those four exact
names through their wrappers to their builders. It does not prove that a
given Stage64 file carried any one name, that registration succeeded at
runtime, or that no other entries/callback implementations were present.

## Fifth factory family: `SlimmableContainer`

Stage75 identified four candidate factory vtables; Stage77 adds an
independent, original-file-backed candidate:

- Builder `0xC5610` installs **vtable `0x246E98`** at `0xC5656/0xC565D`.
  The builder saves incoming rate XMM2 in XMM6 (`0xC5632`) and writes an
  f64 to its factory object's `[RDI+0x18]` at `0xC56A4`.
- Original PE slot `0x246EA0` (`vtable+0x8`) points exactly to
  **virtual method `0xC56D0`**. This slot is distinct from the Stage75 four.
- That method saves incoming XMM3 into XMM8 at `0xC570F`, forwards XMM8
  as XMM2 at `0xC5B83`, and directly calls result constructor `0xC5F40`
  at `0xC5B8E`.
- The result constructor **writes XMM2 f64 to `[RCX+0x18]` at `0xC5F90`**,
  which is a second native source-backed result-field writer besides
  Stage75's `0xCA44B` common writer.

This is an independently verified positive static chain, **not a runtime
observation** and not an assertion that all candidate vtables are enumerated.

## Reproduction and boundaries

Synthetic offline tests, which do not need the vendor DLL:

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage77.py' -v
```

Original-PE audit (already run by the researcher; private file is ignored):

```bash
python research/htkpa/stages/stage77/audit_named_registry.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage77_named_registry.json
```

All prior-stage gates, PE `.pdata` owner entries, exact disassembly anchors,
four literals (including NUL) and two file-backed absolute pointers must
match. The script fails closed on drift and refuses output over the DLL.
**8/8 new Stage77 offline tests and 61/61 combined Stage70–77 tests passed.**

**Still unproven:** the architecture/name from the specific Stage64 capture,
which registry entry was present or selected, the runtime callback and
factory object identities, the actual Stage64 reverse input rate, whole
vendor antialiasing and lab parity. Source-derived branches and candidate
paths must not be silently promoted to live evidence.

**Next only upon `#next`:** trace the input architecture/name provenance
through the actual NAM→CLO entry point and determine whether existing
non-payload metadata can constrain the Stage64 key. No automatic live probe,
hook, DSP modification, WASM, or Resampler Lab edit.
