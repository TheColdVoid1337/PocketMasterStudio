# HTKPA DLL Reverse-Engineering Research v0.1

This is **static research**, not a converter patch. Read `RESEARCH_REPORT.md` first.

Contents:
- `RESEARCH_REPORT.md`: observations grounded in 5868USB.dll machine code and matching 70s WAV captures;
- `inspect_htkpa_static.py`: read-only, deterministic PE constant/disassembly assertion tool; SHA256-pinned DLL (no DLL execution);
- `static_evidence.json`: 19 supported static-code features and exact assembly lines;
- `inspect_probe_wav.py`: region RMS/onset profiler for the captured 70s WAV pair;
- `probe_wav_regions.json`, `probe_regions.png`: independently calculated measurements;
- `summary.txt`: captured CLI output.

The original DLL and user-supplied WAV/CLo/NAM are **not** included; tests require the user's local input files. No PocketMasterStudio production JavaScript files are changed. This research is designed to lead to an independent, runtime-JS implementation, not embedding the proprietary DLL.
