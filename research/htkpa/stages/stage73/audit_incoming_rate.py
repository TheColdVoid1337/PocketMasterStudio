#!/usr/bin/env python3
"""Stage73: source-only parent calls and rate argument provenance in the PE.

Operates on the SHA-pinned original DLL as file data. No DLL execution,
native/audio captures, Frida or production change. Uses GNU or LLVM objdump.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage72"))
import audit_rate_provenance as stage72

BASE = stage72.BASE
DLL_SHA256 = stage72.DLL_SHA256
MAX_SOURCE_STATES = 24000

PINS = {
    "mode_selector_0x11550": {
        0x1158B: "cmp dword ptr [rcx+0x270],0x1",
        0x11592: "jne 0x180011670",
        0x11666: "call 0x18000ff40",
        0x11734: "call 0x180010e70",
    },
    "other_known_parent_0x60f20": {
        0x611AF: "call 0x18000ff40",
        0x6137D: "call 0x180010e70",
    },
    "fixed_44100_wrapper_0xff40": {
        0x10043: "call 0x18000e0e0",
        0x10048: "movd xmm0,eax",
        0x1004C: "cvtdq2pd xmm0,xmm0",
        0x10050: "ucomisd xmm0,qword ptr [rip+0x23ce98]",
        0x10058: "jp 0x1800100ba",
        0x1005A: "jne 0x1800100ba",
        0x100DA: "movsd xmm2,qword ptr [rip+0x23cc16]",
        0x1016D: "call 0x18000f940",
    },
    "passed_rate_wrapper_0x10e70": {
        0x10F7F: "call 0x18000e0e0",
        0x10F84: "movd xmm6,eax",
        0x10F88: "cvtdq2pd xmm6,xmm6",
        0x10F8C: "ucomisd xmm6,qword ptr [rip+0x23bf5c]",
        0x10F94: "jp 0x180010ff6",
        0x10F96: "jne 0x180010ff6",
        0x11016: "movaps xmm2,xmm6",
        0x11086: "cvtpd2ps xmm0,xmm6",
        0x11093: "movss dword ptr [rsp+0x20],xmm0",
        0x110AD: "call 0x180010230",
    },
    "shared_rate_helper_0xe0e0": {
        0xE855: "movsd xmm9,qword ptr [rbx+0x18]",
        0xE85B: "cvtpd2ps xmm9,xmm9",
        0xE9B5: "xorps xmm6,xmm6",
        0xE9B8: "comiss xmm6,xmm9",
        0xE9BC: "jb 0x18000e9f3",
        0xE9EA: "movss xmm9,dword ptr [rip+0x23e401]",
        0xEA01: "ucomiss xmm9,dword ptr [rip+0x23e3e7]",
        0xF620: "cvttss2si ebx,xmm9",
        0xF66B: "mov eax,ebx",
        0xF900: "mov eax,0xfffffffe",
    },
}

PE_F64 = {0x24CCF8: 44100.0, 0x24CEF0: -2.0}
PE_F32 = {0x24CDF0: 44100.0, 0x24CDF4: 48000.0}


def xmm9_cfg(insns: dict[int, str], *, start: int = 0xE0E0,
             target: int = 0xF620) -> dict:
    """Bounded two-arm CFG of XMM9 definitions before successful rate return.

    Windows x64 preserves XMM9 across conforming calls. An indirect branch,
    an unrecognized XMM9 definition or a missing instruction prevents a
    'closed source set' claim. We NEVER infer the selected runtime branch.
    """
    entry, final = BASE + start, BASE + target
    if entry not in insns or final not in insns:
        raise ValueError("Missing rate helper source/target instructions")
    addrs = sorted(va for va in insns if va >= entry)
    next_addr = {va: addrs[i + 1] if i + 1 < len(addrs) else None
                 for i, va in enumerate(addrs)}
    states = set()
    unresolved = set()
    queue = deque([(entry, "ENTRY_UNKNOWN")])
    visited = set()
    while queue:
        if len(visited) >= MAX_SOURCE_STATES:
            unresolved.add("BUDGET_EXCEEDED")
            break
        va, state = queue.popleft()
        if (va, state) in visited:
            continue
        visited.add((va, state))
        if va == final:
            states.add(state)
            continue
        insn = insns[va]
        if va == BASE + 0xE855:
            state = "f64_metadata_object_plus_0x18_to_f32"
        elif va == BASE + 0xE9EA:
            state = "conditional_f32_fallback_48000"
        elif (re.match(r"^\w+\s+xmm9(?:,|$)", insn)
              and insn != "cvtpd2ps xmm9,xmm9"
              and insn.split(" ", 1)[0] not in ("ucomiss", "comiss", "ucomisd", "comisd", "ptest")):
            state = "OTHER_XMM9_DEFINITION"
        opcode = insn.split(" ", 1)[0]
        nxt = next_addr[va]
        edges = []
        if opcode in ("ret", "retn", "int3", "ud2"):
            continue
        if opcode.startswith("j") or opcode.startswith("loop"):
            operand = insn.partition(" ")[2]
            address = re.fullmatch(r"0x[0-9a-f]+", operand)
            if address is None:
                unresolved.add(f"{va-BASE:#x}:UNRESOLVED_JUMP")
            else:
                branch = int(operand, 16)
                if branch in insns:
                    edges.append(branch)
                elif entry <= branch <= addrs[-1]:
                    unresolved.add(f"{va-BASE:#x}:UNDECODED_LOCAL_TARGET")
            if opcode != "jmp" and nxt is not None:
                edges.append(nxt)
        elif nxt is not None:
            edges.append(nxt)
        queue.extend((dest, state) for dest in edges if (dest, state) not in visited)
    return {
        "entry_rva": f"0x{start:x}",
        "target_conversion_rva": f"0x{target:x}",
        "possible_xmm9_sources": sorted(states),
        "visited_instruction_state_pairs": len(visited),
        "unresolved_local_jump_sites": sorted(unresolved),
        "closed_local_set_on_decoded_paths": bool(states) and not unresolved
            and states <= {"f64_metadata_object_plus_0x18_to_f32", "conditional_f32_fallback_48000"},
        "runtime_source_selected": False,
    }


def audit(dll: Path, objdump: str | None = None) -> dict:
    stage72.previous.verify_dll(dll)
    data = dll.read_bytes()
    pe = stage72.previous.PEFunctions(data)
    tool, backend = stage72.select_objdump(objdump)
    instructions = {}
    functions = {
        "mode_selector_0x11550": 0x11550,
        "other_known_parent_0x60f20": 0x60F20,
        "fixed_44100_wrapper_0xff40": 0xFF40,
        "passed_rate_wrapper_0x10e70": 0x10E70,
        "shared_rate_helper_0xe0e0": 0xE0E0,
    }
    for name, rva in functions.items():
        owner = pe.owner(rva)
        if owner.start != rva:
            raise ValueError(f"Stage73 expected function entry changed: {rva:#x}")
        fragment = stage72.read_disassembly(dll, tool, backend, owner.start, owner.end)
        instructions.update(fragment)
    validated = stage72.verify_pins(PINS, instructions)
    pe_values = {}
    for rva, value in PE_F64.items():
        actual = struct.unpack("<d", stage72.pe_file_bytes(data, rva, 8))[0]
        if actual != value:
            raise ValueError(f"Stage73 native f64 constant changed at {rva:#x}")
        pe_values[f"0x{rva:x}"] = actual
    for rva, value in PE_F32.items():
        actual = struct.unpack("<f", stage72.pe_file_bytes(data, rva, 4))[0]
        if actual != value:
            raise ValueError(f"Stage73 native f32 constant changed at {rva:#x}")
        pe_values[f"0x{rva:x}"] = actual
    source_states = xmm9_cfg(instructions)
    return {
        "stage": 73,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SOURCE_RATE_HELPER_TWO_CANDIDATES_RUNTIME_PARENT_UNPROVEN",
        "original_dll_sha256": DLL_SHA256,
        "disassembler_backend": backend,
        "verified_native_instruction_count": sum(map(len, validated.values())),
        "verified_instruction_groups": validated,
        "native_constant_values": pe_values,
        "direct_call_ancestry": {
            "fixed_44100_chain": ["0x11666/0x611af→0xff40", "0x1016d→0xf940", "0xfa41→0xbe830", "0xbf364→0xce00"],
            "passed_rate_chain": ["0x11734/0x6137d→0x10e70", "0x110ad→0x10230", "0x104e1→0xbe830", "0xbf364→0xce00"],
            "shared_rate_helper": "0xe0e0 directly called at 0x10043 and 0x10f7f",
        },
        "passed_rate_provenance": {
            "helper_result": "0xe0e0 returns integer EAX: 0xf620 XMM9→EBX and 0xf66b EBX→EAX; alternate error EAX=-2 at 0xf900",
            "metadata_source": "0xe855 reads f64 [rbx+0x18], 0xe85b converts to f32 XMM9",
            "conditional_default": "0xe9ea reads native f32 48000 from RVA 0x24cdf4 if the 0xe9bc JB branch is not taken",
            "caller_conversion": "0x10f84 EAX→XMM6; 0x10f88 int→f64; 0x11086 f64→f32; 0x11093 passes stack fifth argument to 0x10230 at 0x110ad",
            "negative_sentinel": "both wrappers compare helper's integer result converted to f64 with native -2.0 at RVA 0x24cef0",
            "conditional_branch_at_44100": "0xea01 compares XMM9 to PE f32 44100; comparison is not runtime evidence for selection",
            "rate_xmm9_cfg": source_states,
        },
        "fixed_rate_provenance": {
            "rate": 44100.0,
            "source": "0x100da loads PE f64 44100 at RVA 0x24ccf8 before 0x1016d direct call to 0xf940; f940 initializes context with separate f32 44100 constant (Stage72)",
            "helper_numeric_result": "not forwarded as the source rate to 0xf940 in this source callsite",
        },
        "claims": {
            "exact_native_sha_and_source_instructions_verified": True,
            "actual_stage64_reverse_parent_verified": False,
            "real_48000_fallback_branch_observed_running": False,
            "live_stage64_whole_resampler_48000_source_proven": False,
            "complete_vendor_antialiasing_verified": False,
            "original_dll_executed": False,
        },
        "next_gate": "Source-first identify metadata object at 0xe855 and branch conditions for its f64 +0x18 sample-rate field; no automatic hook or DSP edit.",
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
        "native_constant_values": report["native_constant_values"],
        "rate_xmm9_cfg": report["passed_rate_provenance"]["rate_xmm9_cfg"],
        "runtime_stage64_parent_proven": False,
        "full_report_path": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            struct.error, UnicodeDecodeError) as exc:
        print("[STAGE73 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
