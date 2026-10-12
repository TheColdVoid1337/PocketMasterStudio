# CODEX TASK — Stage23W: Windows-native DLL execution and FIR memory tracing

**Project:** POCKET_MASTER / PocketMasterStudio / HTKPA (NAM → CLO reverse engineering)
**Date:** 2026-10-13
**Mode:** Windows-native dynamic evidence acquisition, **not** production implementation.
**Source of truth:** original vendor \`5868USB.dll\`, SHA-256 \`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa\`.
**Branch:** \`main\`. Work in a small, scoped research checkpoint; do not alter deployed Void Mod, hardware/presets, or the vendor DLL.

## 0. Purpose / crucial distinction

We have thoroughly examined *static* PE disassembly and tested mathematical reconstructions (Stages 23Q–23V). A critical open conflict remains:

- The filter constructor writes **\`byte [filter+0x34] = 1\`** at \`0x18000B996\`.
- At \`0x18000C56E\` the FIR processor checks **that filter object's byte**; the nonzero branch \`0x18000C5B0–0x18000C5DB\` independently multiplies packed real and imaginary doubles. The zero branch \`0x18000C5F0–0x18000C636\` performs complex multiplication. Both treat DC/Nyquist separately.
- Our symmetric-FIR synthetic counterexample annihilates a sine's quadrature in the nonzero branch, although the normal complex product does not.
- Stage23U validates real inverse FFT with 2048× algebraic gain on synthetic signals; Stage23V validates buffer counts only using *passthrough*, not actual native convolution. **There is no native Windows RAM or full FIR output parity yet.**

**Obtain genuine runtime values** from the original, unmodified Windows process to settle which filter object, branch, and spectrum representation actually occur, and give another assistant enough exact information to resume *static disassembly* without access to the debugger. Do not synthesize values and call them native.

## 1. Operating environment / user authorization

The user expressly permits Codex to **run/debug the DLL locally on their Windows PC**. Prefer Windows-native execution, **not WSL or Wine**. The existing WSL \`.venv/bin/python\` is Linux and **cannot load a Windows PE DLL**. A Windows x64 Python venv, if useful, may be created under \`research/_LOCAL_FILES/stage23w_native/.venv/\` (or another path under that ignored private tree). Using Frida with native Windows Python, a portable x64dbg, WinDbg/CDB or Visual Studio debugger is acceptable. Choose a repeatable workflow with the fewest dependencies.

**Keep EVERYTHING private/untracked** under:

\`research/_LOCAL_FILES/stage23w_native/<session-id>/\`

This includes DLL/EXE copies, original NAM/WAV/CLO, debugger databases, process memory, full FFT arrays, captures, screenshots, traces, crash dumps, debugger scripts that embed local paths, temporary builds and downloaded tooling. The entire \`research/_LOCAL_FILES/\` tree is already ignored by Git; confirm with \`git check-ignore -v\`. Do **not** commit, paste into PRs/issues, or overwrite original recordings. Do not alter official output/hardware devices. Do not bypass license checks or tamper with the on-disk DLL. If the Manager has online/device effects, prefer a local/offline normal export with known local captures and avoid device writes.

**Tracked, sanitized deliverables**: task-independent scripts under \`research/htkpa/stages/stage23w/\`; human handoff at \`docs/HTKPA_STAGE23W_NATIVE_HANDOFF.md\`; small derived metadata at \`research/htkpa/stages/stage23w/native_evidence.json\`; append one entry to \`research/htkpa/RE_LOG.md\`. Never commit raw f64 samples, proprietary signals or machine-specific identifying paths.

## 2. Read existing repository evidence FIRST

Read, without rewriting history:

1. \`research/htkpa/RE_LOG.md\` **last two entries**, Stage23V and earlier Stage23S–U.
2. \`docs/NAM_CLO_HTKPA_RESEARCH_STATUS_2026-10-13.md\` (dated DOC-SYNC; later RE_LOG supersedes stale stage naming).
3. \`research/htkpa/stages/stage23s/fft_fir_multiply_source.py\` — two spectrum multiplication branches.
4. \`research/htkpa/stages/stage23t/fft_fir_object_lineage.py\` — distinct \`+0x34\` fields, pointer lineage and DC gain.
5. \`research/htkpa/stages/stage23u/fft_inverse_source.py\` — full inverse real FFT reconstruction.
6. \`research/htkpa/stages/stage23v/fir_stream_blocks_source.py\` — block/scratch geometry.
7. \`docs/NAM_CLO_HTKPA_DLL_RE_STAGE23E.md\` for normal import: stereo PCM16 at 44.1 kHz → channel 0 → 48-kHz mono PCM24 intermediate, plus separate reference.

Original vendor DLL location expected: \`research/_LOCAL_FILES/vendor/5868USB.dll\`. **Check its path and SHA before every trace**; do not assume exports can safely be called directly.

## 3. First milestone — establish a REAL callable Windows execution path

1. Inventory available Windows executables and installed tools: original Sonicake Manager application (if available), DLL imports/exports, 64-bit Windows Python, debugger(s). Identify architecture, dependencies, DLL load success/failure, relevant process name, and process bitness.
2. **Preferred:** run the original manager's existing *normal NAM→CLO conversion* against a private, copied test job, while attaching the debugger/instrumentation tool to the genuine process. Keep all input/output files under \`research/_LOCAL_FILES/\`. Obtain user confirmation only if an unavailable capture/test fixture or UI interaction truly prevents progress.
3. If Manager cannot run, inspect PE export list and call sites before building a minimal **Windows x64** loader/harness. A successful \`LoadLibrary\` alone is **not** a successful FIR probe. Do **not** call \`namConvertCloData\`/\`appNamConvertCloData\` by guessing opaque argument structures or ABI; derive them and document any needed dependencies.
4. Frida attach/interceptors are viable, as are x64dbg/WinDbg conditional breakpoints. Prefer observing over modifying; memory hooks/INT3 are in-process debugging artifacts only. **Do not patch DLL bytes on disk or branch behavior in memory** to force success.
5. If native execution is blocked (missing dependencies, licensing, application, fixture, hardware, anti-debugging), record exact error and attempted command, complete the **BLOCKED** handoff with useful static facts, and stop rather than fabricate results.

Success of milestone 1: a verified Windows x64 process has loaded the **SHA-pinned** DLL, with an explicitly recorded actual module base, and **at least one** of the target code sites was hit during actual execution. Record the original image base \`0x180000000\`, actual module base, and ASLR mapping \`live_va = actual_base + (static_va - 0x180000000)\`.

## 4. Targeted debugger hooks — begin with the critical ambiguity

All source virtual addresses below assume preferred PE base \`0x180000000\`. Compute RVAs and actual live addresses at runtime; never treat hardcoded VAs as ASLR-invariant. On Windows x64, capture RCX/RDX/R8/R9/RSP/RBP/RSI/RDI/RAX, thread ID, stack/caller and timestamps (or hit indices). Distinguish **before** instruction vs **after** instruction and step over calls safely.

### A. Filter creation / spectrum buffer lineage

| Original static VA | Inspect | Why |
|---|---|---|
| \`0x18000B996\` | \`RDI=filter\`, store \`[RDI+0x34]=1\`, object address, call stack | Actual constructor event and exact filter object identity |
| \`0x18000B978\` | \`[RDI+0x50]\` after the pointer store | Coefficient-buffer pointer |
| \`0x18000B9A1\` | Before/after helper \`0x18000AFA0\` | Any coefficient/layout changes |
| \`0x18000BA99\` / \`0x18000BAAC\` | Record filter, spectrum pointer, **pre-forward-FFT buffer** | Packed coefficient inputs, zeros, normalization |
| \`0x18000BAC1\` | Step over FFT call; capture **post-forward-FFT buffer** | Actual coefficient spectrum sent to FIR processor |
| \`0x18000BE0A\` | New FIR state \`+0x8\` filter pointer, after store | Connect processor ↔ exact filter |
| \`0x18000C55E\` / \`0x18000C56A\` | \`[RSI+0x8]\` filter pointer; \`[filter+0x50]\` | Check whether same filter and spectrum |
| \`0x18000C56E\` / \`0x18000C595\` | **Live \`[filter+0x34]\`**, flags and actual taken edge | Which branch actually executes? |
| \`0x18000C5B0\` and \`0x18000C5F0\` | Hit counts and first real/imag pairs | Independent-lane versus complex path |

**Crucial:** \`+0x34\` in the **filter** is a byte flag; \`+0x34\` in the **FIR processor** is a **DWORD working-buffer length** (4096). Do not conflate these objects. If the flag mutates, try a bounded hardware write-watchpoint on **the actual filter address + 0x34**; capture the writer PC/callstack, without global noisy logging.

### B. Input spectra / inverse / streaming

| Original static VA | Inspect | Why |
|---|---|---|
| \`0x18000C445\` / \`0x18000C45F\` | memcpy source, destination, byte count (\`RCX,RDX,R8\`) | Confirm scratch handoff direction |
| \`0x18000C468\` / \`0x18000C484\` | FFT input/output, plan pointer, forward mode \`+1\` | Real input spectrum |
| \`0x18000C577–0x18000C595\` | DC and Nyquist scalar products | Check packed layout |
| \`0x18000C668\` / \`0x18000C684\` | **After multiplication, before inverse**, FFT input and inverse mode \`−1\` | Distinguish arithmetic error from inverse transform |
| Immediately after return from \`0x18000C684\` | FFT output first/middle/tail | Compare 2048× inverse scaling |
| \`0x18000C689–0x18000C6F0\` | startup skip \`+0x84\`, returned counts | 3388 skip and first-block emissions |
| \`0x18000C85D\` / \`0x18000C861\` | swap \`state+0x70/+0x78\`; capture two-block history | Actual overlap/emit order |

Initially sample **one filter-construction event and only the first two or four complete FIR blocks** (not continuous 70-second logs). Make each snapshot attributable to the exact filter object, call stack, current mode and input block. Do not assume every FIR filter is the \`G=708\` first-stage filter; check \`filter+0x48/+0x4C\` and state settings against Stage23H–V.

## 5. Precise private dump format and numerical checks

Place all raw results in \`research/_LOCAL_FILES/stage23w_native/<session-id>/\`. Example filenames:

\`\`\`
manifest.private.json
filter0_coeff_pre_fft.f64le.bin
filter0_coeff_post_fft.f64le.bin
block0_input_pre_fft.f64le.bin
block0_input_post_fft.f64le.bin
block0_after_spectral_multiply.f64le.bin
block0_after_inverse.f64le.bin
block1_after_inverse.f64le.bin
trace.private.jsonl
\`\`\`

For every snapshot, save the **actual** pointer + accessible byte count, type \`float64\`, little-endian raw array bytes, shape (expected 4096 doubles ONLY when pointer/allocation checks agree), SHA-256, block number, capture instruction and timing, process module base, and whether the snapshot was BEFORE or AFTER a call. Do not invent absent dumps; capture a smaller safe memory region if allocation/guard pages prohibit reading 32768 bytes. Record the memory protection/readability checks and why any capture failed.

Derive locally (no raw samples committed): \`N\`, array finite/nonfinite counts, min/max, first/last meaningful index, sum, RMS, imaginary-vs-real bin energy, sample coefficients or FFT bins **by index (small numeric examples only if privacy-safe)**, and normalized correlations/differences against **both** Stage23S multiplication oracles and Stage23U inverse. Compare actual \`filter+0x34\` across events; compare actual spectrum layout with Stage23R's packed convention:

\`[Re X0, Re X2048, Re X1, Im X1, ..., Re X2047, Im X2047]\`

Use **f64 arithmetic and explicit scale conventions**. Where possible, compare Stage23I's candidate 1417-tap coefficient generation to native **pre-FFT** coefficient buffer by hash/summary and tolerance, rather than reverse-engineering opaque native FFT outputs. Show both absolute and relative errors, and whether values match the source-pinned branches within expected float64/SSE tolerance. Do not claim bitwise parity from approximate matching.

## 6. Mandatory HANDOFF FOR THE NEXT STATIC RE CHAT

Codex MUST create \`docs/HTKPA_STAGE23W_NATIVE_HANDOFF.md\`, even if completely blocked. This is the main artifact to bring into ChatGPT for subsequent **static** work; **do not depend on live debugger state**. It must be self-contained and concise enough to read in one chat turn. Use these sections:

1. **Executive result:** NATIVE_HIT / PARTIAL / BLOCKED, actual observed branch, top unresolved question.
2. **Provenance:** date/timezone, host Windows architecture, exact DLL file SHA, PE preferred base and runtime base/ASLR formula, Manager/host executable identity, debugger name/version, tested invocation, run/capture count.
3. **How to reproduce:** local steps/commands, dependency acquisition and Python interpreter bitness; note if only GUI sequence is known.
4. **Chronological event table:** exact static VA, RVA and live VA, hit count, object/pointer identity as stable per-run *aliases* (\`filter_A\`, \`state_A\`, \`buffer_H\`, \`buffer_X\`), values/edges/branch outcomes, stack caller and context; redact volatile ASLR addresses from public version if they reveal private information? (module bases themselves are acceptable).
5. **Filter/FFT state:** bytes at \`filter+0x34\`; provenance and widths of \`filter+0x50\`; size/phase/counter; real/imag storage and numerical evidence. Distinguish filter \`+0x34\` and state \`+0x34\`.
6. **Observed 1–4 block flow:** pre/post FFT hashes and statistical summaries, skip values, copies and swap results. Cite private filenames only as **relative paths inside \`research/_LOCAL_FILES/stage23w_native/\`**, not absolute paths containing user identity. Raw buffers remain local.
7. **Hypothesis table:** for each Stage23S/T/U/V claim, CONFIRMED / CONTRADICTED / NOT_OBSERVED, with measured numerical evidence and the relevant static VA.
8. **Open questions and next static disassembly targets:** exact source address ranges, predicted runtime relationship, a falsifiable hypothesis for each. This is critical: explain **what to disassemble next without needing to re-run Windows**.
9. **Verification / limitations:** native versus source-only versus synthetic labels. State clearly if vendor DLL execution never reached FIR; do not silently mix.
10. **Links and file manifest:** committed scripts and sanitized JSON, full private dump names, hashes/lengths, latest research commit.

Also emit **sanitized** \`research/htkpa/stages/stage23w/native_evidence.json\` containing fields like \`status\`, \`dll_sha256\`, \`tooling\`, \`captured_branches\`, \`observed_filter_flags\`, \`captured_arrays\` (hashes/lengths only), \`numerical_checks\`, \`block_counts\`, \`limitations\`, \`next_targets\` and \`private_run_relative_dir\`. If blocked, populate explicit \`blocker\` and \`attempted_methods\`.

## 7. Boundaries, deliverables, acceptance

**Do NOT:** modify production source; alter live hardware settings; guess ABI; alter on-disk DLL; commit original vendor files/WAV/NAM/CLO, 4096-double RAM buffers, minidumps or raw traces; extrapolate native gains from synthetic arrays; use official CLO gain values to fit anything; run unrelated system-wide instrumentation; claim parity merely from a successful \`LoadLibrary\`. Do not perform a sweeping code refactor.

**Minimum useful success:** verified native \`5868USB.dll\` code execution + one real hit at \`0x18000C56E\` with a live flag and buffer provenance. **Ideal success:** filter coefficient snapshots pre/post \`0x18000BAC1\`, two actual forward/multiply/inverse FIR blocks, and numerical comparison resolving Stage23S ambiguity.

**If blocked:** a precisely reproduced failed execution and a handoff with concrete next action is still a valid research checkpoint. Do not keep cycling on dependencies indefinitely.

**Finish with:**
- \`docs/HTKPA_STAGE23W_NATIVE_HANDOFF.md\` (MANDATORY);
- \`research/htkpa/stages/stage23w/native_evidence.json\` (MANDATORY, sanitized);
- concise reusable Windows debugger/analysis scripts under \`research/htkpa/stages/stage23w/\` when practical, no private hardcoded paths;
- private raw sessions under \`research/_LOCAL_FILES/stage23w_native/\`;
- **one append-only Stage23W entry** to \`research/htkpa/RE_LOG.md\` (including negative findings);
- at least one bounded smoke validation (JSON parse, evidence-to-handoff cross-check, Git ignore check and reproducibility steps);
- commit only safe research outputs to \`main\` if the user-authorized Git workflow is available; otherwise leave ready-to-commit changes and report why.
- finish with a brief summary stating measured native milestones versus blockers, where the handoff is, and the exact next static RE target.

## 8. Required model-effort planning

Start with a lightweight check of host tools, DLL SHA, existing scripts and app entrypoints; **low/medium model effort** is sufficient for tool inventory, path setup, logging, JSON schema scaffolding and report formatting. Use **high reasoning effort** for interpreting Windows x64 ABI, ambiguous memory aliases, FFT bin/phase interpretation, unexpected pointer changes and conflicting runtime versus Stage23S mathematics. Avoid consuming high-effort budget on repetitive log formatting.

**Important:** Dynamic tracing is a one-time evidence-acquisition instrument. The next assistant should be able to continue static disassembly and algebraic reconstruction from \`docs/HTKPA_STAGE23W_NATIVE_HANDOFF.md\` plus sanitized \`native_evidence.json\`, without treating live DLL execution as a permanent dependency.
