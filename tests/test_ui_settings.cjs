'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const UI=require('../src/void_ui.js');
const root=path.resolve(__dirname,'..');
const html=fs.readFileSync(path.join(root,'PocketMasterStudio.html'),'utf8');
const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
const builder=fs.readFileSync(path.join(root,'src/build_studio.js'),'utf8');

test('UI preference reading uses safe defaults and ignores malformed values',()=>{
  const prefs=UI.readPrefs({getItem:()=>'{broken'});
  assert.deepEqual(prefs,{browserNotice:true,folderNotice:true,compactLists:true});
  const saved=UI.readPrefs({getItem:()=>JSON.stringify({
    browserNotice:false,folderNotice:false,compactLists:false,unknown:true
  })});
  assert.deepEqual(saved,{browserNotice:false,folderNotice:false,compactLists:false});
});

test('Library owns Manage and Docs; Studio has a single integrated AI workflow',()=>{
  const menu=app.match(/  const MAIN = \[([\s\S]*?)\];/)?.[1];
  const sub=app.match(/  const LIBRARY = \[([\s\S]*?)\];/)?.[1];
  assert.deepEqual([...menu.matchAll(/id: "([^"]+)"/g)].map(m=>m[1]),
    ['studio','editor','library','nam','prst','settings']);
  assert.deepEqual([...sub.matchAll(/id: "([^"]+)"/g)].map(m=>m[1]),
    ['overview','index','full','map','manage','docs']);
  assert.match(app,/id === "docs"\) return mountDocs\(view\)/);
  assert.match(app,/id === "settings"\) return window\.PMVoidUI\.mountSettings\(view\)/);
  const studio=html.match(/id="view-studio"([\s\S]*?)id="view-library"/)?.[1];
  const manage=html.match(/id="library-pane-manage"([\s\S]*?)id="library-pane-docs"/)?.[1];
  assert.ok(studio&&manage);
  assert.doesNotMatch(studio,/panel-manage|data-tab=/);
  assert.match(studio,/studio-columns/);
  assert.match(studio,/id="pasteBox"/);
  assert.match(studio,/id="genPrompt"/);
  assert.match(manage,/id="dataList"/);
  assert.match(manage,/id="collBody"/);
  assert.match(builder,/input\[type="checkbox"\],input\[type="radio"\]/);
  assert.match(builder,/max-width:16px!important/);
  assert.doesNotMatch(studio,/To connect the pedal/);
});

test('Standalone app has three status lamps and two dismissible startup notices',()=>{
  for(const id of ['statusServer','statusFolder','statusBrowser','startupDialog','startupTitle',
    'startupBody','startupConnect','startupDismiss','startupOptOut','startupOptOutLabel'])
    assert.match(html,new RegExp('id="'+id+'"'));
  assert.match(app,/window\.PMVoidUI\.start\(/);
  assert.ok(html.includes(fs.readFileSync(path.join(root,'src/void_ui.js'),'utf8')));
});

test('startup queue remembers browser opt-out; folder connects from its own action',async()=>{
  const previous={window:global.window,document:global.document,localStorage:global.localStorage,
    navigator:global.navigator,location:global.location};
  const value=new Map(),els={};
  const element=(id)=>{
    if(!els[id])els[id]={
      id,dataset:{},hidden:true,checked:false,textContent:'',title:'',attributes:{},events:{},
      setAttribute(k,v){this.attributes[k]=v;},
      querySelector(q){return q==='.status-text'?this.statusText||(this.statusText={textContent:''}):null;},
      addEventListener(event,fn){this.events[event]=fn;},
      focus(){this.focused=true;},
      click(){return this.events.click?.();},
      change(checked){this.checked=checked;this.events.change?.({target:this});}
    };
    return els[id];
  };
  let connected=false,connectCalls=0,settingsCalls=0;
  try {
    global.window={PMVoidConfigIO:{available:()=>true,connected:()=>connected,location:()=>'Project/config/'}};
    global.document={documentElement:{dataset:{}},getElementById:element,
      querySelectorAll(sel){return sel==='.status-chip'?
        ['statusServer','statusFolder','statusBrowser'].map(element):[];}};
    global.localStorage={getItem:k=>value.get(k)||null,setItem(k,v){value.set(k,v);}};
    Object.defineProperty(global,'navigator',{value:{bluetooth:{}},configurable:true,writable:true});
    global.location={protocol:'http:'};
    UI.start({onConnect:()=>{connectCalls++;connected=true;return Promise.resolve();},
      onSave:()=>Promise.resolve(),onSettings:()=>settingsCalls++});
    assert.equal(element('startupTitle').textContent,'Browser requirements');
    assert.equal(element('startupConnect').hidden,true);
    assert.equal(element('statusServer').dataset.state,'good');
    assert.equal(element('statusFolder').dataset.state,'bad');
    element('startupOptOut').checked=true;
    element('startupDismiss').click();
    assert.equal(element('startupTitle').textContent,'Project folder not connected');
    assert.equal(element('startupConnect').hidden,false);
    assert.equal(UI.readPrefs(global.localStorage).browserNotice,false);
    await element('startupConnect').click();
    assert.equal(connectCalls,1);
    assert.equal(element('startupDialog').hidden,true);
    assert.equal(element('statusFolder').dataset.state,'good');
    element('statusServer').click();
    assert.equal(settingsCalls,1);
    const view={innerHTML:''};
    UI.mountSettings(view);
    assert.match(view.innerHTML,/settingCompactLists/);
    assert.equal(element('settingBrowserNotice').checked,false);
    element('settingCompactLists').change(false);
    assert.equal(document.documentElement.dataset.density,'comfortable');
    assert.equal(UI.readPrefs(global.localStorage).compactLists,false);
  } finally {
    for(const [k,v] of Object.entries(previous)){
      if(v===undefined)delete global[k];else Object.defineProperty(global,k,{value:v,configurable:true,writable:true});
    }
  }
});
