# Native SONICLINK .prst support — PRST Lab integration

This fork vendors the JavaScript native-preset converter from [PRST Lab](https://github.com/TheColdVoid1337/PRST-Lab), source snapshot 2026-10-09. It converts the existing PocketMasterStudio v1.0 JSON preset format (single preset or `PocketMasterBatch`) into **genuine 515-byte .prst files**, with CRC-8/SMBUS and preservation of unknown donor bytes. All code lives in `tools/`, the device mappings in `catalog/`, and regression tests in `tests/`. This initial integration exposes a Node.js CLI; it does **not yet add a browser button** to the self-contained Studio.

## Run from the repository root

Node.js 18+; no npm install needed:

```bash
node --test tests/test_sonicmaster_to_prst.cjs
node tests/test_prst_clone_slots.cjs

# A modeled preset with the bundled stock donor:
node tools/sonicmaster_to_prst.js json/AC-DC.json \\
  --donor templates/pocket_master_reference.prst \\
  --select 'BackBlck R' -o BackBlck_R.prst

# Clone batch with a genuine Clone-ON donor exported from your Pocket Master:
node tools/sonicmaster_to_prst.js json_nam/AC-DC.json \\
  --donor my_clone_on_export.prst \\
  --nam-slots config/nam_slots.owner.example.json \\
  --out-dir generated/AC-DC
```

`--nam-slots` is a **device-specific** map of capture label to physical User Profile slot (1–5). Verify the installed order before use; the example map belongs to one tested pedal. A .prst selects a slot, **not a .nam file**. If a required capture is not installed in the mapped slot, results will be wrong. The converter rejects missing/duplicate slots and never silently guesses. It refuses to overwrite files.

## Safety and verification

- Use an authentic donor .prst from the same firmware/pedal. The bundled stock template is good for stock/model development; **prefer an actual Clone-ON donor** for Clone/NAM output. Inferred bytes do not prove compatibility. Test import, readback and sound through SONICLINK before calling the result validated.
- FX1/FX2 four-byte selectors remain partly inferred; user IR native selectors are unsupported and rejected. A successful parser/CRC check is only an offline check.
- The owner reports that Pocket Master **bypasses its onboard IR in Clone mode**, even when the UI allows toggling its enable flag. This importer preserves JSON IR values but **does not claim the IR actually processes Clone audio**. Amp-only NAM files need external cabinet processing; prefer full-rig NAMs when using the pedal directly.
- This integration does not modify the existing Studio preset generation, bundled HTML, or either original project. Code is published here at the PRST Lab owner's explicit request.

## Source provenance

Copied verbatim from `TheColdVoid1337/PRST-Lab`: `tools/sonicmaster_to_prst.js`, `tools/native_prst_patch.js`, `tools/prst_clone_slots.js`, `catalog/effects.json`, `catalog/fx_native.json`, `config/nam_slots.owner.example.json`, binary reference template and the two JavaScript tests. Keep upstream changes traceable. PocketMasterStudio original: https://github.com/sadurni/PocketMasterStudio.
