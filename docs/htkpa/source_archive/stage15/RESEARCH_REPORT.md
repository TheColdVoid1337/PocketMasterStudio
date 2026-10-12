# Sonicake HTKPA — Stage 15: feedback ratio and final Post-FIR correction

Date: 2026-10-12. **Evidence-first, static reverse engineering of the user-provided Windows `5868USB.dll`.**

## Strict outcome

**Two specific missing blocks from Stage 14 are now resolved at the level of their core arithmetic and data flow:**

1. The `0x1800BC055–0x1800BC33D` feedback stage builds a *regularized ratio of float32 spectral arrays* and passes it to the **already decoded** `0x1800B7670` Mel/dB conditioner, then the shared `0x1800B68F0` Post-FIR synthesizer. The precise identity of every upstream scratch buffer (and complete initialization/branch semantics) has **not yet** been recovered.
2. The finalizer `0x1800B9B70`, called after the three fitting stages, constructs a frequency-domain correction, clamps it to `[0.1, 10]`, Gaussian-smooths it, and calls `0x1800B65A0` to **synthesize a 256-tap correction, causally convolve it into the working Post-FIR, truncate to original length, and subtract its mean**. After rerendering audio, it scales the Post-FIR using a **ratio of square-root summed energies**.

**This is NOT yet an end-to-end reproduction of the vendor HTKPA.** The finalizer's full spectrum provenance, native Fourier internals and all data-driven updates/float32 parity have not been reconstructed; an official CLO has not been generated from NAM/WAV. No new device candidate or modification to the production JS converter is justified by this stage alone.

## Source artifacts

Pinned source: Windows x64 `assets/5868USB.dll`, **SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`**. All addresses below are image-base `0x180000000` virtual addresses, **not file offsets**. Disassembled with GNU `objdump -d -M intel`, never loaded or executed. The DLL, original NAM, WAV, proprietary CLO and full disassembly are not included in the distribution ZIP.

## 1. Precise feedback quotient (0x1800BC055–0x1800BC33D)

At `0x1800BC055`, Sonicake runs the Stage-10 confirmed cross-spectral estimator `0x1800B82B0` on current rendered versus reference audio. Immediately afterward it computes a **float32 output from float64 intermediates** with the following local scalar form:

```
Q[k] = float32( 1_000_000.0 * float32(A[k]) /
                 (1_000_000.0 * float32(B[k]) + 2**-23) )
