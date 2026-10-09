// Void's MOD — slot-driven full-rig NAM policy. User mappings live in config/nam_clone.json.
(function(root,factory){
  if(typeof module==="object"&&module.exports)module.exports=factory();
  else root.PMVoidPolicy=factory();
})(typeof self!=="undefined"?self:this,function(){
"use strict";
const SCHEMA="void-mod-nam-clone/v1";
const MOD_VERSION="0.3.0";
const BASE_VERSION="0.1 (assumed)";
const AMP_DISPLAY=Object.freeze({
"TWD Deluxe":"Fender Tweed Deluxe","B-Man N":"Fender Bassman — Normal","Dark Twin":"Fender Twin Reverb","Voks 30N":"Vox AC30 — Normal","Jazz 120":"Roland JC-120",
"Brit 45":"Marshall JTM45","Brit 50JP":"Marshall Plexi 50 / JMP","Brit 800":"Marshall JCM800","B-Man B":"Fender Bassman — Bright","Voks 30TB":"Vox AC30 — Top Boost",
"Sol 100 OD":"Soldano SLO-100 — Overdrive","Dizzy VH":"Diezel VH4","Eng 120":"ENGL 120","Halen 51":"Peavey 5150 / EVH","Sol 100 LD":"Soldano SLO-100 — Lead",
"Calif DualV":"Mesa/Boogie Dual Rectifier — Vintage","Calif DualM":"Mesa/Boogie Dual Rectifier — Modern","Eng Power":"ENGL Powerball","Flyman B1+":"Friedman BE-100",
"Bog XT":"Bogner Ecstasy","A BassVT":"Ampeg SVT Bass","Voks Bass":"Vox Bass"
});
const LEGACY_VERIFIED=Object.freeze({"AC30 May":Object.freeze({origin:"VOX AC30 DRIVER",includesCab:true})});
const blank=()=>({ampModel:null,captureName:"",fullRig:false});
const defaults=()=>({schema:SCHEMA,preferClone:true,slots:Array.from({length:5},blank)});
const validAmpNames=catalog=>{
 const mod=catalog?.modules?.find(x=>x.name==="AMP");
 return (mod?.effectIds||[]).map(id=>catalog.effects[String(id)]?.name).filter(Boolean);
};
function normalize(input,validNames){
 if(!input || typeof input!=="object"||Array.isArray(input))throw Error("NAM config must be a JSON object");
 if(input.schema!==SCHEMA)throw Error("Unsupported NAM schema (expected "+SCHEMA+")");
 if(input.preferClone!==true&&input.preferClone!==false)throw Error("preferClone must be boolean");
 if(!Array.isArray(input.slots)||input.slots.length!==5)throw Error("Exactly five NAM slots required");
 const uniqueModels=new Set(),uniqueNames=new Set();
 const slots=input.slots.map((raw,index)=>{
  if(!raw||typeof raw!=="object"||Array.isArray(raw))throw Error("Invalid slot "+(index+1));
  const ampModel=raw.ampModel==null||raw.ampModel===""?null:raw.ampModel;
  if(ampModel===null)return blank();
  if(typeof ampModel!=="string"||!AMP_DISPLAY[ampModel]||validNames&&!validNames.includes(ampModel))throw Error("Unknown Pocket Master AMP model in slot "+(index+1));
  if(uniqueModels.has(ampModel))throw Error("AMP "+ampModel+" is assigned to multiple physical slots");
  uniqueModels.add(ampModel);
  const captureName=raw.captureName;
  if(typeof captureName!=="string"||!captureName.trim()||captureName!==captureName.trim()||captureName.length>64)
   throw Error("Slot "+(index+1)+": enter the exact NAM label used on your pedal (1–64 characters)");
  if(uniqueNames.has(captureName))throw Error("NAM name "+captureName+" is assigned more than once");
  uniqueNames.add(captureName);
  if(raw.fullRig!==true)throw Error("Slot "+(index+1)+": confirm that the installed NAM is full rig (amp + cab + mic)");
  return {ampModel,captureName,fullRig:true};
 });
 return {schema:SCHEMA,preferClone:input.preferClone,slots};
}
function resolveForModel(name,config){
 if(!config || config.preferClone!==true)return null;
 const mapping=normalize(config);
 const index=mapping.slots.findIndex(x=>x.ampModel===name);
 return index<0?null:{slot:index+1,...mapping.slots[index]};
}
function slotMap(config){
 if(!config)return {};
 const c=normalize(config),o={};
 for(let i=0;i<5;i++)if(c.slots[i].ampModel)o[c.slots[i].captureName]=i+1;
 return o;
}
function approvedNames(config){
 return config?Object.keys(slotMap(config)):Object.keys(LEGACY_VERIFIED);
}
function isFullRig(name,config){
 return typeof name==="string" && approvedNames(config).includes(name);
}
function assertFullRig(name,config){
 if(!isFullRig(name,config))throw Error('Void MOD: NAM "'+String(name)+
  '" is not an approved full-rig capture. Configure a slot and explicitly confirm Amp + Cab + Mic, or use Modeled.');
 return name;
}
function enforceClone(preset,config){
 if(!preset||preset.ampMode!=="Clone")return preset;
 const m=preset.modules;
 if(!m||!m.Clone||m.Clone.enabled!==true)throw Error("Void MOD: Clone requires an active Clone block");
 assertFullRig(m.Clone.effect,config);
 if(!m.IR||typeof m.IR!=="object")throw Error("Void MOD: Clone requires an IR block");
 m.IR.enabled=false;
 return preset;
}
return Object.freeze({SCHEMA,MOD_VERSION,BASE_VERSION,AMP_DISPLAY,LEGACY_VERIFIED,
 defaults,validAmpNames,normalize,resolveForModel,slotMap,approvedNames,isFullRig,assertFullRig,enforceClone});
});
