# HTKPA source-first Stage 16

Independent read-only reverse engineering of the user's Windows Sonicake Manager DLL. **No vendor source/binary included; nothing is executed in the DLL.**

Verifies scratch workspace topology in `0x1800BB210`, exact regularized feedback operands and in-place destination, fit stages, save/reject control and joint FIR backups.

## Re-run on your local copy

```bash
python verify_stage16.py --dll /path/to/5868USB.dll --out evidence_reproduced.json
```

Requires Python, NumPy, GNU objdump. Pinned SHA-256 of the DLL protects against inaccurate disassembly mapping.

The full technical report is `RESEARCH_REPORT.md`. No new CLOs and no hardware actions. Actual DLL execution, exact FIR parity and SONICLINK equivalence are **not** claimed.
