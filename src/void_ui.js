// Void's MOD — browser-only UX preferences, startup notices and connection status.
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.PMVoidUI = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  const KEY = "pm-void-ui-v1";
  const defaults = Object.freeze({ browserNotice: true, folderNotice: true, compactLists: true });
  function readPrefs(storage) {
    let saved = {};
    try { saved = JSON.parse(storage?.getItem(KEY) || "{}") || {}; } catch (_) {}
    return Object.fromEntries(Object.entries(defaults).map(([key, value]) =>
      [key, typeof saved[key] === "boolean" ? saved[key] : value]));
  }
  let prefs = null, handlers = null, queue = [], active = null;
  const $ = (id) => document.getElementById(id);
  const io = () => window.PMVoidConfigIO;
  const store = () => {
    try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (_) {}
    document.documentElement.dataset.density = prefs.compactLists ? "compact" : "comfortable";
  };
  const webServer = () => /^https?:$/.test(location.protocol);
  const browserReady = () => !!(io()?.available() && ("bluetooth" in navigator) &&
    typeof DecompressionStream !== "undefined" && typeof CompressionStream !== "undefined");
  function refresh() {
    if (typeof document === "undefined") return;
    const status = (id, good, label, explanation) => {
      const node = $(id); if (!node) return;
      node.dataset.state = good ? "good" : "bad";
      node.setAttribute("aria-label", label + ". " + explanation);
      node.title = explanation;
      const text = node.querySelector(".status-text");
      if (text) text.textContent = label;
    };
    status("statusServer", webServer(), webServer() ? "Server ONLINE" : "Server OFFLINE",
      webServer() ? "This page loaded over HTTP(S); not a continuous server heartbeat." :
        "Opened as a local file rather than from the Studio HTTP server.");
    const connected = !!io()?.connected();
    status("statusFolder", connected, connected ? "Folder Connected" : "Folder Disconnected",
      connected ? "Folder: " + io().location() :
        "Connect the project folder to persist config/*.json without rewriting the HTML.");
    status("statusBrowser", browserReady(), browserReady() ? "Compatible Browser" : "Browser Limited",
      browserReady() ? "Web Bluetooth, File System Access and compression APIs detected." :
        "Required features missing; Chrome/Edge on localhost is recommended.");
    if ($("settingsFolderStatus"))
      $("settingsFolderStatus").textContent = connected ? "Connected: " + io().location() :
        "Not connected. Choose the project root (the folder containing config/).";
  }
  function syncControls() {
    for (const [id, prop] of [["settingBrowserNotice","browserNotice"],
      ["settingFolderNotice","folderNotice"],["settingCompactLists","compactLists"]]) {
      const field = $(id); if (field) field.checked = prefs[prop];
    }
  }
  function display(kind) {
    const dialog = $("startupDialog");
    if (!dialog) return;
    active = kind;
    $("startupOptOut").checked = false;
    $("startupError").textContent = "";
    const browser = kind === "browser";
    $("startupTitle").textContent = browser ? "Browser requirements" : "Project folder not connected";
    $("startupBody").textContent = browser
      ? "To connect the pedal through Editor and save project files you need a compatible Chromium browser (Chrome, Edge or Opera). Web Bluetooth and File System Access are required; Safari and Firefox do not support the complete workflow. Open the Studio from the local server for reliable permissions."
      : "Select your PocketMasterStudio project folder to read and write config/studio_state.json and config/nam_clone.json. Your standalone HTML remains unchanged. Until you connect, you can download backups, but unsaved edits are not persisted.";
    $("startupOptOutLabel").textContent = browser ? "Do not show browser information on startup" :
      "Do not remind me when the folder is disconnected";
    $("startupConnect").hidden = browser || !io()?.available();
    dialog.hidden = false;
    $("startupDismiss").focus();
  }
  function next() { const kind = queue.shift(); if (kind) display(kind); }
  function close() {
    if (active && $("startupOptOut").checked) {
      prefs[active === "browser" ? "browserNotice" : "folderNotice"] = false;
      store(); syncControls();
    }
    $("startupDialog").hidden = true;
    active = null;
    next();
  }
  async function connectFromUI() {
    try {
      await handlers.onConnect(); // invoked directly from an actual button click
      refresh();
      if (io()?.connected() && active === "folder") close();
    } catch (e) {
      if (e?.name === "AbortError") return;
      if ($("startupDialog") && !$("startupDialog").hidden)
        $("startupError").textContent = e?.message || String(e);
      else alert(e?.message || String(e));
    }
  }
  function start(options) {
    handlers = options;
    prefs = readPrefs(typeof localStorage === "undefined" ? null : localStorage);
    store();
    $("startupDismiss").addEventListener("click", close);
    $("startupConnect").addEventListener("click", connectFromUI);
    document.querySelectorAll(".status-chip").forEach(node => node.addEventListener("click", handlers.onSettings));
    refresh();
    queue = [];
    if (prefs.browserNotice) queue.push("browser");
    if (prefs.folderNotice && !io()?.connected()) queue.push("folder");
    next();
  }
  function mountSettings(view) {
    view.innerHTML = [
      '<div class="wrap settings-wrap"><h2>Settings</h2>',
      '<p class="mut">UI preferences are stored in this browser. They do not change your project configuration or original .prst files.</p>',
      '<section class="settings-card"><h3>Startup information</h3>',
      '<label class="setting-line"><input id="settingBrowserNotice" type="checkbox"> Show browser requirements on launch</label>',
      '<label class="setting-line"><input id="settingFolderNotice" type="checkbox"> Remind me when the project folder is disconnected</label>',
      '<div class="settings-actions"><button class="mini" type="button" id="settingsShowBrowser">Browser information…</button>',
      '<button class="mini" type="button" id="settingsShowFolder">Folder information…</button></div></section>',
      '<section class="settings-card"><h3>Display</h3>',
      '<label class="setting-line"><input id="settingCompactLists" type="checkbox"> Compact, readable lists</label></section>',
      '<section class="settings-card"><h3>Folder connection</h3><p class="mut" id="settingsFolderStatus"></p>',
      '<div class="settings-actions"><button class="primary" type="button" id="settingsConnect">Connect project folder…</button>',
      '<button type="button" id="settingsSave">Save config</button></div></section></div>'
    ].join("");
    syncControls(); refresh();
    for (const [id, prop] of [["settingBrowserNotice","browserNotice"],
      ["settingFolderNotice","folderNotice"],["settingCompactLists","compactLists"]]) {
      $(id).addEventListener("change", (e) => { prefs[prop] = e.target.checked; store(); });
    }
    $("settingsShowBrowser").addEventListener("click", () => { queue = []; display("browser"); });
    $("settingsShowFolder").addEventListener("click", () => { queue = []; display("folder"); });
    $("settingsConnect").addEventListener("click", connectFromUI);
    $("settingsSave").addEventListener("click", async () => {
      try { await handlers.onSave(); refresh(); }
      catch(e) { if (e?.name !== "AbortError") alert(e?.message || String(e)); }
    });
  }
  return Object.freeze({ readPrefs, start, refresh, mountSettings, KEY });
});
