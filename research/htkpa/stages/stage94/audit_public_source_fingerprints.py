#!/usr/bin/env python3
"""Stage94: SHA-gated, static-only public-source fingerprints in original PE64.

No execution, disassembly engine, private capture, or runtime inference.
The RIP-relative checks validate specified compiled instructions only; they do
not claim an exhaustive cross-reference analysis or any executed path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


STAGE = 94
ORIGINAL_SHA256 = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
ORIGINAL_SIZE = 2_902_016

# For this exact original DLL: byte-level source-family signals, not version IDs.
# Values are (ASCII byte string, expected RVA). Source strings are from
# sdatkinson/NeuralAmpModelerCore NAM/get_dsp.cpp, except tagged vendor/RTTI.
FINGERPRINTS = {
    "nam_missing_weights": (b"Corrupted model file is missing weights.", 0x18F7F8),
    "nam_negative_version": (b"Negative version component: ", 0x18F708),
    "nam_out_of_range": (b"Version string out of range: ", 0x18F728),
    "nam_invalid_version": (b"Invalid version string: ", 0x18F748),
    "nam_unsupported_version": (b"Model config is an unsupported version ", 0x18F7A0),
    "nam_checker_null": (b"version support checker cannot be null", 0x18F7C8),
    "nam_partially_supported": (b"Model config is a partially-supported version ", 0x18F840),
    "r8brain_cdsp_rtti": (b".?AVCDSPResampler24@r8b@@", 0x2A0E50),
    "nam_fast_tanh_rtti": (b".?AVActivationFastTanh@activations@nam@@", 0x2A1A28),
    "juce_wav_reader_rtti": (b".?AVWavAudioFormatReader@juce@@", 0x2A5268),
    "vendor_get_nam_output_log": (b"[NAM] ========== getNamOutput start ==========", 0x2446D8),
    "vendor_nam_head_warning": (b"Warning: model has a 'head' config", 0x18CFE0),
}

# Address of actual 7-byte `lea rdx, [rip + disp32]`, and expected target.
# One string can have multiple compiled references / paths.
COMPILED_REFERENCES = {
    "nam_missing_weights": (0xCB681, 0xCB863),
    "vendor_get_nam_output_log": (0xE2A0,),
    "vendor_nam_head_warning": (0xAF353,),
}


class AuditError(ValueError):
    """Static audit failed closed."""


def u16(data: bytes, at: int) -> int:
    return struct.unpack_from("<H", data, at)[0]


def u32(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def pe64_sections(data: bytes) -> list[dict]:
    if len(data) < 0x200 or data[:2] != b"MZ":
        raise AuditError("not an MZ executable")
    pe = u32(data, 0x3C)
    if pe + 24 > len(data) or data[pe:pe + 4] != b"PE\0\0":
        raise AuditError("missing PE signature")
    if u16(data, pe + 4) != 0x8664:
        raise AuditError("expected AMD64 PE")
    num_sections = u16(data, pe + 6)
    optional_size = u16(data, pe + 20)
    optional_at = pe + 24
    if optional_at + optional_size > len(data) or u16(data, optional_at) != 0x20B:
        raise AuditError("expected PE32+ optional header")
    table = optional_at + optional_size
    if not (1 <= num_sections <= 32) or table + 40 * num_sections > len(data):
        raise AuditError("invalid section table")
    sections = []
    for index in range(num_sections):
        at = table + 40 * index
        name = data[at:at + 8].split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, rva, raw_size, raw_offset = struct.unpack_from("<IIII", data, at + 8)
        if raw_size and (raw_offset > len(data) or raw_size > len(data) - raw_offset):
            raise AuditError(f"section {name}: raw bounds outside file")
        sections.append({"name": name, "rva": rva, "virtual_size": virtual_size,
                         "raw_size": raw_size, "raw_offset": raw_offset})
    return sections


def raw_to_rva(sections: list[dict], raw: int) -> int:
    for section in sections:
        if section["raw_offset"] <= raw < section["raw_offset"] + section["raw_size"]:
            return section["rva"] + raw - section["raw_offset"]
    raise AuditError(f"file offset {raw:#x} not covered by a PE section")


def rva_to_raw(sections: list[dict], rva: int) -> int:
    for section in sections:
        if section["rva"] <= rva < section["rva"] + section["raw_size"]:
            return section["raw_offset"] + rva - section["rva"]
    raise AuditError(f"RVA {rva:#x} not covered by raw section data")


def rip_lea_rdx_target(data: bytes, sections: list[dict], site_rva: int) -> int:
    """Verify a particular instruction encoding, not arbitrary x64 decoding."""
    at = rva_to_raw(sections, site_rva)
    if data[at:at + 3] != b"\x48\x8d\x15":
        raise AuditError(f"RVA {site_rva:#x} is not expected LEA RDX, RIP+disp32")
    disp = struct.unpack_from("<i", data, at + 3)[0]
    return (site_rva + 7 + disp) & 0xFFFFFFFF


def audit(data: bytes) -> dict:
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != ORIGINAL_SIZE or digest != ORIGINAL_SHA256:
        raise AuditError("SHA256/size mismatch: this is not the pinned original DLL")
    sections = pe64_sections(data)
    all_hits = {}
    for label, (literal, expected_rva) in FINGERPRINTS.items():
        raw_hits = []
        start = 0
        while True:
            at = data.find(literal, start)
            if at == -1:
                break
            raw_hits.append(at)
            start = at + 1
        if len(raw_hits) != 1:
            raise AuditError(f"{label}: expected one exact occurrence, found {len(raw_hits)}")
        actual_rva = raw_to_rva(sections, raw_hits[0])
        if actual_rva != expected_rva:
            raise AuditError(f"{label}: expected {expected_rva:#x}, found {actual_rva:#x}")
        all_hits[label] = {"rva": f"0x{actual_rva:X}", "occurrences": 1}

    refs = {}
    for label, sites in COMPILED_REFERENCES.items():
        expected_rva = FINGERPRINTS[label][1]
        refs[label] = []
        for site in sites:
            actual_target = rip_lea_rdx_target(data, sections, site)
            if actual_target != expected_rva:
                raise AuditError(f"{label} at {site:#x}: target {actual_target:#x} != {expected_rva:#x}")
            refs[label].append({"lea_rva": f"0x{site:X}", "target_rva": f"0x{actual_target:X}"})

    return {
        "stage": STAGE,
        "status": "ORIGINAL_PE_PUBLIC_NAM_FINGERPRINTS_AND_SELECTED_XREFS_VERIFIED_STATIC_ONLY",
        "dll_sha256": digest,
        "dll_size": len(data),
        "source_fingerprints": all_hits,
        "selected_compiled_lea_references": refs,
        "fingerprint_count": len(all_hits),
        "reference_count": sum(map(len, refs.values())),
        "evidence_limits": [
            "original PE static bytes and selected compiled references only",
            "matching diagnostics and RTTI imply source-family overlap, not exact source revision",
            "a selected LEA target is not an observed runtime call or exhaustive xref set",
            "no new Frida trace, call-stack binding, execution, or completed CLO",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True, help="pinned original Windows 5868USB.dll")
    parser.add_argument("--out", type=Path, required=True, help="Git-ignored private JSON output")
    args = parser.parse_args()
    report = audit(args.dll.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("stage", "status", "dll_sha256", "fingerprint_count", "reference_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
