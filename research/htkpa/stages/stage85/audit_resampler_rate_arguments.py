#!/usr/bin/env python3
"""Stage85: SHA-gated static NAM metadata-rate to resampler ABI lineage.

Proves a compiled, conditional numerical-argument route. It never equates
model-object pointers with a historical Stage64 resampler instance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage84"))
import audit_constructor_default_rtti as stage84

stage72 = stage84.stage72
stage80 = stage84.stage80
BASE = stage84.BASE
STATUS = "STATIC_METADATA_RATE_TO_RESAMPLER_CONSTRUCTOR_ABI_VERIFIED_RUNTIME_PARENT_UNPROVEN"

# Every anchor is compared against decoded ORIGINAL vendor instructions, not
# disassembly text saved from elsewhere. The seven owners are .pdata bounded.
PINS = {
    0xE0E0: {
        0xE614: "mov word ptr [rsp+0x50],0x0",
        0xE682: "movzx r8d,word ptr [rsp+0x50]",
        0xE698: "call 0x1800cc4e0",
        0xE6A7: "mov rbx,qword ptr [rax]",
        0xE6CA: "test rbx,rbx",
        0xE6CD: "jne 0x18000e855",
        0xE855: "movsd xmm9,qword ptr [rbx+0x18]",
        0xE85B: "cvtpd2ps xmm9,xmm9",
        0xF620: "cvttss2si ebx,xmm9",
        0xF66B: "mov eax,ebx",
    },
    0x10E70: {
        0x10F7F: "call 0x18000e0e0",
        0x10F84: "movd xmm6,eax",
        0x10F88: "cvtdq2pd xmm6,xmm6",
        0x10F8C: "ucomisd xmm6,qword ptr [rip+0x23bf5c]",
        0x10F94: "jp 0x180010ff6",
        0x10F96: "jne 0x180010ff6",
        0x11086: "cvtpd2ps xmm0,xmm6",
        0x11093: "movss dword ptr [rsp+0x20],xmm0",
        0x110AD: "call 0x180010230",
    },
    0x10230: {
        0x1023D: "lea rbp,[rsp-0x27ab8]",
        0x10287: "movss xmm6,dword ptr [rbp+0x27b20]",
        0x1044D: "call 0x1800c04b0",
        0x10453: "movaps xmm1,xmm6",
        0x10456: "lea rcx,[rbp+0x150]",
        0x1045D: "call 0x1800bfe00",
        0x104DA: "lea rcx,[rbp+0x150]",
        0x104E1: "call 0x1800be830",
    },
    0xBFE00: {
        0xBFE1C: "movaps xmm10,xmm1",
        0xBFE20: "mov ecx,dword ptr [rcx+0x27918]",
        0xBFE28: "jne 0x1800c0242",
        0xBFEF9: "movss dword ptr [rdi+0x20ec0],xmm10",
        0xC03AE: "movss dword ptr [rdi+0x20ec0],xmm10",
    },
    0xBE830: {
        0xBE88B: "mov r14,rcx",
        0xBF34D: "movss xmm6,dword ptr [rip+0x18da9b]",
        0xBF355: "movaps xmm2,xmm6",
        0xBF358: "movss xmm1,dword ptr [r14+0x20ec0]",
        0xBF364: "call 0x18000ce00",
    },
    0xCE00: {
        0xCE34: "movaps xmm8,xmm2",
        0xCE38: "movaps xmm9,xmm1",
        0xCFD0: "xorps xmm2,xmm2",
        0xCFD3: "cvtss2sd xmm2,xmm8",
        0xCFD8: "xorps xmm1,xmm1",
        0xCFDB: "cvtss2sd xmm1,xmm9",
        0xCFF3: "call 0x180011b60",
    },
    0x11B60: {
        0x11B67: "movsd qword ptr [rax+0x18],xmm2",
        0x11BCC: "movaps xmm9,xmm2",
        0x11BD0: "movaps xmm8,xmm1",
    },
}


def stack_argument_entry_offset(push_count: int = 8,
                                rbp_negative: int = 0x27AB8,
                                rbp_positive: int = 0x27B20) -> int:
    """Reconstruct 0x10230's fifth-argument address from entry RSP."""
    if push_count < 0 or push_count > 64:
        raise ValueError("Unexpected prologue push count")
    if rbp_negative < 0 or rbp_positive < 0:
        raise ValueError("Negative displacement")
    result = rbp_positive - rbp_negative - 8 * push_count
    if result != 0x28:
        raise ValueError(f"Stack argument ABI offset changed: {result:#x}")
    return result


