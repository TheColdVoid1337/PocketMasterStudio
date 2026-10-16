# Stage88 — complete decoded direct callsite inventory of `0xCE00`

**Status:** `STATIC_SIX_DIRECT_GROUP_CALLSITES_AND_RATE_FAMILIES_VERIFIED_RUNTIME_CALLSITE_UNBOUND`.

Stage87 proved a conditional group → parent `0x11850` → fractional child
`0x135C0` virtual-dispatch path but examined only two callers of
`0xCE00`. **Correction:** the original DLL's disassembled `.text`
contains **six** explicit `call rel32` instructions targeting that helper.
Stage88 verifies the entire decoded direct-call inventory, each five-byte
original PE `E8 rel32` target, the authentic `.pdata` owner, the
surrounding argument setup and three original f64 source-rate constants.
No Windows DLL code was executed.

## Six source-backed direct calls, four rate families

All locations are original RVAs in `5868USB.dll`. The helper receives the
source rate in XMM1 and destination rate in XMM2 (f32); Stage85 independently
checked forwarding to the parent constructor as f64.

| Owner | Call RVA(s) | XMM1 source rate | XMM2 destination rate |
|---|---|---|---|
| `0xD4A0` | `0xD786` | f64 at `[R14+0x8]` converted to f32 | f64 function-entry XMM2, preserved in XMM6 and converted to f32 |
| `0x11160` | `0x112A2`, `0x113C4` | f64 literal selected via word `[RCX+0xA]`: 44100, 48000 or 96000; converted to f32 | f64 function-entry XMM1, preserved in XMM8 and converted to f32 XMM10 |
| `0xBE830` | `0xBF364`, `0xBF47F` | f32 context `[R14+0x20EC0]` | PE literal 44100.0f |
| `0xE2640` | `0xE28F1` | f64 at `[R14+0x8]` converted to f32 | PE literal 44100.0f |

The `0x11160` rate-selector instruction chain `0x1119A–0x111C0`
implements this *compiled* mapping, checked with exact branch instructions
and original PE-backed eight-byte literals:

| Selector word | Original DLL source rate |
|---|---:|
| `0` or values other than `1`/`2` | 44100 Hz (literal RVA `0x24CCF8`) |
| `1` | 48000 Hz (literal RVA `0x24CD00`) |
| `2` | 96000 Hz (literal RVA `0x24CD10`) |

The two `0x11160` calls process distinct parts of a buffer (fields
`+0x7C`/`+0x84`, offsets `+0x78`/`+0x80`). The two
`0xBE830` calls likewise read two context buffers at
`+0x24408` and `+0x24410`; a pair of context flags at
`+0x243D9` and `+0x243DA` guards their containing path. Exact
pointer aliases for historical objects are **not** claimed.

## What this corrects — and what it cannot establish

Stage87's two verified callers (`0xBF364`, `0xE28F1`) are genuine,
but **not exhaustive**. Stage88 newly accounts for `0xD786`,
`0x112A2`, `0x113C4`, and `0xBF47F`. The decoded-direct-call
enumeration is complete for this fixed original `.text` and selected
disassembler. It does **not** enumerate indirect calls, virtual dispatch
via other functions, altered/obfuscated control flow or runtime paths.

The historical Stage64 capture includes four forward `88200/48000` and
seventeen reverse `96000/44100` fractional guard records. A reverse
`96000/44100` pair is **compatible** with the `0x11160` selector
when it equals `2` and the caller-supplied target is 44100; it is
also compatible with other callers whose dynamic source/target inputs
can take those values. The rate pair does **not** identify the historical
callsite, caller stack, parent pointer, selector value, active constructor
branch or NAM object identity. The operator attests every NAM-import
Frida capture used `JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`,
separate from an authenticated same-run NAM/CLO hash (absent).

## Reproduce offline, with the original private files

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage88.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q

python research/htkpa/stages/stage88/audit_all_group_callsites.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage88_group_direct_call_inventory.json
```

The original-source run passed **6/6 direct call encodings**, **60 exact
additional instruction anchors**, **3/3 double-rate constants**, and
**32 new mutation/regression tests**; **221/221 Stage70–88 tests pass**.
The full generated report and authenticated originals stay private in
the user's Google Drive `RE_HTKPA` folder:
https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK

**Next:** historical Stage64 runtime callsite remains
`UNBOUND`; a bounded same-run Frida return-address/parent-pointer capture
would be decisive. Additional static work should target precisely defined
upstream caller guards, never infer a historical selector from rate alone.
