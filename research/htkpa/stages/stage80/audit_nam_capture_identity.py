#!/usr/bin/env python3
"""Stage80: authenticate NAM headers and check capture-internal hash provenance.

Only the exact SHA-pinned user-supplied NAM and CLO fixtures are accepted.
Model weights and audio samples are never reported or passed to the vendor DLL.
The Stage79 exact-capture metadata gate is rerun first.
Later operator testimony about the 2203 filename is recorded separately, not
mistaken for a SHA256 stored within this historical capture.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage79"))
import audit_capture_architecture as stage79


STATUS = "TWO_NAM_ARCHITECTURES_VERIFIED_STAGE64_INPUT_IDENTITY_UNPROVEN"
NAM_PINS = {
    "2203": "29abbdbf982ee64b963d1d8de06848d1b06450a623bb08ba3ffefce146dfac42",
    "SC20": "509ad3d6dc31cf0539afe4a264ff7386d6282ffe9d1e0de4b6cce514b1915b11",
}
CLO_PINS = {
    "2203": "50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7",
    "SC20": "2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a",
}
MAX_NAM_BYTES = 1_000_000
MAX_CLO_BYTES = 65_536


def checked_file(path: Path, expected_sha: str, limit: int) -> bytes:
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Missing, empty or oversized private input: " + path.name)
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("Private input SHA256 mismatch: " + path.name)
    return data


def read_nam_header(data: bytes, label: str) -> dict:
    # Parsed weights are not retained in the output. The original JSON file is
    # bounded and SHA-pinned before parsing; no model inference takes place.
    model = json.loads(
        data.decode("utf-8"),
        object_pairs_hook=stage79.reject_duplicate_object_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid NAM JSON constant")),
    )
    if not isinstance(model, dict) or not isinstance(model.get("config"), dict):
        raise ValueError("Malformed NAM root/config: " + label)
    architecture = model.get("architecture")
    version = model.get("version")
    rate = model.get("sample_rate")
    if (not isinstance(architecture, str) or not architecture or
            not isinstance(version, str) or not version or
            isinstance(rate, bool) or not isinstance(rate, (int, float)) or
            not math.isfinite(rate) or rate <= 0):
        raise ValueError("Malformed NAM architecture/version/sample_rate: " + label)
    return {
        "architecture": architecture,
        "registered_in_stage77_original_pe": architecture in stage79.stage78.stage77.REGISTRATIONS,
        "format_version": version,
        "sample_rate_hz": rate,
        "model_weights_included_in_report": False,
    }


def exact_capture_completion_size(stage64: Path) -> int:
    # Reread just the selected bounded metadata member. Do not unpack or read
    # the two captured native f64 payloads.
    with tarfile.open(stage64, "r:gz") as archive:
        manifest = stage79.metadata_member(archive, "manifest.json", stage79.MAX_METADATA_SIZE)
    state = manifest.get("state") if isinstance(manifest, dict) else None
    size = state.get("completion_size_bytes") if isinstance(state, dict) else None
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("Stage64 completion size not recorded")
    return size


def exact_model_identity_mentions(stage64: Path, nams: dict[str, Path]) -> list[str]:
    """Find literal expected NAM hashes/names in bounded capture JSON only."""
    with tarfile.open(stage64, "r:gz") as archive:
        config = stage79.metadata_member(archive, "config.json", stage79.MAX_METADATA_SIZE)
        manifest = stage79.metadata_member(archive, "manifest.json", stage79.MAX_METADATA_SIZE)
        events_member = archive.getmember("frida_capture/events.jsonl")
        if (not events_member.isfile() or
                not 0 < events_member.size <= stage79.MAX_EVENTS_SIZE):
            raise ValueError("Stage64 events metadata invalid")
        opened = archive.extractfile(events_member)
        if opened is None:
            raise ValueError("Stage64 events unavailable")
        with opened:
            events = stage79.safe_event_list(opened.read(stage79.MAX_EVENTS_SIZE + 1))
    needles = {label: (NAM_PINS[label], nams[label].name.lower()) for label in NAM_PINS}
    results: set[str] = set()

    def visit(value: object, depth: int) -> None:
        if depth > stage79.MAX_NESTING_DEPTH:
            raise ValueError("Capture metadata nesting exceeds bound")
        if isinstance(value, dict):
            for child in value.values():
                visit(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                visit(child, depth + 1)
        elif isinstance(value, str):
            low = value.lower()
            for label, (sha, filename) in needles.items():
                if sha in low or filename in low:
                    results.add(label)

    for source in (config, manifest, events):
        visit(source, 0)
    return sorted(results)


def audit(dll: Path, stage64: Path, nams: dict[str, Path], clos: dict[str, Path],
          objdump: str | None = None) -> dict:
    previous = stage79.audit(dll, stage64, objdump)
    if (previous["status"] != stage79.STATUS_NO_KEY or
            previous["stage64_metadata_inspection"]["candidate_count"] != 0 or
            previous["claims"]["stage64_input_model_architecture_proven"] or
            previous["claims"]["specific_stage64_factory_selected"]):
        raise ValueError("Exact Stage79 no-architecture metadata gate changed")
    if set(nams) != set(NAM_PINS) or set(clos) != set(CLO_PINS):
        raise ValueError("Expected both exact NAM and CLO fixture labels")

    headers = {
        label: read_nam_header(checked_file(nams[label], sha, MAX_NAM_BYTES), label)
        for label, sha in NAM_PINS.items()
    }
    if not all(h["registered_in_stage77_original_pe"] for h in headers.values()):
        raise ValueError("A NAM architecture is absent from exact native registry")
    clo_sizes = {
        label: len(checked_file(clos[label], sha, MAX_CLO_BYTES))
        for label, sha in CLO_PINS.items()
    }
    captured_size = exact_capture_completion_size(stage64)
    exact_mentions = exact_model_identity_mentions(stage64, nams)

    return {
        "stage": 80,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": STATUS,
        "original_dll_sha256": stage79.DLL_SHA256,
        "stage64_archive_sha256": stage79.STAGE64_SHA256,
        "prior_stage79_status_verified": previous["status"],
        "verified_nam_headers": {
            label: {"sha256": NAM_PINS[label], **headers[label]}
            for label in NAM_PINS
        },
        "reference_clo_sizes": clo_sizes,
        "stage64_completion_clo_size": captured_size,
        "clo_size_only_match_nonunique": all(size == captured_size for size in clo_sizes.values()),
        "stage64_exact_source_nam_sha_or_filename_mentions": exact_mentions,
        "stage64_architecture_field_present_in_inspected_metadata": False,
        "independent_stage64_input_nam_identity_proven": False,
        "inference_boundary": "Two authenticated NAMs share an architecture and sample rate; those fields and an 8840-byte CLO do not independently identify the input from capture-internal metadata. The operator subsequently attested the 2203 model filename, but this audit does not claim a same-run SHA256 link.",
        "claims": {
            "original_dll_executed": False,
            "new_frida_hook_or_capture": False,
            "authentic_stage64_metadata_gate_rerun": True,
            "source_nam_architectures_observed": True,
            "specific_stage64_input_nam_identified_in_capture_metadata": False,
            "specific_stage64_native_factory_selected": False,
            "vendor_audio_or_full_nam_to_clo_parity_proven": False,
        },
        "next_gate": "Obtain independent same-run provenance linking exact NAM SHA256 to Stage64's completed CLO SHA256. Existing capture metadata has no source-model identity; do not infer it from architecture, sample rate or CLO size.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--stage64", type=Path, required=True)
    parser.add_argument("--nam-2203", type=Path, required=True)
    parser.add_argument("--nam-sc20", type=Path, required=True)
    parser.add_argument("--clo-2203", type=Path, required=True)
    parser.add_argument("--clo-sc20", type=Path, required=True)
    parser.add_argument("--objdump")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    originals = [args.dll, args.stage64, args.nam_2203, args.nam_sc20,
                 args.clo_2203, args.clo_sc20]
    if args.out and args.out.resolve() in [p.resolve() for p in originals]:
        raise ValueError("Refusing to overwrite original private input")
    report = audit(args.dll, args.stage64,
                   {"2203": args.nam_2203, "SC20": args.nam_sc20},
                   {"2203": args.clo_2203, "SC20": args.clo_sc20}, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage": 80, "status": report["status"],
        "architectures": {k: v["architecture"] for k, v in report["verified_nam_headers"].items()},
        "clo_size_match_nonunique": report["clo_size_only_match_nonunique"],
        "stage64_input_identity_proven": False,
        "report": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, RuntimeError, UnicodeError, json.JSONDecodeError,
            tarfile.TarError) as exc:
        print("[STAGE80 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
