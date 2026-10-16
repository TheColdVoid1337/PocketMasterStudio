# Stage89 — one-run caller/parent/child provenance capture (operator action pending)

**Status:** `AWAITING_USER_OPERATED_FRIDA_CAPTURE`; no historical caller,
parent pointer or NAM/CLO same-run hash has yet been observed in this
stage. This is a **configuration** for the existing universal Frida
runner, **not a new runner or a claimed finished Stage89 audit**.

## Windows PowerShell — single capture using existing runner

1. Update the working copy from the published repository, and close
   Sonicake Manager before starting. Keep original DLL and Windows
   Frida venv in the existing private paths.
2. At `F:\PocketMasterStudio\PocketMasterStudio_Void_mod`:

```powershell
git pull --ff-only origin main
.\tools\FRIDA_CAPTURE.bat --config research\htkpa\stages\stage89\frida.json --module-file research\_LOCAL_FILES\vendor\5868USB.dll --fresh --timeout 900
```

3. Wait for **four `hook_attached` events and `ready`**, then perform
   **one** normal import/conversion of
   `JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam` to CLO. After the
   operation finishes, press Enter in the runner console. The legacy
   runner records hook metadata but does **not** itself certify CLO
   completion, so note whether the import and resulting CLO succeeded.
4. Send only the generated
   `research/_LOCAL_FILES/frida_captures/frida_*.tar.gz` from that run
   to the private **RE_HTKPA** Drive folder:
   https://drive.google.com/drive/folders/1rH8Zr5kKRAItF5SuRjOtNR8BU3RhOYHK
   and give its filename/Drive link. The original DLL, NAM and CLO are
   already private and should not be committed to GitHub.

**Alternate existing WSL launcher:**

```bash
bash tools/FRIDA_WSL.sh --config research/htkpa/stages/stage89/frida.json --fresh --timeout 900
```

The WSL launcher uses the Windows x64 Frida Python; use it only if the
usual WSL/Windows interop is working. Its legacy mode has an auto-quiet
option (12 seconds by default); prefer the PowerShell BAT command above
for a user-supervised single conversion, or explicitly set a longer
`FRIDA_AUTO_QUIET` value in WSL. Neither launcher performs GUI clicks or
automatically imports the NAM file.

## Four bounded, read-only hooks

| Original RVA | Capture | Independent original native instruction at the hook |
|---|---|---|
| `0xCE00` | Return address at `[RSP]`, group-input `RCX`, f32 rates XMM1/XMM2 | Function entry before prologue, return address available on stack |
| `0xD018` | Group-input `RSI`, constructed parent `RBX`, destination slot `RDI` | `mov [rdi], rbx` after guarded parent construction |
| `0x118FD` | Parent `RBX`, child pointer `[RBX+0x50]` | `mov rcx, [rbx+0x50]` before virtual `+0x30` call |
| `0x135C0` | Fractional child `RCX`, incoming count register `R8` | Stage64 guarded fractional function entry |

The legacy runner uses exactly its documented scalar types `ptr`,
`reg_ptr`, `reg_u64`, and `xmm_f32`; no sample arrays, audio blocks,
full memory dumps, JavaScript injection, DLL patches or process killing.
Per-hook caps are 48, 48, 64, 64; nonrequired `0xD018` helps prove
ancestry when reachable but cannot manufacture a path when missing.

For the helper hook, subtract 5 from the captured **return-address
RVA** (after subtracting the actual ASLR module base) to get the
corresponding direct-call RVA. The original Stage88 six-call candidates
are `0xD786`, `0x112A2`, `0x113C4`, `0xBF364`, `0xBF47F`, and `0xE28F1`.
Unknown return addresses must be reported, not forced into this list.

If the same captured group input appears at `0xCE00` and `0xD018`,
then the recorded parent equals a subsequent `0x118FD` parent, and its
recorded child equals a `0x135C0` child, those *same-run pointer matches*
can support concrete ancestry. Match within one capture, accounting for
thread, event order and pointer reuse. A mere matching rate pair or
static vtable type never proves historical Stage64 instance ancestry.
Even a successful Stage89 capture is a **new run**, not retroactive
proof of which caller produced the historical Stage64 archive.

## Verification limit

The source was checked statically against the pinned original
`5868USB.dll` (SHA256
`fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa`).
This config has **not** been exercised under Windows Frida. Capture
success requires actual hook installation, valid scalar hit events,
the original loaded DLL SHA, and an operator-confirmed conversion.
Until then the result remains `AWAITING_USER_OPERATED_FRIDA_CAPTURE`.
