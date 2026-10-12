# Sonicake HTKPA — Stage 8: verified region dispatcher and joint FIR optimizer guard

**Date:** 2026-10-12  
**Method:** read-only PE x64 disassembly + static extraction of float32/float64 and integer constants. No DLL execution, no Windows driver interaction, no physical Pocket Master interaction.  
**Binary:** user-provided `assets/5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. All displayed addresses assume the image base `0x180000000` and are *virtual addresses*, not file offsets.

## Finding 1 — exact region selection and call ordering

The fitted source is a 70s instrument-probe WAV. The beginning-of-signal search at approximately the 6-second mark returns a sample offset `delta` within a 600-sample window (`0x1800BEA5D` to `0x1800BEAD6`, including `mov esi,0x258` at `0x1800BEA84`). This offset is applied to the *output* WAV pointer used for paired fitting. The source input starts at the nominal region boundaries. Therefore each output range below is **time-shifted by `delta / Fs`**, not exactly the same sample index as the input.

All three selected regions are assembled from four actual memory-pointer tables. Their call order is *not* the chronological order in the WAV:

| Call order | Selector | Input nominal range | Output range | Window length | Number of inner iterations |
| ---: | ---: | --- | --- | ---: | ---: |
| 1 | **2** | **23–28 s** | corresponding output starting at 23 s **+delta** | **5 s** | **3** |
| 2 | **1** | **6–21 s** | corresponding output starting at 6 s **+delta** | **15 s** | **2** |
| 3 | **3** | **30–50 s** | corresponding output starting at 30 s **+delta** | **20 s** | **5** |
| After those calls | — | **50–70 s** | corresponding output starting at 50 s **+delta** | **20 s** | separate spectral finisher |

**Specific executable proof:**

1. `0x1800BEB2B / 0x1800BEB4D / 0x1800BEB6F` compute input pointer offsets `23*Fs`, `30*Fs`, `50*Fs`; `0x1800BEA5D` computes `6*Fs`. Output pointer calculation includes detected `delta` for each region.
2. `0x1800BEE9F / 0x1800BEEAA / 0x1800BEEB5` store the three selectors **2,1,3**.
3. `0x1800BEE8E` reads four int32 constants at `0x18024CFB0`, exactly **`[2,3,5,1]`**; `0x1800BEE96` stores that table on the stack. Dispatch selects iteration count from stack offset `+0xC4 + 4*selector`; this maps selectors 1/2/3 to **2/3/5** iterations respectively. The fourth value `1` is present but **not selected** by this three-call loop; its separate purpose is unknown.
4. Constants at `0x18024CCD0`, `0x18024CD34`, `0x18024CD40` are float32 **5, 15 and 20**. The loop's duration table (`0x1800BEF2A` / `0x1800BEF31` / `0x1800BEF3C`, lookup at `0x1800BF0AE`) maps selector 1→15s, 2→5s, 3→20s.
5. The paired pointer lookups occur at `0x1800BF0B6` (output), `0x1800BF0BE` (input), with call `0x1800BF0C9` to `0x1800BB210`; `0x1800BF0D1` checks for three calls.
6. The spectral finishing call `0x1800BF11E` goes to `0x1800B9B70` and uses separate pointers at `0x1800BF111/0x1800BF116`, mapped to the 50-second input/output pair. This is **not a fourth identical call** to `0x1800BB210`.

These constitute a **grounded static-call map**, not a guess that the 23s section is “saturation,” the 6s section is “clean,” etc. The objective of each of these stages remains unproven.

## Finding 2 — `0x1800BB210` really contains an adaptive optimization loop

The callee receives its iteration count at stack `[rsp+0x1C0]` (`0x1800BB245`), and branches back from `0x1800BC5C2` to `0x1800BB440` until that count is consumed. Thus numbers 3/2/5 above **really are fitting iterations**, not merely a static table adjacent to the fitting code.

At `0x1800BC410..0x1800BC440` the routine calculates a scalar control score using:

```text
score = (1 / 512) * sum_{i=0}^{511} abs(logf(v[i] + 2^-23))
```

This expression is confirmed by the 512-element loop bound (`0x200`), float32 `logf` call (`0x1800BC41C`), `abs` masking and binary float32 constant `1/512` at `0x18024C4F0`. **The immediate producer of `v[i]` is identified:** at `0x1800BC3CA`, `r13` receives a dedicated scratch-output pointer; at `0x1800BC3E4` the same pointer is passed on the stack as an output argument to `0x1800B5D00` (`call 0x1800BC3F9`); the callee reads that argument at `0x1800B5FE3` and **stores** values to it at `0x1800B60FE`; then at `0x1800BC410` the score loop reads the *same* `r13[i]`. Thus the metric is over **the output of `0x1800B5D00`**. However, the upstream inputs and mathematical meaning of that function’s output are not yet recovered. **Do not relabel this as final transmitted Post-FIR taps or frequency bins.**

The code directly implements the following *branching behavior* (comparison at `0x1800BC459`, first conditional branch at `0x1800BC469`, second at `0x1800BC514`):

```text
if current_score < previous_score:
    save current candidate arrays and score
