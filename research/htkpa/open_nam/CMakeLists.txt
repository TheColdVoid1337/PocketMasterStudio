cmake_minimum_required(VERSION 3.16)
project(HTKPAOpenNAMProbe LANGUAGES CXX)

# Standalone offline research build. Not included in production HTML.
set(NAMCORE_SOURCE "" CACHE PATH "Absolute path to pinned NeuralAmpModelerCore checkout")
if(NOT NAMCORE_SOURCE OR NOT EXISTS "${NAMCORE_SOURCE}/NAM/get_dsp.h")
  message(FATAL_ERROR "Set -DNAMCORE_SOURCE to a complete, pinned NeuralAmpModelerCore checkout")
endif()
foreach(required
        "Dependencies/eigen/Eigen/Dense"
        "Dependencies/nlohmann/json.hpp"
        "NAM/dsp.cpp"
        "NAM/get_dsp.cpp"
        "NAM/container.cpp"
        "LICENSE")
  if(NOT EXISTS "${NAMCORE_SOURCE}/${required}")
    message(FATAL_ERROR "Missing upstream file: ${required}")
  endif()
endforeach()
file(GLOB NAM_SOURCES CONFIGURE_DEPENDS
    "${NAMCORE_SOURCE}/NAM/*.cpp"
    "${NAMCORE_SOURCE}/NAM/*/*.cpp")
if(NOT NAM_SOURCES)
  message(FATAL_ERROR "No NeuralAmpModelerCore C++ sources found")
endif()
add_executable(htkpa_nam_probe htkpa_nam_probe.cpp ${NAM_SOURCES})
target_compile_features(htkpa_nam_probe PRIVATE cxx_std_20)
target_include_directories(htkpa_nam_probe PRIVATE
    "${NAMCORE_SOURCE}"
    "${NAMCORE_SOURCE}/Dependencies/eigen"
    "${NAMCORE_SOURCE}/Dependencies/nlohmann")
# Baseline uses upstream generic path; no -ffast-math / silent changes.
# The project is built with NAM_SAMPLE=double (upstream default).
target_compile_definitions(htkpa_nam_probe PRIVATE EIGEN_MPL2_ONLY)
if(MSVC)
  target_compile_definitions(htkpa_nam_probe PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
endif()
