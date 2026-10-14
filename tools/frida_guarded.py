"""Reusable guarded Frida metadata mode for tools/frida_capture.py.

This module has NO Sonicake, stage, DLL-address or vendor-version constants.
Only a strictly validated JSON descriptor may specify its original
post-call processor object, dynamic vtable and result pointer/count registers.
Metadata mode reads no waveform; bounded binary mode is separate opt-in.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import platform
import re
import threading
import time


AGENT = r"""
'use strict';
const spec = JSON_SPEC;
let moduleFound = null;
let hook = null, observed = 0, metadataSent = false, firstRejectSent = false;
const site = spec.sites[0], g = site.guard;
function emit(d) { send(Object.assign({kind:'note', thread:Process.getCurrentThreadId()}, d)); }
function readable(p, n) {
  if (p.isNull() || n < 1) return false;
  const r = Process.findRangeByAddress(p);
  if (r === null || r.protection.indexOf('r') < 0) return false;
  return p.compare(r.base) >= 0 &&
    p.add(n-1).compare(r.base.add(r.size)) < 0;
}
function reject(reason) {
  if (spec.trace && observed <= spec.trace.max_events)
    emit({kind:'trace_reject',site:site.name,observed:observed,reason:reason});
  if (!firstRejectSent) {
    firstRejectSent = true;
    emit({kind:'first_rejected_return',site:site.name,reason:reason,observed:observed});
  }
}
rpc.exports = {
  arm() {
    if (hook !== null || moduleFound === null) return false;
    const m = Process.findModuleByName(spec.module);
    if (m === null || !m.base.equals(moduleFound.base) || site.rva >= m.size)
      return false;
    const loc = m.base.add(site.rva);
    const mapped = Process.findRangeByAddress(loc);
    if (mapped === null || mapped.protection.indexOf('x') < 0) return false;
    try {
      hook = Interceptor.attach(loc, {onEnter() {
        if (metadataSent && !spec.trace) return;
        if (spec.trace && observed >= spec.trace.max_events) return;
        if (++observed > g.max_observations) {
          if (observed === g.max_observations+1)
            emit({kind:'observation_limit',site:site.name,limit:g.max_observations});
          return;
        }
        if (spec.trace && observed === spec.trace.max_events)
          emit({kind:'trace_cap_reached',site:site.name,observations:observed});
        try {
          const c = this.context;
          const owner = c[g.owner_reg];
          const slot = owner.add(g.owner_offset);
          if (!readable(slot,Process.pointerSize)) return reject('processor slot unreadable');
          const proc = slot.readPointer();
          if (!readable(proc,Process.pointerSize)) return reject('processor unreadable');
          const vtable = proc.readPointer();
          const expected = m.base.add(g.vtable_rva);
          if (!vtable.equals(expected)) return reject('processor vtable mismatch');
          const count = c[g.count_reg].and(ptr('0xffffffff')).toUInt32();
          if (spec.trace) {
            const traceEvent={kind:'trace_return',site:site.name,observed:observed,
                  owner_pointer:owner.toString(),processor_pointer:proc.toString(),
                  input_pointer:c.rdi.toString(),output_f64:count,
                  count_in_range:count <= g.max_samples};
            // Historical Stage51 config key is retained for archive replay,
            // but static inspection proves the callee CLOBBERS R8D.
            // This is a post-call scratch/phase register, NOT input_f64.
            if (spec.trace.input_count_reg === 'r8')
              traceEvent.postcall_r8d = c.r8.and(ptr('0xffffffff')).toUInt32();
            emit(traceEvent);
          }
          if (count < 1 || count > g.max_samples)
            return reject('return count zero or out of bounds');
          const ref = c[g.output_ref_reg];
          if (!readable(ref,Process.pointerSize)) return reject('result pointer reference unreadable');
          const output = ref.readPointer();
          if (!output.and(ptr('0x7')).isNull()) return reject('result not f64 aligned');
          const bytes = count * 8;
          if (!readable(output, bytes)) return reject('result span not readable');
          if (spec.trace && metadataSent) return;
          BINARY_EXTENSION_POINT
          metadataSent = true;
          emit({kind:'metadata_hit',valid:true,site:site.name,observed:observed,
                processor_vtable:vtable.toString(),expected_vtable:expected.toString(),
                output_pointer:output.toString(),output_f64:count,output_bytes:bytes,
                readable_range:true,pc:loc.toString()});
        } catch(e) { reject('guard exception: '+String(e).slice(0,140)); }
      }});
      emit({kind:'hook_attached',site:site.name,rva:site.rva,hooks_installed:1});
      return true;
    } catch(e) {
      emit({kind:'arm_error',site:site.name,error:String(e).slice(0,160)});
      return false;
    }
  }
};
Process.attachModuleObserver({onAdded(m) {
  if(m.name.toLowerCase()!==spec.module.toLowerCase()) return;
  moduleFound=m;
  emit({kind:'module_found',name:m.name,path:m.path,base:m.base.toString(),size:m.size});
}});
"""




# Stage52: one hook at the FRACTIONAL FUNCTION ENTRY, not the old wrapper
# return site. Paired onEnter/onLeave records per-call input and output counts.
# No waveform access, no arbitrary code from the JSON config, no second hook.
IO_AGENT = r"""
'use strict';
const spec = JSON_SPEC, site = spec.sites[0], guard = site.guard;
let moduleFound = null, attached = false, observed = 0, firstReject = false;
let inputProbeProcessor = null, inputProbeStep = 0, outputProbeDone = false;
function emit(data) { send(Object.assign({kind:'note',thread:Process.getCurrentThreadId()},data)); }
function readable(p, n) {
  if (p.isNull() || n < 1) return false;
  const region = Process.findRangeByAddress(p);
  return region !== null && region.protection.indexOf('r') >= 0 &&
    p.compare(region.base) >= 0 &&
    p.add(n-1).compare(region.base.add(region.size)) < 0;
}
function reject(why,n) {
  if (!firstReject) { firstReject = true; emit({kind:'io_first_reject',reason:why,observed:n}); }
}
rpc.exports = {
  arm() {
    if (attached || moduleFound === null) return false;
    const mod = Process.findModuleByName(spec.module);
    if (mod === null || !mod.base.equals(moduleFound.base) || site.rva >= mod.size) return false;
    const loc = mod.base.add(site.rva);
    const span = Process.findRangeByAddress(loc);
    if (span === null || span.protection.indexOf('x') < 0) return false;
    try {
      Interceptor.attach(loc,{
        onEnter() {
          this.observation = null;
          this.outputRef = null;
          if (observed >= guard.max_observations) return;
          const nth = ++observed;
          if (nth === guard.max_observations)
            emit({kind:'io_cap_reached',observed:nth});
          try {
            const processor = this.context.rcx;
            if (!readable(processor,Process.pointerSize)) return reject('processor unreadable',nth);
            if (!processor.readPointer().equals(mod.base.add(guard.vtable_rva)))
              return reject('fractional vtable mismatch',nth);
            const inputCount = this.context.r8.and(ptr('0xffffffff')).toUInt32();
            if (inputCount > guard.max_input_f64) return reject('input count outside guard',nth);
            const record={observed:nth, input_f64:inputCount,
                          processor_pointer:processor.toString()};
            RATE_PROBE_EXTENSION
            INPUT_PROBE_EXTENSION
            OUTPUT_PROBE_ENTER_EXTENSION
            this.observation = record;
          } catch(e) { reject('enter exception: '+String(e).slice(0,120),nth); }
        },
        onLeave(retval) {
          if (this.observation === null) return;
          try {
            const outputCount = retval.and(ptr('0xffffffff')).toUInt32();
            if (outputCount > guard.max_output_f64)
              return reject('output count outside guard',this.observation.observed);
            OUTPUT_PROBE_LEAVE_EXTENSION
            emit(Object.assign({kind:'fractional_io',valid:true,site:site.name,
                output_f64:outputCount},this.observation));
          } catch(e) { reject('leave exception: '+String(e).slice(0,120),
                              this.observation.observed); }
        }
      });
      attached = true;
      emit({kind:'hook_attached',site:site.name,rva:site.rva,hooks_installed:1});
      return true;
    } catch(e) {
      emit({kind:'arm_error',error:String(e).slice(0,180)});
      return false;
    }
  }
};
Process.attachModuleObserver({onAdded(m){
  if (m.name.toLowerCase() !== spec.module.toLowerCase()) return;
  moduleFound = m;
  emit({kind:'module_found',name:m.name,path:m.path,base:m.base.toString(),size:m.size});
}});
"""


# Fixed scalar object fields read by the native fractional core:
# RVA 0x13C59: mulsd [r10+0x1008]; 0x13C62: divsd [r10+0x1010].
# No waveform reads; installed only in opt-in Stage53 config.
IO_RATE_EXTENSION = r"""
            const rp=spec.rate_probe;
            const nPtr=processor.add(rp.numerator_offset);
            const dPtr=processor.add(rp.denominator_offset);
            if (!readable(nPtr,8) || !readable(dPtr,8))
              return reject('step rate fields unreadable',nth);
            const n=nPtr.readDouble(), d=dPtr.readDouble();
            if (!Number.isFinite(n) || !Number.isFinite(d) ||
                n <= 0 || d <= 0 || n > 7000000 || d > 7000000)
              return reject('invalid fractional step ratio fields',nth);
            record.step_numerator=n;
            record.step_denominator=d;
            record.step_output_input_ratio=d/n;
