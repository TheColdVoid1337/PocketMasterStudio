'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const P=require('../src/void_clone_protocol.js');
const C=require('../src/void_nam_converter.js');
const NAM=JSON.stringify({architecture:'WaveNet',config:{layers:[]}});

function syntheticArrays(){
 return {arrayA:new Float32Array(128).fill(0.1),
  arrayB:new Float32Array(2048).fill(0.01),
  gains:new Float32Array([0.8,0.75,1.1,1.2])};
}
function fakeWorkerFactory({stall=false,wrong=false}={}){
 const made=[];
 const create=()=>{
  const worker={terminated:false,onmessage:null,postMessage(req){
   if(stall)return;
   queueMicrotask(()=>{
    if(worker.terminated)return;
    if(req.type==='probe'){
     worker.onmessage({data:{type:'probe',level:wrong?-100:req.level,response:new Float64Array(1024)}});
    }else if(req.type==='finish'){
     worker.onmessage({data:{type:'finish',...syntheticArrays()}});
    }
   });
  },terminate(){this.terminated=true}};
  made.push(worker);
  return worker;
 };
 return {create,made};
}
const DI=new Float32Array(12348000/4);
const ASSET={workerJs:'w'.repeat(1001),diGzipBase64:'g'.repeat(1001)};

test('JS-only NAM validation rejects incompatible architectures',()=>{
 assert.equal(C.inspect(NAM).architecture,'WaveNet');
 assert.throws(()=>C.inspect('bad json'),/valid JSON/);
 assert.throws(()=>C.inspect(JSON.stringify({architecture:'LSTM'})),/unsupported/);
});
test('JS CLO writer produces native VTSI file, verified gains and CRC',()=>{
 const b=C.encodeClo(syntheticArrays()),v=new DataView(b.buffer);
 assert.equal(P.validateFile(b).bytesLength,8840);
 assert.equal(v.getUint32(4,true),8840);
 assert.equal(v.getUint32(132,true),2048);
 assert.ok(Math.abs(v.getFloat32(104,true)-0.8)<1e-6);
 const a=syntheticArrays();a.arrayA[0]=NaN;
 assert.throws(()=>C.encodeClo(a),/non-finite/);
});
test('5 JS Web Worker probe levels feed fitting without HTTP',async()=>{
 const fake=fakeWorkerFactory(),events=[];
 const op=C.start(NAM,{diOverride:DI,assetOverride:ASSET,
    workerFactory:fake.create,onProgress:e=>events.push(e.stage)});
 const b=await op.promise;
 assert.equal(P.validateFile(b).bytesLength,8840);
 assert.equal(events.filter(x=>x==='probe-done').length,5);
 assert.ok(events.includes('fit'));
 assert.ok(fake.made.length>=1 && fake.made.length<=4);
 assert.ok(fake.made.every(w=>w.terminated));
});
test('malformed worker output aborts without generating a pedal upload',async()=>{
 const fake=fakeWorkerFactory({wrong:true});
 await assert.rejects(()=>C.start(NAM,{diOverride:DI,assetOverride:ASSET,
   workerFactory:fake.create}).promise,/mismatched/);
 assert.ok(fake.made.every(w=>w.terminated));
});
test('cancel terminates JS workers and rejects the operation',async()=>{
 const fake=fakeWorkerFactory({stall:true});
 const op=C.start(NAM,{diOverride:DI,assetOverride:ASSET,workerFactory:fake.create});
 await new Promise(resolve=>setImmediate(resolve));
 await op.cancel();
 await assert.rejects(op.promise,/cancelled/);
 assert.ok(fake.made.every(w=>w.terminated));
});
test('no localhost conversion URL appears in the JS worker implementation',()=>{
 const fs=require('node:fs'),path=require('node:path');
 const file=fs.readFileSync(path.join(__dirname,'../src/void_nam_converter.js'),'utf8');
 assert.doesNotMatch(file,/\/api\/nam\/|application\/x-nam|NAM_BINARY/);
});
