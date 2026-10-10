// NAM/Clone > Direct User Profile uploader (Sonicake USB-MIDI / BLE).
// Real WaveNet .nam conversion uses the local SonicMaster Rust DSP; hardware upload remains explicit.
(function(root,factory){
  if(typeof module==="object"&&module.exports)
    module.exports=factory(require("./void_clone_protocol.js"),require("./void_clone_transport.js"),require("./void_nam_converter.js"));
  else root.PMCloneUploadUI=factory(root.PMCloneProtocol,root.PMCloneTransport,root.PMNamConverter);
})(typeof self!=="undefined"?self:this,function(P,T,C){
 "use strict";
 function mount(host){
  host.innerHTML=[
   '<section class="clone-upload-card"><h3>Direct User Profile Upload (experimental)</h3>',
   '<p class="mut">Convert a supported WaveNet <code>.nam</code> locally to native <code>.clo</code>, or load a ready <code>.clo</code>; send it to User Profile 1–5 using USB-MIDI or BLE. ',
   'This overwrites the selected profile on the pedal. It does not change the modeled-AMP mapping above. ',
   'This tool cannot back up the existing physical slot. Disconnect the Editor before using this separate hardware connection, and overwrite only a replaceable profile.</p>',
   '<p class="mut">NAM conversion runs the SonicMaster MIT Rust DSP on the local 127.0.0.1 server. ',
   'It requires a separately built Rust executable and verified reference DI asset. ',
   'Conversion does not touch the pedal. You can download the converted .clo before choosing to upload.</p>',
   '<div class="clone-upload-form">',
   '<label>1. File (.clo or .nam)</label>',
   '<input id="clone-file" type="file" accept=".clo,.nam">',
   '<div id="clone-file-status" class="mut" role="status">No file selected</div>',
   '<div class="clone-actions"><button type="button" id="clone-convert" disabled>Convert NAM to CLO</button>',
   '<button type="button" id="clone-cancel" disabled>Cancel conversion</button>',
   '<button type="button" id="clone-download" disabled>Download .clo</button></div>',
   '<label>2. Target physical User Profile</label>',
   '<select id="clone-target">',
   ...Array.from({length:5},(_,i)=>'<option value="'+i+'">User Profile '+(i+1)+'</option>'),
   '</select>',
   '<label>3. Name stored on pedal (ASCII, max 15)</label>',
   '<input id="clone-upload-name" maxlength="15" placeholder="e.g. AC30 FullRig">',
   '<label>4. Transport</label>',
   '<select id="clone-transport"><option value="midi">USB-MIDI (recommended)</option>',
   '<option value="ble">Bluetooth LE MIDI</option></select>',
   '<div class="clone-actions"><button type="button" id="clone-device-connect">Connect pedal</button>',
   '<button type="button" id="clone-device-disconnect" disabled>Disconnect</button></div>',
   '<div id="clone-device-state" class="mut" role="status">No pedal session connected</div>',
   '<label class="setting-line clone-consent"><input type="checkbox" id="clone-confirm">',
   '<span>I understand uploading replaces the selected physical User Profile on the pedal.</span></label>',
   '<button type="button" id="clone-upload" class="primary" disabled>Upload to pedal</button>',
   '<div id="clone-upload-progress" role="status" aria-live="polite"></div>',
   '</div></section>'
  ].join("");
  const $=id=>host.querySelector("#"+id);
  const log=(msg,level="INFO")=>window.PMVoidDebug?.event("NAM",msg,level);
  let profile=null,connection=null,busy=false,namText=null,namJob=null,downloadName='';
  const status=(text,level="INFO")=>{
   $("clone-upload-progress").textContent=text;
   log(text,level);
  };
  function updateButtons(){
   $("clone-upload").disabled=busy||!profile||!connection||!$("clone-confirm").checked;
   $("clone-convert").disabled=busy||!namText;
   $("clone-cancel").disabled=!namJob;
   $("clone-download").disabled=busy||!profile;
   $("clone-device-connect").disabled=busy||Boolean(connection);
   $("clone-device-disconnect").disabled=busy||!connection;
   $("clone-file").disabled=busy;
   $("clone-transport").disabled=busy||Boolean(connection);
   $("clone-target").disabled=busy;
   $("clone-upload-name").disabled=busy;
  }
  $("clone-file").addEventListener("change",async()=>{
   const file=$("clone-file").files?.[0];
   profile=null;namText=null;downloadName="";$("clone-confirm").checked=false;
   if(!file){$("clone-file-status").textContent="No file selected";updateButtons();return}
   try{
    const bytes=new Uint8Array(await file.arrayBuffer());
    if(/\.nam$/i.test(file.name)){
     const content=new TextDecoder("utf-8",{fatal:true}).decode(bytes);
     const meta=C.inspect(content);
     namText=content;
     downloadName=file.name.replace(/\.nam$/i,"")+".clo";
     const nameCandidate=file.name.replace(/\.nam$/i,"").replace(/[^\x20-\x7E]/g,"").trim()||"NAM PROFILE";
     $("clone-upload-name").value=P.sanitizedName(nameCandidate);
     $("clone-file-status").textContent=file.name+": "+meta.architecture+
       " ("+meta.version+"). Ready to convert locally; no pedal write.";
     log("NAM inspected: "+file.name+", architecture="+meta.architecture+
       ", version="+meta.version+"; conversion available after local DSP setup");
    }else if(/\.clo$/i.test(file.name)){
     const meta=P.validateFile(bytes);profile=bytes;
     const base=file.name.replace(/\.clo$/i,"");
     $("clone-upload-name").value=P.sanitizedName(base);
     downloadName=file.name;
     $("clone-file-status").textContent=file.name+": "+meta.bytesLength+
       " bytes, VTSI and CRC16 verified. Ready to choose target slot.";
     log("Loaded .clo file "+file.name+": "+meta.bytesLength+
       " bytes; valid magic/FIR layout/CRC16; original kept in memory");
    }else throw Error("Choose a .clo or .nam file");
   }catch(e){
    $("clone-file-status").textContent="Rejected: "+e.message;
    log("Failed to inspect "+file.name+": "+e.message,"ERROR");
   }
   updateButtons();
  });
  $("clone-convert").addEventListener("click",async()=>{
   if(!namText||busy)return;
   busy=true;$("clone-confirm").checked=false;
   let ticker=null;
   try{
    const info=await C.availability();
    if(!info.ready)throw Error((info.requirements||[]).join("; ")||"Local DSP unavailable");
    status("Starting native WaveNet inference + Wiener-Hammerstein fitting. No pedal writes.");
    namJob=C.start(namText);
    const startAt=Date.now();
    ticker=setInterval(()=>{
     if(namJob)$("clone-upload-progress").textContent=
       "Native NAM inference/fitting in progress ("+Math.floor((Date.now()-startAt)/1000)+
       " s elapsed; no pedal write)";
    },2000);
    updateButtons();
    profile=await namJob.promise;
    const checked=P.validateFile(profile);
    namText=null;
    $("clone-file-status").textContent="Converted .clo: "+checked.bytesLength+
      " bytes, VTSI/CRC16/FIR verified. Download or explicitly upload to the pedal.";
    status("NAM conversion complete; generated "+checked.bytesLength+
      "-byte CLO (CRC16 verified). Physical slot has NOT been changed.");
   }catch(e){
    const cancelled=e?.name==="AbortError"||/cancelled/i.test(e.message);
    status(cancelled?"NAM conversion cancelled: no pedal write":
      "NAM conversion FAILED: "+e.message,cancelled?"WARN":"ERROR");
   }finally{if(ticker!==null)clearInterval(ticker);namJob=null;busy=false;updateButtons()}
  });
  $("clone-cancel").addEventListener("click",async()=>{
   if(!namJob)return;
   const job=namJob;
   status("Requesting local NAM conversion cancellation","WARN");
   await job.cancel();
  });
  $("clone-download").addEventListener("click",()=>{
   if(!profile||busy)return;
   const bytes=P.validateFile(profile).bytes;
   const url=URL.createObjectURL(new Blob([bytes],{type:"application/octet-stream"}));
   try{
    const a=document.createElement("a");a.href=url;
    a.download=downloadName||"Converted_NAM.clo";
    document.body.appendChild(a);a.click();a.remove();
    log("CLO download initiated: "+a.download+" ("+bytes.length+" bytes); browser manages file save");
   }finally{setTimeout(()=>URL.revokeObjectURL(url),2000)}
  });
  $("clone-confirm").addEventListener("change",updateButtons);
  $("clone-target").addEventListener("change",()=>{
   $("clone-confirm").checked=false;updateButtons();
  });
  $("clone-device-connect").addEventListener("click",async()=>{
   if(connection||busy)return;
   busy=true;updateButtons();
   const kind=$("clone-transport").value;
   try{
    log("Connecting to Sonicake pedal using "+(kind==="midi"?"USB-MIDI SysEx":"BLE-MIDI"));
    // API permission chooser starts inside this click handler.
    connection=kind==="midi"?await T.connectMidi():await T.connectBle();
    $("clone-device-state").textContent="Connected: "+connection.name+" ("+connection.kind+")";
    status("Pedal transport connected. No data written.");
   }catch(e){
    $("clone-device-state").textContent="Connection failed: "+e.message;
    status("Device connection failed: "+e.message,"ERROR");
   }finally{busy=false;updateButtons()}
  });
  $("clone-device-disconnect").addEventListener("click",async()=>{
   if(!connection||busy)return;
   busy=true;updateButtons();
   try{await connection.disconnect();status("Pedal transport disconnected");}
   catch(e){status("Disconnect failed: "+e.message,"ERROR")}
   finally{connection=null;busy=false;$("clone-device-state").textContent="No pedal session connected";updateButtons()}
  });
  $("clone-upload").addEventListener("click",async()=>{
   if(!profile||!connection||busy||!$("clone-confirm").checked)return;
   const slot=Number($("clone-target").value),name=$("clone-upload-name").value;
   let normalized;
   try{normalized=P.sanitizedName(name)}
   catch(e){status("Invalid clone name: "+e.message,"ERROR");return}
   if(!window.confirm("OVERWRITE User Profile "+(slot+1)+
     " on the physical pedal with "+normalized+"?\n\nThis action cannot be undone by PocketMasterStudio."))
     return;
   busy=true;updateButtons();
   try{
    status("Beginning clone transfer to User Profile "+(slot+1)+" ("+normalized+")");
    const result=await T.upload(connection,{slot,name:normalized,clo:profile,
     onLog:(level,message)=>log(message,level),
     onProgress:(sent,total)=>{$("clone-upload-progress").textContent=
       "Transferring User Profile "+(slot+1)+": "+sent+"/"+total+" ACKed";}});
    const text=result.status==="verified"
      ?"Upload committed and readback verified: User Profile "+(slot+1)+
        " ("+result.readback+")."
      :"Upload flash-committed, but readback is not verified. Check the pedal directly.";
    status(text,result.status==="verified"?"INFO":"WARN");
    $("clone-confirm").checked=false;
   }catch(e){
    status("Clone transfer FAILED: "+e.message,"ERROR");
    $("clone-confirm").checked=false;
   }finally{busy=false;updateButtons()}
  });
  updateButtons();
  return {async dispose(){
    if(namJob)await namJob.cancel();
    if(connection){await connection.disconnect();connection=null}
  }};
 }
 return Object.freeze({mount});
});
