# Stage99 real paired result — operator WSL, 2026-10-20

Real Dart 3.13.6/Node 24.21.0 diagnostic WaveNet compared with pinned NeuralAmpModelerCore at 48000 Hz, 8192 frames, matching stimulus, max slimmable child (1.0), prewarm off, no resampling or fitting.

| Measure | Value |
|---|---:|
| RMS error | 2.2696525484244864e-08 |
| Maximum absolute error | 1.5437486166475223e-07 |
| Normalized RMS error | 2.733829451264937e-07 |
| Mean error | 8.696689549054408e-10 |
| Core RMS | 0.08302099998865412 |
| SonicMaster RMS | 0.08302100185762351 |
| Largest error index (zero-based) | 5393 |
| Bitwise equal | false |

Input SHA-256: `f54ab8b3d61cd8d36fafa316f6542f18ede669febd88901b7c974b299de7745e`. Core binary SHA-256: `ddcb3880286b7457896032309930d1385c4391c93dde3188d991f77beae07dad`. Diagnostic worker SHA-256: `a72b0abead39288f60c1ab4723d7b2c5b0f4e5e6e4a8b221e2cf60e9be04c0f7`.

Evidence is the operator-provided console output, NOT independently retrieved audio samples. For this one test the engines are numerically very close but not bitwise equal. Original Sonicake DLL parity, full NAM-to-CLO fitter, and hardware outputs are NOT verified. Raw outputs and private model identities remain outside public GitHub.
