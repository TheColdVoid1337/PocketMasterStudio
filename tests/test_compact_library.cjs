'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const Html=require('../src/pmhtml.js');
const Tabla=require('../src/pmtabla.js');
const Map=require('../src/pmmap.js');
const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
const html=fs.readFileSync(path.join(root,'PocketMasterStudio.html'),'utf8');
const builder=fs.readFileSync(path.join(root,'src/build_studio.js'),'utf8');
const docs=fs.readFileSync(path.join(root,'docs/VOID_MOD.md'),'utf8');

const modeled={
  version:'1.0',presetName:'RiffR',ampMode:'Normal',slot:49,song:'demo',kind:'R',
  description:'Demo: modeled tone',presetVolume:80,modules:{
    AMP:{enabled:true,effect:'Brit 800',parameters:{}},
    DRV:{enabled:false,effect:'Grey Fuzz',parameters:{}},
    FX1:{enabled:false,effect:'Boost',parameters:{}}
  }
};
const cloned={
  version:'1.0',presetName:'SoloL',ampMode:'Clone',slot:50,song:'solo',kind:'L',
  description:'Solo: mapped Full Rig',presetVolume:100,modules:{
    AMP:{enabled:true,effect:'DONOR-AMP-IGNORE',parameters:{}},
    Clone:{enabled:true,effect:'MY VERIFIED FULL RIG',parameters:{Gain:50}},
    DRV:{enabled:false,effect:'Grey Fuzz',parameters:{}},
    FX1:{enabled:false,effect:'Boost',parameters:{}}
  }
};
const artist={
  type:'PocketMasterBatch',artist:'Example Band',count:2,slots:'49-50',
  presets:[modeled,cloned]
};

test('Listing identifies actual NAM, unmapped Modeled fallback and active capture name',()=>{
  const listing=Html.buildIndex({'Example Band.json':artist},{variant:'mixed'})['index.html'];
  assert.match(listing,/class="mode mode-nam">NAM/);
  assert.match(listing,/class="mode mode-fallback">Modeled fallback/);
  assert.match(listing,/MY VERIFIED FULL RIG/);
  assert.match(listing,/1 NAM Full Rig/);
  assert.match(listing,/Clone\/NAM and Mixed currently share the same rules/);
  assert.equal(Html._helpers.amp(cloned),'MY VERIFIED FULL RIG');
  const normal=Html.buildIndex({'Example Band.json':artist},{variant:'modeled'})['index.html'];
  assert.doesNotMatch(normal,/class="mode mode-fallback">Modeled fallback/);
});

test('Table uses live Clone model without changing its source preset',()=>{
  const before=JSON.stringify(artist);
  const table=Tabla.buildTabla({'Example Band.json':artist},null);
  assert.match(table['presets_full.html'],/class="mode-flag">NAM/);
  assert.match(table['presets_full.html'],/MY VERIFIED FULL RIG/);
  assert.equal(JSON.stringify(artist),before,'Table or print rendering mutated source');
});

test('Map uses NAM name instead of inactive donor and opens compactly',()=>{
  const samples=[{...modeled,slot:1,artist:'Example Band'},{...cloned,slot:2,artist:'Example Band'}];
  const map=Map.buildM50({'Compilation_Best50.json':{
    type:'PocketMasterBatch',collection:'Best 50 (a bit of everything)',
    presets:samples,count:samples.length,slots:'1-2'
  }})['map_Best50.html'];
  assert.match(map,/MY VERIFIED FULL RIG/);
  assert.match(map,/NAM/);
  assert.doesNotMatch(map,/DONOR-AMP-IGNORE/);
  assert.doesNotMatch(map,/<details class="slot" open/);
});

test('Manage combines source and collections, while the Overview duplicate is removed',()=>{
  const manage=html.match(/id="library-pane-manage"([\s\S]*?)id="library-pane-docs"/)?.[1];
  assert.ok(manage,'Unified Library workspace is missing');
  for(const id of ['dataList','dataFilter','collSel','collBody','delBtn','collAdd','collDelete'])
    assert.match(manage,new RegExp('id="'+id+'"'));
  assert.doesNotMatch(html,/id="preview"/);
  assert.doesNotMatch(html,/data-tab="data"|data-tab="collections"/);
  assert.match(builder,/manage-layout/);
  assert.match(app,/function filterSourceList\(query\)/);
  assert.match(app,/\$\("#dataFilter"\)\.addEventListener\("input"/);
  assert.match(app,/id === "overview" \? t\.gen\(map, context\)/);
  assert.ok(html.includes(app),'Standalone HTML has outdated controller');
  assert.ok(html.includes(JSON.stringify(docs)),'Standalone HTML has outdated docs');
});

test('Manage source search filters visible rows without mutating source or checkboxes',()=>{
  const begin=app.indexOf('  function filterSourceList(query) {');
  const end=app.indexOf('  function selectedDeletions()',begin);
  assert.ok(begin>=0&&end>begin,'Missing source filter');
  const songs=[
    {textContent:'Bohemian Rhapsody - solo',hidden:false,checked:true},
    {textContent:'Master of Puppets - rhythm',hidden:false,checked:false}
  ];
  const artists=[
    {hidden:false,open:false,querySelector(){return {textContent:'Queen'};}},
    {hidden:false,open:false,querySelector(){return {textContent:'Metallica'};}}
  ];
  const $$=(query,context)=>{
    if(query==='#dataList details.art')return artists;
    if(query===':scope > div > .song')return [songs[artists.indexOf(context)]];
    throw Error('Unexpected selector '+query);
  };
  const filter=new Function('$$',app.slice(begin,end)+'\nreturn filterSourceList;')($$);
  filter('master');
  assert.equal(artists[0].hidden,true);
  assert.equal(artists[1].hidden,false);
  assert.equal(songs[0].hidden,true);
  assert.equal(songs[1].hidden,false);
  assert.equal(artists[1].open,true);
  filter('');
  assert.equal(artists[0].hidden,false);
  assert.equal(songs[0].hidden,false);
  assert.equal(songs[0].checked,true);
});
