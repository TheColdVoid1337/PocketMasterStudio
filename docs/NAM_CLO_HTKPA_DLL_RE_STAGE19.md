# Sonicake HTKPA Stage 19 — source-pinned 50-tap audio-preprocessing FIR and real WAV gate

**2026-10-12. STRICT STATUS: original initial A/B from real WAV still NOT COMPUTED.** This stage makes a verified upstream checkpoint, not a complete NAM→CLO implementation. No production JS, experimental CLO, or pedal writes.

Source: the user-supplied Windows Sonicake Manager `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. DLL examined statically only with Python PE section parsing and `objdump`, never executed or redistributed.

## Actual recovered native 50-coefficient input FIR

At `0x1800BC739`, `0x1800BC7EF`, and `0x1800BC89E`, `0x1800BC6B0` selects three **different, hard-coded float32 50-tap coefficient banks** by native sample rate **44,100 / 48,000 / 96,000 Hz**. Branch starts are `0x1800BC753`, `0x1800BC802`, and `0x1800BC8B1`. For each branch, the DLL loads exactly **twelve 4-float SSE vectors plus two scalar floats** into one contiguous 50-element stack array.

At `0x1800BC94D` this array is passed as the second argument; `0x1800BC95A` sets the coefficient count to `0x32` (50), and `0x1800BC96D` invokes **`0x1800B5A30`**, the partitioned-convolution helper, to process source audio. Its body uses `0x1800C0F60` with 64-sample blocks. The complete float32 partition/rounding implementation is not yet rebuilt, so a simple reference causal FIR convolution must **not** be called bit-exact vendor processing.

The three actual PE tables are independently decoded in the Stage-19 research script; there are **70 exact address/operand pins**, comprising 42 original PE-source coefficient-reference instructions and 28 call/dataflow control pins. Source-derived table diagnostics (not fitted):

| Native branch | first three coefficients | sum | L2 norm |
| --- | --- | ---: | ---: |
| 44.1 kHz | 2.368210, 3.574280, 3.095710 | −0.0868914 | 7.695335 |
| 48 kHz | 2.369809, 3.532199, 3.386006 | −0.0252041 | 8.024002 |
| 96 kHz | 2.369809, 3.144882, 3.532199 | −0.9660231 | 11.273363 |

The proprietary coefficient arrays are **not committed**. The user can reextract and verify them from the original local SHA-pinned DLL.

## Real-WAV input audit

Two independent user-captured official Manager sessions were read, **not fitted**:

| Model | Input DI WAV | Reference output WAV |
| --- | --- | --- |
| JCM800 2203 Crunch | 70 seconds stereo PCM16, 44.1 kHz | 70 seconds stereo PCM16, 48 kHz |
| SC20 Full Rig | 70 seconds stereo PCM16, 44.1 kHz | 70 seconds stereo PCM16, 48 kHz |

Both input DI WAVs are **byte-identical**, SHA-256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`. Both channel pairs are identical, but the output WAVs differ (2203 RMS ≈0.03403, SC20 RMS ≈0.01028).

A **separate mathematical audit**, not a claim about the complete native preprocessing, applies the DLL-derived **44.1-kHz 50-tap FIR** by simple causal convolution to the actual unresampled 44.1-kHz DI. Its RMS is ≈**0.82734** and peak ≈**8.962** before IIR/nonlinear processing. This must **not** be compared as a vendor sound output, since the actual HTKPA 44.1→48-kHz input conditioning, subsequent gain mapping and further DSP stages have not been implemented. The evidence records only hashes, RMS, peaks, four section measurements and eight example float32 output samples, never full input WAV data. Vendor Pre/Post FIR coefficient arrays were not accessed for fitting.

## Two additional tracing results

After the native 50-tap input FIR, `0x1800BC6B0` executes first and second recursive second-order sections bracketing `0x1800BE700` (the known four-parameter nonlinear saturator), then spectral analyzer `0x1800B82B0`, after which Stage 18's two Gaussians / quadratic spectral floor / A/B quotient become applicable.

For the sections, state buffers and coefficient pointers are confirmed: `context+0x20/+0x28/+0x30` with `context+0x232D8..0x232F8`, and `context+0x20C98/+0x20CA0/+0x20CA8` with `context+0x23300..0x23320`. The **actual coefficient constructor** was located at `0x1800BFF17..0x1800C0216`, with selection into live filter fields at `0x1800BEC36..0x1800BED00`. These source-specific coefficients and native numerical behavior are not yet reproduced.

**Stage-10 correction:** `0x1800B8373` uses `r14d` as the STFT analysis window length; `0x1800B83EA–0x1800B83FB` computes **`trunc(0.5 × window_length_samples)`** as the hop. It is a **50% window hop**, **not a fixed half-second hop** as the old report mistakenly stated. An explicit erratum has been added to [Stage 10](NAM_CLO_HTKPA_DLL_RE_STAGE10.md).

## Verification and strict acceptance gate

Separate user-facing package `Sonicake_HTKPA_DLL_RE_Stage19_v0_19.zip` contains `stage19_source_first.py`, **12 successful independent tests**, full `RESEARCH_REPORT.md`, `evidence.json`, `plot_stage19.py`, figure of the three extracted frequency responses, and README. **70 pinned native instructions and all three coefficient banks pass.** Source-side code reads the local DLL as bytes and never executes it. ZIP integrity checked; no proprietary DLL, capture media or commercial CLO in the archive.

**Still not achieved:** initial real-WAV **A/B arrays**, full optimizer 2→1→3, or coefficient comparison of new independent vendor Pre/Post FIR. The gate remains `NOT_COMPUTED` for A/B and `NOT_TESTED` for official FIR parity — no CLO emitted. Next source-first steps must reproduce the **biquad coefficient constructor**, the four-gain audio fitting procedure `0x1800BDBE0`, native resampling/alignment and the STFT buffer conventions in `0x1800B82B0`, then connect to the working Stage-18 A/B function. Do **not** substitute a generic Welch fit or secretly use official CLO coefficients as fit targets.

The user-auditioned JCM800 2203 v0.2 C and production PocketMasterStudio Void Mod converter remain unchanged.
