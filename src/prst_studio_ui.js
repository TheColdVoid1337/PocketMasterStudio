// Native PRST export widget for the dedicated .prst Lab submenu (PRST Lab codec).
// Deliberately uses the built-in JSON presets; never modifies or uploads to the pedal.
(function () {
  "use strict";
  function mount(host) {
    if (!host) throw Error(".prst Lab export container is missing");
    if (host.querySelector("#native-prst-export")) return;
    const section = document.createElement("section");
    section.id = "native-prst-export";
    section.innerHTML = [
      '<h2 style="font-size:17px;margin:6px 0">Export native .prst / ZIP</h2>',
      '<p class="mut">Export 515-byte binary presets. Void MOD: Clone IR is always OFF; only approved Full Rig (amp+cab) NAM is allowed. Other tones remain Modeled.</p>',
      '<label for="prst-mode">Preset set</label>',
      '<select id="prst-mode"><option value="modeled">Modeled</option><option value="clone">Clone/NAM</option><option value="mixed">Mixed</option></select>',
      '<label for="prst-artist">Artist / pack</label><select id="prst-artist"></select>',
      '<label for="prst-preset">Preset(s)</label><select id="prst-preset"></select>',
      '<label for="prst-donor">Custom donor .prst (optional)</label>',
      '<input type="file" accept=".prst" id="prst-donor">',
      '<p class="mut">Leave empty to use two bundled genuine SONICLINK references: a normal AMP preset and a separate real Clone-ON export. Mixed batches pick the appropriate reference for each preset. Custom donor is optional, ideally exported by your firmware.</p>',
      '<p class="mut">Five NAM slots are configured under <b>NAM/Clone</b> in the main menu. There is no separate slot-map textbox here. Clone always bypasses onboard IR, and preset files never install the .nam capture.</p>',
      '<div class="row"><button type="button" class="primary" id="prst-export">⬇️ Export native .prst / ZIP</button></div>',
      '<div id="prst-status" class="mut" role="status" aria-live="polite"></div>'
    ].join("");
    host.appendChild(section);
    const $ = (id) => section.querySelector("#" + id);
    const mode = $("prst-mode"), artist = $("prst-artist"), preset = $("prst-preset");
    const status = $("prst-status");
    const asset = window.PMPRSTAssets;
    // Physical slot mapping is owned by NAM/Clone settings (config/nam_clone.json).
    const state = () => window.PMStudio && window.PMStudio.S;
    const mapNow = () => {
      const s = state(); if (!s || !s.built) return null;
      return mode.value === "clone" ? s.built.namMap : mode.value === "mixed" ? s.built.mixedMap : s.built.jsonMap;
    };
    function options(select, items) {
      select.replaceChildren();
      for (const [value, label] of items) {
        const opt = document.createElement("option");
        opt.value = value; opt.textContent = label; select.appendChild(opt);
      }
    }
    function refreshArtist() {
      const map = mapNow(); if (!map) return;
      const previous = artist.value;
      const names = Object.entries(map).filter(([name, doc]) =>
        !name.includes("/") && name.endsWith(".json") && doc &&
        doc.type === "PocketMasterBatch" && typeof doc.artist === "string" &&
        Array.isArray(doc.presets)).sort((a,b) => a[1].artist.localeCompare(b[1].artist));
      options(artist, names.map(([name, doc]) => [name, doc.artist + " (" + doc.presets.length + ")"]));
      if (names.some(([name]) => name === previous)) artist.value = previous;
      refreshPreset();
    }
    function refreshPreset() {
      const map = mapNow(), batch = map && map[artist.value];
      if (!batch) { options(preset, []); return; }
      const previous = preset.value;
      options(preset, [["all","All " + batch.presets.length + " presets (ZIP)"],
        ...batch.presets.map((p,i) => [String(i), String(i+1).padStart(2,"0") + " · " + p.presetName + " (" + p.ampMode + ")"])]);
      if ([...preset.options].some((o) => o.value === previous)) preset.value = previous;
    }
    const safeName = (s) => String(s).replace(/[^a-zA-Z0-9_-]+/g, "_").slice(0,60);
    function download(filename, blob) {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = filename;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
    }
    async function exportNative() {
      const button = $("prst-export");
      button.disabled = true;
      status.textContent = "Validating source and PRST template…";
      try {
        const map = mapNow(); if (!map) throw Error("Studio data is not ready.");
        const batch = map[artist.value]; if (!batch) throw Error("Choose an artist.");
        const chosen = preset.value === "all" ? batch.presets : [batch.presets[Number(preset.value)]];
        if (!chosen.length || chosen.some((p) => !p)) throw Error("No presets selected.");
        const donorFile = $("prst-donor").files[0];
        const automatic = !donorFile;
        if (automatic && (typeof asset.templateBase64 !== "string" || typeof asset.cloneTemplateBase64 !== "string"))
          throw Error("Bundled Modeled/Clone SONICLINK PRST references are missing from this Studio build.");
        const decode = (b64) => Uint8Array.from(atob(b64), (ch) => ch.charCodeAt(0));
        const references = automatic ? {
          stock: decode(asset.templateBase64),
          clone: decode(asset.cloneTemplateBase64)
        } : {custom: new Uint8Array(await donorFile.arrayBuffer())};
        if (automatic) {
          if (window.PRSTCloneSlots.inspect(references.stock).cloneEnabled)
            throw Error("Bundled Modeled reference has Clone ON.");
          if (!window.PRSTCloneSlots.inspect(references.clone).cloneEnabled)
            throw Error("Bundled Clone reference has Clone OFF.");
        } else window.PRSTCloneSlots.inspect(references.custom);
        const hasClone = chosen.some((p) => p.ampMode === "Clone");
        const hasGeneratedClone = chosen.some((p) => p.ampMode === "Clone" && !p.nativeImport);
        const cfg = state()?.payload?.void_nam || window.PMVoidPolicy.defaults();
        const validated = window.PMVoidPolicy.normalize(cfg,window.PMVoidPolicy.validAmpNames(asset.catalog));
        const namSlots = window.PMVoidPolicy.slotMap(validated);
        if(hasGeneratedClone && !Object.keys(namSlots).length)throw Error("Configure Full Rig NAM slots in NAM/Clone first.");
        if(hasGeneratedClone)window.PRSTConvert.checkMap(namSlots);
        // Convert and verify ALL results before offering any download.
        const result = chosen.map((p) => {
          // Native library snapshots are archival: preserve the exact imported
          // 515 bytes, even when the corresponding NAM slot is no longer mapped.
          if (p.nativeImport?.rawBase64) {
            const bytes = window.PMPRSTImport.fromBase64(p.nativeImport.rawBase64);
            window.PRSTCloneSlots.inspect(bytes);
            return {bytes,warnings:["Original PRST bytes preserved"]};
          }
          return window.PRSTConvert.convert(p, window.PRSTConvert.selectDonor(p, references), {
            catalog: asset.catalog, fxNative: asset.fxNative, namSlots, voidConfig: validated
          });
        });
        for (const r of result) {
          const parsed = window.PRSTCloneSlots.inspect(r.bytes);
          if (!parsed) throw Error("Invalid output");
        }
        if (result.length === 1) {
          download(safeName(chosen[0].presetName) + ".prst", new Blob([result[0].bytes], {type:"application/octet-stream"}));
        } else {
          const entries = result.map((r,i) => ({
            name: String(i+1).padStart(3,"0") + "_" + safeName(chosen[i].presetName) + ".prst",
            data: r.bytes
          }));
          download(safeName(batch.artist || "presets") + "_" + mode.value + "_native.zip", await window.PMZip.create(entries));
        }
        status.textContent = "Created " + result.length + " native 515-byte PRST candidate(s), CRC checked. SONICLINK import/readback/listening still required." +
          (automatic ? " Used authentic built-in Modeled/Clone references as appropriate." : " Used your custom donor.") +
          (hasClone ? " Generated Clone uses Full Rig and IR OFF; imported PRST snapshots are exported byte-for-byte and are not automatically Full Rig verified." : "");
      } catch (e) {
        status.textContent = "Export blocked: " + (e && e.message || String(e));
      } finally { button.disabled = false; }
    }
    mode.addEventListener("change", refreshArtist);
    artist.addEventListener("change", refreshPreset);
    $("prst-export").addEventListener("click", exportNative);
    const stats = document.getElementById("stats");
    if (stats) new MutationObserver(() => refreshArtist()).observe(stats, {childList:true,subtree:true});
    refreshArtist();
  }
  // Mounted only when the user visits the dedicated .prst Lab main-menu view.
  window.PMPRSTExportUI = Object.freeze({ mount });
})();