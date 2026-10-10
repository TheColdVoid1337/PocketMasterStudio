#!/usr/bin/env node
'use strict';
// Full offline numerical parity, using the ACTUAL compiled Dart-to-JavaScript
// Web Worker (under node:worker_threads) and original SonicMaster reference DI.
// No Rust, Dart, browser, network, or device is needed to run this verification
// after generated assets are built.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib');
const {Worker}=require('node:worker_threads');
const C=require('../../src/void_nam_converter.js');
const P=require('../../src/void_clone_protocol.js');
const ROOT=path.join(__dirname,'../..');
const workerPath=path.join(ROOT,'src/assets/nam_dsp_worker.js');
const diPath=path.join(ROOT,'src/assets/nam_reference_di_44100.f32.gz');
const namPath=path.join(ROOT,'tests/fixtures/sonicmaster_ref_input.nam');
const goldenPath=path.join(ROOT,'tests/fixtures/sonicmaster_native_dsp_ref.clo.b64');

const bootstrap=`
const {parentPort,workerData}=require('node:worker_threads');
globalThis.self=globalThis;
globalThis.postMessage=(data,transfer)=>parentPort.postMessage(data,transfer);
parentPort.on('message',data=>{
  if(typeof globalThis.onmessage!=='function')
    throw Error('dart2js DSP did not install a worker message handler');
  globalThis.onmessage({data});
});
require(workerData.workerPath);
`;
function createWorker(){
 const thread=new Worker(bootstrap,{eval:true,workerData:{workerPath}});
 let handler=null,errorHandler=null,messageErrorHandler=null;
 thread.on('message',data=>handler?.({data}));
 thread.on('error',e=>errorHandler?.(e));
 thread.on('messageerror',e=>messageErrorHandler?.(e));
 return {
   postMessage:(data,transfer)=>thread.postMessage(data,transfer),
   terminate:()=>thread.terminate(),
   set onmessage(fn){handler=fn},
   set onerror(fn){errorHandler=fn},
   set onmessageerror(fn){messageErrorHandler=fn},
 };
}
async function main(){
 if(!fs.existsSync(workerPath)||!fs.existsSync(diPath))
   throw Error('Missing bundled JS DSP/DI; compile in GitHub Actions first.');
 const input=fs.readFileSync(namPath,'utf8');
 if(!fs.existsSync(goldenPath))throw Error('Missing pinned native DSP golden, generated from the same NAM/DI');
 const reference=Buffer.from(fs.readFileSync(goldenPath,'utf8'),'base64');
 P.validateFile(reference);
 const raw=zlib.gunzipSync(fs.readFileSync(diPath));
 if(raw.length!==12348000)throw Error('Pinned reference DI has incorrect length');
 const di=new Float32Array(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.length));
 console.log('DSP baseline: independent native SonicMaster Rust fitting of SAME NAM/DI (not official vendor CLO)');
 const started=Date.now(),progress=[];
 const task=C.start(input,{
   workerFactory:createWorker,
   assetOverride:{workerJs:'test'.repeat(300),diGzipBase64:'test'.repeat(300)},
   diOverride:di,
   onProgress:message=>{
     if(message.stage==='probe-done'||message.stage==='fit'){
       progress.push(message.stage);
       console.log('Progress:',message.stage,message.done||'',message.level||'');
     }
   },
 });
 const generated=Buffer.from(await task.promise);
 P.validateFile(generated);
 const actual=new DataView(generated.buffer,generated.byteOffset,generated.byteLength);
 const expected=new DataView(reference.buffer,reference.byteOffset,reference.byteLength);
 const sections=[['gains',104,4],['pre FIR',136,128],['post FIR',648,2048]];
 let maxRelative=0,maxAbsolute=0,different=0;
 for(const [name,offset,count] of sections){
   let localMax=0;
   for(let i=0;i<count;i++){
     const a=actual.getFloat32(offset+4*i,true),b=expected.getFloat32(offset+4*i,true);
     const delta=Math.abs(a-b),limit=1e-5+Math.abs(b)*1e-4;
     maxAbsolute=Math.max(maxAbsolute,delta);
     maxRelative=Math.max(maxRelative,delta/(Math.abs(b)+1e-8));
     if(delta>limit){different++;if(localMax<delta)localMax=delta}
   }
   console.log(name,'mismatched above threshold:',localMax?localMax:'none');
 }
 if(progress.filter(s=>s==='probe-done').length!==5)throw Error('Not all probe levels ran');
 if(!progress.includes('fit'))throw Error('No Wiener fitting stage');
 if(different)throw Error('Numerical mismatch against same-input SonicMaster Rust golden ('+different+' coefficients)');
 for(let i=64;i<104;i++)if(reference[i]!==generated[i])
   throw Error('DC-blocker mismatch with SonicMaster golden');
 console.log('PASS: 2180 float32 DSP coefficients, VTSI layout, CRC16 and fixed biquad; elapsed',
   ((Date.now()-started)/1000).toFixed(1)+'s; max abs delta',maxAbsolute,'max relative',maxRelative);
}
main().catch(error=>{console.error('FAILED:',error.stack||error);process.exitCode=1});
