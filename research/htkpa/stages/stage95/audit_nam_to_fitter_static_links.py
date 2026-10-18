#!/usr/bin/env python3
"""Stage95: bounded original-PE call bridges from NAM parser to fitter.

Exact-SHA / PE32+ static-only. No disassembly engine, code execution, Frida or
inference that statically coexisting paths were executed in one invocation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
import sys


STAGES_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STAGES_DIR / "stage94"))
sys.path.insert(0, str(STAGES_DIR / "stage70"))
import audit_public_source_fingerprints as s94  # noqa: E402
from audit_parent_calls import PEFunctions  # noqa: E402


STAGE = 95
STATUS = "STATIC_NAM_CORE_LOADER_TO_SHARED_FITTER_BRIDGES_VERIFIED_RUNTIME_UNBOUND"

# (call instruction RVA, expected .pdata caller owner, exact direct callee RVA).
# Statically supported; do not imply these edges all executed in one run.
COMPILED_EDGES = {
    "nam_loader_to_getweights_family": (
        (0xE698, 0xE0E0, 0xCC4E0),
        (0xCC58A, 0xCC4E0, 0xCAE30),
        (0xCAFCE, 0xCAE30, 0xCB200),
    ),
    "nam_worker_internal_wav": ((0xEB1E, 0xE0E0, 0xD4A0),),
    "wrapper_ff40_to_fitter": (
        (0x10043, 0xFF40, 0xE0E0),
        (0x100EB, 0xFF40, 0xD4A0),
        (0x1016D, 0xFF40, 0xF940),
        (0xFA41, 0xF940, 0xBE830),
    ),
    "wrapper_10e70_to_fitter": (
        (0x10F7F, 0x10E70, 0xE0E0),
        (0x11021, 0x10E70, 0xD4A0),
        (0x110AD, 0x10E70, 0x10230),
        (0x104E1, 0x10230, 0xBE830),
    ),
    "shared_fitter_to_resampler": (
        (0xBF364, 0xBE830, 0xCE00),
        (0xBF47F, 0xBE830, 0xCE00),
    ),
}

# Known source/fitter strings are deliberately checked as PE RVA targets;
# the string is not mistaken for proof a throw/log event actually fired.
SELECTED_TEXT_TARGETS = {
    "nam_weights_json_key": (0x18F838, b"weights"),
    "fitter_failure_log": (0x244A38, b"HTKPA startClone failed."),
    "fitter_failure_input_path_log": (0x244A98, b"HTKPA startClone failed. inputSignalPath='"),
}

# (LEA RVA, opcode suffix after 48 8D: 0x15 RDX or 0x0D RCX, expected text).
SELECTED_TEXT_XREFS = {
    "nam_weights_json_key": (
        (0xCB304, 0x15), (0xCB32F, 0x0D),
        (0xCB774, 0x15), (0xCB7A7, 0x0D),
    ),
    "fitter_failure_log": ((0xFA6D, 0x15),),
    "fitter_failure_input_path_log": ((0x105E0, 0x15),),
}

# Static NAM return gate in the two wrappers; both compare to the *same*
# double constant -2.0. JP/JNE can pass inequality *or* unordered inputs.
RETURN_GATES = {
    "wrapper_ff40": {
        "compare_rva": 0x10050, "modrm": 0x05,
        "unordered_branch": (0x10058, 0x100BA),
        "not_equal_branch": (0x1005A, 0x100BA),
        "optional_flag_skip": (0x100C9, 0x1018F),
    },
    "wrapper_10e70": {
        "compare_rva": 0x10F8C, "modrm": 0x35,
        "unordered_branch": (0x10F94, 0x10FF6),
        "not_equal_branch": (0x10F96, 0x10FF6),
        "optional_flag_skip": (0x11005, 0x110CF),
    },
}
RETURN_SENTINEL_RVA = 0x24CEF0


def exact_e8_target(data: bytes, sections: list[dict], site_rva: int) -> int:
    raw = s94.rva_to_raw(sections, site_rva)
    if data[raw:raw + 1] != b"\xE8":
        raise s94.AuditError(f"RVA {site_rva:#x}: missing direct E8 rel32 CALL")
    disp = struct.unpack_from("<i", data, raw + 1)[0]
    return (site_rva + 5 + disp) & 0xFFFFFFFF


def lea_target(data: bytes, sections: list[dict], site_rva: int, modrm: int) -> int:
    raw = s94.rva_to_raw(sections, site_rva)
    if data[raw:raw + 3] != bytes((0x48, 0x8D, modrm)):
        raise s94.AuditError(f"RVA {site_rva:#x}: wrong exact RIP-relative LEA encoding")
    disp = struct.unpack_from("<i", data, raw + 3)[0]
    return (site_rva + 7 + disp) & 0xFFFFFFFF


def ucomisd_target(data: bytes, sections: list[dict], site_rva: int, modrm: int) -> int:
    raw = s94.rva_to_raw(sections, site_rva)
    if data[raw:raw + 4] != bytes((0x66, 0x0F, 0x2E, modrm)):
        raise s94.AuditError(f"RVA {site_rva:#x}: unexpected UCOMISD encoding")
    disp = struct.unpack_from("<i", data, raw + 4)[0]
    return (site_rva + 8 + disp) & 0xFFFFFFFF


def branch_target(data: bytes, sections: list[dict], site_rva: int, kind: str) -> int:
    raw = s94.rva_to_raw(sections, site_rva)
    if kind == "jp":
        expected, size, displacement = b"\x7A", 2, struct.unpack_from("<b", data, raw + 1)[0]
    elif kind == "jne_short":
        expected, size, displacement = b"\x75", 2, struct.unpack_from("<b", data, raw + 1)[0]
    elif kind == "jne_near":
        expected, size, displacement = b"\x0F\x85", 6, struct.unpack_from("<i", data, raw + 2)[0]
    else:
        raise ValueError(f"Unsupported static branch kind: {kind}")
    if data[raw:raw + len(expected)] != expected:
        raise s94.AuditError(f"RVA {site_rva:#x}: changed {kind} opcode")
    return (site_rva + size + displacement) & 0xFFFFFFFF


def audit(data: bytes) -> dict:
    # Stage94 exact original-DLL pin, 12 source-family signatures and four xrefs.
    previous = s94.audit(data)
    sections = s94.pe64_sections(data)
    pe = PEFunctions(data)

    edges = {}
    for family, anchors in COMPILED_EDGES.items():
        checked = []
        for site, expected_owner, expected_target in anchors:
            owner = pe.owner(site).start
            target = exact_e8_target(data, sections, site)
            callee_owner = pe.owner(target).start
            if owner != expected_owner or target != expected_target or callee_owner != expected_target:
                raise s94.AuditError(
                    f"{family} {site:#x}: owner={owner:#x} target={target:#x} "
                    f"callee_owner={callee_owner:#x} differs from pins"
                )
            checked.append({"callsite_rva": f"0x{site:X}",
                            "caller_pdata_owner_rva": f"0x{owner:X}",
                            "callee_rva": f"0x{target:X}"})
        edges[family] = checked

    text_refs = {}
    for label, (target, needle) in SELECTED_TEXT_TARGETS.items():
        raw = s94.rva_to_raw(sections, target)
        if data[raw:raw + len(needle)] != needle:
            raise s94.AuditError(f"{label}: pinned text at RVA {target:#x} changed")
        text_refs[label] = []
        for site, modrm in SELECTED_TEXT_XREFS[label]:
            actual = lea_target(data, sections, site, modrm)
            if actual != target:
                raise s94.AuditError(f"{label}: xref {site:#x} resolved to {actual:#x}")
            text_refs[label].append({"lea_rva": f"0x{site:X}", "text_rva": f"0x{target:X}",
                                     "pdata_owner_rva": f"0x{pe.owner(site).start:X}"})

    raw_const = s94.rva_to_raw(sections, RETURN_SENTINEL_RVA)
    sentinel = struct.unpack_from("<d", data, raw_const)[0]
    if sentinel != -2.0 or data[raw_const:raw_const + 8] != bytes.fromhex("00000000000000c0"):
        raise s94.AuditError("Both wrapper gates require original -2.0 double sentinel")

    gates = {}
    for family, cfg in RETURN_GATES.items():
        compare = cfg["compare_rva"]
        if ucomisd_target(data, sections, compare, cfg["modrm"]) != RETURN_SENTINEL_RVA:
            raise s94.AuditError(f"{family}: unexpected UCOMISD target")
        jp_site, jp_dest = cfg["unordered_branch"]
        jne_site, jne_dest = cfg["not_equal_branch"]
        flag_site, flag_dest = cfg["optional_flag_skip"]
        if (branch_target(data, sections, jp_site, "jp") != jp_dest or
                branch_target(data, sections, jne_site, "jne_short") != jne_dest or
                branch_target(data, sections, flag_site, "jne_near") != flag_dest):
            raise s94.AuditError(f"{family}: original conditional branch target changed")
        gates[family] = {
            "compare_rva": f"0x{compare:X}", "sentinel_rva": f"0x{RETURN_SENTINEL_RVA:X}",
            "value": -2.0, "unordered_or_not_equal_branch_target_rva": f"0x{jp_dest:X}",
            "optional_flag_nonzero_skip_rva": f"0x{flag_dest:X}",
            "branch_condition": "unordered OR not-equal permits follow-on path; zero optional flag further gates it",
        }

    return {
        "stage": STAGE, "status": STATUS, "dll_sha256": previous["dll_sha256"],
        "dll_size": previous["dll_size"],
        "stage94_original_byte_fingerprints_revalidated": previous["fingerprint_count"],
        "source_family_candidate": "NAM/get_dsp.cpp GetWeights / populate_dsp_data (structural, not symbol identity)",
        "compiled_call_families": edges,
        "direct_call_edges_checked": sum(len(x) for x in edges.values()),
        "additional_text_xrefs": text_refs,
        "additional_text_xref_count": sum(len(x) for x in text_refs.values()),
        "wrapper_return_gates": gates,
        "second_missing_weights_xref": "0xCB863 (Stage94), no separately proven direct ancestry",
        "limits": [
            "exact original PE bytes / .pdata / selected E8 CALL and RIP-relative instructions only",
            "direct compiled ancestry is not an observed invocation or source-level function identity",
            "two return gates and optional flag branches are compiled conditional options, not observed decisions",
            "Stage92 captured separate temporal windows; no confirmed one-stack WAV->NAM->fitter timeline",
            "no Ghidra decompilation, live Frida, NAM->CLO execution, parity or completed CLO in Stage95",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.dll.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "stage", "status", "dll_sha256", "direct_call_edges_checked", "additional_text_xref_count")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
