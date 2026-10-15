# Stage79 — Stage64 architecture identity: strict metadata gate

The exact original Sonicake PE64 is available to this audit in the assistant
scratch. The **private Stage64 archive / original input `.nam` are not**.
Therefore the audit must not invent the actual architecture selected by the
specific captured NAM→CLO conversion.

Stage78 already established the static native parser path:

`architecture` JSON property (`0xcb44f`) → metadata `+0x20` → copied packet
`+0x20` (`0xcafe3`) → named factory registry lookup (`0xcaa65/0xcaa76`).
Four source-registered names are `SlimmableContainer`, `ConvNet`, `LSTM`,
`WaveNet`, consistent with the open [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore)
vocabulary. **None of those names is identified as Stage64's chosen key.**

## What Stage79 adds

1. Re-runs the complete SHA-pinned Stage78 static source audit against the
   original private DLL. No vendor code executes.
2. If an explicitly supplied archive is available, refuses anything but the
   **exact SHA256**
   `aa32d8440b532708ce3551404f5a4292791abd31aba197003e850f61f22683ff`.
3. Reads only `frida_capture/config.json`, `manifest.json` and `events.jsonl`
   with bounded JSON decoding, duplicate-key rejection, strict capture
   chronology/completion checks from Stage69. Does **not** open/extract
   captured f64, original audio or `.nam` model weights.
4. Searches just these metadata objects for exact JSON keys named
   `architecture`. Names (if present) are output as **unbound candidates**
   with their source JSON path; matching a Stage77 registered name does not
   prove the same input model or a live factory selection.

The missing archive has a distinct, epistemically conservative status:

`STAGE64_PRIVATE_ARCHIVE_UNAVAILABLE_ARCHITECTURE_UNPROVEN`

An authenticated archive with no explicit `architecture` in the inspected
metadata would receive
`ACCEPTED_STAGE64_METADATA_HAS_NO_ARCHITECTURE_KEY_RUNTIME_UNPROVEN`.
This means *absent from those three metadata files*, not absent in the source
NAM or factory. A candidate, even an exact `WaveNet`, receives
`ACCEPTED_STAGE64_METADATA_HAS_UNBOUND_ARCHITECTURE_CANDIDATE`.

## Independent result (2026-10-15)

- Exact original PE audited successfully; Stage78 source and registration
  gates rerun.
- Stage64 archive **not available in assistant workspace**. Actual metadata
  inspection intentionally **not claimed**. No specific architecture chosen.
- **12 synthetic Stage79 tests**, **81/81** Stage70–79 offline tests pass.
- Synthetic tests cover metadata-only accepted sample, two conflicting
  architecture candidates, malformed/duplicate JSON, duplicate tar entries,
  SHA failure, wrong rate chronology, changed f64 hashes, missing summary,
  bounded traversal and prior-stage runtime-claim drift.
- Neither DLL nor capture is committed; real output remains in private
  `research/_LOCAL_FILES/stage79_capture_architecture.json`.

## Repeat / optional private archive verification

The first invocation verifies the source-only status without requiring any
Stage64 file. The second is only possible once the exact private capture is
available; its absence is not a request for users to run new hooks.

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage79.py' -v

python research/htkpa/stages/stage79/audit_capture_architecture.py \
  --dll /path/to/private/original/5868USB.dll \
  --out research/_LOCAL_FILES/stage79_capture_architecture.json

# Only if the exact authenticated original Stage64 archive is available:
python research/htkpa/stages/stage79/audit_capture_architecture.py \
  --dll /path/to/private/original/5868USB.dll \
  --stage64 /path/to/private/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --out research/_LOCAL_FILES/stage79_capture_architecture.json
```

## Strict next gate

To prove the specific Stage64 *input model architecture*, obtain the exact
input NAM/CLO model metadata and independent provenance linking **that file**
to the completed Stage64 conversion. Even if Stage64 metadata contains an
architecture-looking string, it is **not** the selected runtime native
factory without that association. Only then can we join the neural model
identity to reverse resampler provenance and the anti-aliasing pipeline.

No DSP changes, hook, native execution, vendor audio read, or standalone Lab
parity claim is authorized by this Stage.
