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
   // PocketEdit uses #logContent > .log-entry, with .log-time/.log-type/.log-message.
   const node=document.getElementById("logContent");
   if(!node||!window.MutationObserver)return;
   const forward=entry=>{
    if(!entry?.classList?.contains("log-entry"))return;
    const kind=(entry.querySelector(".log-type")?.textContent||"INFO").replace(/[\[\]]/g,"").toUpperCase();
    const message=entry.querySelector(".log-message")?.textContent||entry.textContent||"";
    const time=entry.querySelector(".log-time")?.textContent||"";
    const level=/ERROR|FAIL/.test(kind)?"ERROR":/WARN/.test(kind)?"WARN":
      /SENT|RECEIVED|RECV|SEND/.test(kind)?"DEBUG":"INFO";
    send(level,"["+kind+"] "+(time?time+" ":"")+message);
   };
   // Include any startup messages emitted before the observer attached.
   Array.from(node.querySelectorAll(".log-entry")).slice(-20).forEach(forward);
   new MutationObserver(records=>{
    for(const record of records)for(const added of record.addedNodes)
      if(added.nodeType===1){
       forward(added);
       added.querySelectorAll?.(".log-entry").forEach(forward);
      }
   }).observe(node,{childList:true});
  };
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",watch,{once:true});else watch();
  send("INFO","Editor debug bridge ready");
 }
 const editorHook="("+editorBridge.toString()+")();";
 return Object.freeze({init,event,entries,serialize,fileName,toggle,saveLog,acceptEditorMessage,attachEditor,editorHook});
});