```

The names `A/B` here are intentionally **position labels**, not a claim that both are direct raw STFT magnitudes. In the vectorized loop the first source array is accessed through `rdi`, the denominator through `r13`, and destination through `r10` (alias displacements rearranged for SIMD); in the scalar tail code the same operations appear explicitly.

| Operation | Verified VA | Machine-code fact |
|---|---|---|
| STFT cross-spectrum estimation | `0x1800BC055` | call `0x1800B82B0` |
| SIMD numerator multiplier | `0x1800BC10D` | `mulpd xmm3,xmm4` |
| SIMD denominator multiplier | `0x1800BC114` | `mulpd xmm2,xmm4` |
| SIMD epsilon and divide | `0x1800BC118`, `0x1800BC11C` | `addpd` then `divpd` |
| Scalar numerator and denominator | `0x1800BC226`, `0x1800BC222` | two `mulsd` by factor `1e6` |
| Scalar epsilon and division | `0x1800BC22A`, `0x1800BC22F` | `addsd` then `divsd` |
| Store scalar float32 result | `0x1800BC237` | `movss` destination |
| Curve conditioning | `0x1800BC33D` | call `0x1800B7670` |
| Working Post-FIR synthesis | `0x1800BC342`, `0x1800BC35C` | destination via `[rsp+0x200]`, shared `0x1800B68F0` |

The exact constants are encoded as doubles: at `0x18024D5A0` **1e6**, at `0x18024D1E0` **2^-23**. Effective denominator regularizer in unscaled units is **1.1920928955e-13** — **not** the adaptive `1e-6 × max(power)` regularizer used in the abandoned Stage-7 research prototype. For zero input numerator and zero denominator the quotient is zero. For truly zero denominator and positive numerator it may become enormously large before later conditioning; **do not assume native clipping in this block**.

**Remaining data-flow uncertainty:** the first of the two arrays, the post-estimator reference/correction array used in the denominator, and their allocation lifetimes need complete SSA/pointer tracing. This prevents us from asserting that `Q` alone is the complete multiplicative update formula for both FIRs.

## 2. Final Post-FIR finishing (0x1800B9B70)

At `0x1800BF100` the HTKPA caller places `context+0x24410` (working Post-FIR) into the fifth argument of the finalizer, then calls `0x1800B9B70` at `0x1800BF11E`. Unlike the three-stage optimizer, this function runs **once after its main loop**.

Native sequence:

1. At `0x1800B9BCB–0x1800B9BD5`, compute `ceil(0.1 × sample_rate)`; for 48 kHz that is **4800**. Allocate enough scratch space for half-spectrum arrays.
2. Prepare matched rendered/target audio (`0x1800B9FF3`, `0x1800BA019`), run spectral work (`0x1800BA3FB`, `0x1800BA8A3`, `0x1800BA8BB`) and complex-bin amplitudes using `sqrtf(re²+im²)` (`0x1800BA97B`). The exact intermediate buffer identities and native transform convention are not fully decoded.
3. Build another **regularized spectral ratio** using doubles: `1e6 * numerator / (1e6 * denominator + 2^-23)` at `0x1800BAC70–0x1800BAD2E`. Clip to **[0.1,10]** (`0x1800BAEB3`, `0x1800BAEC6`), Gaussian smooth via `0x1800B7E10` (`0x1800BAEF9`). This is distinct from directly smoothing a finished FIR.
4. At `0x1800BAF88` call `0x1800B65A0`: it conditions the ratio on a **256-bin** grid, synthesizes a **256-tap correction filter**, and combines it with the existing Post-FIR (see section 3).
5. At `0x1800BAFAB` rerender the signal through the corrected Post-FIR. After separate sums of squared samples, `0x1800BB0C0` and `0x1800BB0CB` take square roots. `0x1800BB0E2` forms their ratio and `0x1800BB12F` multiplies the Post-FIR taps by the ratio. This is an **energy-based output gain calibration**, not just an EQ shelf.

## 3. Corrective FIR convolution and DC removal (0x1800B65A0)

The native function is **not** just a frequency-domain copy operation:

- `0x1800B65B8` and `0x1800B65CC`: allocate two **1024-byte** buffers (256×float32).
- `0x1800B65FD`: run the already known curve conditioner `0x1800B7670` with target count **256**.
- `0x1800B6621`: call shared minimum-phase-like synthesizer `0x1800B68F0`, producing a **256-tap FIR**.
- Allocate `(PostFirLength+255)` float32 accumulator slots and zero-initialize them. The nested loop from `0x1800B6690` through `0x1800B675D` runs **256 inner multiplies per source tap**, adding products to the shifted destination (`0x1800B66A6–0x1800B66AF`). The pointer advances by 4 bytes for the source tap. Thus structurally the output is a **causal linear convolution**, not a circular FFT convolution.
- `0x1800B6771` copies only the first `PostFirLength` output taps to the original working Post-FIR, discarding the extra 255 tail samples.
- `0x1800B67B0–0x1800B67EA` sums and divides by PostFirLength; `0x1800B682B` and `0x1800B68B0` subtract that mean from each output tap.

For ordinary non-degenerate float32 arrays, the isolated algebraic analog is:

```
g = synthesize_256(condition_spectrum)       # recovered stages 13–14
full = causal_convolve(post_fir, g)           # length L+255
h = full[:L]
h = h - mean(h)
post_fir[:] = h
```

The finalizer then applies the energy-based gain from step 5. **Do not confuse this with directly generating a completely fresh 2048-tap Post-FIR: it corrects the already fitted one through convolution.**

## 4. Checks against user-provided official CLOs

These are **evaluation-only checks**, not parameter fitting. The *official* Windows Manager files contain:

| NAM | Sum of 2048 Post-FIR taps after official processing | Post-FIR L2 |
|---|---:|---:|
| JCM800 2203 Crunch | `0.002959` | `1.170528` |
| JCM800 SC20 Full Rig | `0.006035` | `1.922987` |

The near-zero sums are consistent with DC removal before the 48→44.1 kHz FIR resampling (Stages 4 and 11). This does **not** prove the missing time-domain outputs or all coefficients were recreated.

## 5. Reproducibility and strict acceptance

The independent Python script `verify_stage15.py`:

- checks DLL SHA256 without importing or executing any native code;
- verifies **46 exact-address instruction anchors** across both missing processing blocks;
- reads and checks **8 declared binary constants** (some refer to the same underlying scalar, used in two contexts);
- runs **13 synthetic tests** for float32 rounded feedback ratios, causal truncated 256-tap convolution, mean removal and energy gain normalization;
- writes repeatable JSON evidence, separately from source data.

**All 46 + 8 + 13 checks passed.** The report does not assert exact native float32 kernel parity, boundary behavior under zero/negative spectral magnitudes, the full optimizer feedback buffer provenance, or reproduction of vendor FIR from NAM/WAV.

**State of goal:** the two Stage-14 blocks have their key operations recovered, but the *overall full HTKPA* is still incomplete. Priority for another truly independent end-to-end attempt: reconstruct the remaining scratch array provenance in `0x1800BB210`, compute the complete source-derived 2→1→3 proposal/acceptance updates, and validate upstream and corrected FIR coefficients against **both** matching Windows Manager CLOs. No guessed gains, Brightness boosts, or replacing the JS production converter.
