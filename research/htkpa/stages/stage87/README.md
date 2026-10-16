# Stage87 — original compiled parent → fractional child virtual dispatch

**Result:**
`STATIC_GROUP_PARENT_TO_STAGE64_FRACTIONAL_VIRTUAL_DISPATCH_VERIFIED_RUNTIME_INSTANCE_UNBOUND`.

Stage86 proved that the fractional object guarded in authentic Stage64 has
the original DLL's child vtable `0x245170`, whose virtual slot `+0x30`
is the observed hook `0x135C0`. Stage87 extends the *compiled* proof one
level outward: from two native callers through the resampler-group helper,
through a newly created parent and its vtable, down to the guarded child
virtual method. Both original DLL and historical Stage64 archive remain
SHA-gated; there is **no new Frida run** or DLL execution.

## Exact static call route (conditional)

| RVA / object | Original-DLL evidence |
|---|---|
| `0xE28F1` | Helper `0xCE00` called with source from f64 `[R14+0x8]` narrowed to f32 XMM1; target XMM2 is original 44100.0f |
| `0xBF364` | The *other* compiled call to `0xCE00`, with source XMM1 read from f32 context `[R14+0x20EC0]`; same fixed 44100.0f target XMM2. Stage85 authenticated one conditional metadata-derived rate path into this context |
| `0xCFF3` | Helper allocates `0x78`-byte parent on a guarded path and directly invokes `CDSPResampler24` constructor `0x11B60` |
| `0x11BD7–0x11BDE` | Constructor initially installs original parent vtable `0x244FF8`, whose slot `+0x30` points to `0x11850` |
| `0xCF4C` / `0xCFF8` | Group helper loads `0x244B58`, then replaces the constructed parent's vtable with it; its seven method pointers match the constructor vtable (including `+0x30 → 0x11850`) |
| `0xD018` / `0xD01B` | Helper stores parent pointers into the per-channel array, advancing by 8-byte slots |
| `0xD0D5–0xD10E` | Later processing reloads that array, obtains the parent's vtable method `+0x30`, and performs indirect `call R10` → **`0x11850`** when the checked parent class and successful setup apply |
| `0x118CF–0x11909` | Parent method checks child member **`+0x50`**; on nonnull path loads its vtable and calls virtual method **`+0x30`** |
| Child vtable `0x245170` | The seven qwords remain Stage86-authenticated; **child slot `+0x30 → 0x135C0`**, exactly Stage64's guarded hook |

The original compiled route, with the relevant object guards, is:

```text
0xBF364 or 0xE28F1 → 0xCE00 → constructor 0x11B60
  → parent vtable 0x244B58 → group array
  → parent virtual +0x30 (0x11850)
  → parent [+0x50] → child vtable 0x245170
  → child virtual +0x30 (0x135C0 Stage64 hook)
```

The parent vtable target RVAs in slot order are `0xCD30`, `0x11AC0`,
`0x11B50`, `0x11AD0`, `0x11AC0`, `0x11920`, `0x11850` for both the
constructor's `0x244FF8` and the group's `0x244B58` tables. All 14
qwords are read directly through uniquely file-backed PE sections, plus
the seven child qwords rechecked from Stage86. The original fixed target
constant at `0x24CDF0` is independently checked as 44100.0f.

## Meaning and evidence limit

This narrows the **static DLL topology**: a compiled helper contains a
parent-child virtual route capable of invoking the exact hook monitored
in Stage64. It **does not** prove that the specific historical Stage64
reverse resampler instance used either callsite. The capture contains
no parent pointer, return address or caller RVA. Conditional allocations,
branch decisions, different processor subclasses, group indices and other
input paths may alter runtime behavior. Neither an instance pointer link
to `nam::container::ContainerModel` nor a same-run NAM/CLO SHA is present.
The unrelated `ContainerModel` secondary-interface offset `+0x50` must not
be equated with this native resampler's **child member offset `+0x50`**.

The user explicitly states that **all NAM-import Frida captures** used
`JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`. This is operator provenance;
it is not an in-capture same-run model hash. The original Stage64 forward
and reverse fractional rate metadata was accepted through the earlier
gates, but its actual input sample-rate argument and complete DSP/audio
parity remain unproven.

## Offline reproduction

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage87.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q

python research/htkpa/stages/stage87/audit_fractional_dispatch_chain.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage87_fractional_dispatch_chain.json
```

This checked run used **60 exact original instruction anchors** in five
logical functions, two original parent vtables, and 20 new synthetic
mutation/regression tests (**189 total Stage70–87 tests**). The full
report, private originals, critical ZIP, and rollover HANDOFF belong
solely to the user's canonical private `_LOCAL_FILES` Drive folder.

**Next:** collect a bounded **same-run** parent pointer/caller RVA only
if a user-operated native capture becomes available. Static virtual slot
resolution does not reconstruct historical heap ancestry.
