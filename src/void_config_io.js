// Void's MOD: separate on-disk JSON config, never self-modify PocketMasterStudio.html.
// Browser requires explicit File System Access permission to the project root.
(function(root,factory){
  if(typeof module==="object"&&module.exports)module.exports=factory();
  else root.PMVoidConfigIO=factory();
})(typeof self!=="undefined"?self:this,function(){
"use strict";
const STATE_NAME="studio_state.json",NAM_NAME="nam_clone.json",DB="pm-void-config-handles";
let folder=null, rootFolder=null, projectName="",queue=Promise.resolve();
const available=()=>typeof window!=="undefined"&&typeof window.showDirectoryPicker==="function";
async function dbOpen(){
 return new Promise((resolve,reject)=>{
  const req=indexedDB.open(DB,1);
  req.onupgradeneeded=()=>req.result.createObjectStore("handles");
  req.onsuccess=()=>resolve(req.result);
  req.onerror=()=>reject(req.error);
 });
}
async function dbAction(mode,action){
 const db=await dbOpen();
 try{return await new Promise((resolve,reject)=>{
  const tx=db.transaction("handles",mode);
  const request=action(tx.objectStore("handles"));
  request.onsuccess=()=>resolve(request.result);
  request.onerror=()=>reject(request.error);
 });}finally{db.close()}
}
async function remember(handle){
 try{await dbAction("readwrite",store=>store.put(handle,"project-root"))}catch(e){/* file:// storage may be unavailable */ }
}
async function recalled(){
 try{return await dbAction("readonly",store=>store.get("project-root"))}catch(e){return null}
}
async function grant(handle,interactive){
 try{
  let permission=await handle.queryPermission({mode:"readwrite"});
  if(permission!=="granted"&&interactive)permission=await handle.requestPermission({mode:"readwrite"});
  return permission==="granted";
 }catch(e){return false}
}
async function openFolder(handle,interactive=false){
 if(!await grant(handle,interactive))return false;
 folder=await handle.getDirectoryHandle("config",{create:true});
 rootFolder=handle;
 projectName=handle.name||"project";
 return true;
}
async function restore(){
 if(!available())return false;
 const handle=await recalled();
 if(!handle)return false;
 return openFolder(handle,false);
}
async function connect(){
 if(!available())throw Error("Chrome/Edge File System Access is required; download JSON backups instead");
 // Must be called directly from a button click; browsers require a user gesture.
 const handle=await window.showDirectoryPicker({id:"pocketmaster-void-config",mode:"readwrite"});
 if(!await openFolder(handle,true))throw Error("Read/write permission was not granted");
 await remember(handle);
 return load();
}
async function readJSON(filename){
 if(!folder)return null;
 try{const handle=await folder.getFileHandle(filename);
   return JSON.parse(await (await handle.getFile()).text());
 }catch(e){if(e.name==="NotFoundError")return null;throw e}
}
async function load(){
 if(!folder)return null;
 const [state,nam]=await Promise.all([readJSON(STATE_NAME),readJSON(NAM_NAME)]);
 return {state,nam};
}
async function save(data){
 if(!folder)throw Error("Project folder not connected");
 // Serial writes make rapid edits safe; latest write wins.
 const namJSON=JSON.stringify(data.nam,null,2)+"\n";
 const stateJSON=JSON.stringify(data.state,null,2)+"\n";
 const perform=async()=>{
  for(const [file,body] of [[NAM_NAME,namJSON],[STATE_NAME,stateJSON]]){
    const handle=await folder.getFileHandle(file,{create:true});
    const w=await handle.createWritable();try{await w.write(body)}finally{await w.close()}
  }
 };
 queue=queue.catch(()=>{}).then(perform);
 return queue;
}
// Explicit debug exports use the already-authorized project root.
 // Never serve or auto-upload logs, and never overwrite an existing log file.
 const LOG_NAME=/^PocketMasterStudio_debug_\d{8}_\d{6}_[a-z0-9]{6}\.log$/;
 async function saveLog(filename,body){
   if(!rootFolder||!folder)throw Error("Connect project folder first to save logs/");
   if(!LOG_NAME.test(filename))throw Error("Invalid debug log filename");
   if(typeof body!=="string")throw Error("Debug log must be text");
   const dir=await rootFolder.getDirectoryHandle("logs",{create:true});
   try{await dir.getFileHandle(filename);throw Error("Log filename already exists; export again");}
   catch(e){if(e.name!=="NotFoundError")throw e;}
   const file=await dir.getFileHandle(filename,{create:true});
   const writer=await file.createWritable();
   try{await writer.write(body);}finally{await writer.close();}
   return "logs/"+filename;
 }
 const connected=()=>!!folder;
const location=()=>connected()?projectName+"/config/":"not connected";
return Object.freeze({available,connected,location,restore,connect,load,save,saveLog,STATE_NAME,NAM_NAME});
});
