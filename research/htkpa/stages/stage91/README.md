# Stage91 — enumerate the NAM/WAV upstream paths to the Stage89 native worker

**Status:** `STATIC_NAM_WAV_ENTRY_FAMILIES_AND_EXPORTED_WRAPPER_VERIFIED_STAGE89_UPSTREAM_UNBOUND`.

Stage90 tied the **observed Stage89** call to `0xCE00` to original PE callsite
`0xD786`, inside a WAV-reading/resampling function starting at `0xD4A0`.
Stage91 answers the next *static* question: **who can call `0xD4A0`?**

## Result: four complete direct-call routes

Independent original-PE disassembly, `.pdata` ownership, exact `E8 rel32`
bytes, diagnostic string references, rate literals and private Ghidra
Headless decompilation corroborate the following routes. Addresses are
**original PE RVAs**, not runtime ASLR addresses.

| Direct callsite → `0xD4A0` | Owning function | Static route / rate argument |
|---|---|---|
| `0xEB1E` | `0xE0E0` | NAM-associated output/preprocessing worker. Contains `getNamOutput` and NAM-file diagnostics; conditional input-WAV conversion toward NAM sample rate. |
| `0x100EB` | `0xFF40` | Calls NAM worker `0xE0E0` at `0x10043`; tests the worker's result against `-2.0`; guarded WAV call uses the **literal `44100.0` Hz**. |
| `0x11021` | `0x10E70` | Calls NAM worker `0xE0E0` at `0x10F7F`; tests the same sentinel; guarded WAV call uses the **converted return value** of the NAM worker as its rate argument. |
| `0xAD5E9` | `0xAD5D0` | Independently exported wrapper **`getAppNormalWav`**, ordinal **19**; forwards the external rate argument. |

The call graph therefore contains a concrete **NAM-import-associated WAV
preprocessing route**. This materially refines Stage90: encountering a
WAV resampler *during an attempted NAM import* is consistent with the
compiled native implementation, without implying that a NAM model's
internal weights or values were resampled.

The static edge `0xE0E0 → 0xD4A0` is one of four possible direct routes.
**Stage89 only measured the downstream `0xD4A0 → 0xCE00` edge.** The
Stage89 trace did not capture an outside caller of `0xD4A0`, a full call
stack, opened WAV filename, or source/target frequencies. Therefore **which
of these four branches was actually active in Stage89 remains unbound**.
The `getNamOutput` log label describes the native operation; it is not
proof of a successful NAM-to-CLO export.

## Independent checks and limits

The offline auditor `audit_upstream_wav_callers.py` verifies on the original
SHA256-pinned `5868USB.dll`:

- exactly **4 decoded direct calls** into `0xD4A0`, plus **2 decoded direct
  calls** into `0xE0E0` across `.text`;
- each of those **6 callsite bytes** is independently verified as `E8 rel32`,
  along with the prior Stage89 `0xD786 → 0xCE00` edge (**7 exact calls**);
- original `.pdata` owners and **40 exact assembly instruction anchors**;
- five relevant original NAM/WAV diagnostic literals, original `44100.0`
  double/float constants, and the original `-2.0` double sentinel;
- the PE export table's `getAppNormalWav` name, ordinal **19**, and
  original entry RVA `0xAD5D0`.

Ghidra is used to corroborate function intent and higher-level branch
structure, but no decompiler output, vendor DLL, NAM model, raw Frida
capture, or run-specific pointers are uploaded to public GitHub.
The full Ghidra decompilation and original-file audit output are private,
not public GitHub assets. As checked on 2026-10-17, the canonical
[RE_HTKPA](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK)
contains the Stage90 critical checkpoint and historical Ghidra audits, but
no separately named Stage91 checkpoint/report had been uploaded there.

### Deliberately unproven

- The **runtime** caller above `0xD4A0` in Stage89, and any attempt to
  connect this exact outer route to the historical Stage64 trace.
- The opened source WAV's pathname and sampled rate; Frida's two `XMM`
  field-read errors mean the Stage89 rate pair was **not obtained**.
- NAM-file hash in the capture. The operator attests the same
  `JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam` was used for all their
  Frida NAM imports; that identity is **not encoded in the trace**.
- Successful NAM-to-CLO conversion, numerical resampling parity, or why
  the Windows Sonicake Manager crashed. The earlier WER/Event 1000/1001
  queries did not establish an exception cause.

## Reproduction, Bash/WSL

Run locally with the private original DLL; **no vendor binary execution or
live instrumentation** is performed:

```bash
python research/htkpa/stages/stage91/audit_upstream_wav_callers.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage91_upstream_wav_route_private_report.json

python -m unittest discover -s tools -p 'test_htkpa_stage91.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q
```

Observed: **25/25 Stage91 synthetic/mutation tests**, **268/268 accumulated
Stage70–91 tests**, and a successful real-file Stage91 audit. No new
Frida run was requested or performed in this stage.

**Next gate:** inspect static upstream ownership/guard logic and the
precise requirements for capturing the *outer* caller if dynamic proof
becomes essential. Ask the operator for a narrowly scoped WSL Frida
capture **before** claiming actual Stage89 branch provenance; do not
silently substitute static reachability for runtime evidence.