else if current_score > 1.2 * previous_score:
    restore earlier saved candidate arrays
    exponent_scale = exponent_scale * 0.5
else:
    leave current candidate arrays in place
```

- `1.2` is the literal **double** at `0x18024C9A8`, multiplied at `0x1800BC504`.
- `0.5` is the literal **double** at `0x18024C880`, multiplied at `0x1800BC59C`.
- Separately, the power-law exponent scale decays by **0.9 each inner iteration** (`0x1800BB4BE`, pinned float32 at `0x18024C654`). This was initially discovered in Stage 3 but can now be located in the update rule.
- Backups include **both Pre-FIR and Post-FIR**: live contexts from `context+0x24408` and `context+0x24410` are forwarded as stack parameters `+0x1F8/+0x200`; improvement backs them up (`0x1800BC495/0x1800BC4B2`), while severe worsening restores them (`0x1800BC53F/0x1800BC55C`). The arrays are written back at the end (`0x1800BC62D/0x1800BC64A`).

**Important nuance:** The branch accepts an improved score; it **does not automatically reject every worsening**. Only a worsening beyond 20% triggers the restore/half-step branch; a smaller regression stays in the active state. This behavior is easily missed by describing the algorithm as simple gradient descent or “three passes.”

The inner loop also invokes `0x1800B5A30` twice (`0x1800BBB5B`, `0x1800BC381`), plus `0x1800B82B0` twice (`0x1800BC055`, `0x1800BC3C5`). The exact nonlinear/FIR transformation carried out by these helpers **is still NOT recovered**.

## What Stage 8 has NOT shown

- Neither the four gain-fitting outputs nor the 128/2048 final Pre/Post FIR values can yet be calculated solely from the input/output WAVs.
- The 512-component score has not been traced back to a named mathematical buffer; saying “512 coefficients, therefore Post-FIR” would be speculation.
- The constants do not prove a particular optimizer class (alternating least squares, coordinate descent, etc.); only the **actual schedule and branch predicates** are demonstrated.
- No attempt has been made to adapt these results to mobile SONICLINK or to infer its identity with Windows Manager.
- We have intentionally **not** made a CLO candidate: a guessed fitter would violate the source-first development gate.

## Reproduction and tests

The stand-alone `verify_stage8.py`:

1. Requires the *exact expected binary SHA256* and checks PE section mapping.
2. Runs GNU `objdump` **read-only** on two exact address ranges.
3. Checks **70 exact virtual-address instruction predicates**.
4. Extracts iteration `int32[4]`, three window-seconds float32 constants, and five optimizer float/double constants directly from the DLL's PE sections.
5. Asserts a frozen machine-readable three-pass schedule, source/output onset alignment rule, score-window loop, save/restore pointers and three branch cases.
6. Writes only an original research JSON of addresses and assertions; contains no proprietary DLL, vendor audio or CLO data.

On the supplied binary: **70/70 instruction checks pass**. Two independently repeated runs produced equivalent JSON evidence. No library was loaded or executed.

## Targeted next instruction-level work

Prioritize the **full buffer lineage** between `0x1800BB210`'s two `0x1800B82B0` calls, the `0x1800B5A30` calls and the **immediate producer `0x1800B5D00`** of the 512-element score array evaluated near `0x1800BC410`. Recover the mathematical equation for the array returned by `0x1800B5D00` and the identities of its input buffers. Record exact source and destination address expressions, strides, normalization/scaling and FFT convention. Then recover the actual objective being minimized and candidate update equations. Do not substitute a spectral-ratio heuristic simply because we have now found where the stage acts.

Only after a complete equation is grounded in code should we compute official FIR coefficients from the two matched WAV pairs and evaluate the original Stage 4 target. The production JS-only converter and the user-accepted JCM800 2203 v0.2 C remain untouched.
