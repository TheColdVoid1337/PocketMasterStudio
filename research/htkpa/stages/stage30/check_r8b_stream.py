#!/usr/bin/env python3
"""Synthetic r8brain chunk invariance: not native Sonicake parity."""
import json, math, pathlib, struct, subprocess, sys, tempfile, hashlib
def values(path):
    data=path.read_bytes()
    return struct.unpack("<"+str(len(data)//8)+"d",data)
def main(exe):
    with tempfile.TemporaryDirectory() as temp:
        d=pathlib.Path(temp)
        x=[(0.6 if k==100 else 0.0)+.11*math.sin(k*k*1.73e-5)+.025*math.sin(k*.337)+(0.015 if k>5000 else 0) for k in range(16000)]
        source=d/"source.f64le"
        source.write_bytes(struct.pack("<"+str(len(x))+"d",*x))
        runs=[]
        for block in (256,1024,4096,16000):
            output=d/("out_"+str(block)+".f64le")
            command=[str(exe),str(source),str(output),str(block),"2","44100","48000"]
            result=subprocess.run(command,check=True,capture_output=True,text=True)
            record=json.loads(result.stdout)
            record["sha256"]=hashlib.sha256(output.read_bytes()).hexdigest()
            runs.append(record)
        count={x["output_samples"] for x in runs}
        if len(count)!=1:raise AssertionError("chunk-dependent output lengths")
        arrays=[values(d/("out_"+str(b)+".f64le")) for b in (256,1024,4096,16000)]
        diffs=[max((abs(a-b) for a,b in zip(arrays[0],array)),default=0) for array in arrays[1:]]
        if max(diffs)>1e-12:raise AssertionError("chunk-dependent samples: "+str(diffs))
        print(json.dumps({"status":"PASS_SYNTHETIC_ONLY","source_samples":len(x),"max_abs_diff":diffs,"runs":runs,"native_sonicake_parity":"NOT_TESTED"},indent=2))
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: check_r8b_stream.py executable")
    main(pathlib.Path(sys.argv[1]))
