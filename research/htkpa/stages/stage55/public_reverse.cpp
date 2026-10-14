// Stage55: pure PUBLIC r8brain reverse fractional benchmark.
// Expects native 96-kHz inputs captured by Stage54 (3 then 256 f64).
// Public generated samples remain local, never added to Git.
#include "CDSPFracInterpolator.h"
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static std::vector<double> load(const char* name, int expected) {
    std::ifstream file(name, std::ios::binary | std::ios::ate);
    if (!file || file.tellg() != static_cast<std::streamoff>(expected * 8))
        throw std::runtime_error("wrong private input size");
    file.seekg(0);
    std::vector<double> result(expected);
    file.read(reinterpret_cast<char*>(result.data()), expected * 8);
    if (!file) throw std::runtime_error("input read failure");
    for (double value : result)
        if (!std::isfinite(value)) throw std::runtime_error("non-finite input f64");
    return result;
}

int main(int argc, char** argv) {
    try {
        if (argc != 7) {
            std::cerr << "usage: public_reverse IN3_F64 IN256_F64 OUTPUT_F64 ATTENUATION IS_THIRD PREVIOUS_LATENCY\n";
            return 2;
        }
        auto a = load(argv[1], 3);
        auto b = load(argv[2], 256);
        const double attenuation = std::stod(argv[4]);
        const int third = std::stoi(argv[5]);
        const double latency = std::stod(argv[6]);
        if (!(attenuation >= 80.0 && attenuation <= 240.0) ||
            (third != 0 && third != 1) || !std::isfinite(latency) ||
            latency < 0.0 || latency > 1000.0)
            throw std::runtime_error("unsupported controlled public hypothesis");
        r8b::CDSPFracInterpolator frac(96000., 44100., attenuation,
                                       third == 1, latency);
        std::vector<double> scratch(frac.getMaxOutLen(256) + 256, 0.0);
        std::vector<double> output;
        int lengths[2] = {};
        double* dest = scratch.data();
        lengths[0] = frac.process(a.data(), 3, dest);
        if (lengths[0] < 0 || lengths[0] > static_cast<int>(scratch.size()) ||
            (lengths[0] && !dest))
            throw std::runtime_error("invalid first public count/pointer");
        for (int i = 0; i < lengths[0]; i++) output.push_back(dest[i]);
        dest = scratch.data();
        lengths[1] = frac.process(b.data(), 256, dest);
        if (lengths[1] < 0 || lengths[1] > static_cast<int>(scratch.size()) ||
            (lengths[1] && !dest))
            throw std::runtime_error("invalid second public count/pointer");
        for (int i = 0; i < lengths[1]; i++) output.push_back(dest[i]);
        for (double d : output)
            if (!std::isfinite(d)) throw std::runtime_error("non-finite public output");
        std::ofstream out(argv[3], std::ios::binary);
        if (!out) throw std::runtime_error("cannot create local output");
        if (!output.empty()) out.write(
            reinterpret_cast<const char*>(output.data()),
            static_cast<std::streamsize>(output.size() * 8));
        if (!out) throw std::runtime_error("write failed");
        std::cout << "{\"input_f64\":[3,256],\"output_f64\":["
                  << lengths[0] << "," << lengths[1]
                  << "],\"total_f64\":" << output.size()
                  << ",\"src_hz\":96000,\"dst_hz\":44100,"
                  << "\"attenuation_db\":" << attenuation
                  << ",\"is_third\":" << third
                  << ",\"previous_latency\":" << latency << "}\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "[ERROR] " << e.what() << "\n";
        return 1;
    }
}
