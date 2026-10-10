// PocketMasterStudio browser-only NAM conversion. All inference and fitting execute
// in dedicated Web Workers containing SonicMaster's MIT-licensed Dart-to-JS DSP.
// No Rust process, Python DSP endpoint, network fetch, or physical pedal I/O.
(function(root,factory){
  if(typeof module==="object"&&module.exports)
    module.exports=factory(require("./void_clone_protocol.js"));
  else root.PMNamConverter=factory(root.PMCloneProtocol);
})(typeof self!=="undefined"?self:this,function(P){
 "use strict";
 const MAX_BYTES=32*1024*1024,DI_BYTES=12348000;
 const LEVELS=Object.freeze([0.1,0.03,0.01,0.003,1.0]);
 const BIQUAD=Object.freeze([
   0.9963043928146362,-1.9926087856292725,0.9963043928146362,
   -1.9925950765609741,0.9926224946975708
 ]);
 function inspect(source){
   if(typeof source!=="string"||new TextEncoder().encode(source).length>MAX_BYTES)
     throw Error("NAM exceeds 32 MiB or is not text");
   return P.validateNam(source);
 }
 function assets(){
   return typeof window!=="undefined"&&window.PMNamDSPAssets||null;
 }
 function availability(){
   const failures=[];
   if(typeof Worker==="undefined"||typeof Blob==="undefined"||typeof URL==="undefined"||
      typeof URL.createObjectURL!=="function")failures.push("Web Workers / Blob URL not available");
   if(typeof DecompressionStream==="undefined"||typeof atob!=="function")
     failures.push("Browser gzip decompression not available");
   const bundle=assets();
   if(!bundle||typeof bundle.workerJs!=="string"||bundle.workerJs.length<1000||
      typeof bundle.diGzipBase64!=="string"||bundle.diGzipBase64.length<1000)
     failures.push("Compiled DSP and reference DI missing from standalone HTML");
   return Promise.resolve({ready:failures.length===0,backend:"SonicMaster DSP (offline Web Workers)",
     requirements:failures});
 }
 function decodeBase64(str){
   const decoded=atob(str);
   const out=new Uint8Array(decoded.length);
   for(let i=0;i<decoded.length;i++)out[i]=decoded.charCodeAt(i);
   return out;
 }
 async function loadDi(bundle){
   const compressed=decodeBase64(bundle.diGzipBase64);
   const unpack=new Blob([compressed]).stream().pipeThrough(new DecompressionStream("gzip"));
   const buffer=await new Response(unpack).arrayBuffer();
   if(buffer.byteLength!==DI_BYTES)throw Error("SonicMaster reference DI length mismatch");
   if(new Uint8Array(new Uint16Array([1]).buffer)[0]!==1)
     throw Error("Reference DI requires a little-endian Float32 runtime");
   if(bundle.diSha256&&globalThis.crypto?.subtle){
     const hashed=new Uint8Array(await crypto.subtle.digest("SHA-256",buffer));
     const digest=Array.from(hashed,b=>b.toString(16).padStart(2,"0")).join("");
     if(digest!==bundle.diSha256)throw Error("Reference DI SHA-256 mismatch");
   }
   return new Float32Array(buffer);
 }
 function encodeClo(data){
   const a=data?.arrayA,b=data?.arrayB,gains=data?.gains;
   if(!(a instanceof Float32Array)||a.length!==128||
      !(b instanceof Float32Array)||b.length!==2048||
      !(gains instanceof Float32Array)||gains.length!==4)
     throw Error("DSP did not return the required FIR arrays and gains");
   if([...a,...b,...gains].some(x=>!Number.isFinite(x)))
     throw Error("DSP returned a non-finite coefficient");
   const out=new Uint8Array(P.FILE_SIZE),dv=new DataView(out.buffer);
   out.set([0x56,0x54,0x53,0x49],0);
   dv.setUint32(4,P.FILE_SIZE,true);
   dv.setUint32(20,8704,true);
   dv.setFloat64(24,1,true);
   for(let i=0;i<BIQUAD.length;i++)dv.setFloat64(64+i*8,BIQUAD[i],true);
   for(let i=0;i<4;i++)dv.setFloat32(104+i*4,gains[i],true);
   dv.setUint32(124,128,true);dv.setUint32(128,128,true);
   dv.setUint32(132,2048,true);
   for(let i=0;i<128;i++)dv.setFloat32(136+i*4,a[i],true);
   for(let i=0;i<2048;i++)dv.setFloat32(648+i*4,b[i],true);
   dv.setUint16(8,P.crc16(out.subarray(12)),false);
   P.validateFile(out);
   return out;
 }
 function start(source,{onProgress=()=>{},workerFactory=null,assetOverride=null,diOverride=null}={}){
   inspect(source);
   let cancelled=false,settled=false,terminate=()=>{};
   let rejectJob=()=>{};
   const promise=new Promise(async(resolve,reject)=>{
     rejectJob=reject;
     const workers=[];
     let blobUrl=null;
     const cleanup=()=>{
       for(const w of workers){try{w.terminate()}catch(_){}}
       workers.length=0;
       if(blobUrl){URL.revokeObjectURL(blobUrl);blobUrl=null}
     };
     terminate=cleanup;
     const succeed=value=>{
       if(settled)return;
       settled=true;cleanup();resolve(value);
     };
     const fail=error=>{
       if(settled)return;
       settled=true;cleanup();reject(error instanceof Error?error:Error(String(error)));
     };
     try{
       if(cancelled)throw Error("NAM conversion cancelled");
       const current=await availability();
       if(!current.ready&&!assetOverride&&!workerFactory)
         throw Error(current.requirements.join("; "));
       if(cancelled)throw Error("NAM conversion cancelled");
       const bundle=assetOverride||assets();
       const di=diOverride||await loadDi(bundle);
       if(cancelled)throw Error("NAM conversion cancelled");
       if(!(di instanceof Float32Array)||di.byteLength!==DI_BYTES)
         throw Error("Invalid SonicMaster reference DI");
       onProgress({stage:"ready",done:0,total:LEVELS.length});
       const count=Math.max(1,Math.min(LEVELS.length,4,
         typeof navigator!=="undefined"?navigator.hardwareConcurrency||2:2));
       if(!workerFactory)
         blobUrl=URL.createObjectURL(new Blob([bundle.workerJs],{type:"text/javascript"}));
       let next=0,done=0,finishing=false;
       const results=new Array(LEVELS.length);
       const assignment=new Map();
       const requestNext=w=>{
         if(cancelled||settled||finishing)return;
         if(next>=LEVELS.length)return;
         const index=next++;
         assignment.set(w,index);
         w.postMessage({type:"probe",namJson:source,di,level:LEVELS[index]});
         onProgress({stage:"probe",level:LEVELS[index],done,total:LEVELS.length});
       };
       const receive=(w,event)=>{
         if(cancelled||settled)return;
         try{
           const message=event.data;
           if(message?.type==="error")throw Error("SonicMaster DSP: "+message.error);
           if(message?.type==="probe"){
             const i=assignment.get(w);
             if(i===undefined||message.level!==LEVELS[i]||
               !(message.response instanceof Float64Array)||message.response.length<1000)
               throw Error("Malformed or mismatched DSP probe result");
             assignment.delete(w);results[i]={level:LEVELS[i],response:message.response};
             done++;
             onProgress({stage:"probe-done",level:LEVELS[i],done,total:LEVELS.length});
             if(done===LEVELS.length){
               finishing=true;onProgress({stage:"fit",done,total:LEVELS.length});
               const transfer=results.map(v=>v.response.buffer);
               w.postMessage({type:"finish",namJson:source,di,responses:results},transfer);
             }else requestNext(w);
           }else if(message?.type==="finish"){
             if(!finishing)throw Error("Unexpected DSP fit result");
             succeed(encodeClo(message));
           }else throw Error("Unknown DSP worker response");
         }catch(err){fail(err)}
       };
       for(let i=0;i<count;i++){
         const worker=workerFactory?workerFactory(i):new Worker(blobUrl);
         if(!worker||typeof worker.postMessage!=="function"||typeof worker.terminate!=="function")
           throw Error("Invalid DSP worker");
         workers.push(worker);
         worker.onmessage=evt=>receive(worker,evt);
         worker.onerror=evt=>fail(Error("DSP worker failed: "+(evt.message||"unknown")));
         worker.onmessageerror=()=>fail(Error("DSP worker message decode failed"));
       }
       for(const worker of workers)requestNext(worker);
     }catch(err){fail(err)}
   });
   function cancel(){
     if(cancelled||settled)return Promise.resolve();
     cancelled=true;settled=true;terminate();
     rejectJob(Error("NAM conversion cancelled"));
     return Promise.resolve();
   }
   return {promise,cancel};
 }
 return Object.freeze({MAX_BYTES,LEVELS,inspect,availability,start,encodeClo});
});
