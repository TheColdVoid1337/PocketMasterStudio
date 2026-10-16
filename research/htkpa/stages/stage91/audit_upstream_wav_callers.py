#!/usr/bin/env python3
"""Stage91: original-PE NAM/WAV route and four direct callers of 0xD4A0.

Offline static analysis only. The Stage89 Frida event at D786 cannot identify
which of these four higher-level callers was active in that native run.
The vendor DLL and Ghidra decompiled text are not distributed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage88"))
import audit_all_group_callsites as stage88


stage72 = stage88.stage72
BASE = stage88.BASE
DLL_SHA256 = stage88.stage79.DLL_SHA256
STATUS = "STATIC_NAM_WAV_ENTRY_FAMILIES_AND_EXPORTED_WRAPPER_VERIFIED_STAGE89_UPSTREAM_UNBOUND"
WAV_WORKER = 0xD4A0
NAM_WORKER = 0xE0E0
RUNTIME_BOUND_INNER_CALL = 0xD786
CALLS_TO_WAV = {
    0xEB1E: 0xE0E0,
    0x100EB: 0xFF40,
    0x11021: 0x10E70,
    0xAD5E9: 0xAD5D0,
}
CALLS_TO_NAM = {0x10043: 0xFF40, 0x10F7F: 0x10E70}
ROOT_OWNERS = sorted(set(CALLS_TO_WAV.values()) | set(CALLS_TO_NAM.values()))
FIXED_44100_F64 = 0x24CCF8
FIXED_44100_F32 = 0x24CDF0
ERROR_SENTINEL_F64 = 0x24CEF0
PUBLIC_NAM_STRINGS = {
    0x2446D8: b"[NAM] ========== getNamOutput start ==========" ,
    0x244708: b"[NAM] namFile: ",
    0x244848: b"[NAM] converting input sampleRate to ",
    0x244880: b"failed to convert input WAV to NAM sample rate. inputFile='",
    0x2448E8: b"input WAV read failed or is empty. inputFile='",
}
STATIC_PINS = {
    0xE0E0: {
        0xE2A0: "lea rdx,[rip+0x236431]",  # NAM getNamOutput literal
        0xE2FC: "lea rdx,[rip+0x236405]",  # NAM filename log
        0xEA01: "ucomiss xmm9,dword ptr [rip+0x23e3e7]",  # 44100f compare
        0xEA09: "jp 0x18000ea7d",
        0xEA0B: "jne 0x18000ea7d",
        0xEAA0: "lea rdx,[rip+0x235da1]",  # NAM rate-conversion log
        0xEB02: "mov dword ptr [rsp+0x20],0x18",
        0xEB0A: "mov r9d,0x1",
        0xEB10: "movaps xmm2,xmm7",
        0xEB13: "mov rdx,qword ptr [rsi]",
        0xEB16: "lea rcx,[rsp+0x200]",
        0xEB1E: "call 0x18000d4a0",
        0xEBB9: "lea rdx,[rip+0x235cc0]",  # NAM conversion failure
        0xF6D3: "lea rdx,[rip+0x23520e]",  # input WAV read failure
    },
    0xFF40: {
        0x10043: "call 0x18000e0e0",
        0x10048: "movd xmm0,eax",
        0x1004C: "cvtdq2pd xmm0,xmm0",
        0x10050: "ucomisd xmm0,qword ptr [rip+0x23ce98]",  # -2.0 failure
        0x100CF: "mov dword ptr [rsp+0x20],0x18",
        0x100D7: "mov r9d,r14d",
        0x100DA: "movsd xmm2,qword ptr [rip+0x23cc16]",  # 44100.0
        0x100E2: "mov rdx,qword ptr [r12]",
        0x100E6: "lea rcx,[rsp+0x70]",
        0x100EB: "call 0x18000d4a0",
    },
    0x10E70: {
        0x10F7F: "call 0x18000e0e0",
        0x10F84: "movd xmm6,eax",
        0x10F88: "cvtdq2pd xmm6,xmm6",
        0x10F8C: "ucomisd xmm6,qword ptr [rip+0x23bf5c]",  # -2.0
        0x1100B: "mov dword ptr [rsp+0x20],0x18",
        0x11013: "mov r9d,r14d",
        0x11016: "movaps xmm2,xmm6",
        0x11019: "mov rdx,qword ptr [r15]",
        0x1101C: "lea rcx,[rsp+0x68]",
        0x11021: "call 0x18000d4a0",
    },
    0xAD5D0: {
        0xAD5D6: "mov dword ptr [rsp+0x20],r9d",
        0xAD5DB: "mov rdx,rcx",
        0xAD5DE: "mov r9d,r8d",
        0xAD5E1: "lea rcx,[rsp+0x30]",
        0xAD5E6: "movaps xmm2,xmm1",
        0xAD5E9: "call 0x18000d4a0",
    },
}


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def read_bounded_pe_bytes(data: bytes, rva: int, size: int) -> bytes:
    """Assemble a small string/export span from Stage72's <=16-byte PE reads."""
    require(0 < size <= 256, "Unbounded original PE read")
    return b"".join(stage72.pe_file_bytes(data, rva + i, min(16, size - i))
                    for i in range(0, size, 16))


