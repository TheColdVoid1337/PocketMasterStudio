#!/usr/bin/env python3
"""Stage84: file-backed MSVC RTTI and successful container default child.

All originals are read-only. A constructor's initial child is *not* an
observation of the historical Stage64 model instance or selector calls.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage83"))
import audit_slimmable_selection as stage83

stage72 = stage83.stage72
stage77 = stage83.stage77
stage80 = stage83.stage80
BASE = stage72.BASE
STATUS = "STATIC_CONTAINER_RTTI_AND_LAST_CHILD_CONSTRUCTOR_DEFAULT_VERIFIED"

# The vtable[-1] complete-object-locator slots, checked independently of
# Stage83's method targets. All addresses are original image-relative RVAs.
COL_POINTERS = {
    "primary_dsp_interface": (0x246EA8, 0x255798),
    "secondary_slimmable_interface": (0x246F28, 0x2554B8),
}
CLASS_RVA = 0x2A2600
HIERARCHY_RVA = 0x255940
BASE_ARRAY_RVA = 0x255480
BASE_DESCRIPTORS = (
    (0x255A08, CLASS_RVA, 0x0, "ContainerModel", ".?AVContainerModel@container@nam@@"),
    (0x2555F8, 0x2A2780, 0x0, "DSP", ".?AVDSP@nam@@"),
    (0x255958, 0x2A2800, 0x50, "SlimmableModel", ".?AVSlimmableModel@nam@@"),
)

# These constructor instructions are additional to the Stage82-83 pins.
# In the nonempty, validated success path R9 is the 16-byte record count;
# after resetting +0x70 to zero, the constructor overwrites it with R9-1.
PINS = {
    "container_constructor_default": {
        0xC6028: "mov qword ptr [rdi+0x70],rbp",
        0xC603A: "mov rcx,qword ptr [rdi+0x58]",
        0xC603E: "mov r8,qword ptr [rdi+0x60]",
        0xC6042: "cmp rcx,r8",
        0xC6045: "je 0x1800c6226",
        0xC6050: "mov r9,r8",
        0xC6053: "sub r9,rcx",
        0xC6056: "sar r9,0x4",
        0xC6099: "cmp rcx,r8",
        0xC609C: "je 0x1800c60e2",
        0xC60D9: "add rcx,0x10",
        0xC60DD: "cmp rcx,r8",
        0xC60E0: "jne 0x1800c60b0",
        0xC60E2: "lea rax,[r9-0x1]",
        0xC60E6: "xchg qword ptr [rdi+0x70],rax",
        0xC615B: "mov rax,rdi",
    },
}


def _pe(data: bytes, rva: int, length: int) -> bytes:
    """Bounded reader for larger file-backed MSVC RTTI structs."""
    return b"".join(stage72.pe_file_bytes(data, rva + at, min(16, length - at))
                    for at in range(0, length, 16))


def _locator(data: bytes, rva: int, offset: int) -> dict:
    signature, obj_offset, cd_offset, type_rva, hierarchy, self_rva = struct.unpack(
        "<6I", _pe(data, rva, 24))
    if (signature, obj_offset, cd_offset, type_rva, hierarchy, self_rva) != (
            1, offset, 0, CLASS_RVA, HIERARCHY_RVA, rva):
        raise ValueError(f"MSVC complete-object-locator mismatch at {rva:#x}")
    return {"rva": f"0x{rva:x}", "offset_within_complete_object": f"0x{obj_offset:x}",
            "class_type_descriptor_rva": f"0x{type_rva:x}"}


def verify_rtti(data: bytes) -> dict:
    slots = {label: stage77.read_pointer(data, slot, target)
             for label, (slot, target) in COL_POINTERS.items()}
    locators = {
        "primary_dsp_interface": _locator(data, 0x255798, 0),
        "secondary_slimmable_interface": _locator(data, 0x2554B8, 0x50),
    }
    sig, attributes, count, array_rva = struct.unpack("<4I", _pe(data, HIERARCHY_RVA, 16))
    if (sig, attributes, count, array_rva) != (0, 1, 3, BASE_ARRAY_RVA):
        raise ValueError("MSVC class-hierarchy descriptor mismatch")
    entries = struct.unpack("<3I", _pe(data, BASE_ARRAY_RVA, 12))
    if entries != tuple(record[0] for record in BASE_DESCRIPTORS):
        raise ValueError("MSVC base-class array mismatch")
    bases = {}
    for descriptor, type_rva, displacement, label, decorated in BASE_DESCRIPTORS:
        # MSVC 64-bit BaseClassDescriptor: TypeDescriptor RVA, count, PMD,
        # attributes, hierarchy RVA. The PMD's pdisp must be -1 (nonvirtual).
        type_ptr, child_bases, mdisp, pdisp, vdisp, attrs, _chd = struct.unpack(
            "<IIiiiII", _pe(data, descriptor, 28))
        if (type_ptr, child_bases, mdisp, pdisp, vdisp, attrs) != (
                type_rva, 2 if label == "ContainerModel" else 0,
                displacement, -1, 0, 0x40):
            raise ValueError(f"MSVC base-class displacement mismatch: {label}")
        stage77.read_literal(data, type_rva + 0x10, decorated, len(decorated))
        bases[label] = {"type_descriptor_rva": f"0x{type_rva:x}",
                        "object_offset": f"0x{displacement:x}",
                        "native_msvc_name": decorated}
    return {"original_col_slots": slots, "locators": locators,
            "hierarchy_base_count": count, "verified_bases": bases,
            "secondary_interface_is_nam_slimmable_model": True}


def default_child_index(maxima: list[float]) -> int:
    """Model *constructor success-path default*, not a Stage64 observation."""
    stage83.select_index(maxima, 0.0)  # reuse finite/ascending/count validation
    if maxima[-1] < 1.0:
        raise ValueError("Constructor requires final threshold >= 1.0")
    return len(maxima) - 1


def verify_constructor(insns: dict[int, str]) -> dict:
    validated = stage72.verify_pins(PINS, insns)
    return {"validated_instruction_groups": validated,
            "nonempty_constructor_path": "0xc6045 jumps to error path 0xc6226 if no records",
            "record_count": "R9=(array_end-array_begin)>>4 at 0xc6050..0xc6056",
            "entry_index_zeroed": "0xc6028 writes +0x70 = 0 before validation",
            "success_path_selected_index": "0xc60e2 computes R9-1; 0xc60e6 atomically exchanges +0x70",
            "selector_may_later_change_index": True,
            "stage64_live_initial_index_observed": False}


def audit(dll: Path, stage64: Path, nams: dict[str, Path],
          clos: dict[str, Path], objdump: str | None = None) -> dict:
    previous = stage83.audit(dll, stage64, nams, clos, objdump)
    if (previous["status"] != stage83.STATUS or
            previous["claims"]["stage64_selected_child_index_verified"] or
            previous["claims"]["stage64_resampler_parent_verified"]):
        raise ValueError("Stage83 source-only claim boundary changed")
    maxima = previous["authenticated_fixture_2203_thresholds"]
    if maxima != [0.5, 1.0]:
        raise ValueError("Prior authenticated 2203 thresholds changed")
    data = stage80.checked_file(dll, stage80.stage79.DLL_SHA256, stage83.stage82.MAX_DLL_BYTES)
    pe = stage72.previous.PEFunctions(data)
    owner = pe.owner(0xC5F40)
    if owner.start != 0xC5F40:
        raise ValueError("Constructor PE function-owner mismatch")
    tool, backend = stage72.select_objdump(objdump)
    instructions = stage72.read_disassembly(dll, tool, backend, owner.start, owner.end)
    result = verify_constructor(instructions)
    rtti = verify_rtti(data)
    return {
        "stage": 84, "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS, "original_dll_sha256": stage80.stage79.DLL_SHA256,
        "stage64_archive_sha256": stage80.stage79.STAGE64_SHA256,
        "prior_stage83_gate": previous["status"],
        "disassembler_backend": backend,
        "native_constructor_owner": [f"0x{owner.start:x}", f"0x{owner.end:x}"],
        "new_instruction_count": sum(map(len, result["validated_instruction_groups"].values())),
        "constructor_default": result,
        "msvc_rtti_multiple_inheritance": rtti,
        "authenticated_fixture_2203_thresholds": maxima,
        "synthetic_2203_constructor_default_index": default_child_index(maxima),
        "operator_attested_stage64_nam_filename": "JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam",
        "claims": {
            "original_slimmable_model_base_interface_verified": True,
            "static_constructor_last_child_default_verified": True,
            "historical_stage64_constructed_container_verified": False,
            "historical_stage64_initial_child_index_verified": False,
            "historical_stage64_selector_invocation_or_xmm1_verified": False,
            "historical_stage64_active_child_verified": False,
            "historical_stage64_resampler_parent_verified": False,
            "same_run_nam_clo_sha_verified": False,
            "original_dll_executed": False,
            "new_frida_capture": False,
            "complete_vendor_dsp_parity_verified": False,
        },
        "next_gate": "Observe authentic selector call/control or object identity at Stage64; constructor last-child default is conditional, not a live Stage64 claim.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ("dll", "stage64", "nam-2203", "nam-sc20", "clo-2203", "clo-sc20"):
        p.add_argument("--" + flag, required=True, type=Path)
    p.add_argument("--objdump")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    originals = (args.dll, args.stage64, args.nam_2203, args.nam_sc20,
                 args.clo_2203, args.clo_sc20)
    if args.out and args.out.resolve() in (path.resolve() for path in originals):
        raise ValueError("Refusing to overwrite authenticated private original")
    report = audit(args.dll, args.stage64,
                   {"2203": args.nam_2203, "SC20": args.nam_sc20},
                   {"2203": args.clo_2203, "SC20": args.clo_sc20}, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": 84, "status": report["status"],
                      "new_native_instruction_pins": report["new_instruction_count"],
                      "file_backed_rtti_bases": len(BASE_DESCRIPTORS),
                      "2203_constructor_default_child_index": report["synthetic_2203_constructor_default_index"],
                      "stage64_active_child_proven": False}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, UnicodeError, json.JSONDecodeError,
            struct.error) as exc:
        print("[STAGE84 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