"""


# Opt-in input prefixes: RVA 0x135C0 moves RDX to RSI and R8D to R15D.
# Copy only the first 3+256 f64 of the original 96k->44.1 fractional instance.
IO_INPUT_EXTENSION = r"""
            const pick=spec.input_probe;
            const targetRate=(record.step_numerator === pick.numerator &&
                              record.step_denominator === pick.denominator);
            const same=(inputProbeProcessor !== null &&
                        inputProbeProcessor === processor.toString());
            const first=(inputProbeStep === 0 && targetRate &&
                         inputCount === pick.first_f64);
            const second=(inputProbeStep === 1 && targetRate && same &&
                          inputCount === pick.second_f64);
            if (first || second) {
              const n = first ? pick.first_f64 : pick.second_f64;
              const ptrInput = this.context.rdx;
              const nbytes = n * 8;
              if (!ptrInput.and(ptr('0x7')).isNull() || !readable(ptrInput,nbytes))
                return reject('bounded fractional input unreadable/alignment',nth);
              const copy=ptrInput.readByteArray(nbytes);
              if (copy === null || copy.byteLength !== nbytes)
                return reject('fractional input copy incomplete',nth);
              const step = first ? 1 : 2;
              if (first) inputProbeProcessor=processor.toString();
              inputProbeStep=step;
              send({kind:'fractional_input_prefix',valid:true,site:site.name,
                    step:step,observed:nth,processor_pointer:processor.toString(),
                    input_f64:n,copied_bytes:nbytes,
                    rate_numerator:record.step_numerator,
                    rate_denominator:record.step_denominator,
                    provenance:'fractional_rdx_onenter'},copy);
            }
"""


# Exact native output first 32 f64 from the first full-size 88200->48000
# fractional call. RVA 0x135CB reads *R9; RVA 0x13D15 computes R12-*R9.
IO_OUTPUT_ENTER_EXTENSION = r"""
            const want=spec.output_probe;
            if (!outputProbeDone && record.step_numerator===want.numerator &&
                record.step_denominator===want.denominator &&
                inputCount===want.first_input_f64) {
              const ref=this.context.r9;
              if (!readable(ref,Process.pointerSize))
                return reject('48k output pointer-ref unreadable',nth);
              this.outputRef=ref;
            }
"""
IO_OUTPUT_LEAVE_EXTENSION = r"""
            if (this.outputRef !== null && !outputProbeDone) {
              const want=spec.output_probe;
              if (outputCount !== want.first_output_f64)
                return reject('48k output count mismatch',this.observation.observed);
              const ref=this.outputRef;
              if (!readable(ref,Process.pointerSize))
                return reject('48k output reference expired',this.observation.observed);
              const output=ref.readPointer();
              const bytes=want.output_samples*8;
              if (!output.and(ptr('0x7')).isNull() || !readable(output,bytes))
                return reject('48k output prefix unreadable',this.observation.observed);
              const copied=output.readByteArray(bytes);
              if (copied===null || copied.byteLength!==bytes)
                return reject('48k output copy incomplete',this.observation.observed);
              outputProbeDone=true;
              send({kind:'fractional_output_prefix',valid:true,site:site.name,
                    observed:this.observation.observed,
                    processor_pointer:this.observation.processor_pointer,
                    input_f64:this.observation.input_f64,output_f64:outputCount,
                    copied_f64:want.output_samples,copied_bytes:bytes,
                    rate_numerator:want.numerator,rate_denominator:want.denominator,
                    provenance:'fractional_r9_ref_onleave'},copied);
            }
