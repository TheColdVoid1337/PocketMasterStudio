# Stage82 — static `SlimmableContainer` nested-model construction and rate guards

**Result:** `STATIC_SLIMMABLE_SUBMODEL_RECURSION_AND_RATE_GUARDS_VERIFIED`.

The original private `5868USB.dll` was inspected **as inert PE bytes**, at
SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
The Stage81 SHA-authenticated original 2203 and SC20 NAMs and the Stage64
capture were rechecked as prerequisites. This stage executed no vendor code,
Frida capture, original neural model or source DSP.

## New positive native chain

The previously verified Stage77 named `SlimmableContainer` registry candidate
has builder `0xC5610` and a vtable `+0x8` method at **`0xC56D0`**. Stage82
extends that independently anchored method:

| Source RVA(s) | Exact source relationship |
|---|---|
| `0xC572E` → rdata `0x18F438` | Loads literal `submodels`; parser lookup at `0xC5735` |
| `0xC574D` | Requires variant type `2` on the decoded path (array-like); the code also checks nonemptiness |
| `0xC5936` → rdata `0x18F428` | Loads literal `max_value`; lookup at `0xC594E` and numeric conversion paths |
| `0xC5A0F` → rdata `0x18CD34` | Loads literal `model`; lookup at `0xC5A27` |
| `0xC5A7F` | Directly calls nested model packet builder `0xCC2B0` with the decoded `model` value |
| `0xCC34B` → `0xCC3AD` | The nested builder calls metadata parser `0xCB200`, then package dispatch `0xCA760` |
| `0xC5AA7`, `0xC5AAE` | Appends a 16-byte element: `max_value` f64 followed by nested model pointer |
| `0xC5B83`, `0xC5B8E` | Forwards caller XMM3 f64 as XMM2 to result constructor `0xC5F40` |
| `0xC5F90`, `0xC6009` | Constructor writes f64 to result `+0x18` and takes ownership of nested element array at `+0x58` |

This is the missing **static link from the `SlimmableContainer` factory method
to recursive nested model packet construction**. The nested packet dispatch
itself is indirect further down and is not proof that a particular `WaveNet`
instance was constructed in the historical Stage64 run.

## Constructor validation

- `0xC606A` / `0xC606F`: adjacent thresholds have a strict ascending
  condition, with a conditional error on non-increasing values.
- `0xC6085` / `0xC608D` / `0xC6093`: reads original f64 `1.0` at `0x24C918`
  and rejects a last threshold below that value on the checked path.
- `0xC60B0` / `0xC60B4`: dereferences each nested pointer and loads its f64
  `+0x18` rate field.
- `0xC60B9` / `0xC60C1` / `0xC60C9` / `0xC60D3`: compare nested and parent
  rates, with original f64 `-1.0` at `0x24CED0` used as an unknown-rate
  sentinel. The native mismatch error literal starts at `0x18F3E0`.

This verifies **conditional source guards** only. Do not infer which guard
ran, a decoded numerical rate in Stage64, or the selected playback submodel.

## Private model and capture provenance

In Stage81 the exact original 2203 NAM and separate SC20 fixture were both
verified to be top-level `SlimmableContainer` v0.7.0, each containing two
`WaveNet` children with `max_value` thresholds 0.5 and 1.0 and declared
48 kHz rates. This shape does **not** distinguish them. The Frida capture
operator independently attests that **all their Frida NAM-import captures,
including Stage64, used** `JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`.
Historical Frida metadata still does not contain a same-run input SHA.

Private originals, traces and generated report remain excluded from GitHub.
The archive and latest handoff are kept in the agreed private Google Drive
folder; its URL is recorded in the latest handoff.

## Reproduce

Synthetic tests without the vendor DLL:

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage82.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q
```

Read-only private original audit:

```bash
python research/htkpa/stages/stage82/audit_slimmable_submodels.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage82_slimmable_submodels.json
```

The original-source audit **PASS** verified 40 new anchors across three
original `.pdata` function owners, three literal values and two f64
constants, following all previous gates. **10/10 new tests and 111/111
Stage70–82 combined offline tests passed.** Drift aborts rather than
reinterpreting private binaries.

**Next only on `#next`:** distinguish a possible static nested construction
from the actual historical Stage64 factory/selected submodel and reverse
resampler parent. If that connection cannot be proved offline, preserve the
gap; do not equate the known 2203 filename with a dynamic branch trace.
