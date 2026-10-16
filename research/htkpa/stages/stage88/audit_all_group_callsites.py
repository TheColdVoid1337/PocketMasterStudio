#!/usr/bin/env python3
"""Stage88: bound all decoded original-DLL direct rel32 callers of 0xCE00.

The discovery is static and intentionally does not infer the historical
Stage64 caller, runtime pointer, branch, or same-run model provenance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage87"))
import audit_fractional_dispatch_chain as stage87

stage72 = stage87.stage72
stage80 = stage87.stage80
stage79 = stage87.stage79
BASE = stage87.BASE
STATUS = "STATIC_SIX_DIRECT_GROUP_CALLSITES_AND_RATE_FAMILIES_VERIFIED_RUNTIME_CALLSITE_UNBOUND"
GROUP_HELPER = 0xCE00
TEXT_START = 0x1000
TEXT_END = 0x18AE58
MAX_TEXT_BYTES = 0x200000
MAX_DISASSEMBLY_CHARS = 24_000_000

CALL_OWNERS = {
    0xD786: 0xD4A0,
    0x112A2: 0x11160,
    0x113C4: 0x11160,
    0xBF364: 0xBE830,
    0xBF47F: 0xBE830,
    0xE28F1: 0xE2640,
}
STAGE87_SAMPLED_CALLS = (0xBF364, 0xE28F1)
ADDITIONAL_CALLS = (0xD786, 0x112A2, 0x113C4, 0xBF47F)
ENUM_SOURCE_CONSTANTS = {
    0x24CCF8: 44100.0,
    0x24CD00: 48000.0,
    0x24CD10: 96000.0,
}

# Every address is original PE RVA and checked against its true .pdata
# function owner. A direct-call search alone is NOT a caller provenance proof.
PINS = {
    0xD4A0: {
        0xD4D2: "movaps xmm6,xmm2",
        0xD704: "test r14,r14",
        0xD707: "je 0x18000d94f",
        0xD760: "mov r9d,dword ptr [r14+0x18]",
        0xD772: "xorps xmm2,xmm2",
        0xD775: "cvtsd2ss xmm2,xmm6",
        0xD779: "movsd xmm1,qword ptr [r14+0x8]",
        0xD77F: "cvtpd2ps xmm1,xmm1",
        0xD783: "mov rcx,rbx",
        0xD786: "call 0x18000ce00",
    },
    0x11160: {
        0x11193: "movaps xmm8,xmm1",
        0x1119A: "movzx ecx,word ptr [rcx+0xa]",
        0x1119E: "test ecx,ecx",
        0x111A0: "je 0x1800111c0",
        0x111A2: "sub ecx,0x1",
        0x111A5: "je 0x1800111b6",
        0x111A7: "cmp ecx,0x1",
        0x111AA: "jne 0x1800111c0",
        0x111AC: "movsd xmm6,qword ptr [rip+0x23bb5c]",
        0x111B6: "movsd xmm6,qword ptr [rip+0x23bb42]",
        0x111C0: "movsd xmm6,qword ptr [rip+0x23bb30]",
        0x1123E: "mov dword ptr [rbx+0x4],esi",
        0x11241: "mov dword ptr [rbx],r15d",
        0x1128F: "cvtsd2ss xmm10,xmm8",
        0x11294: "cvtsd2ss xmm6,xmm6",
        0x11298: "movaps xmm2,xmm10",
        0x1129C: "movaps xmm1,xmm6",
        0x1129F: "mov rcx,rbx",
        0x112A2: "call 0x18000ce00",
        0x1136C: "mov eax,dword ptr [rdi+0x80]",
        0x11382: "cmp dword ptr [rdi+0x84],ebp",
        0x113BA: "movaps xmm2,xmm10",
        0x113BE: "movaps xmm1,xmm6",
        0x113C1: "mov rcx,rbx",
        0x113C4: "call 0x18000ce00",
    },
    0xBE830: {
        0xBE88E: "cmp byte ptr [rcx+0x243d9],0x0",
        0xBE895: "je 0x1800bf55d",
        0xBE89B: "cmp byte ptr [rcx+0x243da],0x0",
        0xBE8A2: "je 0x1800bf55d",
        0xBF317: "cmp dword ptr [rdi+0x7c],ebp",
        0xBF320: "mov rax,qword ptr [r14+0x24408]",
        0xBF34D: "movss xmm6,dword ptr [rip+0x18da9b]",
        0xBF355: "movaps xmm2,xmm6",
        0xBF358: "movss xmm1,dword ptr [r14+0x20ec0]",
        0xBF361: "mov rcx,rbx",
        0xBF364: "call 0x18000ce00",
        0xBF434: "cmp dword ptr [rdi+0x84],ebp",
        0xBF440: "mov rax,qword ptr [r14+0x24410]",
        0xBF470: "movaps xmm2,xmm6",
        0xBF473: "movss xmm1,dword ptr [r14+0x20ec0]",
        0xBF47C: "mov rcx,rbx",
        0xBF47F: "call 0x18000ce00",
    },
    0xE2640: {
        0xE283D: "test r14,r14",
        0xE2840: "je 0x1800e2ac3",
        0xE28C0: "mov r9d,dword ptr [r14+0x18]",
        0xE28DC: "movsd xmm1,qword ptr [r14+0x8]",
        0xE28E2: "cvtpd2ps xmm1,xmm1",
        0xE28E6: "movss xmm2,dword ptr [rip+0x16a502]",
        0xE28EE: "mov rcx,rbx",
        0xE28F1: "call 0x18000ce00",
    },
}


def text_section_bounds(data: bytes) -> tuple[int, int]:
    """Only accept an original, uniquely file-backed PE .text section."""
    if len(data) < 0x100 or data[:2] != b"MZ":
        raise ValueError("Missing original PE header")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("Missing PE signature")
    coff = pe + 4
    count, opt_size = (struct.unpack_from("<H", data, coff + 2)[0],
                       struct.unpack_from("<H", data, coff + 16)[0])
    table = coff + 20 + opt_size
    if not 1 <= count <= 64 or table + count * 40 > len(data):
        raise ValueError("Unbounded original PE section table")
    found = []
    for i in range(count):
        at = table + 40 * i
        if data[at:at + 8].rstrip(b"\0") != b".text":
            continue
        rva = struct.unpack_from("<I", data, at + 12)[0]
        virtual_size = struct.unpack_from("<I", data, at + 8)[0]
        raw_size = struct.unpack_from("<I", data, at + 16)[0]
        file_off = struct.unpack_from("<I", data, at + 20)[0]
        if (not 0 < virtual_size <= raw_size <= MAX_TEXT_BYTES
                or file_off + raw_size > len(data)):
            raise ValueError("Invalid .text backing")
        found.append((rva, rva + virtual_size))
    if found != [(TEXT_START, TEXT_END)]:
        raise ValueError(f"Unexpected .text bounds {found!r}")
    return found[0]


def direct_calls_in_text(raw: str, first: int, last: int) -> list[int]:
    """Enumerate ONLY disassembler-decoded explicit calls, not indirect edges."""
    if len(raw) > MAX_DISASSEMBLY_CHARS:
        raise ValueError("Unbounded native disassembly")
    target = f"call 0x{BASE + GROUP_HELPER:x}"
    result = []
    for line in raw.splitlines():
        m = re.match(r"^\s*([0-9a-fA-F]+):\s+(.+)$", line)
        if not m:
            continue
        va = int(m.group(1), 16)
        if BASE + first <= va < BASE + last and stage72.normalize_asm(m.group(2)) == target:
            result.append(va - BASE)
    if len(set(result)) != len(result):
        raise ValueError("Duplicate direct call instruction")
    return sorted(result)


def scan_original_text(dll: Path, tool: str, backend: str,
                       bounds: tuple[int, int]) -> list[int]:
    if backend == "LLVM":
        flags = ["--disassemble", "--no-show-raw-insn", "--x86-asm-syntax=intel"]
    elif backend == "GNU":
        flags = ["-d", "-M", "intel", "--no-show-raw-insn"]
    else:
        raise ValueError("Unknown disassembler backend")
    start, end = bounds
    cmd = [tool, *flags, "-j", ".text",
           f"--start-address={BASE + start:#x}",
           f"--stop-address={BASE + end:#x}", str(dll)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"Could not decode original DLL .text: {result.stderr[-400:]}")
    return direct_calls_in_text(result.stdout, start, end)


def verify_rel32_bytes(encoded: bytes, caller_rva: int, helper_rva: int = GROUP_HELPER) -> None:
    """Independently check original PE bytes, not just objdump's text."""
    if len(encoded) != 5 or encoded[0] != 0xE8:
        raise ValueError("Direct call is not five-byte E8 rel32")
    disp = struct.unpack_from("<i", encoded, 1)[0]
    if caller_rva + 5 + disp != helper_rva:
        raise ValueError(f"Original rel32 call at {caller_rva:#x} has a different target")


