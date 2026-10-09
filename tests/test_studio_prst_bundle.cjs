'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'PocketMasterStudio.html'), 'utf8');
const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].map(match => match[1]);

test('distributed HTML embeds the current PRST Lab JS bridge, not a stale build', () => {
  for (const [file, exposed] of [
    ['native_prst_patch.js', 'window.PMPRSTNative=module.exports'],
    ['sonicmaster_to_prst.js', 'window.PRSTConvert=module.exports'],
  ]) {
    const source = fs.readFileSync(path.join(root, 'tools', file), 'utf8')
      .replace(/^#![^\n]*\n/, '');
    const bundled = scripts.find(text => text.includes(exposed));
    assert.ok(bundled, 'missing embedded module: ' + file);
    assert.ok(bundled.includes(source), 'stale embedded module: ' + file);
    new vm.Script(bundled, {filename: 'embedded:' + file});
  }
  assert.ok(html.includes('User IR 1..5: native'), 'native User IR support absent from HTML');
});

test('Void MOD policy is embedded before the live PMBuild module', () => {
  // Identify the actual bundled source modules, not mutable header comments.
  // This remains valid when the policy is renamed or its description changes.
  const policySource=fs.readFileSync(path.join(root,'src/void_policy.js'),'utf8');
  const builderSource=fs.readFileSync(path.join(root,'src/pmbuild.js'),'utf8');
  const policyAt=scripts.findIndex(text => text.includes(policySource));
  const buildAt=scripts.findIndex(text => text.includes(builderSource));
  assert.ok(policyAt>=0, 'missing or outdated embedded Void policy');
  assert.ok(buildAt>policyAt, 'missing PMBuild or wrong policy-before-build script order');
  assert.ok(scripts[policyAt].includes(policySource),'outdated embedded Void policy');
  assert.ok(scripts[buildAt].includes(builderSource),'outdated embedded PMBuild');
  const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
  assert.ok(scripts.some(x=>x.includes(app)),'outdated embedded Studio controller');
  const appendixScript=scripts.find(x=>x.includes('window.PMVoidModReadme = '));
  assert.ok(appendixScript,'Void MOD README not bundled into older payload support');
  const appendix=fs.readFileSync(path.join(root,'docs/VOID_MOD.md'),'utf8');
  assert.ok(appendixScript.includes(JSON.stringify(appendix)));
});

test('Void MOD v0.4.1 includes NAM tab, static app and detached config storage',()=>{
 const files=['src/void_policy.js','src/void_config_io.js','src/void_nam_ui.js','src/prst_studio_ui.js'];
 for(const file of files){
  const code=fs.readFileSync(path.join(root,file),'utf8');
  assert.ok(scripts.some(x=>x.includes(code)),file+' is stale inside compiled HTML');
 }
 assert.match(html,/Void&#39;s MOD v0\.4\.1/);
 assert.match(html,/Save config/);
 const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
 assert.ok(app.includes('label: "NAM/Clone"'),'NAM/Clone top-level nav missing');
 const ignored=fs.readFileSync(path.join(root,'.gitignore'),'utf8');
 assert.match(ignored,/^\/config\/$/m);
 assert.match(html,/studio_state\.json/);
});

test('native PRST importer is in the standalone HTML and shared library bindings are live',()=>{
  const importer=fs.readFileSync(path.join(root,'src/prst_import.js'),'utf8');
  const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
  const policy=fs.readFileSync(path.join(root,'src/pmbuild.js'),'utf8');
  assert.ok(scripts.some(s=>s.includes(importer)),'stale or missing PRST importer');
  assert.ok(scripts.some(s=>s.includes(app)),'stale app controller');
  assert.ok(scripts.some(s=>s.includes(policy)),'stale library generator');
  assert.match(html,/id="importNativeBtn"/);
  assert.match(html,/id="importNativeFile"/);
  assert.match(html,/id="nativePrstList"/);
  assert.ok(app.includes('Native().asBatches('),'native library not merged');
  assert.ok(app.includes('importNativeFiles('),'native import UI not wired');
  assert.ok(app.includes('prst_imports: S.payload.prst_imports || []'),'binary imports not persisted');
  assert.ok(app.includes('refreshNativeEditor()'),'Editor catalog not refreshed');
  assert.match(html,/v0\.4\.0/);
  const appendix=fs.readFileSync(path.join(root,'docs/VOID_MOD.md'),'utf8');
  assert.match(appendix,/native PRST import into the shared library/);
});

test('all .prst controls are moved from Studio Overview into the .prst Lab submenu',()=>{
  const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
  const exportUI=fs.readFileSync(path.join(root,'src/prst_studio_ui.js'),'utf8');
  const builder=fs.readFileSync(path.join(root,'src/build_studio.js'),'utf8');
  const policy=require('../src/void_policy.js');
  assert.equal(policy.MOD_VERSION,'0.4.1');

  // The desktop nav and mobile menu share MAIN; the label must be present there.
  assert.match(app,/id: "prst", label: "\.prst Lab"/);
  assert.match(app,/if \(id === "prst"\) \{/);
  assert.match(app,/id="prst-pane-import"/);
  assert.match(app,/id="prst-pane-export"/);
  assert.match(app,/data-prst-pane="import"/);
  assert.match(app,/data-prst-pane="export"/);
  assert.match(app,/window\.PMPRSTExportUI\.mount\(view\.querySelector\("#prst-pane-export"\)\)/);
  assert.match(app,/renderNativeImports\(\)/);
  assert.match(app,/view\.querySelector\("#importNativeFile"\)/);
  assert.match(app,/view\.querySelector\("#nativePrstList"\)/);

  const overview=html.match(/<section class="panel" id="panel-overview">([\s\S]*?)<\/section>/);
  assert.ok(overview,'Studio Overview panel missing');
  assert.doesNotMatch(overview[1],/nativePrstImport|native-prst-export|importNativeBtn|importNativeFile|nativePrstList/);
  assert.doesNotMatch(builder,/id="nativePrstImport"/);
  assert.match(exportUI,/window\.PMPRSTExportUI = Object\.freeze\(\{ mount \}\)/);
  assert.doesNotMatch(exportUI,/panel-overview/);
  const isolated={window:{}};
  vm.runInNewContext(exportUI,isolated,{filename:'prst_studio_ui.js'});
  assert.equal(typeof isolated.window.PMPRSTExportUI.mount,'function');
  // No automatic mutation of Overview at script evaluation.
  assert.doesNotMatch(exportUI,/DOMContentLoaded/);
  assert.ok(scripts.some(code=>code.includes(exportUI)),'compiled exporter is out of sync');
  assert.ok(scripts.some(code=>code.includes(app)),'compiled controller is out of sync');
  assert.match(html,/Void&#39;s MOD v0\.4\.1/);
  assert.match(html,/\.prst Lab/);
  const doc=fs.readFileSync(path.join(root,'docs/VOID_MOD.md'),'utf8');
  assert.match(doc,/v0\.4\.1 — dedicated \.prst Lab submenu/);
});

test('distributed HTML embeds exact authentic Normal and Clone-ON donor bytes', () => {
  const assetJs = scripts.find(text => text.includes('window.PMPRSTAssets = '));
  assert.ok(assetJs, 'missing embedded PRST assets');
  const match = assetJs.match(/window\.PMPRSTAssets = ([\s\S]+?);\s*$/);
  assert.ok(match, 'unreadable embedded PRST assets');
  const assets = JSON.parse(match[1]);
  for (const [field, filename] of [
    ['templateBase64', 'pocket_master_reference.prst'],
    ['cloneTemplateBase64', 'pocket_master_clone_reference.prst']
  ]) {
    assert.equal(typeof assets[field], 'string');
    const expected = fs.readFileSync(path.join(root, 'templates', filename));
    assert.deepEqual(Buffer.from(assets[field], 'base64'), expected, 'reference mismatch: ' + filename);
  }
});
