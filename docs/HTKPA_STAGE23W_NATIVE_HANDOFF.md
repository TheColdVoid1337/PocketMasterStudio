# HTKPA Stage23W — Windows-native FIR handoff

## Executive result

**NATIVE_HIT / PARTIAL.** A real Sonicake Manager import reaches the FIR lane branch at `0x18000C5B0`; the live filter byte `+0x34` is `1`, its coefficient pointer is live at `+0x50`, and the complex branch `0x18000C5F0` was not hit. The Stage23S conflict is resolved for this filter: the native coefficient spectrum is effectively real, so the lane loop correctly uses one real coefficient for both packed entries.

For packed bins `k >= 1`, native f64 output is bitwise `y[2k]=x[2k]*h[2k]`, `y[2k+1]=x[2k+1]*h[2k]`; all 4096 doubles of a paired block match. The remaining open question is whether the independent Stage23I static coefficient reconstruction matches the native pre-FFT buffer exactly.

## Provenance and reproduction

2026-10-13, Asia/Bangkok; Windows 11 x64; Sonicake Manager 1.0.1; Python 3.13 x64; Frida 17.6.1. Original `5868USB.dll` SHA-256 is `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`; PE preferred base `0x180000000`; a retained runtime base was `0x7ff87e390000`; `live = base + (static - 0x180000000)`.

Use the private Windows venv and attach the reusable tracer to the already running Manager: `research/htkpa/stages/stage23w/native_trace.py --host <Manager.exe> --dll <5868USB.dll> --out research/_LOCAL_FILES/stage23w_native/<session> --pid <pid> --seconds 25`. Wait for `ready.private.json`, then import once. The tracer is observational, range-checks each 32768-byte f64 read, and writes raw arrays/events only under the ignored tree.

## Native event and object facts

The filter alias `filter_A` was `0x215149be050`, with `filter_A+0x50 = 0x215145ca020`, 1417 taps and phase 11. Its processor alias `state_A` had `state_A+0x34 = 4096`; two work buffers alternated. `C56E` recorded 9218 selections in each retained capture, all with `filter+0x34 = 1`; `C5B0` was hit and `C5F0` was not. The constructor (`B996`), coefficient transform (`BAC1/BAC6`), input transform (`C468/C489`), multiply selection, lane multiply, and inverse boundaries were observed during genuine imports. The private event streams are `stage23w_native/20261013_flag_capture_restart/trace.private.jsonl`, `20261013_packed_capture/trace.private.jsonl`, and `20261013_discard_capture/trace.private.jsonl`.

## Filter, spectrum and inverse

`coeff_pre_fft_00` has 1417 significant f64 entries at `0..708` and `3388..4095`, zero in the intervening 2680 entries, exact circular symmetry, and sum `0.0009765624999999992` (approximately `1/1024`). Native `coeff_post_fft_00` equals `conj(rfft(coeff_pre_fft_00))` in Stage23R packing `[Re0, ReNyquist, Re1, Im1, ...]`, maximum error `5.142739455391301e-19`. Odd pair slots have magnitude at most `2.710505431213761e-19`, explaining the flag-1 lane result.

The valid multiplication input is the `C56E` snapshot **after** `C494–C556` repacking, not the earlier `C489` snapshot. Its coefficient snapshot was taken from the same live filter and coefficient pointer in the immediately preceding retained trace. The naive elementwise product misses by `0.0006777608545014361`; the pairwise formula above has maximum error `0.0` and zero nonmatching doubles. Native post-inverse blocks equal `2048 * irfft(conj(packed_product))`; maximum errors are `8.673617379884035e-19` and `9.75781955236954e-19`.

The Stage23I static candidate has the same 4096 layout, 1417 active entries and gain sum, but does **not** equal this native buffer: max f64 error `1.6025453961367097e-06`, RMS `2.8553058553229254e-07`, and all 1417 active entries differ. Its SHA-256 is `ff4b587594a156df2fe8fd34a7a639eeb09e3cc9a59fcfba93afa17737d241be`; native is `649adeb70df4bb17f73ca09c0e4bc8bd3511271fa388d989bb2094ead22b0770`. Treat Stage23I as source-derived, not native coefficient parity.

## Streaming and limits

Native first-block emission is zero, then 1972, then 2680 doubles. At `C689`, observed `state+0x84` starts at 3388 then 708; at `C6D2` it is 2680 then 0. `state+0x38 = 708`. `state+0x54 = 0` reaches `C759`; it does **not** alone establish direct `C824` memcpy, because `state+0x2c` controls that final choice. The tracer now records `output_period = state+0x2c`; capture it before making an output-route claim.

Stage23S lane selection, Stage23T flag lineage, Stage23U inverse sign/scale, and Stage23V block counts are native-confirmed for this run. Exact Stage23I coefficient parity, output-route period, PCM/resampler stages, gains, CLO parity, and device-output equivalence remain unproven. No production source, vendor DLL, device setting, raw audio, RAM dump, or proprietary input is committed.