def decoded_calls(raw: str, rva_first: int, rva_end: int,
                  targets: set[int]) -> dict[int, list[int]]:
    """Only disassembler-decoded direct calls, never raw E8 byte-pattern hits."""
    require(len(raw) <= stage88.MAX_DISASSEMBLY_CHARS, "Unbounded disassembly")
    out = {target: [] for target in targets}
    for line in raw.splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]+):\s+(.+)$", line)
        if not match:
            continue
        addr = int(match.group(1), 16)
        if not BASE + rva_first <= addr < BASE + rva_end:
            continue
        insn = stage72.normalize_asm(match.group(2))
        for target in targets:
            if insn == f"call 0x{BASE + target:x}":
                out[target].append(addr - BASE)
    for target, locations in out.items():
        require(len(set(locations)) == len(locations),
                f"Duplicate direct call to {target:#x}")
    return {target: sorted(out[target]) for target in sorted(out)}


def verify_inventory(inventory: dict[int, list[int]], data: bytes) -> dict:
    expected = {WAV_WORKER: sorted(CALLS_TO_WAV),
                NAM_WORKER: sorted(CALLS_TO_NAM)}
    require(inventory == expected, "Original decoded upstream call inventory changed")
    for target, rv_as in expected.items():
        for call_rva in rv_as:
            encoded = stage72.pe_file_bytes(data, call_rva, 5)
            stage88.verify_rel32_bytes(encoded, call_rva, target)
    stage88.verify_rel32_bytes(stage72.pe_file_bytes(data, RUNTIME_BOUND_INNER_CALL, 5),
                                RUNTIME_BOUND_INNER_CALL, stage88.GROUP_HELPER)
    return {
        "d4a0_call_rvas": [f"0x{r:X}" for r in expected[WAV_WORKER]],
        "e0e0_call_rvas": [f"0x{r:X}" for r in expected[NAM_WORKER]],
        "original_exact_e8_rel32_verified": 1 + sum(map(len, expected.values())),
        "stage89_inner_call_d786_to_ce00_still_original": True,
    }


def verify_pins(insns_by_owner: dict[int, dict[int, str]]) -> dict:
    checks = {}
    for owner, pins in STATIC_PINS.items():
        require(owner in insns_by_owner, f"Missing original caller owner {owner:#x}")
        checks[f"0x{owner:X}"] = stage72.verify_pins(
            {"original_upstream_anchors": pins},
            insns_by_owner[owner])["original_upstream_anchors"]
    return {
        "exact_instruction_anchors": sum(map(len, STATIC_PINS.values())),
        "original_function_owners": checks,
    }


def verify_literals(data: bytes) -> dict:
    expected = {FIXED_44100_F64: ("d", 44100.0),
                FIXED_44100_F32: ("f", 44100.0),
                ERROR_SENTINEL_F64: ("d", -2.0)}
    for rva, (typ, numeric) in expected.items():
        size = struct.calcsize("<" + typ)
        found = struct.unpack("<" + typ, stage72.pe_file_bytes(data, rva, size))[0]
        require(found == numeric, f"Original rate/sentinel literal mismatch at {rva:#x}")
    for rva, literal in PUBLIC_NAM_STRINGS.items():
        require(read_bounded_pe_bytes(data, rva, len(literal) + 1) == literal + b"\0",
                f"Original NAM/WAV diagnostic literal mismatch at {rva:#x}")
    return {
        "f64_fixed_hz": 44100,
        "f32_44100_guard_hz": 44100,
        "double_error_sentinel": -2,
        "rdata_nam_wav_diagnostic_literals_verified": len(PUBLIC_NAM_STRINGS),
    }


def read_pe_exports(data: bytes) -> dict[str, tuple[int, int]]:
    """Bounded x64 IMAGE_EXPORT_DIRECTORY name/ordinal/address table walk."""
    require(len(data) >= 0x100 and data[:2] == b"MZ", "Missing MZ export header")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    require(0 <= pe <= len(data) - 24 and data[pe:pe + 4] == b"PE\0\0",
            "Missing PE export signature")
    optional = pe + 24
    require(optional + 120 <= len(data) and
            struct.unpack_from("<H", data, optional)[0] == 0x20B,
            "Expected original PE32+ export directory")
    directory_rva = struct.unpack_from("<I", data, optional + 112)[0]
    require(directory_rva > 0, "No export directory")
    directory = read_bounded_pe_bytes(data, directory_rva, 40)
    (_, _, _, _, _, base, functions, names,
     table, name_table, ordinal_table) = struct.unpack("<IIHHIIIIIII", directory)
    require(0 < functions <= 1024 and 0 < names <= 1024 and names <= functions,
            "Invalid bounded export counts")
    out = {}
    for idx in range(names):
        name_rva = struct.unpack("<I", stage72.pe_file_bytes(
            data, name_table + 4 * idx, 4))[0]
        raw = read_bounded_pe_bytes(data, name_rva, 128)
        nul = raw.find(b"\0")
        require(0 < nul < 128, "Unterminated PE export name")
        name = raw[:nul].decode("ascii")
        ordinal_index = struct.unpack("<H", stage72.pe_file_bytes(
            data, ordinal_table + 2 * idx, 2))[0]
        require(ordinal_index < functions and name not in out,
                "Invalid or duplicate PE export ordinal/name")
        function_rva = struct.unpack("<I", stage72.pe_file_bytes(
            data, table + 4 * ordinal_index, 4))[0]
        out[name] = (base + ordinal_index, function_rva)
    return out


