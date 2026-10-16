#!/usr/bin/env python3
"""Stage86: original-DLL fractional-child vtable ↔ Stage64 guard binding.

This proves a compiled parent/child *type* relationship, not the parent
pointer or constructor caller of a particular historical captured object.
Only the three bounded Stage64 metadata members are read from the archive.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage85"))
import audit_resampler_rate_arguments as stage85

stage72 = stage85.stage72
stage80 = stage85.stage80
stage79 = stage80.stage79
stage77 = stage85.stage84.stage77
BASE = stage85.BASE
STATUS = "STAGE64_FRACTIONAL_VTABLE_AND_STATIC_RESAMPLER_CHILD_OWNER_VERIFIED_RUNTIME_PARENT_UNPROVEN"

FRACTIONAL_VTABLE_RVA = 0x245170
FRACTIONAL_HOOK_RVA = 0x135C0
FRACTIONAL_HOOK_SLOT = 0x30
RATE_NUMERATOR_OFFSET = 0x1008
RATE_DENOMINATOR_OFFSET = 0x1010
CHILD_OWNER_OFFSET = 0x50
VTABLE_TARGETS = (0x14320, 0x11AC0, 0x11B50, 0x13DC0,
                  0x13D90, 0x13D30, FRACTIONAL_HOOK_RVA)

# Exact instruction operands, disassembled afresh from the SHA-pinned original.
# Compare site 0x11a4c is a consumer; 0x121b5 is an observed direct writer.
PINS = {
    0x11A4C: {
        0x11A4C: "mov rax,qword ptr [rbx]",
        0x11A4F: "lea rcx,[rip+0x23371a]",
        0x11A56: "cmp rax,rcx",
        0x11A59: "jne 0x180011ab2",
    },
    0x11B60: {
        0x11BCC: "movaps xmm9,xmm2",
        0x11BD0: "movaps xmm8,xmm1",
        0x12147: "lea r8,[rip+0x232d52]",
        0x1214E: "cmp rax,r8",
        0x12151: "jne 0x1800122b7",
        0x1216A: "ja 0x180012267",
        0x12170: "mov ecx,0x1048",
        0x12175: "call qword ptr [rip+0x1797c5]",
        0x1217B: "mov rsi,rax",
        0x12186: "test rax,rax",
        0x12189: "je 0x180012210",
        0x1218F: "movd xmm1,dword ptr [rsp+0x168]",
        0x12198: "cvtdq2pd xmm1,xmm1",
        0x1219C: "mulsd xmm1,xmm8",
        0x121A1: "movd xmm0,r14d",
        0x121A6: "cvtdq2pd xmm0,xmm0",
        0x121AA: "divsd xmm1,xmm0",
        0x121AE: "lea rax,[rip+0x232fbb]",
        0x121B5: "mov qword ptr [rsi],rax",
        0x121B8: "movsd qword ptr [rsi+0x1008],xmm1",
        0x121C0: "movsd qword ptr [rsi+0x1010],xmm9",
        0x121C9: "movsd qword ptr [rsi+0x1018],xmm7",
        0x12210: "mov rsi,rdi",
        0x12213: "mov rcx,qword ptr [rbx+0x50]",
        0x12217: "mov qword ptr [rbx+0x50],rdi",
        0x1221B: "test rcx,rcx",
        0x1221E: "je 0x18001222a",
        0x12220: "mov rax,qword ptr [rcx]",
        0x12223: "mov edx,0x1",
        0x12228: "call qword ptr [rax]",
        0x1222A: "mov qword ptr [rbx+0x50],rsi",
        0x1222E: "mov rax,qword ptr [rsi]",
        0x12231: "mov edx,r13d",
        0x12234: "mov rcx,rsi",
        0x12237: "call qword ptr [rax+0x20]",
    },
    0x135C0: {
        0x135C0: "mov rax,rsp",
        0x135C3: "push r12",
        0x135C5: "push r13",
        0x135C7: "sub rsp,0x38",
        0x135CB: "mov r12,qword ptr [r9]",
        0x135CE: "mov r13,r9",
    },
}


def verify_vtable(data: bytes) -> dict:
    """All seven qword slots must be uniquely section-backed original bytes."""
    entries = {}
    for i, target in enumerate(VTABLE_TARGETS):
        slot = FRACTIONAL_VTABLE_RVA + i * 8
        entries[f"+0x{i * 8:x}"] = stage77.read_pointer(data, slot, target)
    if VTABLE_TARGETS[FRACTIONAL_HOOK_SLOT // 8] != FRACTIONAL_HOOK_RVA:
        raise ValueError("Hook slot and static method target diverged")
    return {"vtable_rva": f"0x{FRACTIONAL_VTABLE_RVA:x}",
            "seven_original_file_backed_qword_slots": entries,
            "guarded_hook_slot": f"+0x{FRACTIONAL_HOOK_SLOT:x}",
            "hook_target_rva": f"0x{FRACTIONAL_HOOK_RVA:x}"}


def verify_constructor(insns_by_owner: dict[int, dict[int, str]]) -> dict:
    verified = {}
    for start, pins in PINS.items():
        if start not in insns_by_owner:
            raise ValueError(f"Missing source function owner {start:#x}")
        verified[f"0x{start:x}"] = stage72.verify_pins(
            {"fractional_child": pins}, insns_by_owner[start])["fractional_child"]
    return {
        "new_exact_instruction_pin_count": sum(map(len, PINS.values())),
        "checked_original_instruction_rvas_by_owner": verified,
        "fractional_child_allocation_size_bytes": 0x1048,
        "fractional_child_vtable_install_rva": "0x121b5",
        "fractional_child_rate_fields": {
            "numerator_derived_from_constructor_input_xmm8": f"+0x{RATE_NUMERATOR_OFFSET:x}",
            "denominator_from_constructor_output_xmm9": f"+0x{RATE_DENOMINATOR_OFFSET:x}"},
        "resampler_parent_child_pointer_offset": f"+0x{CHILD_OWNER_OFFSET:x}",
        "prior_child_release_and_new_child_install_are_conditional": True,
        "other_constructor_branches_exist": True,
    }


def verify_capture_config(config: dict, manifest: dict, events: list[dict]) -> dict:
    """Compare existing authenticated Stage64 JSON with the static PE type."""
    if not isinstance(config, dict) or not isinstance(manifest, dict):
        raise ValueError("Stage64 config/manifest invalid")
    sites = config.get("sites")
    if not isinstance(sites, list) or len(sites) != 1 or not isinstance(sites[0], dict):
        raise ValueError("Stage64 guarded hook site missing/ambiguous")
    site = sites[0]
    guard = site.get("guard")
    rates = config.get("rate_probe")
    if (config.get("mode") != "guarded_fractional_io" or
            config.get("sha256") != stage79.DLL_SHA256 or
            site.get("name") != "fractional_entry_io" or
            site.get("rva") != FRACTIONAL_HOOK_RVA or
            not isinstance(guard, dict) or
            guard.get("kind") != "fractional_entry_io" or
            guard.get("vtable_rva") != FRACTIONAL_VTABLE_RVA or
            not isinstance(rates, dict) or
            rates.get("numerator_offset") != RATE_NUMERATOR_OFFSET or
            rates.get("denominator_offset") != RATE_DENOMINATOR_OFFSET):
        raise ValueError("Stage64 fractional guard/hook/ratio fields mismatch original DLL")
    hook_events = [e for e in events if e.get("kind") == "hook_attached"]
    calls = [e for e in events if e.get("kind") == "fractional_io"]
    if (len(hook_events) != 1 or hook_events[0].get("rva") != FRACTIONAL_HOOK_RVA or
            hook_events[0].get("site") != "fractional_entry_io" or
            len(calls) != 21 or [e.get("observed") for e in calls] != list(range(1, 22)) or
            [(e.get("step_numerator"), e.get("step_denominator")) for e in calls] !=
            [(88200, 48000)] * 4 + [(96000, 44100)] * 17 or
            not all(e.get("valid") is True for e in calls)):
        raise ValueError("Stage64 hook events or original 21-call chronology mismatch")
    state = manifest.get("state")
    if (manifest.get("hook_count") != 1 or not isinstance(state, dict) or
            state.get("valid_field_hits") != 21):
        raise ValueError("Stage64 manifest guarded-hit evidence changed")
    # These keys are absent from the 21 observed processor events: do not
    # infer a historical resampler parent/caller, even though its static type
    # is now associated with the original constructor's child layout.
    runtime_parent_keys = {"parent_pointer", "parent_processor_pointer", "owner_pointer",
                           "caller_rva", "return_address", "callstack", "call_stack"}
    recorded = sorted(set().union(*(runtime_parent_keys.intersection(e)
                                    for e in calls)))
    if recorded:
        raise ValueError("Unexpected historical parent evidence requires independent review")
    return {
        "original_hook_rva": f"0x{FRACTIONAL_HOOK_RVA:x}",
        "stage64_guard_vtable_rva": f"0x{FRACTIONAL_VTABLE_RVA:x}",
        "stage64_rate_offsets": [f"0x{RATE_NUMERATOR_OFFSET:x}",
                                 f"0x{RATE_DENOMINATOR_OFFSET:x}"],
        "valid_fractional_io_calls": len(calls),
        "forward_ratio_observations": 4,
        "reverse_ratio_observations": 17,
        "captured_runtime_parent_or_caller_metadata_keys": recorded,
        "historical_parent_instance_from_capture_verified": False,
        "same_run_nam_sha_in_capture_verified": False,
        "capture_audio_or_model_weights_read": False,
    }


def inspect_capture(stage64: Path) -> dict:
    stage79.verify_stage64_sha(stage64)
    prior_metadata = stage79.inspect_stage64_metadata(stage64)
    if not prior_metadata["accepted_capture_metadata_gates"]:
        raise ValueError("Stage79 capture metadata authenticity changed")
    with tarfile.open(stage64, "r:gz") as tar:
        config = stage79.metadata_member(tar, "config.json", stage79.MAX_METADATA_SIZE)
        manifest = stage79.metadata_member(tar, "manifest.json", stage79.MAX_METADATA_SIZE)
        member = tar.getmember("frida_capture/events.jsonl")
        if not member.isfile() or not 0 < member.size <= stage79.MAX_EVENTS_SIZE:
            raise ValueError("Oversized/nonregular Stage64 events JSONL")
        opened = tar.extractfile(member)
        if opened is None:
            raise ValueError("Cannot read bounded Stage64 JSONL")
        with opened:
            raw = opened.read(stage79.MAX_EVENTS_SIZE + 1)
        if len(raw) != member.size:
            raise ValueError("Truncated/oversized Stage64 JSONL")
        events = stage79.safe_event_list(raw)
    return {"three_metadata_members_only": prior_metadata["inspected_archive_entries"],
            **verify_capture_config(config, manifest, events)}


def audit(dll: Path, stage64: Path, nams: dict[str, Path],
          clos: dict[str, Path], objdump: str | None = None) -> dict:
    previous = stage85.audit(dll, stage64, nams, clos, objdump)
    if previous["status"] != stage85.STATUS:
        raise ValueError("Stage85 original-source gate not accepted")
    if (previous["claims"].get("historical_stage64_model_pointer_resampler_parent_bound") or
            previous["claims"].get("stage64_same_run_nam_clo_sha_authenticated") or
            previous["claims"].get("original_dll_executed")):
        raise ValueError("Stage85 historical-runtime claim elevated without evidence")
    data = stage80.checked_file(dll, stage79.DLL_SHA256,
                                stage85.stage84.stage83.stage82.MAX_DLL_BYTES)
    vtable = verify_vtable(data)
    capture = inspect_capture(stage64)
    pe = stage72.previous.PEFunctions(data)
    exe, backend = stage72.select_objdump(objdump)
    owners, insns = {}, {}
    for start, pins in PINS.items():
        if pe.owner(start).start != start:
            raise ValueError(f"Expected .pdata source owner {start:#x}")
        intervals = {(pe.owner(rva).start, pe.owner(rva).end) for rva in pins}
        owners[f"0x{start:x}"] = [[f"0x{b:x}", f"0x{e:x}"]
                                    for b, e in sorted(intervals)]
        merged = {}
        for begin, end in sorted(intervals):
            merged.update(stage72.read_disassembly(dll, exe, backend, begin, end))
        insns[start] = merged
    construction = verify_constructor(insns)
    return {
        "stage": 86, "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": stage79.DLL_SHA256,
        "stage64_archive_sha256": stage79.STAGE64_SHA256,
        "prior_stage85_gate": previous["status"],
        "original_pe_vtable": vtable,
        "stage64_metadata_guard_cross_check": capture,
        "original_constructor_parent_child_topology": construction,
        "pe_function_owners": owners,
        "disassembler_backend": backend,
        "operator_attested_stage64_nam_filename":
            "JCM800 2203_4x12 Marshall_CRUNCH_SM57.nam",
        "claims": {
            "stage64_hook_matches_original_fractional_vtable_slot": True,
            "stage64_guarded_fractional_type_matches_constructor_created_child": True,
            "original_resampler_parent_child_field_offset_verified": True,
            "stage64_ratio_probe_fields_match_constructor_child_fields": True,
            "historical_stage64_specific_parent_pointer_or_caller_verified": False,
            "historical_stage64_constructor_branch_execution_verified": False,
            "historical_stage64_nam_container_pointer_parent_bound": False,
            "stage64_same_run_nam_clo_sha_authenticated": False,
            "original_dll_executed": False,
            "new_frida_capture": False,
            "complete_vendor_dsp_or_audio_parity_verified": False,
        },
        "next_gate": "Acquire bounded same-run native parent pointer/constructor caller evidence for the Stage64 fractional processor; the existing metadata proves type, not instance ancestry.",
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
    print(json.dumps({"stage": 86, "status": result["status"],
                      "new_exact_native_instruction_pins": result[
                          "original_constructor_parent_child_topology"]["new_exact_instruction_pin_count"],
                      "historical_parent_instance": "UNPROVEN"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
