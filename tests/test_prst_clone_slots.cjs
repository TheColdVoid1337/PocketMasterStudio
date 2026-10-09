'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const clone=require('../tools/prst_clone_slots.js');
const input=fs.readFileSync(path.resolve(__dirname,'../templates/pocket_master_reference.prst'));
assert.deepEqual(Buffer.from(clone.edit(input,{})),input);
for(let i=1;i<=5;i++) {
  const out=clone.edit(input,{slot:i,enabled:true});
  assert.equal(clone.inspect(out).cloneEnabled,true);
  assert.equal(clone.inspect(out).cloneSlot,i);
  assert.deepEqual(clone.inspect(out).selector,[i-1,0,0,15]);
  assert.equal(clone.inspect(clone.edit(out,{enabled:false})).cloneEnabled,false);
  assert.equal(clone.inspect(clone.edit(out,{enabled:false})).cloneSlot,i);
}
assert.throws(()=>clone.edit(input,{slot:6}),/from 1 to 5/);
assert.throws(()=>clone.edit(input,{slot:0}),/from 1 to 5/);
const broken=new Uint8Array(input);broken[30]^=1;
assert.throws(()=>clone.inspect(broken),/CRC/);
console.log('PASS Clone slot 1..5, mode toggles, byte preservation, CRC rejection');
