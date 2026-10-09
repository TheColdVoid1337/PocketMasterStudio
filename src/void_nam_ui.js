// Void's MOD NAM/Clone slot editor. Five physical positions, explicit Amp+Cab attestation.
(function(root,factory){
 if(typeof module==="object"&&module.exports)module.exports=factory(require("./void_policy.js"));
 else root.PMVoidNAMUI=factory(root.PMVoidPolicy);
})(typeof self!=="undefined"?self:this,function(policy){
 "use strict";
 const htmlEscape=v=>String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
 function mount(view,{getConfig,catalog,onApply,getSaveStatus,onConnect,onSave,onBackup,onImport}){
  view.classList.add("voidnam");
  view.innerHTML='<div class="void-wrap"><h2>NAM / Clone — Void&#39;s MOD</h2>'+
   '<p class="mut">Configure your five physical User Profile slots. Each slot maps ONE modeled amplifier to the exact NAM label on your pedal. Clone wins for mapped AMPs; unmapped AMPs remain Modeled. Only verified Full Rig (amp + cab + mic) NAM is valid. Built-in IR is always bypassed in Clone.</p>'+
   '<div id="void-io-status" class="note" role="status"></div>'+
   '<div class="row"><button id="void-connect" class="primary">Connect project folder…</button><button id="void-save">Save JSON now</button><button id="void-backup">Download JSON backup</button><button id="void-import">Import JSON…</button><input id="void-import-file" type="file" accept=".json" hidden></div>'+
   '<label class="chk2"><input type="checkbox" id="void-prefer" checked> Prefer configured NAM/Clone over modeled AMP</label>'+
   '<div id="void-slots" class="void-slots"></div>'+
   '<div class="row"><button id="void-apply" class="primary">Apply NAM slots</button></div>'+
   '<div id="void-feedback" class="note" role="status" aria-live="polite"></div>'+
   '<p class="mut">Choose the project root folder (the one containing PocketMasterStudio.html), not config itself. Chrome/Edge creates <code>config/nam_clone.json</code> and <code>config/studio_state.json</code>. Saved changes do not modify the HTML. The config folder is gitignored. File access may require reconnection after reopening the browser.</p></div>';
  const $=s=>view.querySelector(s);
  const models=policy.validAmpNames(catalog);
  if(!models.length)throw Error("AMP catalog missing");
  const rows=$("#void-slots");
  function render(){
   const config=getConfig()||policy.defaults();
   $("#void-prefer").checked=config.preferClone!==false;
   rows.innerHTML=config.slots.map((entry,index)=>{
    const selected=entry.ampModel||"";
    const opts=['<option value="">— Not assigned (Modeled fallback) —</option>',
      ...models.map(model=>'<option value="'+htmlEscape(model)+'"'+(model===selected?' selected':'')+'>'+
        htmlEscape(policy.AMP_DISPLAY[model]||model)+'  ·  '+htmlEscape(model)+'</option>')].join("");
    return '<div class="void-slot" data-slot="'+index+'"><div class="void-slot-num">Slot '+(index+1)+' <span class="mut">User Profile '+(index+1)+'</span></div>'+
     '<label>Modeled amplifier (actual model)</label><select class="void-amp">'+opts+'</select>'+
     '<label>Exact NAM name on your pedal</label><input class="void-name" maxlength="64" placeholder="e.g. My JCM800 Rig" value="'+htmlEscape(entry.captureName||"")+'">'+
     '<label class="chk2"><input class="void-fullrig" type="checkbox"'+(entry.fullRig?' checked':'')+'> I verified this installed NAM contains amp + cabinet + mic (Full Rig)</label></div>';
   }).join("");
  }
  function status(){const s=getSaveStatus();$("#void-io-status").textContent=s||""}
  function draft(){
   return {schema:policy.SCHEMA,preferClone:$("#void-prefer").checked,
    slots:[...rows.querySelectorAll(".void-slot")].map(el=>({
     ampModel:el.querySelector(".void-amp").value||null,
     captureName:el.querySelector(".void-name").value.trim(),
     fullRig:el.querySelector(".void-fullrig").checked
    }))};
  }
  $("#void-apply").onclick=()=>{
   try{
    const config=policy.normalize(draft(),models);
    onApply(config);
    $("#void-feedback").textContent="Applied. Active Clone assignments: "+config.slots.filter(x=>x.ampModel).length+"/5. Other amps use Modeled.";
    render();status();
   }catch(e){$("#void-feedback").textContent="Not applied: "+e.message}
  };
  $("#void-connect").onclick=async()=>{try{await onConnect();render();status();$("#void-feedback").textContent="Connected to config/."}
   catch(e){if(e.name!=="AbortError")$("#void-feedback").textContent=e.message}};
  $("#void-save").onclick=async()=>{try{await onSave();status()}catch(e){$("#void-feedback").textContent=e.message}};
  $("#void-backup").onclick=()=>onBackup();
  $("#void-import").onclick=()=>$("#void-import-file").click();
  $("#void-import-file").onchange=async e=>{const f=e.target.files[0];e.target.value="";if(!f)return;
   try{await onImport(f);render();status();$("#void-feedback").textContent="JSON imported and applied."}
   catch(err){$("#void-feedback").textContent="Import failed: "+err.message}};
  render();status();
  return Object.freeze({render,status});
 }
 return Object.freeze({mount});
});
