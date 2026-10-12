# Stage 7 — Independent NAM → experimental Post-FIR (research)

An original Python spectral estimator using your existing **Void Mod baseline CLO** for the upstream Pre-FIR/nonlinearity and independently predicted WaveNet output from the NAM. It is **not** a new approved converter or a copy of Sonicake HTKPA; it regresses on SC20 and must **not** become a production default. The default action only writes a diagnostic JSON report and does not create a CLO.

## Requirements

Python >=3.10, `numpy`, `scipy`; optional `matplotlib` only for the separately supplied graphs. The reference is stereo identical L/R 16-bit WAV at 44.1/48kHz. The NAM-output NPZ has a 70-second float32 `audio` array (44.1 kHz), a boolean `valid` mask and samples from an **independent WaveNet inference** at ten 2-second regions. The independent NAM WaveNet inference generator was developed in the earlier v0.1 research lab and is **not bundled here**; Stage 7 requires those predictions as input. **You cannot run Stage 7 from just an arbitrary NAM file yet**.

```bash
python -m unittest discover -s . -p 'test_*.py' -v
python spectral_lab.py \
  --reference-wav /path/to/nam_input_wav.wav \
  --independent-nam-output-npz /path/to/synthetic_target.npz \
  --baseline-clo /path/to/VoidMod_Baseline.clo \
  --out-dir /path/to/stage7_results
```

Optional **only for a deliberate local research experiment**: append `--write-experimental-clo`. It will write a clearly named candidate into `--out-dir` and **never writes anything to a connected pedal**. Do not test on device unless preserving existing working slots and controlling monitor volume.

In the supplied JCM800 2203 benchmark the method improves absolute heldout waveform correlation **0.74867 → 0.82262**, but our already hardware-favored v0.2 C reaches **0.88947**. On SC20 the same method **regresses 0.65815 → 0.52652**. **No new experimental CLO is recommended.**

Read `RESEARCH_REPORT.md` for full limitations, numerical evaluation, training/test windows and source vs evaluation boundaries.
