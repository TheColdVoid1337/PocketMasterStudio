# Sonicake HTKPA Stage 22 — real fitter-window and pre-fit reference conditioning

**2026-10-12 · Source-first, read-only.** Native Windows `5868USB.dll`, SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, base `0x180000000`. Original DLL is statically disassembled but **never executed**. No production JS, CLO or pedal writes; proprietary source media not committed.

## Corrected execution order

`0x1800BE830` uses a 70s + 600 samples native-float32 input/reference capacity (allocated at `0x1800B5640`; constants `70.0f, 600.0f, 4.0f`). It **removes the mean and least-squares linear drift of the target/reference buffer** `context+0x243E8` at `0x1800BE8E7..0x1800BEA34`. The source input `context+0x243E0` is not modified in those two operations.

It searches a **600-sample** reference onset interval starting at **6×Fs** and triggers when `abs(reference)>0.01` (`0x1800BEA59..0x1800BEAD6`). It sets separate input/target pointers to **23×Fs** and **23×Fs + onset offset** (`0x1800BEB2B/0x1800BEB41`).

**Crucially, the nonlinear four-gain fitter is called first**, at `0x1800BEDE4`, with Win64 `RDX = r15` (input), `R8 = rbp` (shift-aligned reference) and `R9D=trunc(float32(5×Fs))`. Thus the Stage-21 four-gain fit consumes only the **23–28-second** source and target sections. The IIR helper `0x1800BD490` is called **later** at `0x1800BEE25` with other audio buffer pointers; it does not precede the four-parameter fit. Earlier documentation suggested FIR/IIR preprocessing must run before the gain fitter; **that hypothesis has been explicitly corrected** in [Stage 21](NAM_CLO_HTKPA_DLL_RE_STAGE21.md). Prior to this step, buffer loading and sample-rate conversions may of course occur: exact PCM-to-native-buffer provenance remains unproven.

### Pinned addresses

| Code | Direct evidence |
| --- | --- |
| `0x1800B56B5/0x1800B56F2` | allocations stored at `+0x243E0/+0x243E8` |
| `0x1800BE8E7/0x1800BE930` | target-only mean subtraction |
| `0x1800BE9F2/0x1800BEA01/0x1800BEA34` | OLS slope/intercept then target-only detrend |
| `0x1800BEA5D/0x1800BEA64/0x1800BEAB2` | 6×Fs, 600-sample search and threshold |
| `0x1800BEAF8/0x1800BEAFF` | source/input and target/ref pointers |
| `0x1800BEB2B/0x1800BEB41` | 23×Fs input and target+onset |
| `0x1800BEADA/0x1800BEDBF` | 5×Fs sample count |
| `0x1800BEDDB/0x1800BEDDE/0x1800BEDE4` | exact nonlinear fitting call and argument registers |
| `0x1800BEE25` | subsequent call to IIR helper, **after** nonlinear fit |

## Reproducibility

Separate user-facing `Sonicake_HTKPA_DLL_RE_Stage22_v0_22.zip` contains the independent analyzer `stage22_pre_fit_trace.py`, Stage-21 standalone fitter for reference, research report, README, JSON evidence and verification log. It excludes DLL, user WAV/NAM and vendor CLO.

- **43** exact machine-instruction pins verified; **7** binary float/double constants; **53** synthetic assertions for window addresses, duration, fixed buffer capacity, threshold and affine trend-removal.
- Two independent inspections of the pinned SHA DLL yielded identical evidence JSON SHA256 **`d4c4edbd29674ddd3ab9a161192b579647bb9f58a441b00a8c52970a6faaedbb`**.
- Original manager captures were read **only for diagnostic alignment**, not used to fit any model parameter. On the saved **48-kHz** output PCM16 arrays plus 600 zeros, approximate vectorized OLS gives 0 samples for JCM800 2203 and 19 samples for SC20. **These are not proven bit-exact/native offsets**. The source DI WAV is 44.1 kHz, making precise native input import and resampling an unresolved requirement.
- Native four-gain parity for either JCM800 and whole-FIR parity: **NOT_COMPUTED / NOT_TESTED**, not claimed by synthetic assertions.

## Next source-first acceptance gate

Trace manager ingestion and native float32 buffer population under `context+0x243E0/+0x243E8` (including resampling of the 44.1-kHz DI, sample scaling, delay and padding). Then generate the **actual two 23–28s arrays** and use Stage 21's already-derived saturation fitter; compare to official four gains only as a *held-out* numeric validation target. No guessed resample default or CLO fitting to the official target, no automatic gain/EQ fixes, no production changes. Existing hardware-tested JCM800 2203 v0.2 C remains the control.
