# Sonicake HTKPA Stage 8 — DLL-proven region dispatch and optimizer guard

**2026-10-12. Source-first, read-only static reverse engineering of the user's Windows Sonicake Manager 5868USB.dll. No guessed FIR fitter, no new CLO, no production code or device changes.**

Pinned DLL SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. PE image base: `0x180000000`. The proprietary DLL and captured vendor WAV/CLO are not included in the repository.

## Exact fit schedule — independently verified against machine code

The input probe and matching NAM output are grouped by byte pointers in `0x1800BE830`. The output pointers include a *detected sample-alignment offset* (search near 6s, maximum 600 samples), which must **not** be dropped when later reconstructing the numerical fit.

| Execution order | Selector | Input WAV window | Output WAV window | Inner iterations |
| ---: | ---: | --- | --- | ---: |
| 1 | 2 | 23–28 s (5s) | same window plus measured onset offset | 3 |
| 2 | 1 | 6–21 s (15s) | same window plus measured onset offset | 2 |
| 3 | 3 | 30–50 s (20s) | same window plus measured onset offset | 5 |
| Final spectral stage | n/a | 50–70 s (20s) | same window plus measured onset offset | separate function |

**Evidence, not inference:**
- Selector stores **2→1→3** at `0x1800BEE9F/0x1800BEEAA/0x1800BEEB5`. Dispatch and call to `0x1800BB210`: `0x1800BF050..0x1800BF0C9`; loop count three at `0x1800BF0D1`.
- The four-int table at `0x18024CFB0` is exactly **2,3,5,1**; selector-indexed count lookup at `0x1800BF0A3`. The extra 1 is never used by the three selected calls; its independent meaning is **not known**.
- Float32 window constants at `0x18024CCD0/0x18024CD34/0x18024CD40` are **5,15,20**. Length lookup at `0x1800BF0AE`. Input/output pointer lookups are `0x1800BF0BE/0x1800BF0B6`.
- Source starts are directly calculated via multipliers **6,23,30,50 × sample rate** at `0x1800BEA5D`, `0x1800BEB2B`, `0x1800BEB4D`, `0x1800BEB6F`; the output is offset by the detected onset alignment.
- After the three calls, `0x1800BF111/0x1800BF116` load the 50s output/input pair, and `0x1800BF11E` calls **`0x1800B9B70`**, *not* `0x1800BB210`.

**Do not relabel these as “clean”, “saturation”, or “EQ” passes without following their actual buffers and calculations.**

## Actual optimizer branch logic

The fitter at `0x1800BB210` gets its iteration count at `0x1800BB245` and loops back from `0x1800BC5C2`. Therefore the selected counts are actual optimizer iteration counts, not merely unrelated table entries.

The control score at `0x1800BC410..0x1800BC440` has direct scalar form:

`score = (1/512) * sum_{i=0..511} abs(logf(v[i] + 2^-23))`

This is backed by a 512-element loop, `logf` import, bitwise absolute mask and exact float32 constant 1/512. **The immediate producer of v is now known**: `0x1800BC3CA` loads its scratch pointer, `0x1800BC3E4` passes that same pointer as an output argument to `0x1800B5D00` (`0x1800BC3F9`), and the callee **reads that output pointer** at `0x1800B5FE3`, **writes its results** at `0x1800B60FE`; `0x1800BC410` then reads the same buffer in the score loop. Its **mathematical meaning remains unproven**; do not assume those values are physically transmitted FIR taps.

The branch condition at `0x1800BC459/0x1800BC469`, compared with `1.2` at `0x1800BC504/0x18024C9A8` and `0.5` at `0x1800BC59C/0x18024C880`:

```text
if new_score < previous_score:
    save candidate
else if new_score > 1.2 * previous_score:
    restore saved candidate
    exponent_step *= 0.5
else:
    keep current candidate
```

The two complete **Pre-FIR and Post-FIR coefficient arrays** are saved and restored together: live context pointers `+0x24408` and `+0x24410` are forwarded through the fitter, saved via `0x1800BC495/0x1800BC4B2` and restored via `0x1800BC53F/0x1800BC55C`. Meanwhile the exponential-power correction factor is annealed by **0.9 per iteration** at `0x1800BB4BE`.

**Observed:** paired-filter state tracking, iterative acceptance/rollback, score guard and schedule. **Unproven:** complete score-array provenance, candidate-generation equation, official FIR samples from the WAV. The score is not necessarily a perceptual or waveform error.

## Verification and acceptance

The separately delivered self-contained research archive `Sonicake_HTKPA_DLL_RE_Stage8_v0_8.zip` contains `verify_stage8.py`, `RESEARCH_REPORT.md`, `README.md` and machine-readable `evidence.json`; excludes vendor binaries/audio. The verifier checks **70 exact-address assembly predicates**, the PE SHA-256, four integer iteration constants, three window lengths and five optimization constants. Two independent runs produce the same JSON. **The DLL is never executed**.

**Gate still open:** We have **not** independently generated either complete official FIR from the original input/output WAV. This Stage 8 replaces earlier speculation about fitting order with checked machine-code facts; it does not claim a working official converter, sound quality equivalence or identical mobile SONICLINK behavior.

## Next source-first work

Trace the exact input, output and temporary arrays of `0x1800BB210`'s two `0x1800B82B0` calls (`0x1800BC055/0x1800BC3C5`) and two `0x1800B5A30` calls (`0x1800BBB5B/0x1800BC381`). Trace the input arguments and mathematical output of `0x1800B5D00`, now directly proven to produce the 512-element score buffer; then reproduce the actual candidate transform before trying WAV→FIR again. **No heuristic fitting or production changes without a source-confirmed equation and two-model numerical validation.**

Keep the positively hardware-auditioned JCM800 2203 v0.2 C as control; the main browser JS-only converter stays unchanged.
