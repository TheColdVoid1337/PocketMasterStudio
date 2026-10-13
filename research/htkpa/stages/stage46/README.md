# Stage46 — identify Sonicake's fractional interpolator without executing the DLL

**Status: STATIC_RTTI_VTABLE_CONFIRMED.** Analysis was completed directly on the user-supplied original `5868USB.dll` (SHA-256 `fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`) using **read-only PE64 RTTI/vtable parsing** and LLVM disassembly. No Manager/Frida/dynamic invocation was used, and no raw proprietary bytes were committed.

## Why this is a meaningful result after Stage45

Stage45 confirmed `vendor 1972-f64 first FIR -> public fractional` and `public full 44100→48000` agree on 1067 f64 to **8.673617379884035e-19** maximum error in historical public v6.5/v7.2, with chunk-invariant streaming. However the **actual original vendor post-fractional 48000-Hz signal remains missing**. Repeated public-to-public tests cannot close that gap. The next goal is to find which native function yields the post-fractional result, before contemplating any new runtime instrumentation.

## Original vendor static C++ RTTI findings

The original DLL PE image base is `0x180000000`; addresses below are VAs, equivalently RVAs in the lower six digits. A verified MSVC RTTI CompleteObjectLocator is followed by a vftable with seven `CDSPProcessor` virtual slots, ordered destructor, `getInLenBeforeOutPos`, `getLatency`, `getLatencyFrac`, `getMaxOutLen`, `clear`, **`process`**.

| DLL RTTI class | Vftable RVA | Verified process() VA | Confidence |
| --- | --- | --- | --- |
| `r8b::CDSPBlockConvolver` | `0x244ea0` | **`0x18000C220`** | Matches previously studied Stage32/33 original input hook |
| `r8b::CDSPFracInterpolator<...>` | `0x245170` | **`0x1800135C0`** | Independently validated virtual table slot 6 |
| `r8b::CDSPResampler24` | `0x244b58` | `0x180011850` | Independently validated virtual table slot 6 |

The mangled vendor RTTI name for its template instantiation is `.?AV?$CDSPFracInterpolator@$0BI@$0CKB@@r8b@@`. This is an interesting API/build-lineage clue, **not** evidence of exact public release. Public historical v6.5's `CDSPFracInterpolator` is non-templated in its exposed header; matching FIR numerical output alone does not identify embedded vendor source.

Disassembly of `0x1800135C0` begins with the expected `process` Windows-x64 ABI: `RCX=this`, `RDX=input double*`, `R8D=input count`, `R9=double** output pointer-reference`, `EAX=returned output count`. In particular, the method initially loads `R12=[R9]`, preserves `R9`, and may rewrite the returned output pointer. Thus `R9` should **not** be treated as a direct array pointer and its original value should **not** automatically be treated as the final output address.

These are **STATIC FUNCTION IDENTIFICATIONS**. We have not observed a live virtual call to this exact specialization or established buffer ownership, actual return count, output bytes, timing, hook safety or external output correctness.

## Reproduce statically (no Frida, no Sonicake execution)

The included Python script uses only Python's standard library. Place the original private `5868USB.dll` in an ignored local research directory and run:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
python research/htkpa/stages/stage46/rtti_vtable_map.py \
  --dll research/_LOCAL_FILES/5868USB.dll \
  --out research/_LOCAL_FILES/stage46_static_rtti_map.json
```

The script checks the exact expected SHA-256 and the two strongest address controls. The DLL is not opened as executable code or dynamically loaded; output contains only symbolic metadata. If local path differs, change only `--dll`; **do not commit the original DLL**.

## Next gate — static-only caller and output-lifetime study

Before installing a **single** Frida hook (or rerunning Sonicake), determine from the original code:

- Which wrapper invokes this `process` vtable slot and whether the conversion path reaches it.
- Where the `double*& op0` pointer is stored and whether it is rewritten upon return.
- Whether a post-return pointer/length is valid at the caller, and whether an existing normal **copy site** provides a low-impact observation point.
- Whether the first 1067 f64 at 48 kHz can be aligned to the existing Stage45 **public** reference without silently assuming the same original latency or block boundaries.

**Do not automatically hook `0x1800135C0`.** The previous paired `0x18000C220` / `0x18000C838` experiments crashed the Manager. No native runtime experiment is authorized by the result of static mapping alone. This stage does **not** claim vendor fractional numeric parity, complete native resampler parity or finished NAM→CLO conversion.

See `evidence.json` for original RTTI names, vtable slots, source SHA and static address proof. All user-supplied vendor audio and DLL data remain outside Git.
