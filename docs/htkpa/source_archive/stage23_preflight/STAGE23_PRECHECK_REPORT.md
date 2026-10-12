# Sonicake HTKPA — Stage 23 evidence gate / preflight report

**Date:** 2026-10-12 (Asia/Bangkok).  
**Status:** `BLOCKED_SOURCE_BYTES_UNAVAILABLE` — **Stage 23 is not complete**.  
**Scope:** local source acquisition and strict test preparation; no native numerical result.

## Repo baseline checked live

`TheColdVoid1337/PocketMasterStudio` `main` =
`d1c5438a274c56f984b2d994fc018b740b799b3c`.
Comparison `f8c037776588666312e22ba1ef6c1004adda5dff…main`:
`ahead_by=6, behind_by=0`; changed files in the aggregate only the two
2026-10-12 handoff Markdown documents. `d1c5438a…` vs `main` is `identical`.
There is **no Stage 23 commit**; research/production files have not been touched.

## Source material availability in this chat

- Handoff Markdown is mounted and readable.
- GitHub Stage 21 and Stage 22 Markdown documents are retrievable and read.
- Prior original installer `Sonicake Manager.zip`, matched user capture ZIPs,
  Stage 21 and Stage 22 research ZIPs appear as `/POCKET_MASTER/` Library entries.
- Attempts to materialize the five ZIPs returned:
  `This Project file does not have an authorized raw-byte materialization path.`
- Only handoff Markdown physically exists in this conversation's `/mnt/data`.
- An official Sonicake V1.3.0 archive URL was located, but binary download failed;
  even successful download would require SHA matching before it could substitute
  for the original pinned DLL.

**Therefore:** no SHA check *against actual DLL bytes*, no independent native
instruction disassembly, no loader/PCM/resampler dataflow proof, no real input
pair reconstruction, and **no four model saturation gains** were achieved here.

## Prior research facts (from archived reports, not reverified on DLL in this session)

1. `0x1800B56B5 / 0x1800B56F2`: context float32 buffer pointers
   `+0x243E0 / +0x243E8` allocated for 70 s + 600 samples.
2. `0x1800BF890 / 0x1800BFCA0`: loader-related functions requiring direct
   analysis to prove scale, sample format, frequency conversion, and padding.
3. `0x1800BE8E7..0x1800BEA34`: in-place reference mean removal and OLS detrend.
4. `0x1800BEA59..0x1800BEAD6`: reference onset search from 6 s, at most
   600 samples, threshold `abs(y) > 0.01`.
5. `0x1800BEB2B / 0x1800BEB41`: input and aligned target at 23 s.
6. `0x1800BEDD8..0x1800BEDE4`: count of 5 s, call `0x1800BDBE0` with input and
   target; `0x1800BEE25`: **later** separate IIR helper.
7. Stage 21 has the 4-gain ordinary-domain algebra tested on synthetic signals,
   **not** actual manager pre-fit float32 buffers.

## Strict held-out references (from handoff; not re-extracted here)

| Model | pmax | nmax | prate | nrate |
|---|---:|---:|---:|---:|
| JCM800 2203 | 0.05869761 | 0.06251806 | 425.438965 | 356.188354 |
| SC20 | 0.01061691 | 0.01269747 | 450.926178 | 253.910919 |

The values above must never initialize Stage 21 and are **not results** from
this session.

## Produced and tested

`stage23_source_gate.py`: strictly verifies pinned `5868USB.dll` build,
reads archived WAV headers and fingerprints, records source-provenance and
static `objdump` windows, emits call/field index and audit `gate.json`.
Potential native sample-rate/scaling remain tagged `NOT_PROVEN`.

`test_stage23_source_gate.py`: 5 synthetic tests, all passing.
An invocation without private media writes `BLOCKED_MISSING_PINNED_DLL_BYTES`
(as expected). These tests do **not** validate any new vendor instruction.

## Required next machine-source investigation

Get authorized raw bytes of (1) `Sonicake Manager.zip`, (2) both manager
capture ZIPs, (3) Stage21 and Stage22 researcher ZIPs. Verify hashes, then
inspect the complete producer→consumer graph before selecting any resampling
or numeric scaling formula. Do NOT feed WAV PCM directly into `0x1800BDBE0`
or invoke the optimizer on a guessed native Fs. Do NOT declare numerical
parity or generate hardware CLO.

**GitHub writes:** none. **Production JS changes:** none. **Device writes:** none.
