#!/usr/bin/env node
/* Import PocketMasterStudio/SonicMaster v1.0 presets as native 515-byte PRST.
 * Native codec only: no Python, Bluetooth, network, or NAM upload.
 * Capture names are mapped to physical slots using a REQUIRED user-provided JSON map.
 */
'use strict';
const {write,MODS} = require('./native_prst_patch.js');
const slots = require('./prst_clone_slots.js');
const voidPolicy = require('../src/void_policy.js');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const SLOTS = MODS.slice(0,9);
const isObj = x => !!x && typeof x === 'object' && !Array.isArray(x);
function requireThat(ok, msg) { if (!ok) throw Error(msg); }
function checkMap(map) {
  requireThat(isObj(map), 'Provide a name-to-slot JSON map, e.g. {"JCM800":2,"Plexi":3}');
  const seen = new Set();
  for (const [name, slot] of Object.entries(map)) {
    requireThat(name.trim() === name && name.length>0, 'Empty or whitespace-padded NAM name');
    requireThat(Number.isInteger(slot) && slot>=1 && slot<=5, 'Invalid physical slot for '+name);
    requireThat(!seen.has(slot), 'Multiple NAM names claim physical slot '+slot);
    seen.add(slot);
  }
  return map;
}
function unpack(doc) {
  if (isObj(doc) && doc.version==='1.0' && isObj(doc.modules)) return [doc];
  if (isObj(doc) && doc.type==='PocketMasterBatch' && doc.version==='1.0' && Array.isArray(doc.presets) && doc.presets.length)
    return doc.presets;
  throw Error('Expected single v1.0 preset or PocketMasterBatch v1.0');
}
function convert(preset, donor, {catalog, fxNative, namSlots, overrideName}={}) {
  requireThat(isObj(preset) && preset.version==='1.0' && isObj(preset.modules), 'Malformed v1.0 preset');
  const clone = preset.ampMode==='Clone';
  requireThat(clone || preset.ampMode==='Normal', 'Unsupported ampMode '+preset.ampMode);
  const name = overrideName ?? preset.presetName;
  requireThat(typeof name==='string' && /^[\x20-\x7e]{1,10}$/.test(name), 'Use a unique 1–10-character ASCII presetName');
  requireThat(Number.isInteger(preset.presetVolume) && preset.presetVolume>=0 && preset.presetVolume<=100, name+': invalid presetVolume');
  const bpm = preset.presetBpm;
  if (bpm !== undefined)
    requireThat(Number.isInteger(bpm) && bpm>=40 && bpm<=260, name+': invalid presetBpm');
  requireThat(Array.isArray(preset.signalChain) && preset.signalChain.length===9 &&
    new Set(preset.signalChain).size===9 && SLOTS.every(s=>preset.signalChain.includes(s)), name+': signalChain must contain nine distinct modules');
  requireThat(Object.keys(preset.modules).every(s=>MODS.includes(s)), name+': unknown module key');
  requireThat(Object.keys(preset.modules).every(s=>s==='AMP' ? !clone : true), name+': Clone JSON must not include AMP block');
  requireThat(isObj(catalog) && isObj(catalog.effects) && Array.isArray(catalog.modules), 'Official effects catalog required');
  requireThat(isObj(fxNative) && isObj(fxNative.models), 'Official FX selector catalog required');
  const changes={name,preset_volume:preset.presetVolume,bpm,models:{},parameters:{},enabled:{},signal_chain:[...preset.signalChain,'Clone']};
  const warnings=[];
  if (clone) {
    checkMap(namSlots);
    const entry=preset.modules.Clone;
    requireThat(isObj(entry) && entry.enabled===true && typeof entry.effect==='string', name+': enabled Clone module and effect name required');
    voidPolicy.assertFullRig(entry.effect);
    requireThat(Object.hasOwn(namSlots,entry.effect), name+': NAM "'+entry.effect+'" has no assigned slot in --nam-slots');
    changes.clone_slot=namSlots[entry.effect];
    changes.enabled.Clone=true;
    const props=entry.parameters;
    requireThat(isObj(props), name+': Clone parameters object required');
    changes.parameters.Clone=props;
    warnings.push('Clone '+entry.effect+' uses physical User Profile '+changes.clone_slot+'; capture itself is NOT embedded');
  } else {
    requireThat(!('Clone' in preset.modules), name+': Normal preset unexpectedly includes Clone block');
    changes.enabled.Clone=false;
    requireThat(isObj(preset.modules.AMP) && preset.modules.AMP.enabled, name+': active modeled AMP required');
  }
  for(const module of SLOTS) {
    if (clone && module==='AMP') continue; // preserve genuine donor AMP bytes and bit; real Clone exports keep bit 3 set.
    const item=preset.modules[module];
    requireThat(isObj(item) && typeof item.enabled==='boolean', name+': missing or invalid '+module+'.enabled');
    // Firmware UI permits IR toggle in Clone, but the block is not audible.
    // Always encode IR OFF for Clone, even when importing old JSON with IR ON.
    const active = clone && module==='IR' ? false : item.enabled;
    if (clone && module==='IR' && item.enabled) warnings.push('Void MOD: ignored inaudible Clone IR ON flag; encoding IR OFF');
    changes.enabled[module]=active;
    if (!active) continue;
    requireThat(typeof item.effect==='string' && isObj(item.parameters), name+': '+module+' effect and parameters required');
    // User IR 1..5: native [index, 00, 10, 0A], verified by five device exports.
    if(module!=='NR')changes.models[module]=item.effect;
    changes.parameters[module]=item.parameters;
    if((module==='FX1'||module==='FX2')) warnings.push(module+' selector is catalog-inferred; verify SONICLINK import');
  }
  const output=write(donor,changes,{catalog,fxNative});
  const parsed=slots.inspect(output);
  const storedName=String.fromCharCode(...output.subarray(25,41)).split('\0')[0];
  requireThat(storedName===name && parsed.cloneEnabled===clone,name+': output failed validation');
  if (clone) {
    requireThat(parsed.cloneSlot===changes.clone_slot, name+': wrong native Clone slot');
    const view = new DataView(output.buffer,output.byteOffset,output.byteLength);
    requireThat((view.getUint32(117,true)&0x10)===0, name+': Clone IR must be disabled');
  }
  return {bytes:output,changes,warnings};
}
function collect(doc,donor,options) {
  const all=unpack(doc);
  requireThat(all.every(x=>isObj(x) && x.version==='1.0'), 'Every batch item must be v1.0');
  const selected=options.select===undefined?all:all.filter(x=>x.presetName===options.select);
  requireThat(selected.length && (options.select===undefined || selected.length===1),'--select must identify exactly one preset');
  requireThat(options.overrideName===undefined || selected.length===1,'--name only allowed with one preset');
  return selected.map((preset,index)=>({index,sourceName:preset.presetName,...convert(preset,options.donorForPreset ? options.donorForPreset(preset) : donor,options)}));
}

