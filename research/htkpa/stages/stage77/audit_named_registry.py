#!/usr/bin/env python3
"""Stage77: original-PE named parser registrations and callback indirection.

Source-backed positive registration paths are not a trace of the specific
Stage64 reverse file, its key, or any live constructed resampler object.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage76"))
import audit_registry_selection as stage76

stage75 = stage76.stage75
stage72 = stage76.stage72
BASE = stage76.BASE
DLL_SHA256 = stage76.DLL_SHA256
STATUS = "FOUR_NAMED_STATIC_REGISTRATIONS_CALLBACK_BRIDGE_RUNTIME_KEY_UNPROVEN"

WRAPPER_VTABLE_RVA = 0x246EF0
WRAPPER_CALLBACK_RVA = 0x38540
SLIMMABLE_VTABLE_RVA = 0x246E98
SLIMMABLE_VIRTUAL_METHOD_RVA = 0xC56D0

# A name, entry function, exact file-backed literal RVA, byte length,
# builder function reached via registry wrapper slot +8.
REGISTRATIONS = {
    "SlimmableContainer": (0x19F0, 0x18F488, 18, 0xC5610),
    "ConvNet": (0x1B50, 0x18F578, 7, 0xC62B0),
    "LSTM": (0x1D30, 0x18FA24, 4, 0xCC690),
    "WaveNet": (0x1F50, 0x190C38, 7, 0xD01A0),
}

OWNER_STARTS = {
    **{f"register_{name}": entry for name, (entry, _, _, _) in REGISTRATIONS.items()},
    "registry_insert_0x35ee0": 0x35EE0,
    "callback_holder_move_0x69a0": 0x69A0,
    "registry_callback_0x38540": 0x38540,
    "slimmable_builder_0xc5610": 0xC5610,
    "slimmable_virtual_method_0xc56d0": 0xC56D0,
    "slimmable_result_constructor_0xc5f40": 0xC5F40,
}


def rip_load(rva: int, target_rva: int, register: str) -> str:
    """Expected exact 7-byte PE x64 LEA destination, not a live address."""
    delta = target_rva - (rva + 7)
    if delta < 0 or delta > 0x7FFFFFFF:
        raise ValueError("Unexpected signed RIP-relative registration reference")
    return f"lea {register},[rip+0x{delta:x}]"


def registration_pins() -> dict[str, dict[int, str]]:
    """Pin complete local source linkage, using explicit RVA registration data."""
    out = {}
    for name, (entry, key_rva, key_size, builder) in REGISTRATIONS.items():
        out[f"register_{name}"] = {
            entry + 0x2F: rip_load(entry + 0x2F, WRAPPER_VTABLE_RVA, "rax"),
            entry + 0x36: "mov qword ptr [rsp+0x28],rax",
            entry + 0x3B: rip_load(entry + 0x3B, builder, "rax"),
            entry + 0x42: "mov qword ptr [rsp+0x30],rax",
            entry + 0x6D: f"mov r8d,0x{key_size:x}",
            entry + 0x73: rip_load(entry + 0x73, key_rva, "rdx"),
            entry + 0x7A: "lea rcx,[r11-0x30]",
            entry + 0x7E: "call 0x180013f30",
            entry + 0x84: "call 0x180035df0",
            entry + 0xAC: "call 0x1800069a0",
            entry + 0xB2: "lea r8,[rsp+0x78]",
            entry + 0xB7: "lea rdx,[rsp+0xb8]",
            entry + 0xBF: "mov rcx,rbx",
            entry + 0xC2: "call 0x180035ee0",
        }
    return out


PINS = {
    **registration_pins(),
    "registry_insert_0x35ee0": {
        0x35F29: "mov r15,qword ptr [rdx+0x10]",
        0x35F3D: "movabs rdx,0xcbf29ce484222325",
        0x35F4E: "movabs r11,0x100000001b3",
        0x35F60: "movzx eax,byte ptr [rcx+r8*1]",
        0x35F65: "xor rdx,rax",
        0x35F68: "imul rdx,r11",
        0x35F72: "jb 0x180035f60",
        0x35F74: "mov rax,qword ptr [r10+0x30]",
        0x35F7F: "mov rdx,qword ptr [r10+0x18]",
        0x36035: "cmp rbx,rbp",
        0x36038: "jne 0x1800360cf",
        0x3604B: "call 0x180038160",
        0x36050: "mov rbx,qword ptr [rsp+0x30]",
        0x36055: "add rbx,0x30",
        0x3605E: "mov rcx,qword ptr [rbx+0x38]",
        0x3607E: "mov rcx,rbx",
        0x36081: "call 0x1800069a0",
    },
    "callback_holder_move_0x69a0": {
        0x69AA: "mov rdi,rcx",
        0x69AD: "mov rbx,rdx",
        0x69B0: "mov rcx,qword ptr [rdx+0x38]",
        0x69C4: "call qword ptr [rax+0x8]",
        0x69C7: "mov qword ptr [rdi+0x38],rax",
        0x69F3: "mov qword ptr [rdi+0x38],rcx",
    },
    "registry_callback_0x38540": {
        0x3854A: "movsd xmm2,qword ptr [r9]",
        0x3854F: "mov rax,rcx",
        0x38552: "mov rbx,rdx",
        0x38555: "lea rcx,[rsp+0x38]",
        0x3855A: "mov rdx,r8",
        0x3855D: "call qword ptr [rax+0x8]",
        0x38560: "mov rcx,qword ptr [rax]",
        0x3856A: "mov qword ptr [rbx],rcx",
    },
    "slimmable_builder_0xc5610": {
        0xC5632: "movaps xmm6,xmm2",
        0xC5656: "lea rax,[rip+0x18183b]",
        0xC565D: "mov qword ptr [rdi],rax",
        0xC56A4: "movsd qword ptr [rdi+0x18],xmm6",
        0xC56A9: "mov qword ptr [rsi],rdi",
    },
    "slimmable_virtual_method_0xc56d0": {
        0xC570F: "movaps xmm8,xmm3",
        0xC5B83: "movaps xmm2,xmm8",
        0xC5B8E: "call 0x1800c5f40",
        0xC5B99: "mov qword ptr [rbx],rax",
    },
    "slimmable_result_constructor_0xc5f40": {
        0xC5F73: "movaps xmm7,xmm2",
        0xC5F90: "movsd qword ptr [rcx+0x18],xmm2",
        0xC5FE5: "lea rax,[rip+0x180ec4]",
        0xC5FEC: "mov qword ptr [rdi],rax",
    },
}


def read_pointer(data: bytes, slot_rva: int, target_rva: int) -> str:
    """Exact PE file-backed absolute qword; refuse guessed/zero pointers."""
    value = struct.unpack("<Q", stage72.pe_file_bytes(data, slot_rva, 8))[0]
    if value != BASE + target_rva:
        raise ValueError(f"PE vtable slot mismatch at {slot_rva:#x}: {value:#x}")
    return f"0x{value - BASE:x}"


def read_literal(data: bytes, rva: int, expected: str, declared_length: int) -> str:
    """Read bounded original PE string in chunks due to 16-byte section gate."""
    want = expected.encode("ascii") + b"\0"
    if len(want) != declared_length + 1:
        raise ValueError("Registration literal byte length changed")
    assembled = b"".join(stage72.pe_file_bytes(data, rva + offset,
                        min(16, len(want) - offset))
                        for offset in range(0, len(want), 16))
    if assembled != want:
        raise ValueError(f"Original PE literal mismatch at {rva:#x}")
    return expected


def verify_registration_links(insns: dict[int, str], data: bytes) -> dict:
    validated = stage72.verify_pins(PINS, insns)
    if 0x30 + 0x38 != 0x68:
        raise ValueError("Registry node callback field arithmetic changed")
    entries = {}
    for name, (entry, literal_rva, count, builder_rva) in REGISTRATIONS.items():
        key = read_literal(data, literal_rva, name, count)
        entries[name] = {
            "registration_function_rva": f"0x{entry:x}",
            "original_key_literal_rva": f"0x{literal_rva:x}",
            "verified_exact_key": key,
            "builder_function_rva": f"0x{builder_rva:x}",
            "registration_insert_call_rva": f"0x{entry + 0xc2:x}",
            "runtime_registration_occurrence_verified": False,
            "selected_by_specific_stage64_file": False,
        }
    return {"validated": validated, "registered_candidates": entries,
            "callback_method_rva": read_pointer(data, WRAPPER_VTABLE_RVA + 0x10,
                                                WRAPPER_CALLBACK_RVA),
            "slimmable_virtual_method_rva": read_pointer(data, SLIMMABLE_VTABLE_RVA + 8,
                                                         SLIMMABLE_VIRTUAL_METHOD_RVA)}


def audit(dll: Path, objdump: str | None = None) -> dict:
    previous = stage76.audit(dll, objdump)
    if previous["status"] != stage76.STATUS or previous["claims"][
            "stage64_factory_or_constructed_object_identified"]:
        raise ValueError("Stage76 unresolved exact-source registry gate changed")
    if previous["registry_access"]["registry_entries_enumerated"] or previous[
            "registry_access"]["registry_callback_target_resolved"]:
        raise ValueError("Stage76 dynamic registry boundary unexpectedly changed")

    data = dll.read_bytes()
    pe = stage72.previous.PEFunctions(data)
    tool, backend = stage72.select_objdump(objdump)
    insns = {}
    bounds = {}
    for label, entry in OWNER_STARTS.items():
        owner = pe.owner(entry)
        if owner.start != entry:
            raise ValueError(f"Stage77 .pdata function entry mismatch: {entry:#x}")
        bounds[label] = [f"0x{owner.start:x}", f"0x{owner.end:x}"]
        insns.update(stage72.read_disassembly(dll, tool, backend, owner.start, owner.end))
    verified = verify_registration_links(insns, data)

    return {
        "stage": 77,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": DLL_SHA256,
        "disassembler_backend": backend,
        "prior_stage76_status_verified": previous["status"],
        "verified_native_instruction_count": sum(map(len, verified["validated"].values())),
        "verified_instruction_groups": verified["validated"],
        "pdata_function_bounds": bounds,
        "named_static_registrations": verified["registered_candidates"],
        "callback_bridge": {
            "registration_insert_function_rva": "0x35ee0",
            "insert_hash": "0x35f3d..0x35f72 source FNV-1a 64-bit matches Stage76 read hash",
            "duplicate_or_error_branch": "0x36035/0x36038 may branch away from insertion; runtime registration outcome unobserved",
            "copy_into_node": "0x36050 node -> RBX, 0x36055 RBX+=0x30, 0x36081 -> 0x69a0 copying callback-holder at +0x38 (=node+0x68)",
            "lookup_node_callback_field": "0x3f70f reads [node+0x68] before 0x3f731 indirect call",
            "wrapper_vtable_rva": "0x246ef0",
            "verified_wrapper_slot_0x10_method_rva": verified["callback_method_rva"],
            "wrapper_method": "0x3854a f64 into XMM2; 0x3855d CALL [wrapper+0x8] invokes registered builder; 0x3856a transfers result pointer",
            "runtime_wrapper_vtable_proven_for_stage64": False,
        },
        "extra_slimmable_candidate": {
            "builder_rva": "0xc5610",
            "factory_vtable_install": "0xc5656/0xc565d vtable RVA 0x246e98",
            "verified_factory_slot_0x8_method_rva": verified["slimmable_virtual_method_rva"],
            "factory_rate_write": "0xc56a4 MOVSD [RDI+0x18],XMM6 saved from incoming XMM2",
            "method_to_result_constructor": "0xc570f XMM8=XMM3; 0xc5b83 XMM2=XMM8; 0xc5b8e CALL 0xc5f40",
            "result_rate_write": "0xc5f90 MOVSD [RCX+0x18],XMM2",
            "not_in_stage75_four_candidate_set": True,
            "specific_stage64_slimmable_path_selected": False,
        },
        "claims": {
            "original_dll_executed": False,
            "four_static_name_to_builder_registrations_verified": True,
            "all_runtime_registry_entries_enumerated": False,
            "named_wrapper_callback_source_chain_verified": True,
            "fifth_slimmable_vtable_and_result_f64_writer_verified": True,
            "specific_stage64_registry_key_identified": False,
            "specific_stage64_factory_selected": False,
            "specific_stage64_result_object_alias_proven": False,
            "specific_stage64_48000_source_rate_verified": False,
            "complete_vendor_antialiasing_verified": False,
            "new_hook_or_dsp_patch": False,
        },
        "next_gate": "Reconstruct source architecture/name provenance at the actual NAM→CLO entry, then assess whether Stage64 file metadata fixes a registered key. Do not claim a runtime key or hook automatically.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--objdump", default=None)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out and args.out.resolve() == args.dll.resolve():
        raise ValueError("Refusing to overwrite original DLL")
    report = audit(args.dll, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage": 77,
        "status": report["status"],
        "verified_native_instruction_count": report["verified_native_instruction_count"],
        "named_registration_builder_rvas": {name: v["builder_function_rva"]
            for name, v in report["named_static_registrations"].items()},
        "wrapper_callback_rva": report["callback_bridge"]["verified_wrapper_slot_0x10_method_rva"],
        "fifth_slimmable_factory_method": report["extra_slimmable_candidate"]["verified_factory_slot_0x8_method_rva"],
        "specific_stage64_factory_selected": False,
        "full_report_path": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            struct.error, UnicodeDecodeError) as exc:
        print("[STAGE77 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
