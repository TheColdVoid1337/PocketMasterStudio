#!/usr/bin/env python3
"""Stage83: original PE-backed SlimmableContainer selector and child routing.

Never load/execute the vendor DLL or evaluate private NAM weights. Exact
source control flow is not evidence of the historical Stage64 live selector.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage82"))
import audit_slimmable_submodels as stage82

stage81 = stage82.stage81
stage80 = stage82.stage80
stage77 = stage82.stage77
stage72 = stage82.stage72

STATUS = "STATIC_SLIMMABLE_THRESHOLD_SELECTOR_AND_CHILD_ROUTING_VERIFIED"
PRIMARY_VTABLE_RVA = 0x246EB0
SECONDARY_VTABLE_RVA = 0x246F30

# PE-backed pointer slot offsets, independently verified against Stage82's
# constructor installation of these two *different* native vtables.
VTABLE_SLOTS = {
    "primary_selected_virtual_0x8": (PRIMARY_VTABLE_RVA + 0x8, 0xC5F00),
    "primary_selected_virtual_0x10": (PRIMARY_VTABLE_RVA + 0x10, 0xC5F20),
    "primary_selected_virtual_0x18": (PRIMARY_VTABLE_RVA + 0x18, 0xC5D10),
    "primary_selected_virtual_0x20": (PRIMARY_VTABLE_RVA + 0x20, 0xC5E10),
    "primary_all_children_virtual_0x28": (PRIMARY_VTABLE_RVA + 0x28, 0xC5EB0),
    "secondary_threshold_selector_virtual_0x8": (SECONDARY_VTABLE_RVA + 0x8, 0xC5D30),
}

# Source spans: the .pdata entries cover methods with Win64 unwind metadata;
# the three tiny tail-jump leaf functions do not have their own .pdata entry.
SOURCE_OWNERS = {
    "container_constructor": 0xC5F40,
    "threshold_selector": 0xC5D30,
    "selected_reset": 0xC5E10,
    "all_children_flag": 0xC5EB0,
}
LEAF_RANGES = {
    "selected_virtual_0x18": (0xC5D10, 0xC5D2A),
    "selected_virtual_0x8": (0xC5F00, 0xC5F1A),
    "selected_virtual_0x10": (0xC5F20, 0xC5F37),
}

PINS = {
    "container_constructor": {
        0xC5FE5: "lea rax,[rip+0x180ec4]",
        0xC5FEC: "mov qword ptr [rdi],rax",
        0xC5FEF: "lea rax,[rip+0x180f3a]",
        0xC5FF6: "mov qword ptr [rdi+0x50],rax",
        0xC6009: "mov qword ptr [rdi+0x58],rax",
        0xC6028: "mov qword ptr [rdi+0x70],rbp",
    },
    "threshold_selector": {
        0xC5D44: "mov rbx,rcx",
        0xC5D47: "mov rdx,qword ptr [rcx+0x8]",
        0xC5D4B: "mov rcx,qword ptr [rcx+0x10]",
        0xC5D52: "sar rcx,0x4",
        0xC5D56: "lea rdi,[rcx-0x1]",
        0xC5D61: "movsd xmm0,qword ptr [rdx]",
        0xC5D65: "comisd xmm0,xmm1",
        0xC5D69: "ja 0x1800c5d79",
        0xC5D6B: "inc rax",
        0xC5D6E: "add rdx,0x10",
        0xC5D7C: "mov rax,qword ptr [rbx+0x20]",
        0xC5D80: "cmp rdi,rax",
        0xC5D83: "je 0x1800c5df1",
        0xC5DA1: "mov rax,qword ptr [rbx+0x20]",
        0xC5DA5: "cmp rdi,rax",
        0xC5DBC: "mov rcx,rdi",
        0xC5DBF: "add rcx,rcx",
        0xC5DC2: "mov rax,qword ptr [rbx+0x8]",
        0xC5DC6: "mov rcx,qword ptr [rax+rcx*8+0x8]",
        0xC5DCE: "mov r8d,dword ptr [rbx-0x20]",
        0xC5DD2: "call qword ptr [rax+0x20]",
        0xC5DD5: "mov qword ptr [rbx+0x20],rdi",
    },
    "selected_virtual_0x18": {
        0xC5D13: "mov rcx,qword ptr [rcx+0x70]",
        0xC5D17: "mov rax,qword ptr [rax+0x58]",
        0xC5D1E: "mov rcx,qword ptr [rax+rcx*8+0x8]",
        0xC5D26: "rex.w jmp qword ptr [rax+0x18]",
    },
    "selected_reset": {
        0xC5E4E: "movsd qword ptr [rbx+0x28],xmm6",
        0xC5E53: "mov byte ptr [rbx+0x20],0x1",
        0xC5E57: "mov dword ptr [rbx+0x30],edi",
        0xC5E5A: "mov rcx,qword ptr [rbx+0x70]",
        0xC5E61: "mov rax,qword ptr [rbx+0x58]",
        0xC5E65: "mov rcx,qword ptr [rax+rcx*8+0x8]",
        0xC5E73: "call qword ptr [rax+0x20]",
    },
    "all_children_flag": {
        0xC5EC2: "mov byte ptr [rcx+0x34],dl",
        0xC5EC5: "mov rsi,qword ptr [rcx+0x60]",
        0xC5EC9: "mov rbx,qword ptr [rcx+0x58]",
        0xC5ED2: "mov rcx,qword ptr [rbx+0x8]",
        0xC5EDD: "call qword ptr [rax+0x28]",
        0xC5EE0: "add rbx,0x10",
    },
    "selected_virtual_0x8": {
        0xC5F03: "mov rcx,qword ptr [rcx+0x70]",
        0xC5F07: "mov rax,qword ptr [rax+0x58]",
        0xC5F0E: "mov rcx,qword ptr [rax+rcx*8+0x8]",
        0xC5F16: "rex.w jmp qword ptr [rax+0x8]",
    },
    "selected_virtual_0x10": {
        0xC5F20: "mov r10,qword ptr [rcx+0x70]",
        0xC5F24: "mov rax,qword ptr [rcx+0x58]",
        0xC5F2B: "mov rcx,qword ptr [rax+r10*8+0x8]",
        0xC5F33: "rex.w jmp qword ptr [rax+0x10]",
    },
}


def select_index(max_values: list[float], control: float) -> int:
    """Bounded model of *ordered* JA branch for a supplied, non-live value.

    Strict 'max_value > XMM1' selects that child's index; otherwise the last
    submodel is the default. Demonstrates a boundary, not a Stage64 event.
    """
    if not (isinstance(control, (float, int)) and not isinstance(control, bool)
            and math.isfinite(control)):
        raise ValueError("Control must be finite numeric")
    if not 1 <= len(max_values) <= stage81.MAX_SUBMODELS:
        raise ValueError("Invalid threshold count")
    last = -math.inf
    for value in max_values:
        if (not isinstance(value, (float, int)) or isinstance(value, bool)
                or not math.isfinite(value) or value <= last):
            raise ValueError("Thresholds not finite and ascending")
        last = value
    for index, value in enumerate(max_values):
        if value > control:
            return index
    return len(max_values) - 1


def verify_native_selection(insns: dict[int, str], dll_data: bytes) -> dict:
    matches = stage72.verify_pins(PINS, insns)
    if 0xC5FE5 + 7 + 0x180EC4 != PRIMARY_VTABLE_RVA:
        raise ValueError("Primary vtable RIP pointer changed")
    if 0xC5FEF + 7 + 0x180F3A != SECONDARY_VTABLE_RVA:
        raise ValueError("Secondary vtable RIP pointer changed")
    mapping = {
        label: stage77.read_pointer(dll_data, slot, target)
        for label, (slot, target) in VTABLE_SLOTS.items()
    }
    return {
        "validated_instruction_groups": matches,
        "first_vtable_rva": "0x246eb0",
        "second_vtable_rva": "0x246f30",
        "vtable_slots_resolved": mapping,
        "secondary_vtable_base_object_offset": "0x50",
        "array_begin_object_offset": "0x58",
        "array_end_object_offset": "0x60",
        "current_child_index_object_offset": "0x70",
        "child_stride_bytes": 16,
        "ordered_comparison": "comisd threshold,XMM1 ; JA selects first threshold strictly greater than XMM1; otherwise clamp to last child",
        "boundary_at_equal_threshold_advances_to_next_child": True,
        "index_change_conditional_child_virtual_slot": "0x20",
        "selected_child_virtual_dispatch_slots": ["0x8", "0x10", "0x18", "0x20"],
        "all_children_forwarding_virtual_slot": "0x28",
        "stage64_control_value_observed": False,
    }


def audit(dll: Path, stage64: Path, nams: dict[str, Path],
          clos: dict[str, Path], objdump: str | None = None) -> dict:
    previous = stage82.audit(dll, stage64, nams, clos, objdump)
    if (previous["status"] != stage82.STATUS or
            previous["claims"]["stage64_active_factory_verified"]):
        raise ValueError("Prior Stage82 source/runtime claim gate changed")
    structure = previous["authenticated_2203_nested_structure"]
    if [(item["max_value"], item["architecture"]) for item in structure["submodels"]] != [
            (0.5, "WaveNet"), (1.0, "WaveNet")]:
        raise ValueError("Authenticated original 2203 structure drift")
    sampled = {str(value): select_index([0.5, 1.0], value)
               for value in (-0.01, 0.0, 0.499999, 0.5, 0.75, 1.0, 1.01)}

    data = stage80.checked_file(dll, stage80.stage79.DLL_SHA256, stage82.MAX_DLL_BYTES)
    pe = stage72.previous.PEFunctions(data)
    tool, backend = stage72.select_objdump(objdump)
    insns = {}
    owners = {}
    for label, start in SOURCE_OWNERS.items():
        owner = pe.owner(start)
        if owner.start != start:
            raise ValueError("Native PE .pdata owner changed: " + label)
        owners[label] = [f"0x{owner.start:x}", f"0x{owner.end:x}"]
        insns.update(stage72.read_disassembly(dll, tool, backend, owner.start, owner.end))
    for label, (start, end) in LEAF_RANGES.items():
        try:
            pe.owner(start)
        except ValueError:
            pass  # tiny Win64 leaf routines omit .pdata entries
        else:
            raise ValueError("Previously leaf function unexpectedly has .pdata: " + label)
        insns.update(stage72.read_disassembly(dll, tool, backend, start, end))
    native = verify_native_selection(insns, data)

    return {
        "stage": 83,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": stage80.stage79.DLL_SHA256,
        "stage64_archive_sha256": stage80.stage79.STAGE64_SHA256,
        "prior_stage82_gate": previous["status"],
        "disassembler_backend": backend,
        "native_owners": owners,
        "new_instruction_count": sum(map(len, native["validated_instruction_groups"].values())),
        "native_container_selector_and_dispatch": native,
        "authenticated_fixture_2203_thresholds": [0.5, 1.0],
        "synthetic_ordered_control_examples_only": sampled,
        "attested_operator_frida_import_name": "JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam",
        "claims": {
            "static_exact_original_threshold_selector_verified": True,
            "static_native_child_vtable_routing_verified": True,
            "synthetic_boundary_value_behavior_verified": True,
            "stage64_actual_control_value_verified": False,
            "stage64_selected_child_index_verified": False,
            "stage64_selected_factory_verified": False,
            "stage64_resampler_parent_verified": False,
            "stage64_same_run_nam_clo_sha_verified": False,
            "vendor_dll_executed": False,
            "new_frida_hook_or_capture": False,
            "private_original_audio_or_weights_exported": False,
            "complete_vendor_dsp_parity_proven": False,
        },
        "next_gate": "Trace actual Stage64 control-value/selector call provenance or resolve live parent identity; static 0.5 threshold does not select a historical WaveNet.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("dll", "stage64", "nam-2203", "nam-sc20", "clo-2203", "clo-sc20"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--objdump")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    source_files = [args.dll, args.stage64, args.nam_2203, args.nam_sc20,
                    args.clo_2203, args.clo_sc20]
    if args.out and args.out.resolve() in (p.resolve() for p in source_files):
        raise ValueError("Refusing to overwrite private original input")
    result = audit(args.dll, args.stage64,
                   {"2203": args.nam_2203, "SC20": args.nam_sc20},
                   {"2203": args.clo_2203, "SC20": args.clo_sc20}, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage": 83,
        "status": result["status"],
        "new_native_instruction_pins": result["new_instruction_count"],
        "file_backed_vtable_pointer_slots": len(VTABLE_SLOTS),
        "static_slimmable_selector_verified": True,
        "historical_stage64_child_index_proven": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, UnicodeError, json.JSONDecodeError) as exc:
        print("[STAGE83 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
