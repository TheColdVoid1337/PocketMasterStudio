// HTKPA Stage98: use real upstream NeuralAmpModelerCore for model parsing and inference.
// This is deliberately NOT an implementation of the proprietary CLO fitter.
#include <algorithm>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include "NAM/dsp.h"
#include "NAM/get_dsp.h"
#include "NAM/slimmable.h"

namespace {
namespace fs = std::filesystem;
constexpr std::uintmax_t kMaxInputBytes = 128ULL * 1024 * 1024;
struct Options {
  fs::path model, input, output;
  int sample_rate = 0;
  int block = 64;
  bool prewarm = true;
  bool has_slim = false;
  double slim = 1.0;
};

double parse_double(const char* raw) {
  const std::string s(raw);
  std::size_t parsed = 0;
  const double val = std::stod(s, &parsed);
  if (parsed != s.size() || !std::isfinite(val))
    throw std::runtime_error("invalid finite numeric argument");
  return val;
}
int parse_int(const char* raw, int min, int max) {
  const double value = parse_double(raw);
  if (std::trunc(value) != value || value < min || value > max)
    throw std::runtime_error("integer argument outside permitted range");
  return static_cast<int>(value);
}
Options arguments(int argc, char** argv) {
  Options o;
  for (int i = 1; i < argc; ++i) {
    const std::string arg(argv[i]);
    if (i + 1 >= argc) throw std::runtime_error("missing argument value");
    const char* value = argv[++i];
    if (arg == "--model") o.model = value;
    else if (arg == "--input-f64le") o.input = value;
    else if (arg == "--output-f64le") o.output = value;
    else if (arg == "--sample-rate") o.sample_rate = parse_int(value, 8000, 192000);
    else if (arg == "--block") o.block = parse_int(value, 1, 4096);
    else if (arg == "--prewarm") {
      if (std::string(value) == "on") o.prewarm = true;
      else if (std::string(value) == "off") o.prewarm = false;
      else throw std::runtime_error("--prewarm must be on or off");
    } else if (arg == "--slim") {
      o.slim = parse_double(value);
      if (o.slim < 0.0 || o.slim > 1.0) throw std::runtime_error("--slim outside [0,1]");
      o.has_slim = true;
    } else throw std::runtime_error("unknown option");
  }
  if (o.model.empty() || o.input.empty() || o.output.empty() || o.sample_rate == 0)
    throw std::runtime_error("required: --model --input-f64le --output-f64le --sample-rate");
  if (fs::absolute(o.input) == fs::absolute(o.output))
    throw std::runtime_error("input and output must be different files");
  return o;
}

int run(const Options& opts) {
  static_assert(sizeof(double) == 8 && std::numeric_limits<double>::is_iec559,
                "raw f64 requires IEEE-754 double");
  if constexpr (std::endian::native != std::endian::little)
    throw std::runtime_error("raw f64le input requires little-endian host");
  const auto file_size = fs::file_size(opts.input);
  if (!file_size || file_size > kMaxInputBytes || file_size % sizeof(double))
    throw std::runtime_error("input must be nonempty, <=128MiB and f64-aligned");
  const auto frames = file_size / sizeof(double);
  if (fs::exists(opts.output)) throw std::runtime_error("output already exists");
  auto model = nam::get_dsp(opts.model); // TRUE upstream loader, not hand-parsed JSON.
  if (!model) throw std::runtime_error("NAM Core returned no model");
  if (model->NumInputChannels() != 1 || model->NumOutputChannels() != 1)
    throw std::runtime_error("Stage98 supports mono input and mono output only");
  const double expected = model->GetExpectedSampleRate();
  if (expected > 0.0 && std::abs(expected - opts.sample_rate) > 0.5)
    throw std::runtime_error("source rate differs from NAM expected rate; resample explicitly first");
  if (opts.has_slim) {
    auto* slimmable = dynamic_cast<nam::SlimmableModel*>(model.get());
    if (!slimmable) throw std::runtime_error("--slim requires a SlimmableModel");
    slimmable->SetSlimmableSize(opts.slim);
  }
  model->SetPrewarmOnReset(opts.prewarm);
  model->Reset(static_cast<double>(opts.sample_rate), opts.block);

  std::ifstream input(opts.input, std::ios::binary);
  if (!input) throw std::runtime_error("cannot open raw input");
  const fs::path staging = opts.output.string() + ".stage98_partial";
  if (fs::exists(staging)) throw std::runtime_error("staging output already exists");
  try {
    std::ofstream output(staging, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot create staging output");
    std::vector<double> raw(static_cast<std::size_t>(opts.block));
    std::vector<NAM_SAMPLE> inbuf(static_cast<std::size_t>(opts.block));
    std::vector<NAM_SAMPLE> outbuf(static_cast<std::size_t>(opts.block));
    NAM_SAMPLE* in_ptrs[] = {inbuf.data()};
    NAM_SAMPLE* out_ptrs[] = {outbuf.data()};
    std::uintmax_t done = 0;
    while (done < frames) {
      const int n = static_cast<int>(std::min<std::uintmax_t>(opts.block, frames - done));
      input.read(reinterpret_cast<char*>(raw.data()), std::streamsize(n * sizeof(double)));
      if (!input) throw std::runtime_error("truncated raw input");
      for (int j = 0; j < n; ++j) {
        if (!std::isfinite(raw[j])) throw std::runtime_error("non-finite input sample");
        inbuf[j] = static_cast<NAM_SAMPLE>(raw[j]);
      }
      model->process(in_ptrs, out_ptrs, n); // upstream NAM inference.
      for (int j = 0; j < n; ++j) {
        raw[j] = static_cast<double>(outbuf[j]);
        if (!std::isfinite(raw[j])) throw std::runtime_error("non-finite NAM output");
      }
      output.write(reinterpret_cast<const char*>(raw.data()), std::streamsize(n * sizeof(double)));
      if (!output) throw std::runtime_error("failed to write raw output");
      done += n;
    }
    output.close();
    if (!output) throw std::runtime_error("failed to close raw output");
    fs::rename(staging, opts.output);
  } catch (...) {
    std::error_code ignored;
    fs::remove(staging, ignored);
    throw;
  }
  std::cout << "{\"status\":\"NAM_CORE_UPSTREAM_INFERENCE_COMPLETED\""
            << ",\"frames\":" << frames
            << ",\"sample_rate\":" << opts.sample_rate
            << ",\"expected_sample_rate\":" << expected
            << ",\"block\":" << opts.block
            << ",\"prewarm\":" << (opts.prewarm ? "true" : "false")
            << ",\"slim_applied\":" << (opts.has_slim ? "true" : "false")
            << "}\n";
  return 0;
}
} // namespace

int main(int argc, char** argv) {
  try { return run(arguments(argc, argv)); }
  catch (const std::exception& e) {
    std::cerr << "[Stage98 NAM] " << e.what() << '\n';
    return 2;
  }
}
