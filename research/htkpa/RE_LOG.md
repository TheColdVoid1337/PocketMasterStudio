# HTKPA — RE cycle log (append-only)

**Purpose:** tiny, durable handoff after **every** reverse-engineering work cycle. This is **not** a replacement for [the current full status](../../docs/NAM_CLO_HTKPA_RESEARCH_STATUS_2026-10-13.md), stage code/evidence or occasional DOC-SYNC. Read the **last entry first** on resumption; preserve earlier entries unless a correction is explicitly noted.

**Original target:** Windows `5868USB.dll`, SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`. Source-first static RE. **No native DLL/RAM or end-to-end NAM→CLO parity** is implied by individual unit-test passes.

## Minimal per-cycle contract

After **each** research cycle, including one with a negative result, append **one entry (5–9 compact lines)** to this file **in the same checkpoint commit where feasible**. Keep new research time for disassembly, not prose. Record:

1. **When / stage / result:** date, cycle label and whether the hypothesis succeeded, failed or remains open.
2. **Proof:** exact DLL address/range; what instructions establish; distinguish **SOURCE**, **DERIVED**, **SYNTHETIC**, **NATIVE** (only if genuinely measured).
3. **Verification:** runnable repo-relative script/test, measured outcome or precise failure and its environment.
4. **Unresolved / blockers:** do not hide assumptions or interpret synthetic tests as vendor parity.
5. **Next:** one exact code range and question; relevant SHA/commit/file paths when available.

Avoid re-reporting old stages, lengthy tutorials, version-per-paragraph files, repeated full source listings and new production code. If an earlier conclusion is overturned, append an explicit **CORRECTION** and point to the affected entry rather than silently rewriting history. During the next deliberate DOC-SYNC, integrate durable facts into the long status and keep this log as the chronological trail.

## 2026-10-13 — Stage23O · initial baseline (from committed Stage23O evidence)

- **Result:** **SOURCE/SYNTHETIC** checkpoint for representative specialized radix-4 FFT butterfly paths in `0x18000A850`; 3 branches corresponding to rotations `π/4`, `π/8`, `3π/8`.
- **Proof:** source pins inside `0x18000AA10–0x18000AF09`; scalar SSE paths and sign-bit `xorps` are modeled separately. **Not** the arbitrary-index higher-stage twiddle loop.
- **Verification:** `research/htkpa/stages/stage23o/fft_radix4_special_source.py --dll <original-dll>`; prior research reports 28 address pins, 178 scalar SSE operations across the 3 branches and 3096 independent synthetic cases, max error about `4.58e-15`. No original DLL execution or RAM-output comparison.
- **Saved:** source [Stage23O](stages/stage23o/fft_radix4_special_source.py); research commit [`c62063d`](https://github.com/TheColdVoid1337/PocketMasterStudio/commit/c62063dd6ce3d2c98e0d6199137376dcdb737620). Earlier general base blocks: [Stage23N](stages/stage23n/fft_general_blocks_source.py).
- **OPEN:** arbitrary twiddle-index stage loops, full 4096-double FFT, native spectrum, FIR streaming overlap and sample alignment, actual two-model fitted audio/gains.
- **NEXT — Stage23P:** disassemble and source-model the general loop `0x18000AB50–0x18000AF17` for arbitrary twiddle indices and real call strides `8,32,128,512`; integrate with 23M/N/O, locate first whole-FFT mismatch before claiming parity.
