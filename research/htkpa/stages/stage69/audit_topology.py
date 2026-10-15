#!/usr/bin/env python3
"""Stage69: source-first read-only FIR-before-fractional topology audit.

Original pinned PE64 Sonicake 1.5.2 DLL is opened AS DATA only. An external
LLVM objdump disassembles short, bounded spans without executing vendor code.
Stage64's SHA-pinned private archive provides only JSON metadata; captured
f64 payloads are NOT accessed, copied, dumped, or committed.

This verifies the compiled r8b::CDSPResampler24 construction paths:
  * First intermediate FIR block-convolver with up-by-2 ratio.
  * A distinct final fractional-interpolator slot.
  * Sequential virtual calls: FIR first, final fractional second.

It does NOT identify/verify the dynamic parent context for the 96k->44.1k
Stage64 operation. Same dynamic this-pointer across modes could reflect
allocator reuse, reset or object reconfiguration; it is not proof of origin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
from datetime import datetime, timezone

IMAGE_BASE = 0x180000000
DLL_SHA256 = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
STAGE64_SHA256 = "aa32d8440b532708ce3551404f5a4292791abd31aba197003e850f61f22683ff"
EXPECTED_FORWARD_SHA = "c2dd6839637c854b2d971b555f0d3a3b4ecde0c10e687bafbd2b9077bee5eec6"
EXPECTED_REVERSE_SHA = "c3bb59aa369f6022c4c23f31fa180a9cc28af3839c12181c1ff631f5906a5df8"
FRACTIONAL_VFTABLE_RVA = 0x245170

# Verified against the user's exact vendor DLL with LLVM objdump in Intel mode.
# Specify semantic INSTRUCTION patterns rather than hard-coded raw PE bytes.
# No vendor binary or decompiled code is distributed by this script.
ANCHORS: dict[int, str] = {
    0x11BCC: r"movaps xmm9, xmm2\b",                # destination -> xmm9
    0x11BD0: r"movaps xmm8, xmm1\b",                # source -> xmm8
    0x11C1E: r"mov r13d, 0x2\b",                   # first FIR upsample factor
    0x11C62: r"addsd xmm0, xmm9\b",                # 2 * destination
    0x11C67: r"comisd xmm0, xmm8\b",               # compare with source
    0x11C6C: r"jbe 0x180011f24\b",                # source >= 2*dst other branch
    0x11C7A: r"movsd xmm11, qword ptr \[rip \+ 0x23abfd\].*0x18024c880\b",
    0x11C83: r"comisd xmm9, xmm8\b",              # dst <= src
    0x11C90: r"movaps xmm6, xmm9\b",
    0x11C94: r"mulsd xmm6, xmm11\b",              # dst * 0.5
    0x11C99: r"divsd xmm6, xmm8\b",               # /src; lowpass normalized
    0x11CE0: r"movaps xmm0, xmm6\b",              # filter norm-frequency
    0x11CE3: r"call 0x18000bb80\b",               # public-style FIR filter generator
    0x11CEF: r"mov r9d, 0x1\b",                    # first FIR denominator
    0x11CF5: r"mov r8d, r13d\b",                   # first FIR numerator = 2
    0x11CFE: r"call 0x18000bdf0\b",               # convolver init
    0x11D22: r"mov qword ptr \[rbx \+ 0x8\], rbp\b",  # intermediate slot
    0x11D26: r"mov dword ptr \[rbx \+ 0x48\], 0x1\b", # intermediate count 1
    0x11D6E: r"movaps xmm0, xmm8\b",               # 2*source
    0x11D72: r"addsd xmm0, xmm8\b",
    0x11D77: r"comisd xmm0, xmm9\b",               # compare with destination
    0x11D7C: r"ja 0x180011f04\b",                 # src*2 > dst -> fractional path
    0x11F1F: r"jmp 0x180012170\b",                # construct final interpolator
    0x121AE: r"lea rax, \[rip \+ 0x232fbb\].*0x180245170\b",
    0x1222A: r"mov qword ptr \[rbx \+ 0x50\], rsi\b", # final slot
    0x118B1: r"call qword ptr \[rax \+ 0x30\]\b",    # intermediate process
    0x11909: r"call qword ptr \[rax \+ 0x30\]\b",    # final process
    0xE28DC: r"movsd xmm1, qword ptr \[r14 \+ 0x8\]",  # source rate
    0xE28E6: r"movss xmm2, dword ptr \[rip \+ 0x16a502\].*0x18024cdf0\b",
    0xE28F1: r"call 0x18000ce00\b",                # source -> fixed 44100
    0xBF34D: r"movss xmm6, dword ptr \[rip \+ 0x18da9b\].*0x18024cdf0\b",
    0xBF355: r"movaps xmm2, xmm6\b",
    0xBF358: r"movss xmm1, dword ptr \[r14 \+ 0x20ec0\]",
    0xBF364: r"call 0x18000ce00\b",
}
SPANS = (
    (0x11850, 0x11915),
    (0x11B60, 0x11D90),
    (0x11F04, 0x11F25),
    (0x12170, 0x12245),
    (0xBF34D, 0xBF369),
    (0xE28DC, 0xE28F6),
)

def sha_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()

def verify_pinned(path: Path, expected: str, name: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"{name} does not exist")
    digest = sha_file(path)
    if digest != expected:
        raise ValueError(f"{name} SHA mismatch: {digest} != {expected}")

def parse_instruction_lines(lines: str) -> dict[int, str]:
    result: dict[int, str] = {}
    for line in lines.splitlines():
        match = re.match(r"^\s*([0-9a-fA-F]+):\s*(.+)$", line)
        if match:
            va = int(match.group(1), 16)
            instr = re.sub(r"\s+", " ", match.group(2).strip()).lower()
            result[va] = instr
    return result

def validate_anchors(instructions: dict[int, str]) -> list[str]:
    verified = []
    for rva, pattern in ANCHORS.items():
        va = IMAGE_BASE + rva
        actual = instructions.get(va)
        if actual is None or re.search(pattern, actual) is None:
            raise ValueError(f"native source instruction mismatch at RVA {rva:#x}: {actual!r}")
        verified.append(f"0x{rva:x}")
    return verified

def inspect_source(dll: Path, llvm_objdump: str) -> list[str]:
    found: dict[int, str] = {}
    for start, end in SPANS:
        cmd = [llvm_objdump, "--disassemble", "--no-show-raw-insn",
               "--x86-asm-syntax=intel",
               f"--start-address={IMAGE_BASE+start:#x}",
               f"--stop-address={IMAGE_BASE+end:#x}", str(dll)]
        run = subprocess.run(cmd, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(f"LLVM objdump failed for span {start:#x}: {run.stderr[-1600:]}")
        found.update(parse_instruction_lines(run.stdout))
    return validate_anchors(found)

def _json_from_tar(archive: tarfile.TarFile, name: str) -> dict | list:
    member = archive.getmember("frida_capture/" + name)
    if not member.isfile() or member.size > 180_000:
        raise ValueError("Stage64 metadata missing or out of bounds: " + name)
    f = archive.extractfile(member)
    if f is None:
        raise ValueError("Stage64 metadata not extractable: " + name)
    return json.loads(f.read().decode("utf-8"))

def inspect_stage64(archive_path: Path) -> dict:
    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
        if len(names) != len(set(names)):
            raise ValueError("Stage64 archive duplicate member names")
        config = _json_from_tar(archive, "config.json")
        manifest = _json_from_tar(archive, "manifest.json")
        events_member = archive.getmember("frida_capture/events.jsonl")
        if not events_member.isfile() or events_member.size > 300_000:
            raise ValueError("Stage64 event metadata unavailable")
        stream = archive.extractfile(events_member)
        if stream is None:
            raise ValueError("Stage64 events not extractable")
        events = [json.loads(row) for row in stream.read().splitlines() if row]
    # Never read f64 audio payloads here. Earlier stages authenticated those.
    if (config.get("mode") != "guarded_fractional_io" or
            config.get("sha256") != DLL_SHA256 or
            manifest.get("status") != "FRACTIONAL_EXTENDED_OUTPUTS_CLO_STABLE" or
            manifest.get("hook_count") != 1 or
            manifest.get("completion_verified") is not True or
            manifest.get("process_cleanup_status") != "CLOSED_GRACEFULLY"):
        raise ValueError("Stage64 provenance/CLO completion invalid")
    stream_events = [e for e in events if e.get("kind") == "fractional_io"]
    if (len(stream_events) != 21 or
            [e.get("observed") for e in stream_events] != list(range(1, 22)) or
            not all(e.get("valid") is True for e in stream_events)):
        raise ValueError("Stage64 21-event run sequence not authenticated")
    actual_ratios = [(e.get("step_numerator"), e.get("step_denominator"))
                     for e in stream_events]
    if (actual_ratios[:4] != [(88200, 48000)] * 4 or
            actual_ratios[4:] != [(96000, 44100)] * 17):
        raise ValueError("Unexpected Stage64 forward/reverse ratio chronology")
    forward_ptrs = {e.get("processor_pointer") for e in stream_events[:2]}
    alt_ptrs = {e.get("processor_pointer") for e in stream_events[2:]}
    if (len(forward_ptrs) != 1 or len(alt_ptrs) != 1 or
            None in forward_ptrs or None in alt_ptrs or
            forward_ptrs == alt_ptrs):
        raise ValueError("Stage64 object address chronology differs")
    capture_summaries = {
        event["side"]: event for event in events
        if event.get("kind") == "fractional_extended_output"
    }
    if (set(capture_summaries) != {"forward", "reverse"} or
            capture_summaries["forward"].get("observed") != 1 or
            capture_summaries["forward"].get("sha256") != EXPECTED_FORWARD_SHA or
            capture_summaries["forward"].get("copied_f64") != 1067 or
            capture_summaries["reverse"].get("observed") != 18 or
            capture_summaries["reverse"].get("sha256") != EXPECTED_REVERSE_SHA or
            capture_summaries["reverse"].get("copied_f64") != 114):
        raise ValueError("Stage64 native independent f64 capture metadata mismatch")
    return {
        "total_fractional_calls": 21,
        "first_four_calls_rate_steps": "88200->48000",
        "subsequent_seventeen_calls_rate_steps": "96000->44100",
        "first_forward_processor_address_reused_in_calls": [1, 2],
        "second_processor_address_reused_in_calls": list(range(3, 22)),
        "processor_address_changes_between_observed": [2, 3],
        "same_address_appears_under_two_rate_configurations": True,
        "reinit_vs_alloc_reuse": "NOT_DETERMINABLE_FROM_CAPTURE",
        "original_forward_copied_f64": 1067,
        "original_reverse_copied_f64": 114,
        "native_f64_payload_bytes_accessed_by_this_audit": 0,
    }

def audit(dll: Path, stage64: Path, objdump: str) -> dict:
    verify_pinned(dll, DLL_SHA256, "Original Sonicake DLL")
    verify_pinned(stage64, STAGE64_SHA256, "Stage64 source archive")
    anchors = inspect_source(dll, objdump)
    # Resolve high-level output-rate constant in the original PE as data.
    from struct import unpack_from
    image = dll.read_bytes()
    if image[:2] != b"MZ":
        raise ValueError("Not a PE executable")
    pe_offset = unpack_from("<I", image, 0x3C)[0]
    if image[pe_offset:pe_offset+4] != b"PE\x00\x00":
        raise ValueError("Invalid PE header")
    coff = pe_offset + 4
    sections = unpack_from("<H", image, coff + 2)[0]
    optional_size = unpack_from("<H", image, coff + 16)[0]
    section_offset = coff + 20 + optional_size
    rate_constant = None
    for i in range(sections):
        h = section_offset + i*40
        virtual_size, rva, size, offset = unpack_from("<IIII", image, h+8)
        if rva <= 0x24CDF0 < rva + virtual_size:
            raw_offset = offset + (0x24CDF0 - rva)
            if raw_offset + 4 > offset + size:
                raise ValueError("Native rate constant outside PE raw section")
            rate_constant = unpack_from("<f", image, raw_offset)[0]
            break
    if rate_constant != 44100.0:
        raise ValueError("Native output-rate constant at RVA 0x24CDF0 not 44100.0")
    for rva, expected in ((0x24C880, 0.5),):
        found = False
        for i in range(sections):
            h = section_offset + i*40
            virtual_size, section_rva, size, offset = unpack_from("<IIII", image, h+8)
            if section_rva <= rva < section_rva + virtual_size:
                rel = rva - section_rva
                if rel + 8 > size:
                    raise ValueError("FIR normalized-frequency constant outside PE raw section")
                if unpack_from("<d", image, offset+rel)[0] != expected:
                    raise ValueError("Native FIR normalized-frequency constant is not 0.5")
                found = True
                break
        if not found:
            raise ValueError("FIR normalized-frequency constant RVA not mapped")
    history = inspect_stage64(stage64)
    return {
        "stage": 69, "schema_version": 1,
        "status": "SOURCE_FIR_BEFORE_FRACTIONAL_CONFIRMED_DYNAMIC_PARENT_UNPROVEN",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "dll_sha256": DLL_SHA256, "stage64_sha256": STAGE64_SHA256,
        "source": {
            "verified_instruction_rvas": anchors,
            "instruction_count": len(anchors),
            "constructor": "r8brain CDSPResampler24 @ RVA 0x11b60",
            "source_sample_rate_register": "XMM1 copied to XMM8",
            "destination_sample_rate_register": "XMM2 copied to XMM9",
            "first_intermediate_stage": "CDSPBlockConvolver, upsample 2:1 (source anchor 0x11cfe)",
            "conditional_fir_normalized_cutoff": "If dst<=src, xmm6=(0.5*dst/src) @ 0x11c90-0x11c99, passed as xmm0 to native filter generator at 0x11ce3; for hypothetical 48000->44100 this is 0.459375 and corresponds to an input-rate frequency of 22050 Hz",
            "source_filter_half_constant_rva": "0x24c880 (double 0.5 verified from PE data)",
            "direct_to_final_branch": "src*2>dst at 0x11d7c goes to 0x11f04 then 0x11f1f jumps to fractional setup 0x12170",
            "intermediate_object_slot": "resampler +0x8",
            "intermediate_processor_count": "resampler +0x48 = 1",
            "final_stage": "templated CDSPFracInterpolator vtable RVA 0x245170 at 0x121ae",
            "final_object_slot": "resampler +0x50",
            "processing": "intermediate virtual process at 0x118b1, then final process at 0x11909",
            "candidate_callsite_1": "0xe28f1: source rate from audio object [r14+0x8], output rate from native float32 constant RVA 0x24cdf0",
            "candidate_callsite_2": "0xbf364: source rate from context [r14+0x20ec0], output rate from same native float32 constant RVA 0x24cdf0",
            "both_callsites_target_44100": True,
            "specific_stage64_reverse_callsite_verified": False,
        },
        "runtime": history,
        "claims": {
            "upstream_filter_stage_exists_in_native_resampler_constructor": True,
            "specific_stage64_reverse_call_dynamic_parent_verified": False,
            "specific_stage64_reverse_input_spectral_content_measured": False,
            "complete_vendor_96k_to_44100_antialiasing_verified": False,
            "standalone_lab_reverse_matches_this_entire_pipeline": False,
        },
        "next_gate": "Reconstruct 48k->44.1k callsite provenance and dynamic parent/substage chain; no speculative DSP edits or hook.",
    }

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dll", type=Path, required=True)
    ap.add_argument("--stage64", type=Path, required=True)
    ap.add_argument("--objdump", default="llvm-objdump")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    result = audit(args.dll, args.stage64, args.objdump)
    serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized, encoding="utf-8")
    print(serialized)
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError, KeyError,
            tarfile.TarError, json.JSONDecodeError) as exc:
        import sys
        print("[STAGE69 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
