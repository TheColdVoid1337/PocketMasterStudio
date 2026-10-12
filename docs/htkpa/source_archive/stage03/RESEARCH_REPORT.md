# Sonicake `5868USB.dll` — HTKPA reverse engineering: Stage 3

**12 October 2026** · PocketMasterStudio Void Mod · static binary forensics · **no vendor code executed**.

## Summary

This stage follows `0x1800BB210` (called three times with selector values 2, 1, 3) and `0x1800B9B70` (the next major routine). It identifies *specific numerical operations* missing from the previous research:

1. `0x1800BB210` is an **iterative, adaptive fit/update procedure**, not a simple FIR least-squares call. It calls the existing nonlinear saturator `0x1800BE700`, several convolution/filter routines and `0x1800B82B0` twice per iteration, processes a 512-element score, and adjusts a power-law exponent by a factor of **0.9** between iterations.
2. The earlier-unclassified helper `0x1800B82B0` constructs a **Hamming window** with scalar coefficients 0.54 and 0.46 and a cosine at 2πn/(N−1). This is a verified formula, not just a guess that a window might be involved.
3. `0x1800B9B70` contains **spectral magnitude matching**: `sqrt(re²+im²)` for complex spectra, per-bin division after adding an epsilon, **clamps to [0.1, 10]**, and additional spectral/cosine tapering and amplitude normalization. This is stronger evidence of spectral inverse fitting than the previous “filter construction” designation.
4. The DLL contains a **0.1-second sample-rate-dependent support parameter** near the start of `0x1800B9B70`: `ceil(sample_rate × 0.1)`. This is *not* evidence that the exported CLO has a 0.1-second impulse response or that its 512 stored/output taps correspond directly to this particular buffer.
5. The helper `0x1800B4CF0` shows *circular complex convolution/multiplication* with modulo indexing and real/imaginary arithmetic, while `0x1800B52E0` constructs sine/cosine basis values. They help identify a frequency-domain design path, but its full normalization and sequence of transforms have not yet been reconstructed.

### Source verification

