# Stage42 — locate where r8brain's filter spectra diverge

**Prepared, not user-run yet.** This stage follows the successful user-executed Stage41, which compared two genuine Sonicake FIR spectra against five *real compiled* r8brain public source commits.

## Stage41 result (observed, not assumed)

Every pinned source revision **v6.5 (2023-12-07), v7.0, v7.1 and v7.2 (2026-07-27)** generated **identical-to-each-other** 1417/1543-tap FIR spectrum binaries under the same Linux toolchain, validated by identical SHA-256s. Relative to Sonicake:

| Public revisions | Joint RMS error | Bit-identical original doubles |
| --- | ---: | ---: |
| v6.5 / v7.0 / v7.1 / v7.2 | `1.3529207911675724e-19` | `2511/8192` |
| v7.6 | `5.30608307059938e-15` | `8/8192` |

The pre-v7.6 versions are approx **39,220 times** closer in RMS to the native spectra than public v7.6 in this compilation. They are **not bit-identical to Sonicake**. The identical spectra do **not** uniquely identify the version embedded by Sonicake: a 2024 initial integration could have v6.5, while a 2026 rebuild could carry v7.2.

Public GitHub's diff between [v7.5](https://github.com/avaneev/r8brain-free-src/commit/9e73d2dd59fd5b95108fdb4f590083e35758b45f) and [v7.6](https://github.com/avaneev/r8brain-free-src/commit/cb2abb9977efe2471979b380ed95daa56ab4fdb9) changed only `README.md` and `r8bbase.h`. The new base code implements `exp(x)`/`log(x)` approximations and an altered Bessel routine. These changes offer a plausible, code-confirmed explanation for the FIR difference, but numerical causality and original build provenance still require testing.

## New three-release boundary experiment

Test these five pinned public revisions, using the **same compiled FIR probe and private native FFT data from Stage41**:

| Version | Release date | Pin | ABI for filter generation |
|---|---|---|---|
| v7.2 | 2026-07-27 | `8fff6f3db26f14a8f5e8fb871000613673db5753` | 5 args |
| v7.3 | 2026-08-04 | `901cfd827dc6881b45232676670efb54dee9378f` | 5 args |
| v7.4 | 2026-08-17 | `26f847bf05853fa9e69a90c088c51a2ee46f3c97` | 5 args |
| v7.5 | 2026-09-02 | `9e73d2dd59fd5b95108fdb4f590083e35758b45f` | 6 args |
| v7.6 | 2026-09-30 | `cb2abb9977efe2471979b380ed95daa56ab4fdb9` | 6 args |

Public FIR's `getKernelBlock()` layout is already zero-phase on all these revisions. The Stage41 common decoder converts the original native raw FFT to zero-phase before the comparison, which avoids the original invalid Stage40 result.

The tool reuses Stage41's test code instead of forking implementation details, prints the five per-version summaries, and identifies the **first public version with different SHA-256** relative to v7.2. It does not claim historical Sonicake attribution.

## Run in WSL without Sonicake or Frida

```bash
set -e
cd /mnt/f/PocketMasterStudio/PocketMasterStudio_Void_mod
source .venv/bin/activate
git pull --ff-only origin main

python research/htkpa/stages/stage42/audit_transition.py \
  --native-zip "research/_LOCAL_FILES/stage23w_native(1).zip" \
  --source-cache research/_LOCAL_FILES/stage41_r8brain_git \
  --out research/_LOCAL_FILES/stage42_transition_report.json
```

The script reuses the existing ignored local bare Git source cache and fetches **only missing public commits**, then builds them into temporary directories. Outputs are hash/error metadata; no original DLL, proprietary NAM/audio or native spectra enter Git.

**Interpretation:** If v7.3–v7.5 spectra match v7.2 and v7.6 alone diverges, we can localize the latest-public implementation change to v7.6's math-base update. This is *still not* proof that Sonicake took source exactly from v6.5, v7.2 or v7.5. To discriminate among *numerically identical public implementations*, inspect vendor binary fingerprints/build dates and underlying compiled functions separately.
