// Stage39: full public CDSPBlockConvolver vs original Sonicake first 1972-f64 block.
// Upstream r8brain-free-src MIT (c) 2013-2026 Aleksey Vaneev.
// Pinned revision: cb2abb9977efe2471979b380ed95daa56ab4fdb9.
// CAUTION: This is a comparative experiment; not vendor version identification.
#include "CDSPResampler.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(sizeof(double)==8, "requires 64-bit double");
static std::vector<double> load(const char* path, const size_t n) {
    std::ifstream f(path, std::ios::binary|std::ios::ate);
    if(!f)throw std::runtime_error("could not open private input");
    if(f.tellg() != static_cast<std::streamoff>(n*8))
        throw std::runtime_error("unexpected byte count");
    f.seekg(0);
    std::vector<double> values(n);
    f.read(reinterpret_cast<char*>(values.data()), n*8);
    if(!f)throw std::runtime_error("short private input read");
    for(double v:values)if(!std::isfinite(v))throw std::runtime_error("nonfinite input");
    return values;
}
int main(int argc, char** argv) {
  try {
    if(argc!=3) {
      std::cerr<<"usage: r8b_convolver_gate INPUT_2680.f64le EXPECTED_1972.f64le\n";
      return 2;
    }
    auto input=load(argv[1],2680);
    auto expected=load(argv[2],1972);
    r8b::CDSPFIRFilter& filter=r8b::CDSPFIRFilterCache::getLPFilter(
      0.5, 2.0, 180.15, r8b::fprLinearPhase, 2.0, 1);
    const int taps=filter.getKernelLen();
    const int blockBits=filter.getBlockLenBits();
    r8b::CDSPBlockConvolver conv(filter,2,1,0.0,true);
    std::vector<double> out(2680*2+4096,0.0);
    double* result=out.data();
    const int got=conv.process(input.data(),static_cast<int>(input.size()),result);
    if(got<0 || got>static_cast<int>(out.size()))
      throw std::runtime_error("bad convolver output count");
    // conv must never return a different output pointer in this test.
    if(result!=out.data())throw std::runtime_error("unexpected output pointer rewrite");
    size_t checked=std::min<size_t>(got,expected.size());
    double maxabs=0.0, sqsum=0.0;
    size_t exact=0;
    for(size_t i=0;i<checked;i++){
      const double a=result[i],b=expected[i];
      if(!std::isfinite(a))throw std::runtime_error("nonfinite output");
      if(std::memcmp(&a,&b,8)==0)exact++;
      const double d=std::abs(a-b);
      maxabs=std::max(maxabs,d);sqsum+=d*d;
    }
    const bool count_ok=got==static_cast<int>(expected.size());
    const bool numeric_ok=count_ok && maxabs<=1e-12;
    std::cout<<"{\"status\":\""<<(numeric_ok?"PASS_NUMERIC_CONVOLVER":"NOT_MATCHED")
      <<"\",\"public_filter_taps\":"<<taps
      <<",\"public_fft_length\":"<<(2<<blockBits)
      <<",\"expected_taps\":1417,\"expected_fft_length\":4096"
      <<",\"input_f64\":"<<input.size()<<",\"output_f64\":"<<got
      <<",\"expected_output_f64\":"<<expected.size()<<",\"compared\":"<<checked
      <<",\"bit_exact\":"<<exact<<",\"max_abs\":"<<std::setprecision(17)<<maxabs
      <<",\"rms\":"<<(checked?std::sqrt(sqsum/checked):0)
      <<",\"scope\":\"first FIR stage and exact alignment; NOT fractional interp or final 48k\"}\n";
    return numeric_ok?0:3;
  }catch(const std::exception& e){std::cerr<<"[ERROR] "<<e.what()<<"\n";return 1;}
}
