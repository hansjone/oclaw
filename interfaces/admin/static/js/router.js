import {
  state, t, el, mount, setActive, applyI18nStatic, getRoute,
  authStoreRemove, AUTH_TOKEN_KEY, AUTH_SESSION_KEY, getStoredAuthToken, apiPost,
  isAuthRequiredError,
} from "./core.js";
import { hasPermission, canManageApiGrants, isAdministratorUsername } from "./pages/authz.js";
import { renderStack } from "./pages/stack.js";
import { renderScheduledJobs } from "./pages/scheduled-jobs.js";
import { renderUserManagement } from "./pages/users.js";
import { renderMemory } from "./pages/memory.js";
import { renderModels } from "./pages/models.js";
import { renderAudit } from "./pages/audit.js";
import { renderPlugins } from "./pages/plugins.js";
import { renderSkills } from "./pages/skills.js";
import { renderAttachments } from "./pages/attachments.js";
import { renderWorkspacePaths } from "./pages/workspace-paths.js";
import { renderProfile } from "./pages/profile.js";
import { renderLogin } from "./pages/login.js";

async function router() {
  const route = getRoute();
  const page = route.page;
  const tok = getStoredAuthToken();
  if (!state.authSession || !tok) {
    if (state.authSession || tok) {
      authStoreRemove(AUTH_TOKEN_KEY);
      authStoreRemove(AUTH_SESSION_KEY);
      state.authSession = null;
    }
    const existingLogin = document.querySelector("#content [data-admin-login='1']");
    const ae = document.activeElement;
    // Avoid wiping username/password while the user is typing on an already-shown login form.
    if (existingLogin && ae && existingLogin.contains(ae)) {
      return;
    }
    try {
      await apiPost("/admin/api/auth/bootstrap", {});
    } catch (_) {}
    const loginCard = await renderLogin();
    mount(loginCard);
    return;
  }
  applyI18nStatic();
  setActive(page);
  document.querySelectorAll(".nav__item").forEach((a) => {
    const p = String(a.dataset.page || "");
    if (p === "stack" && !hasPermission("admin:runtime:write")) a.style.display = "none";
    else if (p === "scheduled-jobs" && !hasPermission("admin:read")) a.style.display = "none";
    else if (p === "users" && !hasPermission("admin:user:read")) a.style.display = "none";
    else if (p === "session-monitor" && !isAdministratorUsername()) a.style.display = "none";
    else if (p === "admin-audit" && !hasPermission("admin:user:write")) a.style.display = "none";
    else if (p === "plugins" && !hasPermission("admin:user:write")) a.style.display = "none";
    else if (p === "skills" && !hasPermission("admin:read")) a.style.display = "none";
    else if (p === "attachments" && !isAdministratorUsername()) a.style.display = "none";
    else if (p === "workspace-paths" && !hasPermission("admin:user:read") && !hasPermission("admin:workspace_paths:read")) a.style.display = "none";
    else if (p === "api-grants" && !canManageApiGrants()) a.style.display = "none";
    else a.style.display = "";
  });
  const user = document.getElementById("authUser");
  if (user) {
    const name = String((state.authSession && (state.authSession.display_name || state.authSession.username || state.authSession.user_id)) || "");
    const role = String((state.authSession && state.authSession.role) || "");
    user.textContent = name ? `${name} (${role})` : "";
  }
  const forbiddenCard = () =>
    el("div", { class: "card" }, [el("div", { class: "card__title", text: t("common.forbidden") })]);
  const errorCard = (err) =>
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("common.error") }),
      el("div", { class: "pre", text: String((err && err.message) || err || "") }),
    ]);
  const mountPageLoading = (titleKey) => {
    mount(
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t(titleKey) }),
        el("div", { class: "muted", text: t("chat.loading") }),
      ]),
    );
  };
  /** Let the browser paint the loading card before heavy page fetches/DOM work. */
  const yieldForPaint = () =>
    new Promise((resolve) => {
      requestAnimationFrame(() => resolve());
    });
  let view;
  try {
    if (page === "stack") {
      mountPageLoading("title.stack");
      await yieldForPaint();
      view = await renderStack();
    } else if (page === "scheduled-jobs") {
      view = hasPermission("admin:read") ? await renderScheduledJobs() : forbiddenCard();
    } else if (page === "users") {
      view = hasPermission("admin:user:read") ? await renderUserManagement() : forbiddenCard();
    } else if (page === "memory") view = await renderMemory();
    else if (page === "models") view = await renderModels();
    else if (page === "api-grants" || page === "session-monitor" || page === "admin-audit") {
      view = el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("common.notFound") }),
        el("div", { class: "muted", text: t("common.pageRemoved") }),
      ]);
    } else if (page === "audit") view = await renderAudit(route.params.get("session_id") || "");
    else if (page === "plugins") {
      if (!hasPermission("admin:user:write")) {
        view = forbiddenCard();
      } else {
        mountPageLoading("title.plugins");
        await yieldForPaint();
        view = await renderPlugins();
      }
    } else if (page === "skills") {
      if (!hasPermission("admin:read")) {
        view = forbiddenCard();
      } else {
        mountPageLoading("title.skills");
        await yieldForPaint();
        view = await renderSkills();
      }
    } else if (page === "attachments") {
      view = isAdministratorUsername() ? await renderAttachments() : forbiddenCard();
    } else if (page === "workspace-paths") {
      view =
        hasPermission("admin:user:read") || hasPermission("admin:workspace_paths:read")
          ? await renderWorkspacePaths()
          : forbiddenCard();
    } else if (page === "profile") {
      view = await renderProfile();
    } else view = el("div", { class: "card" }, [el("div", { class: "card__title", text: t("common.notFound") })]);
  } catch (err) {
    // Re-auth already scheduled; do not paint an error over the login redirect.
    if (isAuthRequiredError(err)) return;
    view = errorCard(err);
  }
  if (view) mount(view);
}


export { router };
