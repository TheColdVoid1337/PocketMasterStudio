#!/usr/bin/env python3
"""Stage74: static incoming metadata object, f64 transfer and 48k branch.

Original pinned DLL is read only as PE bytes. Neither native code nor audio
is executed; the unresolved virtual construction is NOT silently resolved.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage73"))
import audit_incoming_rate as stage73

stage72 = stage73.stage72
BASE = stage73.BASE
DLL_SHA256 = stage73.DLL_SHA256
STATUS = "STATIC_METADATA_TO_INDIRECT_FACTORY_BRIDGE_RUNTIME_FIELD_UNPROVEN"

PINS = {
    "helper_0xe0e0_object_gate": {
        0xE17F: "xor r12d,r12d",
        0xE60C: "mov rbx,r12",
        0xE614: "mov word ptr [rsp+0x50],0x0",
        0xE682: "movzx r8d,word ptr [rsp+0x50]",
        0xE690: "lea rcx,[rsp+0x2a0]",
        0xE698: "call 0x1800cc4e0",
        0xE69D: "lea rcx,[rsp+0x38]",
        0xE6A2: "cmp rcx,rax",
        0xE6A5: "je 0x18000e6b2",
        0xE6A7: "mov rbx,qword ptr [rax]",
        0xE6AA: "mov qword ptr [rax],r12",
        0xE6AD: "mov qword ptr [rsp+0x38],rbx",
        0xE6CA: "test rbx,rbx",
        0xE6CD: "jne 0x18000e855",
        0xE850: "jmp 0x18000e5cd",
        0xE855: "movsd xmm9,qword ptr [rbx+0x18]",
        0xE9B5: "xorps xmm6,xmm6",
        0xE9B8: "comiss xmm6,xmm9",
        0xE9BC: "jb 0x18000e9f3",
        0xE9EA: "movss xmm9,dword ptr [rip+0x23e401]",
    },
    "parser_wrapper_0xcc4e0": {
        0xCC511: "movzx ebx,r8w",
        0xCC57C: "movzx r9d,bx",
        0xCC58A: "call 0x1800cae30",
        0xCC65D: "mov rax,rsi",
    },
    "metadata_marshaller_0xcae30": {
        0xCAE6D: "movzx ebx,r9w",
        0xCB026: "movsd xmm0,qword ptr [r13+0x78]",
        0xCB02C: "movsd qword ptr [rbp+0x108],xmm0",
        0xCB034: "movzx r8d,bx",
        0xCB038: "lea rdx,[rbp+0x90]",
        0xCB03F: "mov rcx,r15",
        0xCB042: "call 0x1800ca760",
    },
    "zero_mode_constructor_0xca760": {
        0xCA780: "shr ax,0x8",
        0xCA784: "test al,al",
        0xCA786: "jne 0x1800ca7a0",
        0xCA788: "call 0x1800ca810",
    },
    "intermediate_packet_0xca810": {
        0xCA83D: "mov rbx,rdx",
        0xCA8C5: "movsd xmm0,qword ptr [rbx+0x78]",
        0xCA8CA: "movsd qword ptr [rbp+0x7],xmm0",
        0xCAAAE: "lea r9,[rbp-0x19]",
        0xCAABD: "call 0x1800cab10",
    },
    "virtual_factory_bridge_0xcab10": {
        0xCAB36: "mov rbx,r9",
        0xCAB49: "mov rcx,qword ptr [rdx]",
        0xCAB4C: "mov rax,qword ptr [rcx]",
        0xCAB4F: "mov r9,qword ptr [rax+0x8]",
        0xCAB53: "movsd xmm3,qword ptr [rbx+0x20]",
        0xCAB81: "call r9",
        0xCAB8B: "mov rax,qword ptr [rsi]",
    },
}

OWNER_STARTS = {
    "helper_0xe0e0_object_gate": 0xE0E0,
    "parser_wrapper_0xcc4e0": 0xCC4E0,
    "metadata_marshaller_0xcae30": 0xCAE30,
    "zero_mode_constructor_0xca760": 0xCA760,
    "intermediate_packet_0xca810": 0xCA810,
    "virtual_factory_bridge_0xcab10": 0xCAB10,
}


def local_direct_branches_to(insns: dict[int, str], target_rva: int,
                             owner_start_rva: int, owner_end_rva: int) -> list[str]:
    """Decoded direct jumps only; no indirect/exception-edge conclusions."""
    target_va = BASE + target_rva
    result = []
    for va, asm in insns.items():
        if not BASE + owner_start_rva <= va < BASE + owner_end_rva:
            continue
        op, _, operand = asm.partition(" ")
        if not op.startswith("j") or not re.fullmatch(r"0x[0-9a-f]+", operand):
            continue
        if int(operand, 16) == target_va:
            result.append(f"0x{va - BASE:x}:{op}")
    return sorted(result)


def branch_on_zero_comiss(metadata_rate: float) -> str:
    """Schematic ordered COMISS 0,x / JB; never a runtime trace.

    For NaN COMISS can raise an invalid floating-point exception. If
    masked, the unordered flags would take JB. We report the uncertainty.
    """
    if math.isnan(metadata_rate):
        return "UNORDERED_BRANCH_IF_MASKED_OR_FP_EXCEPTION"
    return "KEEP_METADATA" if 0.0 < metadata_rate else "FALLBACK_48000"


def audit(dll: Path, objdump: str | None = None) -> dict:
    # The full Stage73 accepted exact-native source and SHA gates are rerun.
    previous = stage73.audit(dll, objdump)
    if previous["status"] != "SOURCE_RATE_HELPER_TWO_CANDIDATES_RUNTIME_PARENT_UNPROVEN":
        raise ValueError("Stage73 accepted source-only report status changed")
    if previous["passed_rate_provenance"]["rate_xmm9_cfg"]["possible_xmm9_sources"] != [
            "conditional_f32_fallback_48000", "f64_metadata_object_plus_0x18_to_f32"]:
        raise ValueError("Stage73 source candidates did not match")
    data = dll.read_bytes()
    pe = stage72.previous.PEFunctions(data)
    tool, backend = stage72.select_objdump(objdump)
    insns = {}
    bounds = {}
    for label, rva in OWNER_STARTS.items():
        owner = pe.owner(rva)
        if owner.start != rva:
            raise ValueError(f"Original function owner RVA changed: {rva:#x}")
        bounds[label] = (owner.start, owner.end)
        insns.update(stage72.read_disassembly(dll, tool, backend, owner.start, owner.end))
    validated = stage72.verify_pins(PINS, insns)

    incoming = local_direct_branches_to(insns, 0xE855, *bounds["helper_0xe0e0_object_gate"])
    if incoming != ["0xe6cd:jne"]:
        raise ValueError(f"Unexpected decoded direct branches into metadata load: {incoming}")
    # The byte immediately preceding the metadata load is an unconditional
    # jump away (0xE850), so it is not fall-through from the preceding block.
    if insns[BASE + 0xE850] != "jmp 0x18000e5cd":
        raise ValueError("Possible direct fallthrough predecessor changed")
    if 0x108 - 0x90 != 0x78 or 0x7 - (-0x19) != 0x20:
        raise ValueError("Broken function-local source-rate slot arithmetic")

    return {
        "stage": 74,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": DLL_SHA256,
        "disassembler_backend": backend,
        "stage73_status_verified": previous["status"],
        "verified_native_instruction_count": sum(map(len, validated.values())),
        "verified_instruction_groups": validated,
        "metadata_object_gate": {
            "init": "0xe17f R12=0; 0xe60c RBX=R12",
            "object_result": "0xe698 direct call 0xcc4e0 into [rsp+0x2a0] and 0xe6a7 RBX=[RAX] if not the initial stack slot",
            "ownership_transfer": "0xe6aa [RAX]=R12(0); 0xe6ad [rsp+0x38]=RBX",
            "direct_incoming_jumps_to_0xe855": incoming,
            "nonzero_gate": "0xe6ca TEST RBX,RBX; 0xe6cd JNE to 0xe855; preceding 0xe850 JMP elsewhere",
            "metadata_read": "0xe855 f64 [RBX+0x18] -> XMM9, non-null by local branch gate",
            "resolved_dynamic_object_type": False,
        },
        "nested_metadata_to_virtual_factory": {
            "exact_zero_mode_transfer": "0xe614 stack word=0 -> 0xe682 R8W -> 0xcc511 EBX -> 0xcc57c R9W -> 0xcae6d EBX -> 0xcb034 R8W=0; 0xca786 not taken; 0xca788 direct call ca810",
            "direct_call_chain": ["0xe698→0xcc4e0", "0xcc58a→0xcae30", "0xcb042→0xca760", "0xca788→0xca810", "0xcaabd→0xcab10"],
            "f64_marshaller": "0xcb026 source [R13+0x78] -> 0xcb02c [RBP+0x108]; 0xcb038 pointer [RBP+0x90] passed to 0xca760",
            "intermediate_packet": "0xca83d RBX=RDX; 0xca8c5 reads [RBX+0x78] (same RBP+0x108); 0xca8ca writes local [RBP+0x7]",
            "virtual_call_argument": "0xcaaae R9=&[RBP-0x19]; 0xcab36 RBX=R9; 0xcab53 XMM3=[RBX+0x20] (same [RBP+0x7])",
            "unresolved_boundary": "0xcab4f reads method pointer [vtable+0x8] into R9; 0xcab81 CALL R9; object construction/alias and target +0x18 field assignment unproven",
            "virtual_callee_target_verified": False,
            "object_plus_0x18_write_verified": False,
        },
        "native_fallback_branch": {
            "comparison": "0xe9b5 XMM6=+0; 0xe9b8 COMISS XMM6,XMM9; 0xe9bc JB 0xe9f3 skips fallback",
            "positive_ordered_metadata": branch_on_zero_comiss(44100.0),
            "zero_metadata": branch_on_zero_comiss(0.0),
            "negative_metadata": branch_on_zero_comiss(-1.0),
            "unordered_nan": branch_on_zero_comiss(math.nan),
            "fallback": "0xe9ea original PE f32 48000 at RVA 0x24cdf4, Stage73 verified",
            "runtime_branch_selected": False,
        },
        "claims": {
            "original_dll_executed": False,
            "local_nonnull_gate_verified": True,
            "f64_reaches_unresolved_virtual_call_argument": True,
            "f64_proven_stored_to_result_object_plus_0x18": False,
            "specific_stage64_reverse_parent_verified": False,
            "live_stage64_input_rate_48000_verified": False,
            "complete_vendor_antialiasing_verified": False,
            "new_hook_or_dsp_patch": False,
        },
        "next_gate": "Resolve virtual factory slot +0x8 at 0xcab81 and its result object +0x18 write statically; no live hook or DSP change without a separate decision.",
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
        "stage": report["stage"], "status": report["status"],
        "disassembler_backend": report["disassembler_backend"],
        "verified_native_instruction_count": report["verified_native_instruction_count"],
        "metadata_object_gate": report["metadata_object_gate"],
        "native_fallback_branch": report["native_fallback_branch"],
        "virtual_callee_target_verified": False,
        "runtime_stage64_parent_proven": False,
        "full_report_path": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            UnicodeDecodeError) as exc:
        print("[STAGE74 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
