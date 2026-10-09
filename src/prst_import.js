// PRST -> PocketMasterStudio library bridge (Void's MOD).
// Original native bytes remain canonical; decoded effects are an editable-looking
// catalog view only, never used to silently regenerate an imported binary.
(function(root,factory) {
  if(typeof module==="object"&&module.exports)module.exports=factory(
    require("../tools/prst_clone_slots.js"),require("../tools/native_prst_patch.js"));
  else root.PMPRSTImport=factory(root.PRSTCloneSlots,root.PMPRSTNative);
})(typeof self!=="undefined"?self:this,function(slots,native) {
  "use strict";
  const MODS=native.MODS;
  const requireThat=(v,m)=>{if(!v)throw Error(m)};
  const bytesOf=x=>x instanceof Uint8Array?Uint8Array.from(x):
    x instanceof ArrayBuffer?new Uint8Array(x):new Uint8Array(x.buffer,x.byteOffset,x.byteLength);
  const fromBase64=s=>{
    requireThat(typeof s==="string"&&/^[a-zA-Z0-9+/]+={0,2}$/.test(s),"Invalid native base64");
    if(typeof Buffer!=="undefined")return Uint8Array.from(Buffer.from(s,"base64"));
    return Uint8Array.from(atob(s),c=>c.charCodeAt(0));
  };
  const toBase64=b=>{
    const x=bytesOf(b);
    if(typeof Buffer!=="undefined")return Buffer.from(x).toString("base64");
    let bin="";for(const n of x)bin+=String.fromCharCode(n);
    return btoa(bin);
  };
  function modelFields(catalog,module,effect){
    const group=catalog.modules.find(m=>m.name===module);
    const m=group?.effectIds?.map(id=>catalog.effects[String(id)]).find(m=>m?.name===effect);
    return m?.parameters||null;
  }
  function identify(module,sel,{catalog,fxNative}){
    if(module==="NR")return "Gate";
    if(module==="IR"){
      if(sel[1]===0&&sel[2]===0x10&&sel[3]===0x0A&&sel[0]<5)return "User IR "+(sel[0]+1);
      if(sel[1]!==0||sel[2]!==0||sel[3]!==0x0A)return null;
    }
    if(module==="FX1"||module==="FX2"){
      const hex=[...sel].map(b=>b.toString(16).padStart(2,"0")).join("").toUpperCase();
      const matches=Object.entries(fxNative.models[module]||{})
        .filter(([,v])=>v.prst_selector?.toUpperCase()===hex).map(([name])=>name);
      return matches.length===1?matches[0]:null;
    }
    const matches=Object.entries(native.CODES[module]||{})
      .filter(([,v])=>v===sel[0]).map(([name])=>name);
    return matches.length===1?matches[0]:null;
  }
  function digest(raw){
    let h=2166136261;for(const x of raw){h^=x;h=Math.imul(h,16777619)}
    return (h>>>0).toString(16).padStart(8,"0");
  }
  function decode(raw,{catalog,fxNative,voidConfig}={}){
    requireThat(catalog?.effects&&Array.isArray(catalog.modules)&&fxNative?.models,
      "PRST decoder requires official effect and FX catalogs");
    const b=bytesOf(raw),state=slots.inspect(b),v=new DataView(b.buffer,b.byteOffset,b.byteLength);
    // refuse structures that are not the known native 10-selector/320-float layout.
    requireThat(v.getUint16(121,true)===0x3002&&v.getUint16(123,true)===10&&
      v.getUint16(137,true)===40&&v.getUint16(181,true)===320,
      "Unknown PRST selector or parameter record layout");
    const name=String.fromCharCode(...b.slice(25,41)).split("\0")[0].trim();
    requireThat(name.length>0,"PRST has no preset name");
    const chain=[...b.slice(125,135)].map(i=>MODS[i]);
    requireThat(chain.length===10&&chain.every(Boolean)&&new Set(chain).size===10,
      "Unknown PRST signal-chain order");
    const isClone=state.cloneEnabled;
    requireThat(!isClone||state.selectorKnown,"Clone selector is unknown");
    const volume=v.getUint32(97,true);
    requireThat(volume<=100,"Invalid PRST preset volume");
    const bpm=v.getUint32(105,true);
    const warnings=[],modules={};
    const mask=v.getUint32(117,true);
    for(let i=0;i<9;i++){
      const module=MODS[i],enabled=Boolean(mask&(1<<i));
      if(isClone&&module==="AMP")continue; // AMP donor record remains but is bypassed.
      const selector=b.slice(139+4*i,143+4*i);
      let model=identify(module,selector,{catalog,fxNative});
      if(!model){
        const code=[...selector].map(x=>x.toString(16).padStart(2,"0").toUpperCase()).join("");
        if(enabled&&!(isClone&&module==="IR")){
          // Read-only library imports preserve the original .prst exactly.
          // Never invent a catalog effect for an unknown ACTIVE selector.
          model="Unknown native "+module+" ["+code+"]";
          warnings.push(module+": unknown ACTIVE selector "+code+
            "; decoded editor model unavailable, original PRST preserved");
        }else{
          const group=catalog.modules.find(m=>m.name===module);
          model=catalog.effects[String(group?.effectIds?.[0])]?.name;
          requireThat(model,"No safe disabled placeholder for "+module);
          warnings.push(module+": unknown inactive model selector; original bytes retained");
        }
      }
      const fields=model.startsWith("Unknown native ")?[]:modelFields(catalog,module,model);
      requireThat(fields,"Unknown catalog effect "+module+"."+model);
      const values={};
      for(const field of fields){
        const n=v.getFloat32(183+32*i+4*field.algId,true);
        if(enabled&&!Number.isFinite(n))throw Error("Non-finite "+module+"."+field.name);
        values[field.name]=Number.isFinite(n)?n:field.default;
      }
      modules[module]={enabled:isClone&&module==="IR"?false:enabled,effect:model,parameters:values};
      if(isClone&&module==="IR"&&enabled)warnings.push("Clone IR toggle was ON in file, but onboard IR is inaudible; displayed as OFF");
    }
    if(isClone){
      const configured=voidConfig?.slots?.[state.cloneSlot-1];
      const matched=configured?.fullRig&&configured.captureName;
      const effect=matched?configured.captureName:"Unmapped User Profile "+state.cloneSlot;
      modules.Clone={enabled:true,effect,parameters:{}};
      const i=9;
      const group=catalog.modules.find(m=>m.name==="Clone");
      const spec=catalog.effects[String(group?.effectIds?.[state.cloneSlot-1])];
      const fields=spec?.parameters||[];
      for(const field of fields){
        const n=v.getFloat32(183+32*i+4*field.algId,true);
        if(Number.isFinite(n))modules.Clone.parameters[field.name]=n;
      }
      if(!matched)warnings.push("Clone slot "+state.cloneSlot+" has no confirmed Full Rig NAM mapping; native file is stored unchanged");
    }
    const fingerprint=digest(b);
    const preset={
      version:"1.0",presetName:name,ampMode:isClone?"Clone":"Normal",
      presetVolume:volume,...(bpm>=40&&bpm<=260?{presetBpm:bpm}:{}),
      signalChain:chain.slice(0,9),modules,
      description:"Native PRST import: "+name+" (binary original retained)",
      metadata:{createdDate:"",author:"SONICLINK PRST import",tags:["prst","void-mod"]},
      nativeImport:{id:fingerprint,rawBase64:toBase64(b),cloneSlot:isClone?state.cloneSlot:null,
        readOnly:true,warnings}
    };
    return {preset,id:fingerprint,warnings,bytes:b,rawBase64:preset.nativeImport.rawBase64};
  }
  function record(raw,filename,options){
    const parsed=decode(raw,options);
    return {id:parsed.id,filename:String(filename||"preset.prst").slice(0,200),
      rawBase64:parsed.rawBase64,warnings:parsed.warnings};
  }
  function asBatches(records,options){
    requireThat(Array.isArray(records),"PRST Imports must be an array");
    const result={};
    const seen=new Set();
    records.forEach((entry,index)=>{
      requireThat(entry&&typeof entry==="object"&&typeof entry.rawBase64==="string",
        "Invalid saved PRST record "+index);
      const p=decode(fromBase64(entry.rawBase64),options);
      requireThat(p.id===entry.id,"Saved native PRST fingerprint mismatch "+index);
      requireThat(!seen.has(p.id),"Duplicate imported PRST record "+p.id);
      seen.add(p.id);
      const i=Math.floor(index/50)+1,artist="PRST Imports "+String(i).padStart(3,"0");
      const filename=artist+".json";
      const file=result[filename]||(result[filename]={
        type:"PocketMasterBatch",version:"1.0",artist,exported:"native-import",
        presets:[],count:0});
      const preset=p.preset;
      preset.artist=artist;
      preset.song="prst_"+p.id;
      preset.kind="N";
      preset.description="Imported "+(entry.filename||"PRST")+" — "+preset.ampMode+
        (p.warnings.length?"; "+p.warnings.join("; "):"");
      file.presets.push(preset);file.count++;
    });
    return result;
  }
  function add(records,newRecord){
    requireThat(Array.isArray(records),"PRST imports must be an array");
    if(records.some(x=>x.id===newRecord.id)){
      const current=records.find(x=>x.id===newRecord.id);
      requireThat(current.rawBase64===newRecord.rawBase64,"PRST fingerprint collision");
      return {records,added:false};
    }
    return {records:[...records,newRecord],added:true};
  }
  return Object.freeze({decode,record,asBatches,add,fromBase64,toBase64,digest});
});