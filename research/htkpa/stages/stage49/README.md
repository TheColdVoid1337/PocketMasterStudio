# Stage49 — V1.5.2 native post-fractional f64 prefix: safety gate and experimental design

**Current status: NATIVE_48K_F64_PREFIX_ACCEPTED (32 real f64 samples / 256 bytes + stable 8840-byte CLO). One-hook Windows run succeeded scientifically; GUI teardown required MANUAL close. A generic close-before-unload fix is offline-CI-verified but NOT yet Windows-tested. Full 48-kHz numerical output parity and NAM fitter parity remain OPEN.**

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


## 2026-10-14 — FIRST REAL V1.5.2 NATIVE POST-FRACTIONAL SAMPLE VALUES: ACCEPTED

**Actual user WSL + Windows run** after pulling to `90c7d8f8`: Python compilation, universal self-test, **16/16 unittests in 0.739s**, Bash syntax and configured Windows EXE/CLO path preflight all PASSED. Managed Sonicake Manager V1.5.2 instance, PID `12440`, loaded original `5868USB.dll` from `C:\\Program Files\\Sonicake\\Sonicake Manager\\assets\\5868USB.dll`; original SHA verified before ONE hook at RVA `0x1190C`. Runtime module base `0x7ff85dae0000`, hook PC `0x7ff85daf190c`, actual/expected fractional vtable `0x7ff85dd25170` (base + `0x245170`).

**Journal observation #18:** native postfractional original block **114 f64 / 912 bytes** at pointer `0x24a237ea4a0`. Separate binary event `binary_hit` saved **first 32 f64 / 256 bytes**, `block_0001.bin`, SHA256 `65b48ee4d3a6b0f86f8ab539761f45d52fc5799a7ce8a4e88b86c215eb0b6dae`. The uploaded PRIVATE archive `frida_20261014_131026_259514.tar.gz` (SHA256 `7c375c3ee25abf6f57632c966a11c21514fe38605384bab2aab264831a6ba837`) contains 5 members: `config.json`, `manifest.json`, `events.jsonl`, `HANDOFF.md`, `block_0001.bin`; every member's size/SHA verified. `events.jsonl` has 4 events. A changed `clofile.clo` stabilized at **8840 bytes**; original CLO content itself is NOT in the Frida archive.

**Independent sample checks (derived metrics only, no waveform copied into Git):**

| Metric | Native captured 32 f64 |
|---|---:|
| Values | 32/32 finite IEEE 754 little-endian f64 |
| Exact zero values | 0 |
| Minimum | `-1.5897965351580117` |
| Maximum | `2.1873822524247095` |
| Arithmetic mean | `0.009503496171527891` |
| RMS | `0.5700806961985158` |

Amplitudes above ±1 are **not automatically invalid** for an intermediate floating-point DSP buffer. We have NOT proven the normalization semantics and should not treat these as clipped 16-bit output. These **actual vendor native f64 values** are the first such evidence after Stages44–48, which only had public/hybrid 1067-sample data and native output *metadata*. Native/public aligned numerical parity is NOT TESTED; do not compare the first 32 here to the arbitrary first 32 public samples.

### Separate GUI teardown incident and universal mitigation

After reporting stable CLO, the original universal runner printed `[NOTE] Capture loop ended; removing Frida instrumentation` and, per the user's direct observation, did not progress **until the user manually closed Manager**. Then script unload, detach and run finalization succeeded. Archive records `detached_reason=process-terminated`, `close_messages_sent=0`, but also `process_cleanup_status=CLOSED_GRACEFULLY`. The latter is a **false implication of automatic shutdown**; ZERO owned `WM_CLOSE` messages were sent by the tool. The successful binary+CLO proof is unaffected. The evidence does not time-profile the exact Frida blocking primitive, though the code's first synchronous operation after that log was `script.unload()`.

**Shared `tools/` remediation (not another stage runner):** completed owned `guarded_f64_binary` captures now print bold `[CAPTURE]` at binary receipt, `[READY]` while awaiting CLO, and `[PASS]` after stable CLO, *before cleanup*. For that proven-success case, teardown attempts PID-scoped owned `WM_CLOSE` **before** the potentially blocking Frida `script.unload()`; if target exits, the hook is released with process exit, so redundant unload/detach are skipped. Stage48 metadata and failed/attach-only captures preserve prior order. A process exiting after **zero** actual `WM_CLOSE` messages is henceforth classified as `EXITED_WITHOUT_WM_CLOSE`, not `CLOSED_GRACEFULLY`. No automatic forced kill of a resumed GUI. **Offline GitHub Actions run [38570943745](https://github.com/TheColdVoid1337/PocketMasterStudio/actions/runs/38570943745) passed 19/19 tests** including close order/zero-message/Stage48 regression. Windows verification of this cleanup change is still pending; do **not** rerun the audio experiment merely to retest shutdown.

### Research gate verdict

- **Stage49 small-prefix native acquisition: PASS.**
- **Same-run native samples + changed stable CLO: PASS.**
- **Automatic tool-driven GUI shutdown in this run: NOT PASS — MANUAL close required.**
- **Proposed universal cleanup ordering patch: offline PASS, Windows PENDING.**
- **Native vs public aligned resampler numerical parity: OPEN.**
- **NAM fitting, four gains and CLO serialization parity: OPEN.**

Next research can use the already captured original native 32-f64 block and provenance/streaming analysis. Do not increase hook count or bulk binary copy until equivalent streaming windows/capacity have been established; preserve private bytes outside Git.
