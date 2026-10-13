# Stage28 — public-source identification: r8brain-free-src

Date: 2026-10-13. Status: **STRONG SOURCE-LINEAGE MATCH**, exact library version/build not yet independently pinned.

## Discovery

Public MIT-licensed C++ library: https://github.com/avaneev/r8brain-free-src

Its `CDSPFIRFilter.h::buildLPFilter` is a high-specificity match to the native source-pinned DSP geometry recovered from Sonicake Manager 1.0.1 `5868USB.dll` SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.

Specific *independent* matches:

- `CDSPResampler.h::CDSPResampler24` passes **180.15 dB** attenuation to the generic resampler, matching original Stage24B native filter constructor.
- `CDSPFIRFilter.h::buildLPFilter()` uses `AttenCorrCount=264`, `AttenCorrMin=49.0`, `AttenCorrDiff=176.25`, correction scale `196.0` for the small-transition branch and an inline signed-char correction table. Stage23H observed original DLL lookup **index=197, value=49**, with original PE inline constant table.
- Same nontrivial expression for `pwr`, including the **two cos calls** (mistakenly called exp in Stage23H until corrected in Stage24C), the actual exp term, and matching floating constants including `0.00785021930010397`, `0.633854318781239`, `0.103208573657699`, `0.0969365532127236`.
- Same `pwr > 0.067665322581` small-transition formula for `hl` using `cos(1.1609073390614*pwr - 6.33932586197475*pwr^3)` and `fo1` using `log(pwr)` and `atan(59.7538527741309*pwr)`.
- Same `WinParams[0]=125.0`, `WinParams[1]=pwr`, Kaiser window raised to the power gamma, and FFT-based FIR architecture.
- `CDSPResampler.h` directly includes `CDSPFracInterpolator.h`; the r8brain README says the algorithm performs initial 2x oversampling, then interpolation via a bank of 8–30-tap fractional delay filters. Thus this open code provides the most credible first source for the previously missing fractional stage.

## Other relevant public independent converter

https://github.com/Skyggedans/SonicMaster, licensed MIT. Its `app/rust/src/api/generator.rs` explicitly claims to be an open-source analog of vendor `namConvertCloData`, generates 128-tap input and 2048-tap output FIR arrays and four nonlinear gains, runs WaveNet over a **bundled original-tool-equivalent 44.1 kHz reference DI**, and fits multi-level Wiener–Hammerstein approximation. `app/lib/protocol/clo_dsp.dart` mirrors it. Crucial differentiation: its resample() is explicitly a windowed-sinc approximation of scipy `resample_poly`, not demonstrated to use r8brain's exact resampler; its claimed 'match or beat' fit quality does not establish vendor-algorithm parity. Its value for HTKPA is reference NAM inference, test audio, CLO format, and comparative hypotheses, not proof of identical fitting algorithm.

## Immediate replication path

1. Vendor/pin the public MIT r8brain code at an explicit upstream commit **with attribution and intact MIT copyright/license** under a separate third_party/ namespace or upstream dependency; never conflate with the original Sonicake DLL or proprietary data. First locate closest historical upstream revision corresponding to 1.0.1.
2. Write minimal C++ native harness for 44100->48000 using r8brain `CDSPResampler24`, same input PCM path, and compare actual native capture boundaries and PCM24 WAV. Test exact parameterization (`ReqTransBand`, linear phase) instead of assuming constructor defaults.
3. After resampler parity, use SonicMaster's independent converter as an external baseline for NAM inference and CLO structure; reverse-engineer the vendor fitter only where output behavior differs.
4. Keep all evidence labels: observed original PE SOURCE; upstream public code SOURCE; identical lineage DERIVED; exact vendor version/build NOT_PROVEN; full NAM->CLO parity OPEN.

## License

Public `r8brain-free-src/LICENSE` is MIT, © 2013–2026 Aleksey Vaneev. Its README requests credit “Sample rate converter designed by Aleksey Vaneev of Voxengo”. SonicMaster is MIT; preserve its license if code is used. No proprietary binaries, NAM/DI/raw audio or private captures are to be committed.