def verify_call_inventory(decoded: list[int], data: bytes) -> dict:
    expected = sorted(CALL_OWNERS)
    if decoded != expected:
        raise ValueError(f"Direct callsite inventory changed: {decoded!r} != {expected!r}")
    for rva in decoded:
        verify_rel32_bytes(stage72.pe_file_bytes(data, rva, 5), rva)
    if set(STAGE87_SAMPLED_CALLS).union(ADDITIONAL_CALLS) != set(decoded):
        raise ValueError("Stage87 versus Stage88 extra callsites not reconciled")
    return {
        "decoded_direct_rel32_callsites": [f"0x{r:x}" for r in decoded],
        "direct_rel32_callsite_count": len(decoded),
        "stage87_previously_pinned_two": [f"0x{r:x}" for r in STAGE87_SAMPLED_CALLS],
        "newly_accounted_four": [f"0x{r:x}" for r in ADDITIONAL_CALLS],
        "raw_original_e8_rel32_encoding_verified_count": len(decoded),
        "not_included": ["indirect virtual/function-pointer calls",
                         "undecoded/obfuscated code and runtime dispatch",
                         "historical Stage64 callsite or return address"],
    }


def verify_rate_constants(data: bytes) -> dict:
    out = {}
    for rva, expected in ENUM_SOURCE_CONSTANTS.items():
        actual = struct.unpack("<d", stage72.pe_file_bytes(data, rva, 8))[0]
        if actual != expected:
            raise ValueError(f"Original f64 rate constant mismatch at {rva:#x}")
        out[f"0x{rva:x}"] = int(actual)
    return out


