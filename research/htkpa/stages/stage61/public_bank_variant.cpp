// Stage61: strictly bounded PUBLIC bank parameter scan, not a native DLL tool.
// The Stage59 baseline uses reqAtten=180.15 / IsThird=false; this version exposes
// only attenuation and IsThird for controlled, SHA-pinned source comparisons.
#include "CDSPFracInterpolator.h"
#include <cmath>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc,char** argv) {
  try {
    if(argc != 4) {
      std::cerr<<"usage: public_bank_variant OUTPUT.f64le REQUESTED_ATTENUATION IS_THIRD(0|1)\n";
      return 2;
    }
    const double attenuation=std::stod(argv[2]);
    const int third=std::stoi(argv[3]);
    if(!std::isfinite(attenuation) || attenuation<160.0 ||
       attenuation>205.0 || (third!=0 && third!=1))
      throw std::runtime_error("parameter outside controlled hypothesis bounds");
    double rounded=attenuation;
    r8b::CDSPFracDelayFilterBank::roundReqAtten(rounded,third==1);
    auto& bank=r8b::CDSPFracDelayFilterBankCache::getFilterBank(
      673,3,8,attenuation,third==1,false);
    const int taps=bank.getFilterLen(), fracs=bank.getFilterFracs();
    if(taps!=24 || fracs!=673) {
      std::cout<<"{\"geometry_ok\":false,\"taps\":"<<taps
               <<",\"phases\":"<<fracs
               <<",\"requested_attenuation\":"<<attenuation
               <<",\"effective_attenuation\":"<<rounded
               <<",\"is_third\":"<<third<<"}\n";
      bank.unref();
      return 0;
    }
    constexpr int size=673*24*3;
    constexpr int bytes=size*8;
    const double* table=&bank[0];
    for(int i=0;i<size;++i)
      if(!std::isfinite(table[i]))
        throw std::runtime_error("public coefficient not finite");
    std::ofstream out(argv[1],std::ios::binary);
    if(!out) throw std::runtime_error("cannot open private coefficient output");
    out.write(reinterpret_cast<const char*>(table),bytes);
    if(!out) throw std::runtime_error("private coefficient output write failed");
    bank.unref();
#if defined(R8B_SIMD_ISH)
    const char* layout="simd_pairs_2tap";
#else
    const char* layout="scalar_triplets";
#endif
    std::cout<<"{\"geometry_ok\":true,\"taps\":24,\"phases\":673,"
             <<"\"bytes\":387648,\"layout\":\""<<layout
             <<"\",\"requested_attenuation\":"<<attenuation
             <<",\"effective_attenuation\":"<<rounded
             <<",\"is_third\":"<<third<<"}\n";
    return 0;
  } catch(const std::exception& e) {
    std::cerr<<"[ERROR] "<<e.what()<<"\n";
    return 1;
  }
}
