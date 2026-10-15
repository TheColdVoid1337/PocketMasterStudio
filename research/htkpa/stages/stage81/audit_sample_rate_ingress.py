#!/usr/bin/env python3
"""Stage81: original PE JSON sample_rate -> metadata f64 and NAM structure.

Reads exact SHA-pinned files as inert data. Source instruction paths are
conditional; the operator's 2203 identification is testimonial provenance,
not proof of a runtime rate, selected factory, or same-run file hashes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage80"))
import audit_nam_capture_identity as stage80

stage79 = stage80.stage79
stage78 = stage79.stage78
stage77 = stage78.stage77
stage72 = stage77.stage72

STATUS = "STATIC_SAMPLE_RATE_JSON_TO_F64_METADATA_VERIFIED_2203_NESTED_WAVENET"
ORIGINAL_NAM_RATE = 48000
MAX_SUBMODELS = 16

SOURCE_OWNERS = {
    "sample_rate_json_reader": 0xCA4E0,
    "nam_metadata_parser": 0xCB200,
    "metadata_packet_marshaller": 0xCAE30,
}

PINS = {
    "sample_rate_json_reader": {
        0xCA5A4: "lea rdx,[rip+0xc5385]",   # second original sample_rate literal
        0xCA5AB: "call 0x180027a30",       # conditional map-key comparison
        0xCA651: "lea rdx,[rip+0xc52c8]",   # exact sample_rate JSON key
        0xCA65B: "call 0x18002d3b0",       # property lookup
        0xCA663: "movzx r8d,byte ptr [rax]", # parsed-value kind
        0xCA689: "movsd xmm0,qword ptr [rax]",  # floating value case
        0xCA69B: "mov rax,qword ptr [rax]",  # integer case
        0xCA6A1: "cvtsi2sd xmm0,rax",       # convert integer to f64
        0xCA6D4: "movsd xmm0,qword ptr [rip+0x1827f4]", # missing-value sentinel
    },
    "nam_metadata_parser": {
        0xCB236: "mov r14,rdx",             # output metadata object
        0xCB5EA: "mov rcx,rdi",             # original parsed input object
        0xCB5ED: "call 0x1800ca4e0",       # return source f64
        0xCB5F2: "movsd qword ptr [r14+0x78],xmm0", # metadata +0x78 write
    },
    "metadata_packet_marshaller": {
        0xCAE71: "mov r13,r8",             # same output metadata object
        0xCAFC6: "mov rdx,r13",
        0xCAFCE: "call 0x1800cb200",       # parser receives R13
        0xCB026: "movsd xmm0,qword ptr [r13+0x78]", # metadata +0x78 read
        0xCB02C: "movsd qword ptr [rbp+0x108],xmm0", # packet f64
        0xCB042: "call 0x1800ca760",       # Stage74 packet dispatch
    },
}

KEY_RVAS = (0x18F920, 0x18F930)
MISSING_VALUE_SENTINEL_RVA = 0x24CED0


def nested_nam_structure(data: bytes, label: str) -> dict:
    """Parse a bounded, already-SHA-verified original NAM; never return weights."""
    model = json.loads(
        data.decode("utf-8"),
        object_pairs_hook=stage79.reject_duplicate_object_keys,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError("Invalid NAM constant")),
    )
    if not isinstance(model, dict) or model.get("architecture") != "SlimmableContainer":
        raise ValueError("Expected a top-level SlimmableContainer: " + label)
    if model.get("version") != "0.7.0" or model.get("sample_rate") != ORIGINAL_NAM_RATE:
        raise ValueError("Unexpected original outer version/rate: " + label)
    config = model.get("config")
    subs = config.get("submodels") if isinstance(config, dict) else None
    if not isinstance(subs, list) or not 1 <= len(subs) <= MAX_SUBMODELS:
        raise ValueError("Malformed/bounded slimmable submodels: " + label)

    result = []
    last = 0.0
    for index, item in enumerate(subs):
        if not isinstance(item, dict) or not isinstance(item.get("model"), dict):
            raise ValueError("Malformed submodel object")
        threshold = item.get("max_value")
        if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
                or not math.isfinite(threshold) or not last < threshold <= 1.0):
            raise ValueError("Invalid/non-increasing submodel maximum")
        nested = item["model"]
        if (nested.get("architecture") != "WaveNet" or
                nested.get("version") != model["version"] or
                nested.get("sample_rate") != model["sample_rate"] or
                not isinstance(nested.get("config"), dict)):
            raise ValueError("Unexpected nested model architecture/rate/version")
        result.append({
            "index": index,
            "max_value": float(threshold),
            "architecture": nested["architecture"],
            "sample_rate_hz": ORIGINAL_NAM_RATE,
            "format_version": nested["version"],
        })
        last = float(threshold)
    return {
        "label": label,
        "top_level_architecture": model["architecture"],
        "sample_rate_hz": ORIGINAL_NAM_RATE,
        "format_version": model["version"],
        "submodel_count": len(result),
        "submodels": result,
        "model_weights_in_report": False,
        "model_metadata_in_report": False,
        "runtime_selected_submodel_identified": False,
    }


def verify_native_rate_source(insns: dict[int, str], dll_data: bytes) -> dict:
    matches = stage72.verify_pins(PINS, insns)
    for rva in KEY_RVAS:
        stage77.read_literal(dll_data, rva, "sample_rate", len("sample_rate"))
    if 0xCA5A4 + 7 + 0xC5385 != KEY_RVAS[1]:
        raise ValueError("Secondary sample_rate PE literal target changed")
    if 0xCA651 + 7 + 0xC52C8 != KEY_RVAS[0]:
        raise ValueError("Primary sample_rate PE literal target changed")
    if 0xCA6D4 + 8 + 0x1827F4 != MISSING_VALUE_SENTINEL_RVA:
        raise ValueError("Missing-value sentinel RIP target changed")
    sentinel = struct.unpack("<d", stage72.pe_file_bytes(
        dll_data, MISSING_VALUE_SENTINEL_RVA, 8))[0]
    if sentinel != -1.0:
        raise ValueError("Original PE sample_rate missing-value sentinel changed")
    return {
        "validated_instruction_groups": matches,
        "original_json_key_rvas": [f"0x{rva:x}" for rva in KEY_RVAS],
        "original_json_key": "sample_rate",
        "numeric_handling": "Source tests JSON kind and has f64 and integer-to-f64 paths; no claim that every path succeeds",
        "missing_value_source_constant": sentinel,
        "metadata_writer_rva": "0xcb5f2",
        "same_metadata_field_reader_rva": "0xcb026",
        "metadata_field_offset": "0x78",
        "packet_f64_copy_rva": "0xcb02c",
        "source_path_is_conditional": True,
    }


def audit(dll: Path, stage64: Path, nams: dict[str, Path],
          clos: dict[str, Path], objdump: str | None = None) -> dict:
    previous = stage80.audit(dll, stage64, nams, clos, objdump)
    if previous["status"] != stage80.STATUS or previous["independent_stage64_input_nam_identity_proven"]:
        raise ValueError("Stage80 capture-internal provenance gate changed")
    for label, expected_sha in stage80.NAM_PINS.items():
        if previous["verified_nam_headers"][label]["sha256"] != expected_sha:
            raise ValueError("Stage80 authenticated NAM source changed")
    structures = {
        label: nested_nam_structure(stage80.checked_file(
            nams[label], sha, stage80.MAX_NAM_BYTES), label)
        for label, sha in stage80.NAM_PINS.items()
    }
    expected_submodels = [(0.5, "WaveNet"), (1.0, "WaveNet")]
    for label, structure in structures.items():
        observed = [(item["max_value"], item["architecture"])
                    for item in structure["submodels"]]
        if observed != expected_submodels:
            raise ValueError("Authenticated nested structure changed: " + label)

    data = dll.read_bytes()
    pe = stage72.previous.PEFunctions(data)
    tool, backend = stage72.select_objdump(objdump)
    instructions = {}
    owner_bounds = {}
    for label, start in SOURCE_OWNERS.items():
        owner = pe.owner(start)
        if owner.start != start:
            raise ValueError("Native .pdata owner changed: " + label)
        owner_bounds[label] = [f"0x{owner.start:x}", f"0x{owner.end:x}"]
        instructions.update(stage72.read_disassembly(
            dll, tool, backend, owner.start, owner.end))
    native = verify_native_rate_source(instructions, data)
    return {
        "stage": 81,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": stage80.stage79.DLL_SHA256,
        "stage64_archive_sha256": stage79.STAGE64_SHA256,
        "prior_stage80_source_gate": previous["status"],
        "disassembler_backend": backend,
        "new_verified_instruction_count": sum(map(len, native["validated_instruction_groups"].values())),
        "native_owners": owner_bounds,
        "native_sample_rate_ingress": native,
        "authenticated_model_structure": structures,
        "structure_distinguishes_2203_from_sc20": False,
        "operator_attestation": {
            "source": "firsthand capture operator, separately documented after Stage80",
            "stage64_nam_import_model_label": "2203",
            "historical_input_sha256_independently_recorded": False,
        },
        "claims": {
            "exact_original_pe_data_and_instructions_verified": True,
            "nam_nested_metadata_verified": True,
            "sample_rate_json_to_metadata_field_static_path_verified": True,
            "stage64_runtime_sample_rate_value_verified": False,
            "stage64_selected_submodel_or_factory_verified": False,
            "stage64_exact_same_run_nam_clo_hash_binding_verified": False,
            "original_dll_executed": False,
            "new_frida_capture_or_hook": False,
            "model_weights_in_report": False,
            "complete_vendor_audio_or_antialiasing_parity_proven": False,
        },
        "next_gate": "Resolve conditional factory instance and sample-rate flow into the Stage64 resampler parent; do not equate static metadata ingress or an operator-attested filename with live factory/byte identity.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("dll", "stage64", "nam-2203", "nam-sc20", "clo-2203", "clo-sc20"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--objdump")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    source_paths = [args.dll, args.stage64, args.nam_2203, args.nam_sc20,
                    args.clo_2203, args.clo_sc20]
    if args.out and args.out.resolve() in [p.resolve() for p in source_paths]:
        raise ValueError("Refusing to overwrite private original input")
    result = audit(args.dll, args.stage64,
                   {"2203": args.nam_2203, "SC20": args.nam_sc20},
                   {"2203": args.clo_2203, "SC20": args.clo_sc20}, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage": 81,
        "status": result["status"],
        "new_instruction_pins": result["new_verified_instruction_count"],
        "nested_model_architectures": [
            item["architecture"] for item in
            result["authenticated_model_structure"]["2203"]["submodels"]],
        "sample_rate_static_metadata_path_verified": True,
        "stage64_live_factory_or_same_run_hash_proven": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, UnicodeError, json.JSONDecodeError) as exc:
        print("[STAGE81 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
