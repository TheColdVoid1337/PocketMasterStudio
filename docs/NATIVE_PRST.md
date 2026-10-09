# Native SONICLINK .prst support — PRST Lab integration

This fork vendors the JavaScript native-preset converter from [PRST Lab](https://github.com/TheColdVoid1337/PRST-Lab), source snapshot 2026-10-09. It converts the existing PocketMasterStudio v1.0 JSON preset format (single preset or `PocketMasterBatch`) into **genuine 515-byte .prst files**, with CRC-8/SMBUS and preservation of unknown donor bytes. All code lives in `tools/`, the device mappings in `catalog/`, and regression tests in `tests/`. The fork provides both a Node.js CLI **and a browser export panel** in the self-contained `PocketMasterStudio.html` under **Studio → Overview → Native SONICLINK .prst export**. It supports one preset (.prst) or all presets for an artist (ZIP) in Modeled, Clone/NAM, and Mixed sets.

## Browser workflow

1. Open `PocketMasterStudio.html` in Chrome/Edge and go to **Studio → Overview**.
2. In **Native SONICLINK .prst export**, choose Modeled, Clone/NAM or Mixed; select an artist and one preset or All (ZIP).
3. By default, **do not upload any donor**. Studio includes two genuine SONICLINK reference files: a Modeled export (`templates/pocket_master_reference.prst`) and a **genuine Clone-ON export** (`templates/pocket_master_clone_reference.prst`, original `P17-VindSorg L.prst`, 515 bytes). For Mixed bundles it selects the correct donor **per preset**. Optionally use the **Custom donor .prst** field for firmware-specific experiments. Confirm the physical NAM slot map matches your installed captures.
4. Click **Export .prst / ZIP**. All conversions and CRC checks occur locally; a failed conversion blocks the download (no partial ZIP).
5. Import via SONICLINK and check readback and sound. Binary software validation alone is not hardware acceptance.

The browser bundle embeds both authentic 515-byte reference files as Base64; it chooses the appropriate reference for each preset. The user does not need to upload a donor. The bundle uses the **same PRST Lab JavaScript converter and catalogs** as the CLI. The module is included by `src/build_studio.js` and its UI lives in `src/prst_studio_ui.js`. To rebuild after changing the source, run `node src/build_studio.js` (this also updates Studio's generated documentation/changelog, as in upstream).

## Run from the repository root

Node.js 18+; no npm install needed:

```bash
node --test tests/test_sonicmaster_to_prst.cjs
node tests/test_prst_clone_slots.cjs

# A modeled preset: no donor needed
node tools/sonicmaster_to_prst.js json/AC-DC.json \\
  --select 'BackBlck R' -o BackBlck_R.prst

# Clone batch: automatically use the genuine bundled Clone-ON reference
node tools/sonicmaster_to_prst.js json_nam/AC-DC.json \\
  --nam-slots config/nam_slots.owner.example.json \\
  --out-dir generated/AC-DC

# Optional: supply a genuine Clone-ON reference from your own pedal
# Add --donor my_clone_on_export.prst to either command.
```

`--nam-slots` is a **device-specific** map of capture label to physical User Profile slot (1–5). Verify the installed order before use; the example map belongs to one tested pedal. A .prst selects a slot, **not a .nam file**. If a required capture is not installed in the mapped slot, results will be wrong. The converter rejects missing/duplicate slots and never silently guesses. It refuses to overwrite files.

## Safety and verification

- **Donorless is the default.** The Normal reference is a genuine SONICLINK export; the Clone reference is an independent genuine Clone-ON export (`P17-VindSorg L.prst`) from the owner's device, preserving its opaque fields. Slot 1–5 selections were verified against five original SONICLINK exports: for the Clone source only offset 175 (slot) and offset 20 (CRC) differ; expected slot CRCs are `FB C0 8D B6 17`. This is stronger than synthesizing Clone-ON from a Normal file but still does **not** prove that newly generated combinations import and sound as intended. For another firmware, optionally provide a custom export. Test SONICLINK readback and listening.
- FX1/FX2 four-byte selectors remain partly inferred. **User IR 1–5 selectors are now encoded** with the real SONIC LINK mapping `[n−1, 00, 10, 0A]` at offsets `155..158`; the user IR/WAV content must already be present on the pedal. Encoding a selector does **not** establish whether onboard IR runs in Clone mode. A successful parser/CRC check is only an offline check.
- The owner reports that Pocket Master **bypasses its onboard IR in Clone mode**, even when the UI allows toggling its enable flag. This importer preserves JSON IR values but **does not claim the IR actually processes Clone audio**. Amp-only NAM files need external cabinet processing; prefer full-rig NAMs when using the pedal directly.
- This integration adds an exporter without changing the existing JSON tone-generator semantics or either original project. `PocketMasterStudio.html` in this fork includes the browser module. Code is published here at the PRST Lab owner's explicit request.

## Source provenance

Copied verbatim from `TheColdVoid1337/PRST-Lab`: `tools/sonicmaster_to_prst.js`, `tools/native_prst_patch.js`, `tools/prst_clone_slots.js`, `catalog/effects.json`, `catalog/fx_native.json`, `config/nam_slots.owner.example.json`, binary reference template and the two JavaScript tests. Keep upstream changes traceable. PocketMasterStudio original: https://github.com/sadurni/PocketMasterStudio.

## Authentic Clone reference provenance

Source: user-provided `Vindsorg.zip` (2026-10-09), file `P17-VindSorg L.prst` (User Profile 1), sha256 `bf79ef9b7a8786747a02919803b14ebc4115eb72d468bfaed6dfc58be8d3e8e4`. File is exactly 515 bytes; CRC-8/SMBUS matches; bit 9 is set in enabled mask `0x03ED`; selector bytes 175..178 are `00 00 00 0F`. The other four originals from this ZIP were analyzed and matched the byte-175/CRC-only difference, but do not need to be added to the release. `Prst_diag.zip` was separately inspected (17 Clone-ON diagnostic exports). The subsequent User IR 1–5 mapping is supported by its own authenticated SONIC LINK export evidence and the current PRST-Lab 0.0.1 codec; unsupported selectors remain blocked.

## Synced PRST-Lab 0.0.1 integration source (2026-10-10)

The canonical project is **Python-first** at [PRST-Lab](https://github.com/TheColdVoid1337/PRST-Lab).
The JS bridge originates in `PRST-Lab/integrations/pocketmasterstudio/tools/` and is
copied into this fork's `tools/` (with companion tests under `tests/`).
The importer continues to use **separate authentic Modeled and Clone-ON reference files**
for each preset in a mixed batch; the five **User IR 1–5** native selectors
are now supported from real SONIC LINK export evidence (`[n-1,00,10,0A]` at 155..158).
Optional `--donor` remains supported; `--bundled-template` is an explicit compatibility alias
and cannot be mixed with `--donor`.

Run from this fork's root:

```bash
node --test tests/*.cjs
node src/build_studio.js
```

**Important:** `PocketMasterStudio.html` is a generated bundle. Updating `tools/*.js`
without running `node src/build_studio.js` does **not** update the HTML distributed
to browsers. This fork's bundled HTML has been refreshed for the PRST-Lab 0.0.1 bridge; `tests/test_studio_prst_bundle.cjs` guards against future stale bundles. Rebuild and review the diff before deploying the new editor.
See [the current native binary specification](https://github.com/TheColdVoid1337/PRST-Lab/blob/release/0.0.1/docs/FORMAT.md).

Hardware caveats: two previously generated native candidates survived import/save/export
readback with 513/515 and 512/515 byte matches; inactive DLY Time normalized to 150
and native BPM 68 read back as 120. These observations are not universal firmware guarantees.
