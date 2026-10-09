/* Pocket Master native Clone slot/mode editor. Paired SONICLINK exports, 2026-10-09.
 * Mode: mask bit 9 at offset 117. Slot: byte 175, values 0..4 (slots 1..5).
 * Native selector: [slot - 1, 0, 0, 0x0F]. Does NOT embed NAM models.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PRSTCloneSlots = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const asBytes = (x) => {
    if (x instanceof ArrayBuffer) return new Uint8Array(x.slice(0));
    if (ArrayBuffer.isView(x)) return new Uint8Array(x.buffer.slice(x.byteOffset, x.byteOffset+x.byteLength));
    throw new TypeError('Expected a byte buffer');
  };
  function crc8(data) {
    let c=0;
    for (const b of data) {
      c ^= b;
      for (let j=0; j<8; j++) c = (c&128) ? ((c<<1)^7)&255 : (c<<1)&255;
    }
    return c;
  }
  function inspect(raw) {
    const b=asBytes(raw);
    if (b.length!==515 || String.fromCharCode(...b.subarray(0,13))!=='Pocket Master')
      throw new Error('Not the documented 515-byte Pocket Master PRST format');
    const v=new DataView(b.buffer);
    if (v.getUint16(113,true)!==0x3001 || v.getUint16(135,true)!==0x3003 ||
        v.getUint16(137,true)!==40 || v.getUint16(179,true)!==0x3004)
      throw new Error('Unexpected PRST effect section layout');
    if (crc8(b.subarray(21))!==b[20]) throw new Error('Invalid PRST CRC-8/SMBUS');
    const selector=b.subarray(175,179);
    const known = selector[1]===0 && selector[2]===0 && selector[3]===15 && selector[0]<=4;
    return {cloneEnabled: Boolean(v.getUint32(117,true)&0x200),
      cloneSlot: known ? selector[0]+1 : null,
      selectorKnown: known,
      selector: [...selector]};
  }
  function edit(raw, {slot, enabled}={}) {
    const b=asBytes(raw), found=inspect(b);
    if (slot!==undefined && (!Number.isInteger(slot) || slot<1 || slot>5))
      throw new RangeError('Clone slot must be an integer from 1 to 5');
    if (enabled!==undefined && typeof enabled!=='boolean')
      throw new TypeError('Clone enabled must be boolean');
    if ((slot!==undefined || enabled===true) && !found.selectorKnown)
      throw new Error('Unknown Clone selector layout: refusing to modify');
    if (slot!==undefined) b[175]=slot-1;
    if (enabled!==undefined) {
      const v=new DataView(b.buffer),mask=v.getUint32(117,true);
      v.setUint32(117, enabled ? mask|0x200 : mask&~0x200, true);
    }
    b[20]=crc8(b.subarray(21));
    inspect(b);
    return b;
  }
  return Object.freeze({inspect,edit,crc8});
});
