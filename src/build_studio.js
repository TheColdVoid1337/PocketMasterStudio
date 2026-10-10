// build_studio.js — assemble the self-contained PocketMaster Studio (PocketMasterStudio.html):
// embeds data/ + mld + factory + overrides + portable prompt (one gzip+base64 blob), inlines the
// verified pipeline modules + the Studio controller, runs everything in-browser, saves itself.
const fs = require("fs"), path = require("path"), zlib = require("zlib");
// Self-contained build: source data lives in ../data, build inputs in ./assets, output to ../.
const SRC = __dirname;
const HERE = __dirname;
const ASSETS = path.join(SRC, "assets");
const DATA = path.join(SRC, "..", "data");
const ROOT = path.join(SRC, "..");
const rd = (p) => fs.readFileSync(p, "utf-8");
const rdj = (p) => JSON.parse(rd(p));
const PMBuild = require("./pmbuild.js");
const PMStats = require("./pmstats.js");
const PMChangelog = require("./pmchangelog.js");

const config = rdj(path.join(DATA, "_config.json"));
const data = {};
for (const n of config.order) data[n] = rdj(path.join(DATA, n.replace(/\//g, "-") + ".json"));
const mld = rdj(path.join(ASSETS, "mld.json"));
const factory = rdj(path.join(ASSETS, "pocketmaster_batch_factory_presets_v1_3_3.json"));

// portable AI prompt: the body after the "how to use" header (split on first \n---\n).
const promptMd = rd(path.join(ASSETS, "PROMPT_Portable_Preset_Generator.md")).replace(/\r\n/g, "\n");
const cut = promptMd.indexOf("\n---\n");
const prompt = (cut >= 0 ? promptMd.slice(cut + 5) : promptMd).trim();

let readme = ""; try { readme = rd(path.join(SRC, "README_STUDIO.md")); } catch (e) {}
// This appendix is fork-only and is always appended rather than rewriting
// historical upstream README sections.
const voidModReadme = rd(path.join(ROOT, "docs", "VOID_MOD.md"));
if (!readme.includes("## Void's MOD")) readme = readme.trimEnd() + "\n\n---\n\n" + voidModReadme;

// Optional pre-applied overrides + custom collections shipped with the project, at the repo root
// next to data/ (overrides default to {}, collections to null = the built-in 5).
const readOv = (f) => { try { return rdj(path.join(ROOT, f)); } catch (e) { return {}; } };
let collections = null; try { collections = rdj(path.join(ROOT, "collections.json")); } catch (e) {}
const factory_overrides = readOv("factory_overrides.json");
const nam_overrides = readOv("nam_overrides.json");

// Run the pipeline once so the README headline reflects the REAL generated numbers.
const { summary, total, artistCount } = PMBuild.buildSongs(mld, config, data, factory_overrides);
const stats = PMStats.compute({ summary, total, artistCount }, {
  collections,
  defaultFiles: PMBuild.defaultCollectionDefs().map((d) => d.file),
  namCaptures: PMBuild.NAM_CAPTURES.length,
});
readme = PMStats.apply(readme, stats);

// Advance the change history (a full regeneration counts as a complete export): stamp created/modified
// on the data files / overrides / collections that changed, append a dated batch to changelog.json and
// rewrite CHANGELOG.md. Optional `--since=YYYY-MM-DD` controls the window shown in the README (default:
// the previous full export). Never happens on a plain HTML Save — only here and on the app's Export ZIP.
const sinceArg = ((process.argv.find((a) => a.startsWith("--since=")) || "").split("=")[1] || "").trim() || null;
const now = new Date().toISOString();
const cl = PMChangelog.advanceOnDisk({
  root: ROOT, dataDir: DATA, data, fov: factory_overrides, nov: nam_overrides, collections,
  now, since: sinceArg, stringify: PMBuild.stringify,
});
const changelogState = cl.state;
readme = PMChangelog.applyRecent(readme, cl.recent,
  sinceArg ? "changes since " + sinceArg : "since the previous full export");

// Persist the refreshed README (headline + recent changes) to both source copies.
try { fs.writeFileSync(path.join(SRC, "README_STUDIO.md"), readme, "utf-8"); } catch (e) {}
try { fs.writeFileSync(path.join(ROOT, "README.md"), readme, "utf-8"); } catch (e) {}
console.log("README headline:", stats.artists, "artists /", stats.songs, "songs /", stats.presets,
  "presets (" + stats.minPer + "-" + stats.maxPer + "/artist) /", stats.compilations, "built-in compilations");
console.log("changelog:", cl.changed ? (cl.baseline ? "baseline recorded" : "batch recorded") : "no changes since last export",
  "(" + (changelogState.batches || []).length + " batch(es) total)");

// Docs (markdown) for the Docs tabs — rendered live with pmmd (README carries headline + recent changes).
const docs = [
  { id: "readme", label: "README", md: readme },
  { id: "changelog", label: "Changelog", md: cl.changelogMd },
  { id: "songs", label: "Representative songs", md: rd(path.join(ASSETS, "representative_songs.md")) },
  { id: "prompt-artist", label: "Artist prompt", md: rd(path.join(ASSETS, "PROMPT_Generate_Artist_Presets.md")) },
  { id: "prompt-portable", label: "Portable prompt", md: rd(path.join(ASSETS, "PROMPT_Portable_Preset_Generator.md")) },
];

const payload = { config, data, mld, factory, factory_overrides, nam_overrides, collections, prompt, readme, docs, changelog: changelogState };
const raw = Buffer.from(JSON.stringify(payload), "utf-8");
const blob = zlib.gzipSync(raw, { level: 9 }).toString("base64");
console.log("payload raw", raw.length, "-> gzip+base64", blob.length);

// Editor (PocketEdit): strip its baked library (we inject a fresh one at runtime), embed as a blob.
let editorHtml = rd(path.join(ASSETS, "PocketEdit_multi_import_export.html"));
editorHtml = editorHtml.replace(/(<script id="pm-library"[^>]*>)[\s\S]*?(<\/script>)/, "$1$2");
// Remove the editor's AI Prompt button (Studio has its own AI Prompt tab).
editorHtml = editorHtml.replace(/\s*<button id="aiPromptBtn"[^>]*>[\s\S]*?<\/button>/, "");
// Repurpose "Export as Override": hand the current preset to the Studio to make it definitive
// (no Python / serve.py). Plain Export / Export Multiple keep downloading a JSON as before.
const NEW_OVERRIDE =
`      async function exportOverride(){
        const e = ed(); if(!e){ alert('Editor not ready.'); return; }
        if(!(window.parent && window.parent!==window)){ e._captureExport=null; e.exportPreset(); return; }
        const preset = await new Promise((resolve)=>{ e._captureExport = resolve; Promise.resolve(e.exportPreset()).catch(()=>resolve(null)); });
        if(!preset || !preset.modules){ alert('Could not read the current preset.'); return; }
        window.parent.postMessage({ type:'pm-override', text: JSON.stringify(preset) }, '*');
        try{ e.log('[OVERRIDE] Sent to Studio — review it in the Paste JSON tab.', 'info'); }catch(_){}
      }`;
editorHtml = editorHtml.replace(
  /\n {6}async function exportOverride\(\)\{[\s\S]*?\n {6}\/\/ ---------- wiring ----------/,
  () => "\n" + NEW_OVERRIDE + "\n\n      // ---------- wiring ----------");
// Browse Library: show the full song TITLE (not the slug) in each category, and search it too.
editorHtml = editorHtml
  .replace("libMatch(q,a.artist,s.song,p.n)", "libMatch(q,a.artist,(s.title||'')+' '+s.song,p.n)")
  .replace("songs.push({song:s.song, presets:ps});", "songs.push({song:s.song, title:s.title, presets:ps});")
  .replace("sname.textContent=s.song;", "sname.textContent=s.title||s.song;");
const editorBlob = zlib.gzipSync(Buffer.from(editorHtml, "utf-8"), { level: 9 }).toString("base64");
console.log("editor stripped/patched -> gzip+base64", editorBlob.length);

const inlineSafe = (js) => js.replace(/<\/(script)/gi, "<\\/$1");
const modules = ["void_policy.js", "void_config_io.js", "void_nam_ui.js", "void_ui.js", "void_debug.js", "pmbuild.js", "pmhtml.js", "pmtabla.js", "pmmap.js", "pmmd.js", "pmedit.js", "pmzip.js", "pmstats.js", "pmchangelog.js"]
  .map((f) => `<script>\n${inlineSafe(rd(path.join(HERE, f)))}\n</script>`).join("\n");
const appJs = inlineSafe(rd(path.join(HERE, "studio_app.js")));

const prstWrap = (file, globalName) => {
  const deps = globalName === "PMPRSTNative"
    ? 'if(id==="./prst_clone_slots.js")return window.PRSTCloneSlots;'
    : 'if(id==="./native_prst_patch.js")return window.PMPRSTNative;if(id==="./prst_clone_slots.js")return window.PRSTCloneSlots;if(id==="../src/void_policy.js")return window.PMVoidPolicy;if(id.startsWith("node:"))return {};';
  return '(function(){const module={exports:{}};function require(id){'+deps+'throw Error("Unexpected browser require: "+id);}'+rd(path.join(ROOT, "tools", file)).replace(/^#![^\n]*\n/, "")+'\nwindow.'+globalName+'=module.exports;})();';
};
const prstScripts = [
  rd(path.join(ROOT, "tools/prst_clone_slots.js")),
  prstWrap("native_prst_patch.js", "PMPRSTNative"),
  prstWrap("sonicmaster_to_prst.js", "PRSTConvert"),
  rd(path.join(HERE, "prst_import.js")), // PRST Lab codec -> shared Studio library
  "window.PMPRSTAssets = " + JSON.stringify({
    catalog: rdj(path.join(ROOT, "catalog/effects.json")),
    fxNative: rdj(path.join(ROOT, "catalog/fx_native.json")),
    templateBase64: fs.readFileSync(path.join(ROOT, "templates/pocket_master_reference.prst")).toString("base64"),
    cloneTemplateBase64: fs.readFileSync(path.join(ROOT, "templates/pocket_master_clone_reference.prst")).toString("base64")
  }) + ";",
  "window.PMVoidModReadme = " + JSON.stringify(voidModReadme) + ";"
].map((s) => "<script>\n" + inlineSafe(s) + "\n</script>").join("\n");
const prstUi = inlineSafe(rd(path.join(HERE, "prst_studio_ui.js")));


const CSS = String.raw`
 :root{--bg:#0f1115;--card:#181b21;--card2:#1b2028;--ink:#e8eaed;--mut:#9aa1ad;--line:#272c34;--acc:#6f95ff;--ok:#3ecf9a;--warn:#e6b34d;--err:#ff6f6f}
 @media(prefers-color-scheme:light){:root{--bg:#f6f7f9;--card:#fff;--card2:#f2f4f7;--ink:#1b1d22;--mut:#616773;--line:#e3e6eb}}
 *{box-sizing:border-box} html{-webkit-text-size-adjust:100%}
 body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;overflow-x:hidden;padding-bottom:76px}
 header{padding:12px 16px;border-bottom:1px solid var(--line)}
 h1{margin:0;font-size:18px} .sub{color:var(--mut);font-size:12.5px;margin-top:3px}
 .note{color:var(--mut);font-size:12px;margin-top:6px;line-height:1.4}
 .warn{background:#5a1d1d;color:#ffd9d2;border:1px solid #7a2a2a;border-radius:10px;padding:10px 12px;margin:10px 16px;font-size:13px}
 .tabs{display:flex;gap:6px;overflow-x:auto;padding:8px 12px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5;-webkit-overflow-scrolling:touch}
 .tab{flex:0 0 auto;padding:8px 13px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--mut);font-size:13.5px;cursor:pointer;white-space:nowrap;min-height:40px}
 .tab.on{background:var(--acc);color:#fff;border-color:transparent;font-weight:600}
 .wrap{padding:12px 16px;max-width:1000px;margin:0 auto}
 .panel[hidden]{display:none}
 .row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:10px 0}
 button{padding:11px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font-size:14px;cursor:pointer;min-height:44px}
 button:disabled{opacity:.45;cursor:default} button.primary{background:var(--acc);color:#fff;border-color:transparent;font-weight:600}
 button.attn{background:var(--warn);color:#201800;border-color:transparent;font-weight:700}
 button.mini{min-height:0;padding:2px 8px;font-size:12px;border-radius:6px}
 label{display:block;font-size:13px;color:var(--mut);margin:10px 0 4px}
 input,select,textarea{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font-size:14px;font-family:inherit}
 textarea{min-height:120px;font:12.5px/1.4 ui-monospace,Menlo,Consolas,monospace;resize:vertical}
 #stats{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:6px 0}
 iframe{width:100%;height:60vh;border:1px solid var(--line);border-radius:10px;background:#fff;margin-top:8px}
 .ok{background:var(--card2);border-left:3px solid var(--ok);border-radius:8px;padding:9px 11px;margin:8px 0;font-size:13.5px}
 .err{background:var(--card2);border-left:3px solid var(--err);border-radius:8px;padding:9px 11px;margin:8px 0;font-size:13.5px}
 .warn2{background:var(--card2);border-left:3px solid var(--warn);border-radius:8px;padding:9px 11px;margin:8px 0;font-size:13.5px}
 .ovbox{background:var(--card2);border:1px solid var(--line);border-radius:8px;padding:9px 11px;margin:8px 0;font-size:13px}
 details.art{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:7px 0;padding:2px 10px}
 details.art summary{cursor:pointer;padding:8px 2px;list-style:none} details.art summary::-webkit-details-marker{display:none}
 .mut{color:var(--mut);font-size:12.5px} code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}
 .savebar{position:fixed;left:0;right:0;bottom:0;background:var(--bg);border-top:1px solid var(--line);padding:10px 16px;display:flex;gap:10px;align-items:center;z-index:20}
 .savebar .sp{flex:1} #dirtyTag{background:var(--warn);color:#201800;border-radius:6px;padding:2px 8px;font-size:12px;font-weight:700}
 #toast{position:fixed;left:50%;bottom:84px;transform:translateX(-50%);background:#111;color:#fff;padding:9px 16px;border-radius:10px;font-size:13px;z-index:30}
 select[data-amb]{width:auto;display:inline-block;min-height:34px;padding:4px 8px}
 .checks{display:flex;flex-wrap:wrap;gap:8px 14px;margin:2px 0}
 .chk2{display:flex;align-items:center;gap:7px;font-size:13.5px;cursor:pointer} .chk2 input{width:18px;height:18px}
 .chk{display:flex;align-items:center;gap:7px;padding:5px 2px;cursor:pointer;font-size:13.5px}
 .chk.sub{padding-left:22px;font-size:13px} .chk input{width:18px;height:18px;flex:0 0 auto}
 .kd{background:var(--chip,#232832);color:var(--mut);border-radius:5px;padding:0 6px;font-size:11px;font-weight:700}
 .song{border-top:1px solid var(--line);padding:4px 0}
 .songhead{display:flex;align-items:center;gap:6px} .songhead .chk{flex:1}
 .docbar .mini{min-height:34px} .docbar .mini.on{background:var(--acc);color:#fff;border-color:transparent;font-weight:600}
 .mini[disabled]{opacity:.35;cursor:default}
 iframe.hasbar{height:calc(100vh - 165px)}
 @media(max-width:560px){ iframe.hasbar{height:calc(100vh - 158px)} }
 .slotrow{display:flex;align-items:center;gap:8px;padding:6px 2px;border-top:1px solid var(--line);flex-wrap:wrap}
 .slotrow .sl{min-width:26px;text-align:center;background:var(--chip,#232832);color:var(--mut);border-radius:6px;font-size:12px;font-weight:700;padding:2px 0}
 .slotrow .lbl{flex:1;min-width:140px;font-size:13.5px} .slotrow .gap{color:var(--err);font-weight:600}
 .overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:flex-end;justify-content:center;z-index:50}
 .overlay[hidden]{display:none}
 .sheet{background:var(--bg);border:1px solid var(--line);border-radius:16px 16px 0 0;width:100%;max-width:640px;max-height:82vh;display:flex;flex-direction:column;padding:12px 14px}
 @media(min-width:560px){.overlay{align-items:center}.sheet{border-radius:16px}}
 .sheethead{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
 #pickSearch{margin-bottom:8px}
 .picklist{overflow:auto;flex:1;min-height:0}
 .pick{display:block;text-align:left;width:100%;min-height:0;padding:9px 11px;margin-bottom:4px} .pick .mut{display:block;margin-top:2px}
 .pick.sel{border-color:var(--acc);background:var(--accbg,rgba(80,140,255,.14))}
 .pick .tick{display:none;float:right;font-weight:800;color:var(--acc)} .pick.sel .tick{display:inline}
 .pickfoot{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:8px;padding-top:8px;border-top:1px solid var(--line)}
 .pickfoot[hidden]{display:none} .pickfootbtns{display:flex;gap:6px} #pickAdd[disabled]{opacity:.5}
 .appbar{position:sticky;top:0;z-index:15;background:var(--bg);border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;padding:8px 12px}
 .brand{font-size:15px;white-space:nowrap;display:flex;flex-direction:column;line-height:1.15;gap:3px}.brand b{font-weight:800}
 .brand-version{font:10px/1.1 ui-monospace,Consolas,monospace;letter-spacing:.01em;color:var(--mut);opacity:.85}
 .maintabs{display:flex;gap:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;flex:1}
 .maintab{flex:0 0 auto;display:inline-flex;align-items:center;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--mut);font-size:13px;cursor:pointer;white-space:nowrap;min-height:40px;position:relative}
 .maintab.on{background:var(--acc);color:#fff;border-color:transparent;font-weight:600}
 .ic{margin-right:5px;font-size:14px;line-height:1}
 .maintab.connected::after,.mitem.connected::after{content:"";position:absolute;top:6px;right:7px;width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 5px var(--ok)}
 /* mobile menu (hidden on desktop) */
 .menuBtn{display:none;align-items:center;gap:8px;flex:1;justify-content:space-between;padding:9px 13px;border:1px solid var(--line);border-radius:999px;background:var(--acc);color:#fff;font-size:14px;font-weight:600;cursor:pointer;min-height:42px;position:relative}
 .menuBtn .caret{opacity:.85}
 .menuBtn.conn::before{content:"";position:absolute;top:7px;left:9px;width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 5px var(--ok)}
 .menu{display:none;position:absolute;top:calc(100% + 4px);right:8px;left:8px;background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.35);padding:6px;z-index:40;max-height:78vh;overflow:auto}
 .menu.open{display:block}
 .mgrp{font-size:11px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:.05em;padding:8px 10px 3px}
 .mitem{display:flex;align-items:center;width:100%;text-align:left;padding:11px 12px;border:0;background:transparent;color:var(--ink);font-size:14.5px;border-radius:8px;cursor:pointer;min-height:44px;position:relative}
 .mitem.on{background:var(--acc);color:#fff;font-weight:600}
 @media(max-width:720px){ .maintabs{display:none} .menuBtn{display:inline-flex} }
 .void-wrap{max-width:920px;margin:0 auto;padding:20px 16px 100px}
 .void-wrap h2{font-size:19px;margin:8px 0}.void-slots{display:grid;grid-template-columns:repeat(auto-fit,minmax(265px,1fr));gap:14px;margin-top:16px}
 .void-slot{padding:16px;border:1px solid var(--line);border-radius:12px;background:var(--card)}
 .void-slot-num{font-weight:750}.void-slot-num .mut{font-size:12px;font-weight:400;margin-left:4px}
 .void-slot label.chk2{margin:12px 0 0;font-size:12px;line-height:1.4}
 .void-slot input[type=checkbox]{width:auto}
 .prst-lab-wrap{padding-top:22px;padding-bottom:85px}
 .prst-lab-tabs{margin:18px 0 20px;padding:8px 0}
 .prst-pane[hidden]{display:none!important}
 .prst-pane .ovbox{padding:17px;border-radius:12px}
 .prst-pane #native-prst-export{border:1px solid var(--line);border-radius:12px;background:var(--card2);padding:18px}
 .prst-pane #nativePrstList{margin-top:14px}
 /* Dense readable list workspace */
 #view-studio>.wrap{max-width:1400px}
 @media(max-width:600px){
  .manage-part .slotrow{flex-wrap:wrap}
  .manage-part .slotrow .lbl{flex-basis:calc(100% - 34px)}
 }
 .manage-intro{display:flex;align-items:baseline;flex-wrap:wrap;gap:6px 14px;margin:4px 0 12px}
 .manage-intro h2{margin:0;font-size:17px}.manage-intro .mut{margin:0}
 #panel-manage{max-width:1360px;margin:auto}
 .manage-layout{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}
 .manage-part{min-width:0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}
 .manage-head{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:7px}
 .manage-head h3{font-size:14px;margin:0}.manage-head .mut{font-size:11px}
 .manage-part .field-label{margin:1px 0 3px}
 .manage-part select,.manage-part input[type=search]{padding:7px 9px;min-height:36px}
 .manage-toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:5px;margin:7px 0 8px}
 .manage-toolbar button{min-height:31px;padding:5px 9px;font-size:12px;line-height:1.2}
 .manage-list{max-height:calc(100vh - 280px);min-height:240px;overflow:auto;scrollbar-gutter:stable}
 #dataList details.art{margin:0 0 4px;padding:0 7px;border-radius:7px}
 #dataList details.art summary{padding:4px 0}
 #dataList details.art .song{padding:2px 0}
 #dataList .songhead{gap:3px}
 #dataList .chk{padding:2px 0;font-size:12px;line-height:1.3}
 #dataList .chk.sub{padding-left:19px;font-size:11.5px}
 #dataList .chk input{width:15px;height:15px}
 .manage-part .slotrow{padding:4px 0;gap:4px;flex-wrap:nowrap}
 .manage-part .slotrow .lbl{min-width:0;font-size:12px;line-height:1.3;overflow-wrap:anywhere}
 .manage-part .slotrow .sl{min-width:24px;font-size:11px}
 .manage-part .slotrow button.mini{padding:4px 6px;min-height:28px;flex-shrink:0}
 .manage-part .slotrow .mut{font-size:11px}
 .manage-part details.art[hidden],.manage-part .song[hidden]{display:none!important}
 .variant-hint{font-size:11px;line-height:1.3;color:var(--mut);flex:1 1 230px}
 .pick{padding:6px 9px;margin-bottom:3px;border-radius:7px;line-height:1.3}
 .pick .mut{display:inline;margin-left:5px;font-size:11px}
 .slotrow{padding:4px 2px;gap:5px}
 .prst-pane .slotrow .lbl{font-size:12px}
 @media(max-width:860px){
  .manage-layout{grid-template-columns:minmax(0,1fr)}
  .manage-list{max-height:55vh;min-height:0}
  .manage-part{padding:9px}
 }
 .library-pane[hidden]{display:none!important}
 .view{display:none} .view.active{display:block}
 .view .tabs{position:static}
 .view iframe.full{width:100%;height:calc(100vh - 120px);border:0;border-radius:0;margin:0;background:#fff}
 .docbar{display:flex;gap:8px;padding:10px 12px;align-items:center;border-bottom:1px solid var(--line);flex-wrap:wrap}
 .docbar .seg{display:inline-flex;gap:4px} .docbar .segright{margin-left:auto}
 .loading{padding:20px;color:var(--mut)}
 /* Docs: left section index (desktop) / top bars menu (mobile) + rendered doc */
 .docsview{display:flex;height:calc(100vh - 120px)}
 .docnav{flex:0 0 244px;min-width:0;border-right:1px solid var(--line);overflow:auto;padding:10px;background:var(--bg)}
 .docnav>select{margin-bottom:8px}
 .docnavToggle{display:none}
 .doctoc{display:flex;flex-direction:column;gap:1px}
 .doctoc a{display:block;padding:5px 8px;color:var(--ink);text-decoration:none;font-size:13px;line-height:1.3;border-radius:6px}
 .doctoc a:hover{background:var(--card2)}
 .doctoc a.on{background:var(--acc);color:#fff}
 .doctoc a.l3{padding-left:20px;font-size:12.5px;color:var(--mut)}
 .doctoc a.l3.on{color:#fff}
 .docframe{flex:1;min-width:0;border:0;background:#fff;height:100%}
 @media(max-width:720px){
  .docsview{flex-direction:column;height:calc(100vh - 112px)}
  .docnav{flex:0 0 auto;border-right:0;border-bottom:1px solid var(--line);padding:8px 10px;position:sticky;top:0;z-index:6}
  .docnav>select{margin-bottom:6px}
  .docnavToggle{display:flex;align-items:center;justify-content:space-between;gap:8px;width:100%;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:10px;min-height:40px;font-size:14px;font-weight:600}
  .doctoc{display:none;margin-top:6px;max-height:44vh;overflow:auto}
  .docnav.open .doctoc{display:flex}
 }
 @media(max-width:560px){ h1{font-size:16px} .brand{font-size:13px} .row button{flex:1 1 100%} iframe{height:68vh} .view iframe.full{height:calc(100vh - 112px)} }
 /* short viewports (landscape phones): shrink the chrome so the listing gets the height */
 @media(max-height:520px){
  .appbar{padding:3px 10px} .brand{font-size:12.5px}
  .maintab{min-height:30px;padding:4px 10px;font-size:12px}
  .tabs{padding:4px 10px} .tab{min-height:30px;padding:5px 11px}
  .docbar{padding:4px 10px} .docbar .mini{min-height:26px}
  .view iframe.full{height:calc(100vh - 86px)} iframe.hasbar{height:calc(100vh - 90px)}
  .docsview{height:calc(100vh - 86px)}
 }

 /* Global checkboxes must never inherit the 100%-wide input text rule. */
 input[type="checkbox"],input[type="radio"]{width:16px!important;min-width:16px!important;max-width:16px!important;height:16px!important;min-height:16px!important;max-height:16px!important;flex:0 0 16px!important;margin:0!important;padding:0!important;accent-color:var(--acc)}
 .chk,.chk2,.setting-line{width:auto;min-width:0;margin:0;line-height:1.3}
 #pTypes .chk2{display:inline-flex;align-items:center;gap:6px;padding:4px 7px;border:1px solid var(--line);border-radius:6px;background:var(--card2);font-size:12px}
 .studio-workflow{max-width:1380px;padding-top:16px}
 .studio-heading{display:flex;align-items:baseline;gap:7px 18px;flex-wrap:wrap;margin-bottom:13px}
 .studio-heading h2{font-size:19px;margin:0}.studio-heading p{font-size:12px;color:var(--mut);margin:0}
 .studio-columns{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;align-items:start}
 .studio-step{min-width:0;padding:15px;border:1px solid var(--line);border-radius:11px;background:var(--card)}
 .step-heading{display:flex;gap:9px;align-items:start;margin-bottom:11px}
 .step-heading h3{margin:0;font-size:15px}.step-heading p{margin:3px 0 0;font-size:12px;color:var(--mut)}
 .step-num{display:grid;place-items:center;flex:0 0 26px;height:26px;background:var(--acc);border-radius:7px;color:#fff;font-size:13px;font-weight:800}
 .studio-step>label{display:block;font-size:12px;font-weight:600;margin:10px 0 4px}
 .studio-step .chk2{margin:0}
 .studio-step input:not([type=checkbox]),.studio-step select,.studio-step textarea{font-size:13px;padding:8px 10px}
 .studio-step textarea{line-height:1.5;resize:vertical;min-height:80px}
 .studio-step #pasteBox{min-height:220px;font:12px/1.5 ui-monospace,Consolas,monospace}
 .studio-step #promptOut{min-height:170px;font:12px/1.5 ui-monospace,Consolas,monospace}
 .studio-step .generated-caption:has(+ textarea[hidden]){display:none}
 .studio-actions{display:flex;gap:7px;flex-wrap:wrap;margin:12px 0 6px}
 .studio-actions button{padding:7px 12px;min-height:36px;font-size:13px}
 .studio-hint{padding:8px 10px;border:1px solid var(--line);border-radius:7px;background:var(--card2);font-size:11.5px;color:var(--mut)}
 .manage-wrap{max-width:1480px}.manage-layout{gap:10px;grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
 #panel-manage{max-width:none;width:100%}
 .manage-part{padding:9px;min-width:0;overflow:hidden}
 .manage-list{max-height:calc(100vh - 250px);min-width:0}
 #dataList details.art{margin:0 0 3px;padding:0 6px}
 #dataList details.art summary{padding:4px 1px;display:flex;align-items:center;gap:5px;min-width:0}
 #dataList summary .chk{flex:1;min-width:0;display:flex;align-items:center;gap:5px;margin:0;padding:0;white-space:normal}
 #dataList .song{padding:3px 0}#dataList .songhead{min-width:0;gap:3px}
 #dataList .songhead .chk{flex:1;min-width:0;margin:0;gap:5px;padding:2px 1px;font-size:11.5px;line-height:1.25}
 #dataList .chk.sub{display:flex;gap:5px;margin:0;padding:2px 0 2px 18px;font-size:11px;line-height:1.25}
 #dataList .songhead button.mini{padding:3px 6px;min-height:24px;flex:0 0 auto}
 #dataList .mut{font-size:10.5px;overflow-wrap:anywhere}
 .manage-part .slotrow{display:grid;grid-template-columns:24px minmax(0,1fr) repeat(4,max-content);align-items:center;gap:4px;padding:4px 0;min-width:0}
 .manage-part .slotrow .lbl{min-width:0;font-size:11.5px;overflow-wrap:anywhere;line-height:1.25}
 .manage-part .slotrow .mut{font-size:10px}
 .manage-part .slotrow button.mini{min-height:25px;padding:3px 5px;font-size:10.5px}
 .manage-part .manage-toolbar{gap:5px;margin:5px 0}.manage-part .manage-toolbar button{min-height:29px;padding:4px 8px}
 #pickList .pick{padding:5px 8px;margin-bottom:2px;min-height:0}#pickList .pick .mut{display:inline;margin-left:6px}
 .void-wrap{max-width:1050px;padding:12px 14px 85px}.void-slots{gap:9px;margin-top:9px}.void-slot{padding:11px}
 .prst-lab-wrap{padding-top:12px}.prst-lab-tabs{margin:10px 0 12px}.prst-pane .ovbox{padding:12px}
 .status-strip{display:flex;align-items:center;gap:5px;margin-left:auto;flex:0 0 auto}
 button.status-chip{display:inline-flex;gap:6px;align-items:center;justify-content:center;background:transparent;border:1px solid var(--line);border-radius:7px;color:var(--mut);font-size:10.5px;min-height:29px;padding:5px 7px;white-space:nowrap}
 .status-led{display:block;width:7px;height:7px;min-width:7px;border-radius:50%;background:var(--err);box-shadow:0 0 0 2px rgba(255,111,111,.1)}
 [data-state="good"]>.status-led{background:var(--ok);box-shadow:0 0 0 2px rgba(62,207,154,.12)}
 button.status-chip:hover{border-color:var(--acc)}
 .settings-wrap{max-width:780px;padding:18px 14px 95px}.settings-wrap h2{font-size:19px;margin:0 0 5px}
 .settings-card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px;margin:11px 0}
 .settings-card h3{font-size:14px;margin:0 0 10px}
 .setting-line{display:flex;align-items:flex-start;gap:9px;cursor:pointer;font-size:13px;padding:7px 0}
 .settings-actions{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.settings-actions button{font-size:12px;padding:7px 10px;min-height:35px}
 .startup-backdrop{position:fixed;inset:0;z-index:90;background:rgba(0,0,0,.68);display:flex;align-items:center;justify-content:center;padding:18px}
 .startup-backdrop[hidden]{display:none!important}
 .startup-card{width:min(100%,480px);background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:14px;padding:20px;box-shadow:0 16px 60px rgba(0,0,0,.42)}
 .startup-head{display:flex;gap:9px;align-items:center}.startup-head h2{font-size:18px;margin:0}
 .startup-card p{font-size:13px;line-height:1.55;margin:13px 0}
 .startup-card .startup-choice{font-size:12px;color:var(--mut);margin-top:12px}
 .startup-actions{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;margin-top:14px}
 .startup-actions button{min-height:36px;padding:7px 12px;font-size:13px}.startup-error{color:var(--err);font-weight:600}
 html[data-density="comfortable"] .manage-part .slotrow{padding:9px 0}
 html[data-density="comfortable"] #dataList .song{padding:9px 0}
 html[data-density="comfortable"] #pickList .pick{padding:11px 12px}
 @media(max-width:1140px){.status-strip{order:3;width:100%;justify-content:flex-end;margin-top:4px}.appbar{flex-wrap:wrap}}
 @media(max-width:860px){.studio-columns,.manage-layout{grid-template-columns:minmax(0,1fr)}.manage-list{max-height:50vh;min-height:0}}
 @media(max-width:560px){.status-strip{justify-content:center;gap:4px}button.status-chip{padding:4px 6px;font-size:10px}.manage-part .slotrow{display:flex;flex-wrap:wrap;gap:4px;padding:5px 0}.manage-part .slotrow .lbl{flex:1 1 calc(100% - 34px)}.studio-workflow,.manage-wrap{padding:10px 8px 90px}.studio-step{padding:10px}}

 .overview-header{display:flex;align-items:baseline;flex-wrap:wrap;gap:8px 16px;margin-bottom:6px}
 .overview-header h2{margin:0;font-size:17px}.overview-header #stats{font-size:12px;line-height:1.4}
 #panel-overview{margin:8px 10px 0;padding:10px 12px;border:1px solid var(--line);border-radius:9px;background:var(--card)}
 #panel-overview .row{margin:5px 0;gap:6px}#panel-overview .row button{padding:5px 9px;min-height:29px;font-size:12px}
 #panel-overview .overview-zip-help{font-size:11px;color:var(--mut);margin-top:5px}
 #panel-overview .overview-zip-help summary{cursor:pointer}
 .overview-listing{min-width:0;padding:0}
 .overview-listing iframe.full{height:calc(100vh - 270px);min-height:320px;width:100%;border:0;background:#fff}
 .overview-listing iframe.hasbar{height:calc(100vh - 315px)}
 .overview-listing .docbar{padding:6px 10px}
 .debug-fab{position:fixed;right:16px;bottom:67px;z-index:27;display:flex;gap:7px;align-items:center;border:1px solid var(--acc);border-radius:999px;background:var(--acc);color:white;box-shadow:0 4px 17px rgba(0,0,0,.28);padding:10px 15px;font-size:12px;font-weight:700;cursor:pointer;min-height:40px}
 .debug-fab>span:first-child{font-size:18px;line-height:12px}
 .debug-panel{position:fixed;right:15px;bottom:119px;width:min(640px,calc(100vw - 30px));height:min(65vh,570px);z-index:28;display:flex;flex-direction:column;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:13px;box-shadow:0 9px 38px rgba(0,0,0,.45);overflow:hidden}
 .debug-panel[hidden]{display:none!important}
 .debug-head{display:flex;align-items:center;gap:9px;padding:10px 12px;border-bottom:1px solid var(--line)}
 .debug-head b{font-size:14px}.debug-head .mut{font-size:11px;flex:1}
 .debug-head button{font-size:20px;line-height:1;border:0;background:transparent;color:var(--ink);cursor:pointer}
 .debug-controls{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:8px 10px;border-bottom:1px solid var(--line)}
 .debug-controls select{width:125px;min-width:100px}.debug-controls input[type=search]{width:auto;min-width:120px;flex:1}
 .debug-controls select,.debug-controls input[type=search]{padding:6px 7px;min-height:31px;font-size:11.5px}
 .debug-follow{display:flex;align-items:center;gap:5px;font-size:11px;white-space:nowrap;margin:0}
 .debug-rows{flex:1;min-height:80px;overflow:auto;padding:5px 9px;background:var(--bg);font:11px/1.45 ui-monospace,Consolas,monospace}
 .debug-line{display:grid;grid-template-columns:170px minmax(0,1fr);gap:7px;padding:3px 4px;border-bottom:1px solid var(--line);overflow-wrap:anywhere;white-space:pre-wrap}
 .debug-when{font-size:10px;color:var(--mut)}
 .debug-error .debug-when{color:var(--err)}.debug-warn .debug-when{color:var(--warn)}
 .debug-footer{display:flex;gap:6px;align-items:center;flex-wrap:wrap;padding:8px 10px;border-top:1px solid var(--line)}
 .debug-footer button{padding:6px 8px;min-height:30px;font-size:11.5px}
 .debug-status{font-size:11px;color:var(--mut);padding:0 10px 7px;line-height:1.3}
 @media(max-width:680px){.debug-line{grid-template-columns:minmax(0,1fr)}.debug-when{font-size:10px}.debug-fab{bottom:65px;right:9px}.debug-panel{right:8px;width:calc(100vw - 16px);bottom:114px;height:min(63vh,540px)}.overview-listing iframe.full{height:65vh}}
`;

const BODY = String.raw`
<div class="appbar">
 <div class="brand"><span>🎛️ PocketMaster <b>Studio</b></span><span class="brand-version">Void&#39;s MOD v0.4.1 · Original v0.1 (assumed)</span></div>
 <div class="maintabs" id="maintabs"></div>
 <button class="menuBtn" id="menuBtn" aria-expanded="false" aria-haspopup="true"><span id="menuBtnLabel"></span><span class="caret">▾</span></button>
 <div class="menu" id="menu"></div>
 <div class="status-strip" role="group" aria-label="Connection status">
  <button type="button" id="statusServer" class="status-chip" data-state="bad"><span class="status-led"></span><span class="status-text">Server OFFLINE</span></button>
  <button type="button" id="statusFolder" class="status-chip" data-state="bad"><span class="status-led"></span><span class="status-text">Folder Disconnected</span></button>
  <button type="button" id="statusBrowser" class="status-chip" data-state="bad"><span class="status-led"></span><span class="status-text">Browser Limited</span></button>
 </div>
</div>
<div id="views">
<section class="view active" id="view-studio">
 <div class="wrap studio-workflow">
  <div class="studio-heading"><h2>AI Tone Studio</h2><p>Generate a prompt, request a JSON preset from your AI assistant, then validate and import the response into your library.</p></div>
  <div class="studio-columns">
   <section class="studio-step" id="panel-prompt" aria-labelledby="studioStepOne">
    <div class="step-heading"><span class="step-num">1</span><div><h3 id="studioStepOne">Create a tone prompt</h3><p>Describe an artist, songs and the kinds of guitar tones you want.</p></div></div>
    <label for="pArtist">Artist</label><input id="pArtist" placeholder="e.g. The Police" autocomplete="off">
    <label>Preset types</label>
    <div class="checks" id="pTypes">
      <label class="chk2"><input type="checkbox" value="soft/clean rhythm" checked> Clean rhythm</label>
      <label class="chk2"><input type="checkbox" value="heavy rhythm" checked> Heavy rhythm</label>
      <label class="chk2"><input type="checkbox" value="soft/melodic solo" checked> Soft solo</label>
      <label class="chk2"><input type="checkbox" value="loud/shred solo" checked> Loud solo</label>
    </div>
    <label for="pSongs">Songs, references and tone details</label>
    <textarea id="pSongs" rows="4" placeholder="e.g. Message in a Bottle clean riff; Walking on the Moon lead…"></textarea>
    <label for="pFmt">Requested result</label>
    <select id="pFmt"><option value="app source data JSON">Project source JSON (recommended)</option><option value="complete pedal JSON">Pedal preset JSON</option><option value="both">Both formats</option></select>
    <div class="studio-actions"><button id="genPrompt" class="primary">Generate prompt</button><button id="copyPrompt" hidden>Copy prompt</button></div>
    <label class="generated-caption" for="promptOut">Generated prompt — send this to your AI assistant</label>
    <textarea id="promptOut" rows="9" readonly hidden></textarea>
   </section>
   <section class="studio-step" id="panel-paste" aria-labelledby="studioStepTwo">
    <div class="step-heading"><span class="step-num">2</span><div><h3 id="studioStepTwo">Import the JSON response</h3><p>Paste the AI-generated JSON here. Review the analysis before you apply any changes.</p></div></div>
    <div class="studio-hint">Supports <b>artist source JSON</b> (adds/updates artists) and <b>pedal preset JSON</b> (definitive override). Invalid data is rejected.</div>
    <label for="pasteBox">JSON to validate</label>
    <textarea id="pasteBox" rows="13" spellcheck="false" placeholder='Paste a JSON object here, then choose "Analyze JSON".'></textarea>
    <div class="studio-actions"><button id="analyzeBtn" class="primary">Analyze JSON</button><button id="applyBtn" class="attn" hidden>Apply to library</button><button id="clearPasteBtn">Clear</button></div>
    <div id="pasteResult" aria-live="polite"></div>
   </section>
  </div>
 </div>
</section>
<section class="view" id="view-library">
 <div class="tabs library-tabs" role="tablist" aria-label="Library views">
  <button class="tab on" type="button" role="tab" data-library-pane="overview" aria-selected="true" aria-controls="library-pane-overview">Overview</button>
  <button class="tab" type="button" role="tab" data-library-pane="full" aria-selected="false" aria-controls="library-pane-full">Table</button>
  <button class="tab" type="button" role="tab" data-library-pane="map" aria-selected="false" aria-controls="library-pane-map">Map</button>
  <button class="tab" type="button" role="tab" data-library-pane="manage" aria-selected="false" aria-controls="library-pane-manage">Manage</button>
  <button class="tab" type="button" role="tab" data-library-pane="docs" aria-selected="false" aria-controls="library-pane-docs">Docs</button>
 </div>
 <section class="library-pane" id="library-pane-overview" role="tabpanel">
  <div class="wrap">
 <section class="panel" id="panel-overview">
  <div class="overview-header"><h2>Overview</h2><span id="stats">Loading…</span></div>
  <div class="row">
   <button id="exportZip">📦 Export ZIP (full structure)</button>
   <button id="importBtn">📥 Import project…</button>
   <button id="dlIndex">⬇️ index.html</button>
   <input id="importFile" type="file" accept=".zip,.json" hidden>
  </div>
  <details class="overview-zip-help"><summary>What is included in the project ZIP?</summary><div class="sub">The ZIP contains source data, generated Modeled and NAM presets, listings, PocketMasterStudio.html, and pocketmaster.source.json. Import accepts a project ZIP or source JSON.</div></details>
 </section>
 <div id="overview-listing" class="overview-listing" aria-label="Preset listing"></div>

  </div>
 </section>
 <section class="library-pane" id="library-pane-full" role="tabpanel" hidden></section>
 <section class="library-pane" id="library-pane-map" role="tabpanel" hidden></section>
 <section class="library-pane" id="library-pane-manage" role="tabpanel" hidden>
  <div class="wrap manage-wrap">
 <section class="panel" id="panel-manage">
  <div class="manage-intro">
   <h2>Manage library</h2>
   <p class="mut">Source data and collections share one workspace. Deleting a source preset removes it from the project; removing a collection slot only removes its reference.</p>
  </div>
  <div class="manage-layout">
   <section class="manage-part manage-source" aria-labelledby="manageSourceTitle">
    <div class="manage-head"><h3 id="manageSourceTitle">Source data</h3><span class="mut">Artists · songs · takes</span></div>
    <input id="dataFilter" type="search" placeholder="Filter artists, songs or takes…" aria-label="Filter source data" autocomplete="off">
    <div class="manage-toolbar"><button id="delBtn" class="mini attn">Delete selected from source</button></div>
    <div id="dataList" class="manage-list"></div>
   </section>
   <section class="manage-part manage-collections" aria-labelledby="manageCollectionTitle">
    <div class="manage-head"><h3 id="manageCollectionTitle">Collections</h3><span class="mut">Ordered preset references</span></div>
    <label class="field-label" for="collSel">Collection</label><select id="collSel"></select>
    <div class="manage-toolbar">
     <button id="collAdd" class="mini primary">+ Add preset</button>
     <button id="collNew" class="mini">New</button>
     <button id="collDelete" class="mini attn">Delete collection</button>
    </div>
    <div id="collBody" class="manage-list"></div>
   </section>
  </div>
 </section>
  </div>
 </section>
 <section class="library-pane" id="library-pane-docs" role="tabpanel" hidden></section>
</section>
</div>

<button id="globalLogToggle" class="debug-fab" type="button" aria-label="Open Log / Debug" aria-expanded="false" aria-controls="globalLogPanel"><span aria-hidden="true">≡</span><span>Log / Debug</span></button>
<section id="globalLogPanel" class="debug-panel" role="dialog" aria-label="Application Log and Debug" hidden>
 <div class="debug-head"><b>Log / Debug</b><span id="globalLogCount" class="mut">0 entries</span><button id="globalLogClose" type="button" aria-label="Close log">×</button></div>
 <div class="debug-controls">
  <select id="globalLogLevel" aria-label="Filter severity"><option value="ALL">All levels</option><option value="INFO">Info</option><option value="WARN">Warnings</option><option value="ERROR">Errors</option><option value="DEBUG">Debug</option></select>
  <input type="search" id="globalLogSearch" placeholder="Search events…" aria-label="Search debug entries" autocomplete="off">
  <label class="debug-follow"><input id="globalLogFollow" type="checkbox" checked> Follow</label>
 </div>
 <div id="globalLogRows" class="debug-rows" role="log" aria-live="off"></div>
 <div class="debug-footer"><button type="button" id="globalLogSave" class="primary">Save to logs/</button><button type="button" id="globalLogDownload">Download .log</button><button type="button" id="globalLogClear">Clear</button></div>
 <div id="globalLogExportStatus" class="debug-status" role="status"></div>
</section>
<div id="startupDialog" class="startup-backdrop" hidden>
 <div class="startup-card" role="dialog" aria-modal="true" aria-labelledby="startupTitle" aria-describedby="startupBody">
  <div class="startup-head"><span class="status-led"></span><h2 id="startupTitle">Information</h2></div>
  <p id="startupBody"></p>
  <label class="setting-line startup-choice"><input id="startupOptOut" type="checkbox"><span id="startupOptOutLabel">Do not show this again</span></label>
  <p id="startupError" class="startup-error" role="alert"></p>
  <div class="startup-actions"><button type="button" class="primary" id="startupConnect" hidden>Connect project folder…</button><button type="button" id="startupDismiss">Continue</button></div>
 </div>
</div>
<div id="picker" class="overlay" hidden>
 <div class="sheet">
  <div class="sheethead"><b id="pickTitle">Choose preset</b><button id="pickClose" class="mini">✕</button></div>
  <input id="pickSearch" placeholder="Search by name, artist, song…">
  <div id="pickList" class="picklist"></div>
  <div id="pickFoot" class="pickfoot" hidden>
   <span id="pickCount" class="mut"></span>
   <span class="pickfootbtns"><button id="pickCancel" class="mini">Cancel</button><button id="pickAdd" class="mini on">Add</button></span>
  </div>
 </div>
</div>
<div class="savebar">
 <span id="dirtyTag" hidden>unsaved changes</span><span class="sp"></span>
 <button id="saveBtn" class="primary">💾 Save config</button>
</div>
<div id="toast" hidden></div>
`;

const html =
`<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PocketMaster Studio</title>
<style>${CSS}</style></head><body>
${BODY}
<script type="text/plain" id="pm-payload">${blob}</script>
<script type="text/plain" id="pm-editor">${editorBlob}</script>
${modules}
<script>${appJs}</script>
${prstScripts}
<script>${prstUi}</script>
</body></html>`;

const OUT = path.join(ROOT, "PocketMasterStudio.html");
fs.writeFileSync(OUT, html, "utf-8");
console.log("wrote", OUT, "(" + (html.length / 1024).toFixed(0) + " KB)");