- Source file: user-provided Windows Sonicake Manager `assets/5868USB.dll`, **SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`**.
- PE64 image base: `0x180000000`. All addresses are **virtual** addresses, not raw offsets.
- Independent static tool: `verify_stage3.py` checks **31 exact instruction addresses**, confirms imported CRT math function thunks (`powf`, `logf`, `sqrtf`, `cosf`) and reads 11 pinned data constants from PE sections.
- Pure mathematical primitives reproduced separately in `reproduce_primitives.py` with **5 passing unit tests**. These reproduce only *isolated equations*; they are not a replacement for HTKPA and do not read official reference CLOs.

## 1. `0x1800BB210`: adaptive filtering

### 1.1. Iterated power-law update, precisely observed

At `0x1800BB460`–`0x1800BB492`, the routine:

- loads a positive float into `xmm0`, constructs an exponent from `xmm12 × buffer[i]`, and calls **`powf`** at `0x1800BB46E` (import thunk `0x18017E158`);
- clamps the result into **[0.2, 5.0]**: floor literal `0x3e4ccccd` (0.2) at `0x1800BB48C`, and ceiling register holding **5.0**;
- performs element-wise products (`mulps`, `0x1800BB575`) and divisions (`divps`, `0x1800BB6E1`) on intermediate buffers;
- between iterations, multiplies `xmm12` by the float32 **0.9** (`0x1800BB4BE`, coefficient VA `0x18024C654`). This is an **exponent/step annealing schedule** of some kind; its exact relation to the final fitting objective is still unclear.

The local *scalar* equation is therefore:

```text
b[i] = clamp(powf(a[i], alpha * q[i]), 0.2, 5.0)
alpha_next = alpha * 0.9
```

Here `a[i]`, `q[i]` and the precise meaning of the state arrays remain to be established. We deliberately do not label `b[i]` the final Post-FIR response.

### 1.2. Real nonlinear model inside the loop

Direct call `0x1800BBCC9 → 0x1800BE700` applies the previously recovered asymmetric exponential saturator. Other calls within the *same loop* include:

- `0x1800B7670` (both `0x1800BB4D9` and `0x1800BB4F8`),
- `0x1800B5A30` (`0x1800BBB5B`),
- `0x1800B82B0` (`0x1800BC055` and `0x1800BC3C5`),
- `0x1800B5D00` (`0x1800BC3F9`).

This is **joint nonlinear + filter iteration**. It explains why optimizing just Post-FIR on an existing Void CLO does not reproduce the full official procedure, though it does not yet identify each internal matrix/vector or an exact end-to-end loss function.

### 1.3. A 512-element logged metric

At `0x1800BC410`–`0x1800BC440` an array is processed with:

```text
sum(abs(logf(value[i] + 2^-23))) for i in 0..511
mean = sum / 512
```

Instruction evidence: `logf` thunk at `0x1800BC41C`; absolute-value mask at `0x1800BC42B`; `cmp rdi, 0x200` at `0x1800BC437`; scaling constant **`0.001953125 = 1/512`** at VA `0x18024C4F0`. The algorithm compares the mean with a convergence/control value and takes alternate update paths (`0x1800BC459` onward).

**Caution:** the *origin* of the 512 values is not yet proven. This is **not** proof they are exactly the 512 transmitted Post-FIR taps, even though the lengths coincide.

## 2. `0x1800B82B0`: precise Hamming window

Instructions `0x1800B83B0`–`0x1800B83DC` compute:

\[
w[n] = 0.54 - 0.46\cos\left(\frac{2\pi n}{N-1}\right)
\]

The relevant direct evidence is:

- float32 **2π** at `0x18024CCF0`;
- float32 **0.46** at `0x18024C5B0`;
- float32 **0.54** at `0x18024C5D4`;
- `cosf` via `0x18017E11C` at `0x1800B83CA`;
- `0.46 × cos` at `0x1800B83CF` and `0.54 − …` at `0x1800B83D8`.

For N=129 the mathematical window has values **0.08** at either end and **1.0** at the center. The standalone reference unit test verifies these properties. The integration of this window into the final per-stage FIR output still requires data-flow tracing.

## 3. `0x1800B9B70`: magnitude-driven spectral reconstruction

### 3.1. Time/support and tapering

Near `0x1800B9BCB`:

```text
r13 = ceil(double(sample_rate) × 0.1)
```

At 44.1 kHz this is ~4410 samples, at 48 kHz ~4800, and at 96 kHz ~9600. (These values characterize an internal work interval only.) Later `cosf` is called again at `0x1800BA820` in a taper-like loop. Helper `0x1800B4CF0` is called twice at `0x1800BA8A3` and `0x1800BA8BB` to process complex pairs.

### 3.2. Complex spectral magnitude is explicit

At `0x1800BA962`–`0x1800BAA73`, for consecutive pairs `(re, im)`, the code computes:

\[
M = \sqrt{re^2 + im^2}.
\]

This is confirmed by `mulss`, `addss`, and **`sqrtf`** at `0x1800BA97B` and equivalent neighboring sites. Two different complex spectra are converted into scalar magnitudes.

### 3.3. The stable per-bin ratio

At `0x1800BAC70`–`0x1800BAD2E` (including vector operation at `0x1800BAC9A`), per-frequency magnitudes are formed into a **stabilized ratio**. The SIMD operands contain **1,000,000** and **2^-23** (about 1.19209×10^-7). The local equation is:

\[
r[k] = \frac{10^{6}\, M_a[k]}{10^{6}\, M_b[k]+2^{-23}}.
\]

At `0x1800BAEA5`–`0x1800BAECE` the ratio is explicitly **clipped into [0.1, 10.0]**; the procedure is applied to subsequent processing buffers with a further helper call (`0x1800BAEF9 → 0x1800B7E10`).

We **cannot yet state with confidence** which upstream processed signal corresponds to `M_a` or `M_b`, whether a particular invocation is computing Pre-FIR or Post-FIR, or whether a later normalization/scaling substantially changes the ratio. The formula is recovered *locally*, not as the whole CLO fitting formula.

### 3.4. End-stage amplitude balancing

Two energy sums use squared values (`0x1800BB010`–`0x1800BB0BD`); both pass through **`sqrtf`** before a **ratio at `0x1800BB0E2`**. This is evidence of **energy/RMS normalization** in the filter-finishing chain. The exact source/output roles and propagation need another trace.

## 4. Overall hypothesis after Stage 3

A plausible high-level pipeline of the proprietary Windows converter is:

1. One 70s structured DI through WaveNet, followed by initial input/output conditioning and normalization.
2. Identify nonlinear transfer parameters using polarity-specific signal bins and constrained parameter sweeps.
3. Use **three differently configured** stages (selectors 2→1→3), iterating filtering and the nonlinear transfer with a power-law update, reciprocal operations, frequency-domain estimation and a 512-element convergence/control metric.
4. Build/shape filter responses with spectral magnitude ratios, epsilon protection, bounded gain, Hamming/cosine tapering and energy normalization.
5. Pack **128-tap Pre-FIR**, **4 floats of nonlinear gain**, **2048-tap Post-FIR** into 8840-byte VTSI/CLO; pedal upload sends the restricted 512-tap Post-FIR form.

The function call sequence and *local formulas* are verified; **the mapping of the intermediate arrays to final filters, exact transform conventions and the full update equations are still hypotheses / incomplete**. No official CLO has been reconstructed from the equations in this report. The Mobile SONICLINK and Windows Sonicake Manager algorithms are not proven identical.

## 5. What we can implement next

The most valuable next reverse-engineering target is now *specific*:

- Track two calls to `0x1800B82B0` and their output pointers into subsequent `0x1800B5D00` to establish which array becomes the Pre-FIR / Post-FIR.
- Follow `0x1800B7E10` output through `0x1800B65A0` and `0x1800B5A30` in `0x1800B9B70`, and then into final context arrays `context+0x233xx/0x23bxx` and the VTSI serializer.
- Reconstruct filter-specific normalization/cropping and test *numeric coefficient predictions* against the official JCM800 2203 and SC20 CLOs. Do this before changing the JS-only browser converter.
- Preserve the user-approved JCM800 v0.2 C as a hardware-audition baseline; v0.3 auto-tone is experimental with unknown on-pedal results.

## 6. Reproduce locally

```bash
python verify_stage3.py '/path/to/assets/5868USB.dll' --out evidence.json
python -m unittest -v test_primitives.py
python reproduce_primitives.py
```

The verifier needs Python3 and GNU binutils `objdump`. It validates SHA-256, PE layout, instructions, imported math functions and constants. It **does not execute** the DLL or connect to a physical pedal. No proprietary DLL, copyright audio samples, original NAMs or vendor CLOs are included in the research ZIP.

**Research-only result. No production modification.**
