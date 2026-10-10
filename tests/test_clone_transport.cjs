'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const P=require('../src/void_clone_protocol.js'),T=require('../src/void_clone_transport.js');
const upstream=require('./fixtures/sonicmaster_clone_upload_golden.json');

function reconstructedFullClo(){
 const chunks=upstream.upload_chunks.map(P.fromHex).map(P.unpackChunk);
 const blob=Uint8Array.from(chunks.flatMap(x=>Array.from(x.part)));
 assert.equal(blob.length,P.BLOB_SIZE);
 const full=new Uint8Array(P.FILE_SIZE);
 full.set(blob.subarray(74));
 const v=new DataView(full.buffer);
 v.setUint32(4,P.FILE_SIZE,true);
 v.setUint32(20,P.FILE_SIZE-136,true);
 v.setUint32(132,2048,true);
 v.setUint16(8,P.crc16(full.subarray(12)),false);
 return full;
}
const profileName='ref_wavene';
function fakeNames(name){
 const out=new Uint8Array(1+22+32*5+1);
 out[0]=0xF0;out[out.length-1]=0xF7;
 const str=name.slice(0,10);
 for(let i=0;i<str.length;i++){
  const c=str.charCodeAt(i),v=c===32?[2,0]:c===95?[5,15]:
    c>=97&&c<=111?[6,c-96]:c>=112&&c<=122?[7,c-112]:
    c>=65&&c<=79?[4,c-64]:c>=80&&c<=90?[5,c-80]:
    c>=48&&c<=57?[3,c-48]:[2,0];
  out.set(v,1+22+i*2);
 }
 return out;
}
function fakePedal({ack=true,commit=true,readback=profileName}={}){
 let listeners=new Set(),count=0,names=0;
 const emit=frame=>{for(const cb of [...listeners])cb(frame)};
 const io={
  onFrame(cb){listeners.add(cb);return()=>listeners.delete(cb)},
  send:async(frame)=>{
   const h=P.hex(frame);
   if(h===P.SESSION_INIT.slice(4)){queueMicrotask(()=>emit(P.fromHex('F011300001000000F7')));return}
   if(h===P.CLONE_NAMES.slice(4)){names++;queueMicrotask(()=>emit(fakeNames(readback)));return}
   const data=P.unpackChunk(frame);count++;
   if(ack)queueMicrotask(()=>emit(P.fromHex(P.ACK_HEX)));
   if(data.seq===145&&commit)queueMicrotask(()=>emit(P.fromHex('F0110000010000000102010B0003F7')));
  }
 };
 return {io,get count(){return count},get names(){return names}};
}
test('CLO full file checks CRC and rejects truncated/non-finite payloads',()=>{
 const full=reconstructedFullClo();
 assert.equal(P.validateFile(full).bytesLength,8840);
 assert.equal(P.uploadClo(full).length,2696);
 assert.equal(P.hex(P.uploadClo(full).subarray(0,4)),'56545349');
 const crcBroken=full.slice();crcBroken[900]^=1;
 assert.throws(()=>P.validateFile(crcBroken),/CRC16 mismatch/);
 assert.throws(()=>P.validateFile(full.slice(0,2696)),/8840/);
 const nan=full.slice();new DataView(nan.buffer).setFloat32(136,NaN,true);
 new DataView(nan.buffer).setUint16(8,P.crc16(nan.subarray(12)),false);
 assert.throws(()=>P.validateFile(nan),/Non-finite/);
});
test('146 generated SysEx frames exactly reproduce SonicMaster official-capture golden',()=>{
 const plan=P.makeUpload({slot:0,name:profileName,clo:reconstructedFullClo()});
 assert.equal(plan.chunks.length,146);
 assert.equal(plan.blob[6],0);
 assert.equal(plan.blob[9],15);
 assert.deepEqual(plan.chunks.map(P.hex),upstream.upload_chunks);
 assert.equal(P.makeUpload({slot:2,name:profileName,clo:reconstructedFullClo()}).blob[6],2);
 assert.throws(()=>P.makeUpload({slot:5,name:'test',clo:reconstructedFullClo()}),/0–4/);
});
test('NAM architecture gate never accepts unsupported neural formats as WaveNet',()=>{
 const model={architecture:'WaveNet',config:{layers:[{channels:16,gated:false}]}};
 assert.equal(P.validateNam(JSON.stringify(model)).architecture,'WaveNet');
 assert.throws(()=>P.validateNam('not json'),/valid JSON/);
 assert.throws(()=>P.validateNam(JSON.stringify({architecture:'LSTM'})),/unsupported/);
 assert.throws(()=>P.validateNam(JSON.stringify({architecture:'WaveNet',
  config:{layers:[{channels:16,gated:true}]}})),/Gated/);
 assert.equal(P.validateNam(JSON.stringify({architecture:'SlimmableContainer',
  config:{submodels:[{max_value:1,model:{architecture:'WaveNet'}}]}})).architecture,'WaveNet');
});
test('upload waits for all ACKs and flash commit and verifies name readback',async()=>{
 const {io,...unused}=fakePedal();
 const pedal=fakePedal(),progress=[];
 const result=await T.upload(pedal.io,{slot:0,name:profileName,clo:reconstructedFullClo(),
  onProgress:(a,b)=>progress.push([a,b]),ackTimeout:50,commitTimeout:50});
 assert.equal(result.status,'verified');
 assert.equal(result.readback,profileName.slice(0,10));
 assert.equal(pedal.count,146);
 assert.equal(pedal.names,2);
 assert.deepEqual(progress.at(-1),[146,146]);
});
test('missing ACK or missing flash commit cannot be reported as success',async()=>{
 const stalled=fakePedal({ack:false});
 await assert.rejects(()=>T.upload(stalled.io,{
  slot:1,name:profileName,clo:reconstructedFullClo(),ackTimeout:1,ackRetries:2,commitTimeout:5}),/did not receive ACK/);
 assert.equal(stalled.count,2);
 const noFlash=fakePedal({commit:false});
 await assert.rejects(()=>T.upload(noFlash.io,{
  slot:1,name:profileName,clo:reconstructedFullClo(),ackTimeout:50,commitTimeout:3}),/NOT confirmed/);
 assert.equal(noFlash.count,146);
});
test('commit with wrong name remains explicitly unverified',async()=>{
 const wrong=fakePedal({readback:'oldname'});
 const result=await T.upload(wrong.io,{
  slot:2,name:profileName,clo:reconstructedFullClo(),ackTimeout:50,commitTimeout:50});
 assert.equal(result.status,'committed-unverified');
});

