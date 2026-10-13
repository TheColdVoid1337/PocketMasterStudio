// Stage40: compare public pinned r8brain FIR spectra with original vendor filter FFT.
// No proprietary data linked or committed. Upstream MIT, Aleksey Vaneev / Voxengo.
#include "CDSPResampler.h"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <cstddef>
static_assert(sizeof(r8b::realfft_t)==8,"Stage40 requires double FFT");
void write_one(const std::string& file, const double cutoff, const int expected_taps) {
    r8b::CDSPFIRFilter& filter=r8b::CDSPFIRFilterCache::getLPFilter(
        cutoff,2.0,180.15,r8b::fprLinearPhase,2.0,1);
    const int taps=filter.getKernelLen();
    const int fft_n=2 << filter.getBlockLenBits();
    if(fft_n!=4096)throw std::runtime_error("Unexpected FFT length");
    if(taps!=expected_taps)throw std::runtime_error("Unexpected FIR length");
    const auto* spectrum=filter.getKernelBlock();
    if(!spectrum)throw std::runtime_error("Missing public FIR spectrum");
    std::ofstream output(file,std::ios::binary);
    if(!output)throw std::runtime_error("Cannot write local spectrum");
    output.write(reinterpret_cast<const char*>(spectrum),
                 static_cast<std::streamsize>(sizeof(r8b::realfft_t)*fft_n));
    if(!output)throw std::runtime_error("Short spectrum write");
    std::cout<<"{\"cutoff\":"<<std::setprecision(17)<<cutoff
             <<",\"taps\":"<<taps<<",\"fft_samples\":"<<fft_n
             <<",\"output_file\":\""<<file<<"\"}\n";
    filter.unref();
}
int main(int argc,char** argv) {
    try {
        if(argc!=3){std::cerr<<"usage: r8b_kernel_gate PUBLIC_1417.bin PUBLIC_1543.bin\n";return 2;}
        write_one(argv[1],0.5,1417);
        write_one(argv[2],0.459375,1543);
        return 0;
    } catch(const std::exception& e){
        std::cerr<<"[ERROR] "<<e.what()<<"\n";return 1;
    }
}
