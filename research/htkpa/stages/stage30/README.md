# Stage30 — runnable public r8brain harness

This stage builds a **separate C++ executable** from public MIT r8brain-free-src at upstream commit `cb2abb9977efe2471979b380ed95daa56ab4fdb9` (committed 2026-09-30). It does not load the Sonicake DLL. Upstream source stays in ignored local `research/_LOCAL_FILES/r8brain_src/`; no original proprietary data is committed.

From project root in WSL:

```bash
bash research/htkpa/stages/stage30/build_and_test.sh
```

Requirements: `git`, `c++` with C++17, `python3`; network access to GitHub on the first checkout. The script checks upstream exact HEAD, compiles `r8b_probe.cpp`, then checks synthetic 44.1→48k chunk invariance at 256/1024/4096/16000 input samples. **This has not yet been tested in the user's WSL**.

Binary:

```bash
research/_LOCAL_FILES/r8brain_stage30/r8b_probe input.f64le output.f64le 1024 2 44100 48000
```

Input/output are little-endian **64-bit doubles**, mono. The JSON console record includes sample counts, chunk count, latency, rates and transition band. The output is **not** post-processed to PCM24 or WAV. Initial latency is deliberately not trimmed, and no zero-flush is appended, so comparison with official intermediate WAV needs carefully matched boundaries.

**Critical scientific scope:** success of this synthetic test establishes only standalone r8brain consistency, not the vendor DLL version, its exact resampler invocation, or 44.1→48 native signal parity. Next native capture must collect a contiguous same-call input/output span and total sample counts, allowing byte/float-level comparison with this harness. Commit pin is a reproducibility fixture, *not* the Sonicake version attribution.

Attribution when integrating upstream code: r8brain-free-src, Copyright © 2013–2026 Aleksey Vaneev, MIT license; include the full upstream LICENSE and credit “Sample rate converter designed by Aleksey Vaneev of Voxengo”.