test('NAM/Clone mounts standalone guarded uploader, but NAM does not pretend to be converted',()=>{
 const root=path.join(__dirname,'..');
 const html=fs.readFileSync(path.join(root,'PocketMasterStudio.html'),'utf8');
 const build=fs.readFileSync(path.join(root,'src/build_studio.js'),'utf8');
 const nam=fs.readFileSync(path.join(root,'src/void_nam_ui.js'),'utf8');
 const ui=fs.readFileSync(path.join(root,'src/void_clone_upload_ui.js'),'utf8');
 for(const p of ['src/void_clone_protocol.js','src/void_clone_transport.js',
   'src/void_clone_upload_ui.js']){
   const js=fs.readFileSync(path.join(root,p),'utf8');
   assert.ok(html.includes(js),p+' is not in the standalone HTML');
 }
 assert.ok(html.includes(nam),'NAM tab is stale');
 assert.match(build,/void_clone_protocol\.js/);
 assert.match(nam,/id="void-clone-transfer"/);
 assert.match(ui,/id="clone-confirm"/);
 assert.match(ui,/OVERWRITE User Profile/);
 assert.match(ui,/Standard <code>\.nam<\/code> requires/);
 assert.match(ui,/Conversion not yet integrated/);
 assert.doesNotMatch(ui,/\/editor\/|mountEditor\(/);
});