def verify_export(exports: dict[str, tuple[int, int]]) -> dict:
    require(exports.get("getAppNormalWav") == (19, 0xAD5D0),
            "Original getAppNormalWav export RVA/ordinal mismatch")
    return {"original_pe_export": "getAppNormalWav", "ordinal": 19,
            "function_rva": "0xAD5D0"}


def audit(dll: Path, objdump: str | None = None) -> dict:
    data = dll.read_bytes()
    require(hashlib.sha256(data).hexdigest() == DLL_SHA256,
            "Original DLL SHA256 mismatch")
    bounds = stage88.text_section_bounds(data)
    executable, backend = stage72.select_objdump(objdump)
    args = (["--disassemble", "--no-show-raw-insn", "--x86-asm-syntax=intel"]
            if backend == "LLVM" else ["-d", "-M", "intel", "--no-show-raw-insn"])
    command = [executable, *args, "-j", ".text",
               f"--start-address={BASE + bounds[0]:#x}",
               f"--stop-address={BASE + bounds[1]:#x}", str(dll)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    require(result.returncode == 0, "Cannot disassemble original PE .text")
    calls = decoded_calls(result.stdout, *bounds, {WAV_WORKER, NAM_WORKER})
    inventory = verify_inventory(calls, data)

    pe = stage72.previous.PEFunctions(data)
    for entry in ROOT_OWNERS:
        require(pe.owner(entry).start == entry,
                f"Unexpected original .pdata owner {entry:#x}")
    for call_rva, owner in {**CALLS_TO_WAV, **CALLS_TO_NAM}.items():
        require(pe.owner(call_rva).start == owner,
                f"Original call {call_rva:#x} belongs to another function")
    require(pe.owner(RUNTIME_BOUND_INNER_CALL).start == WAV_WORKER,
            "Stage89 source call moved outside WAV worker")
    insns = {}
    for owner in ROOT_OWNERS:
        f = pe.owner(owner)
        insns[owner] = stage72.read_disassembly(dll, executable, backend,
                                                 f.start, f.end)
    pins = verify_pins(insns)
    literals = verify_literals(data)
    exports = verify_export(read_pe_exports(data))
    return {
        "stage": 91, "schema_version": 1,
        "status": STATUS,
        "original_dll_sha256": DLL_SHA256,
        "provenance": "STATIC_ORIGINAL_PE_PLUS_PRIVATE_GHIDRA_STRUCTURAL_CORROBORATION",
        "decoded_upstream_inventory": inventory,
        "original_pdata_and_instruction_pins": pins,
        "original_literal_values": literals,
        "original_export": exports,
        "four_d4a0_direct_callers": {
            "0xE0E0": "NAM output/preprocessing worker, source WAV to target NAM rate",
            "0xFF40": "calls E0E0; then on guarded path passes fixed 44100 Hz to D4A0",
            "0x10E70": "calls E0E0; then on guarded path passes its returned rate to D4A0",
            "0xAD5D0": "exported getAppNormalWav wrapper, forwards caller parameters",
        },
        "additional_two_calls_to_nam_worker": ["0x10043", "0x10F7F"],
        "stage89_d786_inner_edge_observed": True,
        "which_d4a0_upstream_caller_was_active_in_stage89": "UNBOUND",
        "windows_manager_crash_cause": "UNKNOWN",
        "source_nam_identity_in_stage89_trace": "OPERATOR_ATTESTED_ONLY",
        "new_native_capture": False,
        "original_dll_executed": False,
        "native_clo_export_completion_verified": False,
        "not_claimed": [
            "runtime upstream call stack for Stage89",
            "which specific WAV path was opened during the attempted NAM import",
            "which earlier Stage64 parent instance produced its fractional events",
            "successful NAM-to-CLO completion, numerical parity, or Manager crash cause",
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dll", type=Path, required=True)
    p.add_argument("--objdump")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    require(args.out.resolve() != args.dll.resolve(), "Refusing to overwrite original DLL")
    result = audit(args.dll, args.objdump)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(json.dumps({"stage": 91, "status": STATUS,
                      "d4a0_direct_callers": len(CALLS_TO_WAV),
                      "e0e0_direct_callers": len(CALLS_TO_NAM),
                      "stage89_upstream_caller": "UNBOUND"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
