/* Admin + standalone /chat: restore palette from localStorage before first paint. */
(function () {
  const STORAGE_KEY = "oclaw_admin_theme";
  const DEFAULT_THEME = "netx";
  const THEMES = ["netx", "deepseek", "github", "nord", "dracula", "forest", "catppuccin", "light"];
  const LEGIT = new Set(THEMES);

  function applyAdminTheme(theme) {
    const t = theme && LEGIT.has(theme) ? theme : DEFAULT_THEME;
    if (t === "deepseek") document.body.removeAttribute("data-admin-theme");
    else document.body.setAttribute("data-admin-theme", t);
  }

  function initAdminThemeFromStorage() {
    let raw = DEFAULT_THEME;
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      // Missing key → netx. Existing deepseek/github/… prefs are preserved.
      raw = stored == null || stored === "" ? DEFAULT_THEME : stored;
    } catch (_) {
      raw = DEFAULT_THEME;
    }
    if (!LEGIT.has(raw)) raw = DEFAULT_THEME;
    applyAdminTheme(raw);
    return raw;
  }

  function persistAdminTheme(theme) {
    const t = theme && LEGIT.has(theme) ? theme : DEFAULT_THEME;
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch (_) {}
    applyAdminTheme(t);
  }

  function currentAdminTheme() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      if (v == null || v === "") return DEFAULT_THEME;
      return LEGIT.has(v) ? v : DEFAULT_THEME;
    } catch (_) {
      return DEFAULT_THEME;
    }
  }

  window.OclawAdminTheme = {
    STORAGE_KEY,
    DEFAULT_THEME,
    THEMES,
    applyAdminTheme,
    initAdminThemeFromStorage,
    persistAdminTheme,
    currentAdminTheme,
  };
  initAdminThemeFromStorage();
})();
