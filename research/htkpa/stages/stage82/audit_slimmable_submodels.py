#!/usr/bin/env python3
"""Stage82: original PE SlimmableContainer -> nested-model dispatch.

All originals are treated as inert SHA-pinned input. This is a conditional
source path, not evidence that Stage64 selected this factory or submodel.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage81"))
import audit_sample_rate_ingress as stage81

stage80 = stage81.stage80
stage77 = stage81.stage77
stage72 = stage81.stage72

STATUS = "STATIC_SLIMMABLE_SUBMODEL_RECURSION_AND_RATE_GUARDS_VERIFIED"
MAX_DLL_BYTES = 16_000_000

SOURCE_OWNERS = {
    "slimmable_virtual_method": 0xC56D0,
    "slimmable_result_constructor": 0xC5F40,
    "nested_model_packet_builder": 0xCC2B0,
}

KEYS = {
    "submodels": (0x18F438, 9, 0xC572E, 0xC5735),
    "max_value": (0x18F428, 9, 0xC5936, 0xC594E),
    "model": (0x18CD34, 5, 0xC5A0F, 0xC5A27),
}

PINS = {
    "slimmable_virtual_method": {
        0xC570F: "movaps xmm8,xmm3",
        0xC572A: "add rcx,0x8",
        0xC572E: "lea rdx,[rip+0xc9d03]",
        0xC5735: "call 0x180037910",
        0xC5742: "call 0x1800365b0",
        0xC574D: "cmp al,0x2",
        0xC5936: "lea rdx,[rip+0xc9aeb]",
        0xC594E: "call 0x1800364c0",
        0xC5A0F: "lea rdx,[rip+0xc731e]",
        0xC5A27: "call 0x1800364c0",
        0xC5A7F: "call 0x1800cc2b0",
        0xC5A85: "movsd qword ptr [rbp+0x8],xmm6",
        0xC5AA7: "movsd qword ptr [rdx],xmm6",
        0xC5AAE: "mov qword ptr [rdx+0x8],rax",
        0xC5B83: "movaps xmm2,xmm8",
        0xC5B8E: "call 0x1800c5f40",
        0xC5B99: "mov qword ptr [rbx],rax",
    },
    "slimmable_result_constructor": {
        0xC5F73: "movaps xmm7,xmm2",
        0xC5F90: "movsd qword ptr [rcx+0x18],xmm2",
        0xC6006: "mov rax,qword ptr [r14]",
        0xC6009: "mov qword ptr [rdi+0x58],rax",
        0xC606A: "comisd xmm0,qword ptr [rax+rcx*1]",
        0xC606F: "jae 0x1800c626c",
        0xC6085: "movsd xmm0,qword ptr [rip+0x18688b]",
        0xC608D: "comisd xmm0,qword ptr [r8-0x10]",
        0xC6093: "ja 0x1800c6249",
        0xC609E: "movsd xmm0,qword ptr [rip+0x186e2a]",
        0xC60B0: "mov rax,qword ptr [rcx+0x8]",
        0xC60B4: "movsd xmm6,qword ptr [rax+0x18]",
        0xC60B9: "ucomisd xmm6,xmm7",
        0xC60C1: "ucomisd xmm6,xmm0",
        0xC60C9: "ucomisd xmm7,xmm0",
        0xC60D3: "jne 0x1800c6193",
        0xC60D9: "add rcx,0x10",
    },
    "nested_model_packet_builder": {
        0xCC2E5: "mov rdi,rdx",
        0xCC343: "lea rdx,[rsp+0x30]",
        0xCC348: "mov rcx,rdi",
        0xCC34B: "call 0x1800cb200",
        0xCC3A2: "movzx r8d,bx",
        0xCC3AD: "call 0x1800ca760",
    },
}

FLOAT_CONSTANTS = {
    "required_last_maximum": (0x24C918, 1.0, 0xC6085, 0x18688B, 8),
    "unknown_rate_sentinel": (0x24CED0, -1.0, 0xC609E, 0x186E2A, 8),
}


def verify_nested_source(insns: dict[int, str], dll_data: bytes) -> dict:
    matches = stage72.verify_pins(PINS, insns)
    for key, (literal_rva, size, load_rva, _lookup_rva) in KEYS.items():
        stage77.read_literal(dll_data, literal_rva, key, size)
        # The exact LEA instruction is pinned above, including displacement.
        instruction = insns.get(stage72.BASE + load_rva)
        expected = stage72.normalize_asm(
            f"lea rdx,[rip+0x{literal_rva - load_rva - 7:x}]")
        if instruction != expected:
            raise ValueError("Incorrect PE key RIP target: " + key)

    constants = {}
    for label, (rva, expected, load, displacement, length) in FLOAT_CONSTANTS.items():
        if load + length + displacement != rva:
            raise ValueError("Native constant RIP displacement changed: " + label)
        actual = struct.unpack("<d", stage72.pe_file_bytes(dll_data, rva, 8))[0]
        if actual != expected:
            raise ValueError("Native constant changed: " + label)
        constants[label] = actual

    return {
        "validated_instruction_groups": matches,
        "json_member_literals": {
            key: f"0x{value[0]:x}" for key, value in KEYS.items()},
        "nested_model_packet_entry_rva": "0xcc2b0",
        "nested_model_parser_rva": "0xcb200",
        "nested_model_packet_dispatch_rva": "0xca760",
        "container_result_constructor_rva": "0xc5f40",
        "container_rate_field_offset": "0x18",
        "nested_rate_field_offset": "0x18",
        "element_record_layout": "16 bytes: f64 max_value, then nested-model pointer",
        "float_constants": constants,
        "rate_check": "In loop, compare nested +0x18 with container rate or -1.0; conditional error path for mismatch",
        "threshold_check": "Ascending adjacent f64s; last value must be at least 1.0 on the decoded path",
        "static_path_conditional": True,
    }


def audit(dll: Path, stage64: Path, nams: dict[str, Path],
          clos: dict[str, Path], objdump: str | None = None) -> dict:
    previous = stage81.audit(dll, stage64, nams, clos, objdump)
    if previous["status"] != stage81.STATUS:
        raise ValueError("Prior Stage81 source gate changed")
    if previous["claims"]["stage64_selected_submodel_or_factory_verified"]:
        raise ValueError("Unexpected Stage81 runtime factory claim")

    data = stage80.checked_file(dll, stage80.stage79.DLL_SHA256, MAX_DLL_BYTES)
    pe = stage72.previous.PEFunctions(data)
    tool, backend = stage72.select_objdump(objdump)
    instructions = {}
    owners = {}
    for label, start in SOURCE_OWNERS.items():
        owner = pe.owner(start)
        if owner.start != start:
            raise ValueError("Native function owner changed: " + label)
        owners[label] = [f"0x{owner.start:x}", f"0x{owner.end:x}"]
        instructions.update(stage72.read_disassembly(dll, tool, backend, owner.start, owner.end))
    verified = verify_nested_source(instructions, data)

    return {
        "stage": 82,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": stage80.stage79.DLL_SHA256,
        "stage64_archive_sha256": stage80.stage79.STAGE64_SHA256,
        "prior_stage81_source_gate": previous["status"],
        "disassembler_backend": backend,
        "native_owners": owners,
        "new_verified_instruction_count": sum(map(len, verified["validated_instruction_groups"].values())),
        "slimmable_nested_source": verified,
        "authenticated_2203_nested_structure": previous["authenticated_model_structure"]["2203"],
        "operator_attested_import_nam": "JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam",
        "claims": {
            "exact_original_pe_static_nested_path_verified": True,
            "nested_constructor_rate_guards_verified": True,
            "all_stage64_frida_nam_imports_operator_attested_2203": True,
            "stage64_active_factory_verified": False,
            "stage64_selected_nested_model_verified": False,
            "stage64_runtime_rate_verified": False,
            "stage64_same_run_nam_clo_hash_binding_verified": False,
            "original_vendor_dll_executed": False,
            "frida_capture_added": False,
            "models_or_weights_exposed": False,
            "full_vendor_dsp_or_resampler_parity_proven": False,
        },
        "next_gate": "Relate conditional nested factory construction to an authenticated Stage64 runtime dispatch; source analysis alone cannot select a live submodel.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("dll", "stage64", "nam-2203", "nam-sc20", "clo-2203", "clo-sc20"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--objdump")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    inputs = [args.dll, args.stage64, args.nam_2203, args.nam_sc20,
              args.clo_2203, args.clo_sc20]
    if args.out and args.out.resolve() in (p.resolve() for p in inputs):
        raise ValueError("Refusing to overwrite private original input")
    result = audit(args.dll, args.stage64,
                   {"2203": args.nam_2203, "SC20": args.nam_sc20},
                   {"2203": args.clo_2203, "SC20": args.clo_sc20}, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage": 82,
        "status": result["status"],
        "new_instruction_pins": result["new_verified_instruction_count"],
        "nested_packet_dispatch_static_path": True,
        "stage64_active_factory_or_selected_submodel_proven": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, UnicodeError, json.JSONDecodeError) as exc:
        print("[STAGE82 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
