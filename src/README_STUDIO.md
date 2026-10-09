# PocketMaster Studio

A **single, self-contained HTML app** that generates, edits and packages guitar presets for the
**Sonicake PocketMaster** pedal — everything runs in the browser, with no server and no
dependencies. Open the file, use it, save it.

- **61 artists · 260 songs · 482 presets** (1–21 per artist) + **5 built-in cross-artist
  compilations** (plus any you add), in **three amp sets**: **Modeled** (the tuned modeled amps),
  **Clone/NAM** (every preset on one of 5 NAM captures) and **Mixed** (the best choice per preset).
- Everything is **generated from one embedded source of truth** (`data/`), validating every
  effect and parameter against the real device catalog.
- It is an **all-in-one**: it embeds the **editor** (PocketEdit, with Web Bluetooth to talk to the
  pedal), the **listings/tables/maps** (generated live, so they always reflect your edits) and the
  **docs** — plus the generation/editing tools. No separate hub.
- The app **saves an updated copy of itself** (with your edits embedded) and can **export the
  full file tree as a ZIP** or **import a whole project** back.

> **Requires a Chromium browser with Web Bluetooth** — **Chrome**, **Edge** or **Opera**, on
> desktop **and** Android. Safari and Firefox cannot connect to the pedal, and lack the
> `CompressionStream` / File System Access APIs used to save. The app checks this on load and
> warns if anything is missing.

---

## 🕘 Recent changes

_since the previous full export_

_Baseline established: 61 artists, 260 songs, 455 presets._

## 1. Quick start

1. Open **`PocketMasterStudio.html`** in Chrome/Edge/Opera (double-click, or host it anywhere).
2. It decompresses its embedded data and **runs the whole pipeline in ~50–120 ms**, showing a
   live preview of the generated listing.
3. Use the tabs to generate a prompt, paste AI/pedal JSON, edit data, manage collections.
4. Click **💾 Save** to write a new `PocketMasterStudio.html` containing your changes, or
   **📦 Export ZIP** to get the full extracted file structure.

Nothing is uploaded anywhere; all processing is local to your browser.

---

## 2. Core concepts

- **Source of truth = the embedded `data/`.** The app carries a gzip+base64 blob
  (`<script id="pm-payload">`) holding `data/` (one object per artist), the device catalog
  (`mld.json`), the 50 factory presets, per-preset **overrides**, the **collection definitions**,
  the portable **AI prompt**, and this README. Everything else (`json/`, `json_nam/`, `json_mixed/`,
  all the HTML listings, the editor library) is **derived** from it at runtime.
- **Self-contained & self-saving.** The HTML file exists on disk, but needs **no sibling files** —
  it reads nothing from disk at runtime (which is why it also works on Android `content://`).
  Saving produces a **new copy of the same self-contained file** with the embedded blob replaced.
- **Loose files are optional exports.** The ~1500 individual `json/` files are only produced when
  you export a ZIP (for GitHub browsing, sharing single presets, GitHub Pages). The app itself
  never needs them.

---

## 3. The interface

A top bar switches between the main areas:

| Main tab | What it is |
|---|---|
| **Studio** | The generation/editing tools (sub-tabs below). |
| **Editor** | The embedded **PocketEdit** editor — connects to the pedal over **Web Bluetooth**, imports/exports presets, Browse Library (**Modeled / NAM clones / Mixed** sets). Runs in an isolated `blob:` frame so Web Bluetooth works; its Browse Library is rebuilt from your current data each time it opens. Plain **Export** / **Export Multiple** save a JSON to disk; **Export as Override** hands the preset to Studio to make it definitive (see the round-trip below). |
| **Listing / Table / Map** | The generated pages, rendered **live** (mobile listing, detailed table, song→Best50 map), always up to date with your edits. Each view has a radio-style **`Modeled` / `Clone/NAM` / `Mixed`** amp-set selector (defaults to **Mixed**); Table and Map also have an **Interactive ⇄ Print (A4)** toggle (the amp-set choice applies to both modes; switching amp-set keeps your current search, expanded rows and scroll position). |
| **Docs** | README, representative songs and the two prompt docs, rendered in-page. |

Inside **Studio**:

