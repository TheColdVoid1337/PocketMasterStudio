'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
const prst=fs.readFileSync(path.join(root,'src/prst_studio_ui.js'),'utf8');
const html=fs.readFileSync(path.join(root,'PocketMasterStudio.html'),'utf8');
const builder=fs.readFileSync(path.join(root,'src/build_studio.js'),'utf8');
const Debug=require('../src/void_debug.js');

test('footer save bar is removed and autosave has a status chip and Settings retry',()=>{
  assert.doesNotMatch(html,/id="saveBtn"|id="dirtyTag"|class="savebar"/);
  assert.doesNotMatch(builder,/class="savebar"/);
  assert.match(html,/id="statusSave"/);
  assert.match(html,/id="globalLogSource"/);
  assert.match(fs.readFileSync(path.join(root,'src/void_ui.js'),'utf8'),/setSaveState/);
  assert.match(app,/function saveStatus\(\)/);
  assert.match(app,/function markDirty\(d\)/);
  assert.match(html,/id="settingsSave"/);
  assert.ok(html.includes(app),'Standalone controller is stale');
  assert.ok(html.includes(prst),'Standalone native PRST exporter is stale');
});

test('Editor details stay intact; logger strips emoji without losing actual diagnostics',()=>{
  const sender={},before=Debug.entries.length;
  Debug.attachEditor({contentWindow:sender});
  assert.equal(Debug.acceptEditorMessage({
    type:'pm-void-editor-log',level:'DEBUG',
    message:'[SENT] Connect device packet 0x0A20 data=AD6F'
  },sender),true);
  const editor=Debug.entries.at(-1);
  assert.equal(editor.source,'EDITOR');
  assert.equal(editor.level,'DEBUG');
  assert.match(editor.message,/Connect device packet 0x0A20 data=AD6F/);
  const sanitized=Debug.event('PRST','Downloaded 📦 Test Tone.prst ✅');
  assert.equal(sanitized.message,'Downloaded  Test Tone.prst');
  assert.doesNotMatch(Debug.serialize(),/\p{Extended_Pictographic}/u);
  assert.equal(Debug.entries.length,before+2);
});

test('native PRST import logs file verification, archived bytes and failures',async()=>{
  const start=app.indexOf('  async function importNativeFiles(files) {');
  const end=app.indexOf('  function renderNativeImports(){',start);
  assert.ok(start>=0&&end>start);
  const call=app.slice(start,end);
  const S={payload:{prst_imports:[],collections:[]}};
  const events=[],dirties=[],toasts=[];
  let rejected=false;
  const native={
    record(bytes,filename){if(rejected)throw Error('CRC mismatch');
      return {filename,id:'crc-a102',warnings:[],rawBase64:'AA=='};
    },
    add(records,record){return {records:[...records,record],added:true}}
  };
  const logs=(source,message,level='INFO')=>events.push({source,message,level});
  const importNative=new Function('S','Native','window','namConfig','logEvent','withImportedCollection',
    'regen','markDirty','rebuild','refreshNativeEditor','toast',
    call+'\nreturn importNativeFiles;')(
    S,()=>native,{PMPRSTAssets:{catalog:[],fxNative:{}}},()=>({}),logs,p=>p,()=>{},
    state=>dirties.push(state),()=>{},()=>{},m=>toasts.push(m)
  );
  const file={name:'SoundA.prst',arrayBuffer:async()=>new Uint8Array(515).buffer};
  await importNative([file]);
  assert.equal(S.payload.prst_imports.length,1);
  assert.deepEqual(dirties,[true]);
  for(const expected of ['Import started','Checking SoundA.prst: 515 bytes','Validated SoundA.prst',
    'CRC','Import committed: 1 new']){
    assert.ok(events.some(e=>e.message.includes(expected)),expected);
  }
  rejected=true;
  await assert.rejects(()=>importNative([file]),/CRC mismatch/);
  assert.equal(S.payload.prst_imports.length,1,'Failed PRST import mutated state');
  assert.ok(events.some(e=>e.level==='ERROR'&&/Import validation failed for SoundA.prst: CRC mismatch/.test(e.message)));
});

