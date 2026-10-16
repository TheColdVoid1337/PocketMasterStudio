# Stage86 — authenticated Stage64 fractional hook → original resampler child *type*

**Result:**
`STAGE64_FRACTIONAL_VTABLE_AND_STATIC_RESAMPLER_CHILD_OWNER_VERIFIED_RUNTIME_PARENT_UNPROVEN`.

Read-only, original-source analysis: SHA-pinned `5868USB.dll` and the exact
historical Stage64 archive; 45/45 new native instruction pins, seven original
file-backed virtual method pointers, 21 accepted Stage64 metadata records.
The full Stage85→70 evidence chain is rerun. No original DLL execution, new
Frida activity, model-weight reading or audio-payload extraction is performed.

## Newly closed type-level link

| Site | Verified original DLL or Stage64 metadata |
|---|---|
| Stage64 `config.json` | guarded site RVA `0x135C0`, checked vtable RVA `0x245170` |
| PE-backed vtable `0x245170` | exactly seven method qwords, final slot **`+0x30 → 0x135C0`** |
| Original constructor `0x11B60` | at `0x12170` allocates `0x1048` bytes on a conditional DSP-specific branch |
| `0x121AE` / `0x121B5` | loads address `0x245170` and installs it at the new child object's offset `+0x0` |
| `0x121B8` / `0x121C0` | writes f64 child offsets `+0x1008` and `+0x1010`, exactly the Stage64 rate probes |
| `0x1218F–0x121AA` | computes the numerator using an upstream scaling factor and constructor input rate XMM8; source 48000 is **not** assumed |
| `0x12213` / `0x12217` / `0x1222A` | reads, clears/releases, then stores the fractional child in the parent `CDSPResampler24` object at **`+0x50`** |
| `0x1222E–0x12237` | invokes a newly stored child's virtual method through vtable offset `+0x20` |
| `0x11A4C–0x11A59` | a separate original native routine compares a live object's vtable to the same `0x245170` type marker |

The original vtable's 7 target RVAs, in slot order:
`0x14320`, `0x11ac0`, `0x11b50`, `0x13dc0`, `0x13d90`,
`0x13d30`, `0x135c0`. All are checked as literal qwords in the original
file's uniquely mapped PE section, not inferred from capture output.

The guard metadata belongs to an authentic, SHA-pinned Stage64 Frida run with
21 accepted `fractional_io` calls: 4 forward `88200/48000`, then 17 reverse
`96000/44100`. The prior Stage79 gate also independently validates two
extended-output **metadata hashes and sample counts**, without reading their
payloads. Thus Stage64's guarded processor matches the **original compiled
fractional child class** allocated and retained by this constructor.

## Provenance boundary — do not overstate

This is a **class/type topology** bridge, not a particular historical object's
ancestry. Neither the 21 Stage64 `fractional_io` records nor their guard
configuration includes a captured **parent pointer, caller RVA, return address
or call stack**. Constructor branches and alternative call paths exist. We
cannot identify which constructor call allocated the historical Stage64
processor, show its parent was this specific resampler instance, or connect
its pointer to a `nam::container::ContainerModel` instance. The unrelated
`ContainerModel` SlimmableModel interface offset `+0x50` must not be confused
with this **resampler's own child-pointer offset `+0x50`**.

The operator identifies every NAM-import Frida capture's source as
`JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam`. This testimony does not create
an input-file hash inside the historical Stage64 trace. In particular,
captured reverse `96000/44100` does not establish an actual upstream
48,000-Hz source or numerical/full-audio parity.

## Reproduce with private local originals

```bash
python -m unittest discover -s tools -p 'test_htkpa_stage86.py' -v
python -m unittest discover -s tools -p 'test_htkpa_stage*.py' -q

python research/htkpa/stages/stage86/audit_fractional_ownership.py \
  --dll research/_LOCAL_FILES/vendor/5868USB.dll \
  --stage64 research/_LOCAL_FILES/frida_captures/frida_20261014_201555_724062_cnvuir25.tar.gz \
  --nam-2203 'research/_LOCAL_FILES/models/JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam' \
  --nam-sc20 'research/_LOCAL_FILES/models/Marshall JCM 800 SC20 Full Rig.nam' \
  --clo-2203 research/_LOCAL_FILES/captures/2203/official_vendor.clo \
  --clo-sc20 research/_LOCAL_FILES/captures/SC20/official_vendor.clo \
  --out research/_LOCAL_FILES/stage86_fractional_ownership.json
```

The private report is kept in Git-ignored `_LOCAL_FILES` and the designated
private Drive handoff folder. The next useful evidence is a **bounded
same-run parent/caller object observation**; do not claim it from source
vtable equality alone.
