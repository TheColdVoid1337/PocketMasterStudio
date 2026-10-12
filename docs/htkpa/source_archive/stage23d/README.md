# Stage 23D research-only checkpoint

Validated source-first: the ordinary exported NAM→CLO job selects native `Fs` from the **NAM model's** `sample_rate`, not directly from saved WAV headers; both user Marshall NAMs have 48,000 Hz. Input DI 44.1k is converted towards 48k, target WAV is 48k. Read `RESEARCH_REPORT.md` for address-level evidence, limits and the strict unfulfilled gate.

Verify SHA-pinned DLL (static only) and capture WAV metadata:

```sh
python stage23d_source_provenance.py --dll /path/to/5868USB.dll --2203-capture /path/to/2203 --sc20-capture /path/to/SC20 --out evidence.json
python -m unittest -v test_stage23d.py
```

When original NAM files are available, also pass `--2203-nam /path/to/2203.nam --sc20-nam /path/to/SC20.nam` to SHA-verify the *actual* JSON sample rates. For optional non-native negative-control comparison, run from a clone that has sibling `research/htkpa/stages/stage21/` installed:

```sh
python research/htkpa/stages/stage23d/stage23d_rate_diagnostic.py --2203 /path/to/2203_capture --sc20 /path/to/SC20_capture --out /tmp/stage23d_non_native.json
```

Dependencies for verifier: Python 3, binutils/objdump. Diagnostic: NumPy, SciPy and soundfile. **Do not load or execute the vendor DLL.** Neither the report nor ZIP contains proprietary source binaries, NAM/WAV/CLO, or a completed vendor converter.

## Conditional PCM decoder addendum

`stage23d_pcm_decoder_branch.py` checks ten pinned native instructions including
`0x1801417F0` f32 normalization using `2^-31`, and tests the implied PCM16
left-justified-int32 conversion on the first channel of both original
Marshall capture pairs. This is algebraic equivalence to normalized PCM16,
**not proof that the branch was executed in the original Manager**.

```sh
python stage23d_pcm_decoder_branch.py --dll /path/to/5868USB.dll \
  --2203-capture /path/to/2203_capture --sc20-capture /path/to/SC20_capture
```

Canonical project documentation remains in `docs/` in the GitHub repository.
