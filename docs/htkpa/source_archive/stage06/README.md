# Sonicake HTKPA RE Stage 6 — minimum-phase evidence

This ZIP is a reproducible, read-only research handoff (except for an **explicit opt-in** offline experimental-CLO generator); it does not contain the proprietary Sonicake DLL, original reference WAV, source NAM or official CLOs.

**New finding:** two real Windows Sonicake Manager Post-FIR vectors have coefficient cosines >0.9985 when reconstructed from their magnitude-only FFT via a minimum-phase real cepstrum. Sonicake's DLL also uses complex `expf/cosf/sinf` synthesis after logarithmic spectral transforms. This does **not** fully recover its Post-FIR design from the NAM or prove bit-equivalent output.

Install research Python dependencies: `python -m pip install numpy scipy matplotlib`.

Run self-tests: `python -m unittest -v test_minimum_phase.py`.

To validate against your **own, locally available** matching inputs, run `python verify_stage6.py --help` and supply the six CLO paths and original pinned DLL. The DLL is only disassembled via `objdump`, never loaded or executed.

The packaged **UNVALIDATED** JCM800 candidate is an experimental phase-only edit to the previously user-favored v0.2 C. It keeps the first 512 Post-FIR tap magnitude response nearly identical, but changes the phase and time-domain waveform. It has **not** been accepted on pedal. Original v0.2 C is retained externally; no automatic production change.

Report: `RESEARCH_REPORT.md`; machine-readable proof: `evidence.json`.
