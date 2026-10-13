#!/usr/bin/env python3
"""Stage31: verify provenance/byte counts of bounded Frida resampler output samples.
No claim of complete signal parity: 16-double prefixes may be non-contiguous.
"""
import argparse,json,tarfile,collections,hashlib
from pathlib import Path

EXPECTED="fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
NAMES={"frida_capture/config.json","frida_capture/manifest.json","frida_capture/events.jsonl","frida_capture/HANDOFF.md"}
def analyze(path):
    with tarfile.open(path,"r:gz") as t:
        m=t.getmembers()
        if {x.name for x in m}!=NAMES or any(not x.isfile() or x.size>8000000 for x in m):
            raise ValueError("unexpected archive membership")
        contents={x.name.split("/")[-1]:t.extractfile(x).read() for x in m}
    manifest=json.loads(contents["manifest.json"])
    if not manifest.get("runtime_verified"):raise ValueError("original DLL hash unverified")
    if manifest.get("field_errors") or manifest.get("hook_errors"):raise ValueError("field or Frida error")
    config=json.loads(contents["config.json"])
    if config["sha256"]!=EXPECTED:raise ValueError("wrong DLL config")
    events=[json.loads(l) for l in contents["events.jsonl"].splitlines()]
    captures=[]
    for e in events:
        if e.get("kind")!="hit" or e.get("site")!="output_before_memcpy":continue
        f=e["fields"]
        count=int(f["copy_bytes"]["value"])
        n=f["src_first16_f64"]
        if count%8:raise ValueError("unaligned memcpy length")
        if count<128:raise ValueError("prefix read exceeds memcpy length: "+str(count))
        if len(n["values"])!=16 or len(n["bits"])!=16:raise ValueError("wrong sample count")
        if any("error" in v for v in f.values()):raise ValueError("field error")
        captures.append({"thread":e["thread"],"src":f["src_address"]["value"],
                         "dst":f["dest_address"]["value"],"bytes":count,
                         "samples_observed":16,"first_f64":n["values"][0]})
    if not captures:raise ValueError("no output events")
    return {"status":"NATIVE_BOUNDARY_CAPTURE_VALID","capture_events":len(captures),
            "bytes_per_event":[c["bytes"] for c in captures],
            "threads":dict(collections.Counter(str(c["thread"]) for c in captures)),
            "example_event":captures[0],
            "scope":"bounded prefixes and memcpy sizes; NOT complete native 48k output or parity"}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("archive",type=Path);a=p.parse_args()
    print(json.dumps(analyze(a.archive),indent=2))
