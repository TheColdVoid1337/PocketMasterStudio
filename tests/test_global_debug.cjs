'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'..');
const Debug=require('../src/void_debug.js');

test('unified debug recorder preserves source, severity and unique export convention',()=>{
 const count=Debug.entries.length;
 Debug.event('STUDIO','generated a prompt');
 Debug.event('PRST','invalid CRC','ERROR');
 Debug.event('NAM','mapping changed','DEBUG');
 const recent=Debug.entries.slice(-3);
 assert.deepEqual(recent.map(x=>x.source),['STUDIO','PRST','NAM']);
 assert.deepEqual(recent.map(x=>x.level),['INFO','ERROR','DEBUG']);
 const saved=Debug.serialize();
 assert.match(saved,/PocketMasterStudio Debug Log/);
 assert.match(saved,/\[STUDIO\] generated a prompt/);
 assert.match(saved,/\[PRST\] invalid CRC/);
 const file=Debug.fileName(new Date('2026-10-10T12:38:00Z'),'abc123');
 assert.equal(file,'PocketMasterStudio_debug_20261010_123800_abc123.log');
 assert.equal(Debug.entries.length,count+3);
});

test('Editor log bridge rejects messages from unrelated windows',()=>{
 const frameWindow={};
 Debug.attachEditor({contentWindow:frameWindow});
 const previous=Debug.entries.length;
 assert.equal(Debug.acceptEditorMessage({type:'pm-void-editor-log',level:'ERROR',message:'wrong sender'},{}),false);
 assert.equal(Debug.acceptEditorMessage({type:'other',message:'wrong type'},frameWindow),false);
 assert.equal(Debug.entries.length,previous);
 assert.equal(Debug.acceptEditorMessage({type:'pm-void-editor-log',level:'WARN',message:'pedal disconnected'},frameWindow),true);
 assert.equal(Debug.entries.at(-1).source,'EDITOR');
 assert.equal(Debug.entries.at(-1).level,'WARN');
 assert.match(Debug.editorHook,/postMessage/);
 new Function(Debug.editorHook);
});

test('standalone HTML has one integrated Overview and a globally mounted debug console',()=>{
 const html=fs.readFileSync(path.join(root,'PocketMasterStudio.html'),'utf8');
 const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
 const builder=fs.readFileSync(path.join(root,'src/build_studio.js'),'utf8');
 assert.match(html,/id="overview-listing"/);
 assert.match(html,/id="stats"/);
 assert.match(html,/id="importBtn"/);
 assert.doesNotMatch(html,/data-library-pane="index"|id="library-pane-index"/);
 for(const id of ['globalLogToggle','globalLogPanel','globalLogRows','globalLogLevel',
   'globalLogSearch','globalLogSave','globalLogDownload','globalLogClear','globalLogExportStatus'])
   assert.match(html,new RegExp('id="'+id+'"'));
 assert.match(builder,/void_debug\.js/);
 assert.match(builder,/debug-fab/);
 assert.match(app,/PMVoidDebug\?\.init\(\)/);
 assert.match(app,/PMVoidDebug\?\.attachEditor\(f\)/);
 assert.match(app,/showLibraryTab\("overview"\)/);
 assert.match(app,/id === "overview" \? t\.gen\(map, context\)/);
 assert.ok(html.includes(fs.readFileSync(path.join(root,'src/void_debug.js'),'utf8')));
 assert.ok(html.includes(app));
});

test('logs are written only under authorized project root, never config or HTTP',async()=>{
 const IO=require('../src/void_config_io.js');
 await assert.rejects(()=>IO.saveLog('PocketMasterStudio_debug_20261010_123800_abc123.log','test'),/Connect project folder/);
 const files=new Map();
 const logs={
  async getFileHandle(name,opts={}){
   if(!files.has(name)){
    if(!opts.create){const error=new Error('Not found');error.name='NotFoundError';throw error;}
    const file={async createWritable(){return {async write(data){files.set(name,data)},async close(){}};}};
    files.set(name,'');return file;
   }
   return {async createWritable(){return {async write(data){files.set(name,data)},async close(){}};}};
  }
 };
 const config={async getFileHandle(){const error=new Error('Not found');error.name='NotFoundError';throw error;}};
 const seen=[];
 const rootHandle={name:'PocketMasterStudio',
  async queryPermission(){return 'granted'},
  async getDirectoryHandle(name,opts){seen.push({name,create:!!opts?.create});
   if(name==='config')return config;
   if(name==='logs')return logs;
   throw Error('Unexpected directory '+name);
  }
 };
 const prev=global.window;
 try{
  global.window={showDirectoryPicker:async()=>rootHandle};
  await IO.connect();
  const file='PocketMasterStudio_debug_20261010_123800_abc123.log';
  assert.equal(await IO.saveLog(file,'Hello\n'),'logs/'+file);
  assert.equal(files.get(file),'Hello\n');
  assert.ok(seen.some(x=>x.name==='logs'&&x.create));
  await assert.rejects(()=>IO.saveLog(file,'overwrite'),/already exists/);
  assert.equal(files.get(file),'Hello\n');
  await assert.rejects(()=>IO.saveLog('../other.log','x'),/Invalid debug log filename/);
 }finally{if(prev===undefined)delete global.window;else global.window=prev;}
});
