"""Stage115: original-PE anchor and report contract tested on FAKE DLL bytes only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

CODE=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage115/GO.py'
spec=importlib.util.spec_from_file_location('htkpa_stage115_fixture',CODE)
M=importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)


def fixture():
    """Artificial PE32+/.pdata with injected *short* expected instruction pins."""
    b=bytearray(0x4500)
    b[0:2]=b'MZ'
    struct.pack_into('<I',b,0x3c,0x80)
    b[0x80:0x84]=b'PE\0\0'
    struct.pack_into('<H',b,0x84,0x8664)
    struct.pack_into('<H',b,0x86,2)
    struct.pack_into('<H',b,0x94,0xf0)
    opt=0x98
    struct.pack_into('<H',b,opt,0x20b)
    struct.pack_into('<Q',b,opt+24,M.IMAGE_BASE)
    struct.pack_into('<II',b,opt+112+8*3,0x33d000,12)
    def section(idx,name,rva,n,offset):
        x=opt+0xf0+40*idx
        b[x:x+8]=name.encode().ljust(8,b'\0')
        struct.pack_into('<IIII',b,x+8,n,rva,n,offset)
    section(0,'.text',0xE000,0x2000,0x400)
    section(1,'.pdata',0x33d000,12,0x3000)
    def text_write(rva,chunk):b[0x400+rva-0xE000:0x400+rva-0xE000+len(chunk)]=chunk
    for at,hexbytes in M.ANCHORS.items():text_write(at,bytes.fromhex(hexbytes))
    for at,target in (M.PARSER_CALL,M.WAV_CALL):
        text_write(at,b'\xe8'+struct.pack('<i',target-at-5))
    struct.pack_into('<III',b,0x3000,M.OWNER[0],M.OWNER[1],0x25e968)
    return b


class StaticTests(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(M.VIRTUAL_CALL,0xF231)
        self.assertEqual(M.MAX_BLOCK,0x400)
        self.assertEqual(M.OWNER,(0xE0E0,0xF940))
        self.assertEqual(len(M.ANCHORS),29)

    def test_valid_fake_pe(self):
        r=M.inspect_bytes(bytes(fixture()),check_original_hash=False)
        self.assertEqual(r['status'],'STAGE115_ORIGINAL_PE_FLOAT32_BLOCK_VIRTUAL_CALLSITE_STATIC_VERIFIED')
        self.assertEqual(r['exact_instruction_anchors_verified'],29)
        self.assertEqual(r['model_parser_return_object_slot_written_rva'],'0xE6AD')
        self.assertFalse(r['virtual_slot_function_target_resolved'])
        self.assertFalse(r['true_native_nam_input_buffer_identity_proven'])

    def test_strict_real_sha_on_fake(self):
        with self.assertRaisesRegex(ValueError,'SHA/size'):
            M.inspect_bytes(bytes(fixture()))

    def test_indirect_call_mutation(self):
        b=fixture();b[0x400+0xF231-0xE000+2]=0x20
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_object_slot_storage_mutation(self):
        b=fixture();b[0x400+0xE6AD-0xE000+3]=0x40
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_model_slot_reuse_mutation(self):
        b=fixture();b[0x400+0xF123-0xE000+3]=0x40
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_chunk_capacity_mutation(self):
        b=fixture();b[0x400+0xF130-0xE000+3]=0x05
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_source_copy_mutation(self):
        b=fixture();b[0x400+0xF1B6-0xE000]=0x90
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_output_write_mutation(self):
        b=fixture();b[0x400+0xF296-0xE000+1]=0x0e
        with self.assertRaisesRegex(ValueError,'anchor mismatch'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_direct_parser_call_mutation(self):
        b=fixture();b[0x400+0xE698-0xE000+1]^=1
        with self.assertRaisesRegex(ValueError,'direct call target mismatch'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_direct_wav_call_mutation(self):
        b=fixture();b[0x400+0xEB1E-0xE000+2]^=1
        with self.assertRaisesRegex(ValueError,'direct call target mismatch'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_bad_function_owner(self):
        b=fixture();struct.pack_into('<III',b,0x3000,0xF000,0xF940,0)
        with self.assertRaisesRegex(ValueError,'.pdata owner'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_bad_pdata_bounds(self):
        b=fixture();struct.pack_into('<II',b,0x98+112+24,0x33d000,13)
        with self.assertRaisesRegex(ValueError,'exception directory'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_wrong_architecture(self):
        b=fixture();struct.pack_into('<H',b,0x84,0x14c)
        with self.assertRaisesRegex(ValueError,'AMD64'):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_wrong_section_mapping(self):
        b=fixture();struct.pack_into('<I',b,0x98+0xf0+12,0xf00)
        with self.assertRaises(ValueError):
            M.inspect_bytes(bytes(b),check_original_hash=False)

    def test_report_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            a=Path(folder)/'fake.dll';a.write_bytes(fixture())
            output=Path(folder)/'already.json';output.write_text('{}')
            with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                M.run(a,output)
            self.assertEqual(output.read_text(),'{}')

    def test_no_proprietary_data_or_runtime_calls_in_source(self):
        s=CODE.read_text()
        self.assertNotIn('readByteArray',s)
        self.assertNotIn('subprocess.run',s)
        self.assertNotIn('ctypes.WinDLL',s)
        self.assertNotIn('frida.attach',s)
        self.assertIn("'x'",s)


if __name__=='__main__': unittest.main()
