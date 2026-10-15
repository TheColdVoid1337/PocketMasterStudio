// Stage67: optional browser/worker adapter for the separately verified
// Sonicake-compatible WebAssembly C ABI (Stage66). No side effects on the
// existing NAM->CLO pipeline. The WASM factory and binary are NOT embedded.
// Consumers explicitly load the compiled module then call PMHTKPAWasmAdapter.open.
//
// This adapter does not implement DSP: it owns wasm32 pointers, validates
// inputs, and copies bounded Float64Array blocks across the memory boundary.
// Compiler/source provenance and native numerical parity are checked by
// research/htkpa/native_compat/build_wasm.py and its separate audit.
(function(root,factory){
  if(typeof module==="object"&&module.exports)module.exports=factory();
  else root.PMHTKPAWasmAdapter=factory();
})(typeof self!=="undefined"?self:this,function(){
  "use strict";

  const REVERSE="reverse",FORWARD="forward";
  const MODE=Object.freeze({reverse:1,forward:2});
  const MAX_INPUT=2680,MAX_OUTPUT=8192;
  const ABI_ID="r8brain-v6.5__sonicake-1.5.2__kaiser12.55262798_1.51553897__poly673";
  const textDecoder=(ptr,mem)=>{
    if(!Number.isSafeInteger(ptr)||ptr<=0||ptr>=mem.length)
      throw Error("Invalid HTKPA ABI identity pointer");
    let end=ptr;
    while(end<mem.length&&end-ptr<256&&mem[end])end++;
    if(end===mem.length||end-ptr>=256)
      throw Error("HTKPA ABI identity is not NUL terminated");
    let s="";
    for(let i=ptr;i<end;i++)s+=String.fromCharCode(mem[i]);
    return s;
  };
  function functions(module){
    if(!module||typeof module!=="object")throw TypeError("WASM module is required");
    for(const name of ["_malloc","_free","_htkpa_v1_id","_htkpa_v1_open",
      "_htkpa_v1_min_output_capacity","_htkpa_v1_process",
      "_htkpa_v1_reset","_htkpa_v1_close"]){
      if(typeof module[name]!=="function")throw Error("Missing WASM export "+name);
    }
    if(!(module.HEAPU8 instanceof Uint8Array)||
       !(module.HEAPF64 instanceof Float64Array))
      throw Error("Missing WASM typed memory views");
    const id=textDecoder(module._htkpa_v1_id(),module.HEAPU8);
    if(id!==ABI_ID)throw Error("HTKPA WASM ABI identifier mismatch: "+id);
  }
  function alloc(module,bytes){
    if(!Number.isSafeInteger(bytes)||bytes<=0||bytes>MAX_OUTPUT*8)
      throw RangeError("Unsafe HTKPA WASM allocation");
    const ptr=module._malloc(bytes);
    if(!Number.isSafeInteger(ptr)||ptr<=0||ptr%8!==0)
      throw Error("Invalid HTKPA WASM allocation");
    if(ptr+bytes>module.HEAPU8.byteLength)
      throw Error("HTKPA WASM allocation points outside memory");
    return ptr;
  }
  function open(module,mode){
    functions(module);
    if(mode!==REVERSE&&mode!==FORWARD)
      throw RangeError("Unsupported HTKPA resampling mode");
    const handle=module._htkpa_v1_open(MODE[mode]);
    if(!Number.isSafeInteger(handle)||handle<=0)
      throw Error("Failed to create HTKPA WASM resampler");
    let closed=false;
    const assertOpen=()=>{
      if(closed)throw Error("HTKPA resampler is already closed");
    };
    function process(input){
      assertOpen();
      if(!(input instanceof Float64Array))
        throw TypeError("HTKPA input must be Float64Array");
      if(input.length>MAX_INPUT)
        throw RangeError("HTKPA input block exceeds 2680 samples");
      if(input.some(x=>!Number.isFinite(x)))
        throw RangeError("HTKPA input contains NaN or infinity");
      if(input.length===0)return new Float64Array(0);
      const count=input.length;
      const cap=module._htkpa_v1_min_output_capacity(handle,count);
      if(!Number.isSafeInteger(cap)||cap<0||cap>MAX_OUTPUT)
        throw Error("Invalid HTKPA output capacity");
      let inputPtr=0,outputPtr=0;
      try{
        inputPtr=alloc(module,count*8);
        outputPtr=alloc(module,Math.max(1,cap)*8);
        // Query live heap after allocations: _malloc may grow wasm memory.
        module.HEAPF64.set(input,inputPtr/8);
        const written=module._htkpa_v1_process(
          handle,inputPtr,count,outputPtr,cap);
        if(!Number.isSafeInteger(written)||written<0||written>cap)
          throw Error("HTKPA native resampler returned error "+written);
        // Native process can also grow wasm memory; refresh views again.
        if(outputPtr+written*8>module.HEAPU8.byteLength)
          throw Error("HTKPA output exceeds WASM memory");
        const out=module.HEAPF64.slice(outputPtr/8,outputPtr/8+written);
        if(out.some(x=>!Number.isFinite(x)))
          throw Error("HTKPA returned non-finite output");
        return out;
      }finally{
        if(outputPtr)module._free(outputPtr);
        if(inputPtr)module._free(inputPtr);
      }
    }
    function reset(){
      assertOpen();
      const code=module._htkpa_v1_reset(handle);
      if(code!==0)throw Error("HTKPA resampler reset failed "+code);
    }
    function close(){
      if(closed)return;
      closed=true;
      module._htkpa_v1_close(handle);
    }
    return Object.freeze({mode,process,reset,close,
      get closed(){return closed;}});
  }
  return Object.freeze({ABI_ID,MODES:Object.freeze({REVERSE,FORWARD}),
    MAX_INPUT,MAX_OUTPUT,open});
});