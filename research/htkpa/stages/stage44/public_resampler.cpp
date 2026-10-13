// HTKPA Stage44: full PUBLIC 44100->48000 r8brain resampling pilot.
// This is not original Sonicake final-output parity.
// Pin original MIT source externally to historical releases v6.5/v7.2/v7.6.
#include "CDSPResampler.h"
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static_assert(sizeof(double)==8, "f64 expected");

int main(int argc, char** argv) {
  try {
    if(argc != 4) {
      std::cerr<<"usage: public_resampler INPUT_2680_F64 OUTPUT_F64 BLOCK_SAMPLES\n";
      return 2;
    }
    std::ifstream in(argv[1],std::ios::binary|std::ios::ate);
    if(!in || in.tellg() != static_cast<std::streamoff>(2680*8))
       throw std::runtime_error("expected exactly 2680 original f64 samples");
    in.seekg(0);
    std::vector<double> samples(2680);
    in.read(reinterpret_cast<char*>(samples.data()),2680*8);
    if(!in)throw std::runtime_error("input read failed");
    for(double v:samples)if(!std::isfinite(v))throw std::runtime_error("nonfinite source");
    const int block=std::stoi(argv[3]);
    if(block<1 || block>2680)throw std::runtime_error("invalid chunk size");
    // ReqTransBand=2%, ReqAtten=180.15, linear phase deliberately match
    // Stage43's first FIR filter. This is still an explicit hypothesis.
    r8b::CDSPResampler res(44100.0,48000.0,block,2.0,180.15,
                            r8b::fprLinearPhase);
    std::vector<double> result;
    result.reserve(5000);
    int calls=0;
    for(size_t p=0;p<samples.size();) {
      const int len=static_cast<int>(std::min<size_t>(block,samples.size()-p));
      double* op=nullptr;
      const int count=res.process(samples.data()+p,len,op);
      if(count<0 || count>50000 || (count && !op))
          throw std::runtime_error("invalid public resampler result");
      for(int k=0;k<count;k++) {
        if(!std::isfinite(op[k]))throw std::runtime_error("nonfinite output");
        result.push_back(op[k]);
      }
      p+=len;
      calls++;
    }
    std::ofstream out(argv[2],std::ios::binary);
    if(!out)throw std::runtime_error("cannot create temporary result");
    if(!result.empty())
        out.write(reinterpret_cast<const char*>(result.data()),
                  static_cast<std::streamsize>(result.size()*8));
    if(!out)throw std::runtime_error("result write failed");
    std::cout<<"{\"source_hz\":44100,\"target_hz\":48000,"
             <<"\"transband_percent\":2.0,\"attenuation_db\":180.15,"
             <<"\"phase\":\"linear\",\"input_f64\":2680,"
             <<"\"output_f64\":"<<result.size()
             <<",\"chunk_f64\":"<<block
             <<",\"process_calls\":"<<calls
             <<",\"latency\":"<<res.getLatency()
             <<",\"latency_frac\":"<<std::setprecision(17)<<res.getLatencyFrac()
             <<",\"scope\":\"public r8brain output only; vendor final output unavailable\"}\n";
    return 0;
  }catch(const std::exception& e){
    std::cerr<<"[ERROR] "<<e.what()<<"\n";return 1;
  }
}
