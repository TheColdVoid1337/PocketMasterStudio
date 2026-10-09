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
