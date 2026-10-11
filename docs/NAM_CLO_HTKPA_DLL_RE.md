# NAM → CLO: Sonicake 5868USB.dll HTKPA reverse engineering

**2026-10-12 · Stage 1 · Static analysis only.** This research is independent of the current browser-only converter and does not change default DSP behavior. The user's proprietary Windows DLL, source NAM, and captured WAV/CLO files are **not** committed to the repository.

## Baseline / verification

- Windows Sonicake Manager `assets/5868USB.dll`: x64 PE+, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
- Exported `namConvertCloData`: RVA `0xE1F70`; `appNamConvertCloData`: RVA `0xABEB0`.
- Proven internal call: code at VA `0x18000FA41` calls `0x1800BE830` after loading both WAV buffers.
- A read-only PE/disassembly verifier was built and tested both with a cached objdump and by running `objdump` against the actual DLL. **Nineteen independent static-code checks pass, yielding identical evidence JSON.** The DLL was never executed.
- Captured `nam_input_wav.wav` for SC20 and JCM800 2203 Crunch is byte-identical; SHA-256 `9bb6c1b136dfbeb7538a6060499d98c89342b76ec568b76836e36ab98b29aa1a`.

## Important newly verified behavior

The internal function at `0x1800BE830` processes the buffer at `context+0x243E8` at a sample rate recorded at `context+0x20EC0`:

1. Determines a work length of approximately `70 × sample_rate + 600` samples (literal 70, 600), subtracts the output's mean and a least-squares **linear trend** in-place.
2. Searches a **600-sample window starting at six seconds** for the first sample with `abs(sample) > 0.01` (`0x1800BEA5D`–`0x1800BEAD6`).
3. Accesses explicit positions at **6, 23, 30, 50 seconds**, with additional windows of **5, 15, 20 seconds**.
4. Calls internal procedures **`0x1800BDBE0` → `0x1800BD490` → `0x1800BC6B0`**, then calls `0x1800BB210` in a loop with three entries and finishes via `0x1800B9B70`. The three calls have different arguments: **do not assert they are three identical coordinate-descent iterations**.
5. Packs an **8,840-byte VTSI/CLO**, including the 128-tap Pre-FIR, four float32 nonlinear parameters, 2048-tap Post-FIR and CRC16. Main packing range is `0x1800BF1C4`–`0x1800BF542`. The 512-tap upload form is distinguished elsewhere.

These addresses are VAs assuming image base `0x180000000`, **not file offsets**.

## Probe WAV confirms temporal segmentation

RMS measured from user-provided 70s, 44.1 kHz, 16-bit stereo PCM input (L/R identical):

| Interval (s) | Input RMS (dBFS) | Tentative role |
| --- | ---: | --- |
| 0–5 | −12.38 | increasing-level stimulus |
| 6–21 | −54.34 | quiet stimulus |
| 23–28 | −8.01 | loud stimulus |
| 30–50 | −26.43 | evolving-level stimulus |
| 50–70 | −16.95 | dynamic stimulus |

The official output WAVs for the two NAMs both span 70 seconds at 48 kHz. Approximate resampling to 44.1 kHz yields a threshold crossing in the 600-sample window for **both** models: ~18 samples for SC20; ~0 for JCM800 2203. These counts are not claimed as bit-exact to the DLL.

## Implications

**Strong hypothesis:** the official Windows converter uses multiple purpose-built regions of **one 70-second WaveNet rendering**, rather than five complete separate inference passes at scaled DI levels as SonicMaster does. This is consistent with the vendor log and signal staging and helps explain the speed advantage. A full proof of every inference path, exact fit equations and binary-equivalent output remains outstanding.

The finding is compatible with previous experiments: independent WaveNet predictions match vendor output WAV after an approximately constant ×0.31 factor for both captures, while differences in the fitted CLO parameters remain material. The Windows Manager algorithm is not proven identical to the mobile SONICLINK implementation.

**No production changes** are justified yet; the recent user-accepted v0.1 and v0.2 C Post-FIR experiments must remain available as controls.

## Next RE targets

1. Recover the equations and vector layouts of `0x1800BDBE0`, `0x1800BD490`, `0x1800BC6B0` by correlating the output arrays with reference-window measurements.
2. Trace the three differently parameterized calls to `0x1800BB210`; identify which window/fitting constraint each call handles.
3. Follow writes to `context+0x243F8..0x24404` and final packing at `0x1800BF238..` to recover all four nonlinear parameters.
4. Trace the 128/2048-tap filter buffers and `0x1800B9B70`. Only after formulas are independently reproduced, prototype a single-pass **pure JS** NAM→CLO path behind an experimental opt-in.
5. Validate numerically against both captured official Windows Manager CLOs and on-device using identical DI and loudness-matched presets; avoid claims of sonic fidelity based solely on coefficient similarity.

The conversation's downloadable `Sonicake_HTKPA_DLL_RE_Stage1_v0_1.zip` contains the reproducible **read-only** Python tools, a detailed address/constant report, machine-readable proof lines and WAV-region plot. It intentionally excludes proprietary source material and never executes the DLL or writes to a pedal.
