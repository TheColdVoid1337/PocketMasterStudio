# HTKPA RE — Stage 6: Complex exponential and minimum-phase FIR evidence

**2026-10-12 — clean-room static analysis + independent offline numerical verification**

## Result and acceptance

**Major finding:** Both matched Windows Sonicake Manager Post-FIR filters closely match an independently constructed **minimum-phase impulse response** from their own Fourier magnitude. The DLL also contains a log-spectrum / complex-folding / complex-exponential pipeline consistent with a minimum-phase spectral factorization method.

**Not achieved:** No algorithm has yet generated the *vendor Post-FIR amplitude spectrum itself* directly from the NAM+WAV. No official CLO has been recreated coefficient-by-coefficient from the independent input/output waveforms. This stage therefore **does not meet** the original Stage-4 FIR-from-WAV acceptance gate. Mobile SONICLINK ≠ Windows Manager equivalence also remains unverified.

## 1. DLL evidence — SHA pinned, never loaded or executed

Analyzed `5868USB.dll` SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa` (image base `0x180000000`). `verify_stage6.py` independently checks **20 exact instruction locations** using `objdump` and pins the binary hash. The following operations were directly read from code:

| Virtual address | Machine-code observation | Interpretation |
| --- | --- | --- |
| `0x1800B73BB` | calls `logf` | logarithmic representation of a spectral quantity |
| `0x1800B7450` | calls `0x1800B5D00` | interpolates processed spectral arrays; exact interpolation still under investigation |
| `0x1800B748F` | reverse-indexed spectrum copy | mirrored spectrum layout |
| `0x1800B754A` | calls complex transform helper `0x1800B4A50` | intermediate transformed complex arrays |
| `0x1800B7569` | calls `0x1800B6E30` | uses symmetric complex values |
| `0x1800B6EDB/0x1800B6EEB` | real components added, imaginary components subtracted | conjugate folding consistent with Hermitian symmetry |
| `0x1800B7590` | calls `0x1800B4F60` | another transform in spectral synthesis |
| `0x1800B75D5` | calls `expf` | compute `exp(a)` |
| `0x1800B75E1`, `0x1800B75F4` | calls `cosf` and `sinf` | compute `cos(b)` and `sin(b)` |
| `0x1800B75E6/0x1800B75F9` | multiply by prior `expf` result | reconstruct complex spectrum **`exp(a) * [cos(b) + i sin(b)]`** |
| `0x1800B5B4B` | transform call `0x1800C0F60` in 64-sample blocks | internal block/FFT-style helper; role not completely reconstructed |

The `exp(a)*(cos(b)+i*sin(b))` local formula is **directly proven** by the instructions, not a guess. That `a,b` correspond precisely to a particular cepstral Hilbert convention at *every* point is a supported **hypothesis**, not a full proof until all intermediate buffer mappings are reconstructed.

## 2. Independent minimum-phase experiment

Take any known FIR `h[n]` (not just vendor ones), compute `A[k] = |FFT(h)|`, obtain the real cepstrum `c = IFFT(log(max(A,epsilon)))`, create the causal/minimum-phase cepstrum by doubling strictly positive-time coefficients, and synthesize `h_min = IFFT(exp(FFT(c_min)))`. This is our own Python/Numpy/SciPy **offline experiment**, not code extracted or copied from the DLL.

The analysis uses **1881 nonzero Post-FIR taps** stored in a 2048-tap CLO field, FFT size **32768**, relative magnitude floor **1e−8** and no amplitude, sign, lag or phase fit. Result measure is raw cosine of coefficient vectors at exactly aligned tap index 0:

| CLO (same NAM pairs) | Cosine(Post-FIR, independent minimum-phase reconstruction) | Relative L2 difference |
| --- | ---: | ---: |
| **Official Windows Manager JCM800 2203** | **0.998563** | 0.05360 |
| **Official Windows Manager SC20 Full Rig** | **0.999589** | 0.02867 |
| Baseline Void Mod JCM800 2203 | −0.243669 | 1.57713 |
| Baseline Void Mod SC20 | −0.040724 | 1.44272 |
| Hardware-auditioned JCM800 2203 v0.1 refit | −0.297339 | 1.61080 |
| Hardware-auditioned JCM800 2203 v0.2 C | −0.226487 | 1.56620 |

**Robustness:** At FFT sizes 8192, 16384, 32768 and 65536, the official 2203 similarity remains between **0.998515 and 0.998766**; SC20 similarity between **0.999544 and 0.999800**. The phase fingerprint is not due to one particular FFT size.

The **Pre-FIR** in all six compared CLOs already yields ≈1.0 cosine against minimum-phase reconstruction; the major structural difference is the **Post-FIR**.

## 3. Cross-reference: official JCM800 Post-FIR vs phase-projected Void variants

| Compared to official 2203 Post-FIR | Original raw cosine | After independent minimum-phase projection |
| --- | ---: | ---: |
| Void baseline Post-FIR | −0.1932 | **+0.9622** |
| v0.1 refit Post-FIR | −0.2847 | **+0.9473** |
| v0.2 C Post-FIR | −0.2916 | **+0.9367** |

These compare **all 1881 nonzero taps** and retain each source's native amplitude response. This is not evidence that changing phase in a complete multi-stage amplifier yields better sound; the source FIR spectra, four nonlinear parameters, Pre-FIR and gain staging can still differ.

## 4. Separate candidate for on-pedal phase A/B (NOT validated)

`candidates/JCM800_2203_v06_MIN_PHASE_FROM_C_UNVALIDATED.clo` is a **phase-only experiment** derived from the user-favored **JCM800 v0.2 C**. It projects only the **first 512 taps actually sent to the pedal** to minimum phase, not the entire 1881 coefficient file. This decision specifically avoids entangling a different hidden Post-FIR tail with the candidate.

- All **128 Pre-FIR taps**, all **four nonlinear parameters**, DC filter and other CLO fields remain **byte-identical** to v0.2 C.
- The post-FIR tail after the first 512 samples remains **byte-identical**; CRC16 is recalculated. VTSI length is 8840 bytes.
- The existing v0.2 C physical-audition baseline remains untouched.
- 512-tap Post-FIR cosine against Windows Manager 2203 changes from **−0.29471** to **+0.95036** (no signed gain/lag adjustments).
- Magnitude response of the 512 transmitted taps differs from original v0.2 C by a **mean 0.000217 dB** on a 32768-point FFT grid. The tap L2 norms remain ~0.343812 (before/after). This is a **phase** comparison, not output-volume or equalization correction.
- **Hardware sound not tested.** Changes in transient response, group delay and amplifier perceived tone are possible even with nearly identical magnitude response. No evidence is available yet that phase-projected C sounds better or worse than the originally favored C.

If conducting physical audition: back up v0.2 C and SONICLINK, use a spare slot, reduce monitoring volume, and compare the same DI with the same gain/monitoring chain. **Do not apply this to every NAM or auto-enable it in production.**

## 5. Verification and package contents

- `verify_stage6.py`: 20 pinned DLL instruction checks; VTSI/CRC16 and numerical tests against two official + two Void + two auditioned refit CLOs. SHA-256 pinned, DLL **never executed**.
- `minimum_phase.py`: original independently implemented minimum-phase reconstruction code, no proprietary source or binary.
- `test_minimum_phase.py`: **five passing tests**: known minimum-phase FIR, delay removal, magnitude preservation, invalid input, FFT resolution stability.
- `create_experimental_candidate.py`: explicit-input generator (no device I/O). Verifies CRC, preserves non-Post fields, checks filter magnitude preservation.
- `evidence.json`: hashes, exact assembly lines, numerical results.
- `phase_2203.png`, `phase_sc20.png`: first 110 official post-FIR taps vs minimum-phase reconstructions.

The archive **excludes the commercial DLL, original NAM, official WAV and official CLO source files**. The generated, unvalidated candidate CLO is clearly labeled and is not a proprietary official coefficient dump.

## Next gate

1. Trace `0x1800B4A50 → 0x1800B6E30 → 0x1800B4F60` to recover the actual complex-log spectral phase construction **including signs, gain normalization, Fourier transform conventions and frequency-bin count**.
2. Estimate the smoothed Post-FIR **magnitude** from the NAM's input/output WAV and its Pre-FIR/nonlinear model, without using the official Post-FIR; synthesize minimum-phase taps and compare them to the reference. This is the missing independent end-to-end numerical gate.
3. Obtain level-matched hardware DI reamp A/B feedback for v0.2 C vs new *phase-only* candidate to evaluate audible effect before changing production.
4. Keep shipping JS and all past working reference files unchanged until independent objective and subjective validation on multiple NAMs.
