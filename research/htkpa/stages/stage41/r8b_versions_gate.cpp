// Stage41: historical r8brain-free-src spectrum fingerprint.
// Compile against each pinned upstream revision with HTKPA_LEGACY_API for <=7.2.
// Upstream copyright Aleksey Vaneev / Voxengo, MIT. Only our adapter lives here.
#include "CDSPResampler.h"
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

static_assert(sizeof(double) == 8, "Stage41 expects IEEE double-sized values");

static void dump(const char* file, const double cutoff, int nominal_taps) {
#if HTKPA_LEGACY_API
    r8b::CDSPFIRFilter& f = r8b::CDSPFIRFilterCache::getLPFilter(
        cutoff, 2.0, 180.15, r8b::fprLinearPhase, 2.0);
#else
    r8b::CDSPFIRFilter& f = r8b::CDSPFIRFilterCache::getLPFilter(
        cutoff, 2.0, 180.15, r8b::fprLinearPhase, 2.0, 1);
#endif
    const int n = 2 << f.getBlockLenBits();
    const int taps = f.getKernelLen();
    if(n <= 0 || n > 65536) throw std::runtime_error("invalid FIR FFT length");
    const double* const k = f.getKernelBlock();
    if(k == nullptr) throw std::runtime_error("no generated filter spectrum");
    for(int i=0;i<n;i++) if(!std::isfinite(k[i]))
        throw std::runtime_error("nonfinite packed spectrum");
    std::ofstream out(file, std::ios::binary);
    if(!out) throw std::runtime_error("unable to open local temporary binary");
    out.write(reinterpret_cast<const char*>(k), static_cast<std::streamsize>(n)*8);
    if(!out) throw std::runtime_error("short spectrum write");
    std::cout << "{\"cutoff\":" << std::setprecision(17) << cutoff
              << ",\"filter_taps\":" << taps
              << ",\"expected_taps\":" << nominal_taps
              << ",\"fft_f64\":" << n
              << ",\"alignment\":\"getKernelBlock_post_convertToZP\"}\n";
    f.unref();
}
int main(int argc, char** argv) {
    if(argc != 3) {
        std::cerr << "usage: r8b_versions_gate OUTPUT_1417 OUTPUT_1543\n";
        return 2;
    }
    try {
        dump(argv[1], 0.5, 1417);
        dump(argv[2], 0.459375, 1543);
        return 0;
    } catch(const std::exception& e) {
        std::cerr << "[ERROR] " << e.what() << "\n";
        return 1;
    }
}
