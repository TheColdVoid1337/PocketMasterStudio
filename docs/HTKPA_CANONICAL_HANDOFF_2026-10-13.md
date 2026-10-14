> **SUPERSEDED AS NEW-CHAT ENTRY POINT — 2026-10-14.** Use [docs/dev/HTKPA_CHAT_ROLLOVER_2026-10-14.md](dev/HTKPA_CHAT_ROLLOVER_2026-10-14.md) first, then latest `research/htkpa/RE_LOG.md`. This earlier Stage24B handoff is retained for historical research evidence; its "read this first" claim and next steps are no longer current. Stage48 has now confirmed original native fractional metadata plus a stable CLO, and universal Frida GUI lifecycle is validated separately; actual vendor 48-kHz f64 contents remain unobserved.

---

# POCKET_MASTER / HTKPA — CANONICAL CONTINUATION HANDOFF

**State:** 2026-10-13, immediately after publication of the tracked Stage24B Windows one-click capture bundle.  
**Repository:** [TheColdVoid1337/PocketMasterStudio](https://github.com/TheColdVoid1337/PocketMasterStudio), branch **main**.  
**Read this document FIRST** on entry to a new ChatGPT conversation. It is intended to replace the need to paste the previous long chat.  
**Primary in-repo timeline:** [research/htkpa/RE_LOG.md](../research/htkpa/RE_LOG.md) — **read its final entries first**.  
**Previous detailed native findings:** [docs/HTKPA_STAGE23W_NATIVE_HANDOFF.md](HTKPA_STAGE23W_NATIVE_HANDOFF.md).  
**Up-to-date Stage24B technical gate:** [docs/HTKPA_STAGE24B_STATIC_GATE.md](HTKPA_STAGE24B_STATIC_GATE.md).  
**Windows instructions:** [research/htkpa/stages/stage24b/README_STAGE24B.md](../research/htkpa/stages/stage24b/README_STAGE24B.md).

---

## 0. REQUIRED BEHAVIOR FOR THE NEW CHAT — read before doing anything

You are continuing an **active, long-running source-first reverse-engineering investigation**, NOT starting a new project. Respond to the user in **Russian**. Treat this handoff, then the last RE_LOG entries and cited scripts, as the authoritative current state. Dates and titles of older standalone docs (some say Stage23O) are **historical snapshots**, not the current stopping point.

- The user commands **«ПОЕХАЛИ»** to authorize the **next meaningful technical RE cycle**: inspect the original SHA-pinned PE or real native trace, run narrow numerical tests, publish a clean checkpoint with *honest scope*, append an entry to RE_LOG. Do not reply with a plan only, and do not re-summarize weeks of history when an experiment can be done.
- **GitHub writing has standing approval** under `#writegh` until revoked. Prefer committing tracked, sanitized research scripts and docs to `main`, then verify fetched files and the resulting commit. **Do not modify production Void Mod, hardware presets, device state, export implementations or unrelated code.**
- Scientific priority ~**80% PE source/disassembly, 15% numerical verification, 5% GitHub/reporting**. No guessing FIR coefficients/gain values; reject heuristic correction factors even if they improve agreement with vendor output. Investigate the first discrepancy in actual source instructions/arguments.
- **Important truth vocabulary:** `SOURCE` = verified PE instructions; `SYNTHETIC` = model test using generated inputs; `NATIVE` = actual Windows vendor execution and captured buffers; `DERIVED` = mathematical interpretation; `NOT_PROVEN` = any unclosed parity. Keep them separate in every checkpoint.
- Append **one concise entry per real RE cycle** to `research/htkpa/RE_LOG.md`, including failed/negative hypotheses and any corrections to old findings. Do not silently rewrite historical evidence, don't dilute it with huge repetitive docs per minor experiment.
- Source/checkpoint scripts must reproduce numeric claims and pin the ORIGINAL vendor DLL by SHA. Preserve precise module address and Win64 object/alias separation. Never invent runtime samples or call data from neighboring sessions “same-call” unless pointer provenance proves it.
- The next ChatGPT chat may have the GitHub connector but not the user's local Windows filesystem or this chat's private uploaded ZIP. **Do not assume the private archive is available after rollover.** The user will upload the new `tar.gz` when generated. If necessary for deep numeric comparisons, ask for the original native dump ZIP again *only if it truly changes the analysis*.
- Work across GitHub via the connected GitHub tools. If live repo tools fail, explain the exact blocker rather than claiming a commit. Before writing, check newest `main`: there were multiple active Stage24B checkpoint commits, and the earlier one-click ZIP script was **not** initially in GitHub; it is now tracked.

### One-line message user can send in the NEW chat

> Прочитай целиком `docs/HTKPA_CANONICAL_HANDOFF_2026-10-13.md` из `TheColdVoid1337/PocketMasterStudio` (main) и последние записи `research/htkpa/RE_LOG.md`. Это продолжение нашего HTKPA RE-чата; подтверди актуальный статус и работай по этим правилам.

If the user attaches `stage24b_*.tar.gz` in that chat, **open/read the archive first**, inspect `stage24b/STAGE24B_HANDOFF.md`, `manifest.json`, and `native_events.jsonl`, compare observed IEEE-754 bits with Stage23H/Z and Stage24B evidence, then conduct the next source-first RE step. Do not ask the user to re-explain the project.

---

## 1. Original research target, product context and firm non-goals

- Vendor: Sonicake Manager **1.0.1**, original **Windows x64 `5868USB.dll`**. PE preferred base **`0x180000000`**. File size reported **2,902,016 bytes**. Exact original SHA-256:

```
fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa
```

- Goal: independently reconstruct the normal **NAM → CLO** path, especially real resampling/DI-reference alignment, native Pre/Post FIR, and finally **four real nonlinear fitted parameters** for two original Marshall captures **JCM800 2203** and **SC20**. This is reverse engineering for analysis and clean-room reconstruction; **not** a request to patch, redistribute, or replace the proprietary DLL.
- **Never infer four genuine gains from a CLO target or arbitrary calibration**. Neither Marshall model's four parameters have yet been independently computed from correct native-aligned 23–28-second samples. Official result comparisons remain *held-out* checks.
- **No production or device changes** while investigating. No “hardware parity”, “CLO parity”, or “bitwise vendor output” claims from isolated synthetic or near-f64 FFT results.
- There are two native FIR filter objects/lengths. Do not conflate them. Another double-use pitfall is `filter+0x34` **byte flag** vs `processor+0x34` **DWORD FFT window length 4096**.
- The user has a PC running **Windows 11 x64**, Windows Python 3.13 x64 + **Frida 17.6.1** in an existing isolated private environment. They also use **WSL** for ordinary `.venv/bin/python` static-analysis scripts. A Linux WSL venv **cannot load Windows DLLs**. Prefer the new one-click native tracer instead of firing up Codex for a short capture.
- Typical WSL working folder in this series: `/mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod`. On Windows, the equivalent checkout is on the F: drive, accessible via Explorer.

### Assets and repo boundaries

- **Tracked / safe to commit:** small source RE scripts in `research/htkpa/stages/stageXX/`, sanitized evidence JSON, documentation under `docs/`, append-only `research/htkpa/RE_LOG.md`.
- **Ignored local/private:** `research/_LOCAL_FILES/` including `research/_LOCAL_FILES/vendor/5868USB.dll`, the original NAM/WAV/CLO captures and full RAM arrays, all temporary debugger sessions and their `tar.gz`. This directory is already Git-ignored; do not force-add its contents even if the user says it has no secrets. The user explicitly permits committing all **capture tools and handoff documentation**, not indiscriminately uploading proprietary binaries.
- Original user-supplied `stage23w_native.zip` contains RAM arrays and private JSONL; it was inspected and **not** committed. Its saved facts are described below and in the Stage23W handoff.

---

## 2. Stage timeline and critical recovered math (do not redo blindly)

### Stages 21–22 — four-parameter nonlinear fit (source-derived, NOT applied to native-aligned Marshall samples)

- Source fitter at **`0x1800BDBE0`** reconstructs positive/negative extrema/rates: `pmax, nmax, prate, nrate`, including 0.1-second extrema, initialization/regression, two nine-candidate exponent-rate searches. Stage21 passed earlier source instruction and synthetic gates; **no independently computed real-capture parameter set**.
- Critical Stage22 correction: fitter receives **23–28-second** pair at `0x1800BEDE4` taken from `context+0x243E0` input and `+0x243E8` reference after independent import/detrend/onset alignment. Do **not** run the later `0x1800BD490` 50-tap/IIR on these inputs before saturation fitting. Reference context is approximately 3,360,000 f32 at 48k plus 600 zero samples.
- Source-only candidate official-read values previously noted: JCM800 2203 `pmax .0586976074, nmax .0625180602, prate 425.438965, nrate 356.188354`; SC20 `pmax .0106169116, nmax .0126974732, prate 450.926178, nrate 253.910919`. **These are not four independently fitted results** and must not be used as target parameters.

### Stages 23D–F — normal import path and PCM format

- Normal exported path `namConvertCloData` `0x1800E1F70` invokes asynchronous worker `0x180060F20` and normal sample-rate export `0x180010E70`, not old fixed-44.1k diagnostic branch. Both original NAM models parse at **48,000 Hz**.
- Original DI/source WAV is **stereo 44,100 Hz PCM16**, only channel 0 used, PCM16 normalized by **32768**, resampled to internal **48,000 Hz**, saved as intermediate **mono PCM24 WAV**, then read back. Reference WAV is separately recorded **stereo 48k PCM16**. Conflating DI reference channels/sample rates produces wrong fitted gains.
- Stage23F identifies 673 usable phases, 24-tap third-order polynomial interpolator (source-derived, not complete native-stream parity).

### Stages 23G–J — first FIR geometry and initial window candidate

- First resample stage **up by 2**, then fractional stage. First FIR **1417 taps**, half-length **G=708**, 4096-double FFT working span, initial upsampled fill **2680** and skip **3388**. A second filter instance has **1543 taps / G=771**, as later native buffers prove; do not assign a rate direction to object without live cutoff.
- Stage23I built a 1417-tap symmetric circularly packed coefficient candidate summing `1/1024`. **Stage23I mathematical model was incorrect** about the power window. Its original bit-identical generated SHA is `ff4b587594a156df2fe8fd34a7a639eeb09e3cc9a59fcfba93afa17737d241be`. Do not treat that candidate as the native coefficient vector.
- In Stages 23Y–24B the filter window and two cutoff alternatives were more tightly reconstructed; see sections 4–5.

### Stages 23M–R, U — frequency transform

- Original 4096-real FFT with 2048 complex inner points, positive-exponent packing. Packed spectrum format:

```
[Re(X0), Re(X2048), Re(X1), Im(X1), ..., Re(X2047), Im(X2047)]
```

with positive exponent relative to NumPy `rfft`, so native forward spectrum agrees with **`conj(np.fft.rfft(...))`** on synthetic tests. Inner FFT is composed of 8-complex subblocks, radix-4 stages, terminal radix-2; source-pinned scalar instructions and algebraic numerical tests in stage23m–r.
- Stage23U inverse real FFT includes source-emulated precombine, inner algebraic FFT and final conjugation/sign flips. Synthetic full 4096-real forward+inverse scale is **2048**, 28 tests, max roundtrip error **`4.945377440890297e-12`**. That is synthetic error vs 2048*x, **not native Windows RAM parity**.
- Stage23W later checked actual inverse numerical output, confirming `2048 * irfft(conj(packed_product))` to errors ~`1e-18`, but **not bitwise inverse SSE parity**.

### Stages 23S–T — multiplication-branch correction (VERY IMPORTANT)

- Filter constructor writes `byte [filter+0x34]=1` at **`0x18000B996`**; FIR processor tests at **`0x18000C56E`**. Original Stage23S incorrectly treated flag-1 as naive lane-wise `y_im=x_im*h_im`. That led to a false “imaginary/quadrature loss” paradox.
- Actual native flag-1 multiplication, **BITWISE VERIFIED** for two whole **4096-f64** arrays in the user-provided Stage23W private trace:

```python
y[0:2] = x[0:2] * h[0:2]       # DC/Nyquist
y[2::2] = x[2::2] * h[2::2]   # real
y[3::2] = x[3::2] * h[2::2]   # imaginary * SAME H real coefficient
```

- Previous naive `x*h` makes native max errors **`0.0006777608545014361`** (block0) and **`0.0008636189511658111`** (block1). Correct pair formula gives **0 different f64** for each block. The complex branch `0x18000C5F0` was **not** taken in the recorded import. A real, nearly zero-imaginary coefficient FFT explains the real-coefficient branch; do **not** repeat Stage23S's incorrect oracle.
- Stage23T establishes that filter and processor `+0x34` are unrelated objects/widths. No claim of all possible runtime flag paths.

### Stage23V — streaming and overlap

- First up2 stage consumes **1340 source frames** per full processing block → **2680 upsampled doubles**, saves **708-double** scratch tail.
- `0x18000C445` is `memcpy` **into** work block at `+2680`; `0x18000C45F` copies **from** `+1972` to the 708-double scratch; `0x18000C85D/0x18000C861` swaps work/previous FFT buffers.
- Startup `+0x84=3388`, output counts first blocks **`[0,1972,2680,...]`**, checked synthetically and verified in Stage23W's actual run. Synthetic 4-block `[0,1972,2680,2680]`, total **7332**. `state+0x2c` remains an unobserved output-period parameter in older captures; seeing `state+0x54=0` alone does not prove `0x18000C824` direct copy.

### Stage23W — actual Windows dynamic observation (major breakthrough)

- Executed original Sonicake Manager 1.0.1 + SHA-pinned DLL in Windows 11 x64 with Python3.13/Frida17.6.1. Module runtime base from retained run **`0x7ff87e390000`**. Native address formula: **runtime VA = actual base + (static VA - 0x180000000)**.
- `0x18000C56E` ~**9218** flag-1 hits in retained traces; real coefficient `filter+0x50`; actual lane branch `C5B0`, not complex `C5F0`.
- **Two filter buffers** of 4096 little-endian f64 with 1417 and 1543 nonzero circularly symmetric coefficient slots; each sums ~`1/1024`; arrays **byte-identical** across two independent capture runs:
  - 1417 taps hash `649adeb70df4bb17f73ca09c0e4bc8bd3511271fa388d989bb2094ead22b0770`.
  - 1543 taps hash `ccb1dcb24dc73dfa5b273a22f96d6093713f52518cadf26e595e94ff9ee6b9cc`.
- `coeff_post_fft` vs independently computed `conj(rfft(coeff_pre_fft))`: max abs difference ~`4.34e-19`, imaginary slots ~`2.71e-19`.
- The user's uploaded `stage23w_native.zip` was read directly in the earlier chat: **107 members**, 26,884,892 uncompressed bytes, CRC PASS. `20261013_overlap_capture` contains coefficient, packed input, product and inverse for two **blocks within same filter object/capture**; correct multiplication gave 0 unequal doubles for each.
- Inverse native vs NumPy max errors `8.673617379884035e-19` and `1.1926223897340549e-18` (not bitwise). Earlier captured `input_pre_fft` has 26 anomalously enormous numbers; treat as **invalid timing/uninitialized snapshot** for forward-FFT parity until inspected.
- Native `output_route` trace did not actually include `state+0x2c` despite 9218 emit events; its direct output route remains open.
- Evidence/handoff: [HTKPA_STAGE23W_NATIVE_HANDOFF.md](HTKPA_STAGE23W_NATIVE_HANDOFF.md); [native_evidence.json](../research/htkpa/stages/stage23w/native_evidence.json); [native_analysis.json](../research/htkpa/stages/stage23w/native_analysis.json); [native_trace.py](../research/htkpa/stages/stage23w/native_trace.py). Original raw f64 snapshots are **local only**.

### Stage23X — PCM24 writer

- Source-pinned `float32 → signed PCM24`: saturate input to [-1,1], scale by `2147483647.0`, f64 rounding constant `6755399441055744.0`, signed int32 arithmetic `>> 8`, three little-endian bytes. Stage23X 16 instruction pins / 7 synthetic checks; **no complete writer→reader or resampler parity**.
- Code: `research/htkpa/stages/stage23x/pcm24_writer_source.py`.

---

## 3. Stage23Y / Stage23Z — exact reason old FIR window failed

### Stage23Y: negative result, source candidate reproducible

- Original Stage23I candidate was reconstructed **byte-for-byte** with its known SHA but differed from native pre-FFT 1417 taps at **all 1417 active indices**. Maximum difference **`1.6025453961367097e-6`**, full-4096 RMS `2.8553058553229254e-7`.
- Comparing the normalized window envelope at tap 400 gave candidate `3.756e-10` versus native-derived `0.032414`. This cannot be simple CRT/f64 rounding.
- Relevant static generator path `0x18000B8D0–0x18000B981 → 0x180014810 → 0x180008FD0`.

### Stage23Z: definitive math correction (source first, no fitting)

- PE thunk **`0x18017E152` resolves to imported `pow`**, *not* imported `sin`. Generator `0x180014810` calls that power function at **`0x18001496E`** and **`0x1800149C4`** using exponent `generator+0x20`.
- Prior Stage23I's **`sin(gamma)*window`** was wrong. Correct source-side structure is **`pow(window, gamma)`** with candidate `gamma≈0.15823713794954866`, Bessel parameter `beta=125`, oscillatory sinc kernel, and sum normalization `1/1024`.
- Without tuning `beta`, `gamma`, or coefficients to the native target, source correction reduced max native error to **`9.282550449007586e-10`** (**1726× improvement**) and RMS to **`2.1566018388829852e-10`** (**1324× improvement**).
- **Still 1417/1417 active entries differ bitwise**. DO NOT proclaim exact coefficient parity; the remaining small discrepancy in angle, gamma, oscillator recursion/order or CRT math is the next key problem.
- Script: [stage23z/window_pow_source.py](../research/htkpa/stages/stage23z/window_pow_source.py); [evidence.json](../research/htkpa/stages/stage23z/evidence.json).

---

## 4. Stages 24A–24B — CURRENT SCIENTIFIC POSITION

### Stage24A: constructor argument lineage established

- Static source call chain:
  `0x18000CFF3 → 0x180011B60 → 0x180011CE3 → 0x18000BB80 → 0x18000BD12 → 0x18000B0E0 → 0x18000B981 → 0x180014810`.
- Two cutoff alternatives from original `0x180011C83–0x180011C99`: source-side `0.5` and rate-dependent `0.5 * 44100 / 48000 = 0.459375`.
- Source-derived filter-size predictions for those alternatives (**NO fitting to raw vendor taps**):
  - `cutoff=0.5` ⇒ `G_before_floor=708.9209756461122`, floor G=708 ⇒ **1417** taps.
  - `cutoff=0.459375` ⇒ `G_before_floor=771.614667369918`, floor G=771 ⇒ **1543** taps.
- Exactly matches observed native **two** coefficient lengths, but a **live per-object cutoff/rate branch** remains unmeasured. This is strong source/geometry correspondence, not completed bitwise coefficients.
- Filter object in constructor has f64 `+0` cutoff, `+8` quality, `+0x10` attenuation, `+0x20` normalization gain.
- At `0x18000B981`, Win64 `RCX` points at generator stack object, `RDI` at matching filter object. Generator fields: `+0` f64 G_before_floor, `+0x0c` u32 G integer, `+0x18` f64 upper oscillator `theta`, `+0x20` f64 power exponent `gamma`, `+0x58` u32 index, `+0xC0` f64 beta, `+0xC8` f64 I0(beta) denominator, `+0xD0` f64 initial offset.
- Diagnostic (NOT source-proven) ratio of native `tap[2]/tap[1]` and Stage23Z gives `0.02794104254224959` vs `0.02794316121340997` and *conditional* inferred theta difference `+2.119623458751718e-6` radians. **This is a diagnostic from native output, NOT a valid fitted theta. Never substitute it into reconstructed code.**
- Stage24A 52 source-pinned instruction checks; [source](../research/htkpa/stages/stage24a/generator_argument_gate.py).

### Stage24B: static gate DONE, WINDOWS SCALAR CAPTURE NEXT

- Static Stage24B verified original SHA, **44 instruction pins and 5 PE constants**: attenuation 180.15, quality 2, half-cutoff 0.5, beta 125, pi 3.141592653589793. See [stage24b/generator_gate.py](../research/htkpa/stages/stage24b/generator_gate.py), [evidence.json](../research/htkpa/stages/stage24b/evidence.json).
- Important distinction: **Stage24B live field capture has not been completed in this chat**. Earlier Codex docs promised a one-click ZIP but it was **not in GitHub**. The current chat specifically rectified that: all runnable files are NOW TRACKED under `research/htkpa/stages/stage24b/`.
- The exact two native hook sites needed are:
  1. **`0x18000BD12` (RVA BD12):** filter f64 cutoff/quality/attenuation/gain, filter pointer.
  2. **`0x18000B981` (RVA B981):** paired generator f64 G_before_floor/theta/gamma/beta/denominator/offset, u32 G/index; exact IEEE754 bits and filter identity.
- Do NOT repeat the full Stage23W FFT capture (thousands of hits/large dumps). A few **scalar** observations of the constructor and matching generator are the missing evidence.
- **Current one-click capture files (safe and tracked in GitHub):**
  - [one_click_capture.py](../research/htkpa/stages/stage24b/one_click_capture.py): Windows x64, Frida observer/hook, existing Manager auto-attach or spawn, pinned on-disk and loaded DLL SHA, paired object guard, safe completion, small verified tar.gz.
  - [STAGE24B_CAPTURE.bat](../research/htkpa/stages/stage24b/STAGE24B_CAPTURE.bat): Windows Explorer double-click launcher using existing private Windows Frida venv.
  - [test_one_click_capture.py](../research/htkpa/stages/stage24b/test_one_click_capture.py): pure standard-library regression tests.
  - [README_STAGE24B.md](../research/htkpa/stages/stage24b/README_STAGE24B.md): step-by-step user instructions.
  - [native_generator_trace.py](../research/htkpa/stages/stage24b/native_generator_trace.py): earlier narrow standalone PID-based tracer kept as lower-level tool.
- **Running from Windows**:
  1. In WSL repo root run `git pull --ff-only origin main`.
  2. In **Windows Explorer**, double-click `research\htkpa\stages\stage24b\STAGE24B_CAPTURE.bat`.
  3. Optional: supply the CLO output folder; or simply press Enter at the initial prompt to use manual completion.
  4. Wait for `[READY]`, do **one** normal NAM→CLO import. After it completes, changed stable CLO is auto-detected when watching, otherwise press Enter **after** Manager finishes.
  5. Tool only declares `NATIVE_SCALARS_CAPTURED` when native **same-filter** generator hits, loaded DLL SHA and actual import confirmation are all present. Silence/inactivity alone never counts.
  6. Tool leaves Manager running and saves a verified **`stage24b_YYYYMMDD_HHMMSS.tar.gz`** under ignored `research/_LOCAL_FILES/stage23w_native/stage24b_captures/`.
- **tar.gz exact allowlist:**
  `stage24b/manifest.json`, `stage24b/native_events.jsonl`, `stage24b/STAGE24B_HANDOFF.md`, `stage24b/ready.json`. No proprietary WAV/NAM/CLO/DLL/FFT arrays. Exception statuses `BLOCKED/INCOMPLETE/INTERRUPTED` are archived and **never** called successful.
- **Validated locally without Windows:** Python syntax, stable CLO detection, native object pairing, archive SHA/strict member allowlist and exclusion of dummy proprietary fixtures. **No Frida/Windows execution by ChatGPT**. User must run actual import and return archive.
- Windows Python/Frida expected `research/_LOCAL_FILES/stage23w_native/.venv/Scripts/python.exe`; WSL `.venv/bin/python` is Linux and MUST NOT be used to attach or spawn Windows Manager.

---

## 5. NEXT CHAT WORKFLOW — specific branches

### A. User writes only “прочитай handoff” (without new capture)

1. Read this document and **the last 3–5 RE_LOG entries** using GitHub connector. Inspect latest `main` HEAD rather than assuming the hash from this document remains current.
2. Verify four Stage24B launcher files exist on GitHub and perhaps run/list the offline code checks if a real test runtime is available.
3. Briefly tell user: **Stage24B static gate passes; one-click Windows capture is committed; next step is running the BAT and uploading tar.gz**. Give exact path and action, not a 10-page recap.
4. Do **not** launch an unrelated code cycle or demand Codex unless user explicitly asks.

### B. User uploads the generated `stage24b_*.tar.gz`

1. Open archive with Python `tarfile` **safely** and verify members are strictly the four expected under `stage24b/`; reject any absolute/parent-traversal paths, symlinks or oversized entries. Do not execute any code from the archive.
2. Parse `manifest.json` and `native_events.jsonl`; record `status`, completion method, hook counts, runtime-loaded DLL SHA verification. If `status` is `BLOCKED`, `INCOMPLETE` or `INTERRUPTED`, explain the exact error/attempt and fix only what is necessary.
3. Group `filter_arguments` and `generator_arguments` by **same `filter` address and session**; check a real pair, record filter `cutoff,quality,attenuation,gain` and generator `G_before_floor,G_integer,theta,gamma,beta,bessel_denominator,index,offset`, preferably hex IEEE bits. Distinguish 1417 and 1543 filters by observed G, not array name order alone.
4. Compare live **field values and exact bytes** against *independently computed* Stage23H/Z/A/24B source model. Determine **the first mismatched field/formula**. If gamma and theta match exactly, test recurrence/operation order and Windows CRT functions, not a fitted correction.
5. Inspect source PE only at the relevant connected ranges: `0x18000B2B8–0x18000B844` (gamma/phase), `0x180014810–0x180014A31` (generator oscillator + pow), `0x180008FD0–0x180009023` (Bessel window), `0x180011C83–0x180011CE3` (cutoff/rate selection).
6. Build a **small source-pinned standalone Python test** under a new stage (Stage24C or its correctly named successor), check natively observed values without using them to fit parameters, record residuals and SHA. Append concise RE_LOG entry and commit safely; keep any memory array in ignored directory.
7. **Only after** true parameter/coeff parity should first-stage FIR be integrated with 24-tap fractional interpolator, PCM24 reload and 23–28s fitter real data. Real Marshall gains and CLO equivalence remain separate acceptance gates.

### C. User says «ПОЕХАЛИ» with no archive

- Continue source-first static RE as normal, but **do not assume native field values**. Either find a decisive new source fact or produce a bounded negative-gate checkpoint; do not hallucinate that Windows capture already ran. Remind user of the one-click BAT only as the precise unblocker.

### D. User posts Windows/WSL console logs

- Verify the reported metrics against saved scripts and source scope; with standing GitHub permission, append independent user validation to RE_LOG and optionally advance the native gate. If an error occurs, diagnose the real environment without claiming success.

---

## 6. Canonical files by path

**Read immediately:**

- `docs/HTKPA_CANONICAL_HANDOFF_2026-10-13.md` — this entire file.
- `research/htkpa/RE_LOG.md` — append-only, final entries are freshest.
- `docs/HTKPA_STAGE24B_STATIC_GATE.md` — last fully source-pinned technical gate.
- `research/htkpa/stages/stage24b/README_STAGE24B.md` — one-click Windows capture.
- `research/htkpa/stages/stage24b/one_click_capture.py` — actual tracked launcher.
- `research/htkpa/stages/stage24b/evidence.json` and `generator_gate.py`.

**When investigating numerical discrepancies:**

- `docs/HTKPA_STAGE23W_NATIVE_HANDOFF.md` — native traces and independent private-archive recheck.
- `research/htkpa/stages/stage23w/native_evidence.json`; `native_analysis.json`.
- `research/htkpa/stages/stage23h/native_fir_length.py`.
- `research/htkpa/stages/stage23i/native_fir_coefficients.py` (historically wrong window; retained for lineage).
- `research/htkpa/stages/stage23y/diagnose_window.py` (negative window comparison).
- `research/htkpa/stages/stage23z/window_pow_source.py` (corrected POW window).
- `research/htkpa/stages/stage24a/generator_argument_gate.py`.
- `research/htkpa/stages/stage23s/fft_fir_multiply_source.py` (**old flag-1 oracle is refuted**, do not assume model correct).
- `research/htkpa/stages/stage23u/fft_inverse_source.py`; `stage23v/fir_stream_blocks_source.py`.
- `research/htkpa/stages/stage23x/pcm24_writer_source.py`.
- `docs/NAM_CLO_HTKPA_RESEARCH_STATUS_2026-10-13.md` (last full DOC-SYNC still titled Stage23O; useful background but outdated).
- `docs/POCKET_MASTER_HTKPA_HANDOFF_2026-10-12.md` (very long historical snapshot, only consult if earlier stages need deep source details; **do not automatically load whole 144 kB document**).

---

## 7. Checkpoint discipline and what must NEVER be claimed

- **No independent four gain values** for 2203 or SC20 from actual correctly imported native waveform.
- **No full 44.1→48k resampler parity** and no complete official CLO parity.
- **No exact Stage23Z coefficient bit parity**, even though source-corrected window agrees to ~`9.28e-10`.
- **No native proof of every output branch at `0x18000C824`**, since `state+0x2c` wasn't actually captured.
- **No Windows execution in the Stage24B preparation cycle**. Two Windows hook sites are prepared and tested offline; success requires the user's real `tar.gz`.
- Do not present numeric regression derived from a native final buffer as a source-derived parameter solution. Approximation/inference ≠ source instructions.
- Do not conflate a path named `native_evidence.json` with independently rerun native measurements if it contains only sanitized summaries.
- Never commit the private `research/_LOCAL_FILES/` tree, binaries, original NAM/WAV/CLO, full f64 spectra, passwords, system artifacts or non-project files.
- No Codex delegation is required for one bounded Stage24B scalar capture; user wants to conserve Codex tokens. If a long Codex task is explicitly requested, prefer a tracked Markdown task document plus a **short English Codex prompt**; recommend low/medium effort for boilerplate and higher only for deep Win64/FFT aliasing.

---

## 8. Immediately useful expected handoff from upcoming tar.gz

Example of the *shape* of future evidence (values below are SOURCE CANDIDATES, **NOT OBSERVED NATIVE**):

```json
{
  "stage": "Stage24B",
  "native_status": "AWAITING_USER_WINDOWS_RUN",
  "filter_A_expected_cutoff_by_source": 0.5,
  "filter_A_expected_G_before_floor_by_source": 708.9209756461122,
  "filter_A_expected_taps_by_source": 1417,
  "filter_B_expected_cutoff_by_source": 0.459375,
  "filter_B_expected_G_before_floor_by_source": 771.614667369918,
  "filter_B_expected_taps_by_source": 1543,
  "source_candidate_gamma_for_first_filter": 0.15823713794954866,
  "source_candidate_theta_for_first_filter": 1.5428478841482018,
  "observed_native_values": null
}
```

The real archive will contain event records with values **and IEEE754 bits** for each filter/generator object. Its generated `STAGE24B_HANDOFF.md` is designed to be understandable without Frida, Codex or additional background.

---

## 9. User communication and release hygiene

The user prefers concise Russian progress, genuine source-first technical results, and immediately runnable scripts rather than speculative or verbose planning. When performing multi-step research, give short interim progress and a concrete final status, with GitHub SHA/path and honest test claims. Do not substitute research effort with repeated narration. For a new chat, the handoff's purpose is seamless continuation with **one small introductory message**, not forcing the user to reconstruct their own project history.

Treat Stage24B tar completion as a **gated experiment**, not a milestone that automatically resolves coefficient parity. If Windows capture reveals a new mismatch, focus the very next static RE cycle on precisely that first incorrect value/operation.

**END OF CANONICAL ROLLOVER HANDOFF.**
