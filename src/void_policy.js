// Void's MOD — hard runtime policy for Pocket Master Clone/NAM sound.
// Clone mode bypasses built-in IR DSP on the device: never use an amp-only NAM.
// The allowlist is *specific named captures*, not a claim about generic amp labels.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PMVoidPolicy = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const FULL_RIG_CAPTURES = Object.freeze({
    "AC30 May": Object.freeze({
      origin: "VOX AC30 TOP BOOST / @josevanje",
      source: "https://www.tone3000.com/tones/vox-ac30-top-boost-42210",
      requiredModel: "VOX AC30 DRIVER",
      includesCab: true,
    }),
  });
  const isFullRig = (name) => typeof name === "string" &&
    Object.prototype.hasOwnProperty.call(FULL_RIG_CAPTURES, name);
  const assertFullRig = (name) => {
    if (!isFullRig(name)) throw new Error('Void MOD: NAM "' + String(name) +
      '" is not an approved full-rig capture. Clone bypasses onboard IR. Use a verified amp+cab NAM or keep Modeled AMP.');
    return name;
  };
  const enforceClone = (preset) => {
    if (!preset || preset.ampMode !== "Clone") return preset;
    const modules = preset.modules;
    if (!modules || !modules.Clone || modules.Clone.enabled !== true)
      throw new Error("Void MOD: Clone mode requires an active Clone block");
    assertFullRig(modules.Clone.effect);
    if (!modules.IR || typeof modules.IR !== "object")
      throw new Error("Void MOD: Clone mode requires an explicit disabled IR block");
    modules.IR.enabled = false;
    return preset;
  };
  return Object.freeze({FULL_RIG_CAPTURES,isFullRig,assertFullRig,enforceClone});
});