// Stock and Clone reference are separate authentic SONICLINK exports. In a mixed
// batch, choose a donor for EACH preset, never a single synthetic Clone-ON donor.
function selectDonor(preset,{stock,clone,custom}={}) {
  const useClone=preset.ampMode==='Clone';
  const donor=custom||(useClone?clone:stock);
  requireThat(donor,'No '+(useClone?'Clone':'Modeled')+' PRST reference available');
  const state=slots.inspect(donor);
  if(!custom)requireThat(state.cloneEnabled===useClone,
    'Bundled '+(useClone?'Clone':'Modeled')+' reference has wrong amp mode');
  return donor;
}
function parseArgs(args){
  const result={};let input;
  const opts={'--donor':'donor','--nam-slots':'namSlots','--select':'select','-o':'output','--output':'output','--out-dir':'outDir','--name':'overrideName'};
  for(let i=0;i<args.length;i++){
    const arg=args[i];
    if(arg==='--help'||arg==='-h')return {help:true};
    if(arg==='--bundled-template'){
      requireThat(result.bundledTemplate===undefined,'Duplicate --bundled-template');
      result.bundledTemplate=true;
      continue;
    }
    if(Object.hasOwn(opts,arg)) {
      requireThat(args[i+1]!==undefined && !args[i+1].startsWith('--'),arg+' requires a value');
      requireThat(result[opts[arg]]===undefined,'Duplicate argument '+arg);
      result[opts[arg]]=args[++i];
    } else if(arg.startsWith('-'))throw Error('Unknown option '+arg);
    else { requireThat(input===undefined,'Only one input file allowed');input=arg; }
  }
  requireThat(input && !(result.donor && result.bundledTemplate) && (!!result.output !== !!result.outDir),
    'Specify INPUT, exactly one output target and do not combine --donor with --bundled-template');
  result.input=input;return result;
}
function main(argv){
  const args=parseArgs(argv);
  if(args.help){console.log('Usage: node tools/sonicmaster_to_prst.js INPUT.json --donor TEMPLATE.prst --nam-slots NAM_SLOTS.json --out-dir OUTPUT_DIR\n   or: node tools/sonicmaster_to_prst.js INPUT.json --donor TEMPLATE.prst --nam-slots NAM_SLOTS.json --select "Preset" -o OUTPUT.prst\nDonor .prst is optional: genuine SONICLINK Modeled/Clone references are selected per preset.\n--bundled-template is a compatibility alias for automatic reference selection.\nRequires explicit NAM slots for Clone presets. Generated output still needs SONICLINK import/readback testing. Outputs never overwrite files.');return;}
  // Works both inside PRST-Lab/integrations/pocketmasterstudio/tools and in
  // PocketMasterStudio/tools after vendoring the three JS sources unchanged.
  const base=[path.resolve(__dirname,'..'),path.resolve(__dirname,'../../..')]
    .find(dir=>fs.existsSync(path.join(dir,'catalog/effects.json')) &&
      fs.existsSync(path.join(dir,'templates/pocket_master_reference.prst')));
  requireThat(base,'Cannot find repository root (catalog/ and templates/)');
  const catalog=JSON.parse(fs.readFileSync(path.join(base,'catalog/effects.json'),'utf8'));
  const fxNative=JSON.parse(fs.readFileSync(path.join(base,'catalog/fx_native.json'),'utf8'));
  const namSlots=args.namSlots?JSON.parse(fs.readFileSync(args.namSlots,'utf8')):undefined;
  const doc=JSON.parse(fs.readFileSync(args.input,'utf8'));
  const references=args.donor
    ? {custom:fs.readFileSync(args.donor)}
    : {
        stock:fs.readFileSync(path.join(base,'templates/pocket_master_reference.prst')),
        clone:fs.readFileSync(path.join(base,'templates/pocket_master_clone_reference.prst'))
      };
  // Validate both bundled references (and user-supplied donors) before writing anything.
  if(references.stock)requireThat(!slots.inspect(references.stock).cloneEnabled,'Invalid stock reference');
  if(references.clone)requireThat(slots.inspect(references.clone).cloneEnabled,'Invalid Clone-ON reference');
  if(references.custom)slots.inspect(references.custom);
  const items=collect(doc,null,{catalog,fxNative,namSlots,select:args.select,
    overrideName:args.overrideName,donorForPreset:p=>selectDonor(p,references)});
  if(!args.donor)console.error('NOTICE: Using genuine bundled Modeled/Clone SONICLINK references per preset; verify import/readback and sound on the pedal.');
  requireThat(!args.output || items.length===1,'Multiple presets require --out-dir');
  const files=items.map((p,i)=>args.output?args.output:path.join(args.outDir,
    String(i+1).padStart(3,'0')+'_'+p.changes.name.replace(/[^a-zA-Z0-9_-]/g,'_')+'.prst'));
  const resolved=files.map(f=>path.resolve(f));
  requireThat(new Set(resolved).size===resolved.length,'Output path collision');
  for(const f of resolved)requireThat(!fs.existsSync(f),'Refusing overwrite: '+f);
  // Every conversion and output path is validated before writing the first file.
  for(let i=0;i<items.length;i++){
    fs.mkdirSync(path.dirname(resolved[i]),{recursive:true});
    fs.writeFileSync(resolved[i],items[i].bytes,{flag:'wx'});
    console.log(items[i].sourceName+' => '+resolved[i]+ '  '+(items[i].changes.clone_slot?'NAM slot '+items[i].changes.clone_slot:'modeled')+' CRC OK');
    for(const w of items[i].warnings)console.error('  NOTICE: '+w);
  }
}
module.exports=Object.freeze({checkMap,unpack,convert,collect,selectDonor,parseArgs,main});
if(require.main===module){try{main(process.argv.slice(2));}catch(e){console.error('Conversion failed: '+e.message);process.exitCode=1;}}
