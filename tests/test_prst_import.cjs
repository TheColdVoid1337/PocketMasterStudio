'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const bridge=require('../src/prst_import.js');
const Build=require('../src/pmbuild.js');
const Policy=require('../src/void_policy.js');
const Slots=require('../tools/prst_clone_slots.js');
const catalog=JSON.parse(fs.readFileSync(path.join(root,'catalog/effects.json'),'utf8'));
const fxNative=JSON.parse(fs.readFileSync(path.join(root,'catalog/fx_native.json'),'utf8'));
const normal=fs.readFileSync(path.join(root,'templates/pocket_master_reference.prst'));
const clone=fs.readFileSync(path.join(root,'templates/pocket_master_clone_reference.prst'));
const opts={catalog,fxNative,voidConfig:Policy.defaults()};

test('genuine Normal PRST is decoded and original 515 bytes are retained exactly',()=>{
 const p=bridge.decode(normal,opts);
 assert.equal(p.preset.ampMode,'Normal');
 assert.equal(p.preset.modules.AMP.effect,'Brit 45');
 assert.equal(p.preset.modules.DRV.effect,'Grey Fuzz');
 assert.equal(p.preset.modules.IR.effect,'Bog 4x12');
 assert.equal(p.preset.presetName,'PM_FLAGS_ORDER');
 assert.deepEqual(Buffer.from(p.preset.nativeImport.rawBase64,'base64'),normal);
 assert.equal(p.preset.nativeImport.readOnly,true);
 assert.equal(p.preset.signalChain.length,9);
});
test('genuine Clone PRST imports as a raw, unmapped User Profile snapshot',()=>{
 const p=bridge.decode(clone,opts);
 assert.equal(p.preset.ampMode,'Clone');
 assert.equal(p.preset.modules.IR.enabled,false);
 assert.equal(p.preset.nativeImport.cloneSlot,1);
 assert.match(p.preset.modules.Clone.effect,/Unmapped User Profile 1/);
 assert.ok(p.warnings.some(w=>w.includes('no confirmed Full Rig')));
 assert.deepEqual(Buffer.from(p.rawBase64,'base64'),clone);
});
test('configured slot resolves the exact installed NAM label in shared library',()=>{
 const config=Policy.defaults();
 config.slots[0]={ampModel:'Brit 800',captureName:'My full rig',fullRig:true};
 const p=bridge.decode(clone,{...opts,voidConfig:config});
 assert.equal(p.preset.modules.Clone.effect,'My full rig');
});
test('bad CRC is blocked but unknown ACTIVE effect stays read-only and lossless',()=>{
 const broken=Buffer.from(normal);broken[20]^=1;
 assert.throws(()=>bridge.decode(broken,opts),/CRC/);
 const unknown=Buffer.from(normal);unknown[139+3*4]=254;unknown[20]=Slots.crc8(unknown.subarray(21));
 const parsed=bridge.decode(unknown,opts);
 assert.match(parsed.preset.modules.AMP.effect,/Unknown native AMP/);
 assert.ok(parsed.warnings.some(s=>s.includes('unknown ACTIVE selector')));
 assert.deepEqual(Buffer.from(parsed.rawBase64,'base64'),unknown);
 const record=bridge.record(unknown,'unknown_amp.prst',opts);
 assert.ok(record.warnings.some(s=>s.includes('unknown ACTIVE selector')));
 assert.equal(bridge.asBatches([record],opts)['PRST Imports 001.json'].presets.length,1);
});
test('native presets become shared library batches, searchable and collection selectable',()=>{
 const records=[bridge.record(normal,'normal.prst',opts),bridge.record(clone,'clone.prst',opts)];
 const files=bridge.asBatches(records,opts);
 const batch=files['PRST Imports 001.json'];
 assert.equal(batch.presets.length,2);
 assert.equal(batch.presets[0].song,'prst_'+records[0].id);
 assert.equal(batch.presets[1].ampMode,'Clone');
 const lib=Build.buildLibrary(files,files,files);
 assert.equal(lib.modeled.length,1);
 assert.equal(lib.modeled[0].songs.length,2);
 const catalogRows=require('../src/pmedit.js').presetCatalog(files);
 assert.equal(catalogRows.length,2);
 const ref=['PRST Imports 001','prst_'+records[0].id,'N'];
 assert.ok(Build.makeRefResolver(files).exists(ref));
 const collection={file:'Compilation_PRST_Test.json',collection:'Imported',n:1,refs:[ref]};
 assert.equal(Build.buildCompilations(files,{collections:[collection]})[collection.file].presets[0].nativeImport.id,records[0].id);
 const duplicate=bridge.add(records,records[0]);
 assert.equal(duplicate.added,false);
 assert.equal(duplicate.records.length,2);
});
test('NAM conversion never changes imported native snapshots even if mapping later changes',()=>{
 const rec=bridge.record(normal,'normal.prst',opts);
 const imported=bridge.asBatches([rec],opts);
 const config=Policy.defaults();config.slots[0]={ampModel:'Brit 45',captureName:'JTM FULL RIG',fullRig:true};
 const batch=Build.buildNam(imported,{},config)['files']['PRST Imports 001.json'];
 assert.equal(batch.presets[0].ampMode,'Normal');
 assert.equal(batch.presets[0].nativeImport.rawBase64,rec.rawBase64);
});

