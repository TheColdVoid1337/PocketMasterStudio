'use strict';
// Stage67 Emscripten C-ABI host adapter tests: fake 32-bit WASM memory only.
// These are NOT DSP-equivalence claims. Real parity is Stage66 and future
// independent Emscripten/Stage65 offline wave replay.
const test=require('node:test');
const assert=require('node:assert/strict');
const adapter=require('../src/htkpa_wasm_adapter.js');

function fake({memoryBytes=512,failProcess=false,growOnProcess=false}={}){
  let memory=new ArrayBuffer(memoryBytes),next=256;
  const handlers=new Map(),closed=[];
  let closeCount=0,freeCount=0,resetCount=0;
  const m={};
  function grow(required){
    if(required<=memory.byteLength)return;
    let newLength=memory.byteLength;
    while(newLength<required)newLength*=2;
    const fresh=new ArrayBuffer(newLength);
    new Uint8Array(fresh).set(new Uint8Array(memory));
    memory=fresh;
    m.HEAPU8=new Uint8Array(memory);
    m.HEAPF64=new Float64Array(memory);
  }
  grow(1);
  m.HEAPU8=new Uint8Array(memory);
  m.HEAPF64=new Float64Array(memory);
  const text=adapter.ABI_ID;
  for(let i=0;i<text.length;i++)m.HEAPU8[8+i]=text.charCodeAt(i);
  m.HEAPU8[8+text.length]=0;
  m._htkpa_v1_id=()=>8;
  m._malloc=bytes=>{
    const ptr=Math.ceil(next/8)*8;
    next=ptr+bytes;
    grow(next);
    return ptr;
  };
  m._free=ptr=>{
    assert.ok(ptr>0);
    freeCount++;
  };
  m._htkpa_v1_open=mode=>{
    const handle=100+mode;
    handlers.set(handle,{mode,position:0});
    return handle;
  };
  m._htkpa_v1_close=handle=>{
    assert.ok(handlers.has(handle));
    closed.push(handle);
    handlers.delete(handle);
    closeCount++;
  };
  m._htkpa_v1_min_output_capacity=(handle,n)=>{
    assert.ok(handlers.has(handle));
    return n+3;
  };
  m._htkpa_v1_process=(handle,inPtr,n,outPtr,cap)=>{
    const h=handlers.get(handle);
    if(failProcess)return -3;
    const input=m.HEAPF64.slice(inPtr/8,inPtr/8+n);
    if(growOnProcess)grow(memory.byteLength*2);
    if(cap<n)throw Error('mock missing output memory');
    for(let i=0;i<n;i++)
      m.HEAPF64[outPtr/8+i]=(input[i]+h.position+i)*h.mode;
    h.position+=n;
    return n;
  };
  m._htkpa_v1_reset=handle=>{
    handlers.get(handle).position=0;resetCount++;
    return 0;
  };
  return {module:m, stats:()=>({freeCount,closeCount,resetCount,
    bytes:memory.byteLength,openHandles:handlers.size,closed})};
}

test('Stage67 ABI identifier and explicit two-mode contracts',()=>{
  assert.equal(adapter.MAX_INPUT,2680);
  assert.equal(adapter.MAX_OUTPUT,8192);
  assert.equal(adapter.MODES.REVERSE,'reverse');
  assert.equal(adapter.MODES.FORWARD,'forward');
  assert.match(adapter.ABI_ID,/poly673/);
  const {module}=fake();
  assert.throws(()=>adapter.open({},'reverse'),/Missing WASM export/);
  assert.throws(()=>adapter.open(module,'44100'),/Unsupported/);
  const tampered=fake().module;
  tampered.HEAPU8[8]=0;
  assert.throws(()=>adapter.open(tampered,'forward'),/identifier mismatch/);
});

test('Stage67 stream processes separate bounded Float64 blocks without stale views',()=>{
  const {module,stats}=fake({memoryBytes:512,growOnProcess:true});
  const worker=adapter.open(module,'reverse');
  const first=worker.process(new Float64Array([0.25,0.5,0.75]));
  assert.ok(first instanceof Float64Array);
  assert.deepEqual([...first],[0.25,1.5,2.75]);
  const second=worker.process(new Float64Array([1,2]));
  assert.deepEqual([...second],[4,6]);
  assert.ok(stats().bytes>512);
  assert.equal(stats().freeCount,4);
  worker.reset();
  assert.deepEqual([...worker.process(new Float64Array([0.25,0.5,0.75]))],
                   [...first]);
  assert.equal(stats().resetCount,1);
  worker.close();
  worker.close();
  assert.equal(stats().closeCount,1);
  assert.equal(stats().openHandles,0);
  assert.equal(worker.closed,true);
  assert.throws(()=>worker.process(new Float64Array([1])),/already closed/);
  assert.throws(()=>worker.reset(),/already closed/);
});

test('Stage67 forward mode keeps independent state and returns copied values',()=>{
  const {module,stats}=fake();
  const reverse=adapter.open(module,'reverse');
  const forward=adapter.open(module,'forward');
  const input=new Float64Array([0.1,0.2]);
  const a=forward.process(input);
  assert.deepEqual([...a],[0.2,2.4]);
  assert.deepEqual([...reverse.process(input)],[0.1,1.2]);
  assert.equal(a.length,2);
  input[0]=999;
  assert.equal(a[0],0.2);
  reverse.close();forward.close();
  assert.equal(stats().openHandles,0);
});

test('Stage67 rejects NaN/infinity, wrong array type, input >2680 and freed handles',()=>{
  const {module,stats}=fake();
  const obj=adapter.open(module,'forward');
  assert.throws(()=>obj.process([1,2]),/Float64Array/);
  assert.throws(()=>obj.process(new Float32Array([1,2])),/Float64Array/);
  assert.throws(()=>obj.process(new Float64Array(2681)),/2680/);
  assert.throws(()=>obj.process(new Float64Array([NaN])),/NaN/);
  assert.throws(()=>obj.process(new Float64Array([Infinity])),/NaN/);
  assert.equal(obj.process(new Float64Array(0)).length,0);
  assert.equal(stats().freeCount,0);
  obj.close();
});

test('Stage67 frees both wasm input/output allocations if native process fails',()=>{
  const {module,stats}=fake({failProcess:true});
  const obj=adapter.open(module,'reverse');
  assert.throws(()=>obj.process(new Float64Array([1,2,3])),/returned error -3/);
  assert.equal(stats().freeCount,2);
  obj.close();
});

test('Stage67 works for maximum documented block with memory growth',()=>{
  const {module,stats}=fake({memoryBytes:1024});
  const obj=adapter.open(module,'forward');
  const values=new Float64Array(2680).fill(0.125);
  const output=obj.process(values);
  assert.equal(output.length,2680);
  assert.equal(output[0],0.25);
  assert.equal(output[2679],(2679.125)*2);
  assert.ok(stats().bytes>=2680*8*2);
  obj.close();
});
