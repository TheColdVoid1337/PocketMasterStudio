#!/usr/bin/env python3
"""HTKPA Stage46: READ-ONLY PE64 MSVC RTTI/vftable inspection.

Never loads/executes/hooks proprietary DLL. Compares only pinned source DLL SHA;
prints addresses and metadata, NOT decompiled vendor code or waveform buffers.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

VENDOR_SHA="fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
NAMES={
    "CDSPBlockConvolver":b".?AVCDSPBlockConvolver@r8b@@",
    "CDSPFracInterpolator_template":b".?AV?$CDSPFracInterpolator@",
    "CDSPResampler24":b".?AVCDSPResampler24@r8b@@",
}
SLOTS=("destructor","getInLenBeforeOutPos","getLatency","getLatencyFrac",
       "getMaxOutLen","clear","process")


class PE:
    def __init__(self,data:bytes):
        self.data=data
        if data[:2]!=b"MZ":raise ValueError("not PE/MZ")
        nt=self.u32(0x3c)
        if data[nt:nt+4]!=b"PE\x00\x00":raise ValueError("invalid NT signature")
        coff=nt+4
        count=self.u16(coff+2)
        szopt=self.u16(coff+16)
        opt=coff+20
        if self.u16(opt)!=0x20b:raise ValueError("requires PE32+")
        self.base=self.u64(opt+24)
        self.sections=[]
        for i in range(count):
            off=opt+szopt+40*i
            name=data[off:off+8].rstrip(b"\x00").decode("ascii")
            vsize,rva,size,fo=struct.unpack_from("<IIII",data,off+8)
            self.sections.append((name,rva,vsize,size,fo))
    def u16(self,off):return struct.unpack_from("<H",self.data,off)[0]
    def u32(self,off):return struct.unpack_from("<I",self.data,off)[0]
    def u64(self,off):return struct.unpack_from("<Q",self.data,off)[0]
    def rva(self,off):
        for name,rva,vsz,sz,fo in self.sections:
            if fo<=off<fo+sz:return rva+off-fo
        raise ValueError("unmapped file offset "+hex(off))
    def is_code(self,rva):
        return any(name==".text" and start<=rva<start+vsz
                   for name,start,vsz,sz,fo in self.sections)
    def rdata(self):
        for name,rva,vsz,sz,fo in self.sections:
            if name in (".rdata","_RDATA"):yield (fo,fo+sz)


def find_class(pe,label,term):
    found=[];pos=0;data=pe.data
    while True:
        idx=data.find(term,pos)
        if idx<0:break
        pos=idx+1
        try:td=pe.rva(idx-16)
        except ValueError:continue
        end=data.find(b"\x00",idx,idx+160)
        if end<=idx:continue
        tname=data[idx:end].decode("ascii","replace")
        vtables=[]
        # PE64 CompleteObjectLocator:
        # signature,offset,cdOffset,TypeDescriptorRVA,ClassDescRVA,selfRVA
        for lo,hi in pe.rdata():
            for off in range(lo+12,hi-24,4):
                if pe.u32(off)!=td:continue
                col=off-12
                if pe.u32(col)!=1 or pe.u32(col+16)==0:continue
                if pe.u32(col+20)!=pe.rva(col):continue
                col_rva=pe.rva(col)
                ref=(pe.base+col_rva).to_bytes(8,"little")
                for lo2,hi2 in pe.rdata():
                    pos2=lo2
                    while True:
                        v=data.find(ref,pos2,hi2)
                        if v<0:break
                        pos2=v+1
                        if v+8+len(SLOTS)*8>len(data):continue
                        functions=[pe.u64(v+8+i*8)-pe.base
                                   for i in range(len(SLOTS))]
                        if not all(pe.is_code(f) for f in functions):continue
                        vtables.append({
                            "col_rva":hex(col_rva),
                            "vftable_rva":hex(pe.rva(v+8)),
                            "methods":{name:hex(pe.base+rva)
                                       for name,rva in zip(SLOTS,functions)}
                        })
        if vtables:
            found.append({"rtti_name":tname,
                          "type_descriptor_rva":hex(td),"vtables":vtables})
    if not found:raise ValueError("No valid RTTI vtable found for "+label)
    return found


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--dll",type=Path,required=True)
    ap.add_argument("--out",type=Path)
    args=ap.parse_args()
    b=args.dll.read_bytes()
    h=hashlib.sha256(b).hexdigest()
    if h!=VENDOR_SHA:
        raise ValueError("DLL digest differs from studied file: "+h)
    pe=PE(b)
    mapping={name:find_class(pe,name,term) for name,term in NAMES.items()}
    process=lambda name:mapping[name][0]["vtables"][0]["methods"]["process"]
    if process("CDSPBlockConvolver")!="0x18000c220":
        raise AssertionError("Stage32/33 known block process address mismatch")
    if process("CDSPFracInterpolator_template")!="0x1800135c0":
        raise AssertionError("fractional process address mismatch")
    result={
        "stage":46,"status":"STATIC_RTTI_VTABLE_CONFIRMED",
        "dll_sha256":h,"imagebase":hex(pe.base),"classes":mapping,
        "finding":"MSVC virtual slot 6 process() is 0x18000c220 for block convolver and 0x1800135c0 for templated fractional interpolator",
        "safety":"No runtime call or Frida hook. RTTI proves virtual slot identity, NOT hook stability, pointer lifetime, actual conversion path, or vendor final 48000-Hz output",
        "note":"Template-instantiated class in vendor DLL is not necessarily the same release API as non-template upstream r8brain v6.5",
    }
    txt=json.dumps(result,indent=2)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(txt,encoding="utf-8")
    print(txt)


if __name__=="__main__":main()
