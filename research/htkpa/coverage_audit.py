#!/usr/bin/env python3
"""Read-only SHA-pinned PE coverage audit. Measures referenced function footprints,
not execution coverage, reverse-engineering completeness, or numerical parity."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import re
import struct
from pathlib import Path

DLL_SHA="fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"

def pe_sections(data):
    if data[:2]!=b"MZ": raise ValueError("Missing MZ header")
    p=struct.unpack_from("<I",data,0x3c)[0]
    if data[p:p+4]!=b"PE\0\0": raise ValueError("Missing PE header")
    c=p+4
    size=struct.unpack_from("<H",data,c+16)[0]
    if struct.unpack_from("<H",data,c+20)[0]!=0x20b: raise ValueError("Expected PE32+")
    base=struct.unpack_from("<Q",data,c+20+24)[0]
    count=struct.unpack_from("<H",data,c+2)[0]
    sections={}
    for i in range(count):
        o=c+20+size+40*i
        name=data[o:o+8].split(b"\0",1)[0].decode("ascii")
        sections[name]=struct.unpack_from("<IIII",data,o+8)
    return base,sections

def function_spans(data,base,sections):
    textsize,textrva,_,_=sections[".text"]
    _,_,rawsize,offset=sections[".pdata"]
    spans=[]
    for pos in range(offset,offset+rawsize,12):
        if pos+12>len(data): break
        s,e,_=struct.unpack_from("<III",data,pos)
        if textrva<=s<e<=textrva+textsize: spans.append((base+s,base+e))
    return sorted(set(spans))

def source_pins(path):
    tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    for n in tree.body:
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="PINS" for t in n.targets):
            if not isinstance(n.value,ast.Dict): raise ValueError("PINS must be a literal dictionary")
            out=set()
            for key in n.value.keys:
                if not isinstance(key,ast.Constant) or type(key.value)!=int:
                    raise ValueError("PINS keys must be integer literals")
                out.add(key.value)
            return out
    raise ValueError("No top-level PINS assignment in "+str(path))

def audit(dll,sources,handoff=None):
    data=dll.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    if digest!=DLL_SHA: raise ValueError("Unrecognized DLL SHA256: "+digest)
    base,sections=pe_sections(data)
    spans=function_spans(data,base,sections)
    groups={p.name:source_pins(p) for p in sources}
    pins=set().union(*groups.values())
    def mapped(va):
        return next((f for f in spans if f[0]<=va<f[1]),None)
    touched={f for a in pins if (f:=mapped(a)) is not None}
    cited=set()
    if handoff:
        cited={int(v,16) for v in re.findall(r"0x180[0-9A-Fa-f]{5,8}",handoff.read_text(encoding="utf-8"))}
    union={f for a in pins|cited if (f:=mapped(a)) is not None}
    tsize=sections[".text"][0]
    return {
      "warning":"Full containing-function footprint, NOT number of analyzed bytes",
      "dll_sha256":digest,"dll_bytes":len(data),"text_virtual_bytes":tsize,
      "pdata_unwind_functions":len(spans),
      "source_pin_counts":{k:len(v) for k,v in groups.items()},
      "unique_pins":len(pins),"pins_mapped_to_pdata":sum(mapped(a) is not None for a in pins),
      "pin_touched_functions":len(touched),
      "pin_touched_percent_of_unwind_functions":round(len(touched)*100/len(spans),4),
      "pin_function_full_span_bytes":sum(e-s for s,e in touched),
      "pin_function_full_span_percent_text":round(sum(e-s for s,e in touched)*100/tsize,4),
      "handoff_address_citations":len(cited),
      "union_pins_handoff_functions":len(union),
      "union_full_span_bytes":sum(e-s for s,e in union),
      "union_full_span_percent_text":round(sum(e-s for s,e in union)*100/tsize,4),
      "cautions":[
        "One address pin does not mean its full containing function was analyzed",
        ".pdata excludes some leaf functions; other DLL functionality is irrelevant",
        "Handoff address citations are not a complete historical verifier inventory",
        "This cannot measure progress toward full native WAV/CLO numerical parity"
      ]
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dll",type=Path,required=True)
    ap.add_argument("--source",type=Path,action="append",required=True)
    ap.add_argument("--handoff",type=Path)
    ap.add_argument("--output",type=Path)
    a=ap.parse_args()
    result=audit(a.dll,a.source,a.handoff)
    text=json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n"
    if a.output: a.output.write_text(text,encoding="utf-8")
    print(text,end="")

if __name__=="__main__": main()