"""


def validate_fractional_io(cfg: dict, address_fn) -> dict:
    """Reuse strict SHA/Windows path lifecycle validation; separate entry-hook guard."""
    if not isinstance(cfg,dict) or cfg.get("mode")!="guarded_fractional_io":
        raise ValueError("expected guarded_fractional_io descriptor")
    if set(cfg)-{"module","sha256","mode","image_base","target","completion","sites","lifecycle","rate_probe","input_probe","output_probe"}:
        raise ValueError("unexpected fractional I/O config fields")
    rate_probe=cfg.get("rate_probe")
    if rate_probe is not None:
        if (not isinstance(rate_probe,dict)
                or set(rate_probe)!={"numerator_offset","denominator_offset"}
                or type(rate_probe["numerator_offset"]) is not int
                or type(rate_probe["denominator_offset"]) is not int
                or rate_probe["numerator_offset"]!=0x1008
                or rate_probe["denominator_offset"]!=0x1010):
            raise ValueError("rate_probe only accepts verified f64 offsets 0x1008/0x1010")
    probe=cfg.get("input_probe")
    if probe is not None:
        if (rate_probe is None or not isinstance(probe,dict)
                or set(probe)!={"first_f64","second_f64","total_max_bytes","numerator","denominator"}
                or any(type(v) is not int for v in probe.values())
                or probe!={"first_f64":3,"second_f64":256,"total_max_bytes":2072,
                           "numerator":96000,"denominator":44100}):
            raise ValueError("Stage54 input probe must be exactly 3+256 f64 at 96000->44100")
    out_probe=cfg.get("output_probe")
    if out_probe is not None:
        if (rate_probe is None or not isinstance(out_probe,dict)
                or set(out_probe)!={"output_samples","total_max_bytes","numerator",
                                    "denominator","first_input_f64","first_output_f64"}
                or any(type(v) is not int for v in out_probe.values())
                or out_probe!={"output_samples":32,"total_max_bytes":256,
                               "numerator":88200,"denominator":48000,
                               "first_input_f64":6170612,"first_output_f64":3358150}):
            raise ValueError("Stage54 48k output prefix requires exact guarded full-stream geometry")
    sites=cfg.get("sites")
    if not isinstance(sites,list) or len(sites)!=1:
        raise ValueError("fractional IO accepts exactly one hook")
    site=sites[0]
    if not isinstance(site,dict) or set(site)!={"name","address","fields","required","max_hits","guard"}:
        raise ValueError("fractional IO site keys are fixed")
    if site["fields"]!=[] or site["required"] is not True or site["max_hits"]!=1:
        raise ValueError("fractional IO must use one required, field-free hook")
    guard=site["guard"]
    if not isinstance(guard,dict) or set(guard)!={"kind","vtable_rva","max_observations","max_input_f64","max_output_f64"}:
        raise ValueError("fractional entry guard keys are fixed")
    if guard["kind"]!="fractional_entry_io":
        raise ValueError("fractional entry kind mismatch")
    for key, value, limit in (
        ("max_observations",guard["max_observations"],64),
        ("max_input_f64",guard["max_input_f64"],7000000),
        ("max_output_f64",guard["max_output_f64"],7000000),
    ):
        if type(value) is not int or value!=limit:
            raise ValueError(f"fractional {key} requires verified bound {limit}")
    # Validate *all* common security/launch/output parameters using the
    # established guarded_metadata validator (not a second permissive parser).
    # This dummy guard exists ONLY to invoke common validation; it is NEVER
    # serialized into the resulting entry-hook descriptor or used as an agent.
    proxy=dict(cfg)
    proxy.pop("rate_probe",None)
    proxy.pop("input_probe",None)
    proxy.pop("output_probe",None)
    proxy["mode"]="guarded_metadata"
    proxy["sites"]=[dict(site,guard={
        "kind":"processor_output","owner_reg":"rbx","owner_offset":80,
        "vtable_rva":guard["vtable_rva"],"output_ref_reg":"r15",
        "count_reg":"rax","max_samples":4096,"max_observations":64,
    })]
    normalized=validate_config(proxy,address_fn)
    normalized["mode"]="guarded_fractional_io"
    if rate_probe is not None:
        normalized["rate_probe"]=dict(rate_probe)
    if probe is not None:
        normalized["input_probe"]=dict(probe)
    if out_probe is not None:
        normalized["output_probe"]=dict(out_probe)
    normalized["sites"]=[dict(normalized["sites"][0],guard={
        "kind":"fractional_entry_io",
        "vtable_rva":normalized["sites"][0]["guard"]["vtable_rva"],
        "max_observations":64,"max_input_f64":7000000,
        "max_output_f64":7000000,
    })]
    return normalized

def validate_config(cfg: dict, address_fn) -> dict:
    """Strict declarative guard schema; arbitrary script payloads are forbidden."""
    if not isinstance(cfg,dict):
        raise ValueError("config must be an object")
    mode=cfg.get("mode")
    if mode=="guarded_fractional_io":
        return validate_fractional_io(cfg,address_fn)
    if mode not in ("guarded_metadata","guarded_f64_binary"):
        raise ValueError("guarded mode must be guarded_metadata or guarded_f64_binary")
    trace=cfg.get("trace")
    if trace is not None:
        if (mode!="guarded_f64_binary" or not isinstance(trace,dict) or
                set(trace) not in ({"max_events"},{"max_events","input_count_reg"}) or
                type(trace["max_events"]) is not int or trace["max_events"]!=64):
            raise ValueError("trace requires guarded_f64_binary and max_events=64")
        if "input_count_reg" in trace and trace["input_count_reg"]!="r8":
            raise ValueError("legacy Stage51 input_count_reg accepts only r8 as postcall debug register")
    if not isinstance(cfg.get("module"),str) or not re.fullmatch(r"[A-Za-z0-9_. -]+\.(dll|exe)",cfg["module"],re.I):
        raise ValueError("simple module basename required")
    if not isinstance(cfg.get("sha256"),str) or not re.fullmatch(r"[A-Fa-f0-9]{64}",cfg["sha256"]):
        raise ValueError("original module SHA256 mandatory")
    base = int(str(cfg.get("image_base","0x180000000")),0)
    sites=cfg.get("sites")
    if not isinstance(sites,list) or len(sites)!=1:
        raise ValueError("guarded_metadata requires exactly one site")
    s=sites[0]
    if not isinstance(s,dict) or set(s)-{"name","address","required","max_hits","guard","fields"}:
        raise ValueError("guarded site has unknown properties")
    if s.get("fields"):
        raise ValueError("guarded mode rejects scalar and binary fields; metadata only")
    if not isinstance(s.get("name"),str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}",s["name"]):
        raise ValueError("invalid site name")
    if s.get("required",True) is not True or s.get("max_hits",1)!=1:
        raise ValueError("guarded site must be required with max_hits=1")
    g=s.get("guard")
    permitted={"kind","owner_reg","owner_offset","vtable_rva","output_ref_reg",
               "count_reg","max_samples","max_observations"}
    if not isinstance(g,dict) or set(g)!=permitted:
        raise ValueError("guard fields must match the fixed processor_output schema exactly")
    if g["kind"]!="processor_output":
        raise ValueError("unknown guarded metadata kind")
    regs={"rax","rbx","rcx","rdx","rsi","rdi","rbp","rsp",
          "r8","r9","r10","r11","r12","r13","r14","r15"}
    for key in ("owner_reg","output_ref_reg","count_reg"):
        if g[key] not in regs:
            raise ValueError("unsupported register in "+key)
    def integer(value,key,minimum,maximum):
        if type(value) is not int or not minimum<=value<=maximum:
            raise ValueError(key+" must be an integer in allowed bounds")
        return value
    off=integer(g["owner_offset"],"owner_offset",0,4096)
    if off%8:
        raise ValueError("owner_offset must be pointer aligned")
    max_samples=integer(g["max_samples"],"max_samples",1,4096)
    max_observations=integer(g["max_observations"],"max_observations",1,1024)
    if trace is not None and max_observations<trace["max_events"]:
        raise ValueError("trace max_events exceeds max_observations")
    vtable=address_fn(g["vtable_rva"],base)
    if vtable<0 or vtable>=0x10000000:
        raise ValueError("implausible vtable RVA")
    rv=address_fn(s.get("address"),base)
    if rv>=0x10000000:
        raise ValueError("implausible code RVA")

    target=cfg.get("target")
    if not isinstance(target,dict) or set(target)!={"process_name_contains"}:
        raise ValueError("target must provide process_name_contains only")
    match=target["process_name_contains"]
    if not isinstance(match,str) or not re.fullmatch(r"[A-Za-z0-9_. -]{3,100}",match):
        raise ValueError("invalid process match string")
    # Lifecycle is declarative and OPTIONAL for old guarded configs.
    # All paths are interpreted only on Windows; no app is launched in self-test.
    lifecycle=cfg.get("lifecycle")
    if lifecycle is not None:
        if not isinstance(lifecycle,dict) or set(lifecycle)!={
            "executable","start","close","close_timeout_seconds"
        }:
            raise ValueError("lifecycle must specify executable/start/close/close_timeout_seconds")
        exe=lifecycle["executable"]
        if not isinstance(exe,str) or not re.fullmatch(
            r"[A-Za-z]:/[^\x00-\x1f<>:\"|?*]+",exe):
            raise ValueError("lifecycle.executable must be an absolute C:/... Windows EXE path")
        if (not exe.lower().endswith(".exe") or
                any(part in ("",".","..") for part in exe[3:].split("/")) or
                "\\" in exe or PureWindowsPath(exe).drive==""):
            raise ValueError("unsafe executable path")
        if lifecycle["start"] not in ("fresh","if_missing","attach_only"):
            raise ValueError("lifecycle.start must be fresh, if_missing or attach_only")
        if lifecycle["close"] not in ("if_launched","never"):
            raise ValueError("lifecycle.close must be if_launched or never")
        t=lifecycle["close_timeout_seconds"]
        if type(t) is not int or not 1<=t<=30:
            raise ValueError("lifecycle.close_timeout_seconds must be 1..30")
        lifecycle=dict(lifecycle)

    completion=cfg.get("completion")
    if not isinstance(completion,dict):
        raise ValueError("completion must be a declarative object")
    shared={"type","recursive","stable_seconds"}
    locations=set(completion)-shared
    if (not locations in ({"path"},{"appdata_subdir"}) or
            set(completion)!=shared|locations or completion["type"]!="changed_clo"):
        raise ValueError("completion needs exactly one of path or appdata_subdir")
    if "path" in completion:
        watch=completion["path"]
        if (not isinstance(watch,str) or
                not re.fullmatch(r"[A-Za-z]:/[^\x00-\x1f<>:\"|?*]+",watch) or
                "\\" in watch or
                any(part in ("",".","..") for part in watch[3:].split("/"))):
            raise ValueError("completion.path must be a safe absolute C:/... directory")
    else:
        sub=completion["appdata_subdir"]
        if not isinstance(sub,str) or not sub or ":" in sub or "\\" in sub or sub.startswith("/"):
            raise ValueError("appdata_subdir must be safe slash-separated relative segments")
        if any(part in ("",".","..") or not re.fullmatch(r"[A-Za-z0-9_. -]+",part)
               for part in sub.split("/")):
            raise ValueError("unsafe appdata_subdir")
    if type(completion["recursive"]) is not bool:
        raise ValueError("recursive must be a boolean")
    stable=completion["stable_seconds"]
    if type(stable) not in (int,float) or not 2<=stable<=30:
        raise ValueError("stable_seconds must be 2..30")
    binary=None
    if mode=="guarded_f64_binary":
        binary=cfg.get("binary_capture")
        expected={"max_samples_per_event","max_events","max_total_bytes",
                  "scratch_output_offset","fallback_input_reg"}
        if not isinstance(binary,dict) or set(binary)!=expected:
            raise ValueError("binary_capture needs all five declared fields")
        ns=integer(binary["max_samples_per_event"],"max_samples_per_event",1,32)
        cap=integer(binary["max_total_bytes"],"max_total_bytes",8,256)
        if binary["max_events"] != 1 or type(binary["max_events"]) is not int:
            raise ValueError("only one binary callback allowed")
        if cap%8 or ns*8>cap:
            raise ValueError("binary count exceeds byte budget")
        scratch=integer(binary["scratch_output_offset"],"scratch_output_offset",0,4096)
        if scratch%8 or binary["fallback_input_reg"] not in regs:
            raise ValueError("invalid binary pointer provenance")
    elif "binary_capture" in cfg:
        raise ValueError("metadata mode must never receive binary_capture")
    if set(cfg)-{"module","sha256","mode","image_base","target","completion","sites",
                "lifecycle","binary_capture","trace"}:
        raise ValueError("unknown top-level guarded config key")
    return {
        "module":cfg["module"],"sha256":cfg["sha256"].lower(),
        "mode":mode,"image_base":base,
        **({"binary_capture":binary} if binary is not None else {}),
        **({"trace":dict(trace)} if trace is not None else {}),
        "target":{"process_name_contains":match},
        "completion":dict(completion),
        **({"lifecycle":lifecycle} if lifecycle is not None else {}),
        "sites":[{"name":s["name"],"rva":rv,"required":True,"max_hits":1,
                  "fields":[],"guard":dict(g,owner_offset=off,vtable_rva=vtable,
                                            max_samples=max_samples,
                                            max_observations=max_observations)}],
    }


BINARY_EXTENSION = r"""
          const bcfg = spec.binary_capture;
          const scratchSlot = owner.add(bcfg.scratch_output_offset);
          if (!readable(scratchSlot,Process.pointerSize))
            return reject('scratch slot unreadable');
          const scratch = scratchSlot.readPointer();
          const selected = scratch.isNull() ? c[bcfg.fallback_input_reg] : scratch;
          if (!output.equals(selected))
            return reject('output pointer provenance mismatch');
          const copied = Math.min(count,bcfg.max_samples_per_event);
          const copiedBytes = copied*8;
          if (copied < 1 || copiedBytes > bcfg.max_total_bytes)
            return reject('binary budget exceeded');
          if (!readable(output,copiedBytes))
            return reject('binary prefix unreadable');
          const payload = output.readByteArray(copiedBytes);
          if (payload === null || payload.byteLength !== copiedBytes)
            return reject('prefix copy incomplete');
          metadataSent = true;
          send({kind:'binary_hit',valid:true,site:site.name,observed:observed,
                processor_vtable:vtable.toString(),expected_vtable:expected.toString(),
                output_pointer:output.toString(),output_f64:count,output_bytes:bytes,
                copied_f64:copied,copied_bytes:copiedBytes,
                readable_range:true,provenance:'selected_scratch_or_input',
                pc:loc.toString()},payload);
          return;
