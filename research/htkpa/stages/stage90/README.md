# Stage90 — authenticate the Stage89 same-run chain and identify its WAV caller

**Status:** `NATIVE_STAGE89_D786_CALLSITE_AND_SAME_RUN_PARENT_CHILD_CHAIN_VERIFIED`.

The user-operated Stage89 Frida capture has arrived. A read-only offline
auditor now checks its module identity, installed hooks, ASLR-adjusted return
address, original `E8 rel32` call bytes, single-thread event chronology, and
actual parent/child pointer joins. This is **a verified new-run call chain**,
not proof that the historical Stage64 events used the same parent or branch.

## New native provenance

| Stage89 observed edge | Cross-check | Result |
|---|---|---|
| `0xCE00` caller | Return address minus runtime ASLR base minus 5-byte call instruction; original `.text` `E8 rel32` and Stage88 `.pdata` owner | Callsite **`0xD786`**, owner **`0xD4A0`** |
| `0xCE00` → `0xD018` | Identical group-input object within one capture | Verified 1 join |
| `0xD018` → `0x118FD` | Parent constructed and later observed as dispatcher receiver | Verified 2 joins |
| `0x118FD` → `0x135C0` | Child selected by parent equals child receiver `RCX` in two downstream entries | Verified 2 joins |

The trace contains **4/4 attached hooks**, **6 native hits** on one thread
within **287 ms**, and **0 Frida hook exceptions**. The original DLL is pinned
by SHA256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`.
Raw runtime pointers and the complete event journal remain private.

## Significant Ghidra refinement: this caller handles WAV input

Independent Ghidra Headless reanalysis decompiled the complete original
function starting at `0xD4A0` (not just the group constructor). In the
decompiler output, `0xD4A0` constructs a `juce::WavAudioFormat` reader,
checks the input path through Windows file attributes, obtains an audio
reader, and subsequently invokes `0xCE00` at `0xD786`. Its source-rate
argument comes from the reader-associated floating-point field `+0x8`;
its target-rate argument is supplied to the caller. Stage88 previously
verified the latter two registers at the actual assembly callsite.

This is **strong static evidence for a WAV-file import/resampling path**.
Since Stage89 proves it was the executed caller, the trace is not by itself
evidence that a NAM model's internal values were resampled. The operator
reports that a NAM import was attempted, but the trace does not record
the relevant opened WAV path, NAM filename/hash, or wider call stack. The
Ghidra-derived types and dataflow are subject to decompiler limitations.

This is also consistent at an *architectural* level with public
[r8brain `CDSPResampler.h`](https://github.com/avaneev/r8brain-free-src/blob/master/CDSPResampler.h),
[`CDSPProcessor.h`](https://github.com/avaneev/r8brain-free-src/blob/master/CDSPProcessor.h)
and [`CDSPFracInterpolator.h`](https://github.com/avaneev/r8brain-free-src/blob/master/CDSPFracInterpolator.h):
resampler processor chains invoke virtual processing and may contain
a fractional interpolator. These are **current public-family references**,
not a proven exact vendor source revision, ABI or numerical-parity claim.

## Limits and Manager crash

- Reading `XMM1` and `XMM2` failed in the Frida field-capture helper.
  Consequently Stage89 **did not measure source or target sample rates**.
  The manifest reports 2 field errors but 0 hook exceptions; the
  observed XMM conversion errors do not establish why Manager crashed.
- The user reported Sonicake Manager crashed while importing NAM; the
  capture manifest says `OPERATOR_INTERRUPTED` (Ctrl+C), not a recorded
  Windows exception. `completion_verified=false` and **no successful CLO
  export was established**. Standard WER file and Application 1000/1001
  searches returned no relevant crash record. **Cause remains unknown.**
- The operator consistently identifies the attempted NAM as
  `JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`, but the runtime event file
  does not encode a source NAM identity.
- The captured raw `R8` register fields are not semantically interpreted;
  an observed register value is not automatically a sample count.
- New-run pointer joins cannot retroactively identify the historical
  Stage64 object, selector, route, actual data or rate pair.

## Offline reproducibility

Private original inputs are held in the dedicated
[RE_HTKPA Drive folder](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK).
The public tool emits only a sanitized JSON conclusion. It does not run
the Windows DLL or attach to any process:

```bash
python research/htkpa/stages/stage90/audit_stage89_runtime_chain.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --capture research/_LOCAL_FILES/frida_captures/frida_20261016_181158_278441_bmdlbv64.tar.gz \
  --out research/_LOCAL_FILES/stage90_runtime_chain_private_report.json

python -m unittest discover -s tools -p 'test_htkpa_stage90.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q
```

Observed: **22/22 new synthetic/mutation tests**, **243/243 Stage70–90
tests**, and a successful original-file Stage90 audit. The private
Ghidra source report is retained outside GitHub.

**Next gate:** map the static upstream callers of the WAV-capable
`0xD4A0` and distinguish entry-path ownership, while keeping exact
runtime file provenance **unproven**. If a fresh trace becomes necessary,
request a new narrowly scoped Frida capture from the operator rather than
guessing; do not repeat the crashing import without first considering
the missing Windows crash diagnostics.
