# HTKPA reverse-engineering Stage 4 — FIR output/packing path

This is a **read-only** research checkpoint, not a Windows DLL wrapper, not a production NAM-to-CLO converter and **not** a successful independent reconstruction of official FIR coefficients.

- `RESEARCH_REPORT.md` — verified data-flow map and unresolved coefficient-fitting details.
- `verify_stage4.py` — static instruction/DLL hash and four-CLO cross-check; requires only Python3 + GNU `objdump`.
- `static_validation.json` — expected output of the verifier for the two user-provided matching NAM cases. Includes hashes and numerical comparisons but **no proprietary code or audio**.

Findings: final context Pre/Post FIR arrays → resampling to 44,100 Hz → zero-fill 128/2048 tap slots → CRC VTSI. For a 48,000 Hz source, 128→117 and 2048→1881 nonzero values are observed on **both vendor and Void** profiles. Hence this output resampling is not the reason for the timbral difference. Missing equations are upstream in the joint optimizer/spectral reconstruction.

No commercial DLL, NAM, WAV or CLO is included in this research package.
