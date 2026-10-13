// HTKPA Stage30: isolated public-r8brain signal probe; no vendor DLL linked.
// Upstream r8brain MIT: Copyright (c) 2013-2026 Aleksey Vaneev.
// Credit: Sample rate converter designed by Aleksey Vaneev of Voxengo.
#include "CDSPResampler.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(sizeof(double)==8, "IEEE f64 required");

static std::vector<double> read_f64(const std::string& file) {
  std::ifstream f(file,std::ios::binary|std::ios::ate);
  if(!f) throw std::runtime_error("cannot open f64le input");
  auto n=f.tellg();
  if(n<0 || (static_cast<uint64_t>(n)%8))throw std::runtime_error("input must be aligned f64le");
  if(n>128*1024*1024)throw std::runtime_error("input too large for bounded probe");
  f.seekg(0);
  std::vector<double> x(static_cast<size_t>(n)/8);
  if(!x.empty()&&!f.read(reinterpret_cast<char*>(x.data()),n))throw std::runtime_error("input read failed");
  return x;
}
int main(int argc,char** argv) {
 try {
  if(argc!=7) {
   std::cerr<<"usage: r8b_probe INPUT.f64le OUTPUT.f64le BLOCK_SAMPLES TRANSBAND SRC_HZ DST_HZ\n";
   return 2;
  }
  const int block=std::stoi(argv[3]);
  const double trans=std::stod(argv[4]),src=std::stod(argv[5]),dst=std::stod(argv[6]);
  if(block<1||block>32768||!(trans>0&&trans<=30)||!(src>=8000&&dst>=8000))throw std::runtime_error("invalid config");
  auto in=read_f64(argv[1]);
  for(double x:in)if(!std::isfinite(x))throw std::runtime_error("nonfinite input");
  r8b::CDSPResampler24 res(src,dst,block,trans);
  std::vector<double> out;out.reserve(static_cast<size_t>(in.size()*dst/src)+4096);
  size_t offset=0,blocks=0;
  while(offset<in.size()){
   int n=static_cast<int>(std::min<size_t>(block,in.size()-offset));
   double* ptr=nullptr;
   int got=res.process(in.data()+offset,n,ptr);
   if(got<0||static_cast<size_t>(got)>1000000)throw std::runtime_error("bad output count");
   if(got>0&&!ptr)throw std::runtime_error("null output pointer");
   if(got>0)out.insert(out.end(),ptr,ptr+got);offset+=n;blocks++;
  }
  std::ofstream f(argv[2],std::ios::binary);
  if(!f)throw std::runtime_error("cannot create output");
  if(!out.empty())f.write(reinterpret_cast<const char*>(out.data()),out.size()*sizeof(double));
  if(!f)throw std::runtime_error("write failed");
  std::cout<<"{\"source\":\"r8brain\",\"input_samples\":"<<in.size()
    <<",\"output_samples\":"<<out.size()<<",\"process_calls\":"<<blocks
    <<",\"block\":"<<block<<",\"transband\":"<<trans<<",\"source_hz\":"<<src
    <<",\"dest_hz\":"<<dst<<",\"latency\":"<<res.getLatency()<<"}\n";
 }catch(const std::exception& e){std::cerr<<"[ERROR] "<<e.what()<<"\n";return 1;}
}