def verify_lineage(insns_by_owner: dict[int, dict[int, str]]) -> dict:
    checks = {}
    for start, pins in PINS.items():
        if start not in insns_by_owner:
            raise ValueError(f"Missing owner {start:#x}")
        checks[f"0x{start:x}"] = stage72.verify_pins(
            {"rate_abi": pins}, insns_by_owner[start])["rate_abi"]
    stack_argument_entry_offset()
    return {
        "checked_source_pin_count": sum(map(len, PINS.values())),
        "exact_native_pin_groups": checks,
        "win64_fifth_argument": {
            "caller_store": "0x11093 [rsp+0x20] before call 0x110ad",
            "callee_entry": "0x10230 entry_rsp+0x28 (return address adds 8)",
            "callee_load": "0x10287 [rbp+0x27b20] = entry_rsp+0x28",
            "verified_entry_rsp_offset": "0x28",
        },
        "source_rate_to_constructor": [
            "0xe855: metadata-backed constructed object's f64 +0x18, conditional",
            "0xf620/0xf66b: converted f32 to integer return EAX",
            "0x10f84/0x10f88: EAX converted back to f64 XMM6",
            "0x11086/0x11093: f32 fifth stack argument to 0x10230",
            "0x10287/0x10453: callee XMM6 forwarded as XMM1",
            "0xbfe1c/0xbfef9 or 0xc03ae: context f32 +0x20ec0",
            "0xbf358/0xbf364: context field as XMM1 into 0xce00",
            "0xce38/0xcfdb: XMM1 retained, widened to f64",
            "0xcff3/0x11bd0: CDSPResampler24 constructor input rate XMM1",
        ],
        "target_rate_to_constructor": [
            "0xbf34d/0xbf355: 44100.0f from verified Stage72 PE constant to XMM2",
            "0xce34/0xcfd3: XMM2 retained, widened to f64",
            "0xcff3/0x11bcc: CDSPResampler24 constructor output rate XMM2",
        ],
        "conditional_boundaries": [
            "0xe6cd: nonnull metadata/factory object, no live class identity",
            "0xe9b8/0xe9bc: Stage74 48000 Hz fallback may replace metadata rate",
            "0x10f94/0x10f96: -2.0 sentinel bypasses success branch",
            "0x1048e/0x104c4: initializer guards before 0x104e1",
            "0xbfe28: context flag branches to alternate +0x20ec0 writer",
            "0xcf27/0xcfce: size and allocation guards before constructor",
        ],
    }


def audit(dll: Path, stage64: Path, nams: dict[str, Path],
          clos: dict[str, Path], objdump: str | None = None) -> dict:
    prior = stage84.audit(dll, stage64, nams, clos, objdump)
    if prior["status"] != stage84.STATUS:
        raise ValueError("Stage84 original-source gate not accepted")
    if any(prior["claims"].get(label) for label in (
            "historical_stage64_active_child_verified",
            "historical_stage64_resampler_parent_verified",
            "same_run_nam_clo_sha_verified")):
        raise ValueError("Historical Stage64 provenance gate was silently elevated")

    data = stage80.checked_file(dll, stage80.stage79.DLL_SHA256,
                                stage84.stage83.stage82.MAX_DLL_BYTES)
    pe = stage72.previous.PEFunctions(data)
    exe, backend = stage72.select_objdump(objdump)
    owners = {}
    insns = {}
    for start, pins in PINS.items():
        function = pe.owner(start)
        if function.start != start:
            raise ValueError(f"Expected unique .pdata owner {start:#x}")
        # MSVC splits large functions into multiple adjacent unwind entries:
        # e.g. 0xbfe00..0xbfe36, 0xbfe36..0xc0242, 0xc0242..0xc044a.
        # Every original instruction is mapped to its own .pdata range.
        intervals = {(pe.owner(rva).start, pe.owner(rva).end)
                     for rva in pins}
        owners[f"0x{start:x}"] = [[f"0x{begin:x}", f"0x{end:x}"]
                                   for begin, end in sorted(intervals)]
        merged = {}
        for begin, end in sorted(intervals):
            merged.update(stage72.read_disassembly(dll, exe, backend, begin, end))
        insns[start] = merged
    lineage = verify_lineage(insns)
    return {
        "stage": 85, "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": stage80.stage79.DLL_SHA256,
        "stage64_archive_sha256": stage80.stage79.STAGE64_SHA256,
        "prior_stage84_gate": prior["status"],
        "disassembler_backend": backend,
        "pe_function_owners": owners,
        "numeric_argument_lineage": lineage,
        "operator_attested_stage64_nam_filename":
            "JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam",
        "claims": {
            "static_metadata_input_rate_argument_to_resampler_constructor_verified": True,
            "static_output_rate_44100_argument_to_resampler_constructor_verified": True,
            "exact_win64_fifth_argument_mapping_verified": True,
            "historical_stage64_model_pointer_resampler_parent_bound": False,
            "historical_stage64_selected_child_or_selector_control_known": False,
            "stage64_reverse_96000_source_rate_value_authenticated": False,
            "stage64_same_run_nam_clo_sha_authenticated": False,
            "original_dll_executed": False,
            "new_frida_capture": False,
            "complete_vendor_dsp_or_audio_parity_verified": False,
        },
        "next_gate": "Identify a captured Stage64 native object/caller identity before equating this conditional static numerical route with its specific reverse resampler parent.",
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
    print(json.dumps({"stage": 85, "status": result["status"],
                      "new_original_native_instruction_pins":
                          result["numeric_argument_lineage"]["checked_source_pin_count"],
                      "runtime_parent": "UNPROVEN"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
