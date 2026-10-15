#!/usr/bin/env python3
"""Stage72: original-DLL source-only provenance for two 44.1k resampler callers.

Read the exact-SHA Windows PE64 DLL as inert bytes. Verify native instruction
anchors, distinguish source-file sample rate from a caller-supplied rate, and
follow local R14 assignments through a conservative bounded CFG. Neither a
source branch nor a nominal constant is a Stage64 runtime-parent observation.
GNU binutils objdump and LLVM objdump are both supported (no vendor execution).
"""
from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage70"))
import audit_parent_calls as previous

BASE = previous.IMAGE_BASE
DLL_SHA256 = previous.DLL_SHA256
FLOAT44100_RVA = 0x24CDF0
MAX_SPAN = 32768
MAX_CFG_STATES = 30000

# Exact instruction addresses and operands (normalized to GNU/LLVM Intel syntax).
# All addresses are *RVA*; no copied proprietary code or audio is distributed.
PINS: dict[str, dict[int, str]] = {
    "audio_conversion_caller": {
        0xE27C0: "mov r8b,0x1",
        0xE27C3: "mov rdx,rbx",
        0xE27C6: "lea rcx,[rsp+0x40]",
        0xE27CB: "call 0x180143310",
        0xE27D0: "mov r14,rax",
        0xE283D: "test r14,r14",
        0xE2840: "je 0x1800e2ac3",
        0xE28D4: "mov rcx,r14",
        0xE28D7: "call 0x1801421c0",
        0xE28DC: "movsd xmm1,qword ptr [r14+0x8]",
        0xE28E2: "cvtpd2ps xmm1,xmm1",
        0xE28E6: "movss xmm2,dword ptr [rip+0x16a502]",
        0xE28F1: "call 0x18000ce00",
    },
    "audio_object_factory": {
        0x143335: "mov ecx,0xb0",
        0x14333A: "call 0x1800a3184",
        0x143344: "mov rdx,rsi",
        0x143347: "mov rcx,rax",
        0x14334A: "call 0x18008bb70",
        0x14334F: "mov rbx,rax",
        0x1433BE: "call rax",  # alternative factory is indirect; unresolved
        0x1433C0: "mov rbx,rax",
        0x143408: "movsd xmm1,qword ptr [rax+0x8]",
        0x14344E: "mov rax,rbx",
        0x143465: "ret",
    },
    "wav_reader_branch": {
        0x8BBE3: "mov qword ptr [rdi+0x8],rsi",
        0x8BE4D: "cmp ebx,0x20746d66",  # ASCII fmt + space, little-endian
        0x8BE82: "call qword ptr [rax+0x40]",  # input-source vtable
        0x8BE85: "movd xmm0,eax",
        0x8BE89: "cvtdq2pd xmm0,xmm0",
        0x8BE8D: "movsd qword ptr [rdi+0x8],xmm0",
    },
    "context_rate_consumer": {
        0xBE88B: "mov r14,rcx",
        0xBF358: "movss xmm1,dword ptr [r14+0x20ec0]",
        0xBF364: "call 0x18000ce00",
    },
    "constant_44100_context_caller": {
        0xF99A: "lea rcx,[rbp+0x100]",
        0xF9A1: "call 0x1800c04b0",
        0xF9A7: "movss xmm1,dword ptr [rip+0x23d441]",
        0xF9AF: "lea rcx,[rbp+0x100]",
        0xF9B6: "call 0x1800bfe00",
        0xFA3A: "lea rcx,[rbp+0x100]",
        0xFA41: "call 0x1800be830",
    },
    "parameter_context_caller": {
        0x10287: "movss xmm6,dword ptr [rbp+0x27b20]",
        0x10446: "lea rcx,[rbp+0x150]",
        0x1044D: "call 0x1800c04b0",
        0x10453: "movaps xmm1,xmm6",
        0x10456: "lea rcx,[rbp+0x150]",
        0x1045D: "call 0x1800bfe00",
        0x104DA: "lea rcx,[rbp+0x150]",
        0x104E1: "call 0x1800be830",
    },
    "context_rate_initializer": {
        0xBFE16: "mov rdi,rcx",
        0xBFE1C: "movaps xmm10,xmm1",
        0xBFE20: "mov ecx,dword ptr [rcx+0x27918]",
        0xBFE28: "jne 0x1800c0242",
        0xBFEF9: "movss dword ptr [rdi+0x20ec0],xmm10",
        0xC03AE: "movss dword ptr [rdi+0x20ec0],xmm10",
    },
    "context_constructor": {
        0xC04B0: "xor r8d,r8d",
        0xC0626: "mov qword ptr [rcx+0x27918],r8",
        0xC0650: "ret",
    },
}


