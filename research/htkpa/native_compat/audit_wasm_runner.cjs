'use strict';
// Stage68 PRIVATE real-WASM parity runner. The caller provides verified input
// files from existing native evidence. Runs recovered WebAssembly in Node with
// the exact same ABI adapter intended for browser/worker use. No test doubles.
const fs=require('node:fs');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const crypto=require('node:crypto');
const A=require('../../../src/htkpa_wasm_adapter.js');

const sha=buf=>crypto.createHash('sha256').update(buf).digest('hex');
const nativeF64=filename=>{
  const data=fs.readFileSync(filename);
  if(data.byteLength%8!==0)throw Error('invalid f64le input');
  const out=new Float64Array(data.byteLength/8);
  for(let i=0;i<out.length;i++)out[i]=data.readDoubleLE(i*8);
  if([...out].some(x=>!Number.isFinite(x)))
    throw Error('nonfinite private input');
  return out;
};
const encodeF64=values=>{
  const buffer=Buffer.alloc(values.length*8);
  for(let i=0;i<values.length;i++)buffer.writeDoubleLE(values[i],i*8);
  return buffer;
};
function runBlocks(module,mode,blocks){
  const state=A.open(module,mode);
  try{
    const results=[];
    for(const block of blocks){
      const got=state.process(block);
      results.push(encodeF64(got));
    }
    const out=Buffer.concat(results);
    state.reset();
    const again=Buffer.concat(blocks.map(input=>encodeF64(state.process(input))));
    if(!out.equals(again))throw Error('WASM reset did not replay exactly');
    return out;
  }finally{
    state.close();
  }
}
async function main(){
  if(process.argv.length!==9)
    throw Error('usage: node audit_wasm_runner.cjs MODULE_MJS IN3 IN256 IN2680 OUT_DIR REVERSE_SHAPE FORWARD_SHAPE');
  const [modulePath,three,next256,forwardPath,outDir,reverseShape,forwardShape]=
    process.argv.slice(2);
  if(reverseShape!=='3,256' || forwardShape!=='2680')
    throw Error('unsupported real native conversion fixture');
  const absolute=path.resolve(modulePath);
  const imported=await import(pathToFileURL(absolute).href);
  if(typeof imported.default!=='function')
    throw Error('expected Emscripten modularized ES factory default export');
  const module=await imported.default({
    locateFile:filename=>path.join(path.dirname(absolute),filename)
  });
  const a=nativeF64(three), b=nativeF64(next256), f=nativeF64(forwardPath);
  if(a.length!==3 || b.length!==256 || f.length!==2680)
    throw Error('native source geometry mismatch');
  const reference={
    reverse:runBlocks(module,A.MODES.REVERSE,[a,b]),
    forward:runBlocks(module,A.MODES.FORWARD,[f])
  };
  const split={
    reverse:runBlocks(module,A.MODES.REVERSE,[a,b.slice(0,128),b.slice(128)]),
    forward:runBlocks(module,A.MODES.FORWARD,[f.slice(0,1340),f.slice(1340)])
  };
  if(!reference.reverse.equals(split.reverse) ||
     !reference.forward.equals(split.forward))
    throw Error('WASM block partition changed output bits');
  if(reference.reverse.length!==114*8 || reference.forward.length!==1067*8)
    throw Error('WASM generated unexpected output count');
  fs.mkdirSync(outDir,{recursive:true});
  for(const [side,buf] of Object.entries(reference))
    fs.writeFileSync(path.join(outDir,side+'.f64le'),buf);
  console.log(JSON.stringify({
    status:'WASM_NATIVE_COMPAT_GENERATED',
    reverse_f64:114,forward_f64:1067,
    reverse_sha256:sha(reference.reverse),
    forward_sha256:sha(reference.forward),
    split_bit_equal:true,reset_bit_equal:true,
    wasm_abi:A.ABI_ID
  }));
}
main().catch(e=>{console.error('[ERROR]',e.stack||String(e));process.exitCode=2});
