# Stage95 — original PE NAM Core parser → vendor fitter static bridge

**Accepted status:** `STATIC_NAM_CORE_LOADER_TO_SHARED_FITTER_BRIDGES_VERIFIED_RUNTIME_UNBOUND`.

This is a *bounded static continuation* after Stage94, not a new Frida run,
same-invocation proof or independent NAM→CLO algorithm. The checked input is
the exact SHA-pinned 2,902,016-byte original `5868USB.dll` from the canonical
private RE_HTKPA Drive ZIP. All addresses below are **original PE RVAs**.

## New verified compiled links

### 1. Vendor `getNamOutput` reaches the NAM model-weights parser

Three exact direct `E8 rel32` calls, with original `.pdata` owners verified:

| Call instruction | Original caller owner | Target |
|---:|---:|---:|
| `0xE698` | `0xE0E0` (`getNamOutput` log and Stage92 WAV worker) | `0xCC4E0` |
| `0xCC58A` | `0xCC4E0` | `0xCAE30` |
| `0xCAFCE` | `0xCAE30` | `0xCB200` |

Within `0xCB200`, selected literal-reference instructions `0xCB304` and
`0xCB32F` both target the same JSON key `weights` at `0x18F838`;
`0xCB681` targets the exact missing-weights error at `0x18F7F8`.
This is structurally compatible with upstream
[`NeuralAmpModelerCore/NAM/get_dsp.cpp`](https://github.com/sdatkinson/NeuralAmpModelerCore/blob/0b3d3c97b0859a3a8c92a8628c4dd89a25eb5842/NAM/get_dsp.cpp)
`populate_dsp_data → GetWeights`, but stripped machine code does not establish
**exact function/source revision identity**.

A second compiled missing-weights use at `0xCB863` and key uses at `0xCB774`
and `0xCB7A7` are independently verified. The relevant `.pdata` is split into
small contiguous ranges; do **not** mislabel these as two independently
observed dynamic NAM loads or assert a direct caller ancestry to `0xCB863`.

### 2. Two compiled wrapper routes converge on the same fitter

| Route / `.pdata` owner | Original static call chain (individual `E8` sites) | Outcome |
|---|---|---|
| `0xFF40` | `0x10043→0xE0E0`; `0x100EB→0xD4A0`; `0x1016D→0xF940`; then `0xFA41→0xBE830` | Optional NAM/WAV/fitter route |
| `0x10E70` | `0x10F7F→0xE0E0`; `0x11021→0xD4A0`; `0x110AD→0x10230`; then `0x104E1→0xBE830` | Other NAM/WAV/fitter route; `0x11021` **observed Stage92 outer callsite**, but continuation not observed on that same stack |
| `0xBE830` | `0xBF364→0xCE00` and `0xBF47F→0xCE00` | Shared resampler branch; distinct Stage92 extra 44.1-kHz callsite family |

The fitter wrappers are anchored by compiled message references:
`0xFA6D→0x244A38` (startClone failure) in `0xF940`, and
`0x105E0→0x244A98` (startClone failure with input path) in `0x10230`.
These are label *hints from native diagnostics*, not a proof that all of
`0xBE830` is the complete closed fitting algorithm.

### 3. Both wrappers share the same `-2.0` return-sentinel gate

The original 64-bit double at `.rdata` `0x24CEF0` is **exactly `-2.0`**.

- `0xFF40`: `ucomisd` at `0x10050`; `jp` and `jne` at `0x10058/0x1005A`
  jump to `0x100BA`; optional-flag nonzero skip at `0x100C9→0x1018F`.
- `0x10E70`: `ucomisd` at `0x10F8C`; `jp` and `jne` at `0x10F94/0x10F96`
  jump to `0x10FF6`; optional-flag nonzero skip at `0x11005→0x110CF`.

These exact bytes support a branch that can continue on **not equal or
unordered**, then potentially skip via another optional flag. They do not
prove the Stage92 return value, branch choices, callback behavior, sample
rates, actual WAV paths or matching invocation IDs. This preserves Stage93's
existing double/`-2.0` guard interpretation.

## Reproducible local evidence and tests

Stage95 uses only Python stdlib, the already accepted Stage94 SHA gate and
Stage70 `.pdata` parser. No GUI application, Ghidra runtime, process attach,
binary instrumentation or network access is needed for these exact E8/LEA and
RIP-relative comparison anchors. The previous Ghidra Stage89–90 artifacts in
the same private folder remain available; this stage does not claim a new
Ghidra import/decompilation.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python -m unittest discover -s tools -p 'test_htkpa_stage95.py' -v

python research/htkpa/stages/stage95/audit_nam_to_fitter_static_links.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage95_nam_to_fitter_static_links.json
```

Result on original exact-SHA DLL: **14 pinned direct calls**, **6 additional
selected string references**, **two gated `-2.0` comparisons**, and **8/8
new regression tests**. Complete per-RVA JSON is private in RE_HTKPA; public
`evidence.json` includes only safe anchors and explicit limits. The previously
accepted Stage94 12 source-family fingerprints are rechecked on each run.

## Exact evidence boundary / when native Frida would become useful

- Stage92 **observed** two separately paired same-thread windows
  `0xEB1E → 0xD4A0 → 0xD786` and `0x11021 → 0xD4A0 → 0xD786`, plus
  later `0xBF364`/`0xBF47F` hits. Stage95 does **not** bind these to a single
  invocation, completed `startClone` or CLO artifact.
- A possible *future, separately reviewed* native Frida gate would capture
  **function-entry/exit invocation identity** for the known wrappers,
  `getNamOutput`, the vendor fitter wrapper and `0xBE830`, with bounded
  thread/return metadata and no raw audio/model contents. Existing universal
  Frida runner and crash-aware limits must be preserved; no automatic retry.
- No new runtime request was necessary for the present **static** acceptance.
  Do not extrapolate beyond the pinned direct calls and condition bytes.

No production DSP, WASM, codec, Resampler Lab or NAM/CLO encoder changes.
