# Native SONICLINK .prst support — PRST Lab integration

This fork vendors the JavaScript native-preset converter from [PRST Lab](https://github.com/TheColdVoid1337/PRST-Lab), source snapshot 2026-10-09. It converts the existing PocketMasterStudio v1.0 JSON preset format (single preset or `PocketMasterBatch`) into **genuine 515-byte .prst files**, with CRC-8/SMBUS and preservation of unknown donor bytes. All code lives in `tools/`, the device mappings in `catalog/`, and regression tests in `tests/`. The fork provides both a Node.js CLI **and a browser export panel** in the self-contained `PocketMasterStudio.html` under **Studio → Overview → Native SONICLINK .prst export**. It supports one preset (.prst) or all presets for an artist (ZIP) in Modeled, Clone/NAM, and Mixed sets.

## Browser workflow

1. Open `PocketMasterStudio.html` in Chrome/Edge and go to **Studio → Overview**.
2. In **Native SONICLINK .prst export**, choose Modeled, Clone/NAM or Mixed; select an artist and one preset or All (ZIP).
3. By default, **do not upload any donor**. Studio uses the bundled genuine SONICLINK stock reference. If this export contains Clone/NAM presets, Studio turns on the Clone-mode bit using the paired-export mapping from PRST Lab (experimental until tested with your pedal). Optionally load a donor from the same firmware/device in the **Custom donor .prst** field. Confirm the physical NAM slot map matches your installed captures.
4. Click **Export .prst / ZIP**. All conversions and CRC checks occur locally; a failed conversion blocks the download (no partial ZIP).
5. Import via SONICLINK and check readback and sound. Binary software validation alone is not hardware acceptance.

The browser bundle embeds the exact 515-byte reference from `templates/pocket_master_reference.prst` as Base64. The user does not need to upload a donor. The bundle uses the **same PRST Lab JavaScript converter and catalogs** as the CLI. The module is included by `src/build_studio.js` and its UI lives in `src/prst_studio_ui.js`. To rebuild after changing the source, run `node src/build_studio.js` (this also updates Studio's generated documentation/changelog, as in upstream).

## Run from the repository root

Node.js 18+; no npm install needed:

```bash
node --test tests/test_sonicmaster_to_prst.cjs
node tests/test_prst_clone_slots.cjs

# A modeled preset: no donor needed
node tools/sonicmaster_to_prst.js json/AC-DC.json \\
  --select 'BackBlck R' -o BackBlck_R.prst

# Clone batch: automatically use bundled reference + inferred Clone-ON state
node tools/sonicmaster_to_prst.js json_nam/AC-DC.json \\
  --nam-slots config/nam_slots.owner.example.json \\
  --out-dir generated/AC-DC

# Optional: supply a genuine Clone-ON reference from your own pedal
# Add --donor my_clone_on_export.prst to either command.
```

`--nam-slots` is a **device-specific** map of capture label to physical User Profile slot (1–5). Verify the installed order before use; the example map belongs to one tested pedal. A .prst selects a slot, **not a .nam file**. If a required capture is not installed in the mapped slot, results will be wrong. The converter rejects missing/duplicate slots and never silently guesses. It refuses to overwrite files.

## Safety and verification

- **Donorless is the default.** The included template is a genuine SONICLINK export, but it may differ from your pedal/firmware. For Clone/NAM, the program builds a Clone-ON candidate by changing the verified mode bit in that stock reference. The paired-export evidence covers the mode/slot selector, not every opaque donor field. For stronger compatibility, optionally supply your own **real Clone-ON donor**. Inferred output is not proven hardware-compatible; test import, readback and sound before accepting it.
- FX1/FX2 four-byte selectors remain partly inferred; user IR native selectors are unsupported and rejected. A successful parser/CRC check is only an offline check.
- The owner reports that Pocket Master **bypasses its onboard IR in Clone mode**, even when the UI allows toggling its enable flag. This importer preserves JSON IR values but **does not claim the IR actually processes Clone audio**. Amp-only NAM files need external cabinet processing; prefer full-rig NAMs when using the pedal directly.
- This integration adds an exporter without changing the existing JSON tone-generator semantics or either original project. `PocketMasterStudio.html` in this fork includes the browser module. Code is published here at the PRST Lab owner's explicit request.

## Source provenance

Copied verbatim from `TheColdVoid1337/PRST-Lab`: `tools/sonicmaster_to_prst.js`, `tools/native_prst_patch.js`, `tools/prst_clone_slots.js`, `catalog/effects.json`, `catalog/fx_native.json`, `config/nam_slots.owner.example.json`, binary reference template and the two JavaScript tests. Keep upstream changes traceable. PocketMasterStudio original: https://github.com/sadurni/PocketMasterStudio.
