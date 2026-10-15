# Stage81 — original `sample_rate` ingress and authenticated nested NAM layout

**Accepted, source-only (2026-10-15 UTC / 2026-10-16 Bangkok):**
`STATIC_SAMPLE_RATE_JSON_TO_F64_METADATA_VERIFIED_2203_NESTED_WAVENET`.

The capture operator has confirmed that **all their Frida NAM-import captures,
including Stage64**, used `JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`.
That is firsthand filename testimony. Stage64 still does **not** contain an
independently recorded input NAM SHA256 and completed CLO SHA256 for the same
conversion. This distinction is carried forward from the Stage80 correction.

## New positive finding in the exact original `5868USB.dll`

Stage78 established an `architecture` JSON key path into the named registry;
Stage74 identified a f64 metadata field at `+0x78`, without showing where
the native parser populated it. Stage81 statically connects the native
`sample_rate` JSON property reader to that field:

| Original PE64 RVA | Verified source fact |
| --- | --- |
| `0x18F920`, `0x18F930` | Both exact file-backed, NUL-terminated `sample_rate` literals |
| `0xCA651 → 0xCA65B` | Reader passes the primary literal into native property lookup `0x2D3B0` |
| `0xCA663`, `0xCA689`, `0xCA69B`, `0xCA6A1` | Parser inspects JSON kind; has f64 and integer-to-f64 value paths |
| `0xCA6D4` | Conditional fallback loads original PE-backed f64 **−1.0** from `0x24CED0` |
| `0xCB5ED → 0xCB5F2` | Metadata parser calls the reader, stores its XMM0 f64 into `[R14+0x78]` |
| `0xCAE71`, `0xCAFC6 → 0xCAFCE` | Marshaller passes the same R13 metadata output object to parser `0xCB200` |
| `0xCB026 → 0xCB02C` | The original value is read from `[R13+0x78]` and copied as f64 to packet `[RBP+0x108]` |

**19/19 new exact disassembly pins, both PE key literals, the native sentinel,
and original `.pdata` owners** verified with SHA-gated GNU objdump against
the original DLL. The source path is conditional, and the sentinel does not
assert a live 48-kHz value; no native Windows code was executed.

Stage74 previously followed this packet toward the virtual factory call.
Stage81 fills the **source-field-to-packet gap**, but does *not* resolve which
factory was instantiated or whether its object later supplied the Stage64
reverse resampler. That still requires independent runtime/object lineage.

## Exact private model structure (no weights exposed)

| SHA-authenticated original NAM | Top level | Nested models | Thresholds (`max_value`) | Declared rate |
| --- | --- | --- | --- | --- |
| Operator-attested 2203 | `SlimmableContainer` | Two `WaveNet` submodels | `0.5`, `1.0` | 48,000 Hz (also nested) |
| Separate SC20 control fixture | `SlimmableContainer` | Two `WaveNet` submodels | `0.5`, `1.0` | 48,000 Hz (also nested) |

The matching structure **cannot distinguish the two original NAM files**.
The Stage64 2203 identification comes from the operator, not these shape
fields or the 8,840-byte CLO size. Nothing establishes which nested WaveNet,
if any, was selected or active inside that historical conversion. Nested
weights and model metadata are excluded from all reports.

## Verification / private provenance

Original source checks SHA256-pin the DLL, Stage64 Frida tar, two original NAMs
and reference CLOs through Stage80 before inspecting any Stage81 input.
Original files remain under the ignored `research/_LOCAL_FILES` directory.

```bash
python3 -m unittest discover -s tools -p 'test_htkpa_stage81.py' -v
python3 -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q

python3 research/htkpa/stages/stage81/audit_sample_rate_ingress.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage81_sample_rate_ingress.json
```

Observed: **12/12 Stage81 synthetic tests**, **101/101 Stage70–81 tests**,
original exact-SHA read-only Stage81 CLI **PASS**. No Frida, original DLL
execution, WAV/F64 processing, weights dump, or production DSP changes.

**Next gate:** establish conditional native builder/runtime selection and the
specific object handed to the 96k→44.1k reverse resampler parent. Do not turn
static `sample_rate` ingress into a claim of an observed live 48-kHz path,
anti-aliasing parity, or a byte-exact Stage64 model↔CLO association.
