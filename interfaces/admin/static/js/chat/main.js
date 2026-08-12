import { AUTH_TOKEN_KEY, AUTH_SESSION_KEY, CHAT_URL_SCOPE_KEY, showToast, openBackgroundJobsPanel, forceReloginRequested, clearAuthAndReloginFlagFromUrl, withTimeout, apiGet, apiPost, el, isChatStreaming, clearChatPageBlockers, loadMeProfile, mount, openAdminFromChat, syncAuthUserLabel, renderLogin, state, t, applyI18nStatic, LANG_KEY } from "./core.js";
import { renderChatUi } from "./ui.js";

async function syncLangFromServer() {
  try {
    const r = await apiGet("/admin/api/chat/settings/ui-lang");
    if (r && r.lang && (r.lang === "zh" || r.lang === "en")) {
      state.currentLang = r.lang;
      localStorage.setItem(LANG_KEY, state.currentLang);
    }
  } catch (_) {}
}

async function boot() {
  clearChatPageBlockers();
  applyI18nStatic();
  if (forceReloginRequested()) {
    clearAuthAndReloginFlagFromUrl();
  }
  try {
    state.authSession = JSON.parse(localStorage.getItem(AUTH_SESSION_KEY) || "null");
  } catch (_) {
    state.authSession = null;
  }
  const tok = String(localStorage.getItem(AUTH_TOKEN_KEY) || "").trim();
  if (!state.authSession || !tok) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    state.authSession = null;
    const existingLogin = document.querySelector("#app [data-chat-login='1']");
    const ae = document.activeElement;
    if (existingLogin && ae && existingLogin.contains(ae)) {
      applyI18nStatic();
      syncAuthUserLabel();
      return;
    }
    try {
      await withTimeout(apiPost("/admin/api/auth/bootstrap", {}), 2500, "auth_bootstrap_timeout");
    } catch (_) {}
    mount(await renderLogin());
    applyI18nStatic();
    syncAuthUserLabel();
    return;
  }
  try {
    await withTimeout(syncLangFromServer(), 2500, "ui_lang_timeout");
  } catch (_) {}
  try {
    await withTimeout(loadMeProfile(), 2500, "me_profile_timeout");
  } catch (_) {}
  try {
    mount(await renderChatUi());
  } catch (err) {
    mount(
      el("div", { class: "chat-app--login" }, [
        el("div", { class: "card u-modal-card" }, [
          el("div", { class: "card__title", text: t("common.error") }),
          el("div", { class: "pre", text: String(err) }),
        ]),
      ]),
    );
  }
  applyI18nStatic();
  syncAuthUserLabel();
}

state.boot = boot;

document.body.addEventListener("click", async (e) => {
  const menuBtn = e.target.closest && e.target.closest(".chat-sess-menu-item[data-menu-action]");
  if (menuBtn) {
    const action = String(menuBtn.getAttribute("data-menu-action") || "");
    document.querySelectorAll(".chat-sess-menu-pop").forEach((n) => n.remove());
    if (action === "profile") {
      openAdminFromChat("profile");
      return;
    }
    if (action === "jobs") {
      openBackgroundJobsPanel().catch((err) => showToast(`${t("chat.error")}: ${String(err)}`, { kind: "error" }));
      return;
    }
    if (action === "logout") {
      try {
        await apiPost("/admin/api/auth/logout", {});
      } catch (_) {}
      localStorage.removeItem(AUTH_TOKEN_KEY);
      localStorage.removeItem(AUTH_SESSION_KEY);
      try {
        localStorage.removeItem(CHAT_URL_SCOPE_KEY);
      } catch (_) {}
      state.authSession = null;
      await boot();
      return;
    }
    if (action === "lang") {
      state.currentLang = state.currentLang === "zh" ? "en" : "zh";
      localStorage.setItem(LANG_KEY, state.currentLang);
      try {
        await apiPost("/admin/api/chat/settings/ui-lang", { lang: state.currentLang });
      } catch (_) {}
      clearChatPageBlockers();
      if (isChatStreaming()) {
        applyI18nStatic();
        syncAuthUserLabel();
        showToast(t("chat.langSwitchedWhileStreaming"), { kind: "info", ttlMs: 6500 });
      } else {
        await boot();
      }
      return;
    }
  }
  
});

window.addEventListener("popstate", () => {
  if (state.authSession) boot().catch(() => {});
});

document.addEventListener("keydown", (ev) => {
  if (ev.key !== "Escape" || ev.defaultPrevented) return;
  if (!document.querySelector(".chat-confirm-backdrop, .chat-sess-menu-pop, .chat-img-lightbox, .chat-menu-scrim")) {
    return;
  }
  clearChatPageBlockers();
});

boot().catch((err) => {
  mount(
    el("div", { class: "chat-app--login" }, [
      el("div", { class: "card u-modal-card" }, [
        el("div", { class: "card__title", text: t("common.error") }),
        el("div", { class: "pre", text: String(err) }),
      ]),
    ]),
  );
});

