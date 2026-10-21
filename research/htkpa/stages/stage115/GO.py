#!/usr/bin/env python3
"""HTKPA Stage115: static original-PE float32 block/vtable invocation boundary.

Reads original 5868USB.dll as INERT DATA ONLY. No DLL execution, Frida,
Manager, NAM inference, resampling, fitting, CLO, device or sample capture.
The call site is an authenticated *structural candidate*, not proven native
48-kHz NAM input provenance or runtime invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ORIGINAL_SHA256 = 'fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
ORIGINAL_SIZE = 2_902_016
IMAGE_BASE = 0x180000000
OWNER = (0xE0E0, 0xF940)
PARSER_CALL = (0xE698, 0xCC4E0)
WAV_CALL = (0xEB1E, 0xD4A0)
VIRTUAL_CALL = 0xF231
VIRTUAL_SLOT_OFFSET = 0x10
MAX_BLOCK = 0x400

# Short original-machine-code instruction anchors. A full DLL, large extracted
# opcode blocks, original audio and detailed private trace must stay off GitHub.
# Each pin is a disassembler-confirmed complete x64 instruction, not an E8
# byte scan through arbitrary data.
ANCHORS = {
    0xE69D: '488d4c2438',         # address of parsed-model object slot
    0xE6A7: '488b18',             # returned parser-slot pointer is dereferenced
    0xE6AD: '48895c2438',         # parser result saved in [rsp+0x38]
    0xEE48: '8b7b08',                # mov edi, [rbx+8] -- input vector length
    0xF123: '488b5c2438',       # reload parser result as dispatch object
    0xF128: '4c8bbc2498000000', # load candidate wav sample vector
    0xF130: '8d8100040000',        # lea eax,[rcx+0x400] -- max block
    0xF13D: '448bd7',              # mov r10d,edi
    0xF140: '3bc7',                # cmp eax,edi
    0xF142: '440f4ed0',            # cmovle r10d,eax
    0xF146: '442bd1',              # sub r10d,ecx -- block length
    0xF14C: '4c63e1',              # movsxd r12,ecx
    0xF14F: '4963fa',              # movsxd rdi,r10
    0xF1B0: '498b07',              # mov rax,[r15] -- source vector base
    0xF1B3: '8b0c02',              # mov ecx,[rdx+rax] -- source f32 bits
    0xF1B6: '41890c13',            # mov [r11+rdx],ecx -- local scratch
    0xF209: '8b0c01',              # mov ecx,[rcx+rax] -- f32 tail
    0xF20C: '898c1410070000',      # mov [rsp+rdx+0x710],ecx
    0xF21B: '488b03',              # mov rax,[rbx] -- virtual dispatch owner
    0xF21E: '458bca',              # mov r9d,r10d -- chunk count
    0xF221: '4c8d442478',          # lea r8,[rsp+0x78] -- output reference
    0xF226: '488d942448020000',    # lea rdx,[rsp+0x248] -- input reference
    0xF22E: '488bcb',              # mov rcx,rbx -- object pointer
    0xF231: 'ff5010',              # call qword ptr [rax+0x10]
    0xF284: '488b442478',          # mov rax,[rsp+0x78] -- returned output ptr
    0xF289: 'f30f100408',          # movss xmm0,[rax+rcx] -- returned f32
    0xF28E: 'f3410f59c0',          # mulss xmm0,xmm8 -- postprocess scale
    0xF293: '488b06',              # mov rax,[rsi] -- destination buffer
    0xF296: 'f30f110402',          # movss [rdx+rax],xmm0 -- write f32
}


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


class PE:
    """Minimal fail-closed PE32+ map plus .pdata runtime function owners."""
    def __init__(self, raw: bytes):
        self.raw = raw
        require(len(raw) >= 512 and raw[:2] == b'MZ', 'invalid DOS header')
        offset = struct.unpack_from('<I', raw, 0x3C)[0]
        require(0x40 <= offset <= len(raw)-24 and raw[offset:offset+4] == b'PE\0\0', 'invalid PE signature')
        require(struct.unpack_from('<H',raw,offset+4)[0] == 0x8664, 'not AMD64')
        count = struct.unpack_from('<H',raw,offset+6)[0]
        size = struct.unpack_from('<H',raw,offset+20)[0]
        optional = offset+24
        require(0 < count <= 32 and size >= 240 and optional+size+count*40 <= len(raw), 'invalid section headers')
        require(struct.unpack_from('<H',raw,optional)[0] == 0x20B, 'not PE32+')
        require(struct.unpack_from('<Q',raw,optional+24)[0] == IMAGE_BASE, 'original image base changed')
        self.sections = {}
        for i in range(count):
            s=optional+size+i*40
            name=raw[s:s+8].split(b'\0',1)[0].decode('ascii')
            virtual_size, virtual_rva, file_size, file_offset = struct.unpack_from('<IIII',raw,s+8)
            require(name not in self.sections and file_offset + file_size <= len(raw), 'overlapping or truncated section')
            self.sections[name]=(virtual_rva,virtual_size,file_offset,file_size)
        require('.text' in self.sections and '.pdata' in self.sections,'required PE sections missing')
        pdata_rva, pdata_size = struct.unpack_from('<II',raw,optional+112+8*3)
        prva,pvirt,poff,psize=self.sections['.pdata']
        require(pdata_rva >= prva and pdata_rva+pdata_size <= prva+psize and pdata_size%12==0,
                'exception directory / pdata section invalid')
        self.pdata=(pdata_rva,pdata_size)

    def get(self,rva:int,n:int,section:str='.text')->bytes:
        require(section in self.sections,'unknown PE section')
        base,virt,off,size=self.sections[section]
        require(n>0 and base<=rva and rva+n<=base+size and rva+n<=base+virt,'RVA outside section')
        return self.raw[off+rva-base:off+rva-base+n]

    def owner_of(self,rva:int)->tuple[int,int,int]:
        start,n=self.pdata
        matches=[]
        for offset in range(0,n,12):
            a,b,unwind=struct.unpack('<III',self.get(start+offset,12,'.pdata'))
            if a<=rva<b:
                matches.append((a,b,unwind))
        require(len(matches)==1,'nonunique or missing .pdata owner for RVA')
        return matches[0]


def direct_target(pe:PE, at:int)->int:
    code=pe.get(at,5)
    require(code[0]==0xE8,'expected direct E8 call')
    disp=struct.unpack_from('<i',code,1)[0]
    return at+5+disp


def inspect_bytes(raw: bytes, *, check_original_hash: bool=True) -> dict:
    if check_original_hash:
        require(len(raw)==ORIGINAL_SIZE and hashlib.sha256(raw).hexdigest()==ORIGINAL_SHA256,
                'original private DLL SHA/size mismatch')
    pe=PE(raw)
    anchors={}
    for at,hexbytes in ANCHORS.items():
        expected=bytes.fromhex(hexbytes)
        require(pe.get(at,len(expected))==expected,f'original machine-code anchor mismatch at RVA 0x{at:X}')
        require(pe.owner_of(at)[:2]==OWNER,f'machine-code anchor .pdata owner mismatch at RVA 0x{at:X}')
        anchors[f'0x{at:X}']='PASS'
    for at,target in (PARSER_CALL,WAV_CALL):
        require(direct_target(pe,at)==target,f'direct call target mismatch at RVA 0x{at:X}')
        require(pe.owner_of(at)[:2]==OWNER,'direct call .pdata owner mismatch')
    candidate=pe.owner_of(VIRTUAL_CALL)
    require(candidate[:2]==OWNER,'virtual call is not in original getNamOutput owner')
    # Instructions from F130 through F231 form one guarded static block:
    # truncate to a caller-calculated max 1024; copy f32 to stack; pointer
    # references and count set in Windows x64 arg regs; vtable slot call.
    return {
        'stage':115,
        'status':'STAGE115_ORIGINAL_PE_FLOAT32_BLOCK_VIRTUAL_CALLSITE_STATIC_VERIFIED',
        'provenance':'exact SHA-pinned original 5868USB.dll inert PE32+ x64 byte and .pdata audit',
        'rva_owner':{'begin':f'0x{candidate[0]:X}','end_exclusive':f'0x{candidate[1]:X}'},
        'earlier_model_weight_parser_direct_call_rva':f'0x{PARSER_CALL[0]:X}',
        'model_parser_return_object_slot_written_rva':'0xE6AD',
        'same_local_model_object_slot_loaded_rva':'0xF123',
        'earlier_model_weight_parser_target_rva':f'0x{PARSER_CALL[1]:X}',
        'earlier_wav_resampler_direct_call_rva':f'0x{WAV_CALL[0]:X}',
        'earlier_wav_resampler_target_rva':f'0x{WAV_CALL[1]:X}',
        'float32_source_to_local_buffer_anchor':'0xF1B0–0xF20C',
        'chunk_bounded_by_0x400_elements':True,
        'maximum_candidate_block_frames':MAX_BLOCK,
        'indirect_call_site_rva':f'0x{VIRTUAL_CALL:X}',
        'indirect_vtable_slot_offset_bytes':VIRTUAL_SLOT_OFFSET,
        'windows_x64_call_registers':{
            'rcx':'object pointer from RBX',
            'rdx':'pointer to local slot containing scratch float32 input pointer',
            'r8':'pointer to local slot for float32 output pointer',
            'r9d':'runtime-clamped chunk element count',
        },
        'post_call_float32_output_read_store':'0xF284–0xF296',
        'exact_instruction_anchors_verified':len(anchors),
        'earlier_direct_calls_verified':2,
        'true_native_nam_input_buffer_identity_proven':False,
        'virtual_slot_function_target_resolved':False,
        'runtime_stage97_path_execution_proven':False,
        'vendor_48khz_input_resampler_or_model_numeric_parity_verified':False,
        'actual_nam_inference_method_semantics_proven':False,
        'no_native_execution_or_capture_or_new_inference':True,
    }


def run(dll:Path, output:Path)->dict:
    require(not output.exists(), 'refusing to overwrite existing Stage115 private report')
    report=inspect_bytes(dll.read_bytes())
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as out:
        json.dump(report,out,indent=2);out.write('\n')
    return {'status':report['status'],
            'static_indirect_call_candidate_rva':report['indirect_call_site_rva'],
            'owner':report['rva_owner'],
            'anchored_instructions':report['exact_instruction_anchors_verified'],
            'original_native_input_identity_proven':False,
            'private_report':str(output)}


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dll',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.dll,a.out),indent=2))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,struct.error,json.JSONDecodeError) as exc:
        print('[Stage115] '+str(exc),file=sys.stderr)
        sys.exit(2)
