#!/usr/bin/env python3
"""Stage93: static guard compatibility of the two Stage92 WAV entry callsites.

This reads only original PE bytes and the public, sanitized Stage92 evidence.
It does not execute the vendor DLL, infer a shared Frida stack, or claim CLO.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage91"))
import audit_upstream_wav_callers as stage91


BASE = stage91.BASE
STATUS = "STATIC_DUAL_WAV_CALL_COMPATIBILITY_GUARDS_VERIFIED_STAGE92_STACK_UNBOUND"
NESTED_NAM_WORKER = 0xE0E0
WRAPPER = 0x10E70
OBSERVED_OUTER_SITES = (0xEB1E, 0x11021)
EXPECTED_STAGE92_STATUS = "NEW_RUN_TEMPORAL_SEQUENCES_ORIGINAL_PE_AUDIT_VERIFIED"
STAGE92_EVIDENCE = Path(__file__).resolve().parents[1] / "stage92" / "evidence.json"

# All RVAs are original PE addresses. These checks are deliberately exact:
# branch targets, source/target register transfer and the optional flag guard.
PINS = {
    NESTED_NAM_WORKER: {
        0xEA01: "ucomiss xmm9,dword ptr [rip+0x23e3e7]",  # 44100.0 f32
        0xEA09: "jp 0x18000ea7d",
        0xEA0B: "jne 0x18000ea7d",
        0xEA7D: "call 0x1800df710",
        0xEAA0: "lea rdx,[rip+0x235da1]",
        0xEB02: "mov dword ptr [rsp+0x20],0x18",
        0xEB0A: "mov r9d,0x1",
        0xEB10: "movaps xmm2,xmm7",
        0xEB1E: "call 0x18000d4a0",
    },
    WRAPPER: {
        0x10F7F: "call 0x18000e0e0",
        0x10F84: "movd xmm6,eax",
        0x10F88: "cvtdq2pd xmm6,xmm6",
        0x10F8C: "ucomisd xmm6,qword ptr [rip+0x23bf5c]",  # -2.0 f64
        0x10F94: "jp 0x180010ff6",
        0x10F96: "jne 0x180010ff6",
        0x10FF6: "mov ebx,0xffffffff",
        0x10FFB: "test rsi,rsi",
        0x10FFE: "je 0x18001100b",
        0x11000: "movzx eax,byte ptr [rsi]",
        0x11003: "test al,al",
        0x11005: "jne 0x1800110cf",
        0x1100B: "mov dword ptr [rsp+0x20],0x18",
        0x11013: "mov r9d,r14d",
        0x11016: "movaps xmm2,xmm6",
        0x11021: "call 0x18000d4a0",
    },
}


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def verify_stage92_summary(evidence: dict) -> dict:
    """Pin only accepted sanitized observations; never substitute static proof."""
    require(evidence.get("stage") == 92 and
            evidence.get("status") == EXPECTED_STAGE92_STATUS,
            "Stage92 evidence is not the accepted verified checkpoint")
    require(evidence.get("native_hit_count") == 6 and
            evidence.get("native_hook_count") == 2 and
            evidence.get("native_completion_verified") is False,
            "Stage92 bounded capture/completion facts changed")
    require(evidence.get("proves_same_invocation_stack_identity") is False and
            evidence.get("identifies_stage89_outer_caller") is False,
            "Stage92 stack/historical identity has been overstated")
    seq = evidence.get("new_run_same_thread_temporal_sequences")
    require(isinstance(seq, list) and len(seq) == 2,
            "Expected exactly two separately observed Stage92 windows")
    observed = {}
    for item in seq:
        require(isinstance(item, dict), "Invalid Stage92 window")
        outer, inner, gap = item.get("outer_callsite_rva"), item.get("inner_callsite_rva"), item.get("gap_ms")
        require(outer in {"0xEB1E", "0x11021"} and outer not in observed and
                inner == "0xD786" and isinstance(gap, int) and 0 <= gap <= 2000,
                "Stage92 window mapping or bounded chronology changed")
        observed[outer] = gap
    require(observed == {"0xEB1E": 11, "0x11021": 10},
            "Stage92 temporal gaps are not the accepted original observations")
    return {"outer_sites": ["0xEB1E", "0x11021"],
            "inner_site": "0xD786", "temporal_gaps_ms": [11, 10],
            "source": "SANITIZED_STAGE92_NEW_RUN_OBSERVATION"}


def verify_original_guards(insns: dict[int, dict[int, str]]) -> dict:
    checked = {}
    for owner, pins in PINS.items():
        require(owner in insns, f"Missing original owner {owner:#x}")
        checked[f"0x{owner:X}"] = stage91.stage72.verify_pins(
            {"guard_and_dataflow_anchors": pins}, insns[owner]
        )["guard_and_dataflow_anchors"]
    return {"exact_guard_dataflow_anchors": sum(len(p) for p in PINS.values()),
            "original_owner_anchors": checked,
            "conditional_eb1e_branch": "xmm9 != 44100.0f or unordered takes 0xEA7D (compiled branch)",
            "conditional_11021_branches": [
                "E0E0 integer return converted through XMM6",
                "return != -2.0 or unordered takes 0x10FF6, equality skips conversion",
                "optional RSI flag absent or zero can reach 0x1100B; nonzero skips via 0x110CF",
                "second D4A0 target rate comes from XMM6 via XMM2",
            ]}


def audit(dll: Path, evidence: Path = STAGE92_EVIDENCE, objdump: str | None = None) -> dict:
    stage92 = verify_stage92_summary(json.loads(evidence.read_text(encoding="utf-8")))
    # Reuse the complete Stage91 original SHA, seven E8 rel32, .pdata,
    # direct-call inventory, instruction and literal verifier unchanged.
    upstream = stage91.audit(dll, objdump=objdump)
    require(upstream["status"] == stage91.STATUS,
            "Stage91 original-PE upstream gate did not pass")
    data = dll.read_bytes()
    pe = stage91.stage72.previous.PEFunctions(data)
    executable, backend = stage91.stage72.select_objdump(objdump)
    disassembly = {}
    for owner in PINS:
        func = pe.owner(owner)
        require(func.start == owner, "Original .pdata function owner changed")
        disassembly[owner] = stage91.stage72.read_disassembly(
            dll, executable, backend, func.start, func.end
        )
    guards = verify_original_guards(disassembly)
    require(pe.owner(0xEB1E).start == NESTED_NAM_WORKER and
            pe.owner(0x10F7F).start == WRAPPER and
            pe.owner(0x11021).start == WRAPPER,
            "Expected nested/wrapper .pdata ownership changed")
    for call_rva, callee in ((0xEB1E, 0xD4A0),
                             (0x10F7F, NESTED_NAM_WORKER),
                             (0x11021, 0xD4A0)):
        stage91.stage88.verify_rel32_bytes(
            stage91.stage72.pe_file_bytes(data, call_rva, 5), call_rva, callee
        )
    return {
        "stage": 93,
        "status": STATUS,
        "original_dll_sha256": stage91.DLL_SHA256,
        "original_pe_stage91_full_upstream_gate": "PASS",
        "stage92_observations_reused_not_recaptured": stage92,
        "new_original_pe_guard_dataflow_check": guards,
        "same_wrapper_static_scenario": (
            "10E70 calls E0E0 at 10F7F; E0E0 has conditional EB1E -> D4A0; "
            "after E0E0 returns, 10E70 has conditional 11021 -> D4A0"
        ),
        "single_wrapper_invocation_runtime_proven": False,
        "same_thread_temporal_windows_are_complete_stacks": False,
        "retrospective_stage89_upstream_caller_proven": False,
        "clo_completion_verified": False,
        "original_dll_executed": False,
        "new_frida_capture": False,
        "evidence_classes": ["ORIGINAL_PE_STATIC", "STAGE92_SANITIZED_NATIVE_JOURNAL"],
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dll", type=Path, required=True)
    p.add_argument("--stage92-evidence", type=Path, default=STAGE92_EVIDENCE)
    p.add_argument("--objdump")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    require(args.out.resolve() not in {args.dll.resolve(), args.stage92_evidence.resolve()},
            "Refusing to overwrite an original input")
    result = audit(args.dll, args.stage92_evidence, args.objdump)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": 93, "status": STATUS,
                      "guard_anchors": result["new_original_pe_guard_dataflow_check"]["exact_guard_dataflow_anchors"],
                      "static_scenario_compatible": True,
                      "same_invocation_stack_proven": False}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Stage93 audit rejected: {exc}", file=sys.stderr)
        raise SystemExit(2)