test('native PRST export logs preparation, donor, CRC and actual filename or refusal',async()=>{
  const start=prst.indexOf('    async function exportNative() {');
  const end=prst.indexOf('    mode.addEventListener("change", refreshArtist);',start);
  assert.ok(start>=0&&end>start);
  const src=prst.slice(start,end);
  const chosen={presetName:'Test Tone',ampMode:'Normal',description:'Test',modules:{}};
  const events=[],downloads=[];
  const map={'Sample.json':{artist:'Sample Artist',presets:[chosen]}};
  const mode={value:'modeled'},artist={value:'Sample.json'},preset={value:'0'};
  const status={textContent:''},button={disabled:false};
  const fileInput={files:[]};
  const windowObj={
    PMVoidPolicy:{defaults:()=>({}),normalize:c=>c,validAmpNames:()=>[],slotMap:()=>({})},
    PRSTCloneSlots:{inspect:bytes=>({cloneEnabled:bytes[0]===1})},
    PRSTConvert:{selectDonor:(_,refs)=>refs.stock,convert:()=>({bytes:new Uint8Array(515),warnings:[]})}
  };
  const atobMock=x=>Buffer.from(x,'base64').toString('binary');
  const create=new Function('log','window','asset','status','mode','artist','preset',
    'mapNow','state','safeName','download','$','atob','Blob',src+'\nreturn exportNative;');
  const exportNative=create((level,message)=>events.push({level,message}),windowObj,{
    catalog:[],fxNative:{},templateBase64:Buffer.from([0]).toString('base64'),
    cloneTemplateBase64:Buffer.from([1]).toString('base64')
  },status,mode,artist,preset,()=>map,()=>({payload:{void_nam:{}}}),
  x=>x.replace(/[^a-zA-Z0-9_-]+/g,'_'),(file,blob)=>downloads.push([file,blob]),
  id=>id==='prst-export'?button:id==='prst-donor'?fileInput:null,atobMock,Blob);
  await exportNative();
  assert.equal(button.disabled,false);
  assert.equal(downloads.length,1);
  assert.equal(downloads[0][0],'Test_Tone.prst');
  assert.equal(downloads[0][1].size,515);
  for(const expected of ['Native export started','Preparing 1 preset','Donor selection',
    'CRC verified: Test Tone','Download initiated: Test_Tone.prst']){
    assert.ok(events.some(e=>e.message.includes(expected)),expected);
  }
  map['Sample.json'].presets=[];
  await exportNative();
  assert.equal(downloads.length,1,'Refused export downloaded invalid data');
  assert.ok(events.some(e=>e.level==='ERROR'&&e.message.includes('Native export blocked')));
});

test('autosave only marks the current revision Saved and reports errors',async()=>{
  const start=app.indexOf('  const logEvent = (source,message,level="INFO")');
  const stop=app.indexOf('  function applyNAM',start);
  const first=app.slice(start,stop);
  const m=app.indexOf('  function markDirty(d) {'),n=app.indexOf('  // ---- tabs ----',m);
  assert.ok(start>=0&&stop>start&&m>=0&&n>m);
  const statuses=[],events=[],timers=[];
  let rejectWrite=false;
  const S={dirty:false,payload:{prst_imports:[],collections:[]}};
  const IO={connected:()=>true,location:()=>'/config',save:async()=>{if(rejectWrite)throw Error('Disk full')}};
  const w={PMVoidUI:{setSaveState:s=>statuses.push(s)},PMVoidDebug:{event:(...a)=>events.push(a)}};
  const create=new Function('S','IO','Policy','namConfig','ampNames','sourcePayload',
    'window','setTimeout','clearTimeout','toast',
    'let saveTimer=null,revision=0,namView=null,saveFailed=false;\n'+
    first+app.slice(m,n)+'\nreturn {markDirty,persistConfig,changed};');
  const runtime=create(S,IO,{normalize:c=>c},()=>({}),()=>[],()=>({}),
    w,fn=>{timers.push(fn);return timers.length;},()=>{},()=>{});
  runtime.markDirty(true);
  assert.equal(statuses.at(-1),'saving');
  await runtime.persistConfig();
  assert.equal(statuses.at(-1),'saved');
  assert.equal(S.dirty,false);
  assert.ok(events.some(x=>x[1].includes('Saved studio_state.json and nam_clone.json')));
  rejectWrite=true;
  runtime.changed();
  assert.equal(statuses.at(-1),'saving');
  await assert.rejects(()=>runtime.persistConfig(),/Disk full/);
  assert.equal(statuses.at(-1),'error');
  assert.equal(S.dirty,true);
  assert.ok(events.some(x=>x[2]==='ERROR'&&x[1].includes('Save failed for revision')));
});
