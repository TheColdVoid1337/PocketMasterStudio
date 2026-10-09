'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const convert=require('../tools/sonicmaster_to_prst.js');
const slots=require('../tools/prst_clone_slots.js');
const writer=require('../tools/native_prst_patch.js');
const repo=path.resolve(__dirname,'..');
const donor=fs.readFileSync(path.join(repo,'templates/pocket_master_reference.prst'));
const catalog=JSON.parse(fs.readFileSync(path.join(repo,'catalog/effects.json')));
const fxNative=JSON.parse(fs.readFileSync(path.join(repo,'catalog/fx_native.json')));
const namSlots={'AC30 May':1,JCM800:2,Plexi:3,TwinCln:4,SoloSLO:5};
const chain=['NR','FX1','DRV','AMP','IR','EQ','FX2','DLY','RVB'];
const fx=(effect,parameters,enabled=true)=>({effect,parameters,enabled});
const a={version:'1.0',presetName:'TESTCLONE',ampMode:'Clone',presetVolume:100,
 modules:{NR:fx('Gate',{THRE:20}),FX1:fx('Boost',{Gain:20,'+3dB':0,Bright:0},false),
 DRV:fx('Scream',{Gain:40,Tone:70,Vol:50}),IR:fx('BritGN 4x12',{Vol:85}),
 EQ:fx('GT EQ 1',{'125Hz':0,'400Hz':2,'800Hz':6,'1.6kHz':7,'4kHz':-3,Vol:100}),
 FX2:fx('Phaser',{Rate:0.5}),DLY:fx('Analog',{Mix:19,Time:400,'F.Back':32}),
 RVB:fx('Room',{Mix:10,Decay:40}),Clone:fx('JCM800',{Gain:50,Vol:100,Bass:50,Middle:50,Treble:50})},signalChain:chain};
