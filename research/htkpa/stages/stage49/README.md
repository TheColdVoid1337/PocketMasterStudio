# Stage49 — V1.5.2 native post-fractional f64 prefix: safety gate and experimental design

**Current status: GATE_A_STATIC_PROVENANCE_PASS; GATE_B_UNIVERSAL_CODE_GITHUB_CI_PASS_USER_WSL_PENDING; WINDOWS_BINARY_CAPTURE_NOT_RUN.** This is not a claim of native 48-kHz sample capture, full output parity, NAM fit parity, or Stage49 completion.

## Provenance

- Original Sonicake Manager **V1.5.2** Windows `5868USB.dll` read as data from the user's **PRIVATE** rollover ZIP. SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, PE image base `0x180000000`, 2,902,016 bytes.
- Rechecked independently via LLVM 17.0.0 `llvm-objdump`, no vendor execution. On the same file, verified the previously user-confirmed Stage48 original runtime: SHA-gated single Frida hook at RVA `0x1190C`, fractional vtable RVA `0x245170`, 114 f64/912-byte metadata and new stable 8840-byte CLO. The archived Stage48 manifest contains **no audio bytes** and records its historical GUI close failure; the separate later zero-hook lifecycle smoke PASS stands.
- Original Stage47 findings: [stage47/README.md](../stage47/README.md). Universal Frida: [tools/FRIDA.md](../../../../tools/FRIDA.md). Read these before any native execution.

## Gate A: machine-code proof, exact 1.5.2 DLL

The post-return pointer relationship is stronger than `Process.findRangeByAddress` alone:

| Original VA (RVA = VA - 0x180000000) | Native instruction/meaning |
|---|---|
| `0x18001185C` | `R15=R9`: hold caller's `double**` output reference |
| `0x1800118EA` | `RAX=[RBX+0x70]`: preferred resampler-owned output scratch |
| `0x1800118F6` | if scratch is null, replace `RAX` with preserved original input `RDI` |
| `0x1800118FA` | `*[R15]=RAX`: publish selected output pointer |
| `0x180011901` | `[RSP+0x40]=RAX`: set the local `double*` which final-stage `R9=&[RSP+0x40]` will reference |
| `0x180011909` | `call [vtable+0x30]`: final processor `process` |
| `0x18001190C` | **first instruction after return**; EAX count and selected `*R15` still intact |
| `0x1800135CB` | fractional processor takes initial sample pointer `R12=*R9` |
| `0x1800135CE` | `R13=R9`: saves address of input/output pointer reference |
| `0x180013C38` | exactly one direct f64 output write: `movsd [R12],XMM3` |
| `0x180013C3E` | `R12+=8` after every written f64 |
| `0x180013D15–0x180013D1D` | `EAX=(R12-*R13)/8`: number of generated f64 samples |

Independent disassembly of the `0x1800135C0..0x180013D28` fractional method yielded **347 instructions**, **0 CALLs** and no mutations to `R12` other than initial load / f64 write advancement / count computation. Its initial `*R9` is the same buffer selected by the resampler wrapper, unless a foreign thread corrupts shared state. Thus a **small prefix bounded by both returned count and mapped readable span** is supported by actual writes that just occurred, not by mapping size alone.

**Capacity limits remain material:** the `getMaxOutLen` negotiation (VA `0x180012237`) chooses scratch/input reuse; `0x1800122F0` grows one scratch allocation by `requested_count * 8` bytes using allocator indirection. The **exact runtime allocation capacity** of every possible source buffer has **not** been independently observed. A mapped region may extend beyond an allocation. Nor does an immediate same-thread postcall hook guarantee lifetime against arbitrary other-thread activity. This gate supports an intentionally **bounded first prefix**, not unconstrained bulk sample reads.

Byte fingerprints of the PE **.text** slices used in this independent Gate A recheck:

| Slice RVA, byte count | SHA256 |
|---|---|
| `0x11850`, 197 | `a3655c3afc7446128c0b0bbfbee741b9e3e7a3fddf9fad9bdf50ba3b6514f845` |
| `0x118EA`, 37 | `6a130f37abead668790603d55785a4d360d26ee5234c3e15e0b00e8ea44473a6` |
| `0x135C0`, 1897 | `bf6e1edc79e0fb5ebe51fc4c48cbadc270060b7eb0df1f6ac53b1ce64f08c87a` |
| `0x13D15`, 20 | `006b9de1395b245760d49dcab0abb70cdb82949781b6250292dfc97b3485c271` |
| `0x122F0`, 52 | `581117d7ae5f2072d733a2b5b12127e70c3eeb460b72592553d6a2d8d09bcda7` |

## Stage49 Gate B: one universal /tools opt-in prefix capture

A safe **first** experiment should:

