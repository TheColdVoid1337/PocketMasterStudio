#!/usr/bin/env python3
"""Stage76: exact-original static registry lookup before virtual factory dispatch.

The DLL is read only as SHA-pinned PE data. Neither the registry callback nor
the selected factory method is resolved as a Stage64 runtime identity.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage75"))
import audit_virtual_factories as stage75

stage72 = stage75.stage72
BASE = stage75.BASE
DLL_SHA256 = stage75.DLL_SHA256
STATUS = "STATIC_STRING_KEYED_REGISTRY_CALLBACK_FACTORY_IDENTITY_UNPROVEN"

# Function owners checked independently against the original PE .pdata.
OWNER_STARTS = {
    "lazy_registry_accessor": 0x35DF0,
    "string_registry_lookup": 0x3F5C0,
    "metadata_packet": 0xCA810,
    "indirect_factory_dispatch": 0xCAB10,
    "family_a_vtable_install": 0xC62B0,
    "family_b_vtable_install": 0xCC690,
    "family_c_or_d_vtable_install": 0xD01A0,
    "family_d_vtable_install": 0xDD270,
}

PINS = {
    "lazy_registry_accessor": {
        0x35E22: "lea rax,[rip+0x2916a7]",
        0x35E44: "lea rbx,[rip+0x291685]",
        0x35E76: "call 0x1800384f0",
        0x35E7B: "mov qword ptr [rip+0x291656],rax",
    },
    "string_registry_lookup": {
        0x3F615: "mov r15,qword ptr [r8+0x10]",
        0x3F619: "mov r9,qword ptr [r8+0x18]",
        0x3F626: "movabs rdx,0xcbf29ce484222325",
        0x3F637: "movabs r10,0x100000001b3",
        0x3F641: "movzx eax,byte ptr [rcx+r8*1]",
        0x3F646: "xor rdx,rax",
        0x3F649: "imul rdx,r10",
        0x3F64D: "inc rcx",
        0x3F650: "cmp rcx,r15",
        0x3F653: "jb 0x18003f641",
        0x3F655: "mov r13,qword ptr [rsi+0x30]",
        0x3F65F: "mov rcx,qword ptr [rsi+0x18]",
        0x3F668: "mov rax,qword ptr [rcx+r13*8]",
        0x3F678: "cmp rax,rsi",
        0x3F709: "movsd qword ptr [rsp+0x20],xmm6",
        0x3F70F: "mov rcx,qword ptr [rbx+0x68]",
        0x3F71F: "mov r10,qword ptr [rcx]",
        0x3F722: "lea r9,[rsp+0x20]",
        0x3F727: "mov r8,qword ptr [rsp+0x30]",
        0x3F72C: "mov rdx,qword ptr [rsp+0x38]",
        0x3F731: "call qword ptr [r10+0x10]",
        0x3F735: "mov rax,qword ptr [rsp+0x38]",
    },
    "metadata_packet": {
        0xCAA57: "call 0x180035df0",
        0xCAA5C: "movsd xmm0,qword ptr [rbx+0x78]",
        0xCAA61: "lea r9,[rbx+0x40]",
        0xCAA65: "lea r8,[rbx+0x20]",
        0xCAA69: "movsd qword ptr [rsp+0x20],xmm0",
        0xCAA6F: "lea rdx,[rbp-0x61]",
        0xCAA73: "mov rcx,rax",
        0xCAA76: "call 0x18003f5c0",
        0xCAAA2: "mov rax,qword ptr [rbp-0x61]",
        0xCAAA6: "mov qword ptr [rbp-0x61],rcx",
        0xCAAAA: "mov qword ptr [rbp-0x69],rax",
        0xCAAAE: "lea r9,[rbp-0x19]",
        0xCAAB2: "lea r8,[rbp-0x59]",
        0xCAAB6: "lea rdx,[rbp-0x69]",
        0xCAABA: "mov rcx,rdi",
        0xCAABD: "call 0x1800cab10",
    },
    "indirect_factory_dispatch": {
        0xCAB49: "mov rcx,qword ptr [rdx]",
        0xCAB4C: "mov rax,qword ptr [rcx]",
        0xCAB4F: "mov r9,qword ptr [rax+0x8]",
        0xCAB53: "movsd xmm3,qword ptr [rbx+0x20]",
        0xCAB81: "call r9",
    },
    "family_a_vtable_install": {
        0xC62FE: "lea rax,[rip+0x180cab]",
        0xC6305: "mov qword ptr [rdi],rax",
    },
    "family_b_vtable_install": {
        0xCC6CE: "lea rax,[rip+0x17b033]",
        0xCC6D5: "mov qword ptr [rdi],rax",
    },
    "family_c_or_d_vtable_install": {
        0xD01DC: "call 0x1800d0450",
        0xD01E1: "test al,al",
        0xD01E3: "je 0x1800d025a",
        0xD0200: "lea rax,[rip+0x177ab9]",
        0xD0207: "mov qword ptr [rbx],rax",
        0xD0252: "mov qword ptr [rdi],rbx",
        0xD0268: "call 0x1800ce4b0",
        0xD02CD: "lea rax,[rip+0x1778d4]",
        0xD02D4: "mov qword ptr [rbx],rax",
    },
    "family_d_vtable_install": {
        0xDD2B6: "lea rax,[rip+0x16aa03]",
        0xDD2BD: "mov qword ptr [rdi],rax",
    },
}

INSTALLS = {
    "family_a": (0xC62FE, 0xC6305, 0x246FB0),
    "family_b": (0xCC6CE, 0xCC6D5, 0x247708),
    "family_c": (0xD02CD, 0xD02D4, 0x247BA8),
    "family_d": (0xDD2B6, 0xDD2BD, 0x247CC0),
}


def fnv1a64(raw: bytes) -> int:
    """Pure fixture for the source-pinned lookup hash, not a DLL invocation."""
    value = 0xCBF29CE484222325
    for b in raw:
        value = ((value ^ b) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def verify_source_links(insns: dict[int, str]) -> dict:
    """Check identities/targets of the positive *static* chain only."""
    pinned = stage72.verify_pins(PINS, insns)
    # Both machine-code relative loads and verified Stage75 table pointers
    # must agree; constructing an object does not prove lookup selection.
    installs = {}
    for name, (load_rva, store_rva, vtable_rva) in INSTALLS.items():
        if stage75.FACTORY_CHAINS[name]["vtable_rva"] != vtable_rva:
            raise ValueError(f"{name}: Stage75 candidate vtable changed")
        load = insns.get(BASE + load_rva, "")
        match = re.fullmatch(r"lea rax,\[rip\+0x([0-9a-f]+)\]", load)
        if match is None:
            raise ValueError(f"{name}: unexpected RIP-relative vtable load")
        actual_va = BASE + load_rva + 7 + int(match.group(1), 16)
        if actual_va != BASE + vtable_rva:
            raise ValueError(f"{name}: RIP-relative vtable installation target changed")
        installs[name] = {
            "vtable_load_rva": f"0x{load_rva:x}",
            "vtable_store_rva": f"0x{store_rva:x}",
            "vtable_rva": f"0x{vtable_rva:x}",
            "linked_to_stage75_vtable_slot": True,
            "live_registry_factory_identity_proven": False,
        }
    return {"verified_instruction_groups": pinned, "installations": installs}


def audit(dll: Path, objdump: str | None = None) -> dict:
    previous = stage75.audit(dll, objdump)
    if previous["status"] != stage75.STATUS:
        raise ValueError("Stage75 accepted source status changed")
    limits = previous["important_limits"]
    if limits["specific_call_0xcab81_targets_any_listed_method"] or limits[
            "stage64_runtime_factory_instance_identified"]:
        raise ValueError("Stage75 unresolved factory boundary changed")
    if previous["claims"]["actual_stage64_virtual_factory_selected"]:
        raise ValueError("Stage75 runtime identity unexpectedly claimed")

    data = dll.read_bytes()
    pe = stage72.previous.PEFunctions(data)
    tool, backend = stage72.select_objdump(objdump)
    insns = {}
    owners = {}
    for label, start in OWNER_STARTS.items():
        owner = pe.owner(start)
        if owner.start != start:
            raise ValueError(f"Stage76 .pdata owner changed: {start:#x}")
        owners[label] = [f"0x{owner.start:x}", f"0x{owner.end:x}"]
        insns.update(stage72.read_disassembly(dll, tool, backend, owner.start, owner.end))
    verified = verify_source_links(insns)

    return {
        "stage": 76,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": DLL_SHA256,
        "disassembler_backend": backend,
        "prior_stage75_status_verified": previous["status"],
        "verified_native_instruction_count": sum(map(len, verified["verified_instruction_groups"].values())),
        "verified_instruction_groups": verified["verified_instruction_groups"],
        "pdata_function_bounds": owners,
        "registry_access": {
            "accessor_rva": "0x35df0",
            "lazy_initializer_call_rva": "0x35e76 (0x384f0)",
            "returned_registry_base_rva": "0x2c74d0",
            "lookup_callsite_rva": "0xcaa76",
            "lookup_function_rva": "0x3f5c0",
            "key_argument": "0xcaa65 R8=&[RBX+0x20], a string-like field from the metadata packet",
            "aux_argument": "0xcaa61 R9=&[RBX+0x40]",
            "rate_argument": "0xcaa5c/0xcaa69 [RBX+0x78] f64 -> stack argument",
            "output_pointer": "0xcaa6f RDX=&[RBP-0x61]",
            "hash": {
                "algorithm": "FNV-1a 64-bit source-pinned seed/multiplier/byte loop",
                "seed": "0xcbf29ce484222325",
                "multiplier": "0x100000001b3",
                "key_length_field": "0x3f615 [R8+0x10]",
                "hash_table_bucket": "0x3f655/0x3f65f/0x3f668",
                "key_from_specific_stage64_capture_proven": False,
            },
            "registry_callback": "0x3f70f object=[node+0x68], 0x3f71f vtable, 0x3f731 CALL [vtable+0x10]",
            "registry_callback_target_resolved": False,
            "registry_entries_enumerated": False,
        },
        "selected_factory_pointer_transfer": {
            "post_lookup": "0xcaaa2 output pointer [RBP-0x61] -> RAX; 0xcaaaa stored to [RBP-0x69]",
            "bridge_argument": "0xcaab6 RDX=&[RBP-0x69] passed to 0xcab10 at 0xcaabd",
            "factory_dispatch": "0xcab49 RCX=[RDX], 0xcab4c vtable, 0xcab4f slot+8, 0xcab81 CALL R9",
            "indirect_boundaries": ["0x3f731 registry callback +0x10", "0xcab81 factory method +0x8"],
            "specific_factory_vtable_resolved": False,
        },
        "candidate_vtable_installations": verified["installations"],
        "conditional_family_c_d_branch": {
            "function_rva": "0xd01a0",
            "predicate": "0xd01dc call 0xd0450; 0xd01e1 TEST AL,AL; 0xd01e3 JE 0xd025a",
            "earlier_family_d_install": "0xd0200/0xd0207 -> 0x247cc0",
            "later_family_c_install": "0xd02cd/0xd02d4 -> 0x247ba8",
            "actual_branch_in_stage64_known": False,
        },
        "claims": {
            "original_dll_executed": False,
            "string_keyed_lookup_and_fnv_hash_verified": True,
            "two_indirect_callback_boundaries_verified": True,
            "four_candidate_vtables_installed_by_source_code": True,
            "original_stage64_registry_key_observed": False,
            "registry_callback_concrete_target_verified": False,
            "stage64_factory_or_constructed_object_identified": False,
            "stage64_reverse_rate_provenance_complete": False,
            "vendor_complete_antialiasing_proven": False,
            "new_hook_or_dsp_patch": False,
        },
        "next_gate": "Statically map registry registration and per-key callback candidates; do not equate source vtable installations with Stage64 runtime selection. Live metadata-only observation requires separate explicit decision.",
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
        "stage": 76,
        "status": report["status"],
        "verified_native_instruction_count": report["verified_native_instruction_count"],
        "registry_lookup_rva": report["registry_access"]["lookup_function_rva"],
        "registry_callback": report["registry_access"]["registry_callback"],
        "candidate_vtable_install_count": len(report["candidate_vtable_installations"]),
        "stage64_factory_identified": False,
        "full_report_path": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            struct.error, UnicodeDecodeError) as exc:
        print("[STAGE76 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
