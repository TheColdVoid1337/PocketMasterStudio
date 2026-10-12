# HTKPA static reverse-engineering — Stage 2

Reproducible, read-only x64 static analysis of the user-provided `5868USB.dll` that identifies the saturator mathematical function, the function which fits its four gains, sample-rate-specific coefficient banks, a recursive filtering subroutine, and the three-way processing selector order.

Contents:
- `RESEARCH_REPORT.md`: detailed findings with addresses, direct evidence, hypotheses and limitations.
- `verify_stage2.py`: pinned SHA-256, PE raw-data reading, disassembly checks and import verification. No executable loading or device actions.
- `evidence_direct.json`: 30+ concrete assembly checks and interpreted values.
- `saturator_control_pairs.json`: data extracted from two paired official and Void `.clo` files, no proprietary bytes included.

Run:

```bash
python verify_stage2.py /path/to/5868USB.dll --out my_evidence.json
```

Result must report 30 verified machine-code instructions, expf resolved and 44.1/48/96 kHz rate branches. Do not generalize addresses to other versions of the DLL.

**Security and engineering boundaries:** zero Windows execution, zero write/overwrite of hardware profiles, zero modification of shipping Void Mod conversion. The original proprietary DLL and WAV captures are not included.