test('new and legacy PRST records are placed in the Imported collection without changing other collections',()=>{
  const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
  const start=app.indexOf('  function withImportedCollection(payload) {');
  const end=app.indexOf('  // Native binary imports are append-only snapshots:',start);
  assert.ok(start>=0&&end>start,'Native collection organizer was not found in live controller');
  const withImportedCollection=new Function('PMBuild',app.slice(start,end)+
    '\nreturn withImportedCollection;')(Build);
  const records=[bridge.record(normal,'a.prst',opts),bridge.record(clone,'b.prst',opts)];
  const manual={file:'Compilation_Owner.json',collection:'Favorites',n:50,refs:[['Pink Floyd','ComfortablyNumb','L']]};
  const original={prst_imports:records,collections:[manual]};
  const updated=withImportedCollection(original);
  assert.equal(original.collections.length,1,'original project mutated before validation');
  assert.deepEqual(original.collections[0].refs,manual.refs);
  const imported=updated.collections.find(c=>c.collection==='Imported');
  assert.ok(imported);
  assert.equal(imported.file,'Compilation_Imported.json');
  assert.deepEqual(imported.refs,records.map((r,i)=>['PRST Imports 001','prst_'+r.id,'N']));
  assert.equal(updated.collections[0].collection,'Favorites');
  assert.equal(withImportedCollection(updated),updated,'migration must be idempotent');
  const files={...bridge.asBatches(records,opts)};
  const compilation=Build.buildCompilations(files,{collections:updated.collections.filter(c=>c.collection==='Imported')});
  assert.deepEqual(compilation[imported.file].presets.map(p=>p.nativeImport.id),records.map(r=>r.id));
  assert.deepEqual(Buffer.from(compilation[imported.file].presets[0].nativeImport.rawBase64,'base64'),normal);
});
test('Imported grows to retain more than 50 archives and does not duplicate prior refs',()=>{
  const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
  const start=app.indexOf('  function withImportedCollection(payload) {');
  const end=app.indexOf('  // Native binary imports are append-only snapshots:',start);
  const organizer=new Function('PMBuild',app.slice(start,end)+'\nreturn withImportedCollection;')(Build);
  const records=Array.from({length:52},(_,i)=>({id:String(i).padStart(8,'0')}));
  const prior={file:'Compilation_Imported.json',collection:'Imported',n:50,
    refs:[['PRST Imports 001','prst_00000000','N']]};
  const payload={prst_imports:records,collections:[prior]};
  const updated=organizer(payload),imports=updated.collections[0];
  assert.equal(imports.refs.length,52);
  assert.equal(imports.n,52);
  assert.deepEqual(imports.refs[50],['PRST Imports 002','prst_00000050','N']);
  assert.equal(organizer(updated),updated);
});
