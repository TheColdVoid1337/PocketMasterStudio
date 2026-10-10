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

**Import .prst** is now available under **.prst Lab → Import .prst**. Select one or multiple native SONICLINK files. The importer validates the known 515-byte format, CRC-8/SMBUS, effect sections, signal chain and active effect selectors. An unknown ACTIVE effect selector is retained with an explicit Unknown native model label and a decoding warning; the original file stays byte-exact and read-only instead of guessing its sound.

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

### Void's MOD v0.4.1 — dedicated .prst Lab submenu

All native `.prst` interactions now live in the **`.prst Lab`** item in the main menu (desktop tabs and mobile menu). Open it and use its **Import .prst** / **Export .prst** sub-tabs:

- **Import .prst:** select multiple SONICLINK files, inspect the saved read-only snapshots, download their original 515 bytes, or remove them from the shared library. Imported presets automatically appear in the **Imported** collection, and remain available in Listing, Table and Editor. Earlier imported records are added to this collection when existing project state is loaded; existing collections are preserved. The backing PRST Imports 001/002 artist batches remain internal library sources, not inferred artist attributions.
- **Export .prst:** choose Modeled, Clone/NAM or Mixed; select artist and preset (or the whole pack as ZIP), optionally provide a genuine donor, and export native binaries with the existing validation and Full Rig safeguards.

Neither importer nor exporter is displayed on **Studio → Overview** anymore. The **NAM/Clone** menu continues to configure five physical Full Rig slots; `.prst Lab` uses that configuration without moving or duplicating it. Existing imported PRST records remain in `config/studio_state.json`; the app adds missing Imported collection references without changing native records or the save format. This is a UI reorganization; the native decoder, converter and byte-preserving archive behavior have not changed.

Older v0.4.0 text above that references `Studio → Overview → Import .prst` describes the previous interface; **the `.prst Lab` menu is now authoritative**.

### Library navigation (Void's MOD v0.4.1 follow-up)

The main navigation is now **Studio → Editor → Library → NAM/Clone → .prst Lab → Docs**. **Library** groups the existing **Overview**, **Listing**, **Table** and **Map** views under one menu. Their generators, Modeled/Clone/Mixed selectors and print modes remain unchanged. Project ZIP import/export, statistics and the Listing preview now reside under **Library → Overview**, without duplicating state.

**Studio** retains AI Prompt, Paste JSON, Data and Collections. **Data** manages artists, songs and preset variants in the editable source; **Collections** manages ordered references to existing presets. Removing a collection entry is different from deleting a source preset, so these tools remain separate. This is a navigation-only change: no migration of `config/`, no rewriting of native `.prst` data.
