# Stage108 — candidate fixed 0.31 output gain and PCM16 encoding vs Manager

**Status:** `STAGE108_OFFLINE_PCM16_CANDIDATE_TESTED_OPERATOR_PENDING`.

This is a **read-only DSP-output diagnostic**, not proprietary NAM/fitter parity.
Stage107 real operator proved **140,000 vendor samples in seven 20k-frame zero-DI bins are all PCM16 +2**, whereas the open NAM Core f64 output on each bin has mean `0.00020439285435713828`. A fixed 0.31 multiplier makes these values compatible with PCM16 rounding to +2. Subsequent 2026-10-21 operator testing also showed every one of the **3,087,000** float32 samples in the original 44.1-kHz public DI equals `original Stage97 vendor PCM16 / 32768` numerically. See `../stage107/OPERATOR_INPUT_FLOAT32_PCM16_IDENTITY_20261021.md`; **source input quantization is not the cause of the Stage105 early residual**. Vendor 44.1→48-kHz resampler and loaded model byte identity remain unknown.

## Purpose

Compare the **first 1.6M frames** of the original SHA-pinned Stage97 Manager outputFile.wav (48 kHz, stereo identical PCM16) to the existing **SHA-pinned open upstream NeuralAmpModelerCore C++ f64 output**, without rerunning either. Do *not* tune gain to each audio window or change source signal.

Explicit candidate encodings:

1. Fixed `gain=0.31` then signed int16 scaling (`×32768`), clipping and **round-to-nearest-even** (Python `round`). This is the primary falsifiable hypothesis.
2. Same fixed gain, **round-to-nearest-away-from-zero** (ties explicit), and **truncation toward zero**. These are controls, not presumed Manager settings.
3. Global diagnostic `gain=0.3098390026147448` derived previously by Stage103 from Manager WAV on [300k,1.5M) (i.e. **it is fitted to the very target** and must NOT be confused with an independently specified implementation). Try the same three quantizers for visibility only.

Each candidate is measured as exact PCM16 sample matches, within-one-LSB matches, integer RMS/mean/max absolute difference, and candidate clipping counts. Both sample counts and per-bin results are preserved privately for full 1.6M, fitter [300k,1.5M), four quiet-active-dominated bins [300k,1.1M), two louder bins [1.1M,1.5M), startup [0,300k), tail [1.5M,1.6M), all six individual 200k bins, and exactly the seven zero-DI 20k bins established by Stage107.

## Source and privacy gates

- Requires original ignored Stage102 `comparison_private.json`, original Stage103 `stage103_gain_audit_private.json`, and Stage107 `stage107_silence_floor_private.json`, with exact known statuses, lengths and original Stage103 global gain.
- Rehashes original Stage102 prewarm-OFF C++ f64 output against the original private Stage102 manifest; verifies original vendor ZIP SHA, exact allowlisted files, 48k 70s stereo identical PCM16 through Stage102's `authentic_wavs`. Input DI/Stage101 equality is separately documented and is not re-run.
- Reads existing f64 and Manager WAV **without modifying** them. Stores only `stage108_fixed_gain_pcm16_private.json` in existing ignored Stage102 folder; refuses overwrite. Does not put original ZIP/WAV/NAM/f64, private model hash or raw samples into GitHub.
- No inference, resampling, DLL, Manager, Frida, closed fitter, USB or device action; no production changes. A close output match would be circumstantial evidence of candidate gain/quantizer, **not** proof that native Manager uses that exact formula or internal buffers.

## Operator WSL

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python3 -m unittest discover -s tools -p 'test_htkpa_stage108.py' -q
python3 research/htkpa/stages/stage108/GO.py \
  --stage102-report 'research/_LOCAL_FILES/stage102/29abbdbf982ee64b_stage102_open_sonicmaster_di_resample_v1/comparison_private.json' \
  --stage97-zip 'research/_LOCAL_FILES/CLO_10-19-26-0253.zip'
```

**16/16 synthetic/fixture tests passed in the assistant's isolated environment before publication**, including a synthetic miniature end-to-end run, exact quantization tie/bounds behavior and fail-closed overwrite. Actual results are **PENDING** until operator execution. No identical vendor NAM processing or output quantization has yet been established.

## Interpretation gate

If fixed 0.31 plus nearest PCM16 matches all or most louder samples but not early quiet nonzero DI, investigate **vendor resampling, model input conditioning or residual signal processing** rather than silently applying additional window-dependent gain. If exact matches are weak on both regimes, don't claim fixed gain reproduces vendor output. Compare rounding variants to detect evidence of a quantization convention; beware that empirical best matching on this single recording is not causal identification.