1. Reuse exact Stage48 module SHA gate, one postreturn RVA `0x1190C` hook, vtable check, count 1–4096, output pointer alignment and readable span.
2. Additionally validate actual pointer provenance: `*R15` equals selected `[RBX+0x70]` when non-null, otherwise original input `RDI`. Deny capture on disagreement.
3. Capture no more than **32 f64 / 256 bytes** from the first valid post-fractional event. No target-thread JSON/hex sample conversion. Do not install paired C220/C838 hooks. Binary Frida `send(meta, ArrayBuffer)` only after all checks.
4. Host validates payload exactly, stores `block_0001.bin` only in ignored `research/_LOCAL_FILES/frida_captures/` along with SHA256, count, provenance and stage config; never place waveform/other proprietary binaries in Git.
5. Require a distinct **new or changed stable CLO** and one verified audio block before accepting `NATIVE_48K_SAMPLES_CAPTURED_CLO_STABLE`. A passing offline test or a metadata-only run must not be promoted to sample capture. Any agent exception / mismatched pointer / invalid payload / target crash is a stop, not a retry.
6. Keep binary capture strictly opt-in to shared `tools/frida_guarded.py` and `tools/frida_capture.py`, **never** by permitting unguarded `fields` in Stage48 mode. Stage-specific execution parameters belong only to `stage49/frida.json`; no stage-specific Python or shell launcher.

## Alignment and next experiments

The first 32 samples are a **diagnostic prefix**, not a parity-ready 1067-sample public sequence. Stage45's 1067 public/hybrid startup samples and Stage48's 114 native-output block are not demonstrably aligned. Numeric parity remains **NOT_ALIGNED** until original input identity, streaming chunk sequence, resampler state, startup latency and normalization/no-flush window are independently controlled. Stage49 capture must **not** silently update production DSP or NAM fitter behavior.

## Prepared universal execution — DO NOT REPEAT Stage48

Stage49 JSON is now present as `research/htkpa/stages/stage49/frida.json`. It opts in to `guarded_f64_binary`, one validated post-return hook, original V1.5.2 DLL SHA, 32 native f64 (256 bytes) maximum from the FIRST guarded valid output block. No Stage49 shell/Python copy exists.

**GitHub Actions offline CI PASS (16/16 tests, Python compile/self-test, Node JS syntax and Bash syntax), while an actual user WSL checkout run is still pending.** The source is committed, but the tools have **not** run on the user's Windows. First execute only offline/preflight checks, then if everything passes, launch exactly ONE managed conversion. Do not keep retrying if Frida reports an error or Manager crashes.

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
git status --short
python -m py_compile tools/frida_capture.py tools/frida_guarded.py tools/test_frida_universal.py
python tools/frida_capture.py --self-test
python -m unittest discover -s tools -p 'test_frida_universal.py' -v
bash -n tools/FRIDA_WSL.sh
bash tools/FRIDA_WSL.sh --config research/htkpa/stages/stage49/frida.json --preflight
```

If and **only if** the preceding offline/preflight gates pass and Sonicake Manager is **CLOSED**, start the single Stage49 native experiment:

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
bash tools/FRIDA_WSL.sh --config research/htkpa/stages/stage49/frida.json
```

After `[HOOK]`, perform exactly ONE normal NAM→CLO conversion inside the launched Manager; do not change any user NAM or CLO while the tool is running. A real positive result must record both **one local `block_0001.bin` with a SHA256**, and **a new/changed stable CLO**. Normal exit should be `NATIVE_48K_SAMPLES_CAPTURED_CLO_STABLE`; `LIFECYCLE_SMOKE_CLOSED_GRACEFULLY` was already independently accepted in Stage48 and must **not** be rerun.

If only a partial event was persisted before interruption, `events.jsonl` + SHA-validated local `block_0001.bin` remain forensic evidence, **not** a completed Stage49 success. Report the terminal output and `manifest.json` / `events.jsonl` first; do not upload proprietary `block_0001.bin` into GitHub. Archive is private under `research/_LOCAL_FILES/frida_captures/`. Do not compare the block numerically to any public sequence until aligned streaming provenance is established.

### 2026-10-14 CI acceptance of preparation (NOT the native runtime)

- GitHub Actions workflow `Universal Frida offline contract` run [38568363327](https://github.com/TheColdVoid1337/PocketMasterStudio/actions/runs/38568363327), head `d08702902f66d4d7376743eb562b3b0ff7006e87`: **PASS**, including **16/16** Python unit tests in 0.235 seconds, Python compilation, shared self-test, Stage48 regression, generated Stage49 JavaScript `node --check`, and Bash syntax.
- Prior intermediate test commit `3203e9c2` found a duplicate `const slot` declaration in the generated binary-agent JS and correctly failed. Fixed by distinct `scratchSlot` in `d0870290`; no code on Windows was ever executed as part of this correction.
- **NEXT GATE:** local user WSL tests/preflight. Only after their PASS perform one Manager V1.5.2 conversion with the new one-shot guarded binary config. No vendor f64 values have been captured yet; no parity conclusions.