| Sub-tab / action | What it does |
|---|---|
| **Overview** | Live stats + a preview of the generated listing. Buttons: Export ZIP, Import project, download index.html. |
| **AI Prompt** | Fill in artist + songs + output format → generate a ready-to-paste prompt (full device catalog embedded) for any AI chat. Copy it, ask for the **app source JSON**. |
| **Paste JSON** | Paste the JSON the AI returns **or** a preset exported from the pedal. Auto-detected: a **source artist** (`{name, songs:[…]}`) is merged into `data/`; a **pedal export** (has `modules`) is made **definitive** via an override, matched by preset name. |
| **Data** | Browse the source (artist → song → variants). Reorder songs within an artist (**↑/↓** — sets the artist bundle's slot order; within a song, presets stay auto-ordered calm→loud). Tick songs/presets and **delete** them; deletions that break a collection prompt you to substitute (searchable). Lists active overrides (removable). |
| **Collections** | Manage collections: **reorder** slots (↑/↓), replace/remove any slot, or **add** presets (searchable picker — when there are free slots you can **tick several at once**, capped at the number of free slots; if the collection is full you pick one preset and which slot to replace). **Create** new collections and **delete** them. |
| **💾 Save** (always visible) | Re-gzips the edited source and writes a new `PocketMasterStudio.html` (File System Access on desktop, download on Android). |

**The round-trip** (edit a preset on the pedal → make it definitive): tweak it on the pedal, open
the **Editor** tab and use **Export as Override** (in the ⚙️ advanced settings) — the preset is
handed to Studio and pre-loaded into **Paste JSON** automatically (you can also paste it by hand).
Confirm, and it is stored as a per-preset **override** and re-applied on every regeneration, so your
tweak becomes permanent.

---

## 4. Data model

### 4.1 `data/<Artist>.json` (the source)

```jsonc
{
  "name": "AC/DC",                 // display name (may contain "/")
  "songs": [
    {
      "slug": "BackInBlack",       // used in filenames
      "short": "BackBlck",         // ≤ 8 chars, base of presetName
      "variants": [                // one entry per preset the song needs
        {
          "kind": "R",             // C clean · R driven · D 2nd dist · H heavy · L/L2/L3 lead
          "role": "rhy",           // cln → lds → rhy → hvy → ldr  (level, gate, order)
          "desc": "Back in Black: greasy open Plexi riff",
          "mods": {                // ONLY the modules/params you set; the rest are filled from mld.json
            "AMP": { "effect": "Brit 45", "enabled": true, "params": { "Gain": 60, "Vol": 84 } },
            "IR":  { "effect": "BritGN 4x12", "enabled": true, "params": { "Vol": 85 } }
          }
        }
      ]
    }
  ]
}
```

`_config.json` holds `order` (build/list order — add new artists here), `tone_bc` (solos shipped
in 3 voicings A/B/C) and `double_chorus` (solos shipped as a detune+chorus pair). `La/Lb/Lc` and
`Ld/Lh` variants are produced automatically from those tables — never write them by hand.

### 4.2 The signal chain (fixed)

```
NR → FX1 → DRV → AMP → IR → EQ → FX2 → DLY → RVB
```

Each preset always contains all 9 modules; each is enabled or bypassed but still carries an effect
and its parameters. Every name and value is **validated against `mld.json`** — an out-of-range
value or unknown effect fails the build (and, in the app, blocks the incorporation with a message).

### 4.3 Overrides (round-trip)

A per-preset patch keyed `"Artist|PresetName"` storing an exact `{ampMode, presetVolume, modules}`.
`ampMode: "Normal"` overrides target the modeled `json/` set; `"Clone"` overrides target the NAM
`json_nam/` set. An override **freezes** that preset (its computed design is ignored) until removed.
Overrides live in two files at the **repo root**, next to `data/`: **`factory_overrides.json`** and
**`nam_overrides.json`** (each an object of those keys). The Node build loads them (empty `{}` if
absent) and **Export ZIP writes them out**, so overrides you create in the app round-trip to disk.
Inside the app, overrides are created by the round-trip (**Export as Override**) and are
listed/removable in the **Data** tab.

> **Source presets are Modeled-only.** In `data/<Artist>.json` every preset uses a *modeled* amp
> (`ampMode` is implicitly `Normal`); the **NAM (Clone) version is generated automatically**. Don't
> put `"Clone"` presets in the source — if a pasted source contains any, the app skips them with a
> notice.

### 4.4 Collections

Five cross-artist compilations, each an ordered list of references `[artist, songSlug, kind]`:
*Interesting Solos* (40), *Classic Rock* (40), *A Bit of Everything* (40), *Best 50* (50) and
*Best 50 v2* (50, the same 50 interleaved by era). Editable in the **Collections** tab (reorder,
replace, add/remove, and create/delete collections). A missing reference (after a deletion) is
skipped with a warning instead of breaking the build. If you change them, they are saved to a
root-level **`collections.json`** (loaded by the Node build and written by Export ZIP); with no
`collections.json` the built-in 5 are used.

---

## 5. The generation pipeline (the computed rules)

The builder is deterministic — the same source always produces the same output. Key computed logic
(all in `pmbuild.js`):

- **Role volumes.** `presetVolume` is a flat 30 for the modeled set (level-matched to the NAM set,
  which runs at 100). Solo-vs-rhythm balance lives in AMP Vol / gates / drive, not master volume.
- **Gain-aware lead gate.** Each solo's noise-gate threshold is computed from the amp's *design*
  gain: hot rigs (≥78) → gate 22 (kill at-rest hiss); low-gain / sustained-fuzz leads (<50) → gate
  10 (keep bloom); graded 13/16/19 in between.
- **Hot-solo gain cap.** Amp gain on the fiercest solos is capped at 76 (still saturated, less
  pick-sensitive); the gate uses the pre-cap gain so the rig stays tightly gated at rest.
- **Fuzz handling.** Every fuzz preset (rhythm or solo) gets a firmer gate floor (32 solo / 28
  rhythm) and its fuzz amount capped at 56 (the dirt comes from the fuzz, not the amp).
- **Lead level.** Light AMP Vol trim (−2) and the pure +3 dB boost dropped, so leads sit at/just
  above the rhythm they cut over.
- **Tone voicings A/B/C** and the **detune/chorus doubling pair** are expanded from `_config.json`.
- **NAM conversion** (`json_nam/`): **every** modeled amp is mapped to its closest of 5 NAM captures
  (`AC30 May`, `JCM800`, `TwinCln`, `Plexi`, `SoloSLO`), everything level-maxed (Clone/IR/EQ/preset
  volume at 100; IR off for the two full-rig captures).
- **Mixed conversion** (`json_mixed/`): the **whole** preset set, but **per preset** it keeps the
  best option — the clone **only** where the modeled amp *is* (or is the same voice/lineage as) a
  capture; otherwise it keeps the tuned modeled amp. A clone resets Gain/Vol/EQ to defaults and
  leans on the capture, so for amps a capture only *approximates* the tuned model sounds closer. The
  clone whitelist (`MIXED_CLONE` in `pmbuild.js`) is: `Voks 30TB`, `Voks 30N` → AC30 · `Dark Twin`
  → TwinCln · `Brit 50JP` → Plexi · `Brit 800` → JCM800 · `Sol 100 LD`, `Sol 100 OD` → SoloSLO.
  Every other modeled amp (tweed/Bassman/Jazz-120, Ampeg, Bogner/Mesa/ENGL/Diezel/5150/Friedman,
  JTM45…) stays **modeled**. Today that splits the catalog ≈ **73 % clone / 27 % modeled**.

Outputs, all built in memory: the per-artist bundle `json/<Artist>.json`, per-song bundles,
individual presets, the 5 compilations, the mobile listing (`index.html` + `README.md`), the
detailed table (`presets_full.html` + a printable A4 `presets_print.html`), the song→Best50 map
(`map_Best50.html` + printable), and the **NAM and Mixed twins** of all of it.

### NAM captures (load these on the pedal)

The `json_nam/` (Clone-mode) presets — and the clone half of `json_mixed/` — reference **5 NAM
captures by name**. The `.nam` files are **not distributed with this project** — they are community
captures made by their individual authors on **TONE3000** (<https://www.tone3000.com>). Download one
capture per amp and load it onto the pedal's NAM slots under **exactly the name in the first column**
(any good capture of the same amp works — these are the specific ones this project was tuned against):

| Load as | Amp | Capture (TONE3000) | Loading notes |
|---|---|---|---|
| `AC30 May` | Vox AC30 Top Boost | [AC30 Top Boost](https://www.tone3000.com/tones/vox-ac30-top-boost-42210) · @josevanje | Full rig → use the "driver" model · **IR OFF** on the pedal |
| `JCM800` | Marshall JCM800 | [JCM800 2203 updated](https://www.tone3000.com/tones/marshall-jcm800-2203-updated-2534) · @jesco | Full rig → gain ≈ 6.0 (or one with an SD-1) · **IR OFF** on the pedal |
| `Plexi` | Marshall Plexi 1959 | [Plexi 1959 EL34](https://www.tone3000.com/tones/marshall-plexi-super-lead-1959-el34-40971) · @ripper | DI → "Channel I High Jumped" · keep a cab (default **BritGN 4x12**) |
| `TwinCln` | Fender Twin | [Fender '65 Twin Reverb](https://www.tone3000.com/tones/fender-65-twin-reverb-42063) · @buoliver | DI → clean · keep a cab (default **Double 2x12**) |
| `SoloSLO` | Soldano SLO-100 | [Soldano SLO100](https://www.tone3000.com/tones/soldano-slo100--5170) · @itty | DI → "SLO100" / "lead100" · keep a cab (default **Sol 4x12**) |

**Full rig vs DI:** *Full-rig* captures already include the cab, so turn the pedal's **IR/cab off**
for them; *DI* captures are amp-only, so leave a cab enabled (the pedal's default works). This matches
the generator, which auto-disables IR for the `AC30 May` and `JCM800` clones.

When asking an AI for a **`"Clone"` (NAM) preset**, its `Clone` block's `effect` must be one of
these exact names (the AI Prompt tab already includes this list).

---

## 6. Exported ZIP layout

`📦 Export ZIP` writes `PocketMasterStudio-project.zip` (~1.9 MB) with the complete tree, so a
GitHub repo shows everything browsable **and** ships the self-contained app:

```
data/_config.json, data/<Artist>.json          ← the source (human-readable)
factory_overrides.json, nam_overrides.json      ← your overrides ({} if none)
collections.json                                ← custom collections (only if you changed them)
json/…            <Artist>.json, <Artist>/…, Compilation_*.json,
                  index.html, README.md, presets_full.html, presets_print.html,
                  map_Best50.html, map_Best50_print.html
json_nam/…        the NAM (Clone) twin of json/ (same files)
json_mixed/…      the Mixed twin of json/ (same files)
README.md         this document
pocketmaster.source.json                        ← lossless project source (for Import)
PocketMasterStudio.html                         ← the app itself, with your edits embedded
```

**Import project** accepts that ZIP (it reads `pocketmaster.source.json`; if absent, it
reconstructs from `data/`), or a bare `.source.json`.

---

## 7. Repository layout & how to modify

```
PocketMasterStudio/
├── PocketMasterStudio.html   the app (open this)
├── README.md                 this document
├── data/                     SOURCE of truth — <Artist>.json + _config.json (browsable, editable)
├── factory_overrides.json    per-preset overrides for the modeled set (see §4.3); {} if none
├── nam_overrides.json        per-preset overrides for the NAM set; {} if none
├── collections.json          custom collection definitions (see §4.4); omit to use the built-in 5
├── json/ json_nam/ json_mixed/  generated preset trees + HTML listings (optional; from export_tree.js)
├── linux/                    optional BLE-MIDI receive bridge (see §9)
└── src/                      build tooling (needs Node ≥ 17, no npm install)
    ├── build_studio.js       assembles ../PocketMasterStudio.html
    ├── export_tree.js        (re)writes ../json + ../json_nam + ../json_mixed
    ├── pmbuild.js            core builder: roles, gates, caps, voicings, compilations, NAM, Mixed, library
    ├── pmhtml.js             index.html + README.md
    ├── pmtabla.js            presets_full.html + presets_print.html
    ├── pmmap.js              map_Best50.html + printable
    ├── pmmd.js               Markdown → HTML (docs)
    ├── pmedit.js             in-app editing engine (add / definitive / delete / collections)
    ├── pmzip.js              self-contained ZIP create/read (no external libs)
    ├── studio_app.js         the UI controller (tabs, editor mount, live pages, flows)
    ├── README_STUDIO.md      embedded as the app's README
    └── assets/               build inputs: mld.json, factory presets, the editor, the doc markdowns
```

**Rebuild the app:** `node src/build_studio.js` (reads `data/` + `src/assets/`, writes the HTML).
**Regenerate the loose tree:** `node src/export_tree.js`. **Add/edit an artist:** edit
`data/<Artist>.json` (or do it in the app and Save), then rebuild. **Change behaviour** (gates,
caps, page look): edit the relevant `src/*.js` module and rebuild.

The app embeds two gzip+base64 blobs: `pm-payload` (the source: data, catalog, factory presets,
overrides, collections, prompt, docs) and `pm-editor` (the PocketEdit editor with its baked library
stripped — a fresh one is injected at runtime from your current data). The main tabs live in
`studio_app.js` (`MAIN`): the editor mounts in a `blob:` iframe with a `bluetooth` Permissions-Policy
`allow`, and posts `pm-connection` / `pm-download` messages to the shell (the shell shows the
connection dot, saves downloads, and routes a preset export into **Paste JSON**).

**Note on numbers:** the `Rate` parameter is the only non-integer value in the catalog, so whole
`Rate` values keep their `.0` (handled by `stringify`); every other value is an integer.

---

## 8. Publishing to GitHub

Commit the exported tree. The self-contained `PocketMasterStudio.html` works from GitHub Pages over
`https://` (a secure context — Web Bluetooth, saving and export all work in Chromium). The loose
`json/` files are there for browsing and for importing single presets into the standalone editor.

---

## 9. Linux: reading from the pedal (optional bridge)

On Linux, Chromium can **send** MIDI to the pedal over BLE but usually can't **receive** its
notifications — so the embedded editor can't read/export presets (which the round-trip needs).
The small **`linux/ble_midi_bridge.py`** fixes that: it subscribes to the pedal's BLE
characteristic via BlueZ and forwards notifications to the editor over `ws://localhost:8765`. The
editor tries it automatically on Connect (a silent no-op on Windows/Mac/Android).

This is an optional **browser/OS Bluetooth workaround**, separate from the app — the app itself
needs nothing installed. The bridge needs Python + `pip install dbus-fast websockets` on the Linux
machine, and only matters when you want to read from the pedal on Linux. It works with the app
opened locally (`file://` or `http://localhost`); over `https://` the insecure `ws://` is blocked
as mixed content. See `linux/README_LINUX.md`.

## 10. Credits

- The embedded editor is an adapted copy of **PocketEdit** by suckyble —
  <https://github.com/suckyble/PocketEdit>.
- The Linux BLE-MIDI receive bridge (`linux/ble_midi_bridge.py`) and the Linux approach come from
  vahr76's PocketEdit fork — <https://github.com/vahr76/PocketEdit>.
- The 5 NAM amp captures come from the **TONE3000** community — <https://www.tone3000.com>. Neural
  Amp Modeler (NAM) captures are made and shared by their individual authors there; credit for each
  capture belongs to its original creator (see §5, *NAM captures*).

## 11. Disclaimer

Artist, band and song names are used **descriptively**, to indicate the sound each preset aims to
evoke. Not affiliated with, sponsored by or endorsed by any artist, band or manufacturer; all
trademarks belong to their owners. Contains **no copyrighted audio, lyrics or notation** — the
presets are original parameter settings. For personal, non-commercial use.

---

## Void's MOD — Clone/NAM Full Rig policy (authoritative)

> This is a fork-specific override of the upstream README's §5 NAM/IR advice. The original README text above is preserved for attribution and historical reference, **but the earlier suggestion to enable the Pocket Master IR for DI/amp-head NAMs is incorrect for this hardware**.

### What the pedal actually does

- With **Clone enabled**, the pedal's onboard **IR DSP is bypassed**. Its firmware UI may show an IR model and allow ON/OFF, but toggling it has **no audible effect**. It cannot add a cab to an amp-only NAM.
- Every **Clone NAM must contain the complete amp + speaker cabinet + microphone response (Full Rig / Amp + Cab)**. DI, Amp Head, preamp-only, and undocumented/unknown capture types are **not allowed** by Void's MOD. A named NAM slot is not proof of capture identity; verify the actual `.nam` installed on the pedal.
- For every generated Clone JSON, **`modules.IR.enabled = false`**, irrespective of donor state or legacy source. Native `.prst` export likewise clears IR enable bit 4. User IR selectors remain available for **Normal/Modeled** presets only.

### Current capture allowlist

| NAM label | Status | Evidence / required capture |
|---|---|---|
| `AC30 May` | **Approved Full Rig** | [VOX AC30 TOP BOOST — @josevanje](https://www.tone3000.com/tones/vox-ac30-top-boost-42210), **VOX AC30 DRIVER** model (Amp + Cab). Other models within this pack are not automatically approved. |
| `JCM800` | **Blocked — amp-head** | Upstream link [JCM800 2203 updated](https://www.tone3000.com/tones/marshall-jcm800-2203-updated-2534) is Amp Head, not a verified cab-inclusive NAM. |
| `Plexi` | **Blocked — DI** | Upstream capture explicitly states *No cab*. |
| `TwinCln` | **Blocked — amp-head** | Upstream Fender '65 Twin description specifies *head only*. |
| `SoloSLO` | **Blocked — amp-head** | Upstream Soldano SLO100 listing is Amp Head. |

The allowlist is intentionally strict. It lives in `src/void_policy.js`; a new capture must be verified as **Amp + Cab** and registered there **after** installing the correct real NAM. Merely renaming an amp-head file to `AC30 May` does not make it a Full Rig.

### How generation and export behave

1. In **NAM-safe** and **Mixed** generation, presets whose source AMP does not map to an approved Full Rig stay **Modeled / Normal**. They are **not** forcibly converted to `AC30 May` or another incompatible full rig.
2. Legacy NAM overrides pointing to a blocked DI/head capture are ignored and the original modeled preset is kept; valid Full Rig overrides have their IR forcibly disabled.
3. Direct CLI/browser `.prst` export **rejects Clone** presets pointing to unapproved NAM labels (including old generated JSON). For a valid Clone, even an old JSON saying IR ON produces a native preset with IR OFF.
4. The hardware can still display/toggle an inactive IR block in Clone mode. These programmatic constraints cannot change the firmware DSP path.
5. **`json_nam/` and `json_mixed/` files from previous commits are legacy exports**, not authoritative after this policy change. Regenerate them before using direct JSON download/CLI workflows.

### Rebuild and test in WSL

```bash
source .venv/bin/activate
node --test tests/*.cjs
node src/build_studio.js
node src/export_tree.js
```

After rebuilding, open `PocketMasterStudio.html`. The original upstream README remains above; **Void's MOD takes precedence wherever the two disagree**.

### Void's MOD v0.3.0 — persistent JSON configuration and NAM/Clone slots

The original PocketMaster Studio is labeled **v0.1 (assumed)** because the upstream repository does not specify a release version. This fork is **Void's MOD v0.3.0**. The interface shows both versions discreetly below the PocketMaster Studio title.

**HTML is an application, not a save file.** Edits to presets, source artists, collections and overrides are saved to \`config/studio_state.json\`. The five user-installed NAM slots are saved to \`config/nam_clone.json\`. The entire \`config/\` directory is ignored by Git. Changes are automatically saved while the project folder is connected: no need to re-export, rewrite or replace \`PocketMasterStudio.html\`.

To start, open the standalone HTML in **Chrome or Edge** and choose **NAM/Clone → Connect project folder**. Select the directory containing \`PocketMasterStudio.html\`; the app creates \`config/\` inside it, asks for read/write access and loads any existing state. The browser may require reconnecting after restart, especially when opened with \`file://\`. Browser security prevents silent writes to arbitrary local files; without folder permission, use **Download JSON backup** and **Import JSON**. Don't mistake a downloaded file for an automatically saved one.

The **NAM/Clone** menu provides exactly **five physical User Profile slots**. For each slot choose one of all **22 official Pocket Master modeled AMP effects** (shown by the original real-world amplifier name plus device-internal code) and type the **exact NAM profile name installed on that slot**. You must explicitly check the **Full Rig (Amp + Cab + Mic)** confirmation. Slot indices, not names, are encoded in \`.prst\` files. A file does not upload or verify the actual NAM model; the confirmation means the user has checked the capture itself.

**Clone preference is ON by default.** A generated preset uses Clone only if its modeled AMP matches an explicitly assigned/confirmed Full Rig slot. Every other amp falls back to Modeled; no generic amp-family inference or silent JCM800/AC30 substitution. Unassigned slots remain idle. Turn off "Prefer configured NAM/Clone" to force modeled generation without deleting the mapping. Clone always exports with IR **OFF**; the built-in IR DSP does not process Clone audio.

This v0.3.0 slot configuration replaces the **previous hardcoded legacy five-capture mapping and its AC30-only verified allowlist for automatic generation**. The original upstream README descriptions and the preceding Void's MOD research history remain above, but **this v0.3.0 section governs current runtime behavior**. The Full Rig attestation is user-supplied, not automatic acoustic verification.

Local export and CLI also read \`config/nam_clone.json\`, when present. \`node src/export_tree.js\` regenerates loose \`json_nam/\` and \`json_mixed/\` trees for a release (not required after each edit). \`node --test tests/*.cjs\` checks the policy, storage contract and bundle.

### Void's MOD v0.4.0 — native PRST import into the shared library

**Import .prst** is now available under **Studio → Overview → Import .prst files…**. Select one or multiple native SONICLINK files. The importer validates the known 515-byte format, CRC-8/SMBUS, effect sections, signal chain and active effect selectors. An unknown ACTIVE effect selector is retained with an explicit Unknown native model label and a decoding warning; the original file stays byte-exact and read-only instead of guessing its sound.

Imported presets appear as **PRST Imports 001**, **PRST Imports 002**, etc. inside the common Listing, Table, Editor library and Collections picker (50 presets per artist batch). The original 515-byte binary is stored byte-for-byte as Base64 inside the ignored local **config/studio_state.json**, with a stable fingerprint. Duplicate binaries are ignored. Each entry can be removed from the library or downloaded unchanged; project ZIP exports carry the imported archive.

The decoded models, modules and parameters are a **read-only view**. They are not guaranteed to represent every opaque native field, and imported presets must not be silently regenerated from that interpretation. The original binary is authoritative and is re-exported unchanged. Native Clone imports do not install NAM files: an installed NAM is resolved only when the physical slot has a confirmed Full Rig mapping. Otherwise the entry remains an unmapped archival Clone snapshot with a warning, not a newly generated Full Rig tone. New Clone generation still requires a configured Full Rig and always bypasses onboard IR.

Existing Studio save behavior is unchanged: importing presets into a connected project updates the separate JSON state, not PocketMasterStudio.html. All selected files validate before any are added, avoiding partial imports. Without folder permission, export a JSON backup and connect/import it again in Chrome/Edge.

### Void's MOD — one-click START.bat (local Chrome server)

On Windows, **double-click `START.bat`** in the project root. It locates Windows Python 3.9+ (`py -3` preferred, `python` fallback), runs `tools/studio_server.py` and opens **Google Chrome** at:

`http://127.0.0.1:8765/PocketMasterStudio.html`

Keep the terminal open while using Studio. **Ctrl+C** in that window stops the server. No internet, Node/npm or third-party Python packages are required; the server uses only the Python standard library. It binds to **127.0.0.1** (not the LAN). HTML caching is disabled, while private `config/`, `.git/` and project files are **not HTTP-accessible**.

**Config remains external.** Use **NAM/Clone → Connect project folder** and select the project root to grant file-system access. Switching from `file://` to `http://127.0.0.1:8765` creates a different browser origin, so you may need to connect the folder again once. Existing `config/*.json` files remain intact. Saving still does NOT rewrite the HTML.

If Windows Python is missing, install it from [python.org](https://www.python.org/downloads/windows/). The WSL `.venv` does not automatically make `py` available to a Windows BAT. Alternatively, from WSL:

```bash
python3 tools/studio_server.py --no-browser
```

Then paste the localhost address into **Windows Chrome** (requires working WSL localhost forwarding). The server deliberately does not silently change ports: the stable origin preserves browser file-handle permissions. If port 8765 is already occupied, close the previous server; `--port 8766` is an optional manual override with a different origin.

**One-time upgrade warning:** If a previous untracked `START.bat` shows as `?? START.bat` in Git, preserve it *before* `git pull`, e.g. `mv START.bat ../START.before_void_mod.bat` from WSL. The newly tracked launcher will then pull without an untracked-file conflict. Your old launcher remains backed up.

Run server smoke checks via `python3 -m unittest discover -s tests -p 'test_studio_server.py' -v`. Native PRST tests remain `node --test tests/*.cjs`.
