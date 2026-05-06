/* Admin + standalone /chat: restore palette from localStorage before first paint. */
(function () {
  const STORAGE_KEY = "oclaw_admin_theme";
  const THEMES = ["deepseek", "github", "nord", "dracula", "forest", "catppuccin", "light"];
  const LEGIT = new Set(THEMES);

  function applyAdminTheme(theme) {
    const t = theme && LEGIT.has(theme) ? theme : "deepseek";
    if (t === "deepseek") document.body.removeAttribute("data-admin-theme");
    else document.body.setAttribute("data-admin-theme", t);
  }

  function initAdminThemeFromStorage() {
    let raw = "deepseek";
    try {
      raw = localStorage.getItem(STORAGE_KEY) || "deepseek";
    } catch (_) {
      raw = "deepseek";
    }
    if (!LEGIT.has(raw)) raw = "deepseek";
    applyAdminTheme(raw);
    return raw;
  }

  function persistAdminTheme(theme) {
    const t = theme && LEGIT.has(theme) ? theme : "deepseek";
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch (_) {}
    applyAdminTheme(t);
  }

  function currentAdminTheme() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      return v && LEGIT.has(v) ? v : "deepseek";
    } catch (_) {
      return "deepseek";
    }
  }

  window.OclawAdminTheme = {
    STORAGE_KEY,
    THEMES,
    applyAdminTheme,
    initAdminThemeFromStorage,
    persistAdminTheme,
    currentAdminTheme,
  };
  initAdminThemeFromStorage();
})();