def verify_callsite_context(insns: dict[int, dict[int, str]]) -> dict:
    checks = {}
    for owner, pins in PINS.items():
        if owner not in insns:
            raise ValueError(f"Missing owner {owner:#x}")
        checks[f"0x{owner:x}"] = stage72.verify_pins(
            {"source_rate_family": pins}, insns[owner])["source_rate_family"]
    return {
        "checked_exact_instruction_pins": sum(map(len, PINS.values())),
        "verified_pin_rvas_by_pdata_owner": checks,
        "four_rate_input_families": {
            "0xd786": {
                "owner": "0xd4a0",
                "source_XMM1": "f64 [r14+0x8] converted to f32",
                "target_XMM2": "incoming f64 XMM2 converted to f32 via preserved XMM6",
                "guard": "nonnull R14 branch",
            },
            "0x112a2_and_0x113c4": {
                "owner": "0x11160",
                "source_XMM1": "three PE-backed f64 literals 44100/48000/96000 selected by word [rcx+0xa], converted to f32 XMM6",
                "target_XMM2": "incoming f64 XMM1 preserved in XMM8 and converted to f32 XMM10",
                "two_segments": "0x7c/0x84 lengths; 0x78/0x80 offsets from RDI",
            },
            "0xbf364_and_0xbf47f": {
                "owner": "0xbe830",
                "source_XMM1": "f32 [r14+0x20ec0]",
                "target_XMM2": "PE-backed f32 44100.0 constant, shared preserved XMM6",
                "two_segments": "context buffers at r14+0x24408 and r14+0x24410",
                "guard": "two nonzero context bytes at +0x243d9 and +0x243da",
            },
            "0xe28f1": {
                "owner": "0xe2640",
                "source_XMM1": "f64 [r14+0x8] narrowed to f32",
                "target_XMM2": "PE-backed f32 44100.0 constant",
                "guard": "nonnull R14 branch",
            },
        },
        "source_enum_0x11160": {
            "word_0": 44100, "word_1": 48000, "word_2": 96000,
            "word_other": 44100,
            "switch": "0x1119a–0x111c0; exact original bytes and literals checked",
        },
        "stage64_reverse_ratio_not_unique_to_any_caller": True,
        "same_run_stage64_specific_caller_determined": False,
    }


