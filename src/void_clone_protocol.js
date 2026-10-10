/*
SonicMaster protocol adaptation (Skyggedans/SonicMaster).
MIT License

Copyright (c) 2026 Andrii Klaptsov

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
*/
// PocketMasterStudio: Sonicake clone profile binary codec and chunked SysEx.
// Protocol ported from SonicMaster (MIT), app/lib/protocol/{clo_codec,clo_upload_frame,
// sysex_chunk_upload,crc16_modbus,crc8_smbus}. No hardware I/O in this module.
(function(root,factory){
  if(typeof module==="object"&&module.exports)module.exports=factory();
  else root.PMCloneProtocol=factory();
})(typeof self!=="undefined"?self:this,function(){
  "use strict";
  const FILE_SIZE=8840,UPLOAD_SIZE=2696,BLOB_SIZE=2770;
  const NAME_LIMIT=15,UPLOAD_TAPS=512,FILE_TAPS=2048;
  const ACK_HEX="F00B02000100000003010400080000F7";
  const CLONE_COMMIT_SIG="0102010B0003";
  const SESSION_INIT="8080F0050900010000000201020300F7";
  const CLONE_NAMES="8080F0030500010000000201020204F7";
  const SERVICE_UUID="03b80e5a-ede8-4b33-a751-6ce34ec4c700";
  const CHAR_UUID="7772e5db-3868-4112-a1a9-f2669d106bf3";
  const bytes=x=>x instanceof Uint8Array?x:new Uint8Array(x);
  const hex=x=>Array.from(bytes(x),b=>b.toString(16).padStart(2,"0")).join("").toUpperCase();
  function fromHex(h){
    if(typeof h!=="string"||h.length%2||!/^[a-f0-9]*$/i.test(h))throw Error("Invalid hex");
    const out=new Uint8Array(h.length/2);
    for(let i=0;i<out.length;i++)out[i]=parseInt(h.slice(2*i,2*i+2),16);
    return out;
  }
  function crc16(x){
    let crc=0xFFFF;
    for(const b of x){crc^=b;for(let i=0;i<8;i++)crc=(crc&1)?((crc>>>1)^0xA001):(crc>>>1);}
    return crc&0xFFFF;
  }
  function crc8(x){
    let crc=0;
    for(const b of x){
      crc^=b;
      for(let i=0;i<8;i++)crc=crc&0x80?((crc<<1)^7)&255:(crc<<1)&255;
    }
    return crc;
  }
  function validateFile(input){
    const src=bytes(input);
    if(src.length!==FILE_SIZE)throw Error(".clo must be exactly 8840 bytes; got "+src.length);
    if(hex(src.subarray(0,4))!=="56545349")throw Error("Not a .clo file (expected VTSI magic)");
    const dv=new DataView(src.buffer,src.byteOffset,src.byteLength);
    if(dv.getUint32(4,true)!==FILE_SIZE)throw Error("Incorrect .clo declared size");
    if(dv.getUint32(20,true)!==8704)throw Error("Incorrect .clo body length");
    if(dv.getUint32(124,true)!==128||dv.getUint32(128,true)!==128||
       dv.getUint32(132,true)!==FILE_TAPS)throw Error("Unsupported .clo FIR layout");
    const stored=dv.getUint16(8,false),calculated=crc16(src.subarray(12));
    if(stored!==calculated)throw Error(".clo CRC16 mismatch: expected 0x"+
      stored.toString(16)+", calculated 0x"+calculated.toString(16));
    for(const [offset,size,count] of [[64,8,5],[104,4,4],[136,4,128],[648,4,FILE_TAPS]]){
      for(let i=0;i<count;i++){
        const v=size===8?dv.getFloat64(offset+i*size,true):dv.getFloat32(offset+i*size,true);
        if(!Number.isFinite(v))throw Error("Non-finite .clo DSP coefficient at byte "+(offset+i*size));
      }
    }
    return {bytes:src,crc:stored,bytesLength:src.length};
  }
  function uploadClo(input){
    const {bytes:src}=validateFile(input);
    const out=src.slice(0,UPLOAD_SIZE),view=new DataView(out.buffer);
    view.setUint32(4,UPLOAD_SIZE,true);
    view.setUint32(20,UPLOAD_SIZE-136,true);
    view.setUint32(132,UPLOAD_TAPS,true);
    view.setUint16(8,crc16(out.subarray(12)),false);
    return out;
  }
  function sanitizedName(name){
    const ascii=Array.from(String(name||"")).filter(c=>c.charCodeAt(0)>=32&&c.charCodeAt(0)<127).join("").trim();
    if(!ascii)throw Error("Profile name must contain printable ASCII");
    return ascii.slice(0,NAME_LIMIT);
  }
  function makeBlob({slot,name,clo}){
    if(!Number.isInteger(slot)||slot<0||slot>4)throw Error("Clone slot must be 0–4");
    const upload=uploadClo(clo),ascii=sanitizedName(name),blob=new Uint8Array(BLOB_SIZE);
    blob[0]=0x11;blob[1]=0x25;blob[6]=slot;blob[9]=0x0F;
    for(let i=0;i<ascii.length;i++)blob[10+i]=ascii.charCodeAt(i);
    blob.set(upload,74);
    return blob;
  }
  const pair=x=>[(x>>>4)&15,x&15];
  function frame(total,seq,part){
    if(total<1||total>255||seq<0||seq>=total||part.length>19)throw Error("Invalid chunk");
    const check=crc8([total,seq,part.length,...part]);
    return Uint8Array.from([0xF0,...pair(check),...pair(total),...pair(seq),
      ...pair(part.length),...Array.from(part).flatMap(pair),0xF7]);
  }
  function chunks(blob){
    const data=bytes(blob),total=Math.ceil(data.length/19);
    if(total>255)throw Error("Too many clone packets");
    const frames=[];
    for(let i=0;i<total;i++)frames.push(frame(total,i,data.subarray(i*19,Math.min(data.length,(i+1)*19))));
    return frames;
  }
  function makeUpload({slot,name,clo}){
    const blob=makeBlob({slot,name,clo});
    return {blob,chunks:chunks(blob),slot,name:sanitizedName(name)};
  }
  function unpackChunk(f){
    const data=bytes(f);
    if(data[0]!==0xF0||data.at(-1)!==0xF7||data.length<10)throw Error("Invalid SysEx chunk");
    const field=i=>(data[i]<<4)|data[i+1];
    const crc=field(1),total=field(3),seq=field(5),length=field(7);
    if(data.length!==10+2*length)throw Error("Chunk size mismatch");
    const part=new Uint8Array(length);
    for(let i=0;i<length;i++)part[i]=field(9+i*2);
    if(crc!==crc8([total,seq,length,...part]))throw Error("Chunk CRC8 mismatch");
    return {total,seq,part};
  }
  function decodeUserNames(framed){
    const h=typeof framed==="string"?framed:hex(framed);
    let payload=h.toUpperCase().replace(/^8080F0/,"").replace(/^F0/,"").replace(/F7$/,"");
    const lookup=code=>{
      const a=parseInt(code.slice(0,2),16),b=parseInt(code.slice(2,4),16);
      if(code==="0000")return null;
      if(a===2&&b===0)return " ";
      if(a===3&&b>=0&&b<=9)return String.fromCharCode(48+b);
      if(a===4&&b>=1&&b<=15)return String.fromCharCode(64+b);
      if(a===5&&b>=0&&b<=10)return String.fromCharCode(80+b);
      if(a===6&&b>=1&&b<=15)return String.fromCharCode(96+b);
      if(a===7&&b>=0&&b<=10)return String.fromCharCode(112+b);
      const special={"020D":"-","020E":".","020F":"/","050F":"_","0203":"#","0206":"&","0207":"'","050B":"[","050D":"]"};
      return Object.hasOwn(special,code)?special[code]:undefined;
    };
    return Array.from({length:5},(_,i)=>{
      const nameHex=payload.slice((22+i*32)*2,(22+i*32)*2+40);
      if(nameHex.length!==40)return "";
      let out="",padded=false;
      for(let j=0;j<10;j++){
        const value=lookup(nameHex.slice(j*4,j*4+4));
        if(value===undefined||padded&&value!==null)return "";
        if(value===null)padded=true;else out+=value;
      }
      return out;
    });
  }
  function validateNam(text){
    let model;
    try{model=typeof text==="string"?JSON.parse(text):text;}catch(_){throw Error("NAM is not valid JSON");}
    if(!model||typeof model!=="object"||Array.isArray(model))throw Error("Invalid NAM model");
    if(model.architecture==="SlimmableContainer"){
      const submodels=model.config?.submodels;
      if(!Array.isArray(submodels))throw Error("SlimmableContainer has no WaveNet submodels");
      let best;
      for(const item of submodels){
        if(item?.model?.architecture==="WaveNet"&&(!best||(item.max_value||0)>=(best.max_value||0)))best=item;
      }
      if(!best)throw Error("SlimmableContainer contains no supported WaveNet");
      model=best.model;
    }
    if(model.architecture!=="WaveNet")throw Error("NAM architecture "+(model.architecture||"unknown")+" unsupported; WaveNet required");
    const forbidden=["conv_pre_film","conv_post_film","input_mixin_pre_film",
      "input_mixin_post_film","activation_pre_film","activation_post_film",
      "layer1x1_post_film","head1x1_post_film","film_params"];
    for(const layer of model.config?.layers||[]){
      if(layer.gated===true||Array.isArray(layer.gating_mode)&&layer.gating_mode.some(x=>x!=="none"))
        throw Error("Gated WaveNet unsupported");
      if(layer.bottleneck!=null&&layer.bottleneck!==layer.channels)
        throw Error("WaveNet bottleneck unsupported");
      const active=v=>v&&typeof v==="object"?!("active" in v)||v.active===true:v!=null&&v!==false;
      if(active(layer.head1x1)||active(layer.head_1x1_config)||
         forbidden.some(k=>active(layer[k])))throw Error("Unsupported NAM conditioning/head layer");
    }
    return {architecture:"WaveNet",version:String(model.version||"unspecified")};
  }
  return Object.freeze({FILE_SIZE,UPLOAD_SIZE,BLOB_SIZE,NAME_LIMIT,ACK_HEX,CLONE_COMMIT_SIG,
    SESSION_INIT,CLONE_NAMES,SERVICE_UUID,CHAR_UUID,crc8,crc16,hex,fromHex,
    validateFile,uploadClo,sanitizedName,makeBlob,makeUpload,frame,chunks,unpackChunk,
    decodeUserNames,validateNam});
});
