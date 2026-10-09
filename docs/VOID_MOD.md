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
