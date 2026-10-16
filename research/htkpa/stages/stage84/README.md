# Stage84 — original `ContainerModel` RTTI and constructor-selected default child

**Accepted source-only result:** `STATIC_CONTAINER_RTTI_AND_LAST_CHILD_CONSTRUCTOR_DEFAULT_VERIFIED`.

The original SHA-authenticated `5868USB.dll` is **read as inert PE bytes only**.
No original DLL execution, Windows/WSL session, Frida capture, NAM weight
processing, private audio export, or production DSP change is involved.
Stage83 and all earlier model/capture source-hash gates must pass first.

## A positive distinction: constructor default is the **last** child

Stage83 found the `nam::container::ContainerModel` threshold selector at
`0xC5D30`, which can later select a child using an externally supplied XMM1
f64 control. Stage84 inspects the *successful constructor* at `0xC5F40`:

| Original DLL RVA | Original-source effect |
|---|---|
| `0xC6028` | Temporarily zeroes the selected index at result `+0x70` |
| `0xC603A–0xC6045` | Reads record begin/end from result `+0x58/+0x60`; empty records take an error branch `0xC6226` |
| `0xC6050–0xC6056` | Computes `R9=(end−begin)>>4`, i.e. the count of 16-byte records |
| `0xC6064–0xC60E0` | Existing Stage82 guards for ordered maximum thresholds and child sample rates |
| `0xC60E2–0xC60E6` | Computes `R9−1` and exchanges this **last-child index** into `+0x70` |
| `0xC615B` | Returns the constructed result object on the successful path |

Therefore an accepted *two-child* container made from the authenticated 2203
NAM structure `[0.5, 1.0]` would **initially have child index `1`**, even
though an *explicit later* selector invocation with a hypothetical control
below `0.5` would choose child index `0`. The constructor index is a default,
**not** a proof of a selector invocation, actual Stage64 object creation, or
the child active at a historical timestamp.

## A positive interface identity: `nam::SlimmableModel`

The two file-backed vtable[-1] pointers lead to separate native MSVC RTTI
complete-object locators but the same class-hierarchy descriptor:

| Original RVA | What it independently pins |
|---|---|
| `0x246EA8 → 0x255798` | Primary complete-object locator, object offset `0` |
| `0x246F28 → 0x2554B8` | Secondary locator, object offset `0x50` |
| Both locators | Same `ContainerModel` type `0x2A2600` and hierarchy `0x255940` |
| `0x255940 → 0x255480` | Exactly three RTTI base descriptors |
| `0x255A08` | `nam::container::ContainerModel` at object offset `0` |
| `0x2555F8` | `nam::DSP` at offset `0` |
| `0x255958` | `nam::SlimmableModel` at offset `0x50` |

The verifier reads the full NUL-terminated MSVC decorated names directly
from original file-backed `.data` and checks each base-class PMD displacement,
the hierarchy array, both locators and their absolute vtable[-1] pointers.
Stage83's `0x246F38 → 0xC5D30` identifies the secondary interface's
virtual `+0x8` method as the threshold selector. This links its **class and
interface identity** statically; it does not identify any historical caller.

## Evidence boundary

- User/operator testimony identifies every NAM-import Frida input filename,
  including Stage64, as `JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`.
  The original capture still lacks same-run source NAM and completed CLO hashes.
- The original DLL implements constructor-last-child default **and** an
  independently callable virtual threshold selector. Static PE evidence
  cannot decide if/when Stage64 instantiated that class or subsequently
  invoked the selector, or which XMM1/control value it used.
- Neither the live Stage64 child nor the object that created its reverse
  `96000→44100` resampler parent is identified. Full source/DSP/audio parity
  remains unproven. The matching SC20 model structure is a separate control.

## Reproduce

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage84.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q

python research/htkpa/stages/stage84/audit_constructor_default_rtti.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage84_constructor_default_rtti.json
```

**Verified:** 16/16 new exact native instructions, 2/2 vtable RTTI
locator slots, two locators, one hierarchy with three exact base descriptors
and names; 14/14 new synthetic tests, **138/138** Stage70–84 offline tests.
The full private report, critical archive and latest handoff belong in the
canonical user-designated `_LOCAL_FILES` Drive folder, not public GitHub.

**Next only on `#next`:** find authenticated Stage64 evidence of a particular
native object/caller/selector control or trace source-specific ownership of
the reverse resampler. Do not infer a live selected model from constructor
defaults, RTTI names or illustrative threshold values.
