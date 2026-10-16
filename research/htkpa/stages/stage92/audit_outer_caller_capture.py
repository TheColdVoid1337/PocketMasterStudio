#!/usr/bin/env python3
"""Stage92: offline validation of a NEW, user-operated, bounded Frida capture.

Do not use a Stage89 capture as input. This cannot retroactively identify its
outer caller. This audit reads a private tarball and exact original DLL as data;
its emitted report contains no ASLR bases, heap addresses, or event journal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage90"))
import audit_stage89_runtime_chain as stage90
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage91"))
import audit_upstream_wav_callers as stage91


STATUS = "STAGE92_NATIVE_CAPTURE_GATE_PREPARED_RUNTIME_NOT_YET_OBSERVED"
MATCHED = "NEW_RUN_DIRECT_OUTER_AND_INNER_CALLS_SAME_THREAD_SEQUENCE_OBSERVED"
UNBOUND = "NEW_RUN_OUTER_TO_INNER_PAIR_UNBOUND"
SITES = {"wav_worker_d4a0_entry": 0xD4A0, "resampler_ce00_entry": 0xCE00}
MAX_SITE_HITS = 4
MAX_SEQUENCE_MS = 2000
CONFIG_MEMBER = "frida_capture/config.json"
EXPECTED_SHA = stage90.EXPECTED_DLL_SHA256


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def validate_config(config: dict) -> None:
    """Reject expanded or changed instrumentation, including audio field reads."""
    require(isinstance(config, dict), "Invalid config object")
    require(set(config) == {"module", "sha256", "image_base", "sites"},
            "Unexpected top-level capture mode or option")
    require(config.get("module") == "5868USB.dll" and
            config.get("sha256") == EXPECTED_SHA and
            int(str(config.get("image_base", "0")), 0) == stage91.BASE,
            "Wrong pinned module, SHA or image base")
    sites = config.get("sites")
    require(isinstance(sites, list) and len(sites) == 2,
            "Stage92 must have exactly two scalar sites")
    observed = {}
    for site in sites:
        require(isinstance(site, dict), "Invalid site object")
        require(set(site) in ({"name", "address", "max_hits", "required", "fields"},
                              {"name", "rva", "max_hits", "required", "fields"}),
                "Unexpected site-level instrumentation option")
        name = site.get("name")
        require(name in SITES and name not in observed, "Unexpected/duplicate site")
        addr = site.get("rva", site.get("address"))
        require(int(str(addr), 0) == SITES[name], "Wrong site RVA")
        require(site.get("required") is True and
                type(site.get("max_hits")) is int and
                site["max_hits"] == MAX_SITE_HITS,
                "Stage92 required/hit bound changed")
        fields = site.get("fields")
        require(isinstance(fields, list) and len(fields) == 1,
                "Only return-address metadata allowed")
        f = fields[0]
        require(set(f) in ({"name", "type", "reg", "offset"},
                           {"name", "type", "reg", "offset", "count"}),
                "Unexpected return-address field option")
        require(isinstance(f, dict) and f.get("name") == "return_address" and
                f.get("type") == "ptr" and f.get("reg") == "rsp" and
                int(str(f.get("offset", 0)), 0) == 0,
                "Unexpected field; no audio or heap payload allowed")
        observed[name] = True
    require(set(observed) == set(SITES), "Missing stage site")


def verify_original_dll(data: bytes) -> None:
    require(hashlib.sha256(data).hexdigest() == EXPECTED_SHA,
            "Original DLL SHA256 mismatch")


def original_direct_owner(data: bytes, call_rva: int, target: int) -> int | None:
    """Only attribute exact decoded, original PE E8 rel32 calls."""
    if target == 0xD4A0:
        owner = stage91.CALLS_TO_WAV.get(call_rva)
    elif target == 0xCE00:
        owner = stage91.stage88.CALL_OWNERS.get(call_rva)
    else:
        return None
    if owner is None:
        return None  # An indirect or unexpected caller is not a direct-call proof.
    encoded = stage91.stage72.pe_file_bytes(data, call_rva, 5)
    stage91.stage88.verify_rel32_bytes(encoded, call_rva, target)
    found = stage91.stage72.previous.PEFunctions(data).owner(call_rva).start
    require(found == owner, "Original .pdata owner mismatch")
    return owner


def validated_hits(manifest: dict, events: list[dict], data: bytes) -> list[dict]:
    require(manifest.get("status") in
            {"CAPTURED_HOOKS_ONLY", "INCOMPLETE", "OPERATOR_INTERRUPTED"},
            "Capture status does not support runtime conclusion")
    require(manifest.get("expected_sha256") == EXPECTED_SHA and
            manifest.get("hook_count") == 2, "Wrong capture SHA or hook count")
    state = manifest.get("state", {})
    require(isinstance(state, dict) and state.get("runtime_verified") is True and
            state.get("ready") is True and state.get("hook_errors") == 0 and
            state.get("field_errors") == 0, "Runtime readiness or Frida errors")
    require(manifest.get("completion_verified") is False,
            "Unexpected completion claim in metadata-only capture")
    loads = [e for e in events if e.get("kind") == "module_loaded"]
    require(len(loads) == 1 and
            str(loads[0].get("path", "")).lower().endswith("5868usb.dll") and
            loads[0].get("runtime_sha256") == EXPECTED_SHA,
            "Wrong original runtime module identity")
    base = stage90.hex_pointer(loads[0].get("base"), "ASLR base")
    hooks = [e for e in events if e.get("kind") == "hook_attached"]
    require(len(hooks) == 2 and
            {e.get("site"): e.get("rva") for e in hooks} == SITES,
            "Hook installation mismatch")
    ready = [(i, e) for i, e in enumerate(events) if e.get("kind") == "ready"]
    require(len(ready) == 1 and ready[0][1].get("installed") == 2 and
            ready[0][1].get("requested") == 2, "Two hooks not ready")
    hits = []
    for index, e in enumerate(events):
        if e.get("kind") != "hit":
            continue
        require(index > ready[0][0], "Hit before ready")
        site = e.get("site")
        require(site in SITES and e.get("rva") == SITES[site] and
                stage90.hex_pointer(e.get("pc"), "runtime PC") == base + SITES[site],
                "Unexpected hit address or ASLR")
        ret = stage90.field_pointer(e, "return_address")
        require(ret > base + 5, "Return address outside expected PE image")
        call = ret - base - 5
        owner = original_direct_owner(data, call, SITES[site])
        require(isinstance(e.get("timestamp_ms"), int) and
                type(e.get("thread")) is int, "Missing native time/thread metadata")
        hits.append({"site": site, "call": call, "owner": owner,
                     "thread": e["thread"], "time": e["timestamp_ms"]})
    require(0 < len(hits) <= 2 * MAX_SITE_HITS and
            len(hits) == state.get("hits"), "Native hit count mismatch")
    for site in SITES:
        count = sum(h["site"] == site for h in hits)
        require(count <= MAX_SITE_HITS and
                count == state.get("site_hits", {}).get(site, 0),
                "Native site counter mismatch")
    require([h["time"] for h in hits] == sorted(h["time"] for h in hits),
            "Nonmonotonic event chronology")
    return hits


def find_observed_sequence(hits: list[dict]) -> tuple[dict | None, int]:
    """Only a chronological same-thread sequence; not a saved stack identity."""
    candidates = []
    for idx, inner in enumerate(hits):
        if inner["site"] != "resampler_ce00_entry" or inner["call"] != 0xD786 or inner["owner"] != 0xD4A0:
            continue
        preceding = [h for h in hits[:idx]
                     if h["site"] == "wav_worker_d4a0_entry" and
                     h["thread"] == inner["thread"] and h["owner"] is not None and
                     0 <= inner["time"] - h["time"] <= MAX_SEQUENCE_MS]
        if len(preceding) == 1:
            candidates.append(preceding[0])
    distinct = {(h["call"], h["thread"], h["time"]) for h in candidates}
    return (candidates[0] if len(distinct) == 1 else None), len(distinct)


def audit(manifest: dict, events: list[dict], config: dict,
          data: bytes, archive_sha256: str) -> dict:
    validate_config(config)
    verify_original_dll(data)
    hits = validated_hits(manifest, events, data)
    matched, number_of_candidates = find_observed_sequence(hits)
    status = MATCHED if matched is not None else UNBOUND
    return {
        "stage": 92, "status": status,
        "provenance": "NEW_OPERATOR_FRIDA_JOURNAL_PLUS_SHA_PINNED_ORIGINAL_PE",
        "original_dll_sha256": EXPECTED_SHA,
        "private_capture_archive_sha256": archive_sha256,
        "installed_hooks": 2, "observed_hits": len(hits),
        "outer_worker_hits": sum(h["site"] == "wav_worker_d4a0_entry" for h in hits),
        "inner_group_hits": sum(h["site"] == "resampler_ce00_entry" for h in hits),
        "candidate_same_thread_sequences": number_of_candidates,
        "outer_caller_direct_rva": f"0x{matched['call']:X}" if matched else "UNBOUND",
        "outer_caller_original_pdata_owner": f"0x{matched['owner']:X}" if matched else "UNBOUND",
        "inner_original_callsite_rva": "0xD786" if matched else "UNBOUND",
        "proves_same_invocation_stack_identity": False,
        "identifies_historical_stage89_upstream_call": False,
        "model_identity_in_native_trace": False,
        "clo_export_completed": False,
        "manager_crash_cause": "UNKNOWN",
        "not_claimed": [
            "historical Stage89 outer caller or Stage64 parent identity",
            "exact same-invocation call stack, file path or input sample rate",
            "NAM hash, CLO export completion or crash cause",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(args.out.resolve() not in {args.dll.resolve(), args.capture.resolve()},
            "Refusing to overwrite a private input")
    manifest, events, archive_sha = stage90.load_capture(args.capture)
    with tarfile.open(args.capture, mode="r:gz") as archive:
        config = json.loads(stage90.bounded_json_member(archive, CONFIG_MEMBER))
    result = audit(manifest, events, config, args.dll.read_bytes(), archive_sha)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stage": 92, "status": result["status"],
                      "observed_hits": result["observed_hits"],
                      "outer_caller": result["outer_caller_direct_rva"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