## Next static targets and validation

Investigate the Stage23I generator's upstream parameters and math-call precision to explain the measured coefficient mismatch. Separately disassemble `0x18000C6FC–0x18000C861` around `state+0x54/+0x2c`, with the falsifiable prediction that `+0x2c <= 1` selects `C824`; use one bounded live capture only to read that field. Continue static WAV decoder/resampler work from Stage23E only with these FIR facts retained.

The first static WAV-writer gate is now source-pinned in `stage23x/pcm24_writer_source.py`: it saturates f32 at `[-1, 1]`, converts with `2147483647.0` plus the native f64 rounding magic, then packs signed `int32 >> 8` as three little-endian bytes. Reload/decoder parity and resampler output remain open.

Tracked sanitized artifacts are `research/htkpa/stages/stage23w/native_evidence.json`, `native_analysis.json`, `native_trace.py`, `analyze_native_fir.py`, and `validate_native_evidence.py`. Validate with `python research/htkpa/stages/stage23w/validate_native_evidence.py`; analysis requires an interpreter with NumPy and explicit private input/coeff/result roots.

## Independent uploaded raw-archive audit — 2026-10-13

The subsequent user-provided private `stage23w_native.zip` was opened and **checked directly**, rather than relying only on Codex's written numerical claims. The ZIP has **107 members**, **26,884,892 uncompressed bytes**, and no CRC errors. Raw arrays remain private; this addendum gives only hashes and aggregate results. No original proprietary DLL bytes were present in this archive; the DLL SHA is taken from the corresponding recorded native manifest, not rehashed from ZIP.

- **One-run provenance:** `20261013_overlap_capture` includes `coeff_pre_fft_00`, `coeff_post_fft_00`, `input_packed_00/01`, `after_spectral_multiply_00/01` and `after_inverse_00/01`. Recorded object IDs confirm the coefficient object and both selected blocks share **the same filter pointer** and 4096-double work plan *within this run*. This strengthens the earlier handoff caveat about comparing adjacent runs.
- **Independent native arithmetic audit:** for each of those **two** 4096-double blocks, the exact rule `y[0:2]=x[0:2]*h[0:2]`, `y[2::2]=x[2::2]*h[2::2]`, `y[3::2]=x[3::2]*h[2::2]` reproduced the captured post-multiply buffer with **0 mismatched f64 elements / max error 0.0**. The *incorrect* naive `x*h` rule differs by **0.0006777608545014361** (block 0) and **0.0008636189511658111** (block 1). **CORRECTION:** Stage23S's earlier imaginary-lane oracle `x_im*h_im` does not represent the native flag-1 path.
- **Independent inverse check:** `2048 * numpy.fft.irfft(conj(unpack(captured_product)), n=4096)` differs from native output by at most **8.673617379884035e-19** (block 0) and **1.1926223897340549e-18** (block 1). This is f64 numerical parity to near machine precision, **not** bitwise equality of inverse FFT samples.
- **Two filter constructions, not one:** first coefficient snapshot has **1417** nonzero f64 entries, SHA256 `649adeb70df4bb17f73ca09c0e4bc8bd3511271fa388d989bb2094ead22b0770`; second has **1543** nonzero entries, SHA256 prefix `ccb1dcb24dc73dfa`. Both are circularly symmetric and sum to approximately `1/1024`. Both pre-FFT and post-FFT buffers match **byte-for-byte across `20261013_flag_capture_restart` and `20261013_overlap_capture`**, despite distinct runtime sessions. The 1543-tap instance should not be assigned to a specific resampler route without further call-site proof.
- **Frequency-domain check:** independent NumPy positive-sign real FFT of both real coefficient arrays matches native coefficient packing to maximum abs error **4.336808689942018e-19**; maximum imaginary bin magnitude **2.710505431213761e-19**.
- **Output-route gate remains OPEN:** the new `20261013_output_route/trace.private.jsonl` contains **9218 `emit_boundary` events** but **zero events with an `output_period`/`state+0x2c` property**. All 9218 recorded `output_shift` values are 0; this **does not** prove the `C824` direct-copy branch. The checked-in tracer has a newer `output_period` field, but the retained capture evidently predates that data being recorded. A short new native capture or static proof is still needed.
- **Early-buffer limitation:** `input_pre_fft_00` and `input_post_fft_00` in that run each contain **26 finite values with magnitude above 10^10** (maximum approximately `2.194×10^306`), unlike finite `input_packed_00`. These early named snapshots must **not** be treated as complete trustworthy real FFT input/output reference without validating capture timing and memory initialization. The correct multiplier comparison uses `input_packed` at `C56E` after repacking.

**Static RE handoff remains:** locate the Stage23I coefficient-generator divergence (actual versus candidate coefficient values), determine the output branch from `state+0x2c` at `0x18000C6FC–0x18000C861`, and validate input FFT snapshot timing before any forward-FFT native parity claim. The private archive is not committed.
