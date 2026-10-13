// Stage45: genuine Sonicake FIRST FIR output -> real PUBLIC r8brain fractional stage.
// Original raw 1972-f64 FIR output is supplied only as a local private file.
// This is a vendor-FIR/public-fractional HYBRID, NOT native final 48 kHz output.
#include "CDSPFracInterpolator.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(sizeof(double)==8,"64-bit doubles required");

int main(int argc,char** argv) {
  try {
    if(argc!=4) {
      std::cerr<<"usage: hybrid_fractional VENDOR_FIRST_FIR_1972.f64le OUTPUT.f64le CHUNK\n";
      return 2;
    }
    std::ifstream f(argv[1],std::ios::ate|std::ios::binary);
    if(!f || f.tellg()!=static_cast<std::streamoff>(1972*8))
      throw std::runtime_error("expected exactly 1972 f64 private native FIR output");
    f.seekg(0);
    std::vector<double> input(1972);
    f.read(reinterpret_cast<char*>(input.data()),1972*8);
    if(!f)throw std::runtime_error("input read failed");
    for(const auto x:input) if(!std::isfinite(x))
      throw std::runtime_error("nonfinite native FIR input");
    const int chunk=std::stoi(argv[3]);
    if(chunk<=0 || chunk>1972)throw std::runtime_error("invalid chunk");

    // Matches public CDSPResampler's second stage of 44100 -> 48000
    // under Stage44's first-stage linear FIR assumptions.
    r8b::CDSPFracInterpolator frac(88200.0,48000.0,180.15,false,0.0);
    std::vector<double> output;
    output.reserve(2048);
    std::vector<double> scratch(frac.getMaxOutLen(chunk)+128,0.0);
    int calls=0;
    for(size_t p=0;p<input.size();) {
      const int n=static_cast<int>(std::min<size_t>(chunk,input.size()-p));
      double* dst=scratch.data();
      const int got=frac.process(input.data()+p,n,dst);
      if(got<0||got>static_cast<int>(scratch.size())||dst!=scratch.data())
        throw std::runtime_error("invalid fractional interpolator output pointer/size");
      for(int k=0;k<got;k++) {
        if(!std::isfinite(dst[k]))throw std::runtime_error("nonfinite public fractional output");
        output.push_back(dst[k]);
      }
      p+=n;
      ++calls;
    }
    std::ofstream out(argv[2],std::ios::binary);
    if(!out)throw std::runtime_error("cannot open temporary hybrid file");
    if(!output.empty())
      out.write(reinterpret_cast<const char*>(output.data()),
                static_cast<std::streamsize>(output.size()*8));
    if(!out)throw std::runtime_error("failed to write temporary hybrid output");
    std::cout<<"{\"input_f64\":1972,\"output_f64\":"<<output.size()
      <<",\"chunk_f64\":"<<chunk<<",\"process_calls\":"<<calls
      <<",\"source_hz\":88200,\"target_hz\":48000"
      <<",\"attenuation_db\":180.15,\"prev_latency\":0"
      <<",\"scope\":\"original vendor first FIR followed by PUBLIC fractional interpolation; vendor final output unavailable\"}\n";
    return 0;
  } catch(const std::exception& e) {
    std::cerr<<"[ERROR] "<<e.what()<<"\n";
    return 1;
  }
}
