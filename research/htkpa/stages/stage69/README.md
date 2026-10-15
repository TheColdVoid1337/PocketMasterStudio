# Stage69 — original DLL FIR-before-fractional topology (offline)

**Scope:** original Sonicake Manager 1.5.2 PE64 \`5868USB.dll\` SHA256
\`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa\`,
plus the independently confirmed Stage64 original runtime metadata archive SHA256
\`aa32d8440b532708ce3551404f5a4292791abd31aba197003e850f61f22683ff\`.
No original DLL execution, Frida attachment, new NAM→CLO run or audio-byte extraction.

## Findings — distinguish SOURCE and NATIVE

**SOURCE (verified in private original PE by LLVM objdump):**

- Constructor at RVA \`0x11b60\`: source rate passed in XMM1 → XMM8;
  destination in XMM2 → XMM9.
- Branch condition RVA \`0x11c62..0x11c6c\` tests \`2*destination <= source\`.
  In the alternative path, native code constructs an intermediate
  \`CDSPBlockConvolver\` at \`0x11cfe\` with ratio **2:1** (R8D=2, R9D=1),
  stores it at \`resampler+0x8\` and sets count at \`+0x48=1\`.
- When \`destination<=source\`, the filter generator receives
  \`NormFreq = 0.5*destination/source\`, computed at RVAs
  \`0x11c90..0x11c99\` and passed to filter generation at \`0x11ce3\`.
  Native constant at RVA \`0x24c880\` is **0.5 (double)**.
  For *candidate* **48,000→44,100**, \`NormFreq = 0.459375\`, equivalent
  to 22,050 Hz when multiplied by source rate 48,000 Hz. This frequency
  normalization suggests a pre-fractional low-pass designed for the output
  Nyquist boundary; neither actual measured attenuation nor an identified
  live parent is implied by these instructions.
- Conditional \`2*source > destination\` at \`0x11d6e..0x11d7c\` leads
  via \`0x11f04/0x11f1f\` to final fractional constructor at \`0x12170\`.
  Fractional vftable RVA \`0x245170\` installed at \`0x121ae\`, final
  processor stored at \`resampler+0x50\` at \`0x1222a\`.
- Wrapper \`CDSPResampler24::process\` calls intermediate processor at
  \`0x118b1\` and final processor at \`0x11909\` in that order.
- Two *potential* high-level calls explicitly target float32 constant
  **44,100.0 Hz** at native RVA \`0x24cdf0\`: callsite \`0xe28f1\`
  (source rate audio object \`[r14+0x8]\`) and \`0xbf364\`
  (source rate context \`[r14+0x20ec0]\`). Which, if either, produced
  the Stage64 reverse calls is **not yet established**.

**NATIVE (private Stage64 original capture; event metadata only):**

- 21 fractional calls during successful conversion/8840-byte CLO:
  #1–4 internal **88,200→48,000**; #5–21 internal **96,000→44,100**.
- First processor memory address occurs in calls #1–2, second occurs
  #3–21, **including two different rate configurations**. A reused memory
  address is *not* evidence that one live object changes mode or that the
  operations have the same upstream parent. Allocator reuse/reinitialization
  cannot be disambiguated from these observations.
- Previous Stage64 captured 1067 first forward f64 and 114 reverse f64;
  Stage65/66 established near-f64-precision standalone reproductions.
  Stage69 **does not** read or recapture those f64 payloads.

**Derived architectural hypothesis:**
A full native **48,000→44,100** conversion can naturally construct
**48k → 96k via a 2:1 lowpass FIR**, followed by the observed **96k → 44.1k**
fractional last stage. This explains why testing the *fractional-only*
reverse primitive at 25/30/35 kHz yielded large aliased outputs even though
the complete vendor resampling path **may filter those inputs before the
fractional stage**. Native runtime linkage and full-signal anti-alias
performance are **NOT_PROVEN**; do not modify or rename the verified
standalone primitive to imply it already includes a prefilter.

## Reproduce in WSL

Run offline tests first:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python -m unittest discover -s tools -p 'test_htkpa_stage69.py' -v
```

Then the actual original-DLL disassembly and Stage64 metadata audit:

```bash
python research/htkpa/stages/stage69/audit_topology.py \
  --dll "/mnt/c/Program Files/Sonicake/Sonicake Manager/assets/5868USB.dll" \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --out research/_LOCAL_FILES/stage69_fir_topology.json
```

Requires LLVM \`llvm-objdump\` on WSL; the script fails closed if the
original DLL, Stage64 archive, or exact instruction anchors differ. Only
sanitized metadata is printed and written to the ignored location. The
private original DLL and private Stage64 .tar.gz must NOT be committed.

## Acceptance / next gate

Stage69 acceptance means the source-constructor's **conditional
FIR(×2) → fractional** path and two original 44.1-kHz target callsites
are mechanically anchored, and the Stage64 chronological sample-rate
observations have been independently rechecked. It does **not** establish
that the specific Stage64 reverse object was called by that constructor.

A future *separate* Stage70 could trace one high-level callsite to its
parent resampler construction (statical xrefs first), before considering
any strictly SHA-guarded **single-hook metadata-only** parent provenance
probe. No new Frida run is necessary for Stage69.
