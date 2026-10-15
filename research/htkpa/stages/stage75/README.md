# Stage75 — candidate virtual factories and the f64 `+0x18` writer

**Original-DLL source-only status (2026-10-15):**
`FOUR_STATIC_FACTORY_CHAINS_TO_F64_FIELD_WRITER_RUNTIME_TARGET_UNPROVEN`.

The researcher ran the Stage75 audit independently on the **original
SHA-pinned 5868USB.dll** from the private rollover ZIP. It reran Stage74,
Stage73 and their original-byte prerequisites, then matched **38/38 new
instructions across 10 original `.pdata` functions** plus **four exact
file-backed 64-bit vtable method pointers**. GNU objdump Intel syntax was
used; no DLL execution, Frida, audio/f64 payload capture, DSP modification
or user WSL work was needed.

## The newly verified field writer

Native function `0xCA430` is a candidate common constructor. Its original
instructions:

- `0xCA43B/0xCA442`: install a vtable at RVA `0x247018` into the object.
- **`0xCA44B`: `MOVSD QWORD PTR [RCX+0x18],XMM3`** — actual f64 write
  at the same offset later read in the Stage74 helper at `0xE855`.

This proves a *native writer exists* with a matching offset and input
register; it does **not** yet prove that the Stage64 object being read
was constructed by this function.

## Four source-backed factory candidates

`0xCAB49/0xCAB4C` dereferences a factory-object vtable;
`0xCAB4F` reads method slot `+0x8` into R9 and `0xCAB81` calls that
**indirect target**, with f64 XMM3 supplied at `0xCAB53`.

The original PE contains these four verified pointers at exactly the
same vtable slot offset. Each pointed-to function contains a *direct*
path through a derived constructor into `0xCA430`:

| Candidate family | Factory vtable + `0x8` slot | Method RVA | Verified direct chain to `0xCA430` | Result pointer store |
|---|---|---|---|---|
| A | `0x246FB8` | `0xC64A0` | `0xC6527 → 0xC76C0`; `0xC7737 → 0xCA430` | `0xC652D` |
| B | `0x247710` | `0xCC730` | `0xCC798 → 0xCD220`; `0xCD261 → 0xCA430` | `0xCC79E` |
| C | `0x247BB0` | `0xD0C10` | `0xD0CF9 → 0xD4F40`; `0xD4FF3 → 0xCA430` | `0xD0CFF` |
| D | `0x247CC8` | `0xD9B90` | `0xDA83D → 0xDB7D0`; `0xDB81F → 0xCA430` | `0xDA843` |

Corresponding vtable bases are `0x246FB0`, `0x247708`, `0x247BA8`,
and `0x247CC0`. These are **positive file-backed candidates**, not
an exhaustive registry inventory and not a runtime-vtable identification.
An arbitrary vtable can have other methods or implementations at `+0x8`.

Source disassembly also verifies the f64 argument forwarding pattern:

- A/B: incoming XMM3 is saved via nonvolatile XMM6 and a stack f64;
  constructors reload XMM3 before calling `0xCA430`.
- C: incoming XMM3 is saved in XMM6 and passed on the stack; the derived
  constructor reloads that f64 into XMM3 at `0xD4FEB`. A different
  float32 value briefly occupies XMM3 in the factory method, which is
  **not** evidence that the f64 constructor input was replaced.
- D: the method saves incoming XMM3 in XMM7, writes a stack f64 at
  `0xDA7FC`, and the derived constructor reloads XMM3 at `0xDB80D`.

In each case the pointed-to method is a *candidate* executable path to a
matching f64 writer. These static source paths do not establish that
all branches return normally, that the factory actually ran in Stage64,
or that its constructed object is the one later passed to the resampler.

## Why runtime parent remains unproven

Stage74 identified an object from a registry/lookup and the indirect
factory call `0xCAB81`, but it did not establish which runtime object
was stored at its `RCX` argument. Stage75 does not equate the four
file-backed vtables with that runtime object's actual vtable. The
dynamic selection and object alias have to be traced separately.

The exact fallback result from Stage74 is unchanged: **ordered positive
metadata retains its rate; ordered zero or negative input takes the
48 000 Hz fallback**. Neither the specific Stage64 reverse rate nor
the whole native anti-aliasing pipeline is therefore proved.

## Reproduce and limits

Synthetic offline tests (no original DLL required):

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage75.py' -v
```

Independently executed exact-original-PE audit in the researcher's
private, Git-ignored workspace:

```bash
python research/htkpa/stages/stage75/audit_virtual_factories.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage75_virtual_factories.json
```

The script supports GNU or LLVM objdump, verifies the SHA and previous
stage source claims, checks ten `.pdata` owner entries, all 38 exact
instruction pins, the four PE-backed vtable pointers, and both direct
calls in each candidate chain. It rejects altered or missing data, and
refuses to overwrite the original DLL. The local full JSON and vendor
binary stay private/ignored. **8/8 new Stage75 offline tests and 45/45
combined Stage70–75 tests passed**.

**Next (only upon `#next`):** trace the name/registry lookup and the
selected factory object's vtable identity at `0xCAB81` to determine
whether any verified candidate can be connected to the specific Stage64
object. If the static lookup remains unresolved, explicitly decide
whether a narrowly scoped metadata-only dynamic observation is justified.
No automatic Frida hook, DSP/Resampler Lab/WASM or production changes.
