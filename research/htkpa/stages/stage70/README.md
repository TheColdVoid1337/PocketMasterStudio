# Stage70 — SHA-gated source call-graph trace for the 44.1-kHz native path

**Status:** local original-DLL execution of this *read-only audit* is pending.
Stage69 was independently accepted in user WSL on 2026-10-15: five offline
regressions passed, and 34/34 LLVM instruction anchors and the original
Stage64 metadata matched the exact SHA-pinned artifacts.

## Narrow question

Two native high-level callsites, RVA `0xE28F1` and `0xBF364`, each pass
destination **44,100 Hz** to a shared helper at RVA `0xCE00`. The original
`CDSPResampler24` constructor starts at RVA `0x11B60` and has a conditional
FIR(2:1) → fractional processing structure (Stage69). Can we trace a **direct
compiled call path** from the shared helper to that constructor?

Stage70 uses the original V1.5.2 DLL only as static PE64 data, reads its
exception `.pdata` directory to establish bounded function ownership,
reconfirms both callsite targets, and uses LLVM objdump's Intel output to
follow **direct call instructions** from the shared helper for at most four
levels and 64 distinct functions. It **does not** resolve indirect calls,
jump edges, virtual dispatch, function pointers, or data-dependent branches.

Even a positive direct-call path proves only source-level reachability.
It does **not** prove which parent created the Stage64 observed 96k→44.1k
fractional processor, that the live original input was 48 kHz, or the
complete vendor filter's actual stopband attenuation. A negative or
search-budget-exhausted result is not evidence that such a relationship is
absent from the original program.

## Reproduce in WSL

Already-required inputs (all PRIVATE and ignored by Git):

- Original installed DLL SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
- The independently produced, accepted Stage69 local JSON
  `research/_LOCAL_FILES/stage69_fir_topology.json`.

No Frida, new native conversion, new WAV, F64 access, or new dependency beyond
the `llvm-objdump` that already passed Stage69 (user has Ubuntu LLVM 21.1.8).

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python -m unittest discover -s tools -p 'test_htkpa_stage70.py' -v
python research/htkpa/stages/stage70/audit_parent_calls.py \
  --dll "/mnt/c/Program Files/Sonicake/Sonicake Manager/assets/5868USB.dll" \
  --stage69 research/_LOCAL_FILES/stage69_fir_topology.json \
  --out research/_LOCAL_FILES/stage70_parent_calls.json
```

The JSON report stores RVAs, code-graph edges, source SHA/provenance and
explicit uncertainty flags, **never original machine-code bytes**. Do not
commit DLLs, stage64 archives, disassembly transcripts, captured audio or
the local JSON report. Paste the console output for the next review.

## Acceptance

- Both fixed callsites must still resolve to `0xCE00` in the exact DLL.
- Both callsite owners, `0xCE00` and `0x11B60` must map uniquely to real
  `.pdata` function entries. SHA/provenance mismatches fail closed.
- The report must say one of:
  - `STATIC_DIRECT_CALL_PATH_FOUND_RUNTIME_PARENT_UNPROVEN`, or
  - `BOUNDED_STATIC_DIRECT_CALL_PATH_NOT_FOUND_RUNTIME_PARENT_UNPROVEN`.
- In either case, runtime parent provenance remains **UNPROVEN**.
- If the graph does not connect, inspect the bounded edges and indirect-call
  count before deciding whether a different static analysis is required.
  Do not start a dynamic hook automatically.

Production converter, standalone Resampler Lab and Stage66 native-compat
bridge remain unchanged.
