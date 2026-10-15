# Stage78 — NAM architecture source field and upstream family identification

Source-first, original PE64 **read only**, no DSP modifications, hooks, native
execution or audio reads. Stage77 is rerun as an exact-original SHA/source gate.

## Main new finding

The **original Sonicake `5868USB.dll`** contains an exact file-backed JSON key
`architecture` at RVA **`0x18f890`**. Unlike an isolated keyword search,
disassembly of its property reader and metadata constructor proves this
**conditional static source path** (image base `0x180000000`):

1. In function `0xcb200`, `0xcb44f` points to the exact `architecture` literal;
   `0xcb459` calls JSON property lookup `0x2d3b0`; `0xcb465` calls `0x2d2d0`
   to retrieve its value; `0xcb46d` points at the output object's `+0x20`
   string-like field, into which `0xcb47e..0xcb488` copy the value.
2. In function `0xcae30`, `0xcae71` saves the output object as `R13`, and
   `0xcafce` calls the parser `0xcb200` with this same output object in `RDX`.
   Under the `0xcaf91` conditional branch, `0xcafd6/0xcafdd` copy the object
   to the stack packet at `[RBP+0x90]`, then `0xcafe3/0xcafee` copy its
   `+0x20` string field into `[RBP+0xb0]`.
3. `0xcb038/0xcb042` pass the packet to `0xca760`, which Stage74 proved
   reaches `0xca810` for the zero mode. At `0xca83d`, `RBX=RDX`, and
   `0xcaa65` supplies `&[RBX+0x20]` to registered name lookup `0x3f5c0`
   (`0xcaa76`). Stage76 proved this lookup uses source FNV-1a, with an indirect
   callback. Stage77 proved four exact static registrations for
   `SlimmableContainer`, `ConvNet`, `LSTM`, `WaveNet`.

All links here are from native, SHA-pinned machine code and file-backed
original-PE data; a positive **static** path does **not** prove that one
particular input took that path or picked a particular key at runtime.

## Ready upstream implementations, not newly invented vendor architectures

These are established Neural Amp Modeler concepts:

| Name in original DLL | Primary-source reference | Interpretation |
| --- | --- | --- |
| `WaveNet` | [Official `.nam` spec](https://github.com/sdatkinson/neural-amp-modeler/blob/main/docs/source/model-file.rst) | Documented normal `architecture` field value |
| `LSTM` | Same official specification | Documented normal `architecture` field value |
| `ConvNet` | [Original NAM Core project history](https://github.com/sdatkinson/NeuralAmpModelerCore/issues/47) | Existing native Core architecture family |
| `SlimmableContainer` | [Original NAM Core releases](https://github.com/sdatkinson/NeuralAmpModelerCore/releases) (v0.5.0) | Container for slimmable / A2-family models |

The original native PE also holds file-backed **MSVC C++ RTTI names** with
`nam` namespaces for `ConvNet`, `LSTM`, `WaveNet`, `SlimmableWavenet`, and an
encoded `A2FastModel` specialization. The auditor independently validates all
five complete NUL-terminated strings; these names corroborate use of the
same C++ class **vocabulary**, but do not prove byte-for-byte binary identity,
license provenance, a particular upstream revision or a runtime-selected
architecture.

Useful source starting points:

- [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore) — C++ DSP implementation, **MIT-licensed upstream** (license of the *upstream project*, not a claim about the proprietary vendor DLL).
- [Neural Amp Modeler](https://github.com/sdatkinson/neural-amp-modeler) — trainer and `.nam` serialization spec.
- [NeuralAmpModelerCore releases](https://github.com/sdatkinson/NeuralAmpModelerCore/releases) — release history, including slimmable support.

This makes upstream Core a sensible **reference implementation for source
comparison**, not authority to substitute DSP behavior or claim Stage64 parity.

## Reproduce

Requires the exact original private DLL (SHA256
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`)
and a GNU `objdump` or supported LLVM objdump. Do not commit original DLL or
any private `_LOCAL_FILES` reports.

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage78.py' -v

python research/htkpa/stages/stage78/audit_architecture_provenance.py \
  --dll /path/to/private/original/5868USB.dll \
  --out research/_LOCAL_FILES/stage78_architecture_provenance.json
```

The full Stage70–78 synthetic suite passes **69 tests** (Stage78 contributes
8), and Stage78 verifies **38 new exact instructions** across **four**
original `.pdata` function owners, **one** architecture key string and
**five** RTTI strings. A missing/mutated DLL, changed source call, wrong
field offset, altered namespace string or Stage77 runtime-claim escalation
fails closed.

## Remaining question

The specific Stage64 reverse file's parsed `architecture` value is
**unknown**. No original Stage64 raw input file or dynamic architecture-key
capture was part of this static audit. In particular, do not infer that
Stage64 uses WaveNet just because it is a registered family. The next gate is
an actual input NAM/CLO architecture value or independently verified runtime
provenance linking that input to the selected factory; only then revisit the
sample-rate/antialiasing parent problem.
