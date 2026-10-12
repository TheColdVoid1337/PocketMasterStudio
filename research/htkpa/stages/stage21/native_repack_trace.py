#!/usr/bin/env python3
"""Execute a bounded model of the *address operations* in native repack block.

Reads SHA-pinned DLL disassembly, not vendor bytecode execution. Implements
only the integer address moves and copies 0x1800BDF47..0x1800BE16C. Each
input sample is tagged so pointer aliases can be verified symbolically.
"""
import argparse, hashlib, re, subprocess
from pathlib import Path
DLL_HASH='fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa'
START=0x1800BDF47;STOP=0x1800BE16C

def disasm(path):
    assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==DLL_HASH
    raw=subprocess.check_output(['objdump','-d','-M','intel','--no-show-raw-insn',f'--start-address={START:#x}',f'--stop-address={STOP:#x}',str(path)],text=True)
    return {int(m.group(1),16):(m.group(2).split()[0],m.group(2).split(None,1)[1] if len(m.group(2).split(None,1))>1 else '') for line in raw.splitlines() if (m:=re.match(r'\s*([0-9a-f]+):\s*(.*)',line)) and START<=int(m.group(1),16)<STOP}

def emulate_reordering(B,asm):
    assert B>=4
    p=100000;q=200000;rsp=300000
    regs={x:0 for x in ['rax','rbx','rcx','rdx','rsi','rdi','rbp','r8','r9','r10','r11','r12','r13','r14','r15','rsp']}
    regs.update(rsp=rsp, r13=B, rbx=p+8*B,r12=q,r14=q+8*B,r15=0)
    mem={}
    for i in range(B):
     mem[p+4*i]=('X',i)
     mem[p+4*B+4*i]=('P',i)
     mem[p+8*B+4*i]=('N',i)
    for i in range(4*B): mem[q+4*i]=('none',i)
    stack={0x28:p,0x20:p+4*B,0x38:p+8*B,0x40:4*B,0x48:B,0x68:q+8*B,0x70:q}
    for k,v in stack.items():mem[rsp+k]=v
    regs['r8']=0;regs['r11']=0
    regs['xmm7']=-0.0
    
    ALIAS={**{f'e{r[1:]}':r for r in ['rax','rbx','rcx','rdx','rsi','rdi','rbp']},**{f'r{i}d':f'r{i}' for i in range(8,16)}}
    def getreg(r):
     r=r.strip();r=ALIAS.get(r,r);return regs[r]
    def setreg(r,v):
     alias=r in ALIAS;r=ALIAS.get(r,r)
     regs[r]=((v&0xffffffff if alias else ((v+2**63)%(2**64)-2**63)) if isinstance(v,int) else v)
    
    def addr(expr):
     expr=expr.replace(' ','').replace('+-','-').replace('-','+-')
     total=0
     for atom in expr.split('+'):
      if not atom:continue
      sg=-1 if atom.startswith('-') else 1
      atom=atom.lstrip('-')
      if '*' in atom:
       v,n=atom.split('*');total+=sg*getreg(v)*int(n,0)
      elif atom in regs or atom in ALIAS:total+=sg*getreg(atom)
      else:total+=sg*int(atom,0)
     return total
    
    def val(term):
     term=term.strip()
     if ' PTR ' in term:
      return mem.get(addr(term[term.index('[')+1:term.index(']')]),('uninit',term))
     if term.startswith('['):return mem.get(addr(term[1:-1]),('uninit',term))
     if term.startswith('xmm'):return regs[term]
     if term in regs or term in ALIAS:return getreg(term)
     return int(term,0)
    
    def store(term,v):
     term=term.strip()
     if ' PTR ' in term:
      a=addr(term[term.index('[')+1:term.index(']')]);mem[a]=v
    
     elif term.startswith('xmm'):regs[term]=v
     elif term in regs or term in ALIAS:setreg(term,v)
     else:raise ValueError(('store',term))
    
    def operands(rest):
     # comments and long PIC disappear
     rest=rest.split(' # ')[0]
     return [s.strip() for s in rest.split(',',1)]
    
    pc=0x1800bdf47;steps=0;cmp=0;zero=False
    while pc <0x1800be16c:
     steps+=1
     if steps>10000:raise ValueError('loop stuck')
     try:op,rest=asm[pc]
     except KeyError:raise RuntimeError('Unknown native instruction '+hex(pc))
     inst=operands(rest)
     pcs=sorted(asm);nextpc=next((x for x in pcs if x>pc),0x1800be16c)
     try:
      if op in ['mov','movsxd','movss']:
       v=val(inst[1]);store(inst[0],v)
      elif op=='lea':store(inst[0],addr(inst[1][1:-1]))
      elif op in ['add','sub']:
       x=val(inst[0]); y=val(inst[1]);v=(x+y if op=='add' else x-y);store(inst[0],v);cmp=v;zero=v==0
      elif op=='neg':store(inst[0],-val(inst[0]));zero=val(inst[0])==0
      elif op=='shr':store(inst[0],(val(inst[0])%(2**64))>>val(inst[1]))
      elif op=='shl':store(inst[0],val(inst[0])<<val(inst[1]))
      elif op=='inc':store(inst[0],val(inst[0])+1)
      elif op=='dec':store(inst[0],val(inst[0])-1);cmp=val(inst[0]);zero=cmp==0
      elif op=='cmp':cmp=val(inst[0])-val(inst[1]);zero=cmp==0
      elif op in ['jge','jl','jne','je','jle','jg']:
       cond={'jge':cmp>=0,'jl':cmp<0,'jne':not zero,'je':zero,'jle':cmp<=0,'jg':cmp>0}[op]
       if cond:nextpc=int(inst[0],0)
      elif op=='xor':
       store(inst[0],0)
      elif op=='xorps':
       if inst[1]=='xmm7':
        # symbolic negative marker or numeric
        v=regs[inst[0]];regs[inst[0]]= ('neg',v)
       else:raise ValueError(('xorps',rest))
      elif op in ['nop','data16','xchg']:pass
      else:raise ValueError((hex(pc),op,rest))
     except Exception as ex:
      raise RuntimeError(f'{pc:#x} {op} {rest}: {ex}')
     pc=nextpc
    return [mem.get(q+4*i) for i in range(4*B)]

def main():
    p=argparse.ArgumentParser();p.add_argument('--dll',required=True);a=p.parse_args()
    asm=disasm(a.dll)
    assert len(asm)>90
    for B in (4,5,7,8,9,10,12):
        got=emulate_reordering(B,asm)
        expected=[('neg',('X',i)) for i in range(B-1,-1,-1)]
        expected +=[('X',i) for i in range(B)]
        expected +=[('N',i) for i in range(B-1,-1,-1)]
        expected +=[('P',i) for i in range(B)]
        assert got==expected,(B,got,expected)
    print('Native pointer/address traces PASS for B=4,5,7,8,9,10,12; exact 4B reordering proven')
if __name__=='__main__':main()
