# Stage29 — r8brain provenance and configuration gate (2026-10-13)

**Status:** source lineage HIGH CONFIDENCE; vendor embedded version/build **NOT YET DETERMINED**. Goal: identify original r8brain source and actual vendor parameterization for an independent MIT-compatible recreation, not another substitute NAM→CLO fitter.

## Source-comparison checkpoints

| Native evidence from SHA-pinned original `5868USB.dll` | Public r8brain source | Judgment |
| --- | --- | --- |
| Filter constructor cutoff=0.5, quality/transband=2, attenuation=180.15, gain=2 | `CDSPResampler.h::CDSPResampler24` constructs base with `ReqTransBand=2.0`, `ReqAtten=180.15`, `fprLinearPhase` (current master around lines 790–809) | Exact unusually distinctive defaults. Branch selection still depends on rate/phase. |
| Native correction table index 197 → signed 49; `AttenCorrCount=264`, minimum 49, span 176.25, scale 196 | `CDSPFIRFilter.h::buildLPFilter`, small-transition branch table (lines ~369–393) | Source-family fingerprint |
| Stage24C two CRT calls `cos` and one `exp`; exact `pwr` formula and power-Kaiser window beta=125 | `CDSPFIRFilter.h` lines ~395–480 | High-specificity mathematical match |
| Native filter cutoffs .5/.459375, G=708/771; f64 coefficients 8184/8192 bit equal to reconstructed | `CDSPFIRFilter`, `CDSPSincFilterGen` | Strong independent numeric support; not exact SIMD/CRT bit parity |
| Stage25 FFT product bit-identical, inverse numerical near-identical; Stage26 scratch 24/24 bit-identical; Stage27 stride=1 contiguous memcpy | `CDSPFIRFilter`, `CDSPBlockConvolver`, `CDSPResampler` streaming | Structurally consistent; class/function identity needs per-address mapping |
| Missing actual fractional branch | `CDSPFracInterpolator.h` and two-stage oversample2→fractional architecture in README | Promising source, NOT YET NATIVE VERIFIED |

**Key original files**:
- https://github.com/avaneev/r8brain-free-src/blob/master/CDSPResampler.h
- https://github.com/avaneev/r8brain-free-src/blob/master/CDSPFIRFilter.h
- https://github.com/avaneev/r8brain-free-src/blob/master/CDSPFracInterpolator.h
- https://github.com/avaneev/r8brain-free-src/blob/master/CDSPBlockConvolver.h
- https://github.com/avaneev/r8brain-free-src/blob/master/CDSPSincFilterGen.h

## Version narrowing (requires real evidence)

The public master in October 2026 is a moving target (r8bbase.h currently declares 7.6), **not** a justified identification of the version in Sonicake Manager 1.0.1. Use upstream tags/commits to compare:

1. Does native `0x18000C...` stream path match old or newer `CDSPBlockConvolver` work/scratch logic, including exact `R8B_EXTFFT` and FFT format?
2. Does `0x18000B...` coefficient generation use the pre- or post-v5.9 Kaiser optimization? Differences among the 8 remaining near-ULP values may localize CRT/compiler rather than source revision.
3. Does native fractional inner loop match pre/post-v5.3 SSE2 optimization and pre/post-v7.4 timing logic?
4. Are FFT routines native Ooura RDFT or PFFFT DOUBLE, and which historical implementation? Confirm by original PE instruction signature before selecting compile definitions.
5. Cross-check native `CDSPResampler` construction and chosen steps for actual 44100→48000 sample rates, not merely `CDSPResampler24` defaults.

## Next fastest concrete parity experiment

Build a minimal public r8brain C++ executable (pinned commit, MIT notices) that converts **identical** mono 44100 f64/f32 input in chunks with `CDSPResampler24(44100,48000,maxInLen,2.0)`; measure output count, latency, first 64 output values, and streaming invariance; compare to same-conversion native boundaries/PCM24 output. If mismatch, investigate **rate-step configuration and fractional-stage version** before reimplementing DSP. Public r8brain source and our RE scripts must remain separated; do not ship Sonicake DLL or private audio in Git.

## Scope control

This investigation strongly identifies the **resampler**, NOT the Sonicake-specific NAM→CLO nonlinear fitting. The preexisting SonicMaster fitting approach is a known unsuccessful project baseline; do not substitute it for vendor RE.

r8brain-free-src MIT © Aleksey Vaneev, attribution and license required if reusing code. README requests: “Sample rate converter designed by Aleksey Vaneev of Voxengo”.
