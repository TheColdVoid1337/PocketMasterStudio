# Stage85 — concrete numerical sample-rate lineage into native resampler constructor

**Original-DLL source-only result:**
`STATIC_METADATA_RATE_TO_RESAMPLER_CONSTRUCTOR_ABI_VERIFIED_RUNTIME_PARENT_UNPROVEN`.

The read-only audit uses the original SHA-pinned Sonicake `5868USB.dll` and
reruns every Stage84 and earlier binary/capture/model input gate. It checks
**47/47 additional native instruction anchors** across seven logical entry
points and their original `.pdata` unwind ranges; no native binary execution,
Frida capture, audio conversion, model-weight export or DSP patch occurs.

## Newly closed argument-identity gap

Stage69–70 identified a native 44,100-Hz call to helper `0xCE00` and its
direct `0xCFF3 → 0x11B60` constructor call. Stage72–78 independently found
the source-rate read, input metadata and registered NAM model factories.
Stage85 establishes **which floating-point register becomes which constructor
argument**, and checks the Windows x64 fifth-stack-argument hop that connects
the parsed metadata rate to one *conditional compiled* resampler route:

| Step / RVA | Authenticated original machine-code meaning |
|---|---|
| `0xE698`, `0xE6A7`, `0xE855` | A conditional nonnull result of model/metadata creation is transferred into RBX, then f64 `[RBX+0x18]` becomes f32 XMM9 |
| `0xF620`, `0xF66B` | XMM9 is converted to signed integer, returned in EAX |
| `0x10F7F–0x10F88` | The wrapper calls that rate helper and converts EAX to f64 XMM6, subject to sentinel guard |
| `0x11086–0x110AD` | It narrows XMM6 to f32 and sends the result as the fifth stack argument to `0x10230` |
| `0x1023D`, `0x10287` | Eight pushes and `RBP=RSP−0x27AB8` prove `[RBP+0x27B20]` is `entry RSP+0x28`, the fifth argument, not another field |
| `0x10453`, `0x1045D`, `0xBFE1C` | `0x10230` passes the rate as XMM1 to context initializer `0xBFE00`, retained as XMM10 |
| `0xBFEF9` / `0xC03AE` | Both verified conditional paths write that f32 rate to context `+0x20EC0` |
| `0xBF358`, `0xBF364` | Consumer `0xBE830` reads the same context field as XMM1 and calls `0xCE00` |
| `0xCE38`, `0xCFDB`, `0xCFF3`, `0x11BD0` | The helper saves XMM1 in XMM9, widens it back to f64 **XMM1**, and constructor `0x11B60` preserves that rate in XMM8 |
| `0xBF34D`, `0xBF355`, `0xCE34`, `0xCFD3`, `0x11BCC` | The separately verified original constant **44,100 Hz** enters XMM2, is widened to f64 XMM2, and is received by the same constructor in XMM9 |

The `0x10230` callee stack equation is:

`entry RSP − 8×8 pushes − 0x27AB8 + 0x27B20 = entry RSP + 0x28`.

Thus **on the checked successful branch** an upstream metadata-derived
source-rate number and the fixed 44.1-kHz destination arrive in the
**correct order** at `CDSPResampler24`. The source-rate number is not
necessarily the NAM header's 48,000. It can be altered by the Stage74
48,000 fallback, integer conversion, and different wrapper branches.

## Deliberate evidence limit

- This connects **numerical arguments across one native code path**, not a
  pointer identity from Stage84's `ContainerModel` to a particular resampler.
- Static branch reachability is not proof the path ran during Stage64; its
  96,000→44,100 reverse fractional parent and exact runtime input rate remain
  **unknown**. The `0xFF40 → 0xF940` alternative source-rate wrapper still
  exists and cannot be silently removed from consideration.
- The original Stage64 trace has no same-run input NAM SHA/CLO SHA pair.
  Operator testimony identifies the named 2203 model in *every* NAM-import
  capture, but does not create capture-internal same-run file hashes.
- Other conditional guards, indirect constructors, native model selection
  control, actual child index, anti-alias numeric parity and audio parity
  remain unresolved.

## Reproduce locally (private files are Git-ignored)

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage85.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q

python research/htkpa/stages/stage85/audit_resampler_rate_arguments.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage85_resampler_rate_arguments.json
```

The private report captures RVAs, control limits and accepted gates but no
binary bytes/audio/model payloads. Keep it only in Git-ignored `_LOCAL_FILES`
and its designated **private** Drive folder. The next gate is authentic
Stage64 native object/caller identity, not an assumed 48k live source rate.
