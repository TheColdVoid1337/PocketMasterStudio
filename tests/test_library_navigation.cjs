'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
const html=fs.readFileSync(path.join(root,'PocketMasterStudio.html'),'utf8');
const builder=fs.readFileSync(path.join(root,'src/build_studio.js'),'utf8');

test('top-level menu is Studio, Editor, Library, NAM/Clone, .prst Lab, Docs',()=>{
  const main=app.match(/  const MAIN = \[([\s\S]*?)\];/)?.[1];
  assert.ok(main,'missing MAIN routes');
  assert.deepEqual([...main.matchAll(/id: "([^"]+)"/g)].map(x=>x[1]),
    ['studio','editor','library','nam','prst','docs']);
  const lib=app.match(/  const LIBRARY = \[([\s\S]*?)\];/)?.[1];
  assert.ok(lib,'missing Library pane definitions');
  assert.deepEqual([...lib.matchAll(/id: "([^"]+)"/g)].map(x=>x[1]),
    ['overview','index','full','map']);
  const studio=html.match(/id="view-studio"([\s\S]*?)id="view-library"/)?.[1];
  assert.ok(studio);
  for(const id of ['panel-prompt','panel-paste','panel-data','panel-collections'])
    assert.match(studio,new RegExp('id="'+id+'"'));
  assert.doesNotMatch(studio,/id="panel-overview"/);
  assert.doesNotMatch(html,/data-tab="overview"/);
  const overview=html.match(/id="library-pane-overview"([\s\S]*?)id="library-pane-index"/)?.[1];
  assert.ok(overview,'Overview not hosted under Library');
  for(const id of ['stats','preview','exportZip','importBtn','dlIndex'])
    assert.match(overview,new RegExp('id="'+id+'"'));
  for(const [id,label] of [['overview','Overview'],['index','Listing'],['full','Table'],['map','Map']]){
    assert.match(html,new RegExp('data-library-pane="'+id+'"[^>]*>'+label+'</button>'));
    assert.match(html,new RegExp('id="library-pane-'+id+'"'));
  }
  assert.match(builder,/id="view-library"/);
  assert.ok(html.includes(app),'generated HTML embeds different Studio JS');
  assert.match(app,/for \(const t of LIBRARY\) if \(t\._render/);
});

test('Studio tab switcher is scoped and cannot deactivate Library / PRST Lab controls',()=>{
  const start=app.indexOf('  function showTab(id) {');
  const end=app.indexOf('  function showLibraryTab(id) {',start);
  assert.ok(start>=0&&end>start);
  const studioTabs=['prompt','data'].map(tab=>({
    dataset:{tab},active:tab==='prompt',attrs:{},
    classList:{toggle(k,v){if(k==='on')this.active=v;}},
    setAttribute(k,v){this.attrs[k]=v;}
  }));
  const studioPanels=['prompt','data'].map(id=>({id:'panel-'+id,hidden:id!=='prompt'}));
  const unrelated={active:true};
  const $$=selector=>{
    if(selector==='#view-studio [data-tab]')return studioTabs;
    if(selector==='#view-studio .panel')return studioPanels;
    throw Error('Unexpected global query: '+selector);
  };
  const show=new Function('$$',app.slice(start,end)+'\nreturn showTab;')($$);
  show('data');
  assert.equal(studioTabs[1].classList.active,true);
  assert.equal(studioTabs[0].classList.active,false);
  assert.equal(studioPanels[1].hidden,false);
  assert.equal(studioPanels[0].hidden,true);
  assert.equal(unrelated.active,true);
});

test('Library tabs lazily mount once, preserve views and retry failures',()=>{
  const start=app.indexOf('  function showLibraryTab(id) {');
  const end=app.indexOf('  // ---- PROMPT generation ----',start);
  assert.ok(start>=0&&end>start);
  const tabs=['overview','index','full','map'].map(id=>({
    dataset:{libraryPane:id},attrs:{},
    classList:{toggle(k,v){if(k==='on')this.active=v;}},
    setAttribute(k,v){this.attrs[k]=v;}
  }));
  const panes=['overview','index','full','map'].map(id=>({
    id:'library-pane-'+id,hidden:id!=='overview',cleared:false,
    replaceChildren(){this.cleared=true;}
  }));
  const rootEl={};
  const $=selector=>selector==='#view-library'?rootEl:
    panes.find(p=>'#'+p.id===selector)||null;
  const $$=(selector,scope)=>{
    assert.equal(scope,rootEl,'Library selector escaped its own view');
    return selector==='[data-library-pane]'?tabs:
      selector==='.library-pane'?panes:[];
  };
  const mounted=new Set(['overview']),mountCount={},errors=[];
  const show=new Function('$','$$','LIBRARY','mountedLibrary',
    'mountLibraryPane','toast','console',
    app.slice(start,end)+'\nreturn showLibraryTab;')(
      $, $$, ['overview','index','full','map'].map(id=>({id,label:id})),
      mounted,id=>{
        mountCount[id]=(mountCount[id]||0)+1;
        if(id==='map'&&mountCount[id]===1)throw Error('temporary test failure');
      },e=>errors.push(e),{error(){}});
  show('index');
  assert.equal(mountCount.index,1);
  assert.equal(panes[1].hidden,false);
  assert.equal(tabs[1].attrs['aria-selected'],'true');
  show('overview');
  show('index');
  assert.equal(mountCount.index,1,'Listing iframe was remounted on tab return');
  show('map');
  assert.equal(mounted.has('map'),false);
  assert.equal(panes[3].hidden,true);
  assert.equal(panes[3].cleared,true);
  assert.equal(errors.length,1);
  show('map');
  assert.equal(mountCount.map,2);
  assert.equal(panes[3].hidden,false);
  assert.equal(tabs[3].attrs['aria-selected'],'true');
});
