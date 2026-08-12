import { state, t, el, applyI18nStatic, apiPost, authStoreSet, AUTH_TOKEN_KEY, AUTH_SESSION_KEY, navigateAdmin } from "../core.js";

async function renderLogin() {
  applyI18nStatic();
  const username = el("input", { class: "input", placeholder: t("auth.username"), value: "" });
  const userHint = el("div", { class: "muted", text: t("auth.consoleUsernameHint") });
  const password = el("input", { class: "input", type: "password", placeholder: t("auth.password") });
  const status = el("div", { class: "muted", text: "" });
  const doLogin = async () => {
    const resp = await apiPost("/admin/api/auth/login", {
      tenant_id: "",
      username: username.value.trim(),
      password: password.value.trim(),
      purpose: "console",
    });
    if (!resp.ok || !resp.token) {
      const err = String(resp.error || "");
      status.textContent = err === "user_disabled" ? t("auth.disabled") : t("auth.invalid");
      return;
    }
    const newTok = String(resp.token || "").trim();
    authStoreSet(AUTH_TOKEN_KEY, newTok);
    authStoreSet(AUTH_SESSION_KEY, JSON.stringify(resp.session || {}));
    state.authSession = resp.session || null;
    await navigateAdmin();
  };
  const onEnterLogin = (ev) => {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    doLogin();
  };
  username.addEventListener("keydown", onEnterLogin);
  password.addEventListener("keydown", onEnterLogin);
  const btn = el("button", { class: "btn btn--primary", text: t("auth.login"), onclick: doLogin });
  // Focus after mount so users can type immediately.
  setTimeout(() => {
    try {
      username.focus();
    } catch (_) {}
  }, 0);
  return el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("auth.login") }),
    el("div", { class: "row" }, [username]),
    userHint,
    el("div", { class: "row" }, [password]),
    el("div", { class: "row" }, [btn]),
    status,
  ]);
}


export { renderLogin };
