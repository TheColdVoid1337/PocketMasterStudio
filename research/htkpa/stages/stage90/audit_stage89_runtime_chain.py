#!/usr/bin/env python3
"""Stage90: offline, read-only validation of the bounded Stage89 Frida trace.

Inputs are PRIVATE. Output is deliberately sanitized: no original heap
addresses, binary bytes, decompilation, or full event journal are emitted.
The capture cannot establish successful CLO output or a Windows crash cause.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage88"))
import audit_all_group_callsites as stage88


EXPECTED_DLL_SHA256 = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
EXPECTED_SITES = {
    "group_ce00_entry": (0xCE00, 1),
    "group_parent_install": (0xD018, 1),
    "parent_child_dispatch": (0x118FD, 2),
    "fractional_child_entry": (0x135C0, 2),
}
EXPECTED_CALLSITE = 0xD786
EXPECTED_CALLER_OWNER = 0xD4A0
STATUS = "NATIVE_STAGE89_D786_CALLSITE_AND_SAME_RUN_PARENT_CHILD_CHAIN_VERIFIED"
CAPTURE_MEMBERS = ("frida_capture/manifest.json", "frida_capture/events.jsonl")
MAX_JSON_BYTES = 2_000_000


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def hex_pointer(value: object, description: str) -> int:
    require(isinstance(value, str) and value.startswith("0x"),
            f"Invalid {description}: not hex")
    try:
        number = int(value, 16)
    except ValueError as exc:
        raise ValueError(f"Invalid {description}: malformed hex") from exc
    require(0 < number < 2**64, f"Invalid {description}: zero or out of range")
    return number


def field_pointer(event: dict, field: str) -> int:
    obj = event.get("fields", {}).get(field, {})
    return hex_pointer(obj.get("value"), field)


def bounded_json_member(archive: tarfile.TarFile, name: str) -> str:
    matches = [m for m in archive.getmembers() if m.name == name]
    require(len(matches) == 1 and matches[0].isfile(), f"Missing/duplicate {name}")
    require(0 < matches[0].size <= MAX_JSON_BYTES, f"Unbounded {name}")
    stream = archive.extractfile(matches[0])
    require(stream is not None, f"Unreadable {name}")
    return stream.read().decode("utf-8-sig")


def load_capture(path: Path) -> tuple[dict, list[dict], str]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with tarfile.open(path, mode="r:gz") as archive:
        manifest = json.loads(bounded_json_member(archive, CAPTURE_MEMBERS[0]))
        journal = bounded_json_member(archive, CAPTURE_MEMBERS[1])
        events = [json.loads(line) for line in journal.splitlines() if line.strip()]
    require(isinstance(manifest, dict) and isinstance(events, list), "Invalid trace schema")
    require(0 < len(events) <= 1000, "Unexpected event journal size")
    require(all(isinstance(e, dict) for e in events), "Invalid event record")
    return manifest, events, digest


def verify_native_callsite(dll_bytes: bytes, rva: int) -> int:
    require(hashlib.sha256(dll_bytes).hexdigest() == EXPECTED_DLL_SHA256,
            "Original DLL SHA256 mismatch")
    require(rva in stage88.CALL_OWNERS, "Return address is not a Stage88 direct caller")
    encoded = stage88.stage72.pe_file_bytes(dll_bytes, rva, 5)
    stage88.verify_rel32_bytes(encoded, rva)
    return stage88.CALL_OWNERS[rva]


def audit(manifest: dict, events: list[dict], dll_bytes: bytes,
          archive_sha256: str) -> dict:
    """Cross-check original E8 rel32, ASLR, chronology, thread and pointer joins."""
    require(manifest.get("status") == "OPERATOR_INTERRUPTED", "Unexpected run final status")
    require(manifest.get("completion_verified") is False,
            "Stage89 must not be described as a completed CLO export")
    require(manifest.get("expected_sha256") == EXPECTED_DLL_SHA256,
            "Manifest original DLL pin mismatch")
    require(manifest.get("hook_count") == 4, "Manifest hook count mismatch")

    loads = [e for e in events if e.get("kind") == "module_loaded"]
    require(len(loads) == 1, "Expected one verified module-load event")
    module = loads[0]
    require(str(module.get("path", "")).lower().endswith("5868usb.dll"),
            "Unexpected runtime module path")
    require(module.get("runtime_sha256") == EXPECTED_DLL_SHA256,
            "Runtime module SHA256 mismatch")
    base = hex_pointer(module.get("base"), "ASLR module base")

    hooks = [e for e in events if e.get("kind") == "hook_attached"]
    require(len(hooks) == len(EXPECTED_SITES), "Four hooks were not attached")
    require({e.get("site"): e.get("rva") for e in hooks} ==
            {name: rva for name, (rva, _) in EXPECTED_SITES.items()},
            "Wrong hook site RVA mapping")
    ready = [e for e in events if e.get("kind") == "ready"]
    require(len(ready) == 1 and ready[0].get("installed") == 4
            and ready[0].get("requested") == 4, "No complete ready state")
    require(manifest.get("state", {}).get("runtime_verified") is True
            and manifest["state"].get("ready") is True, "Manifest readiness mismatch")
    require(manifest["state"].get("hook_errors") == 0,
            "Unexpected Frida hook exception count")

    hits = [e for e in events if e.get("kind") == "hit"]
    require(len(hits) == 6 and manifest["state"].get("hits") == 6,
            "Unexpected native hit count")
    actual = {name: [e for e in hits if e.get("site") == name]
              for name in EXPECTED_SITES}
    for name, (rva, count) in EXPECTED_SITES.items():
        require(len(actual[name]) == count, f"Unexpected {name} count")
        require(manifest["state"].get("site_hits", {}).get(name) == count,
                f"Manifest {name} count mismatch")
        for event in actual[name]:
            require(event.get("rva") == rva, f"Wrong runtime {name} RVA")
            require(hex_pointer(event.get("pc"), f"{name} PC") == base + rva,
                    f"Wrong ASLR-relative {name} PC")
    require(sum(map(len, actual.values())) == len(hits), "Unknown native hit site")
    require(len({e.get("thread") for e in hits}) == 1, "Events span multiple threads")
    require(all(isinstance(e.get("timestamp_ms"), int) for e in events),
            "Missing event timestamps")
    timeline = [e["timestamp_ms"] for e in hits]
    require(timeline == sorted(timeline), "Non-monotonic hit chronology")
    ready_index = next(i for i, e in enumerate(events) if e.get("kind") == "ready")
    first_index = next(i for i, e in enumerate(events) if e.get("kind") == "hit")
    require(first_index > ready_index, "Native hit before hooks ready")
    require([e["site"] for e in hits] == [
        "group_ce00_entry", "group_parent_install",
        "parent_child_dispatch", "fractional_child_entry",
        "parent_child_dispatch", "fractional_child_entry"],
        "Different native construction/processing order")

    group = actual["group_ce00_entry"][0]
    install = actual["group_parent_install"][0]
    parent_events = actual["parent_child_dispatch"]
    child_events = actual["fractional_child_entry"]

    ret = field_pointer(group, "return_address")
    require(ret > base + 5, "Return address below image base")
    caller_rva = ret - base - 5
    require(caller_rva == EXPECTED_CALLSITE, "Unexpected Stage89 runtime callsite")
    owner = verify_native_callsite(dll_bytes, caller_rva)
    require(owner == EXPECTED_CALLER_OWNER, "Different original .pdata caller owner")

    group_input = field_pointer(group, "group_input_pointer")
    require(field_pointer(install, "group_input_pointer") == group_input,
            "Group input pointer did not reach parent-install point")
    parent = field_pointer(install, "parent_pointer")
    child = field_pointer(parent_events[0], "child_pointer")
    for i, event in enumerate(parent_events):
        require(field_pointer(event, "parent_pointer") == parent,
                "Parent dispatch did not use the created parent")
        require(field_pointer(event, "child_pointer") == child,
                "Parent dispatch changed fractional child")
        require(field_pointer(child_events[i], "child_pointer") == child,
                "Child entry was not the parent's fractional child")
        require(hex_pointer(child_events[i].get("registers", {}).get("rcx"),
                            "child RCX") == child, "Child RCX did not match the object")
        require(child_events[i].get("registers", {}).get("r8") ==
                child_events[i].get("fields", {}).get("input_count_register", {}).get("value"),
                "R8 field does not reflect captured register")

    rate_fields = [group.get("fields", {}).get(name, {})
                   for name in ("source_hz_f32", "target_hz_f32")]
    rate_captured = all(isinstance(f, dict) and "value" in f and "error" not in f
                        for f in rate_fields)
    rate_errors = sum(isinstance(f, dict) and bool(f.get("error"))
                      for f in rate_fields)
    require(manifest["state"].get("field_errors") >= rate_errors,
            "Manifest did not account for failed field readings")

    return {
        "status": STATUS,
        "provenance": "NATIVE_STAGE89_CAPTURE_PLUS_ORIGINAL_PE_STATIC",
        "original_dll_sha256": EXPECTED_DLL_SHA256,
        "private_archive_sha256": archive_sha256,
        "runtime_hook_count": len(hooks),
        "observed_native_hits": len(hits),
        "observed_one_thread": True,
        "hit_span_ms": timeline[-1] - timeline[0],
        "bound_group_callsite_rva": f"0x{caller_rva:X}",
        "static_pdata_function_owner_rva": f"0x{owner:X}",
        "original_e8_rel32_target_rva": f"0x{stage88.GROUP_HELPER:X}",
        "input_to_install_pointer_join_verified": True,
        "parent_same_instance_join_count": len(parent_events),
        "fractional_child_same_instance_join_count": len(child_events),
        "rates_captured": rate_captured,
        "rate_field_read_errors": rate_errors,
        "frida_hook_errors": manifest["state"]["hook_errors"],
        "clo_export_completion_verified": False,
        "windows_crash_root_cause": "UNKNOWN",
        "historical_stage64_instance_retroactively_identified": False,
        "model_name_measured_by_capture": False,
        "not_inferred": [
            "source/target sample rates or semantic meaning of R8 values",
            "successful CLO export", "cause of Sonicake Manager exit/crash",
            "same-instance pointer lineage for the historical Stage64 run",
            "NAM filename or hash from Stage89 runtime records",
            "exact source-version or numerical equivalence to public r8brain",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True, help="PRIVATE authentic 5868USB.dll")
    parser.add_argument("--capture", type=Path, required=True, help="PRIVATE Stage89 archive")
    parser.add_argument("--out", type=Path, required=True, help="Sanitized local JSON report")
    args = parser.parse_args()
    manifest, events, archive_sha256 = load_capture(args.capture)
    report = audit(manifest, events, args.dll.read_bytes(), archive_sha256)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "callsite": report["bound_group_callsite_rva"],
                      "parent_joins": report["parent_same_instance_join_count"],
                      "child_joins": report["fractional_child_same_instance_join_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
