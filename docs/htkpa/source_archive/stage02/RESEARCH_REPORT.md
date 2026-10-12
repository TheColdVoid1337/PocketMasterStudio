# Sonicake 5868USB.dll — HTKPA reverse engineering, stage 2

**Date:** 2026-10-12  
**Project:** PocketMasterStudio Void Mod  
**Scope:** static disassembly, imported-function resolution, actual CLO parameter comparison. No DLL execution, no hardware communication, no edits to production JS.

## 1. Binary, validation and method

Pinned Windows x64 DLL (`assets/5868USB.dll` from user-supplied Sonicake Manager):

- SHA-256: `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
- x64 PE image base `0x180000000`; VAs below must **not** be confused with raw file offsets.
- `verify_stage2.py` reads the DLL as **bytes**, checks the hash and PE sections, and invokes `objdump -d -M intel` and `objdump -p`; it does not import or execute vendor code.
- **30 instruction checks** passed against pinned assembly; `expf` IAT import verified; the independently generated and previously cached disassembly give **byte-identical JSON evidence**.
- `evidence_direct.json` contains concrete instruction addresses and verified constants; no undocumented formula is asserted to be recovered.

## 2. The original saturator's mathematical formula is confirmed

### 2.1. Direct scalar function (`0x180028690`)

A standalone vendor function uses imported `expf` (`0x18017E12E` thunk → IAT RVA `0x18B9A8`). Its branching and arithmetic independently establish:

\[
f(x)=\begin{cases}
P_{\max}\left(1-\exp(-P_{rate}x)\right),&x>0\\
N_{\max}\left(\exp(N_{rate}x)-1\right),&x\le 0
\end{cases}
\]

*Positive* path: `0x18002869D` tests sign, `0x1800286B2` multiplies positive rate by `x`, sign flips at `0x1800286B6`, `expf` at `0x1800286C0`, `1 − exp` at `0x1800286CD`, amplitude multiply at `0x1800286D1`.

*Negative* path: `0x1800286E7` multiplies negative rate by `x`, `expf` at `0x1800286EE`, `exp − 1` at `0x1800286F3`, negative amplitude multiply at `0x180028700`.

This is mathematically **the same asymmetric exponential saturator family already implemented by SonicMaster/Void Mod**. The vendor operates using `float32`/`expf` in this function; the pure-Dart fitting uses double arithmetic until float32 output. Tiny rounding differences are possible, even with the same formula.

### 2.2. Vector application (`0x1800BE700`)

This routine reads the four gains from context offsets `+0x243F8`, `+0x243FC`, `+0x24400`, `+0x24404` and calls the same scalar nonlinear function four times per loop-unrolled iteration. Therefore the four CLO gains are not opaque random fields: they directly control a vendor DSP nonlinear transfer function.

### 2.3. Fitting the gains (`0x1800BDBE0`)

This is no longer an unidentified preprocessing function. The caller at `0x1800BEDA3`–`0x1800BEDE4` explicitly passes **addresses of the four nonlinear gain fields** to it. The routine:

1. Computes positive and negative maxima and other binned signal statistics (e.g. compare/store at `0x1800BDD91`, `0x1800BDDB4`; count/bin loops and reductions at `0x1800BDECD`).
2. Forms predicted nonlinear values using `expf` and accumulates **squared errors** against the counterpart signal (`0x1800BE4A1`–`0x1800BE4FD`, separate sign paths).
3. Searches scalar rate multipliers in the range **0.8 to 1.2, step 0.05** (literals `0x18024C608`, `0x18024C748`, `0x18024C9A8`), separately for positive and negative shapes; see loops beginning near `0x1800BE480` and `0x1800BE560`.
4. Writes four resulting fields at `0x1800BE661`, `0x1800BE676`, `0x1800BE682`, `0x1800BE68F`.

**Caution:** This describes observable algorithmic structure, not yet a bit-exact high-level reconstruction of binning, initialization, scaling or loss normalization. The fit is not just the four-parameter unconstrained nonlinear least-squares optimizer used in SonicMaster.

## 3. Recursive audio filtering is present upstream of fitting

`0x1800BD490` contains a repeated two-state recursive structure with coefficients at:

- First feedback bank: `context+0x232F0`, `context+0x232F8`.
- First feedforward bank: `context+0x232D8`, `context+0x232E0`, `context+0x232E8`.
- A second feedback/feedforward bank: `context+0x23318`, `context+0x23320`, `context+0x23300`, `context+0x23308`, `context+0x23310`.

For the first bank the arithmetic is **consistent with** a direct-form-II second-order section:

```
w[n] = scaled_input[n] - a1*w[n-1] - a2*w[n-2]
y[n] = output_scale * (b0*w[n] + b1*w[n-1] + b2*w[n-2])
w[n-2] = w[n-1]; w[n-1] = w[n]
```

Machine-code evidence: `0x1800BD564`–`0x1800BD5C6`, and another analogous section near `0x1800BDACD`–`0x1800BDB3B`. The scale constants, exact coefficient initialization and algorithmic purpose of the stages are **not yet known**. In particular, these recursive stages are *not* proof that the final `CLO` stores IIR instead of FIR: the actual CLO remains 128/2048 FIR.

## 4. Explicit sample-rate-specific coefficient sets

`0x1800BC6B0` branches on float32 sample-rate comparisons with literal values **44100, 48000 and 96000 Hz** (`0x18024CDF0`, `0x18024CDF4`, `0x18024CDF8`) and loads differing tables of SIMD constants, e.g. near `0x1800BC753`, `0x1800BC802`. This is concrete evidence of **sample-rate-dependent DSP preprocessing**. It remains premature to label these tables as a particular resampler, EQ calibration or windowing kernel; trace the consumer and external comparisons first.

## 5. The three-pass call is a selector dispatch, not proven repeated fitting

The dispatcher inside `0x1800BE830` writes **2, 1, 3** (`0x1800BEE9F`, `0x1800BEEAA`, `0x1800BEEB5`) into three selector positions; the loop at `0x1800BF050`–`0x1800BF0D5` then indexes different input/output pointers and stage-specific lengths before calling `0x1800BB210`.

This is **not** evidence of three identical coordinate-descent iterations. It is more consistent with three differently configured fitting stages or regions, but their exact outputs remain unknown.

`0x1800B9B70` follows the selector loop and contributes to final filter construction; its mathematical role is still unresolved. `0x1800C0D40` then processes both coefficient arrays before the 8840-byte VTSI container is packed.

## 6. Cross-check: actual official CLO gain parameters

The same four gain fields were decoded from the user-provided vendor and Void Mod CLO pairs, using little-endian float32 at byte offset 104. These are **measured file values**, not estimates:

| NAM | Version | Positive Max | Negative Max | Positive Rate | Negative Rate |
|---|---|---:|---:|---:|---:|
| JCM800 2203 Crunch | Windows Manager | 0.058698 | 0.062518 | 425.44 | 356.19 |
| JCM800 2203 Crunch | Void baseline | 0.207526 | 0.207998 | 764.80 | 764.80 |
| SC20 Full Rig | Windows Manager | 0.010617 | 0.012697 | 450.93 | 253.91 |
| SC20 Full Rig | Void baseline | 0.054729 | 0.056443 | 877.18 | 1182.64 |

The **formula** used by the vendor matches SonicMaster's saturator family, but the **fit** produces very different gains. Do not infer the resulting loudness directly from these numbers: Pre-FIR and Post-FIR differ, and the pre-saturator signal scale is also different.

## 7. Revised engineering diagnosis

**Confirmed:** Basic nonlinear math has the same form as our current model. The vendor has its own waveform-bin/statistical preprocessing, separate per-polarity SSE parameter fitting, recursive audio conditioning and sample-rate-specific coefficient sets; it processes three distinct selector configurations. This is substantially more specific than Stage 1.

**Not recovered:** the entire HTKPA algorithm, exact FIR-design equations, how the vendor chooses initial Pre-FIR and final Post-FIR, stable/bit-exact reproduction of gains, or a DLL-independent single-pass CLO encoder that matches the vendor.

**Next target:** follow data lineage at `0x1800BB210` (three selector-specific output writes), then `0x1800B9B70` and `0x1800B82B0` to identify actual frequency-domain/linear-algebra filter optimization. Use two pinned input/output WAV pairs and their official CLOs to validate the extracted formulas. Only after those tests should a new JS experimental path be prototyped.

**Production:** Void Mod JS-only converter is unchanged. The user's well-received JCM800 v0.2 C remains the hardware-auditioned quality reference; v0.3 auto-tone remains experimental.

## Run the verifier

```bash
python verify_stage2.py /path/to/5868USB.dll --out evidence_direct.json
```

If a **full** disassembly has already been cached, the optional `--cached-disasm /path/to/dll_disasm.txt` avoids rerunning objdump. Both paths were run, with identical machine-readable evidence. Requires only Python 3 and GNU binutils; never executes the DLL. The original DLL, WAV, NAM and commercial CLO data are **not redistributed** in this research package.