def normalize_asm(raw: str) -> str:
    """Strip comments and layout variations only; retain operand semantics."""
    raw = raw.split("#", 1)[0].split(";", 1)[0].lower().strip()
    raw = " ".join(raw.split())
    raw = re.sub(r"\s*,\s*", ",", raw)
    raw = re.sub(r"\s*\+\s*", "+", raw)
    raw = re.sub(r"\s*-\s*", "-", raw)
    return raw


def parse_disassembly(raw: str, start: int, end: int) -> dict[int, str]:
    result = {}
    for line in raw.splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]+):\s+(.+)$", line)
        if not match:
            continue
        va = int(match.group(1), 16)
        if BASE + start <= va < BASE + end:
            instruction = normalize_asm(match.group(2))
            if not instruction or va in result:
                raise ValueError("Empty/duplicate objdump instruction address")
            result[va] = instruction
    if not result:
        raise ValueError(f"No original-PE disassembly in RVA span {start:#x}..{end:#x}")
    return result


def select_objdump(explicit: str | None) -> tuple[str, str]:
    path = (shutil.which(explicit) if explicit else
            shutil.which("llvm-objdump") or shutil.which("objdump"))
    if path is None:
        raise FileNotFoundError("No llvm-objdump or GNU objdump found")
    result = subprocess.run([path, "--version"], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Could not inspect objdump version")
    version = result.stdout.lower()
    if "llvm" in version:
        return path, "LLVM"
    if "gnu objdump" in version:
        return path, "GNU"
    raise ValueError("Unsupported disassembler; LLVM or GNU objdump required")


def read_disassembly(dll: Path, tool: str, backend: str,
                     start: int, end: int) -> dict[int, str]:
    if not 0 <= start < end or end - start > MAX_SPAN:
        raise ValueError("Out-of-bounds static disassembly request")
    if backend == "LLVM":
        flags = ["--disassemble", "--no-show-raw-insn", "--x86-asm-syntax=intel"]
    elif backend == "GNU":
        flags = ["-D", "-M", "intel", "--no-show-raw-insn"]
    else:
        raise ValueError("Unknown disassembler backend")
    cmd = [tool, *flags, f"--start-address={BASE + start:#x}",
           f"--stop-address={BASE + end:#x}", str(dll)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(f"{backend} objdump failed at {start:#x}: {proc.stderr[-800:]}")
    return parse_disassembly(proc.stdout, start, end)


def pe_file_bytes(data: bytes, rva: int, size: int) -> bytes:
    """Read native PE data by section-backed RVA, never via live process."""
    if not 0 < size <= 16 or len(data) < 0x100 or data[:2] != b"MZ":
        raise ValueError("Invalid PE byte-range request")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Missing PE signature")
    coff = pe + 4
    count, opt_size = struct.unpack_from("<H", data, coff + 2)[0], struct.unpack_from("<H", data, coff + 16)[0]
    table = coff + 20 + opt_size
    if not 1 <= count <= 64 or table + count * 40 > len(data):
        raise ValueError("Missing PE section table")
    matches = []
    for index in range(count):
        off = table + index * 40
        va, rawsize, rawptr = (struct.unpack_from("<I", data, off + 12)[0],
                               struct.unpack_from("<I", data, off + 16)[0],
                               struct.unpack_from("<I", data, off + 20)[0])
        if va <= rva and rva + size <= va + rawsize:
            pos = rawptr + rva - va
            if pos + size <= len(data):
                matches.append(data[pos:pos + size])
    if len(matches) != 1:
        raise ValueError(f"PE RVA data not uniquely file-backed: {rva:#x}")
    return matches[0]


def verify_pins(groups: dict[str, dict[int, str]],
                instructions: dict[int, str]) -> dict[str, list[str]]:
    hits = {}
    for name, pins in groups.items():
        hits[name] = []
        for rva, expected in pins.items():
            actual = instructions.get(BASE + rva)
            if actual != normalize_asm(expected):
                raise ValueError(f"Source anchor mismatch at {rva:#x}: {actual!r} != {expected!r}")
            hits[name].append(f"0x{rva:x}")
    return hits


def local_r14_cfg(instructions: dict[int, str], *, start_rva: int,
                  target_rva: int, assignment_rva: int, label: str) -> dict:
    """Conservative intra-function R14 state propagation, not runtime tracing.

    All branch arms are considered. Calls preserve R14 under the Windows x64
    nonvolatile-register ABI. Indirect jumps/unparsed branches are explicitly
    incomplete, and assembly scanning is not an interprocedural alias proof.
    """
    source = BASE + start_rva
    target = BASE + target_rva
    order = sorted(va for va in instructions if va >= source)
    if source not in instructions or target not in instructions:
        raise ValueError("CFG source/target address not decoded")
    nxt = {va: order[i + 1] if i + 1 < len(order) else None
           for i, va in enumerate(order)}
    seen = set()
    q = deque([(source, "ENTRY_UNTRACED")])
    states = set()
    unresolved = set()
    while q:
        if len(seen) >= MAX_CFG_STATES:
            unresolved.add("CFG_STATE_BUDGET")
            break
        va, state = q.popleft()
        if (va, state) in seen:
            continue
        seen.add((va, state))
        if va == target:
            states.add(state)
            continue
        instruction = instructions[va]
        if va == BASE + assignment_rva:
            state = label
        elif (re.match(r"^(?!cmp\b|test\b|push\b|call\b|jmp\b)\w+\s+r14(?:d|w|b)?\b", instruction)
              or re.match(r"^xchg\s+[^,]+,r14(?:d|w|b)?\b", instruction)):
            state = "OTHER_R14_WRITE"
        operation = instruction.split(" ", 1)[0]
        next_va = nxt.get(va)
        edges = []
        if operation in {"ret", "retn", "int3", "ud2"}:
            continue
        if operation.startswith("j") or operation.startswith("loop"):
            operand = instruction.partition(" ")[2]
            found = re.fullmatch(r"0x([0-9a-f]+)", operand)
            if not found:
                unresolved.add(f"{va - BASE:#x}:INDIRECT_OR_UNKNOWN_BRANCH")
            else:
                branch = int(found.group(0), 16)
                if branch in instructions:
                    edges.append(branch)
                elif source <= branch <= max(order):
                    unresolved.add(f"{va - BASE:#x}:UNDECODED_TARGET")
            if operation != "jmp" and next_va is not None:
                edges.append(next_va)
        elif next_va is not None:
            edges.append(next_va)
        for successor in edges:
            pair = (successor, state)
            if pair not in seen:
                q.append(pair)
    return {
        "target_rva": f"0x{target_rva:x}",
        "entry_rva": f"0x{start_rva:x}",
        "assignment_rva": f"0x{assignment_rva:x}",
        "possible_r14_states_at_target": sorted(states),
        "visited_address_state_pairs": len(seen),
        "unresolved_branch_sites": sorted(unresolved),
        "source_reaches_target": bool(states),
        "unique_local_r14_assignment_on_decoded_paths": (
            states == {label} and not unresolved),
        "runtime_object_identity_proven": False,
    }


def audit(dll: Path, objdump: str | None) -> dict:
    previous.verify_dll(dll)
    data = dll.read_bytes()
    pe = previous.PEFunctions(data)
    tool, backend = select_objdump(objdump)
    reads = {}
    all_ins = {}
    ranges = {
        "audio_conversion_caller": (0xE28F1, None),
        "audio_object_factory": (0x143310, None),
        "wav_reader_branch": (0x8BE8D, None),
        "context_rate_consumer": (0xBF364, None),
        "constant_44100_context_caller": (0xFA41, None),
        "parameter_context_caller": (0x104E1, None),
        "context_rate_initializer": (0xBFE00, 0xC044A),
        # Leaf initializer omits .pdata: use an explicitly bounded native
        # entry/ret span and exact instruction anchors, never invent an owner.
        "context_constructor": (0xC04B0, 0xC0651),
    }
    for label, (owner_rva, explicit_end) in ranges.items():
        if explicit_end is None:
            owner = pe.owner(owner_rva)
            start, end = owner.start, owner.end
        else:
            start, end = owner_rva, explicit_end
        part = read_disassembly(dll, tool, backend, start, end)
        reads[label] = part
        all_ins.update(part)
    validated = verify_pins(PINS, all_ins)
    rate_constant = struct.unpack("<f", pe_file_bytes(data, FLOAT44100_RVA, 4))[0]
    if rate_constant != 44100.0:
        raise ValueError(f"Original 0x24cdf0 sample-rate constant changed: {rate_constant}")
    local = {
        "audio_object": local_r14_cfg(reads["audio_conversion_caller"],
                                      start_rva=pe.owner(0xE28F1).start,
                                      target_rva=0xE28DC,
                                      assignment_rva=0xE27D0,
                                      label="rax_return_from_helper_0x143310"),
        "context_object": local_r14_cfg(reads["context_rate_consumer"],
                                        start_rva=pe.owner(0xBF364).start,
                                        target_rva=0xBF358,
                                        assignment_rva=0xBE88B,
                                        label="entry_rcx_argument"),
    }
    return {
        "stage": 72,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "STATIC_CALLER_RATE_PROVENANCE_FOUND_RUNTIME_STAGE64_UNPROVEN",
        "dll_sha256": DLL_SHA256,
        "disassembler_backend": backend,
        "verified_instruction_count": sum(map(len, validated.values())),
        "verified_instruction_groups": validated,
        "local_r14_cfg": local,
        "audio_object_0xe28f1": {
            "r14_assignment": "0xe27d0: RAX result of helper direct call at 0xe27cb",
            "helper": "0x143310, native object constructor 0x8bb70 and unresolved alternate indirect factory call 0x1433be",
            "wav_fmt_branch": "0x8be4d compares 'fmt '; 0x8be82 reads source integer, 0x8be85/0x8be89 converts to f64, 0x8be8d stores object+0x8",
            "local_source_rate_load": "0xe28dc: xmm1=f64 [r14+0x8], converted to float32 at 0xe28e2",
            "runtime_input_rate_hz": None,
        },
        "context_object_0xbf364": {
            "r14_assignment": "0xbe88b: R14=entry RCX, Windows x64 first pointer argument",
            "known_direct_caller_sites": ["0xfa41", "0x104e1"],
            "constant_44100_caller": "0xf9a1 constructs [rbp+0x100]; 0xf9a7 XMM1=PE f32 44100 at RVA 0x24cdf0; 0xf9b6 initializes context; 0xfa41 passes same stack object to 0xbe830",
            "parameter_rate_caller": "0x10287 XMM6 from [rbp+0x27b20] stack input; 0x1044d constructs [rbp+0x150]; 0x10453 passes XMM6 as XMM1 to 0xbfe00; 0x104e1 passes same context object",
            "initializer": "0xc0626 fresh constructor sets context+0x27918=0; 0xbfe1c XMM10=XMM1, 0xbfe20/0xbfe28 branches on flag; 0xbfef9 or conditional 0xc03ae stores f32 XMM10 to context+0x20ec0",
            "local_source_rate_load": "0xbf358: xmm1=f32 [r14+0x20ec0]",
            "constant_rva": "0x24cdf0",
            "pinned_constant_44100_float32": rate_constant,
            "runtime_input_rate_hz": None,
        },
        "claims": {
            "original_dll_executed": False,
            "source_level_rate_field_chains_identified": True,
            "all_indirect_call_and_alias_paths_resolved": False,
            "actual_stage64_reverse_parent_verified": False,
            "live_original_source_rate_48000_verified": False,
            "complete_original_96k_to_44100_antialias_verified": False,
        },
        "next_gate": "Do not hook or edit DSP: review decoded local R14 CFG and investigate conditional entry to direct callers / unresolved file factories before any separately approved metadata-only runtime probe.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--objdump", default=None, help="LLVM or GNU objdump (auto by default)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out and args.out.resolve() == args.dll.resolve():
        raise ValueError("Refusing to overwrite original DLL")
    report = audit(args.dll, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    compact = {
        "stage": report["stage"], "status": report["status"],
        "disassembler_backend": report["disassembler_backend"],
        "verified_instruction_count": report["verified_instruction_count"],
        "local_r14_cfg": report["local_r14_cfg"],
        "fixed_context_caller_rate": report["context_object_0xbf364"]["pinned_constant_44100_float32"],
        "context_direct_callers": report["context_object_0xbf364"]["known_direct_caller_sites"],
        "stage64_runtime_parent_proven": False,
        "live_original_48000_input_proven": False,
        "full_report_path": str(args.out) if args.out else None,
    }
    print(json.dumps(compact, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, RuntimeError, OSError,
            struct.error, UnicodeDecodeError) as exc:
        print("[STAGE72 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
