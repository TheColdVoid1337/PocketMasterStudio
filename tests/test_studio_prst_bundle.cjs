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
  const find=(token) => scripts.findIndex(text => text.includes(token));
  const policyAt=find('// Void\'s MOD — hard runtime policy');
  const buildAt=find('// pmbuild.js — in-browser/Node port');
  assert.ok(policyAt>=0 && buildAt>policyAt,'missing policy or wrong script order');
  const policySource=fs.readFileSync(path.join(root,'src/void_policy.js'),'utf8');
  const builderSource=fs.readFileSync(path.join(root,'src/pmbuild.js'),'utf8');
  assert.ok(scripts[policyAt].includes(policySource),'outdated embedded Void policy');
  assert.ok(scripts[buildAt].includes(builderSource),'outdated embedded PMBuild');
  const app=fs.readFileSync(path.join(root,'src/studio_app.js'),'utf8');
  assert.ok(scripts.some(x=>x.includes(app)),'outdated embedded Studio controller');
  const appendixScript=scripts.find(x=>x.includes('window.PMVoidModReadme = '));
  assert.ok(appendixScript,'Void MOD README not bundled into older payload support');
  const appendix=fs.readFileSync(path.join(root,'docs/VOID_MOD.md'),'utf8');
  assert.ok(appendixScript.includes(JSON.stringify(appendix)));
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
