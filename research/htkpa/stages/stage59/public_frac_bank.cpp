// Stage59 PUBLIC r8brain coefficient-bank export for numerical comparison only.
// Read-only access to the public MIT bank. No native DLL loading.
#include "CDSPFracInterpolator.h"
#include <cmath>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc,char** argv) {
  try {
    if(argc != 3) {
      std::cerr<<"usage: public_frac_bank OUTPUT.f64le REQ_ATTEN\n";
      return 2;
    }
    const double req=std::stod(argv[2]);
    if(!std::isfinite(req) || req<170.0 || req>190.0)
      throw std::runtime_error("out-of-range public attenuation candidate");
    // Static native convolution loads 24 taps * 3 quadratic coefficients,
    // indexed by phase * 72. The table has 673 phase positions.
    auto& bank=r8b::CDSPFracDelayFilterBankCache::getFilterBank(
      673, 3, 8, req, false, false);
    if(bank.getFilterLen()!=24 || bank.getFilterFracs()!=673)
      throw std::runtime_error("public bank geometry mismatch");
    constexpr int fracs=673, taps=24, coeffs=3;
    constexpr int bytes=fracs*taps*coeffs*8;
    const double* p=&bank[0];
    for(int i=0;i<fracs*taps*coeffs;i++)
      if(!std::isfinite(p[i]))throw std::runtime_error("public coefficient is not finite");
    std::ofstream out(argv[1],std::ios::binary);
    if(!out) throw std::runtime_error("cannot open temporary coefficient output");
    out.write(reinterpret_cast<const char*>(p),bytes);
    if(!out) throw std::runtime_error("cannot write public coefficient bytes");
    bank.unref();
#if defined(R8B_SIMD_ISH)
    const char* layout="simd_pairs_2tap";
#else
    const char* layout="scalar_triplets";
#endif
    std::cout<<"{\"phases\":673,\"taps\":24,\"element_size\":3,"
             <<"\"bytes\":387648,\"layout\":\""<<layout<<"\",\"requested_attenuation\":"<<req
             <<"}\n";
    return 0;
  } catch(const std::exception& e) {
    std::cerr<<"[ERROR] "<<e.what()<<"\n";
    return 1;
  }
}
