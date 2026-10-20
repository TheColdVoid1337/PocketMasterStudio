#!/usr/bin/env node
'use strict';
// Stage99-only isolated Node runner for a separately compiled SonicMaster
// diagnostic Dart worker. No production converter import, no native vendor DLL.
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {Worker}=require('node:worker_threads');

function getArgs(argv){
 const a={};
 for(let i=2;i<argv.length;i+=2){
  if(i+1>=argv.length||!['--model','--worker-js','--input-f64le','--output-f64le'].includes(argv[i])||a[argv[i]])
   throw Error('Expected unique --model --worker-js --input-f64le --output-f64le');
  a[argv[i]]=argv[i+1];
 }
 for(const k of ['--model','--worker-js','--input-f64le','--output-f64le'])if(!a[k])throw Error('Missing '+k);
 return a;
}
function sha(buf){return crypto.createHash('sha256').update(buf).digest('hex');}
const bootstrap=`
const {parentPort,workerData}=require('node:worker_threads');
globalThis.self=globalThis;
globalThis.postMessage=(data,transfer)=>parentPort.postMessage(data,transfer);
parentPort.on('message',data=>{
  if(typeof globalThis.onmessage!=='function')throw Error('SonicMaster diagnostic worker did not register onmessage');
  globalThis.onmessage({data});
});
require(workerData.workerPath);
`;

async function main(){
 const a=getArgs(process.argv);
 const model=fs.readFileSync(a['--model']);
 if(model.byteLength<16||model.byteLength>32*1024*1024)throw Error('Invalid NAM file length');
 const parsed=JSON.parse(model.toString('utf8'));
 if(!parsed||typeof parsed!=='object'||!parsed.architecture||!parsed.config)throw Error('NAM architecture/config missing');
 const raw=fs.readFileSync(a['--input-f64le']);
 if(raw.byteLength!==8192*8)throw Error('Input must be exactly 8192 mono f64le frames');
 if(path.resolve(a['--input-f64le'])===path.resolve(a['--output-f64le']))throw Error('Input and output paths must differ');
 if(fs.existsSync(a['--output-f64le']))throw Error('Refusing to overwrite output');
 const input=new Float64Array(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength));
 for(const v of input)if(!Number.isFinite(v))throw Error('Nonfinite input');
 const workerPath=path.resolve(a['--worker-js']);
 if(!fs.statSync(workerPath).isFile())throw Error('Diagnostic Dart worker missing');
 const output=await new Promise((resolve,reject)=>{
  const thread=new Worker(bootstrap,{eval:true,workerData:{workerPath}});
  let settled=false;
  const finish=(err,value)=>{
   if(settled)return; settled=true; clearTimeout(timeout); thread.terminate();
   if(err)reject(err);else resolve(value);
  };
  const timeout=setTimeout(()=>finish(Error('SonicMaster diagnostic timeout')),120000);
  thread.on('error',e=>finish(e));
  thread.on('exit',code=>{if(!settled)finish(Error('Worker exited before response: '+code));});
  thread.on('message',data=>{
   if(data?.type==='error')return finish(Error('SonicMaster diagnostic: '+String(data.error).slice(0,250)));
   if(data?.type!=='raw'||!(data.output instanceof Float64Array)||data.output.length!==8192)
    return finish(Error('Malformed SonicMaster diagnostic response'));
   if(Array.from(data.output).some(x=>!Number.isFinite(x)))return finish(Error('Nonfinite SonicMaster output'));
   finish(null,data.output);
  });
  thread.postMessage({type:'raw',namJson:model.toString('utf8'),input},[input.buffer]);
 });
 const out=Buffer.from(output.buffer,output.byteOffset,output.byteLength);
 fs.writeFileSync(a['--output-f64le'],out,{flag:'wx'});
 console.log(JSON.stringify({status:'SONICMASTER_DART_RAW_DIAGNOSTIC_COMPLETED',frames:8192,
  input_sha256:sha(raw),output_sha256:sha(out),fit_executed:false,resampling_executed:false}));
}
main().catch(e=>{console.error('[Stage99 SonicMaster]',e.message||String(e));process.exitCode=2;});
