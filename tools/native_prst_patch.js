/* Native 515-byte PRST patcher for vetted controls; dependency-free JS.
 * Unknown bytes are retained from a genuine exported template.
 * Clone mode/slot mapping was verified with paired SONICLINK exports.
 */
'use strict';
const slots=require('./prst_clone_slots.js');
const MODS=['NR','FX1','DRV','AMP','IR','EQ','FX2','DLY','RVB','Clone'];
const CODES={
 DRV:{'Scream':0,'Bass Drive':64,'Butter OD':2,'JP Dist':42,'Shark':48,'Dark Mouse':43,'Grey Fuzz':34,'Red Fuzz':36},
 AMP:{'TWD Deluxe':1,'B-Man N':3,'Dark Twin':4,'Voks 30N':17,'Jazz 120':20,'Brit 45':42,'Brit 50JP':47,'Brit 800':53,'B-Man B':36,'Voks 30TB':39,'Sol 100 OD':71,'Dizzy VH':101,'Eng 120':95,'Halen 51':90,'Sol 100 LD':89,'Calif DualV':104,'Calif DualM':105,'Eng Power':99,'Flyman B1+':93,'Bog XT':109,'A BassVT':115,'Voks Bass':117},
 IR:{'TWD 1x8':1,'TWD-P 1x10':2,'Viblux 1x12':4,'Voks 1x12':8,'TWD 2x12':27,'Double 2x12':18,'Star 2x12':25,'Jazz 2x12':17,'BritGN 2x12':19,'BritGN 4x12':34,'Bog 4x12':39,'Dizzy 4x12':46,'Halen 4x12':32,'Sol 4x12':40,'Dual 4x12':36},
 EQ:{'GT EQ 1':53,'GT EQ 2':54,'Bass EQ':58},
 DLY:{'Pure':0,'Slap':5,'Warm':13,'Mag':2,'Tube':11,'Reverse':19,'Analog':20,'Sweep':6,'Ping Pong':4},
 RVB:{'Air':11,'Room':0,'Hall':1,'Church':2,'Plate 1':16,'Plate 2':15,'Spring':4,'Light':6,'Ocean':7,'Dream':21}
};
const ok=(v,m)=>{if(!v)throw Error(m)};
const obj=v=>v&&typeof v==='object'&&!Array.isArray(v);
function modelSpec(catalog,module,model){
 const m=catalog?.modules?.find(x=>x.name===module);
 const e=m?.effectIds?.map(id=>catalog.effects[String(id)]).find(x=>x?.name===model);
 ok(e&&Array.isArray(e.parameters),'Unknown official model '+module+'.'+model);
 return e.parameters;
}
function safeValue(field,v,module){
 ok(typeof v==='number'&&Number.isFinite(v),module+'.'+field.name+' not a number');
 if(field.min!=null)ok(v>=field.min-1e-5,module+'.'+field.name+' below minimum');
 if(field.max!=null)ok(v<=field.max+1e-5,module+'.'+field.name+' above maximum');
 if(field.step&&field.min!=null)ok(Math.abs((v-field.min)/field.step-Math.round((v-field.min)/field.step))<1e-5,module+'.'+field.name+' invalid step');
 if(field.min==null&&field.max==null&&['Bright','Char','+3dB'].includes(field.name))ok(v===0||v===1,module+'.'+field.name+' invalid toggle');
}
function write(template,changes,{catalog,fxNative}={}){
 const input=slots.inspect(template); // length/magic/CRC/critical TLVs
 const bytes=Uint8Array.from(template), view=new DataView(bytes.buffer);
 ok(view.getUint16(121,true)===0x3002&&view.getUint16(123,true)===10&&
   view.getUint16(179,true)===0x3004&&view.getUint16(181,true)===320,'Unsupported effect TLV layout');
 ok(obj(changes),'Patch changes must be an object');
 const supported=new Set(['name','preset_volume','bpm','models','parameters','enabled','signal_chain','clone_slot']);
 for(const k of Object.keys(changes))ok(supported.has(k),'Unknown patch key '+k);
 if(changes.name!==undefined){ok(typeof changes.name==='string'&&/^[\x20-\x7e]{1,15}$/.test(changes.name),'Name 1..15 ASCII required');bytes.fill(0,25,41);for(let i=0;i<changes.name.length;i++)bytes[25+i]=changes.name.charCodeAt(i)}
 for(const [k,offset,lo,hi] of [['preset_volume',97,0,100],['bpm',105,40,260]])if(changes[k]!==undefined){const n=changes[k];ok(Number.isInteger(n)&&n>=lo&&n<=hi,k+' outside range');view.setUint32(offset,n,true)}
 const models=changes.models||{},parameters=changes.parameters||{},enabled=changes.enabled||{};
 ok(obj(models)&&obj(parameters)&&obj(enabled),'models/parameters/enabled must be objects');
 const sel=slots.inspect(template);
 if(changes.clone_slot!==undefined){
  ok(sel.selectorKnown,'Unexpected Clone selector bytes');
  const slot=changes.clone_slot;ok(Number.isInteger(slot)&&slot>=1&&slot<=5,'Clone slot must be 1..5');
  bytes[175]=slot-1;
 }
 const newModel={};
 for(const [module,model] of Object.entries(models)){
  const i=MODS.indexOf(module);ok(i>=1&&i<=8&&module!=='Clone','Bad stock module '+module);
  const fields=modelSpec(catalog,module,model);
  const at=139+4*i;
  if(module==='IR'){
   // Five genuine SONIC LINK exports confirm: User IR n = [n-1, 00, 10, 0A].
   // Stock IR uses the same module family but a different 3rd selector byte.
   const userMatch=/^User IR ([1-5])$/.exec(model);
   if(userMatch){
    bytes[at]=Number(userMatch[1])-1;
    bytes[at+1]=0x00;
    bytes[at+2]=0x10;
    bytes[at+3]=0x0A;
   } else {
    ok(Object.hasOwn(CODES.IR,model),'Unverified native selector '+module+'.'+model);
    bytes[at]=CODES.IR[model];
    bytes[at+1]=0x00;
    bytes[at+2]=0x00;
    bytes[at+3]=0x0A;
   }
  } else if(module==='FX1'||module==='FX2'){
   const hex=fxNative?.models?.[module]?.[model]?.prst_selector;
   ok(typeof hex==='string'&&/^[\da-fA-F]{8}$/.test(hex),'Missing FX selector for '+module+'.'+model);
   for(let j=0;j<4;j++)bytes[at+j]=parseInt(hex.slice(j*2,j*2+2),16);
  }else{
   ok(Object.hasOwn(CODES[module]||{},model),'Unverified native selector '+module+'.'+model);
   bytes[at]=CODES[module][model]; // preserve three opaque module bytes
  }
  newModel[module]=model;
  for(const field of fields){ok(Number.isInteger(field.algId)&&field.algId>=0&&field.algId<=7,'Bad parameter algId');safeValue(field,field.default,module);view.setFloat32(183+32*i+4*field.algId,field.default,true)}
 }
 for(const [module,values] of Object.entries(parameters)){
  const i=MODS.indexOf(module);ok(i>=0&&obj(values),'Invalid parameter block '+module);
  let model=newModel[module];
  if(module==='NR')model='Gate';
  if(module==='Clone'){
   ok(input.selectorKnown,'Clone selector unknown');
   model='User Profile '+(changes.clone_slot??input.cloneSlot);
  }
  ok(model,'Set a model for active '+module+' before writing parameters');
  const fields=modelSpec(catalog,module,model);
  for(const [label,value]of Object.entries(values)){
   const field=fields.find(f=>f.name===label);
   ok(field,'Unknown parameter '+module+'.'+label);
   safeValue(field,value,module);
   view.setFloat32(183+32*i+4*field.algId,value,true);
  }
 }
 // Void MOD: Clone uses full-rig NAM with its own speaker. Force the
 // hardware IR enabled-mask bit OFF regardless of donor or source JSON.
 const cloneOn = enabled.Clone===true || (enabled.Clone===undefined && input.cloneEnabled);
 if(cloneOn && enabled.IR===true)throw Error('Void MOD: IR cannot be enabled with Clone');
 for(const [module,flag] of Object.entries(enabled)){
  const i=MODS.indexOf(module);ok(i>=0&&typeof flag==='boolean','Invalid enable flag '+module);
  const mask=view.getUint32(117,true);
  view.setUint32(117,flag?mask|(1<<i):mask&~(1<<i),true);
 }
 if(changes.signal_chain!==undefined){const chain=changes.signal_chain;
  ok(Array.isArray(chain)&&chain.length===10&&new Set(chain).size===10&&MODS.every(m=>chain.includes(m)),'Bad signal chain');
  for(let i=0;i<10;i++)bytes[125+i]=MODS.indexOf(chain[i]);
 }
 if(cloneOn)view.setUint32(117,view.getUint32(117,true)&~0x10,true);
 bytes[20]=slots.crc8(bytes.subarray(21));
 slots.inspect(bytes);
 return bytes;
}
module.exports={MODS,write};
