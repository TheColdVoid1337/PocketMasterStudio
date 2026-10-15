# Stage83 — original `SlimmableContainer` selector and child virtual dispatch

**Result:** `STATIC_SLIMMABLE_THRESHOLD_SELECTOR_AND_CHILD_ROUTING_VERIFIED`.

No original DLL execution, Frida instrumentation, model inference, source
audio handling, or WASM/production DSP edits. The private original
`5868USB.dll` (SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`)
was read solely as file-backed PE bytes. Stage82 and all prior source/capture
hash gates were rerun before accepting the new anchors.

## Two concrete vtables in the original result constructor

Stage82 established constructor `0xC5F40` and nested 16-byte records:
`f64 max_value` followed by a child-model pointer. Stage83 verifies
**two separate PE-backed vtables** in that constructor:

- `0xC5FE5/0xC5FEC` install original vtable **RVA `0x246EB0`** at the
  result's base (`+0x0`).
- `0xC5FEF/0xC5FF6` install **RVA `0x246F30`** at result `+0x50`.
  This secondary interface has its own `this` pointer at `base+0x50`.
- The original native array starts at result `+0x58`, ends at `+0x60`,
  and its current-selected-child index is result `+0x70`.

Six individual 64-bit pointers are validated against the *actual* `.rdata`
bytes, rather than inferred from method names:

| Vtable slot | Exact source method | Route |
|---|---|---|
| Primary `0x246EB8` (`+0x8`) | `0xC5F00` | Selected child virtual `+0x8` |
| Primary `0x246EC0` (`+0x10`) | `0xC5F20` | Selected child virtual `+0x10` |
| Primary `0x246EC8` (`+0x18`) | `0xC5D10` | Selected child virtual `+0x18` |
| Primary `0x246ED0` (`+0x20`) | `0xC5E10` | Selected child virtual `+0x20`, after storing forwarded state |
| Primary `0x246ED8` (`+0x28`) | `0xC5EB0` | Iterate *all children*, invoking each child virtual `+0x28` |
| Secondary `0x246F38` (`+0x8`) | `0xC5D30` | Threshold-based selected-child index update |

All selected-child tail-call routes read the current index at result
`+0x70` and dereference the child pointer at
`array_base + index × 16 + 8`. The selector receives its secondary
interface pointer (`base + 0x50`), so its offsets `+0x8`, `+0x10`, `+0x20`
map respectively to the result's `+0x58`, `+0x60`, `+0x70`.

## Verified ordered-threshold selection

The secondary method `0xC5D30` computes the child count from the
16-byte stride at `0xC5D52`, scans thresholds with `COMISD` at `0xC5D65`,
and branches using **strict `JA`** at `0xC5D69`:

> Choose the **first** child where `max_value > supplied XMM1`;
> if there is no such child, use the **last** child index.

If the chosen index differs from the stored current index, it invokes
the chosen nested model's virtual `+0x20` (`0xC5DD2`) and stores the new
index (`0xC5DD5`). The source also contains synchronization around that
change. This establishes the conditional method behavior, *not* the origin
or actual value of XMM1 in Stage64.

For the two SHA-authenticated original 2203 `WaveNet` children with
`max_value = [0.5, 1.0]`, this code implies the following for finite,
ordered **illustrative** input values:

| Hypothetical XMM1 | Selected child index |
|---:|---:|
| `0.499999` | `0` |
| `0.5` (exact equality) | `1` |
| `0.75` | `1` |
| `1.0` or greater | `1` (last-child clamp) |

These are synthetic branch examples, **not a replay, profiling result or
claim that Stage64 chose a given model**. NaN/unordered floating-point
control, machine floating-point exceptions, outside caller contracts and
the physical meaning of the control parameter are not established.

## Provenance / what remains unknown

The operator's firsthand statement still identifies the input *model name*
used for **all Frida NAM-import captures including Stage64** as
`JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`. Both 2203 and the separate
SC20 authenticated fixture happen to have identical sanitized 2-child
topologies, so those thresholds cannot distinguish which NAM's raw bytes
were present. No capture-internal same-run NAM/CLO SHA binding exists.

Although conditional native **selection and child delegation** are now
source-verified, no authenticated Stage64 event establishes its runtime
selector XMM1 value, concrete vtable pointer, selected child index, or
object relationship to the captured reverse 96k→44.1k resampler parent.
Full native anti-aliasing, numeric parity and audio parity remain unproven.

## Verify

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage83.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q
```

Original *read-only* audit, after the prior private files are present:

```bash
python research/htkpa/stages/stage83/audit_slimmable_selection.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage83_slimmable_selection.json
```

**Original-source PASS:** 53/53 exact native instruction anchors, six
original file-backed vtable pointers, four PE `.pdata` owners and three
separately bounded Win64 leaf routines. **13/13 new Stage83 synthetic
tests, 124/124 combined Stage70–83 offline tests pass.** The complete
private audit report and rollover handoff are saved in the user-designated
private Google Drive folder, not public GitHub.

**Next only on `#next`:** search source-linked caller/control provenance
or an existing authenticated Stage64 runtime event proving the selected
native object and resampler parent. If evidence is absent, keep the gap
explicit without constructing speculative Frida data.
