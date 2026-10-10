'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const P=require('../src/void_clone_protocol.js'),C=require('../src/void_nam_converter.js');
const golden=require('./fixtures/sonicmaster_clone_upload_golden.json');
const NAM=JSON.stringify({architecture:'WaveNet',config:{layers:[]}}),ID='123e4567-e89b-42d3-a456-426614174000';
function sample(){
 const blob=Uint8Array.from(golden.upload_chunks.map(P.fromHex).map(P.unpackChunk).flatMap(x=>Array.from(x.part)));
 const b=new Uint8Array(P.FILE_SIZE);b.set(blob.subarray(74));
 const view=new DataView(b.buffer);
 view.setUint32(4,8840,true);view.setUint32(20,8704,true);view.setUint32(132,2048,true);
 view.setUint16(8,P.crc16(b.subarray(12)),false);return b;
}
test('NAM inspection never fabricates or accepts unsupported architectures',()=>{
 assert.equal(C.inspect(NAM).architecture,'WaveNet');
 assert.throws(()=>C.inspect('bogus'),/valid JSON/);
 assert.throws(()=>C.inspect(JSON.stringify({architecture:'LSTM'})),/unsupported/);
});
test('local DSP response must be 8840-byte CRC validated CLO',async()=>{
 const b=sample(),seen=[];
 const fetchImpl=async(url,opts)=>{seen.push([url,opts.method]);return{ok:true,arrayBuffer:async()=>b.buffer}};
 const actual=await C.start(NAM,{id:ID,fetchImpl}).promise;
 assert.deepEqual(actual,b);
 assert.deepEqual(seen,[['/api/nam/convert','POST']]);
 await assert.rejects(C.start(NAM,{id:ID,fetchImpl:async()=>({ok:true,arrayBuffer:async()=>new Uint8Array(8840).buffer})}).promise,/Not a \.clo/);
});
test('DSP failures report prerequisites without implying upload',async()=>{
 await assert.rejects(C.start(NAM,{id:ID,fetchImpl:async()=>({ok:false,status:503,json:async()=>({error:'Rust not built'})})}).promise,/Rust not built/);
 const check=await C.availability(async()=>({ok:true,json:async()=>({ready:false,requirements:['build','reference DI']})}));
 assert.equal(check.ready,false);assert.equal(check.requirements.length,2);
});
test('cancel invokes server process kill endpoint before browser abort',async()=>{
 const urls=[];
 const fetchImpl=(url,opts)=>{urls.push(url);
  if(url.startsWith('/api/nam/cancel'))return Promise.resolve({ok:true});
  return new Promise((_,reject)=>opts.signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));
 };
 const task=C.start(NAM,{id:ID,fetchImpl});
 await task.cancel();
 await assert.rejects(task.promise,/aborted/);
 assert.deepEqual(urls,['/api/nam/convert','/api/nam/cancel?job='+ID]);
});
