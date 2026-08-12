import { state, t, el, mount, toggleLang, applyI18nStatic, resolveChatUrl, apiPost, authStoreGet, authStoreSet, authStoreRemove, AUTH_TOKEN_KEY, AUTH_SESSION_KEY } from "./core.js";
import { router } from "./router.js";

state.navigate = router;
state.reauthHandler = () => router().catch(() => {});
applyI18nStatic();

window.addEventListener("hashchange", router);
const btnRefreshEl = document.getElementById("btnRefresh");
if (btnRefreshEl) btnRefreshEl.addEventListener("click", router);
const btnLangEl = document.getElementById("btnLang");
if (btnLangEl) btnLangEl.addEventListener("click", () => {
  toggleLang();
  router();
});
const adminThemeSelectEl = document.getElementById("adminThemeSelect");
if (adminThemeSelectEl && window.OclawAdminTheme) {
  adminThemeSelectEl.addEventListener("change", () => {
    try {
      window.OclawAdminTheme.persistAdminTheme(adminThemeSelectEl.value);
    } catch (_) {}
  });
}
const btnBackChatEl = document.getElementById("btnBackChat");
if (btnBackChatEl) {
  try {
    btnBackChatEl.setAttribute("href", resolveChatUrl());
  } catch (_) {}
  btnBackChatEl.addEventListener("click", (ev) => {
    // Keep SPA behavior explicit, while href remains fallback if JS fails earlier.
    ev.preventDefault();
    window.location.assign(resolveChatUrl());
  });
}
const btnLogoutEl = document.getElementById("btnLogout");
if (btnLogoutEl) btnLogoutEl.addEventListener("click", async () => {
  try {
    await apiPost("/admin/api/auth/logout", {});
  } catch (_) {}
  authStoreRemove(AUTH_TOKEN_KEY);
  authStoreRemove(AUTH_SESSION_KEY);
  state.authSession = null;
  await router();
});
try {
  state.authSession = JSON.parse(authStoreGet(AUTH_SESSION_KEY) || "null");
} catch (_) {
  state.authSession = null;
}
router().catch((err) => {
  mount(el("div", { class: "card" }, [el("div", { class: "card__title", text: t("common.error") }), el("div", { class: "pre", text: String(err) })]));
});


