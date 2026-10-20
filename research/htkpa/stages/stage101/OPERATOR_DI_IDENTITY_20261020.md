# Stage101 operator DI identity gate — 2026-10-20 (Bangkok)

**Result: ACCEPTED OPERATOR CONSOLE EVIDENCE; original private report not independently inspected by assistant.**

After manually installing the Stage101 offline auditor from the private RE_HTKPA handoff patch, the operator ran **13/13 regression tests successfully** and audited the SHA-gated original Stage97 Manager WAV/CLO ZIP against the two existing SonicMaster reference CLOs.

The Stage101 tool reported `STRUCTURAL_FIR_LENGTH_FINGERPRINT_MATCHED_NOT_FITTER_PARITY`, `vendor_structurally_valid=true`, `all_three_clo_fir_lengths_match=true`, `all_three_fixed_biquad_match=true`.

**New independent input gate**: SonicMaster's existing public 70-s mono 44.1-kHz float32 reference DI was quantized directly to PCM16 and compared without gain fit, lag shift, or resampling against the native Manager's Stage97 stereo 44.1-kHz input WAV.

| Operator-reported metric | Value |
|---|---:|
| Frames compared | **3,087,000** |
| Exact PCM16 identity | **true** |
| Identity fraction | **1.0 (100%)** |
| RMS difference, PCM16 LSB | **0.0** |
| Zero-lag cosine similarity | **1.0** |

This closes **one input-excitation provenance gate**. Equal test DI does not establish native vs open NAM output identity, matched runtime state, proprietary fitter algorithm equivalence, coefficient parity or CLO production. The captured 70-s 48-kHz Manager output WAV now offers a concrete next comparison target for open NAM Core; model identity, input resampling, channel handling, PCM16 quantization, prewarm, and alignment must be controlled before interpreting errors.

**Data boundaries:** Original model, vendor DLL, WAV/CLO bytes, private JSON and audio hashes remain excluded from public GitHub. Complete operator-derived private summary and local Stage101 script/test archive are in canonical RE_HTKPA. Public production browser converter unchanged. The experimental Stage101 auditor itself is not yet tracked on public GitHub (manual local patch).
