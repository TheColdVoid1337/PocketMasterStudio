# PocketMasterStudio developer guide

PocketMasterStudio is a **standalone browser application**. Its editable sources are in `data/`, `src/` and `catalog/`; the checked-in `PocketMasterStudio.html` and `json*/` trees are generated outputs.

## Documentation map

- [Main README](../../README.md) — setup, library, NAM/Clone, backups, editor and native PRST.
- [Source and build](../../src/README.md) — main HTML and loose-file build pipeline.
- [Void's MOD](../VOID_MOD.md) — current configuration, Full Rig rules, offline conversion, upload and diagnostics.
- [Native PRST](../NATIVE_PRST.md) — native preset import/export.
- [Third-party license](../third_party/SONICMASTER_LICENSE.txt) — attribution to SonicMaster.
- [CI workflow](../../.github/workflows/nam-js-build.yml) — Dart-to-JS worker build, pinned reference DI and parity checks.

## Verify and rebuild

```bash
node --test tests/*.cjs
python3 -m unittest discover -s tests -p 'test_studio_server.py' -v
node tools/nam_js/verify_golden.cjs
node src/build_studio.js
```

`src/README_STUDIO.md` is the **canonical main README source**, which should remain identical to the repository's `README.md`; the HTML builder embeds that source. The standalone HTML carries the prebuilt DSP worker and compressed DI, so there is no runtime dependency on a cloud service, vendor library, Dart, Rust or the local Python server.

For release rebuilds that actually modify the DSP, follow the CI workflow to refresh `src/assets/nam_dsp_worker.js` and the pinned reference asset before rebuilding `PocketMasterStudio.html`. `node src/export_tree.js` regenerates the optional preset JSON exports.

A passed numerical fixture or SysEx protocol test is **not physical device acceptance**. Actual upload requires deliberate slot selection, overwrite permission, readback, and sensible listening checks.
