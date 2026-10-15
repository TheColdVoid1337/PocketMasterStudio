#!/usr/bin/env python3
"""Stage71: bounded source-only NAM ancestry and sample-rate-field audit.

The SHA-pinned original DLL is parsed as a PE64 file, never loaded or run.
NAM export roots are followed through direct calls only. Source-rate field
reads are checked at the original Stage69 callsites, with nearby R14 writes
reported merely as candidates (never asserted as dynamic data provenance).
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage70"))
import audit_parent_calls as previous

DLL_SHA256 = previous.DLL_SHA256
CONSTRUCTOR_RVA = previous.CONSTRUCTOR_RVA
HELPER_RVA = previous.HELPER_RVA
NAM_EXPORT_RVAS = {
    "namConvertCloData": 0xE1F70,
    "namConvertClo": 0xE22A0,
    "appNamConvertCloData": 0xABEB0,
    "appNamConvertClo": 0xAC0E0,
}
CALLSITE_RATE_READS = {
    0xE28F1: (0xE28DC, "movsd xmm1, qword ptr [r14 + 0x8]", 0xE2640),
    0xBF364: (0xBF358, "movss xmm1, dword ptr [r14 + 0x20ec0]", 0xBE830),
}
MAX_GRAPH_FUNCTIONS = 128
MAX_GRAPH_DEPTH = 5
MAX_EXPORT_NAMES = 8192


class PEExports:
    """Parse PE32+ export table with strict file-backed RVA bounds."""

    def __init__(self, data: bytes):
        if len(data) < 0x100 or data[:2] != b"MZ":
            raise ValueError("Not an MZ image")
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\x00\x00":
            raise ValueError("Truncated or invalid PE image")
        coff = pe + 4
        machine, nsections = struct.unpack_from("<HH", data, coff)
        opt_size = struct.unpack_from("<H", data, coff + 16)[0]
        opt = coff + 20
        if (machine != 0x8664 or opt_size < 144 or
                opt + opt_size > len(data) or
                struct.unpack_from("<H", data, opt)[0] != 0x20B):
            raise ValueError("Original DLL must be PE32+ x64")
        if struct.unpack_from("<Q", data, opt + 24)[0] != previous.IMAGE_BASE:
            raise ValueError("Original image-base mismatch")
        if struct.unpack_from("<I", data, opt + 108)[0] < 1:
            raise ValueError("PE export directory absent")
        export_rva, export_size = struct.unpack_from("<II", data, opt + 112)
        if not export_rva or not 40 <= export_size <= 500_000:
            raise ValueError("Invalid export directory")
        table = opt + opt_size
        if not 1 <= nsections <= 64 or table + 40 * nsections > len(data):
            raise ValueError("Invalid PE section table")
        sections = []
        for i in range(nsections):
            off = table + i * 40
            vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
            sections.append((va, vsize, rawsize, rawptr))

        def get_bytes(rva: int, length: int) -> bytes:
            if length < 0 or length > 500_000:
                raise ValueError("Unbounded export read")
            for va, _vsize, rawsize, rawptr in sections:
                if va <= rva and rva + length <= va + rawsize:
                    pos = rawptr + rva - va
                    if pos + length <= len(data):
                        return data[pos:pos + length]
            raise ValueError(f"Export RVA {rva:#x} not file-backed")

        def get_u32(rva: int) -> int:
            return struct.unpack("<I", get_bytes(rva, 4))[0]

        def get_u16(rva: int) -> int:
            return struct.unpack("<H", get_bytes(rva, 2))[0]

        def get_cstr(rva: int) -> str:
            chars = bytearray()
            for index in range(256):
                char = get_bytes(rva + index, 1)[0]
                if char == 0:
                    return chars.decode("ascii")
                chars.append(char)
            raise ValueError("Unterminated export name")

        directory = get_bytes(export_rva, 40)
        count_funcs = struct.unpack_from("<I", directory, 20)[0]
        count_names = struct.unpack_from("<I", directory, 24)[0]
        address_funcs = struct.unpack_from("<I", directory, 28)[0]
        address_names = struct.unpack_from("<I", directory, 32)[0]
        address_ordinals = struct.unpack_from("<I", directory, 36)[0]
        if (not 0 < count_funcs <= MAX_EXPORT_NAMES or
                not 0 < count_names <= MAX_EXPORT_NAMES):
            raise ValueError("Invalid number of exports")
        self.names = {}
        for i in range(count_names):
            name = get_cstr(get_u32(address_names + 4 * i))
            ordinal = get_u16(address_ordinals + 2 * i)
            if ordinal >= count_funcs or name in self.names:
                raise ValueError("Duplicate/invalid named export")
            function_rva = get_u32(address_funcs + 4 * ordinal)
            if export_rva <= function_rva < export_rva + export_size:
                continue  # forwarded export; never mislabel as native function
            self.names[name] = function_rva

    def verify_named_anchors(self) -> dict[str, str]:
        for name, expected in NAM_EXPORT_RVAS.items():
            if self.names.get(name) != expected:
                raise ValueError(f"NAM export RVA mismatch: {name}")
        return {name: f"0x{value:x}" for name, value in NAM_EXPORT_RVAS.items()}


def verify_stage70(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError("Stage70 accepted local report missing")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("Stage70 report must be an object")
    graph = report.get("source_call_graph") or {}
    source = report.get("source_callsite_owners") or {}
    if (report.get("stage") != 70 or
            report.get("status") != "STATIC_DIRECT_CALL_PATH_FOUND_RUNTIME_PARENT_UNPROVEN" or
            report.get("dll_sha256") != DLL_SHA256 or
            graph.get("static_direct_call_path_to_constructor") != ["0xce00", "0x11b60"] or
            graph.get("path_found") is not True or
            source.get("0xe28f1", {}).get("direct_target_rva") != "0xce00" or
            source.get("0xbf364", {}).get("direct_target_rva") != "0xce00" or
            (report.get("claims") or {}).get("specific_stage64_reverse_object_linked_to_this_parent") is not False):
        raise ValueError("Stage70 accepted static-path provenance mismatch")
    return report


def rate_field_evidence(pe: previous.PEFunctions, read_function) -> dict:
    """Report rate reads plus all textual R14 definitions, without data-flow claims."""
    result = {}
    for callsite, (read_rva, expected, expected_owner) in CALLSITE_RATE_READS.items():
        owner = pe.owner(callsite)
        if owner.start != expected_owner:
            raise ValueError(f"Stage70 callsite owner changed: {callsite:#x}")
        instructions = read_function(owner.start, owner.end)
        actual = instructions.get(previous.IMAGE_BASE + read_rva)
        if actual != expected:
            raise ValueError(f"Original source-rate field instruction mismatch at {read_rva:#x}: {actual}")
        candidate_writes = []
        for va, insn in sorted(instructions.items()):
            if not owner.start <= va - previous.IMAGE_BASE <= read_rva:
                continue
            match = re.match(r"^(mov|lea|cmov\w*|xchg)\s+r14(?:d)?\s*,\s*(.+)$", insn)
            pop = re.match(r"^pop\s+r14\b", insn)
            if match or pop:
                operand = match.group(2) if match else ""
                category = ("stack_restore" if pop else
                            "address_expression" if match.group(1) == "lea" else
                            "memory" if "[" in operand else
                            "register" if re.match(r"[er][a-z0-9]+$", operand) else
                            "other")
                candidate_writes.append({
                    "rva": f"0x{va - previous.IMAGE_BASE:x}",
                    "kind": match.group(1) if match else "pop",
                    "operand_category": category,
                })
        result[f"0x{callsite:x}"] = {
            "function_owner_rva": f"0x{owner.start:x}",
            "source_rate_load_rva": f"0x{read_rva:x}",
            "source_rate_field": "[r14+0x8] float64" if callsite == 0xE28F1 else "[r14+0x20ec0] float32",
            "candidate_prior_r14_assignments": candidate_writes,
            "register_origin_proven": False,
            "runtime_sample_rate_value_proven": False,
            "limitations": "Linear disassembly order is not control-flow-aware; candidate writes are NOT a reaching-definition proof",
        }
    return result


def trace_nam_roots(pe: previous.PEFunctions, read_function,
                    *, max_functions: int = MAX_GRAPH_FUNCTIONS,
                    max_depth: int = MAX_GRAPH_DEPTH) -> dict:
    """Bounded direct-call ancestry from four pinned native NAM export RVAs."""
    targets = {pe.owner(at).start: f"0x{at:x}" for at in CALLSITE_RATE_READS}
    queue = deque()
    skipped_roots = {}
    for name, rva in NAM_EXPORT_RVAS.items():
        try:
            owner = pe.owner(rva)
        except ValueError:
            skipped_roots[name] = "NO_UNIQUE_PDATA_OWNER"
            continue
        queue.append((name, owner, 0, [owner.start]))
    seen = set()
    cache = {}
    paths = {f"0x{at:x}": None for at in CALLSITE_RATE_READS}
    edges = []
    indirect = 0
    oversize = []
    while queue and len(seen) < max_functions:
        name, owner, depth, path = queue.popleft()
        key = (name, owner.start)
        if key in seen:
            continue
        seen.add(key)
        if owner.start in targets:
            target_label = targets[owner.start]
            if paths[target_label] is None:
                paths[target_label] = {"origin_export": name,
                                       "owner_chain": [f"0x{x:x}" for x in path]}
        if len(paths) == 2 and all(paths.values()):
            break
        if owner.end - owner.start > previous.MAX_FUNCTION_BYTES:
            oversize.append(f"0x{owner.start:x}")
            continue
        if owner.start not in cache:
            cache[owner.start] = previous.direct_calls(read_function(owner.start, owner.end))
        calls, unresolved = cache[owner.start]
        indirect += unresolved
        for at, target in calls:
            try:
                callee = pe.owner(target)
            except ValueError:
                continue
            edges.append({"root": name, "callsite_rva": f"0x{at:x}",
                          "parent_rva": f"0x{owner.start:x}",
                          "callee_rva": f"0x{callee.start:x}"})
            if depth < max_depth and callee.start not in path:
                queue.append((name, callee, depth + 1, path + [callee.start]))
    return {
        "static_ancestry_to_candidate_callsites": paths,
        "visited_root_function_pairs": len(seen),
        "resolved_direct_edges": edges,
        "unresolved_indirect_call_count": indirect,
        "oversized_function_rvas_skipped": sorted(set(oversize)),
        "export_roots_without_unique_pdata_owner": skipped_roots,
        "bounded_search_incomplete": (bool(queue or oversize or skipped_roots)
                                      and not all(paths.values())),
        "max_depth": max_depth, "max_function_visits": max_functions,
        "source_only_not_runtime_provenance": True,
    }


def audit(dll: Path, stage70: Path, objdump: str) -> dict:
    previous.verify_dll(dll)
    verify_stage70(stage70)
    data = dll.read_bytes()
    pe = previous.PEFunctions(data)
    exports = PEExports(data).verify_named_anchors()
    read_cache = {}

    def read(start: int, end: int) -> dict[int, str]:
        if start not in read_cache:
            read_cache[start] = previous.disassemble(dll, objdump, start, end)
        return read_cache[start]

    rates = rate_field_evidence(pe, read)
    ancestry = trace_nam_roots(pe, read)
    found = sum(x is not None for x in ancestry["static_ancestry_to_candidate_callsites"].values())
    status = ("STATIC_NAM_ANCESTRY_TO_BOTH_CALLSITES_FOUND_RUNTIME_UNPROVEN" if found == 2 else
              "STATIC_NAM_ANCESTRY_TO_ONE_CALLSITE_FOUND_RUNTIME_UNPROVEN" if found == 1 else
              "BOUNDED_STATIC_NAM_ANCESTRY_NOT_FOUND_RUNTIME_UNPROVEN")
    return {
        "stage": 71, "schema_version": 1, "status": status,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dll_sha256": DLL_SHA256, "stage70_accepted_direct_path": True,
        "verified_named_nam_exports": exports,
        "source_rate_loads": rates, "nam_direct_call_ancestry": ancestry,
        "claims": {
            "original_named_nam_export_rvas_verified": True,
            "original_source_rate_field_loads_verified": True,
            "static_ancestry_candidate_count": found,
            "runtime_stage64_reverse_parent_proven": False,
            "runtime_original_48000_input_rate_proven": False,
            "whole_vendor_antialias_attenuation_proven": False,
        },
        "scope": "SHA-pinned PE export/.pdata and LLVM direct-call only; no original DLL execution, Frida, audio, or native sample data",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--stage70", type=Path, required=True)
    parser.add_argument("--objdump", default="llvm-objdump")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out and args.out.resolve() in (args.dll.resolve(), args.stage70.resolve()):
        raise ValueError("Refusing to overwrite input artifact")
    report = audit(args.dll, args.stage70, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ancestry = report["nam_direct_call_ancestry"]
    summary = {
        "stage": report["stage"], "status": report["status"],
        "verified_named_nam_exports": report["verified_named_nam_exports"],
        "source_rate_loads": report["source_rate_loads"],
        "static_ancestry_to_candidate_callsites": ancestry["static_ancestry_to_candidate_callsites"],
        "visited_root_function_pairs": ancestry["visited_root_function_pairs"],
        "direct_edge_count": len(ancestry["resolved_direct_edges"]),
        "direct_edges_sample": ancestry["resolved_direct_edges"][:20],
        "unresolved_indirect_call_count": ancestry["unresolved_indirect_call_count"],
        "bounded_search_incomplete": ancestry["bounded_search_incomplete"],
        "runtime_stage64_reverse_parent_proven": False,
        "runtime_original_48000_input_rate_proven": False,
        "full_report_path": str(args.out) if args.out else None,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            struct.error, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print("[STAGE71 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
