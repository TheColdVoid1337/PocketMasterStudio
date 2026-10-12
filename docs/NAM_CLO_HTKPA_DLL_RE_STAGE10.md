# Sonicake HTKPA — Stage 10: DLL-confirmed cross-spectral fitting score

**2026-10-12. Source-first reverse engineering only. Production NAM→CLO JS converter, device slots and previous experimental CLOs remain unchanged.**

## The now-confirmed meaning of Stage 9's unknown arrays

Stage 9 proved that `0x1800B5D00` linearly interpolates two input arrays onto **512 Mel-uniform frequencies from 80 to 10,000 Hz** and that `0x1800BB210` evaluates:

```text
E = mean_{j=0..511}(abs(logf(v[j] + 2^-23)))
```

Stage 10 traces the two array producers inside **`0x1800B82B0`**, using their caller/callee pointers and exact instructions. The arrays are:

- **Abscissa** `a[k] = (k / N) × sample_rate` in ordinary **linear Hz**.
- **Ordinate** `b[k] = abs(S_AB[k]) / (S_AA[k] + 2^-23)` — a normalized cross-spectral **transfer magnitude** between current generated waveform **A** and desired waveform **B**.

Here `S_AA[k] = Σ_t |A_t[k]|²` and `S_AB[k] = Σ_t A_t[k] × conj(B_t[k])` (or the conjugate, depending on FFT imaginary sign conventions; magnitude is unaffected). Their complex real and imaginary components are accumulated across windowed frames. The same DLL function calculates `sqrt(Re² + Im²)` and divides by the accumulated first-signal auto-spectrum plus the literal epsilon.

Thus **the optimizer's control score evaluates spectral transfer deviation from unity on a perceptual frequency grid, not the values of 512 transmitted FIR taps**. This distinction resolves the Stage 8/9 open buffer-identity question.

## Verified data flow: code addresses (PE image base 0x180000000)

| Operation | VA and evidence |
| --- | --- |
| Current generated waveform **A** | `0x1800BC368` passes `r15` as output of `0x1800B5A30` (call at `0x1800BC381`); `0x1800BC399` passes that `r15` as first argument audio to `0x1800B82B0`. Inside `0x1800B5A30`, `0x1800B5A87` preserves destination from `r9`, and `0x1800B5C11/0x1800B5C15` addresses/copies to that destination. |
| Reference waveform **B** | `0x1800BC391` passes fitter's saved third audio argument (`[rsp+0x1B0]`) as the **second** audio buffer. Upstream `0x1800BF0B6` selects the corresponding probe output WAV region. |
| First and second input work buffers | `0x1800B85A6` and `0x1800B85C2` read and copy the incoming source arrays before preprocessing. |
| Hamming analysis window | `0x1800B83CA..0x1800B83DC`: `0.54 - 0.46*cos(2*pi*n/(N-1))`; local mean removed before weighting. |
| **Half-second frame hop** | `0x1800B83F3` reads exact double **0.5** at `0x18024C880`; `0x1800B83FB` truncates `0.5 × Fs` to an integer. End-window clamping is separately handled and is **not** assumed equal to standard STFT padding. |
| Two FFT-style transforms | `0x1800B8E38` and `0x1800B8E55` invoke `0x1800289D0` with each windowed signal and separate real/imag output arrays. Exact native transform normalization remains unverified. |
| Accumulate `S_AA` | `0x1800B901E..0x1800B9030`: square first-signal complex channels, sum, and add into a persistent auto-power array. |
| Accumulate complex `S_AB` | `0x1800B903E..0x1800B9066`: products of the two signals' real/imag channels, sum real contributions, subtract imaginary contributions, accumulate both. |
| Magnitude `abs(S_AB)` | `0x1800B9548..0x1800B9551`: sum of squares and square root. |
| Divide by `S_AA + epsilon` | `0x1800B9554..0x1800B955F`: epsilon vector at `0x18024D110`, equal float32 `2^-23`. Scalar tail `0x1800B97EF..0x1800B9817` also checked. |
| Generate abscissa in Hz | `0x1800B9564..0x1800B957B`: `k*Fs/N`, `floor(N/2)+1` bins. Scalar tail `0x1800B981D..0x1800B9832`. |
| Interpolate and score | `0x1800BC3D2..0x1800BC3F9` calls `0x1800B5D00` with transfer magnitude knots and 512 Mel-Hz queries; `0x1800BC410..0x1800BC440` scores the interpolated ratios. |

## Validation and limits

Research bundle `Sonicake_HTKPA_DLL_RE_Stage10_v0_10.zip` was delivered separately as a conversation artifact and includes an independently authored read-only verifier, `RESEARCH_REPORT.md`, and JSON evidence. Against the user-supplied SHA-pinned `5868USB.dll` it passed **51 exact address/instruction predicates**, checked **five PE constants**, and passed **eight synthetic scalar tests**. Two runs yielded byte-identical JSON. The DLL was **not executed** or redistributed.

**Independent synthetic test**: if B is exactly 1.7×A, the cross-spectrum ratio tends to 1.7 on sufficiently excited bins; unity signals produce a near-zero logarithmic score. A pure phase shift can leave transfer magnitude unchanged. These are properties of the now-proven scalar formulas, **not** evidence of bit-exact reproduction of the DLL's complete transform, optimizer or fitted CLO.

### Remaining strict acceptance gate

We have **not** calculated an exact official Pre-FIR or Post-FIR directly from source NAM/probe WAV. The **objective is more precisely known** now, but the mechanism for changing Pre-FIR and Post-FIR remains to be recovered.

**Next source-first Stage 11 target**: trace `0x1800BB440..0x1800BBB5B`, both calls to `0x1800B7670` (`0x1800BB4D9`, `0x1800BB4F8`), and `0x1800B68F0`. Establish actual candidate update equations, buffer identities and normalization from machine code **before** writing a fitting implementation or exporting experimental CLOs. Retain the user-preferred JCM800 2203 v0.2 C as subjective control; production JS remains unchanged.

**The Windows Manager algorithm is not proven identical to mobile SONICLINK.**


## Erratum added during source-first Stage 19 (2026-10-12): STFT hop is **half a window**, not half a second

The Stage-10 text `Half-second frame hop` / `≈0.5-second hop` was mistaken. `0x1800B8373` assigns the **analysis window length** to `r14d`. `0x1800B83EA–0x1800B83FB` converts that same window length to double, multiplies by PE double `0.5` (`0x18024C880`), then truncates to an integer. Therefore the actual step is **`trunc(window_samples*0.5)`**, a 50%-window hop. For a 4,800-sample window at 48 kHz it is 2,400 samples or 0.05 seconds, **not 0.5 seconds**. Any synthetic STFT fitting code using the previous fixed duration must be corrected before a numerical A/B comparison. This is an evidence-backed correction, not a heuristic. See [Stage 19](NAM_CLO_HTKPA_DLL_RE_STAGE19.md).
