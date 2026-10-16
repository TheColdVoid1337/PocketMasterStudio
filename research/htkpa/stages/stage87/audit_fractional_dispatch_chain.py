#!/usr/bin/env python3
"""Stage87: original-PE fractional child dispatch route through its parent.

Shows conditional compiled virtual dispatch from the resampler-group helper
to parent method 0x11850 and onward to the Stage64-guarded child method.
The historical Stage64 parent pointer/caller was NOT captured.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage86"))
import audit_fractional_ownership as stage86

stage72 = stage86.stage72
stage80 = stage86.stage80
stage79 = stage86.stage79
stage77 = stage86.stage77
BASE = stage86.BASE
STATUS = "STATIC_GROUP_PARENT_TO_STAGE64_FRACTIONAL_VIRTUAL_DISPATCH_VERIFIED_RUNTIME_INSTANCE_UNBOUND"

PARENT_VTABLE_RVA = 0x244B58
PARENT_CTOR_VTABLE_RVA = 0x244FF8
PARENT_DISPATCH_RVA = 0x11850
VIRTUAL_DISPATCH_SLOT = 0x30
PARENT_VTABLE_TARGETS = (0xCD30, 0x11AC0, 0x11B50, 0x11AD0,
                         0x11AC0, 0x11920, PARENT_DISPATCH_RVA)
FIXED_TARGET_F32_RVA = 0x24CDF0

# All addresses are ORIGINAL DLL RVAs, grouped by the entry of the owning
# authentic .pdata function. Not a blind text search through disassembly.
PINS = {
    0xE2640: {
        0xE28DC: "movsd xmm1,qword ptr [r14+0x8]",
        0xE28E2: "cvtpd2ps xmm1,xmm1",
        0xE28E6: "movss xmm2,dword ptr [rip+0x16a502]",
        0xE28EE: "mov rcx,rbx",
        0xE28F1: "call 0x18000ce00",
        0xE28F6: "mov r14,rax",
    },
    0xBE830: {
        0xBF34D: "movss xmm6,dword ptr [rip+0x18da9b]",
        0xBF355: "movaps xmm2,xmm6",
        0xBF358: "movss xmm1,dword ptr [r14+0x20ec0]",
        0xBF361: "mov rcx,rbx",
        0xBF364: "call 0x18000ce00",
        0xBF369: "mov rbx,rax",
    },
    0xCE00: {
        0xCE3C: "mov rsi,rcx",
        0xCE3F: "movsxd r15,dword ptr [rcx]",
        0xCE87: "mov qword ptr [rax],r15",
        0xCE8A: "lea rbx,[rax+0x8]",
        0xCE8E: "mov qword ptr [rsp+0xe0],rbx",
        0xCEF2: "lea r13,[rax+0x8]",
        0xCEF6: "mov qword ptr [rsp+0xf8],r13",
        0xCF27: "test r15d,r15d",
        0xCF30: "mov rdi,r13",
        0xCF4C: "lea r15,[rip+0x237c05]",
        0xCFB8: "mov ecx,0x78",
        0xCFBD: "call qword ptr [rip+0x17e97d]",
        0xCFC3: "mov rbx,rax",
        0xCFCB: "test rax,rax",
        0xCFCE: "je 0x18000cffd",
        0xCFD3: "cvtss2sd xmm2,xmm8",
        0xCFDB: "cvtss2sd xmm1,xmm9",
        0xCFF0: "mov rcx,rax",
        0xCFF3: "call 0x180011b60",
        0xCFF8: "mov qword ptr [rbx],r15",
        0xCFFF: "mov rcx,qword ptr [rdi]",
        0xD002: "mov qword ptr [rdi],0x0",
        0xD018: "mov qword ptr [rdi],rbx",
        0xD01B: "add rdi,0x8",
        0xD023: "jne 0x18000cf60",
        0xD0D5: "mov r14,qword ptr [rsp+0xf8]",
        0xD0F0: "mov rcx,qword ptr [r14+rbx*1]",
        0xD0F4: "mov rax,qword ptr [rcx]",
        0xD0F7: "mov r10,qword ptr [rax+0x30]",
        0xD10E: "call r10",
        0xD229: "mov rax,rdi",
    },
    0x11B60: {
        0x11BD7: "lea rax,[rip+0x23341a]",
        0x11BDE: "mov qword ptr [rcx],rax",
        0x11C07: "mov qword ptr [rbx+0x50],rdi",
    },
    0x11850: {
        0x11859: "mov rbx,rcx",
        0x1185F: "mov ecx,dword ptr [rcx+0x48]",
        0x11867: "jne 0x180011878",
        0x11885: "mov qword ptr [rsp+0x50],r14",
        0x1188A: "lea r14,[rbx+0x8]",
        0x118AB: "mov rcx,qword ptr [r14]",
        0x118AE: "mov rax,qword ptr [rcx]",
        0x118B1: "call qword ptr [rax+0x30]",
        0x118CF: "cmp qword ptr [rbx+0x50],0x0",
        0x118D9: "jne 0x1800118ea",
        0x118FD: "mov rcx,qword ptr [rbx+0x50]",
        0x11901: "mov qword ptr [rsp+0x40],rax",
        0x11906: "mov rax,qword ptr [rcx]",
        0x11909: "call qword ptr [rax+0x30]",
    },
}


def verify_parent_vtables(data: bytes) -> dict:
    """Both PE-backed parent class vtables must share exact seven methods."""
    tables = {}
    for label, vtable in (("constructor_initial", PARENT_CTOR_VTABLE_RVA),
                          ("group_installed", PARENT_VTABLE_RVA)):
        entries = {}
        for i, target in enumerate(PARENT_VTABLE_TARGETS):
            entries[f"+0x{i * 8:x}"] = stage77.read_pointer(data, vtable + i * 8, target)
        if entries[f"+0x{VIRTUAL_DISPATCH_SLOT:x}"] != f"0x{PARENT_DISPATCH_RVA:x}":
            raise ValueError("Parent virtual dispatch slot changed")
        tables[label] = {"rva": f"0x{vtable:x}", "seven_qword_method_targets": entries}
    # The Stage86 audit checks the child's seven target methods independently.
    stage86.verify_vtable(data)
    fixed_target = struct.unpack("<f", stage72.pe_file_bytes(data, FIXED_TARGET_F32_RVA, 4))[0]
    if fixed_target != 44100.0:
        raise ValueError("Original target 44100.0f changed")
    return {"original_parent_vtables": tables,
            "parent_slot_0x30_target": f"0x{PARENT_DISPATCH_RVA:x}",
            "child_slot_0x30_target": f"0x{stage86.FRACTIONAL_HOOK_RVA:x}",
            "shared_original_44100f_constant_rva": f"0x{FIXED_TARGET_F32_RVA:x}"}


def verify_route(insns_by_owner: dict[int, dict[int, str]]) -> dict:
    groups = {}
    for owner, pins in PINS.items():
        if owner not in insns_by_owner:
            raise ValueError(f"Missing source owner {owner:#x}")
        groups[f"0x{owner:x}"] = stage72.verify_pins(
            {"route": pins}, insns_by_owner[owner])["route"]
    return {
        "new_checked_instruction_pin_count": sum(map(len, PINS.values())),
        "verified_instruction_rvas_by_source_owner": groups,
        "shared_helper_two_compiled_input_paths": {
            "0xe28f1": "f64 +0x8 narrowed to f32 XMM1 before helper; fixed 44100.0f XMM2",
            "0xbf364": "f32 context +0x20ec0 to XMM1 before helper; fixed 44100.0f XMM2",
        },
        "per_channel_compiled_chain": [
            "0xcff3 constructs 0x78-byte parent via 0x11b60 on nonnull allocation",
            "0xcff8 installs PE vtable 0x244b58 into constructed parent",
            "0xd018 inserts parent pointer into helper's +0x8 based pointer array",
            "0xd0f0/d0f7/d10e calls parent vtable slot +0x30 (0x11850)",
            "0x118fd/0x11906/0x11909 conditionally dispatches child at parent +0x50 via its slot +0x30 (0x135c0)",
        ],
        "conditional_parent_and_child_object_types_required": True,
        "same_run_stage64_exact_parent_or_caller_observed": False,
    }


def audit(dll: Path, stage64: Path, nams: dict[str, Path],
          clos: dict[str, Path], objdump: str | None = None) -> dict:
    prior = stage86.audit(dll, stage64, nams, clos, objdump)
    if prior["status"] != stage86.STATUS:
        raise ValueError("Stage86 exact-original gate not accepted")
    claims = prior["claims"]
    if any(claims.get(label) for label in (
            "historical_stage64_specific_parent_pointer_or_caller_verified",
            "historical_stage64_nam_container_pointer_parent_bound",
            "stage64_same_run_nam_clo_sha_authenticated",
            "original_dll_executed")):
        raise ValueError("Stage86 unproven historical identity was elevated")
    data = stage80.checked_file(dll, stage79.DLL_SHA256,
                                stage86.stage85.stage84.stage83.stage82.MAX_DLL_BYTES)
    vtables = verify_parent_vtables(data)
    pe = stage72.previous.PEFunctions(data)
    exe, backend = stage72.select_objdump(objdump)
    owners, insns = {}, {}
    for start, pins in PINS.items():
        if pe.owner(start).start != start:
            raise ValueError(f"Unexpected original .pdata owner {start:#x}")
        ranges = {(pe.owner(rva).start, pe.owner(rva).end) for rva in pins}
        owners[f"0x{start:x}"] = [[f"0x{begin:x}", f"0x{end:x}"]
                                    for begin, end in sorted(ranges)]
        merged = {}
        for begin, end in sorted(ranges):
            merged.update(stage72.read_disassembly(dll, exe, backend, begin, end))
        insns[start] = merged
    route = verify_route(insns)
    return {
        "stage": 87, "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": stage79.DLL_SHA256,
        "stage64_archive_sha256": stage79.STAGE64_SHA256,
        "prior_stage86_gate": prior["status"],
        "original_file_backed_dispatch": vtables,
        "original_compiled_parent_child_call_route": route,
        "pe_function_owners": owners,
        "disassembler_backend": backend,
        "operator_attested_stage64_nam_filename":
            "JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam",
        "claims": {
            "both_static_helper_entry_routes_to_resampler_constructor_verified": True,
            "per_channel_parent_vtable_dispatch_to_0x11850_verified": True,
            "parent_child_virtual_dispatch_to_stage64_0x135c0_verified": True,
            "historical_stage64_specific_parent_pointer_or_callsite_verified": False,
            "historical_stage64_active_constructor_branch_verified": False,
            "stage64_same_run_nam_clo_sha_authenticated": False,
            "actual_stage64_input_48000_verified": False,
            "original_dll_executed": False,
            "new_frida_capture": False,
            "complete_vendor_dsp_or_audio_parity_verified": False,
        },
        "next_gate": "Identify parent pointer/return-address from a new bounded same-run capture only when available; static dual dispatch is not historical object ancestry.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dll", "stage64", "nam-2203", "nam-sc20", "clo-2203", "clo-sc20"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--objdump")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    originals = (args.dll, args.stage64, args.nam_2203, args.nam_sc20,
                 args.clo_2203, args.clo_sc20)
    if args.out and args.out.resolve() in (p.resolve() for p in originals):
        raise ValueError("Refusing to overwrite authenticated original")
    result = audit(args.dll, args.stage64,
                   {"2203": args.nam_2203, "SC20": args.nam_sc20},
                   {"2203": args.clo_2203, "SC20": args.clo_sc20}, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": 87, "status": result["status"],
                      "native_pin_count": result["original_compiled_parent_child_call_route"]["new_checked_instruction_pin_count"],
                      "historical_parent": "UNPROVEN"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
