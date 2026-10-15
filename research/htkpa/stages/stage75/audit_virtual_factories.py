#!/usr/bin/env python3
"""Stage75: four file-backed virtual factory slot candidates to f64 field writer.

Original vendor DLL is an exact-SHA read-only PE. A vtable candidate is not
proof of a particular live factory instance or Stage64 dynamic call target.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage74"))
import audit_metadata_bridge as stage74

stage73 = stage74.stage73
stage72 = stage74.stage72
BASE = stage74.BASE
DLL_SHA256 = stage74.DLL_SHA256
STATUS = "FOUR_STATIC_FACTORY_CHAINS_TO_F64_FIELD_WRITER_RUNTIME_TARGET_UNPROVEN"

FACTORY_CHAINS = {
    "family_a": {
        "vtable_rva": 0x246FB0, "method_rva": 0xC64A0,
        "caller_rva": 0xC6527, "constructor_rva": 0xC76C0, "base_call_rva": 0xC7737,
        "result_store_rva": 0xC652D,
    },
    "family_b": {
        "vtable_rva": 0x247708, "method_rva": 0xCC730,
        "caller_rva": 0xCC798, "constructor_rva": 0xCD220, "base_call_rva": 0xCD261,
        "result_store_rva": 0xCC79E,
    },
    "family_c": {
        "vtable_rva": 0x247BA8, "method_rva": 0xD0C10,
        "caller_rva": 0xD0CF9, "constructor_rva": 0xD4F40, "base_call_rva": 0xD4FF3,
        "result_store_rva": 0xD0CFF,
    },
    "family_d": {
        "vtable_rva": 0x247CC0, "method_rva": 0xD9B90,
        "caller_rva": 0xDA83D, "constructor_rva": 0xDB7D0, "base_call_rva": 0xDB81F,
        "result_store_rva": 0xDA843,
    },
}

PINS = {
    "virtual_dispatch_0xcab10": {
        0xCAB49: "mov rcx,qword ptr [rdx]",
        0xCAB4C: "mov rax,qword ptr [rcx]",
        0xCAB4F: "mov r9,qword ptr [rax+0x8]",
        0xCAB53: "movsd xmm3,qword ptr [rbx+0x20]",
        0xCAB81: "call r9",
    },
    "base_rate_constructor_0xca430": {
        0xCA43B: "lea rax,[rip+0x17cbd6]",
        0xCA442: "mov qword ptr [rcx],rax",
        0xCA44B: "movsd qword ptr [rcx+0x18],xmm3",
        0xCA4A9: "mov rax,r10",
    },
    "family_a_method_0xc64a0": {
        0xC64C4: "movaps xmm6,xmm3",
        0xC64FA: "movsd qword ptr [rsp+0x40],xmm6",
        0xC6527: "call 0x1800c76c0",
        0xC652D: "mov qword ptr [rsi],rax",
    },
    "family_a_constructor_0xc76c0": {
        0xC772B: "movsd xmm3,qword ptr [rsp+0x130]",
        0xC7737: "call 0x1800ca430",
        0xC773C: "lea rax,[rip+0x17f885]",
    },
    "family_b_method_0xcc730": {
        0xCC754: "movaps xmm6,xmm3",
        0xCC776: "movsd qword ptr [rsp+0x38],xmm6",
        0xCC798: "call 0x1800cd220",
        0xCC79E: "mov qword ptr [rsi],rax",
    },
    "family_b_constructor_0xcd220": {
        0xCD255: "movsd xmm3,qword ptr [rsp+0xe8]",
        0xCD261: "call 0x1800ca430",
        0xCD266: "lea rax,[rip+0x17a4b3]",
    },
    "family_c_method_0xd0c10": {
        0xD0C38: "movaps xmm6,xmm3",
        0xD0CC3: "movsd qword ptr [rsp+0x40],xmm6",
        0xD0CEE: "movss xmm3,dword ptr [rdi+0x28]",
        0xD0CF9: "call 0x1800d4f40",
        0xD0CFF: "mov qword ptr [rsi],rax",
    },
    "family_c_constructor_0xd4f40": {
        0xD4FEB: "movsd xmm3,qword ptr [rbp+0x1a0]",
        0xD4FF3: "call 0x1800ca430",
        0xD4FF8: "lea rax,[rip+0x172bc1]",
    },
    "family_d_method_0xd9b90": {
        0xD9BCE: "movaps xmm7,xmm3",
        0xDA7FC: "movsd qword ptr [rsp+0x40],xmm7",
        0xDA83D: "call 0x1800db7d0",
        0xDA843: "mov qword ptr [r13+0x0],rax",
    },
    "family_d_constructor_0xdb7d0": {
        0xDB80D: "movsd xmm3,qword ptr [rbp+0x80]",
        0xDB81F: "call 0x1800ca430",
        0xDB824: "lea rax,[rip+0x16c455]",
    },
}

OWNER_STARTS = {
    "virtual_dispatch_0xcab10": 0xCAB10,
    "base_rate_constructor_0xca430": 0xCA430,
    "family_a_method_0xc64a0": 0xC64A0,
    "family_a_constructor_0xc76c0": 0xC76C0,
    "family_b_method_0xcc730": 0xCC730,
    "family_b_constructor_0xcd220": 0xCD220,
    "family_c_method_0xd0c10": 0xD0C10,
    "family_c_constructor_0xd4f40": 0xD4F40,
    "family_d_method_0xd9b90": 0xD9B90,
    "family_d_constructor_0xdb7d0": 0xDB7D0,
}


def read_exact_virtual_slot(data: bytes, vtable_rva: int, expected_method_rva: int) -> dict:
    """Read the actual PE-backed qword at vtable+8; fail closed on changes."""
    method_va = struct.unpack("<Q", stage72.pe_file_bytes(data, vtable_rva + 8, 8))[0]
    if method_va != BASE + expected_method_rva:
        raise ValueError(f"Original PE virtual slot mismatch at {vtable_rva + 8:#x}: {method_va:#x}")
    return {
        "factory_vtable_rva": f"0x{vtable_rva:x}",
        "verified_slot_rva": f"0x{vtable_rva + 8:x}",
        "virtual_method_rva": f"0x{expected_method_rva:x}",
        "source": "Original PE file-backed absolute 64-bit function pointer",
    }


def audit(dll: Path, objdump: str | None = None) -> dict:
    previous = stage74.audit(dll, objdump)
    if previous["status"] != stage74.STATUS or not previous["claims"]["local_nonnull_gate_verified"]:
        raise ValueError("Stage74 accepted source-only metadata gate changed")
    if previous["nested_metadata_to_virtual_factory"]["virtual_callee_target_verified"]:
        raise ValueError("Prior Stage74 virtual boundary unexpectedly changed")
    data = dll.read_bytes()
    pe = stage72.previous.PEFunctions(data)
    objdump_tool, backend = stage72.select_objdump(objdump)
    insns = {}
    for label, start in OWNER_STARTS.items():
        owner = pe.owner(start)
        if owner.start != start:
            raise ValueError(f"Stage75 function owner entry changed: {start:#x}")
        insns.update(stage72.read_disassembly(dll, objdump_tool, backend, owner.start, owner.end))
    validated = stage72.verify_pins(PINS, insns)
    slots = {label: read_exact_virtual_slot(data, item["vtable_rva"], item["method_rva"])
             for label, item in FACTORY_CHAINS.items()}
    for label, item in FACTORY_CHAINS.items():
        # Both direct edges are source-pinned; the final target is the
        # *candidate* base constructor in which +0x18 is written.
        if insns[BASE + item["caller_rva"]] != f"call 0x{BASE + item['constructor_rva']:x}":
            raise ValueError(f"{label}: intermediary constructor call changed")
        if insns[BASE + item["base_call_rva"]] != f"call 0x{BASE + 0xCA430:x}":
            raise ValueError(f"{label}: base rate constructor call changed")

    return {
        "stage": 75,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": DLL_SHA256,
        "disassembler_backend": backend,
        "prior_stage74_status_verified": previous["status"],
        "verified_native_instruction_count": sum(map(len, validated.values())),
        "verified_instruction_groups": validated,
        "source_virtual_dispatch": "0xcab49/0xcab4c object vtable; 0xcab4f slot +0x8 into R9; 0xcab53 incoming rate XMM3; 0xcab81 CALL R9",
        "candidate_vtable_method_chains": {
            name: {
                **slots[name],
                "verified_direct_method_to_constructor_call_rva": f"0x{chain['caller_rva']:x}",
                "intermediate_constructor_rva": f"0x{chain['constructor_rva']:x}",
                "verified_direct_base_call_rva": f"0x{chain['base_call_rva']:x}",
                "result_object_store_rva": f"0x{chain['result_store_rva']:x}",
                "candidate_dynamic_method_selected": False,
            }
            for name, chain in FACTORY_CHAINS.items()
        },
        "base_constructor": {
            "rva": "0xca430",
            "vtable_installed": "0xca43b/0xca442 PE vtable RVA 0x247018",
            "f64_field_write": "0xca44b MOVSD [RCX+0x18],XMM3",
            "rate_reaches_writer_on_candidate_direct_chains": True,
        },
        "important_limits": {
            "four_entries_exhaust_all_possible_factory_vtables": False,
            "stage64_runtime_factory_instance_identified": False,
            "specific_call_0xcab81_targets_any_listed_method": False,
            "specific_stage64_reverse_object_is_constructed_by_base_rva_0xca430": False,
            "complete_dynamic_metadata_to_field_link_proven": False,
        },
        "claims": {
            "original_dll_executed": False,
            "four_static_vtable_slots_verified_in_original_pe": True,
            "four_direct_method_to_base_constructor_paths_verified": True,
            "f64_field_writer_exists_in_base_constructor": True,
            "actual_stage64_virtual_factory_selected": False,
            "live_stage64_whole_resampler_48000_source_proven": False,
            "complete_native_antialiasing_verified": False,
            "production_or_resampler_lab_changed": False,
        },
        "next_gate": "Trace the selected source object's factory-vtable identity into 0xcab81 through registry/lookup; if static identity remains unresolved, decide separately on metadata-only runtime observation. No automatic hook/DSP edits.",
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
        "stage": 75,
        "status": report["status"],
        "verified_native_instruction_count": report["verified_native_instruction_count"],
        "verified_factory_slot_count": len(report["candidate_vtable_method_chains"]),
        "vtable_and_method_rvas": {k: {"vtable": v["factory_vtable_rva"], "method": v["virtual_method_rva"]}
                                    for k, v in report["candidate_vtable_method_chains"].items()},
        "f64_field_writer": report["base_constructor"]["f64_field_write"],
        "actual_stage64_virtual_factory_selected": False,
        "full_report_path": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            struct.error, UnicodeDecodeError) as exc:
        print("[STAGE75 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
