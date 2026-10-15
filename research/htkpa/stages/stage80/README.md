# Stage80 — authenticated NAM metadata versus Stage64 capture identity

This stage closes Stage79's **missing-private-input** problem while separating
capture-internal evidence from later capture-operator testimony. It does not
run `5868USB.dll`, a Frida hook, model inference or audio processing.

## Operator provenance correction (2026-10-15 UTC)

The capture operator explicitly confirmed: during **every Frida capture that
involved importing a NAM**, they used
`JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam` (2203). This includes the Stage64
NAM-import capture. **The source model's filename is therefore known by
firsthand operator testimony**, not unknown as the original Stage80 wording
suggested. `Marshall JCM 800 SC20 Full Rig.nam` remains a separate comparison
fixture; it was not the operator's NAM import input for these Frida runs.

The original Stage80 audit status below concerns **independently authenticated
same-run bytes** only. The Stage64 archive itself did not record a NAM input
SHA256 or finished CLO SHA256. The SHA-pinned 2203 fixture's bytes cannot be
cryptographically bound to that particular run on testimony alone. Neither
the live native factory nor numeric parity is established by this correction.

## Exact offline result (2026-10-15 UTC)

- The SHA-pinned Stage64 tar passed the full Stage79 static and capture-metadata
  gate. Its selected `config.json`, `manifest.json` and `events.jsonl` contain
  **zero** explicit `architecture` keys. Status:
  `ACCEPTED_STAGE64_METADATA_HAS_NO_ARCHITECTURE_KEY_RUNTIME_UNPROVEN`.
- Both separately authenticated original NAM files have top-level
  `architecture = "SlimmableContainer"`, `version = "0.7.0"` and
  `sample_rate = 48000`. The name is in the exact original DLL's Stage77
  registered-name set. This proves **source-file metadata**, not live factory
  selection by Stage64.
- Both separately authenticated official reference `.clo` files are **8,840
  bytes**. Stage64's completion manifest also reports 8,840 bytes, but all
  three having the same size is **not file identity or provenance**. No actual
  Stage64 output CLO hash or source NAM hash/name was preserved in its bounded
  capture metadata. The operator's subsequent identification of the 2203
  filename is an independent, testimonial source of provenance.
- The two NAMs have the **same architecture and sample rate**, so those fields
  cannot *independently* distinguish the model used in the specific captured
  conversion; the operator's declaration does identify its model label.

Original **machine-evidence-only** audit status:
`TWO_NAM_ARCHITECTURES_VERIFIED_STAGE64_INPUT_IDENTITY_UNPROVEN`.
Operator testimony: `STAGE64_2203_MODEL_LABEL_OPERATOR_ATTESTED`.

## Verification

Private files live at `research/_LOCAL_FILES/` and **must not be committed**.
Use the exact files described in the private source manifest. Stage80's
read-only CLI checks SHA pins and refuses altered/private test inputs.

```bash
python3 -m unittest discover -s tools -p 'test_htkpa_stage80.py' -v
python3 -m unittest discover -s tools -p 'test_htkpa_stage*.py'

python3 research/htkpa/stages/stage80/audit_nam_capture_identity.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage80_nam_capture_identity.json
```

Observed: Stage80 **8/8** synthetic tests, combined Stage70–80 **89/89**
offline tests, full real SHA-pinned read-only audit PASS. Private full report:
`research/_LOCAL_FILES/stage80_nam_capture_identity.json`.

## Strict next gate

The specific Stage64 input **model label is operator-attested as 2203**. What
remains unproven is a byte-exact same-run input/output association. Future
evidence would link the input NAM SHA256 to the output CLO SHA256 **in the same conversion run**,
using an independent application/import manifest or timestamped immutable
source-file record. Do not claim that architecture, filename, sample rate or
generic CLO size provide a cryptographic link. This gate can be designed
without deploying another intrusive Frida hook.

No production DSP changes, native execution, neural weight export, audio
parity or complete reverse antialiasing claim is made by Stage80.
