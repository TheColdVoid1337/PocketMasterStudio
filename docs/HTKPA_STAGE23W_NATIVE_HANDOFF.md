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

## Streaming and limits

Native first-block emission is zero, then 1972, then 2680 doubles. At `C689`, observed `state+0x84` starts at 3388 then 708; at `C6D2` it is 2680 then 0. `state+0x38 = 708`. `state+0x54 = 0` reaches `C759`; it does **not** alone establish direct `C824` memcpy, because `state+0x2c` controls that final choice. The tracer now records `output_period = state+0x2c`; capture it before making an output-route claim.

Stage23S lane selection, Stage23T flag lineage, Stage23U inverse sign/scale, and Stage23V block counts are native-confirmed for this run. Exact Stage23I coefficient parity, output-route period, PCM/resampler stages, gains, CLO parity, and device-output equivalence remain unproven. No production source, vendor DLL, device setting, raw audio, RAM dump, or proprietary input is committed.

## Next static targets and validation

First run `stage23i/native_fir_coefficients.py` against the SHA-pinned DLL and compare its 4096-double candidate to the native pre-FFT private buffer by f64 error, not FFT appearance. Then disassemble `0x18000C6FC–0x18000C861` around `state+0x54/+0x2c`, with the falsifiable prediction that `+0x2c <= 1` selects `C824`; use one bounded live capture only to read that field. Finally trace the native WAV decoder/resampler only after retaining this FIR conclusion.

Tracked sanitized artifacts are `research/htkpa/stages/stage23w/native_evidence.json`, `native_analysis.json`, `native_trace.py`, `analyze_native_fir.py`, and `validate_native_evidence.py`. Validate with `python research/htkpa/stages/stage23w/validate_native_evidence.py`; analysis requires an interpreter with NumPy and explicit private input/coeff/result roots.
