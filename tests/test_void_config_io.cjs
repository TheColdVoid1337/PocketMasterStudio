'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const base=path.resolve(__dirname,'..');

test('Void MOD saves separate NAM mapping and edited source JSON without writing HTML',async()=>{
 const files=new Map(),writes=[];
 const folder={async getFileHandle(name,{create}={}){
  if(!files.has(name)&&!create){const e=Error('missing');e.name='NotFoundError';throw e}
  if(!files.has(name))files.set(name,'');
  return {
   async getFile(){return{text:async()=>files.get(name)}},
   async createWritable(){
    let data='';
    return{async write(text){data+=text},async close(){files.set(name,data);writes.push(name)}};
   }
  };
 }};
 const root={name:'PocketMasterStudio_Void_mod',
  async queryPermission(){return 'granted'},
  async getDirectoryHandle(name){assert.equal(name,'config');return folder}};
 const win={showDirectoryPicker:async()=>root};
 const source=fs.readFileSync(path.join(base,'src/void_config_io.js'),'utf8');
 vm.runInNewContext(source,{window:win,self:win,Promise,JSON});
 const io=win.PMVoidConfigIO;
 const loadedFirst=await io.connect();
 assert.equal(loadedFirst.state,null);
 assert.equal(loadedFirst.nam,null);
 const mapping={schema:'void-mod-nam-clone/v1',preferClone:true,
  slots:[{ampModel:'Brit 800',captureName:'My JCM Full Rig',fullRig:true},...Array.from({length:4},()=>({ampModel:null,captureName:'',fullRig:false}))]};
 const state={data:{'Artist':{name:'Artist',songs:[]}},config:{order:['Artist']},void_nam:mapping};
 await io.save({state,nam:mapping});
 const result=await io.load();
 assert.equal(result.nam.slots[0].captureName,'My JCM Full Rig');
 assert.equal(result.state.data.Artist.name,'Artist');
 assert.deepEqual([...files.keys()].sort(),['nam_clone.json','studio_state.json']);
 assert.deepEqual(writes.sort(),['nam_clone.json','studio_state.json']);
 assert.ok(!files.has('PocketMasterStudio.html'));
});
test('Void MOD generated README appendix and gitignore do not alter upstream prose',()=>{
 const main=fs.readFileSync(path.join(base,'README.md'),'utf8');
 const source=fs.readFileSync(path.join(base,'src/README_STUDIO.md'),'utf8');
 for(const content of [main,source]){
  assert.ok(content.startsWith('# PocketMaster Studio\n'));
  assert.ok(content.includes("## Void's MOD"));
  assert.ok(content.includes("### Void's MOD v0.3.0"));
 }
 assert.ok(fs.readFileSync(path.join(base,'.gitignore'),'utf8').includes('/config/'));
});
