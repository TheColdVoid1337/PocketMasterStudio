// PocketMasterStudio local SonicMaster DSP bridge; no DSP approximations here.
// Runs on loopback tools/studio_server.py via a separate native Rust process.
// No upload happens in this module. Output must pass full CLO validation.
(function(root,factory){
 if(typeof module==="object"&&module.exports)module.exports=factory(require("./void_clone_protocol.js"));
 else root.PMNamConverter=factory(root.PMCloneProtocol);
})(typeof self!=="undefined"?self:this,function(P){
 "use strict";
 const TYPE="application/x-nam", MAX_BYTES=32*1024*1024;
 const ENDPOINT="/api/nam/convert";
 function inspect(source){
  if(typeof source!=="string"||new TextEncoder().encode(source).length>MAX_BYTES)
   throw Error("NAM exceeds 32 MiB or is not text");
  return P.validateNam(source);
 }
 async function availability(fetchImpl=fetch){
  const res=await fetchImpl("/api/nam/availability",{cache:"no-store"});
  if(!res.ok)throw Error("PocketMasterStudio local server unavailable ("+res.status+")");
  return res.json();
 }
 function start(source,{fetchImpl=fetch,id,signal}={}){
  inspect(source);
  if(!id){
   if(!globalThis.crypto?.randomUUID)throw Error("Secure browser UUID generation unavailable");
   id=globalThis.crypto.randomUUID();
  }
  if(!/^[0-9a-fA-F-]{36}$/.test(id))throw Error("Invalid conversion identifier");
  const control=new AbortController();
  if(signal)signal.addEventListener("abort",()=>control.abort(),{once:true});
  let cancelled=false;
  const promise=(async()=>{
   const res=await fetchImpl(ENDPOINT,{
    method:"POST",headers:{"Content-Type":TYPE,"X-Conversion-ID":id},
    body:source,signal:control.signal
   });
   if(!res.ok){
    let detail;
    try{detail=(await res.json()).error;}catch(_){}
    throw Error(detail||"Local NAM conversion failed (HTTP "+res.status+")");
   }
   if(cancelled)throw Error("NAM conversion cancelled");
   const result=new Uint8Array(await res.arrayBuffer());
   P.validateFile(result);
   if(cancelled)throw Error("NAM conversion cancelled");
   return result;
  })();
  async function cancel(){
   if(cancelled)return;
   cancelled=true;
   try{await fetchImpl("/api/nam/cancel?job="+encodeURIComponent(id),{
    method:"POST",headers:{"Content-Type":TYPE},body:""
   });}catch(_){}
   finally{control.abort();}
  }
  return {id,promise,cancel};
 }
 return Object.freeze({MAX_BYTES,inspect,availability,start});
});