"""


def persist_guarded_binary(cfg: dict, state: dict, folder: Path,
                           event: dict, binary: bytes) -> dict:
    """Validate and persist one private binary event; no other files allowed.

    This pure host-side boundary is callable by offline unit tests without Frida.
    It never interprets sample values, and fails closed on any mismatch.
    """
    if cfg.get("mode")!="guarded_f64_binary" or not isinstance(event,dict):
        raise ValueError("binary hit in unapproved capture mode")
    lim=cfg["binary_capture"]
    g=cfg["sites"][0]["guard"]
    n=event.get("copied_bytes")
    nf=event.get("copied_f64")
    total=event.get("output_f64")
    observed=event.get("observed")
    if (event.get("kind")!="binary_hit" or event.get("valid") is not True
            or event.get("site")!=cfg["sites"][0]["name"]
            or event.get("provenance")!="selected_scratch_or_input"
            or event.get("readable_range") is not True
            or type(n) is not int or type(nf) is not int
            or type(total) is not int or type(observed) is not int
            or not 1<=observed<=g["max_observations"]
            or not 1<=nf<=total<=g["max_samples"]
            or event.get("output_bytes")!=total*8
            or n!=nf*8 or not 8<=n<=lim["max_total_bytes"]
            or nf>lim["max_samples_per_event"] or
            state.get("binary_valid",False)):
        raise ValueError("untrusted or out-of-budget binary event")
    buf=bytes(binary)
    if len(buf)!=n:
        raise ValueError("binary payload length mismatch")
    name="block_0001.bin"
    file=folder/name
    with file.open("xb") as f:
        f.write(buf)
        f.flush()
        os.fsync(f.fileno())
    digest=hashlib.sha256(buf).hexdigest()
    state["binary_valid"]=True
    state["binary_file"]=name
    state["binary_bytes"]=n
    return dict(event,file=name,sha256=digest)


def persist_fractional_input(cfg: dict, state: dict, folder: Path,
                             event: dict, binary: bytes) -> dict:
    """Persist two exact 96k->44.1 native RDX input prefixes, max 2072 bytes.

    No audio bytes enter tracked code or reports. Fail closed if processor,
    sequence, rate, size, or callback provenance does not match the descriptor.
    """
    if cfg.get("mode")!="guarded_fractional_io" or "input_probe" not in cfg:
        raise ValueError("unapproved fractional input payload")
    if not isinstance(event,dict):
        raise ValueError("fractional input event is not an object")
    p=cfg["input_probe"]
    step=event.get("step")
    expected={1:p["first_f64"],2:p["second_f64"]}
    current=state.get("input_prefix_events",0)
    n=expected.get(step) if type(step) is int else None
    owner=event.get("processor_pointer")
    if (event.get("kind")!="fractional_input_prefix" or event.get("valid") is not True
            or event.get("site")!=cfg["sites"][0]["name"]
            or step!=current+1 or n is None
            or event.get("input_f64")!=n or event.get("copied_bytes")!=n*8
            or event.get("rate_numerator")!=p["numerator"]
            or event.get("rate_denominator")!=p["denominator"]
            or event.get("provenance")!="fractional_rdx_onenter"
            or type(event.get("observed")) is not int
            or not 1<=event["observed"]<=cfg["sites"][0]["guard"]["max_observations"]
            or not isinstance(owner,str) or not re.fullmatch(r"0x[0-9a-fA-F]+",owner)
            or (step==2 and owner!=state.get("input_probe_processor"))
            or (step==2 and event["observed"]<=state.get("input_probe_first_observed",0))):
        raise ValueError("invalid or misaligned fractional input callback")
    buf=bytes(binary)
    if len(buf)!=n*8 or len(buf)>p["total_max_bytes"]:
        raise ValueError("fractional input callback exceeded byte budget")
    if state.get("input_prefix_total_bytes",0)+len(buf)>p["total_max_bytes"]:
        raise ValueError("fractional input total byte budget exceeded")
    name=f"input_{step:04d}.bin"
    with (folder/name).open("xb") as out:
        out.write(buf)
        out.flush()
        os.fsync(out.fileno())
    digest=hashlib.sha256(buf).hexdigest()
    state["input_prefix_events"]=step
    state["input_prefix_total_bytes"]=state.get("input_prefix_total_bytes",0)+len(buf)
    state["input_probe_processor"]=owner
    if step==1:
        state["input_probe_first_observed"]=event["observed"]
    state["input_prefix_valid"]=(step==2)
    return dict(event,file=name,sha256=digest)


def persist_fractional_output(cfg: dict, state: dict, folder: Path,
                              event: dict, binary: bytes) -> dict:
    """Exactly one guarded 32-f64 48-kHz prefix. Never copy the full stream."""
    if cfg.get("mode")!="guarded_fractional_io" or "output_probe" not in cfg:
        raise ValueError("unauthorized native output payload")
    if not isinstance(event,dict):
        raise ValueError("invalid native output callback")
    p=cfg["output_probe"]
    ptr=event.get("processor_pointer")
    if (event.get("kind")!="fractional_output_prefix" or event.get("valid") is not True
            or event.get("site")!=cfg["sites"][0]["name"]
            or type(event.get("observed")) is not int
            or not 1<=event["observed"]<=cfg["sites"][0]["guard"]["max_observations"]
            or event.get("input_f64")!=p["first_input_f64"]
            or event.get("output_f64")!=p["first_output_f64"]
            or event.get("copied_f64")!=p["output_samples"]
            or event.get("copied_bytes")!=p["total_max_bytes"]
            or event.get("rate_numerator")!=p["numerator"]
            or event.get("rate_denominator")!=p["denominator"]
            or event.get("provenance")!="fractional_r9_ref_onleave"
            or not isinstance(ptr,str) or not re.fullmatch(r"0x[0-9a-fA-F]+",ptr)
            or state.get("output_probe_valid",False)):
        raise ValueError("bad or duplicated native 48k output prefix")
    buf=bytes(binary)
    if len(buf)!=p["total_max_bytes"]:
        raise ValueError("wrong 48k prefix byte count")
    filename="output_0001.bin"
    with (folder/filename).open("xb") as stream:
        stream.write(buf)
        stream.flush()
        os.fsync(stream.fileno())
    digest=hashlib.sha256(buf).hexdigest()
    state["output_probe_valid"]=True
    state["output_probe_bytes"]=len(buf)
    state["output_probe_processor"]=ptr
    return dict(event,file=filename,sha256=digest)


def agent_source(cfg: dict) -> str:
    if cfg["mode"]=="guarded_fractional_io":
        return (IO_AGENT.replace("RATE_PROBE_EXTENSION",
                                 IO_RATE_EXTENSION if cfg.get("rate_probe") else "")
                 .replace("INPUT_PROBE_EXTENSION",
                          IO_INPUT_EXTENSION if cfg.get("input_probe") else "")
                 .replace("OUTPUT_PROBE_ENTER_EXTENSION",
                          IO_OUTPUT_ENTER_EXTENSION if cfg.get("output_probe") else "")
                 .replace("OUTPUT_PROBE_LEAVE_EXTENSION",
                          IO_OUTPUT_LEAVE_EXTENSION if cfg.get("output_probe") else "")
                 .replace("JSON_SPEC",json.dumps(cfg,ensure_ascii=True)))
    return (AGENT.replace("BINARY_EXTENSION_POINT",
                          BINARY_EXTENSION if cfg["mode"]=="guarded_f64_binary" else "")
            .replace("JSON_SPEC",json.dumps(cfg,ensure_ascii=True)))


def snapshot(folder: Path | None, recursive: bool) -> dict:
    if folder is None or not folder.is_dir():
        return {}
    glob = folder.rglob("*.clo") if recursive else folder.glob("*.clo")
    result = {}
    for file in glob:
        try:
            st = file.stat()
            result[str(file.resolve()).casefold()] = (st.st_size, st.st_mtime_ns)
        except OSError:
            continue
    return result


def resolve_completion(args, cfg: dict):
    completion = cfg.get("completion") or {}
    if args.completion_dir:
        path = args.completion_dir
    elif completion.get("path"):
        path = Path(completion["path"])
    elif completion.get("appdata_subdir"):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise RuntimeError("APPDATA absent; pass --completion-dir")
        path = Path(appdata).joinpath(*completion["appdata_subdir"].split("/"))
    else:
        path = None
    if path is not None and not path.is_dir():
        raise FileNotFoundError("CLO watch directory missing: "+str(path))
    return path, bool(completion.get("recursive", True)), float(completion.get("stable_seconds", 3))


def choose_pid(device, args, cfg, report):
    processes = device.enumerate_processes()
    pattern = cfg["target"]["process_name_contains"].casefold()
    if args.pid is not None:
        selected = next((p for p in processes if p.pid == args.pid), None)
        if selected is None:
            raise ValueError("Requested PID not running; it may have restarted")
        if pattern not in selected.name.casefold():
            raise ValueError("PID does not match target.process_name_contains; refusing attach")
        report("TARGET", "Verified", selected.name, "| PID", selected.pid)
        return selected.pid
    found = [p for p in processes if pattern in p.name.casefold()]
    if len(found) != 1:
        raise ValueError("Found "+str(len(found))+" target candidates for "+
                         repr(pattern)+"; open exactly one or pass --pid. "+
                         "Use --list-processes for diagnostics.")
    report("TARGET", "Auto-detected", found[0].name, "| PID", found[0].pid)
    return found[0].pid



def preflight_paths(args, cfg, report):
    """Verify configured Windows EXE and output directory; ZERO attach/hooks.

    Safe to invoke from universal launcher before any native experiment.
    """
    if os.name!="nt" or platform.architecture()[0]!="64bit":
        raise RuntimeError("Path preflight needs Windows x64 Python; use the shared WSL wrapper")
    lifecycle=cfg.get("lifecycle") or {}
    if lifecycle.get("start") in ("fresh","if_missing"):
        exe=Path(lifecycle["executable"])
        if not exe.is_file():
            raise FileNotFoundError(
                "Configured EXE does not exist: "+str(exe)+
                "; set lifecycle.executable to the actual installed app EXE in this stage JSON")
        report("TARGET","Configured EXE exists:",exe)
    else:
        report("TARGET","attach_only mode; no EXE launch requested")
    completion,_,stable=resolve_completion(args,cfg)
    report("CLO","Configured completion directory exists:",completion,
           "| stable interval:",stable,"s")
    report("NOTE","Preflight complete; no process was launched or attached, no hooks installed")
    return 0


def launch_target(device, args, cfg, report, state):
    """Pick an existing PID or SPAWN a fresh app under this session's ownership.

    Frida device.spawn() starts the target suspended. capture() must install
    the module observer and only then device.resume(pid). This also ensures
    cleanup knows exactly which process this invocation owns.
    """
    lifecycle=cfg.get("lifecycle")
    if lifecycle is None or lifecycle["start"]=="attach_only":
        pid=choose_pid(device,args,cfg,report)
        state.update(launched_by_tool=False,target_pid=pid,target_resumed=True)
        return pid,False
    if args.pid is not None:
        raise ValueError("--pid cannot be combined with lifecycle.start="+
                         lifecycle["start"]+"; choose attach_only for an existing PID")
    match=cfg["target"]["process_name_contains"].casefold()
    current=[p for p in device.enumerate_processes() if match in p.name.casefold()]
    if lifecycle["start"]=="fresh" and current:
        raise ValueError("lifecycle.start=fresh requires the application CLOSED first; "
                         "detected "+str(len(current))+" matching process(es). "
                         "Will NOT terminate a pre-existing user process.")
    if lifecycle["start"]=="if_missing" and len(current)==1:
        pid=current[0].pid
        state.update(launched_by_tool=False,target_pid=pid,target_resumed=True)
        report("TARGET","Reusing",current[0].name,"| PID",pid,
               "(user-owned process will NOT be closed)")
        return pid,False
    if lifecycle["start"]=="if_missing" and len(current)>1:
        raise ValueError("Multiple matching running processes; refusing arbitrary choice")
    exe=Path(lifecycle["executable"])
    if not exe.is_file():
        raise FileNotFoundError("Configured Windows application EXE not found: "+str(exe)+
                                "; edit lifecycle.executable in the stage JSON")
    report("TARGET","Launching configured EXE via Frida spawn:",exe)
    pid=device.spawn([str(exe)])
    state.update(launched_by_tool=True,target_pid=pid,target_resumed=False,
                 configured_executable=str(exe))
    report("TARGET","Spawned own Manager PID",pid,
           "(suspended until Frida observer is ready)")
    return pid,True


def process_exists(device,pid):
    try:
        return any(p.pid==pid for p in device.enumerate_processes())
    except Exception:
        return None


def request_graceful_close_windows(pid: int) -> int:
    """Send WM_CLOSE to TOP-LEVEL windows belonging to this exact owned PID.

    No process kill, no taskkill and no window close for unrelated processes.
    """
    import ctypes
    from ctypes import wintypes
    user32=ctypes.WinDLL("user32",use_last_error=True)
    enum_proc=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user32.EnumWindows.argtypes=(enum_proc,wintypes.LPARAM)
    user32.EnumWindows.restype=wintypes.BOOL
    user32.GetWindowThreadProcessId.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype=wintypes.DWORD
    user32.PostMessageW.argtypes=(wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM)
    user32.PostMessageW.restype=wintypes.BOOL
    user32.IsWindow.argtypes=(wintypes.HWND,)
    user32.IsWindow.restype=wintypes.BOOL
    windows=[]
    @enum_proc
    def visit(hwnd,_):
        owner=wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid and user32.IsWindow(hwnd):
            windows.append(hwnd)
        return True
    # Win32 BOOL EnumWindows(WNDENUMPROC lpEnumFunc, LPARAM lParam)
    # The second LPARAM is mandatory (0 here); omitting it caused the
    # Stage48 error: "this function takes 2 arguments (1 given)".
    if not user32.EnumWindows(visit, 0):
        raise OSError("EnumWindows failed")
    sent=0
    for hwnd in windows:
        if user32.PostMessageW(hwnd,0x0010,0,0):  # WM_CLOSE
            sent+=1
    return sent


def close_owned_target(device,pid,state,cfg,report):
    """Best-effort graceful shutdown, strictly limited to a tool-owned PID."""
    lifecycle=cfg.get("lifecycle") or {}
    if not state.get("launched_by_tool") or lifecycle.get("close")!="if_launched":
        state["cleanup_status"]="NOT_OWNED_OR_DISABLED"
        return
    alive=process_exists(device,pid)
    if alive is False:
        state["cleanup_status"]="ALREADY_EXITED"
        report("TARGET","Tool-launched process already exited; nothing to close")
        return
    if state.get("target_resumed") is False:
        # Only a STILL SUSPENDED process that WE created may be force-cleaned
        # because no GUI window exists for a graceful WM_CLOSE.
        try:
            device.kill(pid)
            state["cleanup_status"]="KILLED_OWN_SUSPENDED_TARGET"
            report("WARN","Cancelled own unresumed process",pid)
        except Exception as e:
            state["cleanup_status"]="SUSPENDED_PROCESS_CLEANUP_FAILED"
            state["cleanup_error"]=str(e)[:200]
        return
    try:
        sent=request_graceful_close_windows(pid)
        state["close_messages_sent"]=sent
        report("TARGET","Requested graceful WM_CLOSE for owned PID",pid,
               "| top-level windows:",sent)
        deadline=time.monotonic()+lifecycle["close_timeout_seconds"]
        while time.monotonic()<deadline:
            alive=process_exists(device,pid)
            if alive is False:
                if sent:
                    state["cleanup_status"]="CLOSED_GRACEFULLY"
                    report("TARGET","Owned application exited after WM_CLOSE")
                else:
                    state["cleanup_status"]="EXITED_WITHOUT_WM_CLOSE"
                    report("WARN","Process exited but no WM_CLOSE was sent;",
                           "automatic close NOT confirmed (possibly manual/external)")
                return
            time.sleep(.25)
        state["cleanup_status"]=("STILL_RUNNING_AFTER_WM_CLOSE" if sent
                                 else "STILL_RUNNING_NO_OWNED_WINDOW")
        report("WARN","Owned process",pid,"did not exit within",
               lifecycle["close_timeout_seconds"],"s; WM_CLOSE sent:",sent,
               "; LEFT RUNNING (never force-kill active GUI)")
    except Exception as e:
        state["cleanup_status"]="GRACEFUL_CLOSE_FAILED"
        state["cleanup_error"]=str(e)[:200]
        report("WARN","Unable to close owned process gracefully:",str(e)[:200])


def smoke_lifecycle(args,cfg,report):
    """Managed Windows EXE launch/close smoke: ZERO attach, hooks or conversion.

    Deliberately refuses an already-open Manager so the smoke cannot close a
    user-owned process. Windows UI startup is given a short grace interval.
    """
    if os.name!="nt" or platform.architecture()[0]!="64bit":
        raise RuntimeError("Managed lifecycle smoke requires Windows x64 Python")
    lifecycle=cfg.get("lifecycle") or {}
    if lifecycle.get("start")!="fresh" or lifecycle.get("close")!="if_launched":
        raise ValueError("Lifecycle smoke requires JSON start=fresh, close=if_launched")
    if args.pid is not None:
        raise ValueError("Lifecycle smoke cannot target an existing --pid")
    preflight_paths(args,cfg,report)
    import frida
    device=frida.get_local_device()
    state={}
    pid=None
    try:
        pid,spawned=launch_target(device,args,cfg,report,state)
        if not spawned:
            raise RuntimeError("Lifecycle smoke refused a process it does not own")
        device.resume(pid)
        state["target_resumed"]=True
        report("TARGET","Lifecycle smoke: started owned GUI PID",pid)
        report("NOTE","Waiting 4s for GUI window; NO Frida attach/hook and NO conversion")
        time.sleep(4)
    finally:
        if pid is not None:
            report("TARGET","Lifecycle smoke: requesting graceful close for owned PID",pid)
            close_owned_target(device,pid,state,cfg,report)
    result=state.get("cleanup_status","NOT_RUN")
    report("STATUS","LIFECYCLE_SMOKE_"+result,"| PID:",pid,"| ZERO hooks")
    return 0 if result=="CLOSED_GRACEFULLY" else 3


def list_processes(report, cfg=None):
    if os.name != "nt" or platform.architecture()[0] != "64bit":
        raise RuntimeError("Process discovery requires Windows x64 Python")
    import frida
    processes = frida.get_local_device().enumerate_processes()
    pattern = ((cfg or {}).get("target") or {}).get("process_name_contains", "sonicake").casefold()
    hits = [p for p in processes if pattern in p.name.casefold()]
    report("TARGET", "Frida sees", len(processes), "processes; pattern", repr(pattern))
    for p in sorted(hits, key=lambda x:(x.name.casefold(),x.pid)):
        report("NOTE", p.name, "PID", p.pid)
    report("NOTE", "No process attached; ZERO hooks installed")
    return 0


def reconcile(folder: Path, state: dict):
    """Recover persisted truth even when an exception interrupts capture()."""
    p = folder / "events.jsonl"
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    state["journal_events"] = len(lines)
    trace_returns_in_journal=0
    trace_rejections_in_journal=0
    io_events_in_journal=0
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            state["invalid_journal_lines"] = state.get("invalid_journal_lines",0)+1
            continue
        kind = e.get("kind")
        if kind == "hook_attached" and e.get("hooks_installed") == 1:
            state["ready"] = True
            state["hook_attached"] = True
        elif kind == "fractional_io" and e.get("valid") is True:
            if (type(e.get("input_f64")) is int and type(e.get("output_f64")) is int
                    and 0<=e["input_f64"]<=7000000
                    and 0<=e["output_f64"]<=7000000):
                state["metadata_valid"]=True
                state["hits"]=max(1,state.get("hits",0))
                io_events_in_journal+=1
                state["last_metadata"]=e
        elif kind == "metadata_hit" and e.get("valid") is True:
            state["valid_field_hits"] = max(1,state.get("valid_field_hits",0))
            state["hits"] = max(1,state.get("hits",0))
            state["metadata_valid"] = True
            state["last_metadata"] = e
        elif kind == "binary_hit" and e.get("valid") is True:
            name=e.get("file")
            n=e.get("copied_bytes")
            digest=e.get("sha256")
            if (name=="block_0001.bin" and type(n) is int and 8<=n<=256
                    and n%8==0 and isinstance(digest,str)
                    and re.fullmatch(r"[0-9a-f]{64}",digest)):
                file=folder/name
                try:
                    if (file.stat().st_size==n and
                            hashlib.sha256(file.read_bytes()).hexdigest()==digest):
                        state["metadata_valid"]=True
                        state["binary_valid"]=True
                        state["binary_file"]=name
                        state["binary_bytes"]=n
                        state["last_metadata"]=e
                except OSError:
                    pass
        elif kind == "fractional_input_prefix" and e.get("valid") is True:
            name=e.get("file")
            step=e.get("step")
            n={1:3,2:256}.get(step) if type(step) is int else None
            processor=e.get("processor_pointer")
            if (n is not None and name==f"input_{step:04d}.bin"
                    and e.get("input_f64")==n and e.get("copied_bytes")==n*8
                    and e.get("rate_numerator")==96000
                    and e.get("rate_denominator")==44100
                    and e.get("provenance")=="fractional_rdx_onenter"
                    and type(e.get("observed")) is int
                    and re.fullmatch(r"0x[0-9a-fA-F]+",processor or "")
                    and re.fullmatch(r"[0-9a-f]{64}",e.get("sha256") or "")
                    and step==state.get("input_prefix_events",0)+1
                    and (step==1 or processor==state.get("input_probe_processor"))):
                f=folder/name
                try:
                    if (f.stat().st_size==n*8 and
                            hashlib.sha256(f.read_bytes()).hexdigest()==e["sha256"]):
                        state["input_prefix_events"]=step
                        state["input_prefix_total_bytes"]=state.get("input_prefix_total_bytes",0)+n*8
                        state["input_probe_processor"]=processor
                        state["input_prefix_valid"]=(step==2)
                except OSError:
                    pass
        elif kind == "fractional_output_prefix" and e.get("valid") is True:
            if (e.get("file")=="output_0001.bin"
                    and e.get("input_f64")==6170612 and e.get("output_f64")==3358150
                    and e.get("copied_f64")==32 and e.get("copied_bytes")==256
                    and e.get("rate_numerator")==88200 and e.get("rate_denominator")==48000
                    and e.get("provenance")=="fractional_r9_ref_onleave"
                    and re.fullmatch(r"[0-9a-f]{64}",e.get("sha256") or "")):
                file=folder/"output_0001.bin"
                try:
                    if (file.stat().st_size==256
                            and hashlib.sha256(file.read_bytes()).hexdigest()==e["sha256"]):
                        state["output_probe_valid"]=True
                        state["output_probe_bytes"]=256
                except OSError:
                    pass
        elif kind == "first_rejected_return":
            state["first_rejection"] = e.get("reason")
        elif kind == "trace_return":
            trace_returns_in_journal+=1
        elif kind == "trace_reject":
            trace_rejections_in_journal+=1
        elif kind == "trace_cap_reached":
            state["trace_cap_reached"] = True
    state["trace_returns"]=max(state.get("trace_returns",0),trace_returns_in_journal)
    state["trace_rejections"]=max(state.get("trace_rejections",0),trace_rejections_in_journal)
    if io_events_in_journal:
        state["io_events"]=max(state.get("io_events",0),io_events_in_journal)


def interrupted_status(state: dict) -> str:
    return ("METADATA_OBSERVED_OPERATOR_INTERRUPTED"
            if state.get("metadata_valid") else "OPERATOR_INTERRUPTED")


def self_test(validate_fn):
    """Pure-Python contract plus real Stage48 journal regression; no Frida."""
    import tempfile
    from types import SimpleNamespace

    cfg = validate_fn({
        "module":"test.dll","sha256":"a"*64,
        "mode":"guarded_metadata",
        "target":{"process_name_contains":"test"},
        "completion":{"type":"changed_clo","appdata_subdir":"Test/App","recursive":True,"stable_seconds":3},
        "sites":[{"name":"aftercall","address":"0x1190c",
                  "guard":{"kind":"processor_output","owner_reg":"rbx",
                           "owner_offset":80,"vtable_rva":"0x245170",
                           "output_ref_reg":"r15","count_reg":"rax",
                           "max_samples":4096,"max_observations":256}}]
    })
    js = agent_source(cfg)
    assert js.count("Interceptor.attach(") == 1
    assert "rpc.exports" in js and "Process.attachModuleObserver" in js
    assert ".readByteArray(" not in js and ".readDouble(" not in js
    assert cfg["sites"][0]["guard"]["vtable_rva"] == 0x245170
    class Device:
        def enumerate_processes(self):
            return [SimpleNamespace(name="Test Manager.exe",pid=14000),
                    SimpleNamespace(name="explorer.exe",pid=222)]
    assert choose_pid(Device(),SimpleNamespace(pid=None),cfg,lambda *a:None)==14000
    assert choose_pid(Device(),SimpleNamespace(pid=14000),cfg,lambda *a:None)==14000
    with tempfile.TemporaryDirectory(prefix="frida_guarded_test_") as td:
        d=Path(td)
        events=[
            {"kind":"module_found","base":"0x7ff862660000"},
            {"kind":"hook_attached","hooks_installed":1},
            {"kind":"first_rejected_return","reason":"return count zero or out of bounds"},
            {"kind":"metadata_hit","valid":True,"output_f64":114,"output_bytes":912},
        ]
        (d/"events.jsonl").write_text("".join(json.dumps(e)+"\n" for e in events),encoding="utf-8")
        state={}
        reconcile(d,state)
        assert state["hook_attached"] and state["last_metadata"]["output_f64"]==114
        assert state["journal_events"]==4
        assert interrupted_status(state)=="METADATA_OBSERVED_OPERATOR_INTERRUPTED"
        sub=d/"profile"
        sub.mkdir()
        (sub/"ok.clo").write_bytes(b"fake")
        assert len(snapshot(d,True))==1 and len(snapshot(d,False))==0
    # Config injection must never permit raw JS supplied by arbitrary stage.
    for bad in ({"mode":"guarded_metadata","sites":[{"name":"x","address":"0x1190c",
                   "guard":{"javascript":"unsafe"}}]},
                {"mode":"guarded_metadata","sites":[{"name":"x","address":"0x1190c"}]}):
        try:
            validate_fn({"module":"test.dll","sha256":"a"*64,**bad})
            raise AssertionError("invalid guarded config accepted")
        except (ValueError,KeyError,TypeError):
            pass
    return "guarded metadata offline tests PASS (single hook, legacy journal recovery, auto PID, CLO recurse)"


def finalize_guarded_capture(device,pid,state,cfg,report,script,session):
    """For completed one-shot binary captures, close the OWNED GUI before unload.

    The user's first successful Stage49 run hung in script.unload() until
    Manager was closed manually. This avoids that synchronous unloading call
    while a completed binary capture's target still runs. Metadata-only Stage48
    and unsuccessful/attach-only cases preserve the original teardown order.
    """
    close_first=((cfg.get("mode")=="guarded_f64_binary" and state.get("binary_valid")
                 or cfg.get("mode")=="guarded_fractional_io" and state.get("io_events",0)>0)
                 and state.get("runtime_verified") and state.get("hook_attached")
                 and state.get("completion_verified") and state.get("launched_by_tool")
                 and (cfg.get("lifecycle") or {}).get("close")=="if_launched")
    report("NOTE","Capture loop ended; beginning owned-GUI/Frida cleanup")
    if close_first:
        state["cleanup_order"]="OWNED_GUI_BEFORE_FRIDA"
        report("CLOSE","Verified native evidence + CLO persisted. Requesting WM_CLOSE for owned PID",
               pid,"BEFORE potentially blocking Frida unload")
        close_owned_target(device,pid,state,cfg,report)
        if process_exists(device,pid) is False:
            state["frida_cleanup_status"]="TARGET_EXIT_RELEASED_HOOK"
            report("CLOSE","Owned target exited; Frida hooks released by process exit;",
                   "no synchronous script.unload() required")
            return
        report("WARN","Owned GUI still running; normal Frida teardown may block.",
               "No active process will be force-killed.")
    else:
        state["cleanup_order"]="FRIDA_BEFORE_OWNED_GUI"
    if script is not None:
        try:
            report("NOTE","Calling Frida script.unload()")
            script.unload()
            report("NOTE","Frida script unloaded")
        except Exception as exc:
            state["script_unload_error"]=str(exc)[:250]
            report("WARN","Frida script unload:",str(exc)[:250])
    if session is not None:
        try:
            report("NOTE","Calling Frida session.detach()")
            session.detach()
            report("NOTE","Frida session detached")
        except Exception as exc:
            state["session_detach_error"]=str(exc)[:250]
            report("WARN","Frida session detach:",str(exc)[:250])
    if not close_first:
        report("TARGET","Cleanup phase: closing only owned PID",pid)
        close_owned_target(device,pid,state,cfg,report)


def capture(args, cfg, folder: Path, state: dict, report, sha):
    """Windows-only guarded capture; shared state survives interrupts.

    The caller owns manifest + archive creation. No proprietary media persisted.
    """
    if os.name!="nt" or platform.architecture()[0]!="64bit":
        raise RuntimeError("Guarded capture requires Windows x64 Python")
    import frida
    device=frida.get_local_device()
    # Watch/config validation happens BEFORE spawning the application.
    watch,recursive,stable_seconds=resolve_completion(args,cfg)
    pid,spawned=launch_target(device,args,cfg,report,state)
    baseline=snapshot(watch,recursive)
    report("CLO","Watching",watch,"| baseline files:",len(baseline))
    state.update(pid=pid,runtime_verified=False,ready=False,hits=0,
                 valid_field_hits=0,metadata_valid=False,binary_valid=False,hook_attached=False,
                 hook_errors=0,field_errors=0,site_hits={},
                 first_rejection=None,completion_verified=False,
                 trace_returns=0,trace_rejections=0,trace_cap_reached=False,
                 io_events=0,input_prefix_events=0,input_prefix_total_bytes=0,
                 input_prefix_valid=False,input_probe_processor=None,
                 output_probe_valid=False,output_probe_bytes=0)
    events=folder/"events.jsonl"
    lock=threading.RLock()
    pending=[]
    disconnect=threading.Event()
    session=None
    script=None
    try:
        session=device.attach(pid)
        def on_detach(reason,*unused):
            disconnect.set()
            state["detached_reason"]=str(reason)
        session.on("detached",on_detach)
        script=session.create_script(agent_source(cfg))

        def on_message(msg,binary):
            if binary is not None:
                try:
                    payload=msg.get("payload")
                    if (cfg["mode"]=="guarded_fractional_io"
                            and isinstance(payload,dict)
                            and payload.get("kind")=="fractional_input_prefix"):
                        e=persist_fractional_input(cfg,state,folder,payload,binary)
                    elif (cfg["mode"]=="guarded_fractional_io"
                          and isinstance(payload,dict)
                          and payload.get("kind")=="fractional_output_prefix"):
                        e=persist_fractional_output(cfg,state,folder,payload,binary)
                    else:
                        e=persist_guarded_binary(cfg,state,folder,payload,binary)
                except (OSError,ValueError,TypeError) as exc:
                    e={"kind":"unexpected_binary_payload",
                       "error":"binary rejected: "+str(exc)[:120]}
            elif msg.get("type")=="send":
                e=msg.get("payload",{})
                if not isinstance(e,dict):e={"kind":"invalid_event"}
                elif (cfg["mode"]=="guarded_f64_binary" and e.get("kind") in ("metadata_hit","binary_hit")
                      or cfg["mode"]=="guarded_fractional_io" and e.get("kind") in
                             ("fractional_input_prefix","fractional_output_prefix")):
                    e={"kind":"invalid_event","error":"binary event requires paired bytes"}
            else:
                e={"kind":"frida_error","error":str(msg)[:400]}
            with lock:
                with events.open("a",encoding="utf-8") as f:
                    f.write(json.dumps(e,ensure_ascii=True)+"\n")
                    f.flush()
                kind=e.get("kind")
                if kind=="module_found":pending.append(e)
                elif kind=="hook_attached":
                    state["ready"]=True
                    state["hook_attached"]=True
                elif kind in ("metadata_hit","binary_hit","fractional_io") and e.get("valid") is True:
                    state["metadata_valid"]=True
                    state["valid_field_hits"]+=1
                    state["hits"]+=1
                    state["site_hits"][e["site"]]=1
                    state["last_metadata"]=e
                    if kind=="fractional_io":
                        state["io_events"]+=1
                elif kind=="first_rejected_return":state["first_rejection"]=e.get("reason")
                elif kind in ("arm_error","frida_error","unexpected_binary_payload","invalid_event"):
                    state["hook_errors"]+=1
                elif kind=="observation_limit":state["observation_limit_reached"]=True
                elif kind=="trace_return":state["trace_returns"]+=1
                elif kind=="trace_reject":state["trace_rejections"]+=1
                elif kind=="trace_cap_reached":state["trace_cap_reached"]=True
                elif kind=="io_cap_reached":state["io_cap_reached"]=True
                elif kind=="io_first_reject":state["io_first_rejection"]=e.get("reason")
            if kind=="fractional_output_prefix":
                report("CAPTURE","*** NATIVE 48K OUTPUT SAVED ***",e.get("copied_f64"),
                       "f64 /",e.get("copied_bytes"),"bytes |",
                       e.get("file"),"| SHA256",e.get("sha256"))
            if kind=="fractional_input_prefix":
                report("CAPTURE","*** NATIVE 96K INPUT SAVED ***",e.get("input_f64"),
                       "f64 /",e.get("copied_bytes"),"bytes",
                       "|",e.get("file"),"| SHA256",e.get("sha256"))
            if kind=="hook_attached":
                report("HOOK","Verified single hook:",e.get("site"),"| RVA",hex(e.get("rva",0)))
            elif kind in ("metadata_hit","binary_hit"):
                report("META","Native output:",e.get("output_f64"),"f64 /",
                       e.get("output_bytes"),"bytes",
                       "| observation",e.get("observed"))
                if kind=="binary_hit" and state.get("binary_valid"):
                    report("CAPTURE","*** NATIVE F64 DATA SAVED ***",
                           e.get("copied_f64"),"f64 /",e.get("copied_bytes"),"bytes",
                           "|",e.get("file"))
                    report("CAPTURE","SHA256:",e.get("sha256"))
                    report("READY","BINARY VERIFIED; awaiting stable new/changed CLO")
            elif kind=="fractional_io":
                if cfg.get("rate_probe"):
                    report("IO","input",e.get("input_f64"),"→ output",e.get("output_f64"),
                           "| step factors",e.get("step_numerator"),"/",
                           e.get("step_denominator"),"| call",e.get("observed"))
                else:
                    report("IO","Actual fractional input",e.get("input_f64"),
                           "→ output",e.get("output_f64"),"| call",e.get("observed"))
            elif kind=="io_cap_reached":
                report("IO","Single-hook trace reached fixed 64-observation limit")
            elif kind=="io_first_reject":
                report("NOTE","First guarded fractional entry rejected:",e.get("reason"))
            elif kind=="first_rejected_return":
                report("NOTE","Initial return rejected:",e.get("reason"))
            elif kind=="trace_cap_reached":
                report("TRACE","*** MAX 64 OBSERVATIONS RECORDED ***",
                       "native output counts stored in events.jsonl")
            elif kind in ("arm_error","frida_error"):
                report("ERROR",kind,e.get("error"))

        script.on("message",on_message)
        script.load()
        if spawned:
            # Module observer has already been registered inside suspended
            # process; loaded DLL SHA still gates any future hook attachment.
            device.resume(pid)
            state["target_resumed"]=True
            report("TARGET","Resumed tool-launched PID",pid)
        report("FRIDA","Observer attached (NO hook before loaded module SHA verified)")
        start=time.monotonic()
        heartbeat=start
        next_poll=0.0
        next_pid_check=0.0
        discovered=None
        stable_since=None
        armed=False
        while time.monotonic()-start<args.timeout:
            time.sleep(.2)
            now=time.monotonic()
            with lock:
                pending_module=pending.pop(0) if pending else None
                hooked=state["hook_attached"]
                metadata=state["metadata_valid"]
                errors=state["hook_errors"]
                too_many=state.get("observation_limit_reached",False)
            if disconnect.is_set():
                return ("BLOCKED_TARGET_DETACHED","manager_detached",pid)
            if errors:
                return ("BLOCKED_AGENT_ERROR","frida_error",pid)
            if too_many:
                return ("INCOMPLETE_OBSERVATION_LIMIT","guard_limit",pid)
            if pending_module is not None and not armed:
                armed=True
                path=Path(pending_module["path"])
                if path.name.casefold()!=cfg["module"].casefold():
                    raise RuntimeError("loaded module filename mismatch")
                actual=sha(path)
                if actual!=cfg["sha256"]:
                    raise RuntimeError("Loaded module SHA256 mismatch: refused to install hook")
                with lock:
                    state["runtime_verified"]=True
                    state["module_base"]=pending_module.get("base")
                if not script.exports_sync.arm():
                    raise RuntimeError("Frida arm() refused to install guarded hook")
                report("FRIDA","Loaded DLL SHA verified. ONE",
                       ("bounded-f64" if cfg["mode"]=="guarded_f64_binary"
                        else "fractional-entry I/O metadata" if cfg["mode"]=="guarded_fractional_io"
                        else "metadata-only"),
                       "hook armed.")
                report("NOTE","Perform exactly ONE normal conversion in target app.")
            if now>=next_pid_check:
                next_pid_check=now+3.0
                if not any(p.pid==pid for p in device.enumerate_processes()):
                    return ("BLOCKED_TARGET_EXITED","target_exited",pid)
            if watch is not None and now>=next_poll:
                next_poll=now+1.0
                changed=[(path,meta) for path,meta in snapshot(watch,recursive).items()
                         if meta[0]>0 and baseline.get(path)!=meta]
                if changed:
                    newest=max(changed,key=lambda item:item[1][1])
                    if newest!=discovered:
                        discovered=newest
                        stable_since=now
                        report("CLO","New/changed candidate:",Path(newest[0]).name,
                               "|",newest[1][0],"bytes")
                    elif stable_since is not None and now-stable_since>=stable_seconds:
                        if not state["completion_verified"]:
                            report("CLO","Stable new/changed CLO:",Path(newest[0]).name)
                        state["completion_verified"]=True
                        state["completion_path"]=newest[0]
                        state["completion_size_bytes"]=newest[1][0]
                else:
                    discovered=None
                    stable_since=None
            if now-heartbeat>=15:
                heartbeat=now
                report("WAIT","elapsed",round(now-start),"s | hook",hooked,
                       "| metadata",metadata,"| CLO",state["completion_verified"])
            if (cfg.get("input_probe") and state["completion_verified"] and
                    stable_since is not None and now-stable_since>stable_seconds+6 and
                    not (state.get("input_prefix_valid") and state.get("output_probe_valid"))):
                report("WARN","Stage54 missing bounded native prefix after stable CLO:",
                       "| 96k input",state.get("input_prefix_events",0),"/ 2",
                       "| 48k output",state.get("output_probe_valid",False),
                       "| all available data will be archived")
                return ("INCOMPLETE_REQUIRED_PREFIXES","stable_clo_missing_prefix",pid)
            if (state["runtime_verified"] and hooked and metadata and
                    (cfg["mode"]=="guarded_metadata" or
                     cfg["mode"]=="guarded_fractional_io" and
                        (not cfg.get("input_probe") or state["input_prefix_valid"]) and
                        (not cfg.get("output_probe") or state["output_probe_valid"]) or
                     state["binary_valid"]) and
                    state["completion_verified"] and not errors):
                if cfg["mode"]=="guarded_f64_binary":
                    if cfg.get("trace"):
                        report("TRACE","*** STREAM TRACE VERIFIED ***",
                               "| returns:",state.get("trace_returns",0),
                               "| rejects:",state.get("trace_rejections",0),
                               "| limit hit:",state.get("trace_cap_reached",False))
                    report("PASS","*** NATIVE F64 + STABLE CLO VERIFIED ***",
                           state.get("binary_bytes"),"private sample bytes | CLO",
                           state.get("completion_size_bytes"),"bytes")
                    report("PASS","Bounded native prefix capture complete; NOT numerical parity.")
                if cfg["mode"]=="guarded_fractional_io":
                    if cfg.get("input_probe"):
                        report("PASS","*** NATIVE 96K INPUT + 48K OUTPUT PREFIXES VERIFIED ***",
                               state.get("input_prefix_total_bytes",0),"input bytes,",
                               state.get("output_probe_bytes",0),"output bytes; CLO stable")
                    else:
                        report("PASS","*** NATIVE FRACTIONAL I/O TRACE + STABLE CLO VERIFIED ***",
                               state.get("io_events",0),"input/output pairs; ZERO audio reads")
                status=("METADATA_GUARD_PASS_CLO_STABLE" if cfg["mode"]=="guarded_metadata"
                        else ("FRACTIONAL_PAIRED_PREFIXES_CLO_STABLE" if cfg.get("input_probe")
                              else "FRACTIONAL_IO_TRACE_CLO_STABLE") if cfg["mode"]=="guarded_fractional_io"
                        else "NATIVE_48K_SAMPLES_CAPTURED_CLO_STABLE")
                return (status,"stable_clo_after_guard",pid)
        return (("BINARY_OBSERVED_CLO_UNVERIFIED_TIMEOUT" if cfg["mode"]=="guarded_f64_binary"
                 else "METADATA_OBSERVED_CLO_UNVERIFIED_TIMEOUT")
                if state["metadata_valid"] else "INCOMPLETE_TIMEOUT","timeout",pid)
    finally:
        finalize_guarded_capture(device,pid,state,cfg,report,script,session)
