"""Small read-only PE virtual-address to raw-file byte mapper; never loads DLL."""
from __future__ import annotations
import struct
DLL_SHA='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'

def dll_pe_at(data:bytes,addr:int,n:int)->bytes:
    if data[:2]!=b'MZ':raise ValueError('not MZ')
    peoff=struct.unpack_from('<I',data,0x3c)[0]
    if data[peoff:peoff+4]!=b'PE\0\0':raise ValueError('not PE')
    nsec=struct.unpack_from('<H',data,peoff+6)[0]
    optsz=struct.unpack_from('<H',data,peoff+20)[0]
    optoff=peoff+24
    imagebase=struct.unpack_from('<Q',data,optoff+24)[0]
    rva=addr-imagebase
    for j in range(nsec):
        off=optoff+optsz+j*40
        size,virt,raw,ptr=struct.unpack_from('<4I',data,off+8)
        if virt<=rva and rva+n<=virt+raw:
            return data[ptr+rva-virt:ptr+rva-virt+n]
    raise ValueError(f'PE address lacks file data: {addr:#x}')