def audit(dll: Path, stage64: Path, nams: dict[str, Path],
          clos: dict[str, Path], objdump: str | None = None) -> dict:
    prior = stage87.audit(dll, stage64, nams, clos, objdump)
    if prior["status"] != stage87.STATUS:
        raise ValueError("Stage87 original source gate not accepted")
    if any(prior["claims"].get(k) for k in (
            "historical_stage64_specific_parent_pointer_or_callsite_verified",
            "stage64_same_run_nam_clo_sha_authenticated",
            "actual_stage64_input_48000_verified",
            "original_dll_executed")):
        raise ValueError("Stage87 runtime/provenance limits were silently elevated")

    data = stage80.checked_file(dll, stage79.DLL_SHA256,
                                stage87.stage86.stage85.stage84.stage83.stage82.MAX_DLL_BYTES)
    bounds = text_section_bounds(data)
    exe, backend = stage72.select_objdump(objdump)
    inventory = verify_call_inventory(scan_original_text(dll, exe, backend, bounds), data)
    pe = stage72.previous.PEFunctions(data)
    owner_spans, insns = {}, {}
    for start, pins in PINS.items():
        if pe.owner(start).start != start:
            raise ValueError(f"Unexpected .pdata function owner: {start:#x}")
        ranges = {(pe.owner(rva).start, pe.owner(rva).end) for rva in pins}
        merged = {}
        for begin, end in sorted(ranges):
            merged.update(stage72.read_disassembly(dll, exe, backend, begin, end))
        insns[start] = merged
        owner_spans[f"0x{start:x}"] = [[f"0x{begin:x}", f"0x{end:x}"]
                                     for begin, end in sorted(ranges)]
    for caller, owner in CALL_OWNERS.items():
        if pe.owner(caller).start != owner:
            raise ValueError(f"Direct caller {caller:#x} outside expected function")
    rates = verify_rate_constants(data)
    context = verify_callsite_context(insns)

    return {
        "stage": 88, "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": stage79.DLL_SHA256,
        "stage64_archive_sha256": stage79.STAGE64_SHA256,
        "prior_stage87_status": prior["status"],
        "original_pe_text_bounds": [f"0x{x:x}" for x in bounds],
        "whole_text_direct_call_inventory": inventory,
        "four_original_pdata_calling_functions": owner_spans,
        "original_enum_source_rate_f64_literals": rates,
        "four_family_rate_abi": context,
        "disassembler_backend": backend,
        "operator_attested_stage64_nam_filename":
            "JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam",
        "claims": {
            "all_six_original_disassembler_decoded_explicit_group_calls_verified": True,
            "all_six_original_direct_e8_rel32_encodings_verified": True,
            "three_selectable_literal_source_rates_in_0x11160_verified": True,
            "stage87_two_direct_sites_are_not_exhaustive": True,
            "historical_stage64_exact_caller_or_parent_pointer_verified": False,
            "historical_stage64_enum_selector_verified": False,
            "stage64_same_run_nam_clo_sha_authenticated": False,
            "actual_stage64_input_48000_verified": False,
            "native_vendor_dll_executed": False,
            "new_frida_capture": False,
            "complete_vendor_dsp_or_audio_parity_verified": False,
        },
        "next_gate": "A same-run captured return-address/caller RVA and parent pointer are required to choose among static callers.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dll", "stage64", "nam-2203", "nam-sc20", "clo-2203", "clo-sc20"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--objdump")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    originals = (args.dll, args.stage64, args.nam_2203, args.nam_sc20,
                 args.clo_2203, args.clo_sc20)
    if args.out and args.out.resolve() in (p.resolve() for p in originals):
        raise ValueError("Refusing to overwrite authenticated original")
    result = audit(args.dll, args.stage64,
                   {"2203": args.nam_2203, "SC20": args.nam_sc20},
                   {"2203": args.clo_2203, "SC20": args.clo_sc20}, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": 88, "status": result["status"],
                      "original_direct_calls": result["whole_text_direct_call_inventory"]["direct_rel32_callsite_count"],
                      "rate_families": 4, "historical_stage64_caller": "UNPROVEN"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
