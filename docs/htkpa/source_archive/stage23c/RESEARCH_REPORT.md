# Sonicake HTKPA Stage 23C — FIR + fractional polynomial resampler construction

**12 October 2026 — Stage 23 continuation, source-confirmed architectural checkpoint; not finished Stage 23.** SHA-pinned original DLL: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`, Windows x64 PE image base `0x180000000`. No DLL execution, firmware interaction, device writes, commercial runtime redistribution, or production JS edits.

## 1. Significant correction to the interpretation of Stage23B

Stage23B proved the dynamic-rate source path and located a filter descriptor cache but did not reconstruct downstream stage layout. We now confirm the common **44.1→48k and 48→44.1k** `target*2 > source` branch of `0x180011B60` creates **one 2:1 FIR intermediate stage AND one distinct fractional polynomial interpolation stage**. It does **not** reduce to an FIR with final truncation, nor is a standard `scipy.signal.resample_poly` implementation demonstrated equivalent.

The first FIR filter descriptor is acquired by `0x18000BB80` (calls `0x18000B0E0` on cache miss) at `0x180011CE3`, with documented cutoff choice of `0.5` when `target>source`, otherwise `0.5*target/source`; `0x18000BDF0` constructs the first stage with `r8d=2`, `r9d=1` (`0x180011CEF/CF5/CFE`). Direct native PE vtable at `0x180244EA0` proves sizing method `0x18000C140` (`+0x20`) and streaming method `0x18000C220` (`+0x30`). The constructor calls first-stage sizing at `0x180011D37`. Because `0x18000BDF0` initializes phase `+0x58 = 0` (`0x18000BF21`), the capacity formula `0x18000C140–C152` in this branch is `(2*N - 1 + phase + 1)/1 = 2*N`.

Crucially, code `0x180011D6E–0x180011D7C` checks `2*source > target` and for the two rate pairs enters `0x180011F04 → 0x180011F1F → 0x180012170`. Here **another object** of size `0x1048` is created with vtable `0x180245170`, stored at `resampler+0x50` (`0x18001222A`), and its sizing method is invoked (`0x180012237`). Its `+0x1008` carries `2*source`, `+0x1010` the `target`, and `+0x1018` a prior-stage delay/phase value. It is a fractional-rate interpolator, **not a second FIR cache object**.

## 2. Read-only PE vtable proof

`0x180244EA0` seven function pointers: `CC70,C100,C110,C120,C140,C160,C220` (all prefixed by PE base `0x18000...`).

`0x180245170` seven function pointers: `14320,11AC0,11B50,13DC0,13D90,13D30,135C0`. The latter two functional anchors are: `0x180013D90` output-buffer *capacity*, and `0x1800135C0` streaming sample interpolation.

At `0x180013D94–DB5` the fractional stage returns **`ceil(input_count * target_fs / intermediate_fs) + 1`**. The `ceil` identification is pinned to imported CRT thunk `0x18017E10A` → IAT `0x18018BA30` (`ceil`). This is a capacity provision / method return; NOT proof that one extra WAV sample is written. For captured 70s DI `N=3,087,000` @44.1k into a hypothetical 48k path: FIR capacity 6,174,000 @2*44.1k; interpolation capacity **3,360,001** samples. Reverse 48k→44.1k: 6,720,000 intermediate and **3,087,001** final capacity. The extra +1 is the documented constructor capacity guard, not an established outputFile.wav length.

## 3. 24-sample interpolation / dynamically constructed 673-phase polynomial table

The vtable streaming method `0x1800135C0`:

- `0x1800135F1` uses global runtime table `0x1802C7560` (not backed by PE raw file). `0x18001360C` loads immutable double **673.0** from `0x18024CCB8`.
- `0x180013763–0x18001377B` multiplies fractional phase by 673, `cvttsd2si` selects bin, then computes local fractional remainder.
- The table address calculation at `0x18001376F–0x180013775` maps each bin to **72 doubles = 576 bytes**: `((bin + 8*bin)<<3)*8`. These 72 coefficients are organized as **24 groups × three f64 polynomial coefficients**; the sample reads run from `[r10+rax*8+0x8]` through `[...+0xC0]`, 24 samples. Each group's coefficient polynomial is evaluated with fractional phase and its square, then weighted by one sample and accumulated.
- Source instruction `0x180013C38` writes a `double` interpolated sample; following code `0x180013C49–0x180013CAD` advances the fractional-rate position, adjusts a ring-buffer index and stores next remainder.
- The generated table is **not in the DLL's ordinary on-disk bytes**: producer at `0x1800163FF` references its address; code through `0x180016440..0x18001687B` applies coefficient transformations and stores values to `[rax]`, `[rax+8]`, `[rax+0x10]` (and successive groups). Therefore simply extracting 673×24×3 floats from a static `.rdata` section is invalid. This provenance is the next numerical research target.

This interpolation makes the resampler structurally distinct from a generic FIR+truncation, despite sharing the same sample-rate ratio.

## 4. Upstream FIR coefficient source

`0x18000B0E0` does more than select a generic sinc: it derives filter length and coefficient workspace and calls `0x180014810` from `0x18000B981`. The latter advances oscillator states and calls `0x180008FD0` to compute a radial window. The window path uses squared normalized radius and `sqrt(1 - t²)`, a Bessel-like helper `0x180008E90`, and a stored normalizer (`0x180008FD0–0x18000902B`). The mathematical shape is compatible with a Kaiser/Bessel window, but native transcendental approximation, exact radius/phase initialization and sequence of oscillator products remain **unproved numerically**. After kernel construction `0x18000B9C0` sums coefficient doubles; `0x18000B9E3` divides a target normalization by that sum, and `0x18000BA02` multiplies individual taps. The fallback `0x180008D70` also has a sum-and-normalize path.

This differs from adopting SciPy's generic Kaiser window or reusing a modern polyphase routine. There is **no source-grounded end-to-end audio parity yet**.

## 5. Reproduction and checked inputs

`stage23_polyphase_source.py` pins **79 original DLL instruction addresses**, the **14 precise PE vtable function pointers**, and immutable **673.0** double. It passes **10** independent synthetic arithmetic checks. Two `evidence.json` runs are byte-identical. The earlier Stage21 and Stage22 standalones were rerun against the exact DLL SHA and passed (Stage21 **75 pins / 8 constants / 77 assertions**; Stage22 **43 pins / 7 constants / 53 assertions**).

Read-only captured input DI SHA256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a` (both models identical, 70s PCM16 stereo 44.1k); output WAVs 70s PCM16 stereo 48k. Vendor CLO 2203 SHA `50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7`; SC20 SHA `2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a` (read-only). **No new vendor gains from paired WAV have been calculated**.

## 6. Exact remaining strict gates

1. Reconstruct the **runtime phase-polynomial table initialization** at `0x1800161xx–0x18001687B` from original PE and independent mathematical validation; then implement the 24-sample evaluator at `0x1800135C0` with ring-buffer, initial phase and delay.
2. Reconstruct native FIR coefficient synthesis `0x18000B0E0→0x180014810→0x180008FD0` including original table values / approximants and FFT stage processing.
3. Confirm actual Manager exported sample rate and dataflow for both WAVs and scale, produce source-equivalent floating buffers at `context+0x243E0/+0x243E8`, detrend, onset and fitted window.
4. Only after (1)-(3) compute independent `(pmax,nmax,prate,nrate)` from unchanged Stage21 fitter and compare **both** Marshall models against official CLO as held-out oracle.

No production changes, no new CLO, no pedal upload. This is Stage23C checkpoint; full Stage 23 remains OPEN.
