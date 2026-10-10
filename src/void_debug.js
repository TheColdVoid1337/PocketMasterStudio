// Shared application log — kept in memory and exported only on demand.
(function(root,factory){
 if(typeof module==="object"&&module.exports)module.exports=factory();
 else root.PMVoidDebug=factory();
})(typeof self!=="undefined"?self:this,function(){
 "use strict";
 const LIMIT=1500, entries=[],started=new Date().toISOString();
 let ready=false,visible=false,editorWindow=null;
 const levels=["DEBUG","INFO","WARN","ERROR"];
 const safe=x=>{
  if(x instanceof Error)return String(x.stack||x.message).slice(0,3000);
  if(typeof x==="string")return x.slice(0,3000);
  try{return JSON.stringify(x).slice(0,3000)}catch(e){return String(x).slice(0,3000)}
 };
 const $=id=>document.getElementById(id);
 function event(source,message,level="INFO"){
  const e={time:new Date().toISOString(),level:levels.includes(level)?level:"INFO",
   source:String(source).slice(0,32),message:safe(message)};
  entries.push(e);if(entries.length>LIMIT)entries.shift();
  render();return e;
 }
 const fileName=(now=new Date(),salt)=>"PocketMasterStudio_debug_"+
   now.toISOString().replace(/[-:]/g,"").replace("T","_").slice(0,15)+"_"+
   (salt||Math.random().toString(36).slice(2,8).padEnd(6,"0"))+".log";
 const serialize=()=>["# PocketMasterStudio Debug Log",
  "Session started: "+started,"Exported: "+new Date().toISOString(),
  "Entries: "+entries.length,"No automatic network upload.","",
  ...entries.map(e=>"["+e.time+"] ["+e.level+"] ["+e.source+"] "+e.message)
 ].join("\n")+"\n";
 function render(){
  if(!visible||typeof document==="undefined")return;
  const box=$("globalLogRows");if(!box)return;
  const filter=$("globalLogLevel").value,term=$("globalLogSearch").value.toLowerCase();
  const found=entries.filter(e=>(filter==="ALL"||e.level===filter)&&
   (!term||(e.message+" "+e.source).toLowerCase().includes(term)));
  const frag=document.createDocumentFragment();
  for(const e of found.slice(-500)){
   const line=document.createElement("div");line.className="debug-line debug-"+e.level.toLowerCase();
   const time=document.createElement("span");time.className="debug-when";time.textContent=e.time.slice(11,23)+" "+e.level+" "+e.source;
   const message=document.createElement("span");message.textContent=e.message;
   line.append(time,message);frag.appendChild(line);
  }
  box.replaceChildren(frag);$("globalLogCount").textContent=found.length+" / "+entries.length+" entries";
  if($("globalLogFollow").checked)box.scrollTop=box.scrollHeight;
 }
 function toggle(force){
  const node=$("globalLogPanel");if(!node)return;
  visible=typeof force==="boolean"?force:!visible;
  node.hidden=!visible;$("globalLogToggle").setAttribute("aria-expanded",String(visible));
  if(visible)render();
 }
 async function saveLog(){
  const status=$("globalLogExportStatus");status.textContent="";
  if(!window.PMVoidConfigIO?.connected()){
   status.textContent="Connect the project folder in Settings to save in logs/, or use Download.";
   event("LOG","Save requested while folder disconnected","WARN");return false;
  }
  const name=fileName();
  try {
   const path=await window.PMVoidConfigIO.saveLog(name,serialize());
   status.textContent="Saved to "+path;event("LOG","Saved "+path);return true;
  }catch(err){
   status.textContent="Unable to save: "+safe(err);event("LOG","Save failed: "+safe(err),"ERROR");return false;
  }
 }
 function download(){
  const name=fileName(),url=URL.createObjectURL(new Blob([serialize()],{type:"text/plain;charset=utf-8"}));
  const a=document.createElement("a");a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);event("LOG","Downloaded "+name);
 }
 function acceptEditorMessage(data,source){
  if(!editorWindow||source!==editorWindow||data?.type!=="pm-void-editor-log")return false;
  event("EDITOR",data.message,levels.includes(data.level)?data.level:"INFO");return true;
 }
 const attachEditor=frame=>{editorWindow=frame?.contentWindow||null;};
 function init(){
  if(ready)return;ready=true;
  for(const level of ["log","info","warn","error","debug"]){
   if(typeof console[level]!=="function")continue;
   const original=console[level].bind(console);
   console[level]=(...args)=>{
    event("CONSOLE",args.map(safe).join(" "),level==="log"?"INFO":level.toUpperCase());
    return original(...args);
   };
  }
  window.addEventListener("error",e=>event("WINDOW",(e.message||"Unknown error")+" @ "+(e.filename||"")+":"+(e.lineno||0),"ERROR"));
  window.addEventListener("unhandledrejection",e=>event("PROMISE",safe(e.reason),"ERROR"));
  window.addEventListener("message",e=>acceptEditorMessage(e.data,e.source));
  $("globalLogToggle").addEventListener("click",()=>toggle());
  $("globalLogClose").addEventListener("click",()=>toggle(false));
  $("globalLogLevel").addEventListener("change",render);
  $("globalLogSearch").addEventListener("input",render);
  $("globalLogFollow").addEventListener("change",render);
  $("globalLogClear").addEventListener("click",()=>{entries.length=0;event("LOG","Session log cleared");});
  $("globalLogSave").addEventListener("click",()=>saveLog());
  $("globalLogDownload").addEventListener("click",download);
  event("APP","Unified logger started");
 }
 // Inject this hook ahead of the Editor's scripts, without editing upstream Editor files.
 function editorBridge(){
  if(window.__pmLogBridge)return;window.__pmLogBridge=true;
  const text=x=>{try{return x instanceof Error?x.stack||x.message:typeof x==="string"?x:JSON.stringify(x)}catch(_){return String(x)}};
  const send=(level,message)=>{try{parent.postMessage({type:"pm-void-editor-log",level,message:String(message).slice(0,2500)},"*")}catch(_){}};
  for(const level of ["log","info","warn","error","debug"]){
   if(typeof console[level]!=="function")continue;
   const original=console[level].bind(console);
   console[level]=(...args)=>{send(level==="log"?"INFO":level.toUpperCase(),args.map(text).join(" "));return original(...args)};
  }
  window.addEventListener("error",e=>send("ERROR",(e.message||"Unknown")+" @ "+(e.filename||"")));
  window.addEventListener("unhandledrejection",e=>send("ERROR",text(e.reason)));
  const watch=()=>{
   // PocketEdit's existing log panel remains intact; mirror its text additions when identifiable.
   const ids=["logContent","logOutput","debugLog","consoleLog","logMessages","log-container","log"];
   const node=ids.map(id=>document.getElementById(id)).find(Boolean);
   if(!node||!window.MutationObserver)return;
   let last=node.textContent||"";
   new MutationObserver(()=>{
    const current=node.textContent||"";if(current===last)return;
    const diff=current.startsWith(last)?current.slice(last.length):current;last=current;
    if(diff.trim())send("DEBUG",diff.slice(-1800));
   }).observe(node,{childList:true,subtree:true,characterData:true});
  };
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",watch,{once:true});else watch();
  send("INFO","Editor debug bridge ready");
 }
 const editorHook="("+editorBridge.toString()+")();";
 return Object.freeze({init,event,entries,serialize,fileName,toggle,saveLog,acceptEditorMessage,attachEditor,editorHook});
});
