// HTKPA recovered Sonicake 1.5.2 fractional resampler — isolated C ABI.
// Original mathematical implementation: MIT-licensed r8brain-free-src v6.5.
// Build ONLY against SHA-pinned PUBLIC sources, with temporary constructor
// patch produced by stage63.patch_header(...,"native_window_poly_673").
// No vendor/DLL code or audio is embedded. This is not yet browser runtime.
//
// Modes established by real native output measurements:
//   1 = exact fractional 96000->44100, constructor 180.15 / false / 0
//   2 = 44100->48000 chain, 2% transition / 180.15 attenuation / linear,
//       internal fractional stage uses the same original DLL Kaiser + 673.
//
// Opaque handles own stream state; independent handles never share it.
// After reset(), sample timing and convolution history return to zero state.
// Return >=0: output f64 samples, <0: C ABI error. No C++ exceptions cross C.
#include "CDSPFracInterpolator.h"
#include "CDSPResampler.h"
#include <cmath>
#include <cstring>
#include <memory>
#include <new>
#include <vector>

namespace {
constexpr int kReverse=1;
constexpr int kForward=2;
constexpr int kMaxInput=2680;
constexpr int kBadArgs=-1;
constexpr int kBufferTooSmall=-2;
constexpr int kExecutionFailure=-3;
constexpr int kNonFinite=-4;
struct Context {
    int mode;
    std::unique_ptr<r8b::CDSPFracInterpolator> fractional;
    std::unique_ptr<r8b::CDSPResampler> chain;
    explicit Context(int which) : mode(which) {
        if (mode==kReverse) {
            fractional.reset(new r8b::CDSPFracInterpolator(
                96000.0,44100.0,180.15,false,0.0));
        } else if(mode==kForward) {
            chain.reset(new r8b::CDSPResampler(
                44100.0,48000.0,kMaxInput,2.0,180.15,
                r8b::fprLinearPhase));
        }
    }
    int max_out(int n) {
        return mode==kReverse ? fractional->getMaxOutLen(n)
                              : chain->getMaxOutLen(n);
    }
    void reset() {
        if(mode==kReverse) fractional->clear();
        else chain->clear();
    }
};
}

#if defined(_WIN32)
#define HTKPA_API extern "C" __declspec(dllexport)
#elif defined(__GNUC__) || defined(__clang__)
#define HTKPA_API extern "C" __attribute__((visibility("default")))
#else
#define HTKPA_API extern "C"
#endif

HTKPA_API const char* htkpa_v1_id(void) noexcept {
    return "r8brain-v6.5__sonicake-1.5.2__kaiser12.55262798_1.51553897__poly673";
}

HTKPA_API void* htkpa_v1_open(int mode) noexcept {
    if(mode!=kReverse && mode!=kForward) return nullptr;
    try {
        return static_cast<void*>(new Context(mode));
    } catch (...) {
        return nullptr;
    }
}

HTKPA_API int htkpa_v1_min_output_capacity(
    void* opaque,int input_count) noexcept {
    if(!opaque || input_count<0 || input_count>kMaxInput) return kBadArgs;
    try {
        Context* ctx=static_cast<Context*>(opaque);
        return ctx->max_out(input_count);
    } catch (...) {
        return kExecutionFailure;
    }
}

HTKPA_API int htkpa_v1_process(
    void* opaque,const double* input,int input_count,
    double* output,int output_capacity) noexcept {
    if(!opaque || input_count<0 || input_count>kMaxInput ||
       output_capacity<0 || (input_count>0 && !input) ||
       (output_capacity>0 && !output))
        return kBadArgs;
    try {
        Context* ctx=static_cast<Context*>(opaque);
        const int required=ctx->max_out(input_count);
        if(required<0 || required>100000) return kExecutionFailure;
        if(output_capacity<required) return kBufferTooSmall;
        for(int i=0;i<input_count;++i)
            if(!std::isfinite(input[i]))return kNonFinite;
        // MIT API takes a mutable input pointer, so copy caller-owned data.
        std::vector<double> local(input_count>0 ? input_count : 1,0.0);
        if(input_count>0)
            std::memcpy(local.data(),input,
                        static_cast<std::size_t>(input_count)*sizeof(double));
        double* op=ctx->mode==kReverse ? output : nullptr;
        const int written=ctx->mode==kReverse
            ? ctx->fractional->process(local.data(),input_count,op)
            : ctx->chain->process(local.data(),input_count,op);
        if(written<0 || written>output_capacity ||
            (written>0 && !op))
            return kExecutionFailure;
        // Avoid committing non-finite samples or overwriting client input.
        for(int i=0;i<written;++i)
            if(!std::isfinite(op[i]))return kNonFinite;
        if(ctx->mode==kForward && written>0)
            std::memcpy(output,op,static_cast<std::size_t>(written)*sizeof(double));
        return written;
    } catch (...) {
        return kExecutionFailure;
    }
}

HTKPA_API int htkpa_v1_reset(void* opaque) noexcept {
    if(!opaque) return kBadArgs;
    try {
        static_cast<Context*>(opaque)->reset();
        return 0;
    } catch (...) {
        return kExecutionFailure;
    }
}

HTKPA_API void htkpa_v1_close(void* opaque) noexcept {
    try { delete static_cast<Context*>(opaque); } catch (...) {}
}
