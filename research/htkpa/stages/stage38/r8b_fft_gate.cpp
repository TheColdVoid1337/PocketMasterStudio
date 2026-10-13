// Stage38: public r8brain CDSPRealFFT vs native Sonicake intermediate buffers.
// r8brain-free-src: MIT; (c) 2013-2026 Aleksey Vaneev.
// Source pin: cb2abb9977efe2471979b380ed95daa56ab4fdb9
#include "CDSPRealFFT.h"
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

static_assert(sizeof(r8b::realfft_t) == sizeof(double),
              "Stage38 requires double-precision r8brain FFT build");
static std::vector<double> load(const std::string& name) {
    std::ifstream in(name, std::ios::binary | std::ios::ate);
    if (!in) throw std::runtime_error("cannot read native buffer: " + name);
    const auto size = in.tellg();
    if (size != 32768) throw std::runtime_error("expected exactly 4096 f64: " + name);
    in.seekg(0);
    std::vector<double> out(4096);
    in.read(reinterpret_cast<char*>(out.data()), 32768);
    if (!in) throw std::runtime_error("short read: " + name);
    return out;
}
struct Metrics {
    double max_abs = 0.0;
    double sum_sq = 0.0;
    int exact = 0;
    int total = 0;
    int first_mismatch = -1;
    void add(const double a, const double b) {
        if (!std::isfinite(a) || !std::isfinite(b))
            throw std::runtime_error("nonfinite FFT result");
        if (std::memcmp(&a, &b, sizeof(double)) == 0) exact++;
        else if (first_mismatch < 0) first_mismatch = total;
        const double d = std::fabs(a-b);
        max_abs = std::max(max_abs, d);
        sum_sq += d*d;
        total++;
    }
    void show(const char* stage, const int index) const {
        std::cout << "{\"frame\":" << index
                  << ",\"stage\":\"" << stage
                  << "\",\"compared_f64\":" << total
                  << ",\"bit_exact\":" << exact
                  << ",\"first_bit_mismatch\":" << first_mismatch
                  << ",\"max_abs\":" << std::setprecision(17) << max_abs
                  << ",\"rms\":" << std::sqrt(sum_sq/total) << "}\n";
    }
};

int main(int argc, char** argv) {
    try {
        if (argc != 2) {
            std::cerr << "usage: r8b_fft_gate PATH_TO_EXTRACTED_20261013_output_route\n";
            return 2;
        }
        const std::string dir = argv[1];
        r8b::CDSPRealFFTKeeper fft2048(11);
        r8b::CDSPRealFFTKeeper fft4096(12);
        bool passed = true;
        for (int i=0; i<2; i++) {
            const std::string n=(i==0 ? "_00.f64le.bin":"_01.f64le.bin");
            auto pre=load(dir+"/input_pre_fft"+n);
            const auto native_fft=load(dir+"/input_post_fft"+n);
            auto spectrum=std::vector<double>(pre.begin(),pre.begin()+2048);
            fft2048->forward(spectrum.data());
            Metrics fwd;
            for (int k=0; k<2048; k++) fwd.add(spectrum[k],native_fft[k]);
            fwd.show("r8brain_2048_forward_vs_native",i);

            auto multiplied=load(dir+"/after_spectral_multiply"+n);
            const auto native_inverse=load(dir+"/after_inverse"+n);
            fft4096->inverse(multiplied.data());
            Metrics inv;
            for (int k=0; k<4096; k++) inv.add(multiplied[k],native_inverse[k]);
            inv.show("r8brain_4096_inverse_vs_native",i);
            passed &= fwd.max_abs <= 1e-13 && inv.max_abs <= 1e-13;
        }
        std::cout<<"{\"status\":\""<<(passed?"PASS_NUMERICAL_FFT_ONLY":"MISMATCH")
                 <<"\",\"source\":\"pinned_public_r8brain_7_6\","
                 <<"\"limit\":\"FFT kernels only; not full block convolution or final 48000 Hz resampler\"}\n";
        return passed?0:1;
    } catch (const std::exception& e) {
        std::cerr<<"[ERROR] "<<e.what()<<"\n";
        return 1;
    }
}
