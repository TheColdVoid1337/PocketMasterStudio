// Browser USB-MIDI / BLE transport and acknowledged clone writer.
// From SonicMaster MIT protocol: DeviceService._writeChunks and _writeCloneSlot.
// An ACK is not a flash-commit. This module never auto-writes upon connection.
(function(root,factory){
  if(typeof module==="object"&&module.exports)module.exports=factory(require("./void_clone_protocol.js"));
  else root.PMCloneTransport=factory(root.PMCloneProtocol);
})(typeof self!=="undefined"?self:this,function(P){
  "use strict";
  const makeEmitter=()=>{
    const listeners=new Set();
    return {onFrame(fn){listeners.add(fn);return()=>listeners.delete(fn)},
      emit(frame){for(const fn of listeners){try{fn(frame)}catch(e){/* isolate listener faults */}}},
      clear(){listeners.clear()}};
  };
  const isSysEx=data=>data.length>=7&&data[0]===0xF0&&data.at(-1)===0xF7;
  function assembler(emit){
    const collecting=new Map();
    return input=>{
      let data=input instanceof Uint8Array?input:new Uint8Array(input);
      const start=data.indexOf(0xF0);
      if(start>0)data=data.slice(start);
      if(!isSysEx(data))return;
      const total=(data[3]<<4)|data[4],seq=(data[5]<<4)|data[6];
      if(total<=1){emit(data);return}
      if(total>255||seq>=total||data.length<10)return;
      const key=data[3]+"_"+data[4];
      let entry=collecting.get(key);
      if(!entry||entry.total!==total){
        entry={total,parts:new Map(),first:data};
        collecting.set(key,entry);
      }
      entry.parts.set(seq,data.slice(9,-1));
      if(entry.parts.size!==total)return;
      const payload=Array.from({length:total},(_,i)=>entry.parts.get(i));
      collecting.delete(key);
      if(payload.some(x=>!x))return;
      emit(Uint8Array.from([0xF0,entry.first[1],entry.first[2],0,1,0,0,0,0,
        ...payload.flatMap(x=>Array.from(x)),0xF7]));
    };
  }
  function waitFor(io,matcher,send,timeoutMs){
    return new Promise((resolve,reject)=>{
      let finished=false;
      const off=io.onFrame(frame=>{
        if(!matcher(frame)||finished)return;
        finished=true;clearTimeout(timer);off();resolve(frame);
      });
      const timer=setTimeout(()=>{
        if(finished)return;
        finished=true;off();resolve(null);
      },timeoutMs);
      Promise.resolve().then(send).catch(e=>{
        if(finished)return;
        finished=true;clearTimeout(timer);off();reject(e);
      });
    });
  }
  const hexNoHdr=bytes=>P.hex(bytes);
  const isAck=f=>hexNoHdr(f)===P.ACK_HEX;
  const hasCommit=f=>hexNoHdr(f).includes(P.CLONE_COMMIT_SIG);
  const isData=f=>isSysEx(f)&&!isAck(f)&&!hasCommit(f);
  const sessionFrame=P.fromHex(P.SESSION_INIT.slice(4));
  const namesFrame=P.fromHex(P.CLONE_NAMES.slice(4));
  async function upload(io,params={}){
    const {slot,name,clo,onLog=()=>{},onProgress=()=>{},ackTimeout=1200,
      ackRetries=10,commitTimeout=5000}=params;
    if(!io||typeof io.send!=="function"||typeof io.onFrame!=="function")throw Error("No transport");
    // Pure validation and packing happen before any device write.
    const uploadPlan=P.makeUpload({slot,name,clo});
    const log=(message,level="INFO")=>onLog(level,message);
    log("Prepared User Profile "+(slot+1)+": "+uploadPlan.name+
      "; source .clo 8840 bytes; upload 2696 bytes; "+uploadPlan.chunks.length+" chunks");
    const init=await waitFor(io,isData,()=>io.send(sessionFrame),1500);
    if(!init)throw Error("Pedal did not answer edit-session request (020300); no upload performed");
    log("Edit session entered (020300)");
    const before=await waitFor(io,isData,()=>io.send(namesFrame),2000);
    if(!before)throw Error("User Profile names request (020204) timed out; no upload performed");
    const oldNames=P.decodeUserNames(before);
    log("User Profile names received; target slot "+(slot+1)+
      " before upload: "+(oldNames[slot]||"[unreadable]"),"DEBUG");
    let committed=false;
    const detach=io.onFrame(f=>{if(hasCommit(f))committed=true});
    try{
      for(let i=0;i<uploadPlan.chunks.length;i++){
        let ack=false;
        for(let attempt=1;attempt<=ackRetries&&!ack;attempt++){
          const response=await waitFor(io,isAck,()=>io.send(uploadPlan.chunks[i]),ackTimeout);
          ack=Boolean(response);
          if(!ack)log("Missing ACK: chunk "+(i+1)+"/"+uploadPlan.chunks.length+
            ", attempt "+attempt+"/"+ackRetries,"WARN");
        }
        if(!ack)throw Error("Upload stopped: chunk "+(i+1)+" did not receive ACK after "+ackRetries+" attempts");
        onProgress(i+1,uploadPlan.chunks.length);
        log("ACK received for chunk "+(i+1)+"/"+uploadPlan.chunks.length,"DEBUG");
      }
      if(!committed){
        const notification=await waitFor(io,hasCommit,()=>{},commitTimeout);
        committed=Boolean(notification)||committed;
      }
    }finally{detach()}
    if(!committed)throw Error("All chunks ACKed, but flash-commit was NOT confirmed (domain 03). No successful save claimed; power-cycle and retry.");
    log("Flash commit confirmed by device (domain 03).");
    const after=await waitFor(io,isData,()=>io.send(namesFrame),2200);
    if(!after){
      log("Flash committed, but name readback timed out; verify slot manually","WARN");
      return {status:"committed-unverified",slot,name:uploadPlan.name,chunks:uploadPlan.chunks.length};
    }
    const names=P.decodeUserNames(after);
    const observed=names[slot],expected=uploadPlan.name.slice(0,10);
    if(!observed||observed!==expected){
      log("Flash committed; User Profile "+(slot+1)+" readback differs/unreadable: "+
        (observed||"[unreadable]")+", expected prefix "+expected,"WARN");
      return {status:"committed-unverified",slot,name:uploadPlan.name,readback:observed,
        chunks:uploadPlan.chunks.length};
    }
    log("User Profile "+(slot+1)+" readback verified: "+observed);
    return {status:"verified",slot,name:uploadPlan.name,readback:observed,
      chunks:uploadPlan.chunks.length};
  }
  async function connectBle(navigatorObj=typeof navigator!=="undefined"?navigator:null){
    if(!navigatorObj?.bluetooth?.requestDevice)throw Error("Web Bluetooth is unavailable (use Chrome/Edge on localhost)");
    const device=await navigatorObj.bluetooth.requestDevice({
      filters:[{services:[P.SERVICE_UUID]}],optionalServices:[P.SERVICE_UUID]});
    const gatt=await device.gatt.connect();
    const service=await gatt.getPrimaryService(P.SERVICE_UUID);
    const char=await service.getCharacteristic(P.CHAR_UUID);
    const e=makeEmitter(),recv=assembler(f=>e.emit(f));
    const handler=event=>recv(new Uint8Array(event.target.value.buffer,
      event.target.value.byteOffset,event.target.value.byteLength));
    await char.startNotifications();
    char.addEventListener("characteristicvaluechanged",handler);
    return {kind:"BLE",name:device.name||"Sonicake BLE",onFrame:e.onFrame,
      async send(frame){
        if(!device.gatt.connected)throw Error("Bluetooth device disconnected");
        const data=Uint8Array.from([0x80,0x80,...frame]);
        if(char.properties?.writeWithoutResponse&&char.writeValueWithoutResponse)
          await char.writeValueWithoutResponse(data);
        else if(char.writeValue)await char.writeValue(data);
        else throw Error("BLE characteristic does not support writes");
      },
      async disconnect(){
        char.removeEventListener("characteristicvaluechanged",handler);
        e.clear();
        if(device.gatt.connected)device.gatt.disconnect();
      }};
  }
  async function connectMidi(navigatorObj=typeof navigator!=="undefined"?navigator:null){
    if(!navigatorObj?.requestMIDIAccess)throw Error("Web MIDI SysEx unavailable (use Chrome/Edge on localhost)");
    const access=await navigatorObj.requestMIDIAccess({sysex:true});
    if(!access.sysexEnabled)throw Error("Web MIDI SysEx permission was not granted");
    const relevant=n=>/pocket.?master|smart.?box|sonicake/i.test(n||"");
    const outputs=Array.from(access.outputs.values()).filter(x=>relevant(x.name));
    const inputs=Array.from(access.inputs.values()).filter(x=>relevant(x.name));
    if(outputs.length!==1||inputs.length!==1)
      throw Error("Expected exactly one Pocket Master/Smart Box MIDI input and output; found "+
        inputs.length+" input(s), "+outputs.length+" output(s). Disconnect other MIDI devices or use BLE.");
    const output=outputs[0],input=inputs[0],e=makeEmitter(),recv=assembler(f=>e.emit(f));
    if(output.open)await output.open();
    if(input.open)await input.open();
    const handler=event=>recv(new Uint8Array(event.data));
    input.addEventListener("midimessage",handler);
    return {kind:"USB-MIDI",name:output.name||"Sonicake USB-MIDI",onFrame:e.onFrame,
      send:async frame=>{if(output.state==="disconnected")throw Error("MIDI device disconnected");output.send(Array.from(frame))},
      async disconnect(){
        input.removeEventListener("midimessage",handler);e.clear();
        if(input.close)await input.close();
        if(output.close)await output.close();
      }};
  }
  return Object.freeze({upload,connectBle,connectMidi,assembler,waitFor,isAck,hasCommit});
});
