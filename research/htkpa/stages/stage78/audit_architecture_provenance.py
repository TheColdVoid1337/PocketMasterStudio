#!/usr/bin/env python3
"""Stage78: original-PE NAM architecture JSON key -> native registry key.

Read-only PE/static analysis. Upstream architecture naming is contextual, not
proof of identical compiled code or of the architecture used in Stage64.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage77"))
import audit_named_registry as stage77

stage72 = stage77.stage72
BASE = stage77.BASE
DLL_SHA256 = stage77.DLL_SHA256
STATUS = "STATIC_JSON_ARCHITECTURE_TO_NAM_REGISTRY_KEY_RUNTIME_SELECTION_UNPROVEN"

ARCHITECTURE_LITERAL_RVA = 0x18F890
# File-backed MSVC RTTI strings, recorded as independent namespace/name hints.
# They do not establish bitwise identity with an upstream release.
RTTI_NAMES = {
    "ConvNet": (0x2A2840, ".?AVConvNet@convnet@nam@@"),
    "LSTM": (0x2A2E08, ".?AVLSTM@lstm@nam@@"),
    "WaveNet": (0x2A2F50, ".?AVWaveNet@wavenet@nam@@"),
    "SlimmableWavenet": (0x2A3090, ".?AVSlimmableWavenet@slimmable_wavenet@nam@@"),
    "A2FastModel_encoded_specialization": (0x2A2E60, ".?AV?$A2FastModel@$07@?A0xbd49d576@a2_fast@wavenet@nam@@"),
}

OWNER_STARTS = {
    "json_architecture_reader": 0xCB200,
    "metadata_marshaller": 0xCAE30,
    "metadata_packet": 0xCA810,
    "registry_lookup": 0x3F5C0,
}

PINS = {
    "json_architecture_reader": {
        0xCB236: "mov r14,rdx",
        0xCB44F: "lea rdx,[rip+0xc443a]",
        0xCB456: "mov rcx,rdi",
        0xCB459: "call 0x18002d3b0",
        0xCB45E: "lea rdx,[rbp-0x9]",
        0xCB462: "mov rcx,rax",
        0xCB465: "call 0x18002d2d0",
        0xCB46A: "mov rbx,rax",
        0xCB46D: "lea rsi,[r14+0x20]",
        0xCB471: "cmp rsi,rax",
        0xCB474: "je 0x1800cb49b",
        0xCB476: "mov rcx,rsi",
        0xCB479: "call 0x180013e40",
        0xCB47E: "movups xmm0,xmmword ptr [rbx]",
        0xCB481: "movups xmmword ptr [rsi],xmm0",
        0xCB484: "movups xmm1,xmmword ptr [rbx+0x10]",
        0xCB488: "movups xmmword ptr [rsi+0x10],xmm1",
    },
    "metadata_marshaller": {
        0xCAE71: "mov r13,r8",
        0xCAF8E: "cmp edi,0x1",
        0xCAF91: "je 0x1800cb1d3",
        0xCAFC6: "mov rdx,r13",
        0xCAFC9: "lea rcx,[rsp+0x30]",
        0xCAFCE: "call 0x1800cb200",
        0xCAFD3: "mov rdx,r13",
        0xCAFD6: "lea rcx,[rbp+0x90]",
        0xCAFDD: "call 0x1800126e0",
        0xCAFE3: "lea rdx,[r13+0x20]",
        0xCAFE7: "lea rcx,[rbp+0xb0]",
        0xCAFEE: "call 0x1800126e0",
        0xCB034: "movzx r8d,bx",
        0xCB038: "lea rdx,[rbp+0x90]",
        0xCB042: "call 0x1800ca760",
    },
    "metadata_packet": {
        0xCA83D: "mov rbx,rdx",
        0xCAA65: "lea r8,[rbx+0x20]",
        0xCAA76: "call 0x18003f5c0",
    },
    "registry_lookup": {
        0x3F615: "mov r15,qword ptr [r8+0x10]",
        0x3F626: "movabs rdx,0xcbf29ce484222325",
        0x3F731: "call qword ptr [r10+0x10]",
    },
}


def verify_architecture_source(insns: dict[int, str], data: bytes) -> dict:
    validated = stage72.verify_pins(PINS, insns)
    # Pin the RIP load target independently of mnemonic normalization.
    load_rva = 0xCB44F
    if load_rva + 7 + 0xC443A != ARCHITECTURE_LITERAL_RVA:
        raise ValueError("Architecture literal RIP target changed")
    architecture_key = stage77.read_literal(data, ARCHITECTURE_LITERAL_RVA,
                                            "architecture", 12)
    rtti = {}
    for name, (rva, decorated) in RTTI_NAMES.items():
        rtti[name] = {
            "original_rtti_literal_rva": f"0x{rva:x}",
            "decorated_name": stage77.read_literal(data, rva, decorated, len(decorated)),
            "exact_upstream_code_identity_proven": False,
        }
    if not all(name in stage77.REGISTRATIONS for name in ("ConvNet", "LSTM", "WaveNet")):
        raise ValueError("Stage77 architecture registry names changed")
    if 0xB0 - 0x90 != 0x20:
        raise ValueError("Architecture packet offset changed")
    return {"verified_instruction_groups": validated, "architecture_json_key": architecture_key,
            "native_rtti_class_hints": rtti}


def audit(dll: Path, objdump: str | None = None) -> dict:
    previous = stage77.audit(dll, objdump)
    if previous["status"] != stage77.STATUS:
        raise ValueError("Stage77 accepted exact-source status changed")
    for claim in ("specific_stage64_registry_key_identified",
                  "specific_stage64_factory_selected", "original_dll_executed"):
        if previous["claims"][claim]:
            raise ValueError(f"Stage77 runtime/source-only boundary changed: {claim}")
    if set(previous["named_static_registrations"]) != set(stage77.REGISTRATIONS):
        raise ValueError("Stage77 accepted named registrations changed")

    data = dll.read_bytes()
    pe = stage72.previous.PEFunctions(data)
    tool, backend = stage72.select_objdump(objdump)
    insns = {}
    bounds = {}
    for label, entry in OWNER_STARTS.items():
        owner = pe.owner(entry)
        if owner.start != entry:
            raise ValueError(f"Stage78 .pdata function owner mismatch at {entry:#x}")
        bounds[label] = [f"0x{owner.start:x}", f"0x{owner.end:x}"]
        insns.update(stage72.read_disassembly(dll, tool, backend, owner.start, owner.end))
    verified = verify_architecture_source(insns, data)
    return {
        "stage": 78,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": DLL_SHA256,
        "disassembler_backend": backend,
        "prior_stage77_status_verified": previous["status"],
        "verified_native_instruction_count": sum(map(len, verified["verified_instruction_groups"].values())),
        "verified_instruction_groups": verified["verified_instruction_groups"],
        "pdata_function_bounds": bounds,
        "json_architecture_key": {
            "field_name": verified["architecture_json_key"],
            "original_literal_rva": f"0x{ARCHITECTURE_LITERAL_RVA:x}",
            "property_reader": "0xcb44f literal -> 0xcb459 call 0x2d3b0 -> 0xcb465 call 0x2d2d0",
            "output_field": "0xcb46d R14+0x20; 0xcb47e..0xcb488 string-like value copy",
            "input_file_architecture_value_observed": False,
        },
        "static_registry_key_provenance": {
            "conditional_marshalling": "0xcaf91 branch to exception path for EDI==1; source parser path at 0xcafce is conditional",
            "source_output_object": "0xcae71 R13=R8; 0xcafce calls 0xcb200 with RDX=R13",
            "transfer_to_packet": "0xcafd6/0xcafdd copy R13 -> RBP+0x90; 0xcafe3/0xcafee copy R13+0x20 -> RBP+0xb0",
            "dispatch": "0xcb038 RDX=&[RBP+0x90] -> 0xca760 -> 0xca810",
            "lookup_key": "0xca83d RBX=RDX; 0xcaa65 R8=&[RBX+0x20] -> 0xcaa76 registry lookup 0x3f5c0",
            "registered_architectures": list(stage77.REGISTRATIONS),
            "actual_runtime_key_from_stage64": None,
            "json_parser_full_control_flow_proven": False,
        },
        "original_pe_rtti_hints": verified["native_rtti_class_hints"],
        "upstream_references": {
            "original_nam_format": "https://github.com/sdatkinson/neural-amp-modeler/blob/main/docs/source/model-file.rst",
            "original_nam_core": "https://github.com/sdatkinson/NeuralAmpModelerCore",
            "original_nam_core_releases": "https://github.com/sdatkinson/NeuralAmpModelerCore/releases",
            "provenance_scope": "matching names/namespace; no byte-for-byte upstream binary, release version or derived-code attribution claim",
        },
        "claims": {
            "original_dll_executed": False,
            "architecture_literal_and_source_to_registry_key_verified": True,
            "named_nam_namespace_rtti_literals_verified": True,
            "upstream_code_identity_or_release_verified": False,
            "specific_stage64_architecture_key_identified": False,
            "specific_stage64_factory_selected": False,
            "specific_stage64_reverse_parent_verified": False,
            "complete_vendor_antialiasing_verified": False,
            "new_hook_or_dsp_patch": False,
        },
        "next_gate": "Obtain exact Stage64 input NAM/CLO architecture metadata or a safe runtime provenance trace; never infer a concrete key or DSP effect from static names alone.",
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
        "stage": 78, "status": report["status"],
        "verified_native_instruction_count": report["verified_native_instruction_count"],
        "source_architecture_json_key": report["json_architecture_key"]["field_name"],
        "native_rtti_names": list(report["original_pe_rtti_hints"]),
        "specific_stage64_architecture_key_identified": False,
        "full_report_path": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            UnicodeDecodeError) as exc:
        print("[STAGE78 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
