// NAM/Clone > Direct User Profile uploader (Sonicake USB-MIDI / BLE).
// This is the direct .clo upload stage. WaveNet .nam DSP conversion is NOT enabled.
(function(root,factory){
  if(typeof module==="object"&&module.exports)
    module.exports=factory(require("./void_clone_protocol.js"),require("./void_clone_transport.js"));
  else root.PMCloneUploadUI=factory(root.PMCloneProtocol,root.PMCloneTransport);
})(typeof self!=="undefined"?self:this,function(P,T){
 "use strict";
 function mount(host){
  host.innerHTML=[
   '<section class="clone-upload-card"><h3>Direct User Profile Upload (experimental)</h3>',
   '<p class="mut">Send a validated Sonicake <code>.clo</code> capture to User Profile 1–5 using USB-MIDI or BLE. ',
   'This overwrites the selected profile on the pedal. It does not change the modeled-AMP mapping above. ',
   'This tool cannot back up the existing physical slot. Disconnect the Editor before using this separate hardware connection, and overwrite only a replaceable profile.</p>',
   '<p class="mut">Standard <code>.nam</code> requires a computational WaveNet → .clo conversion ',
   '(reference DI + DSP fit). This independent conversion stage is not available in PocketMasterStudio yet. ',
   'Selecting a NAM here checks architecture only and never writes it.</p>',
   '<div class="clone-upload-form">',
   '<label>1. File (.clo or .nam)</label>',
   '<input id="clone-file" type="file" accept=".clo,.nam">',
   '<div id="clone-file-status" class="mut" role="status">No file selected</div>',
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
  let profile=null,connection=null,busy=false;
  const status=(text,level="INFO")=>{
   $("clone-upload-progress").textContent=text;
   log(text,level);
  };
  function updateButtons(){
   $("clone-upload").disabled=busy||!profile||!connection||!$("clone-confirm").checked;
   $("clone-device-connect").disabled=busy||Boolean(connection);
   $("clone-device-disconnect").disabled=busy||!connection;
   $("clone-file").disabled=busy;
   $("clone-transport").disabled=busy||Boolean(connection);
   $("clone-target").disabled=busy;
   $("clone-upload-name").disabled=busy;
  }
  $("clone-file").addEventListener("change",async()=>{
   const file=$("clone-file").files?.[0];
   profile=null;$("clone-confirm").checked=false;
   if(!file){$("clone-file-status").textContent="No file selected";updateButtons();return}
   try{
    const bytes=new Uint8Array(await file.arrayBuffer());
    if(/\.nam$/i.test(file.name)){
     const content=new TextDecoder("utf-8",{fatal:true}).decode(bytes);
     const meta=P.validateNam(content);
     $("clone-file-status").textContent=file.name+": "+meta.architecture+
       " ("+meta.version+"). Conversion not yet integrated; no upload available.";
     log("NAM inspected: "+file.name+", "+meta.architecture+
       "; requires WaveNet DSP converter before the .clo upload stage","WARN");
    }else if(/\.clo$/i.test(file.name)){
     const meta=P.validateFile(bytes);profile=bytes;
     const base=file.name.replace(/\.clo$/i,"");
     $("clone-upload-name").value=P.sanitizedName(base);
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
    if(connection){await connection.disconnect();connection=null}
  }};
 }
 return Object.freeze({mount});
});
