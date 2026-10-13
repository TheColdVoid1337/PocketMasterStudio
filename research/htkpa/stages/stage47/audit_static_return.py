#!/usr/bin/env python3
"""HTKPA Stage47: static-only call-site and output-pointer/lifetime audit.

Reads an exact-SHA proprietary PE DLL as DATA with llvm-objdump. It never loads
the DLL, opens Manager or uses Frida. It emits only instruction metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

EXPECTED_DLL_SHA = "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa"
BASE = 0x180000000
ADDR = {
    "resampler_process": BASE + 0x11850,
    "intermediate_call": BASE + 0x118B1,
    "last_stage_call": BASE + 0x11909,
    "last_stage_return_site": BASE + 0x1190C,
    "resampler_clear_last_vtable_compare": BASE + 0x11A56,
    "frac_process": BASE + 0x135C0,
    "frac_result_pointer_read": BASE + 0x135CB,
    "frac_output_write": BASE + 0x13C38,
    "frac_count_return": BASE + 0x13D1D,
    "frac_vftable": BASE + 0x245170,
    "last_stage_capacity_check": BASE + 0x12237,
    "last_stage_buffer_choice": BASE + 0x12263,
}

# Each text pattern identifies the instruction at a FULL absolute image VA, not
# an arbitrary byte sequence. llvm-objdump's AT&T syntax is required.
WRAPPER_ANCHORS = {
    0x1185C: r"^movq\s+%r9,\s*%r15$",
    0x11892: r"^leaq\s+0x40\(%rsp\),\s*%r9$",
    0x118B1: r"^callq\s+\*0x30\(%rax\)$",
    0x118BA: r"^movl\s+%eax,\s*%r8d$",
    0x118BD: r"^movq\s+0x40\(%rsp\),\s*%rax$",
    0x118C2: r"^movq\s+%rax,\s*%rdx$",
    0x118CF: r"^cmpq\s+\$0x0,\s*0x50\(%rbx\)$",
    0x118EA: r"^movq\s+0x70\(%rbx\),\s*%rax$",
    0x118FA: r"^movq\s+%rax,\s*\(%r15\)$",
    0x118FD: r"^movq\s+0x50\(%rbx\),\s*%rcx$",
    0x11901: r"^movq\s+%rax,\s*0x40\(%rsp\)$",
    0x11906: r"^movq\s+\(%rcx\),\s*%rax$",
    0x11909: r"^callq\s+\*0x30\(%rax\)$",
    0x1190C: r"^addq\s+\$0x20,\s*%rsp$",
}
FRAC_ANCHORS = {
    0x135CB: r"^movq\s+\(%r9\),\s*%r12$",
    0x135CE: r"^movq\s+%r9,\s*%r13$",
    0x13C38: r"^movsd\s+%xmm3,\s*\(%r12\)$",
    0x13C3E: r"^addq\s+\$0x8,\s*%r12$",
    0x13D15: r"^subq\s+\(%r13\),\s*%r12$",
    0x13D19: r"^sarq\s+\$0x3,\s*%r12$",
    0x13D1D: r"^movl\s+%r12d,\s*%eax$",
    0x13D28: r"^retq$",
}
SETUP_ANCHORS = {
    0x1222A: r"^movq\s+%rsi,\s*0x50\(%rbx\)$",
    0x12231: r"^movl\s+%r13d,\s*%edx$",
    0x12237: r"^callq\s+\*0x20\(%rax\)$",
    0x1223A: r"^cmpl\s+%r12d,\s*%eax$",
    0x1223F: r"^movq\s+0x58\(%rbx\),\s*%rax$",
    0x1224E: r"^movq\s+%rdi,\s*0x70\(%rbx\)$",
    0x12256: r"^leaq\s+0x68\(%rbx\),\s*%rcx$",
    0x1225A: r"^callq\s+0x1800122f0\b.*$",
    0x1225F: r"^movq\s+0x68\(%rbx\),\s*%rax$",
    0x12263: r"^movq\s+%rax,\s*0x70\(%rbx\)$",
}
CLEAR_ANCHORS = {
    0x11A4F: r"^leaq\s+0x23371a\(%rip\),\s*%rcx$",
    0x11A56: r"^cmpq\s+%rcx,\s*%rax$",
}

def disasm(dll: Path, objdump: str, a: int, b: int) -> dict[int, str]:
    cmd = [objdump, "-d", "--no-show-raw-insn",
           "--start-address="+hex(a), "--stop-address="+hex(b), str(dll)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError("llvm-objdump failed: "+p.stderr[-1200:])
    out = {}
    for line in p.stdout.splitlines():
        m = re.match(r"^\s*([0-9a-fA-F]+):\s+(.+)$", line)
        if m:
            insn = m.group(2).split("#", 1)[0].strip()
            out[int(m.group(1), 16)] = insn
    return out

def assert_instructions(name: str, instructions: dict[int, str],
                        wanted: dict[int, str]) -> None:
    for offset, pattern in wanted.items():
        addr = BASE+offset
        found = instructions.get(addr, "<MISSING>")
        if not re.fullmatch(pattern, found):
            raise ValueError(f"{name} instruction failed @ {addr:#x}: {found!r}, expected {pattern!r}")

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dll", type=Path, required=True)
    p.add_argument("--objdump", default="llvm-objdump")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    if not args.dll.is_file():
        raise FileNotFoundError("Private original DLL missing: "+str(args.dll))
    digest = hashlib.sha256(args.dll.read_bytes()).hexdigest()
    if digest != EXPECTED_DLL_SHA:
        raise ValueError("Original DLL SHA256 mismatch: "+digest)

    wrapper = disasm(args.dll, args.objdump, BASE+0x11850, BASE+0x11915)
    clearer = disasm(args.dll, args.objdump, BASE+0x11A39, BASE+0x11A60)
    frac = disasm(args.dll, args.objdump, BASE+0x135C0, BASE+0x13D29)
    setup = disasm(args.dll, args.objdump, BASE+0x12213, BASE+0x12268)
    assert_instructions("resampler", wrapper, WRAPPER_ANCHORS)
    assert_instructions("clear", clearer, CLEAR_ANCHORS)
    assert_instructions("fractional", frac, FRAC_ANCHORS)
    assert_instructions("last-stage buffer setup", setup, SETUP_ANCHORS)

    # The final virtual slot offset 0x30 is grounded by CDSPProcessor's
    # 7-slot vftable; a static indirect call never proves its runtime target.
    final_vftable = BASE + 0x245170
    if "# "+hex(final_vftable) not in "\n".join(
        disasm_with_comments(args.dll, args.objdump, BASE+0x11A4F, BASE+0x11A59)):
        raise ValueError("Clear/reset source did not resolve expected fractional vftable pointer")

    # In the exact fractional function there are no calls, and the only
    # direct dereference of saved output reference R13 is an operand READ at
    # 0x13D15. Treat this as a bounded fact about this function only.
    calls = [(hex(a), insn) for a,insn in frac.items()
             if re.search(r"\bcall\w*\b", insn)]
    refs = [(hex(a), insn) for a,insn in frac.items()
            if "(%r13)" in insn]
    if calls or refs != [(hex(BASE+0x13D15), frac[BASE+0x13D15])]:
        raise ValueError("Fractional pointer-ref or call behavior changed: "+repr((calls,refs)))

    result = {
        "stage":47, "status":"STATIC_LAST_STAGE_RETURN_SITE_VERIFIED",
        "dll_sha256":digest, "imagebase":hex(BASE),
        "key_addresses":{key:hex(value) for key,value in ADDR.items()},
        "wrapper_call_path":[
            {"site":hex(BASE+0x118B1),
             "operation":"virtual slot6 process() on intermediate processor; R9=&stack local 0x40; EAX count and local output pointer fed to next stage"},
            {"site":hex(BASE+0x118FA),
             "operation":"original caller's double*& output pointer set to candidate final output storage through [R15]"},
            {"site":hex(BASE+0x11909),
             "operation":"virtual slot6 process() on processor pointer held at resampler [RBX+0x50]"},
            {"site":hex(BASE+0x1190C),
             "operation":"FIRST instruction after final stage returns; EAX output count and [R15] proposed output base; single STATIC observation candidate only"}
        ],
        "last_stage_output_storage":{
            "processor_pointer":"RBX+0x50",
            "max_out_len_call":"virtual slot 4 getMaxOutLen at 0x180012237",
            "available_buffer_choices":"Reuse intermediate tmp buffer [RBX+0x58], reallocate dedicated [RBX+0x68], or leave [RBX+0x70]=0 for in-place output to original input buffer",
            "candidate_output_pointer":"The pointer written to original double*& at [R15] immediately BEFORE final virtual call",
            "candidate_output_count":"EAX immediately AFTER final virtual call at 0x18001190C",
            "pointer_lifetime_caveat":"Buffer may be owned by resampler and overwritten on subsequent process(); cannot claim safe cross-call access. Bound reads to the current returned EAX count and verify the memory region before use.",
        },
        "fractional_process_checks":{
            "entry_va":hex(BASE+0x135C0),
            "input_f64_count_register":"R8D",
            "input_f64_pointer_register":"RDX",
            "output_reference_register":"R9 (double**)",
            "output_base_loaded_into":"R12 at "+hex(BASE+0x135CB),
            "output_write":"movsd XMM3,[R12] at "+hex(BASE+0x13C38),
            "output_pointer_increment":"R12 += 8 at "+hex(BASE+0x13C3E),
            "output_count_from_pointer_delta":"(R12 - *R13)/8 returned EAX at "+hex(BASE+0x13D1D),
            "in_function_indirect_or_direct_calls":len(calls),
            "output_reference_memory_reads":[v[0] for v in refs],
            "output_reference_repointed_by_function":"No direct write observed within this exact analyzed function"
        },
        "clear_method_control":{
            "class_specific_vftable_va":hex(final_vftable),
            "meaning":"resampler clear() explicitly recognizes the native templated fractional vftable via pointer comparison; supports its role as last processor but does NOT confirm this converter instance's actual runtime type"
        },
        "risk_and_scope":{
            "hook_attempted":False,
            "vendor_fractional_samples_captured":False,
            "runtime_reachability_proven":False,
            "safe_memory_lifetime_proven":False,
            "candidate":"0x18001190C post-last-stage return; no Frida config or runtime testing in Stage47",
            "next_gate":"Check last-stage dynamic vftable identity, buffer allocation/capacity and a one-shot guarded observation design before any native process runs"
        },
        "privacy":"No original instruction bytes, DLL, source waveforms or Frida hooks committed."
    }
    serialized = json.dumps(result, ensure_ascii=False, indent=2)+"\n"
    print(serialized)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(serialized,encoding="utf-8")

def disasm_with_comments(dll:Path,objdump:str,a:int,b:int)->list[str]:
    cmd=[objdump,"-d","--no-show-raw-insn","--start-address="+hex(a),
         "--stop-address="+hex(b),str(dll)]
    run=subprocess.run(cmd,capture_output=True,text=True,check=True)
    return run.stdout.splitlines()

if __name__=="__main__":
    main()
