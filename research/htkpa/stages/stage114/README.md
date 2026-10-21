# Stage114 — evidence gate before capturing vendor pre-NAM 48-kHz input

**Status:** `STAGE114_EXISTING_NATIVE_TRACE_PROVENANCE_GAP_CONFIRMED` (2026-10-21 Bangkok). One real read-only inspection of the original private Stage96 Frida archive and Stage113 public evidence, with **15/15 independent synthetic tests PASS**. This stage does **not** run Sonicake Manager, Frida, the DLL, resampling, NAM, fitter, CLO or device commands.

## Falsifiable question

Do the authentic existing native events prove the **sample values/format/buffer identity of Sonicake's input to NAM**? Stage96 previously proved same-invocation call ancestry inside wrapper `0x10E70`, but its `invocation_trace` mode only records function entry/exit events. Stage113 tested original 44.1-kHz input WAV versus a **public candidate** resampled 48-kHz DI; it did not see Sonicake's internal 48-kHz input.

## Real audited source and method

Original Stage96 `frida_20261018_195315_795910_3s0kasuh.tar.gz` from the user's private `RE_HTKPA` Drive folder. The historical original archive SHA and runtime DLL SHA matched the previously accepted Stage96 pins. Four archive members passed an exact allowlist; the archived config, manifest and 30 JSONL events were read as inert data, never extracted or executed. Exact event topology: **1 loaded module, 8 attached hooks, 1 ready, 10 invocation entries, 10 matching leaves**; manifest reports zero hook/field errors, `CAPTURED_HOOKS_ONLY`, `completion_verified=false`, `contains_audio_bytes=false`. Stage113 published provenance explicitly marks its 48k DI as *open resampler candidate*.

Stage114 checks existing capture integrity and event schemas. It does **not** repeat Stage96's original-PE disassembly or independently reconstruct all previously accepted parent/child native callsite evidence.

**Result:** The Stage96 capture has **no sampled pre-NAM float array, trusted pre-NAM buffer pointer, native buffer format or independently observed target sample rate**. This is a limit of the captured evidence, not evidence that the application lacked an internal input buffer.

## Strict next step

Before a new native run, identify from original-PE instructions **which exact argument crosses into NAM inference** and whether it carries the 48-kHz sample buffer (not merely a WAV/fitter/resampler object). Prove candidate offset, sample type, count, rate, lifetime and relation to one wrapper invocation. Only then design a bounded SHA-pinned, **metadata-only** probe in the **existing universal Frida runner**; evaluate historical Manager crash risks before any operator run. A separate, narrower **private sample** capture would require its own validated site/acceptance, not arbitrary memory dumping. No new Stage115 capture script or Windows action is claimed ready.

See [public result](OPERATOR_RESULT_20261021.md) and [evidence](evidence.json). The detailed Stage114 report remains private; no Stage102–113 reruns or source audio publication. The Stage114 public auditor is at [GO.py](GO.py), and the independent synthetic fixtures are at [tools/test_htkpa_stage114.py](../../../../tools/test_htkpa_stage114.py). The same Stage114 auditor and fixtures were tested locally (15/15 PASS).

Historical read-only source-audit command (the original private report already exists, so **do not rerun** against its same output):
```bash
python research/htkpa/stages/stage114/GO.py \
  --capture /PRIVATE/frida_20261018_195315_795910_3s0kasuh.tar.gz \
  --stage113-evidence research/htkpa/stages/stage113/evidence.json \
  --output /PRIVATE/stage114_native_input_provenance_gap_private.json
```
