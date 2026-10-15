#!/usr/bin/env python3
"""Stage70: SHA-gated, read-only native resampler parent-call exploration.

This tool disassembles a bounded set of PE64 functions as *data*. It finds
direct static calls from two Stage69 44.1-kHz callsites into the shared helper
and, where possible, from that helper to the CDSPResampler24 constructor.
No vendor code is loaded or executed. No process is attached. A static call
edge is NOT evidence of a particular Stage64 runtime object's parent.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

DLL_SHA256 = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
STAGE64_SHA256 = "aa32d8440b532708ce3551404f5a4292791abd31aba197003e850f61f22683ff"
IMAGE_BASE = 0x180000000
CALLSITES = (0xE28F1, 0xBF364)
HELPER_RVA = 0xCE00
CONSTRUCTOR_RVA = 0x11B60
MAX_FUNCTION_BYTES = 32768
MAX_FUNCTIONS = 64
MAX_DEPTH = 4


@dataclass(frozen=True, order=True)
class Function:
    start: int
    end: int


class PEFunctions:
    """Read the PE64 exception (.pdata) directory; no PE runtime loading."""

    def __init__(self, data: bytes):
        if len(data) < 0x100 or data[:2] != b"MZ":
            raise ValueError("Not a complete MZ executable")
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
            raise ValueError("Invalid PE signature or truncated header")
        coff = pe + 4
        machine, count = struct.unpack_from("<HH", data, coff)
        opt_size = struct.unpack_from("<H", data, coff + 16)[0]
        opt = coff + 20
        if machine != 0x8664 or opt + opt_size > len(data) or opt_size < 144:
            raise ValueError("Expected complete x64 PE32+ optional header")
        if struct.unpack_from("<H", data, opt)[0] != 0x20B:
            raise ValueError("Expected PE32+ image")
        self.image_base = struct.unpack_from("<Q", data, opt + 24)[0]
        if self.image_base != IMAGE_BASE:
            raise ValueError("Original PE image-base mismatch")
        directory_count = struct.unpack_from("<I", data, opt + 108)[0]
        if directory_count < 4:
            raise ValueError("PE exception directory absent")
        exc_rva, exc_size = struct.unpack_from("<II", data, opt + 112 + 3 * 8)
        if exc_size == 0 or exc_size % 12 or exc_size > 2_000_000:
            raise ValueError("Missing/invalid PE64 RUNTIME_FUNCTION directory")
        table = opt + opt_size
        if count < 1 or count > 64 or table + count * 40 > len(data):
            raise ValueError("Invalid PE section table")
        sections = []
        for i in range(count):
            off = table + i * 40
            vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
            sections.append((va, vsize, rawsize, rawptr))
        exception_offset = None
        for va, vsize, rawsize, rawptr in sections:
            if va <= exc_rva and exc_rva + exc_size <= va + rawsize:
                exception_offset = rawptr + exc_rva - va
                break
        if (exception_offset is None or
                exception_offset + exc_size > len(data)):
            raise ValueError("PE exception directory not file-backed")
        functions = []
        for off in range(exception_offset, exception_offset + exc_size, 12):
            begin, end, unwind = struct.unpack_from("<III", data, off)
            if (begin, end, unwind) == (0, 0, 0):
                continue
            if not 0 < begin < end and 0 < unwind:
                raise ValueError("Invalid PE64 RUNTIME_FUNCTION entry")
            functions.append(Function(begin, end))
        self.functions = sorted(set(functions))
        if not self.functions:
            raise ValueError("PE64 exception table contains no functions")
        self._starts = [f.start for f in self.functions]

    def owner(self, rva: int) -> Function:
        index = bisect_right(self._starts, rva) - 1
        if index < 0 or rva >= self.functions[index].end:
            raise ValueError(f"No unique .pdata function for RVA {rva:#x}")
        if index and self.functions[index - 1].end > rva:
            raise ValueError(f"Overlapping .pdata functions at RVA {rva:#x}")
        return self.functions[index]


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_dll(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError("Original DLL not found")
    actual = sha_file(path)
    if actual != DLL_SHA256:
        raise ValueError(f"Original DLL SHA mismatch: {actual}")


def verify_stage69(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError("Stage69 accepted local JSON not found")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("Stage69 report must be an object")
    source = report.get("source") or {}
    claims = report.get("claims") or {}
    if (report.get("stage") != 69 or
            report.get("status") != "SOURCE_FIR_BEFORE_FRACTIONAL_CONFIRMED_DYNAMIC_PARENT_UNPROVEN" or
            report.get("dll_sha256") != DLL_SHA256 or
            report.get("stage64_sha256") != STAGE64_SHA256 or
            source.get("instruction_count") != 34 or
            len(source.get("verified_instruction_rvas", [])) != 34 or
            claims.get("upstream_filter_stage_exists_in_native_resampler_constructor") is not True or
            claims.get("specific_stage64_reverse_call_dynamic_parent_verified") is not False):
        raise ValueError("Stage69 acceptance/provenance gate failed")


def parse_disassembly(output: str) -> dict[int, str]:
    instructions = {}
    for line in output.splitlines():
        found = re.match(r"^\s*([0-9a-fA-F]+):\s*(.+)$", line)
        if found:
            instructions[int(found.group(1), 16)] = " ".join(
                found.group(2).strip().lower().split())
    return instructions


def direct_call_target(instruction: str) -> int | None:
    match = re.match(r"^call\s+(0x[0-9a-f]+)\b", instruction)
    if match:
        return int(match.group(1), 16)
    return None  # indirect calls, jumps and operand data are NOT resolved


def disassemble(dll: Path, objdump: str, start: int, end: int) -> dict[int, str]:
    if not 0 <= start < end or end - start > MAX_FUNCTION_BYTES:
        raise ValueError(f"Unsafe/unbounded disassembly span {start:#x}:{end:#x}")
    run = subprocess.run([
        objdump, "--disassemble", "--no-show-raw-insn",
        "--x86-asm-syntax=intel", f"--start-address={IMAGE_BASE + start:#x}",
        f"--stop-address={IMAGE_BASE + end:#x}", str(dll),
    ], capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(f"llvm-objdump failed for {start:#x}: {run.stderr[-1000:]}")
    instructions = parse_disassembly(run.stdout)
    if not instructions:
        raise ValueError(f"No instructions for source span {start:#x}:{end:#x}")
    return instructions


def direct_calls(instructions: dict[int, str]) -> tuple[list[tuple[int, int]], int]:
    calls = []
    indirect = 0
    for va, instruction in instructions.items():
        if instruction.startswith("call "):
            target = direct_call_target(instruction)
            if target is None:
                indirect += 1
            else:
                calls.append((va - IMAGE_BASE, target - IMAGE_BASE))
    return calls, indirect


def trace(pe: PEFunctions, read_function, *, max_functions: int = MAX_FUNCTIONS,
          max_depth: int = MAX_DEPTH) -> dict:
    """Breadth-first *direct-call* graph, never inferred runtime provenance."""
    helper = pe.owner(HELPER_RVA)
    ctor = pe.owner(CONSTRUCTOR_RVA)
    queue = deque([(helper, 0, [helper.start])])
    seen = set()
    edges = []
    indirect_count = 0
    reached_path = None
    skipped_oversize = []
    while queue and len(seen) < max_functions:
        owner, depth, path = queue.popleft()
        if owner.start in seen:
            continue
        seen.add(owner.start)
        if owner.end - owner.start > MAX_FUNCTION_BYTES:
            skipped_oversize.append(owner.start)
            continue
        calls, indirect = direct_calls(read_function(owner.start, owner.end))
        indirect_count += indirect
        for at, target in calls:
            try:
                target_owner = pe.owner(target)
            except ValueError:
                continue  # import or other non-.pdata target; NOT inferred
            edges.append({"at_rva": f"0x{at:x}",
                          "from_function_rva": f"0x{owner.start:x}",
                          "target_rva": f"0x{target:x}",
                          "to_function_rva": f"0x{target_owner.start:x}"})
            if target_owner == ctor and reached_path is None:
                reached_path = [f"0x{x:x}" for x in path + [ctor.start]]
                break
            if (depth < max_depth and target_owner.start not in seen and
                    target_owner.start not in path):
                queue.append((target_owner, depth + 1, path + [target_owner.start]))
        if reached_path is not None:
            break
    return {
        "helper_function_rva": f"0x{helper.start:x}",
        "constructor_function_rva": f"0x{ctor.start:x}",
        "static_direct_call_path_to_constructor": reached_path,
        "path_found": reached_path is not None,
        "visited_function_count": len(seen),
        "direct_edges": edges,
        "unresolved_indirect_call_instructions": indirect_count,
        "oversized_skipped_function_rvas": [f"0x{x:x}" for x in skipped_oversize],
        "bounded_search_incomplete": bool(queue or skipped_oversize) and reached_path is None,
        "max_depth": max_depth,
        "max_functions": max_functions,
    }


def audit(dll: Path, stage69: Path, objdump: str) -> dict:
    verify_dll(dll)
    verify_stage69(stage69)
    pe = PEFunctions(dll.read_bytes())
    owners = {}
    for at in CALLSITES:
        owner = pe.owner(at)
        instructions = disassemble(dll, objdump, at, at + 6)
        target = direct_call_target(instructions.get(IMAGE_BASE + at, ""))
        if target != IMAGE_BASE + HELPER_RVA:
            raise ValueError(f"Stage69 callsite no longer targets shared helper at {at:#x}")
        owners[f"0x{at:x}"] = {
            "owner_start_rva": f"0x{owner.start:x}",
            "owner_end_rva": f"0x{owner.end:x}",
            "direct_target_rva": f"0x{HELPER_RVA:x}",
        }
    graph = trace(pe, lambda start, end: disassemble(dll, objdump, start, end))
    return {
        "stage": 70, "schema_version": 1,
        "status": ("STATIC_DIRECT_CALL_PATH_FOUND_RUNTIME_PARENT_UNPROVEN"
                   if graph["path_found"] else
                   "BOUNDED_STATIC_DIRECT_CALL_PATH_NOT_FOUND_RUNTIME_PARENT_UNPROVEN"),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dll_sha256": DLL_SHA256, "stage69_provenance": "ACCEPTED_34_OF_34",
        "stage64_original_archive_sha256": STAGE64_SHA256,
        "source_callsite_owners": owners, "source_call_graph": graph,
        "claims": {
            "both_candidate_callsites_reach_shared_helper_directly": True,
            "static_helper_to_constructor_direct_call_path_found": graph["path_found"],
            "specific_stage64_reverse_object_linked_to_this_parent": False,
            "vendor_live_48000_input_rate_verified": False,
            "vendor_complete_antialiasing_measured": False,
            "indirect_call_edges_resolved": False,
        },
        "scope": "PE64 .pdata and LLVM direct-call graph only; no DLL execution, Frida, audio, or captured f64 access",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    parser.add_argument("--stage69", required=True, type=Path)
    parser.add_argument("--objdump", default="llvm-objdump")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out and args.out.resolve() in (args.dll.resolve(), args.stage69.resolve()):
        raise ValueError("Refusing to overwrite input artifact")
    report = audit(args.dll, args.stage69, args.objdump)
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    # Keep the user-facing terminal result short: the complete static-edge
    # inventory remains in the ignored local --out report for later review.
    graph = report["source_call_graph"]
    summary = {
        "stage": report["stage"], "status": report["status"],
        "source_callsite_owners": report["source_callsite_owners"],
        "helper_function_rva": graph["helper_function_rva"],
        "constructor_function_rva": graph["constructor_function_rva"],
        "static_direct_call_path_to_constructor": graph["static_direct_call_path_to_constructor"],
        "visited_function_count": graph["visited_function_count"],
        "direct_edge_count": len(graph["direct_edges"]),
        "direct_edges_sample": graph["direct_edges"][:20],
        "unresolved_indirect_call_instructions": graph["unresolved_indirect_call_instructions"],
        "oversized_skipped_function_rvas": graph["oversized_skipped_function_rvas"],
        "bounded_search_incomplete": graph["bounded_search_incomplete"],
        "specific_stage64_reverse_object_linked_to_this_parent": False,
        "full_report_path": str(args.out) if args.out else None,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            struct.error, json.JSONDecodeError) as exc:
        print("[STAGE70 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
