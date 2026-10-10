'use strict';
// Regression tests that EXECUTE .prst Lab UI handlers, not just grep its markup.
// No jsdom/npm needed: a minimal DOM-shaped fixture exercises the exact
// JavaScript branch from studio_app.js and the menu activation lifecycle.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = fs.readFileSync(path.join(__dirname, '..', 'src', 'studio_app.js'), 'utf8');

const classList = () => {
  const values = new Set();
  return {
    add: x => values.add(x),
    remove: x => values.delete(x),
    contains: x => values.has(x),
    toggle: (x, force) => {
      const on = force == null ? !values.has(x) : !!force;
      if (on) values.add(x); else values.delete(x);
      return on;
    },
  };
};
function element(attributes = {}) {
  const handlers = new Map();
  return {
    ...attributes,
    classList: classList(),
    attrs: {},
    hidden: !!attributes.hidden,
    addEventListener(name, fn) { handlers.set(name, fn); },
    setAttribute(name, value) { this.attrs[name] = value; },
    click() { return handlers.get('click')?.({target:this}); },
    dispatch(name, event) { return handlers.get(name)?.(event); },
    get handlers() { return handlers; },
  };
}
function livePrstBranch() {
  const start = app.indexOf('    if (id === "prst") {');
  const end = app.indexOf('    if (id === "editor") return mountEditor(view, t);', start);
  assert.ok(start >= 0 && end > start, 'Could not locate real .prst Lab mount branch');
  return new Function('id', 'view', '$', '$$', 'window', 'renderNativeImports',
    'importNativeFiles', 'removeNative', 'Native', 'download', 'S', 'alert', 'Blob', 'logEvent',
    app.slice(start, end));
}

test('opening .prst Lab initializes BOTH subtabs and usable import/download/remove actions', async () => {
  const importTab = element({dataset:{prstPane:'import'}});
  const exportTab = element({dataset:{prstPane:'export'}});
  const importPane = element(), exportPane = element({hidden:true});
  const importButton = element();
  const fileInput = element({files:[],value:''});
  const importedList = element();
  let pickerOpens = 0;
  fileInput.click = () => { pickerOpens++; };
  const controls = {
    '#prst-pane-import': importPane,
    '#prst-pane-export': exportPane,
    '#importNativeBtn': importButton,
    '#importNativeFile': fileInput,
    '#nativePrstList': importedList,
  };
  const view = element();
  view.querySelector = selector => controls[selector] || null;
  view.querySelectorAll = selector =>
    selector === '[data-prst-pane]' ? [importTab, exportTab] : [];
  const $ = (selector, root) => root.querySelector(selector);
  const $$ = (selector, root) => root.querySelectorAll(selector);
  const nativeEntries = [{filename:'origin.prst',rawBase64:'sample'}];
  const imported = [], removed = [], downloads = [], errors = [];
  let exporterMounts = 0, listRenders = 0;
  const fakeWindow = {
    PMPRSTExportUI: {
      mount(container) {
        assert.equal(container, exportPane);
        exporterMounts++;
      },
    },
  };
  const fakeBlob = class {
    constructor(parts, options) { this.parts=parts; this.type=options.type; }
  };
  livePrstBranch()('prst', view, $, $$, fakeWindow,
    () => { listRenders++; },
    async files => { imported.push(...files); },
    index => { removed.push(index); },
    () => ({fromBase64: () => new Uint8Array([1,2,3])}),
    (filename, bytes) => { downloads.push({filename,bytes}); },
    {payload:{prst_imports:nativeEntries}}, m=>errors.push(m),fakeBlob,()=>{});

  assert.equal(exporterMounts, 1, 'real .prst exporter not mounted');
  assert.equal(listRenders, 1, 'existing native records not rendered');
  assert.equal(importTab.handlers.has('click'),true);
  assert.equal(exportTab.handlers.has('click'),true);
  assert.equal(importButton.handlers.has('click'),true);
  assert.equal(fileInput.handlers.has('change'),true);
  assert.equal(importedList.handlers.has('click'),true);
  assert.equal(importPane.hidden,false);
  assert.equal(exportPane.hidden,true);

  exportTab.click();
  assert.equal(exportPane.hidden,false);
  assert.equal(importPane.hidden,true);
  assert.equal(exportTab.classList.contains('on'),true);
  assert.equal(exportTab.attrs['aria-selected'],'true');

  importTab.click();
  assert.equal(importPane.hidden,false);
  assert.equal(exportPane.hidden,true);
  assert.equal(importTab.attrs['aria-selected'],'true');
  importButton.click();
  assert.equal(pickerOpens,1,'Import .prst button did not open file picker');

  const selected = [{name:'tone.prst'}];
  fileInput.files=selected;
  fileInput.value='some-path';
  await fileInput.dispatch('change',{target:fileInput});
  assert.deepEqual(imported,selected);
  assert.equal(fileInput.value,'','file input should reset for reimports');

  await importedList.dispatch('click',{target:{
    closest(sel) {
      if(sel==='[data-native-remove]')return {dataset:{nativeRemove:'0'}};
      return null;
    },
  }});
  assert.deepEqual(removed,[0]);
  await importedList.dispatch('click',{target:{
    closest(sel) {
      if(sel==='[data-native-download]')return {dataset:{nativeDownload:'0'}};
      return null;
    },
  }});
  assert.equal(downloads.length,1);
  assert.equal(downloads[0].filename,'origin.prst');
  assert.deepEqual(Array.from(downloads[0].bytes.parts[0]),[1,2,3]);
  assert.deepEqual(errors,[]);
});

test('failed initial menu mount is not cached or shown as a dead view; retry succeeds', () => {
  const start=app.indexOf('  function activate(id) {');
  const end=app.indexOf('  function mount(id) {',start);
  assert.ok(start>=0&&end>start,'Menu activate function not found');
  const nav=element({dataset:{main:'prst'}}),other=element({dataset:{main:'studio'}});
  const failedView=element({id:'view-prst'});
  failedView.remove=()=>{failedView.removed=true};
  const firstView=element({id:'view-studio'});
  const label=element();
  const mounted={studio:true};
  const toastCalls=[],errors=[];
  let attempts=0;
  const $=sel=>{
    if(sel==='#view-prst')return failedView;
    if(sel==='#menuBtnLabel')return label;
    return null;
  };
  const $$=sel=>{
    if(sel==='.maintab, .mitem')return [nav,other];
    if(sel==='#views .view')return [firstView,failedView];
    return [];
  };
  const activate=new Function('MAIN','mounted','mount','$','$$','tabHtml','toast','console',
    app.slice(start,end)+'\nreturn activate;')(
    [{id:'studio',label:'Studio'}, {id:'prst',label:'.prst Lab'}],
    mounted,
    () => {if(++attempts===1)throw Error('test: one transient error')},
    $, $$, t=>t.label, m=>toastCalls.push(m),{error:(...v)=>errors.push(v)});
  activate('prst');
  assert.equal(attempts,1);
  assert.equal(mounted.prst,undefined,'failed mount was incorrectly marked initialized');
  assert.equal(failedView.removed,true,'failed partial view was not removed');
  assert.equal(nav.classList.contains('on'),false);
  assert.match(toastCalls[0],/Could not open .prst Lab/);
  activate('prst');
  assert.equal(attempts,2,'retry did not reinitialize');
  assert.equal(mounted.prst,true);
  assert.equal(nav.classList.contains('on'),true);
  assert.equal(failedView.classList.contains('active'),true);
  assert.equal(label.innerHTML,'.prst Lab');
  assert.equal(errors.length,1);
});
