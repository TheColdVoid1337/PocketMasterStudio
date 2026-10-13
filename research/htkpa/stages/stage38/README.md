# Stage38 — native Sonicake FFT vs open-source r8brain FFT

**Gate state:** native-vs-NumPy Ooura-convention mathematical check PASSED on two complete frames. A **real compiled r8brain 7.6 FFT code check is prepared but has not been run on the user's WSL**. This is strictly a Fourier-stage test, not final NAM→CLO parity.

## Verified native numbers (no new Manager runs)

From private `stage23w_native(1).zip`, group `20261013_output_route/`: inspect native 2048-point forward input and first 2048 output doubles; native 4096-point inverse input/output. Native arrays are complete and captured at separate FIR pipeline locations.

| Frame | NumPy 2048 FFT max abs | NumPy 4096 inverse max abs |
| --- | ---: | ---: |
| 0 | 8.326672684688674e-17 | 8.673617379884035e-19 |
| 1 | 1.1102230246251565e-16 | 1.1926223897340549e-18 |

Packed real FFT uses `[DC, Nyquist, real(k1), imag(k1), ...]`. Ooura's sign convention differs from `numpy.fft.rfft`; conjugate the spectrum before inverse and multiply the NumPy `irfft` result by **4096/2 = 2048** to reproduce the raw unnormalized native transform. The first 1972 doubles of native inverse frame 0 **exactly** equal the successful Stage35 binary `memcpy` event (bitwise).

The native geometry matches the public C++ formula in `CDSPBlockConvolver.h`: 2x upsampling, filter length 1417, `PrevInputLen = (1417-1+2-1)/2 = 708`, `InputLen = 4096 - 708*2 = 2680`, native copied block = `2680-708 = 1972`.

## Compile the actual public source in WSL

Use the already-pinned Stage30 r8brain checkout at `research/_LOCAL_FILES/r8brain_src/`, commit `cb2abb9977efe2471979b380ed95daa56ab4fdb9`. The Stage38 audit checks the exact upstream HEAD, compiles local `r8b_fft_gate.cpp` with the **real upstream `CDSPRealFFTKeeper`**, then checks two source FFT blocks against the saved native buffers. It writes all private sample arrays exclusively into a temporary local directory and deletes that directory after testing.

Obtain your local private Stage23W archive or use the compact **private** Stage38 fixture ZIP supplied in the conversation, and place it inside the ignored `research/_LOCAL_FILES/` directory. For example:

```bash
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main
python research/htkpa/stages/stage38/audit.py \
  --native-zip research/_LOCAL_FILES/stage38_private_fft_fixtures.zip \
  --upstream research/_LOCAL_FILES/r8brain_src \
  --out research/_LOCAL_FILES/stage38_numeric_report.json
```

Optionally add `--stage35-archive research/_LOCAL_FILES/frida_captures/frida_20261013_144322_324693.tar.gz` to independently check exact native inverse→copy byte identity. The private fixture contains only 8 original 32768-byte FFT arrays; **never commit** them or the report's input audio.

## Remaining gates

- Actual native vs compiled public-source FFT values for **all 2048 + 4096 doubles × 2 frames**, including bit equality and maximum error, have not yet been observed; do not claim r8brain compiled parity until the WSL test is run.
- End-to-end `CDSPBlockConvolver` output comparison, full fractional interpolator and 44.1→48 kHz output parity are also pending.
- Upstream revision v7.6 is a **reproducible control**, not an identified original Sonicake build. Do not equate exact mathematical FFT agreement with exact vendor source version.

Upstream source: https://github.com/avaneev/r8brain-free-src (MIT © Aleksey Vaneev, Voxengo). No proprietary source redistributed.
