# Stage93 — original-PE guard analysis of the two Stage92 WAV-worker entries

**Status:** `STATIC_DUAL_WAV_CALL_COMPATIBILITY_GUARDS_VERIFIED_STAGE92_STACK_UNBOUND`.

Stage92 observed two new-run, **same-thread temporal** sequences with
outer `0xD4A0` callsites `0xEB1E` (11 ms before its inner `0xD786 → 0xCE00`)
and `0x11021` (10 ms). Those observations passed the original-DLL byte-level
Stage92 audit. They do **not** prove that the two WAV calls occurred in one
invocation of any higher-level function.

## New narrow static result

This stage checks whether those two observed outer callsites can appear in a
**single compiled wrapper scenario**, not whether that actually happened.
All addresses below are original PE RVAs, not runtime pointers.

1. Wrapper `0x10E70` calls NAM worker `0xE0E0` at **`0x10F7F`**.
2. Within `0xE0E0`, the compare `ucomiss xmm9, [44100.0f]` at `0xEA01`
   branches on unequal or unordered to `0xEA7D`, a route containing
   **`0xEB1E → 0xD4A0`**. The actual `xmm9` value for Stage92 was not captured.
3. After the `0x10F7F` call returns, `0x10E70` converts its integer return
   `EAX` through `XMM6` to a double at `0x10F84–0x10F88`. It compares this
   result with the original **`-2.0` sentinel** at `0x10F8C`.
4. Equality with `-2.0` follows the skip/error branch. Inequality or unordered
   goes to `0x10FF6`, with another gate on optional `RSI` flag data:
   absent or byte zero can reach `0x1100B`; nonzero skips to `0x110CF`.
5. On the pass-through branch `0x11016` forwards `XMM6` to `XMM2`, then
   **`0x11021 → 0xD4A0`**. This is a compiled argument transfer, **not** a
   measured Stage92 sample rate or WAV pathname.

Consequently, the static call structure is compatible with one wrapper
entering `0xE0E0`, conditionally performing the first WAV operation, returning,
and conditionally performing the second WAV operation. **This is not a runtime
same-stack or same-invocation proof.** The outer temporal sequences may have
come from separate wrapper invocations. In particular, original return/exit
events, actual branch predicates, NAM hash, opened WAV path, output CLO and
historical Stage89 ancestry remain unbound.

## Falsifiable offline gate

`audit_dual_wav_guard_path.py` operates on the **original** SHA-pinned
`5868USB.dll` as inert file data and on already accepted **sanitized** Stage92
`evidence.json`. It first reruns the complete Stage91 original-PE checks:
the four direct `D4A0` callers, two `E0E0` callers, 7 exact `E8 rel32`
instructions, 40 pinned original instructions, `.pdata` owners, literals and
export. It then independently checks **25 additional exact guard/return-
register/flag/argument anchors** across original `.pdata` owners `0xE0E0`
and `0x10E70`, plus their three direct-call bytes, and rejects mutation of
either accepted Stage92 temporal sequence or an invented same-stack claim.

No Frida instrumentation, Manager launch, DLL execution, DSP implementation,
public Ghidra decompilation, model/audio payload read or CLO export is involved.
The reused Stage92 observations remain explicitly separate from this new
static inference.

Verified in the analyst sandbox against the actual original DLL:

- Original vendor SHA256:
  `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`
- Original-DLL audit: **PASS**, 25/25 new instruction anchors.
- Stage93 synthetic/negative controls: **26/26 PASS**.
- Combined `test_htkpa_stage*.py` suite: **380/380 PASS**.

The complete standalone Stage93 offline output belongs in the private
[RE_HTKPA](https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK)
folder. No raw vendor binary or Frida journal belongs in public GitHub.

## Reproduce from WSL Bash (no Frida)

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python -m unittest discover -s tools -p 'test_htkpa_stage93.py' -q
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q

python research/htkpa/stages/stage93/audit_dual_wav_guard_path.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --out research/_LOCAL_FILES/stage93_dual_wav_guard_private_report.json
```

**Next evidence gate:** Do not rerun Stage92 to re-prove its outer callsites.
If exact *same-invocation* identity becomes indispensable, it requires an
explicitly scoped, operator-approved runtime return/stack correlation, not
further static speculation. Separately, actual completed NAM → CLO output
must be demonstrated by file/capture evidence; operator-attested no-crash
Stage92 execution is not a completion marker.
