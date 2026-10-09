'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const VoidPolicy=require('../src/void_policy.js');
const Build=require('../src/pmbuild.js');
const Writer=require('../tools/native_prst_patch.js');
const fs=require('node:fs');
const donor=fs.readFileSync(path.resolve(__dirname,'../templates/pocket_master_clone_reference.prst'));
const catalog=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../catalog/effects.json'),'utf8'));
const fxNative=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../catalog/fx_native.json'),'utf8'));
const clone=x=>JSON.parse(JSON.stringify(x));
const mod={enabled:true,effect:'BritGN 4x12',parameters:{Vol:85}};
const preset=(amp)=>({version:'1.0',ampMode:'Normal',presetName:'POLICYTEST',
 presetVolume:100,modules:{
 AMP:{enabled:true,effect:amp,parameters:{}},IR:clone(mod),
 NR:{enabled:false,effect:'Gate',parameters:{THRE:20}}
 },signalChain:['NR','FX1','DRV','AMP','IR','EQ','FX2','DLY','RVB']});
const unpack=(r)=>r.files['Unit.json'].presets[0];
test('full-rig allowlist includes only verified specific capture, never DI/head labels',()=>{
 assert.deepEqual(Build.NAM_CAPTURES,['AC30 May']);
 for(const x of ['JCM800','Plexi','TwinCln','SoloSLO','unknown'])
   assert.equal(VoidPolicy.isFullRig(x),false,x);
 assert.equal(VoidPolicy.isFullRig('AC30 May'),true);
});
test('NAM conversion uses verified full-rig, IR disabled in JSON',()=>{
 const doc={type:'PocketMasterBatch',version:'1.0',artist:'Unit',presets:[preset('Voks 30TB')]};
 const original=clone(doc);
 const result=unpack(Build.buildNam({'Unit.json':doc}));
 assert.equal(result.ampMode,'Clone');
 assert.equal(result.modules.Clone.effect,'AC30 May');
 assert.equal(result.modules.IR.enabled,false);
 assert.deepEqual(doc,original,'builder may not mutate source');
});
test('unsafe NAM and Mixed modes fall back to modeled rather than bad full-rig substitution',()=>{
 for(const amp of ['Brit 800','Brit 50JP','Dark Twin','Sol 100 LD','A BassVT']){
  const doc={type:'PocketMasterBatch',version:'1.0',artist:'Unit',presets:[preset(amp)]};
  for(const build of [Build.buildNam,Build.buildMixed]){
    const result=unpack(build({'Unit.json':doc}));
    assert.equal(result.ampMode,'Normal',amp);
    assert.equal(result.modules.IR.enabled,true,amp);
    assert.equal(result.modules.AMP.effect,amp);
    assert.equal(result.modules.Clone,undefined);
  }
 }
});
test('legacy non-full-rig override is ignored instead of leaking unsafe Clone',()=>{
 const doc={type:'PocketMasterBatch',version:'1.0',artist:'Unit',presets:[preset('Brit 800')]};
 const override={'Unit|POLICYTEST':{ampMode:'Clone',modules:{
  Clone:{enabled:true,effect:'JCM800',parameters:{Gain:50}},IR:{...mod,enabled:true}
 }}};
 const result=Build.buildNam({'Unit.json':doc},override);
 assert.equal(unpack(result).ampMode,'Normal');
 assert.ok(result.unknown.some(s=>s.includes('blocked non-full-rig override')));
});
test('verified Clone override is normalized to IR OFF even if user enabled it',()=>{
 const doc={type:'PocketMasterBatch',version:'1.0',artist:'Unit',presets:[preset('Brit 800')]};
 const override={'Unit|POLICYTEST':{ampMode:'Clone',modules:{
  Clone:{enabled:true,effect:'AC30 May',parameters:{Gain:50}},IR:{...mod,enabled:true}
 }}};
 const result=unpack(Build.buildNam({'Unit.json':doc},override));
 assert.equal(result.ampMode,'Clone');
 assert.equal(result.modules.IR.enabled,false);
});
test('binary writer rejects explicit Clone+IR ON; automatically clears inherited Clone IR donor bit',()=>{
 assert.throws(()=>Writer.write(donor,{enabled:{Clone:true,IR:true}},{catalog,fxNative}),/IR cannot be enabled with Clone/);
 const modified=Uint8Array.from(donor),view=new DataView(modified.buffer);
 view.setUint32(117,view.getUint32(117,true)|0x10,true);
 const Slots=require('../tools/prst_clone_slots.js');
 modified[20]=Slots.crc8(modified.subarray(21));
 const bytes=Writer.write(modified,{enabled:{Clone:true}},{catalog,fxNative});
 assert.equal(new DataView(bytes.buffer).getUint32(117,true)&0x10,0);
 assert.equal(Slots.crc8(bytes.subarray(21)),bytes[20]);
});
