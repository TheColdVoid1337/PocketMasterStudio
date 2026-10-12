# Stage23D source restoration and revalidation

2026-10-12. Original ZIP SHA256 `69ee4bf61fc3ec9f18a0981d44caaaaac31842a2d3d719de39d9698d1245fa19` passed CRC inspection. Its 14 text members were restored without byte edits: 12 code/evidence files under `research/htkpa/stages/stage23d/`, two Markdown originals under `docs/htkpa/source_archive/stage23d/`. The placeholder status now points to the restored sources. `research/htkpa/stage23d_archive_manifest.json` records each original member and SHA256; the historical 144-file manifest is unchanged.

Preflight: clean `main` at `ad0e666cb9daf3ae8d436c64aa59d1065edcbf69`; `git pull --ff-only origin main` reported already up to date. Original archive integrity 144/144; private manifest 16/16 hashes and sizes passed. Private files are ignored and none are tracked. Both input WAVs are stereo PCM16, 3,087,000 frames at 44,100 Hz; both references are stereo PCM16, 3,360,000 frames at 48,000 Hz. The protected baseline hash also passed.

## Reproduce without modifying the historical scripts

The historical scripts expect `nam_input_wav.wav` and `outputFile.wav`; the private pack uses `input_DI.wav` and `output_reference.wav`. A separate runner creates temporary copies under the historical names and removes only those owned temporary copies on exit. It does not edit the original scripts, input files or historical JSON evidence.

From repository root in WSL/Linux, with Python, objdump, NumPy, SciPy and SoundFile:

```sh
python research/htkpa/source_integrity.py
python research/htkpa/source_integrity.py --manifest research/htkpa/stage23d_archive_manifest.json
python research/htkpa/verify_audio_checkpoints.py --private-root research/_LOCAL_FILES --out research/_LOCAL_FILES/scratch/checkpoints
```

Verified using `.venv/bin/python` in WSL. The existing environment initially lacked numerical dependencies; installed NumPy 2.5.4, SciPy 1.18.1 and SoundFile 0.14.0 into the ignored `.venv`. All commands above exited 0:

| Check | Result |
| --- | --- |
| Stage21 | 75 instructions, 8 constants, 77 synthetic assertions |
| Stage21 symbolic pointer trace | 7 block-count cases |
| Stage22 | 43 instructions, 7 constants, 53 assertions |
| Stage23C | 79 instructions, 14 vtable entries, 673.0 constant, 10 synthetic assertions |
| Stage23D | 42 instructions, 5 PE strings, 48000.0 constant, both actual NAM hashes/metadata |
| Stage23D repeat | byte-identical new evidence including NAM metadata |
| Stage23D unit suite | 5/5 |
| Stage23D decoder addendum | 10 instructions, 2^-31 constant; all four first-channel PCM arrays agree exactly with PCM16 / 32768 |

The archived addendum script compares two arithmetic expressions; it does **not** call SoundFile. The earlier report's SoundFile comparison is historical evidence, not a claim about this script's fresh run. A separate Stage23E experiment should independently compare with SoundFile and verify branch reachability.

The new evidence includes actual NAM metadata, so its hash is not expected to equal the historical WAV-only evidence. No generic resampling diagnostic was promoted to native parity. Both models' native four gains and FIR parity remain **NOT_COMPUTED**.
