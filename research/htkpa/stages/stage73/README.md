# Stage73 — incoming wrapper ancestry and source-rate candidates

**Original-DLL source-only result (2026-10-15):**
`SOURCE_RATE_HELPER_TWO_CANDIDATES_RUNTIME_PARENT_UNPROVEN`.

The researcher ran this audit **independently on the original pinned
`5868USB.dll`**, privately supplied in the earlier rollover ZIP, using GNU
`objdump` in Intel syntax. **34/34 original instruction pins** and four
file-backed PE floating constants matched. The DLL was never loaded/executed.
Only sanitized code, tests, source observations and evidence are committed;
the DLL and complete local report remain private and Git-ignored.

## Incoming parent chains

Stage72 showed two direct incoming calls to the context rate consumer
`0xBE830`. Stage73 identifies both wrappers' entry points and shared rate
helper without inferring which path was active during Stage64:

| Entry/direct parent | Wrapper | Next direct call | Stage72 context consumer |
|---|---|---|---|
| `0x11666` in `0x11550`; `0x611AF` in `0x60F20` | `0xFF40` | `0x1016D → 0xF940` | `0xFA41 → 0xBE830` |
| `0x11734` in `0x11550`; `0x6137D` in `0x60F20` | `0x10E70` | `0x110AD → 0x10230` | `0x104E1 → 0xBE830` |

The `0x11550` parent inspects DWORD `[rcx+0x270]` against `1` at
`0x1158B`, with a branch at `0x11592`. This is a *static* mode selector,
not evidence of Stage64's actual mode. Other indirect parents may exist.

Both wrappers call the same larger helper `0xE0E0`, at `0x10043` and
`0x10F7F`. Both convert its integer EAX result to a floating-point value
and compare it with the original PE float64 **−2.0** sentinel at RVA
`0x24CEF0`; a negative sentinel path is not a valid observed rate.

## Where the source frequency can come from

The original `0xE0E0` helper has two source paths for XMM9 before its
successful float-to-integer conversion at `0xF620` and EAX return at
`0xF66B`:

| Instructions | Source candidate | Meaning |
|---|---|---|
| `0xE855`, `0xE85B` | f64 `[rbx+0x18]` → f32 XMM9 | Frequency supplied from an object; identity, original file and live value remain unknown |
| `0xE9B5–0xE9EA` | file-backed f32 **48 000.0** at PE RVA `0x24CDF4` | Conditional fallback when the compare against zero at `0xE9B8/0xE9BC` does not jump |

`0xEA01` subsequently compares XMM9 to a *separate* file-backed f32
**44 100.0** at RVA `0x24CDF0`. Merely seeing either constant or branch
does not establish which rate was used in the Stage64 reverse capture.

The `0x10E70` wrapper converts the helper's integer result through XMM6
(`0x10F84`, `0x10F88`), converts f64 back to f32 (`0x11086`), places
the result in its fifth stack argument (`0x11093`) and directly calls
`0x10230` at `0x110AD`. Stage72 traced this argument onward to the
`0xBE830` source-rate field via `0xBFE00`.

The other wrapper `0xFF40` also tests the helper return but loads an
independent **44 100.0 f64** constant from RVA `0x24CCF8` at `0x100DA`
before calling `0xF940` at `0x1016D`. Stage72 already demonstrated the
f32 44 100 source-context initializer inside `0xF940`; the helper's
returned numeric value is not the forwarded source rate in that chain.

## Bounded control-flow check

Starting at the helper's verified function entry `0xE0E0`, the audit
conservatively explores both arms of each directly decoded conditional
jump, tracking XMM9 definition labels until `0xF620`. On the original
DLL it visited **2,031 instruction/state pairs** and found exactly two
candidate labels along decoded paths: **metadata +0x18** and **48k
fallback**, with **zero unresolved local jump sites**. This is a closed
set *on the examined local instruction paths only*, **not** a guarantee
about Windows exception edges, unknown cross-function effects, aliases,
the live source object, or actual execution. The analysis assumes
conforming Windows x64 preservation of nonvolatile XMM9 across calls.
Any unrecognized XMM9 assignment, indirect jump or analysis budget
exhaustion prevents the local closed-set flag.

## Reproduce

Offline synthetic tests, without the vendor binary:

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage73.py' -v
```

Assistant's independently executed original-DLL audit (where the
private DLL has been placed under the Git-ignored local folder):

```bash
python research/htkpa/stages/stage73/audit_incoming_rate.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage73_incoming_rate.json
```

The tool also supports an explicit `--objdump` path and either LLVM or GNU
Intel disassembly. It rejects an unpinned DLL SHA, missing/changeable
source instruction anchors, altered native PE constant bytes, and unsafe
output pointed directly at the input DLL. The complete local report
remains at `research/_LOCAL_FILES/stage73_incoming_rate.json`.

**Still not proven:** the runtime identity of the Stage64 reverse
fractional object's parent, execution of the 48k fallback, the actual
whole-native input rate of that object, or complete vendor antialias
performance. No DSP, Resampler Lab, hook, browser or WASM behavior was
modified.

**Next (only upon `#next`):** identify the producer and meaning of the
metadata object's f64 `+0x18` and the precise fallback branch predicate,
then decide if a tightly scoped metadata-only runtime check is necessary.
No speculative DSP edit or automatically deployed hook.