const opts={catalog,fxNative,namSlots};
function decoded(n){const v=new DataView(n.buffer,n.byteOffset,n.byteLength);return {name:String.fromCharCode(...n.subarray(25,41)).split('\0')[0],volume:v.getUint32(97,true),mask:v.getUint32(117,true),crc:n[20]};}
test('all 5 slots reproduce exactly the real selectors and valid CRC',()=>{
 for(let slot=1;slot<=5;slot++){const map={[a.modules.Clone.effect]:slot};const {bytes}=convert.convert(a,donor,{...opts,namSlots:map});const p=slots.inspect(bytes);
  assert.equal(p.cloneEnabled,true);assert.equal(p.cloneSlot,slot);assert.equal(decoded(bytes).volume,100);
  assert.equal(bytes[175],slot-1);assert.equal(bytes[178],15);assert.equal(decoded(bytes).mask&0x200,0x200);
 }
});
test('preserves original template, names, output levels and exact DSP values',()=>{
 const source=Uint8Array.from(donor);const {bytes}=convert.convert(a,donor,opts);
 assert.deepEqual(source,Uint8Array.from(donor),'source mutated');
 assert.equal(decoded(bytes).name,'TESTCLONE');assert.equal(decoded(bytes).volume,100);
 const v=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
 assert.equal(v.getFloat32(183+9*32+4*1,true),100);
 assert.equal(v.getFloat32(183+5*32+4*4,true),-3);
 assert.equal(v.getFloat32(183+6*32,true),0.5);
 assert.equal(v.getFloat32(183+8*32+4*2,true),40);
 assert.equal(bytes[139+9*4],1);
});
test('requires explicit correct slot map and refuses duplicate names for same slot',()=>{
 assert.throws(()=>convert.convert(a,donor,{...opts,namSlots:{}}),/no assigned slot/);
 assert.throws(()=>convert.convert(a,donor,{...opts,namSlots:{JCM800:8}}),/Invalid physical slot/);
 assert.throws(()=>convert.convert(a,donor,{...opts,namSlots:{JCM800:2,Plexi:2}}),/Multiple NAM names/);
 assert.throws(()=>convert.convert(a,donor,{...opts,namSlots:undefined}),/Provide a name-to-slot/);
});
test('malformed presets and unverified user IR are blocked',()=>{
 const p=structuredClone(a);p.modules.IR.effect='User IR 1';
 assert.throws(()=>convert.convert(p,donor,opts),/User IR native selector/);
 const p2=structuredClone(a);p2.modules.Clone.parameters.Gain=101;
 assert.throws(()=>convert.convert(p2,donor,opts),/above maximum/);
 const p3=structuredClone(a);p3.modules.FX2.parameters.Rate=0.53;
 assert.throws(()=>convert.convert(p3,donor,opts),/invalid step/);
 const p4=structuredClone(a);p4.modules.AMP=fx('Brit 800',{});
 assert.throws(()=>convert.convert(p4,donor,opts),/must not include AMP/);
 const p5=structuredClone(a);p5.modules.Clone.effect='JCM900';
 assert.throws(()=>convert.convert(p5,donor,opts),/no assigned slot/);
});
test('batch length and selection, rejects ambiguous select',()=>{
 const b={type:'PocketMasterBatch',version:'1.0',presets:[a,{...a,presetName:'SECOND',modules:{...a.modules,Clone:{...a.modules.Clone,effect:'Plexi'}}}]};
 const c=convert.collect(b,donor,opts);
 assert.equal(c.length,2);assert.equal(slots.inspect(c[0].bytes).cloneSlot,2);assert.equal(slots.inspect(c[1].bytes).cloneSlot,3);
 assert.equal(convert.collect(b,donor,{...opts,select:'SECOND'}).length,1);
 assert.throws(()=>convert.collect(b,donor,{...opts,select:'missing'}),/exactly one/);
});
test('CLI exports native file, rejects overwrite and no partial output on invalid batch',()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'prst-clone-'));
 try{
  const input=path.join(tmp,'input.json'),map=path.join(tmp,'slots.json'),out=path.join(tmp,'single.prst');
  fs.writeFileSync(input,JSON.stringify(a));fs.writeFileSync(map,JSON.stringify(namSlots));
  const cli=path.resolve(repo,'tools/sonicmaster_to_prst.js');
  const args=[cli,input,'--donor',path.join(repo,'templates/pocket_master_reference.prst'),'--nam-slots',map,'-o',out];
  const good=spawnSync(process.execPath,args,{encoding:'utf8'});
  assert.equal(good.status,0,good.stderr);assert.equal(slots.inspect(fs.readFileSync(out)).cloneSlot,2);
  const again=spawnSync(process.execPath,args,{encoding:'utf8'});
  assert.notEqual(again.status,0);assert.match(again.stderr,/Refusing overwrite/);
  const bad=path.join(tmp,'invalid-batch.json'),outDir=path.join(tmp,'multi');
  fs.writeFileSync(bad,JSON.stringify({type:'PocketMasterBatch',version:'1.0',presets:[a,{...a,presetName:'BAD',modules:{...a.modules,Clone:{...a.modules.Clone,effect:'NOT LOADED'}}}]}));
  const fail=spawnSync(process.execPath,[cli,bad,'--donor',path.join(repo,'templates/pocket_master_reference.prst'),'--nam-slots',map,'--out-dir',outDir],{encoding:'utf8'});
  assert.notEqual(fail.status,0);assert.equal(fs.existsSync(outDir),false);
 }finally{fs.rmSync(tmp,{recursive:true,force:true});}
});
test('native model/signal-chain bytes change but undocumented donor trailing bytes survive',()=>{
 const {bytes}=convert.convert(a,donor,opts);
 assert.equal(bytes.length,515);assert.equal(bytes[514],donor[514]);
 assert.deepEqual([...bytes.subarray(125,135)],[0,1,2,3,4,5,6,7,8,9]);
});

test('preserves genuine donor BPM when source omits presetBpm; edits only when given',()=>{
 const modified=Uint8Array.from(donor),view=new DataView(modified.buffer);
 view.setUint32(105,77,true);modified[20]=slots.crc8(modified.subarray(21));
 const b=convert.convert(a,modified,opts).bytes;
 assert.equal(new DataView(b.buffer).getUint32(105,true),77);
 const withBpm={...a,presetBpm:144};
 const c=convert.convert(withBpm,modified,opts).bytes;
 assert.equal(new DataView(c.buffer).getUint32(105,true),144);
 assert.throws(()=>convert.convert({...a,presetBpm:999},modified,opts),/invalid presetBpm/);
});
