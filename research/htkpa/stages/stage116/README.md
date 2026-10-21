# Stage116 — one-site, register-only Frida capture preparation at `0xF231`

**Current status: `STAGE116_STATIC_PINNED_ONE_SITE_METADATA_PROBE_READY_RUNTIME_PENDING`.** Real original 2,902,016-byte SHA-verified `5868USB.dll` audited offline in the assistant environment on 2026-10-21 (Bangkok). The Stage115 static anchor/owner gate passed again; **20/20 new synthetic Stage116 tests PASS; 37/37 Stage115+116 PASS**. **NO Windows Manager invocation, native Frida capture, NAM import or new audio measurement occurred in Stage116.**

## One narrow question

Does the actual original Manager execute the SHA-anchored **call *instruction*** RVA `0xF231` during a user-initiated NAM→CLO operation, and, if so, what *bounded register-only metadata* is present at that point?

Stage115 established that the compiler loads a model-associated object into `RCX`, sets `RDX` and `R8` to addresses of local input/output pointer slots, sets `R9D` to a chunk element count with static maximum **1024**, and executes `call qword ptr [rax+0x10]`. These are **static instructions**, not proof of execution or actual model/48-kHz input identity. At `0xF231` the hook sees the registers **before** the indirect call, not the target function's `onEnter` or post-call return. **No assertion is made that these arguments are valid/readable audio buffers.**

## Implementation (existing universal runner, no shared runtime modifications)

`frida.json` uses the existing `tools/frida_capture.py` **legacy scalar** mode (mode field intentionally absent). Exactly one site is declared: `nam_candidate_f231_call` at RVA `0xF231`; `max_hits=8`. Exactly four validated direct register reads:

| Field | Existing Frida type | Register | Scope |
|---|---|---|---|
| `object_register` | `reg_ptr` | `RCX` | Value of model-associated object pointer; not dereferenced |
| `input_slot_address` | `reg_ptr` | `RDX` | Address of a local slot; **not input audio bytes** |
| `output_slot_address` | `reg_ptr` | `R8` | Address of a local slot; **not output audio bytes** |
| `candidate_chunk_count` | `reg_u64` | `R9` | Register value; interpreted as `R9D` chunk elements (1..1024 required by postrun auditor) |

Only pointer *values* and integer register values are recorded. No `ptr`, `f32`, `f64`, `f64_binary`, `f64_slice`, `f64_block`, `xmm`, model-object dereference, memory read, buffer payload, code modification or unbounded trace is requested. Note the universal **legacy** agent contains general-purpose memory-reading branches for other configurations; the **exact reviewed Stage116 configuration** selects only the direct-register branches. Do not call this the stricter `guarded_metadata` mode: its processor/vtable guard targets a different site and is not transferable to `0xF231`.

The legacy runner verifies the **on-disk** original DLL SHA before capture (when `--module-file` is supplied), but loaded-module SHA is recorded and verified **after** instrumentation in this mode. Stage116's postrun `GO.py audit` rejects any wrong/absent runtime SHA, missing hook, field errors, unexpected extra members, binary sidecar, sample-data claims, wrong PC/ASLR, null/unaligned pointer, out-of-range chunk count, or unreviewed configuration. This postrun condition is not a pre-attach memory-safety guarantee. Instrumenting a live native call instruction carries nonzero GUI crash/hang risk; past Stage89 crashed during an import, although later sessions succeeded.

## Offline original-DLL gate — already executed (do not overwrite)

```bash
python3 research/htkpa/stages/stage116/GO.py preflight \
  --config research/htkpa/stages/stage116/frida.json \
  --dll /PRIVATE/5868USB.dll \
  --out /PRIVATE/stage116_preflight_private.json
python3 -m unittest discover -s tools -p 'test_htkpa_stage116.py' -q
```

The real preflight result is a **static/source** readiness gate, not a Frida observation; its full JSON is held privately in `RE_HTKPA`. Tests operate on synthetic PE and Frida TAR fixtures. They do not start/attach Sonicake Manager.

## Native Windows gate — explicitly NOT performed

Before requesting any native probe, the operator must independently run the existing universal runner's offline tests, original Windows x64 DLL SHA preflight and assess live process risk. The legacy `--preflight` confirms the DLL's provided file SHA but **does not verify the Windows Manager EXE path**; check that separately. One supervised, new user-operated conversion is required to trigger the probe. Do **not** auto-retry after a crash, terminate a user-owned GUI or rely on automatic closure in this legacy mode. No large audio/model memory may be read. Raw Frida `events.jsonl` includes process addresses and must be kept private in the designated `RE_HTKPA` Drive folder.

A future one-run command, **only after an intentional operator choice**, will use `tools/FRIDA_WSL.sh --config research/htkpa/stages/stage116/frida.json --fresh --timeout 240` with `FRIDA_AUTO_QUIET=0`; setting auto-quiet to zero avoids mistaking eight early registered hits for a completed conversion. The user should wait for `[HOOK]`/`ready`, perform one conversion, and manually finish the observer; `CAPTURED_HOOKS_ONLY` is not a CLO success claim. If the process crashes, preserve the interrupted archive rather than repeating. The public repository deliberately carries **no auto-run script** and no stage-specific Frida engine.

If a genuine new capture is later supplied, analyze it with:

```bash
python3 research/htkpa/stages/stage116/GO.py audit \
  --config research/htkpa/stages/stage116/frida.json \
  --dll /PRIVATE/5868USB.dll \
  --capture /PRIVATE/ACTUAL_NEW_STAGE116_CAPTURE.tar.gz \
  --out /PRIVATE/stage116_native_register_audit_private.json
```

The auditor reads only an existing allowlisted archive and writes one private JSON exclusively. If the run meets all strict gates, it can establish that the **specific instruction executed** with a bounded `R9D` register value in a particular capture. It does **not** prove that pointer slots contain valid audio, that the input was 48 kHz, that the loaded model bytes equal any archived NAM, that this is the same exact Stage97 invocation, or any resampler/quantizer/fitter/CLO/device numerical parity.

## Privacy and conclusion

Static preflight report and any future raw capture/audit: **restricted** [RE_HTKPA Google Drive](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK). Code, tests, exact reviewed config, sanitized evidence and synthesis: public GitHub. No original DLL, model, WAV, CLO, private SHA ledger or raw runtime pointers in public files. **Stage116 is prepared and preflighted offline; its native capture remains pending**. Do not rerun Stage102–115.
