import { state } from "./state.js";
import { t, tf, applyI18nStatic, toggleLang } from "./i18n/index.js";

const SESSION_MONITOR_ROLE_FILTER_KEY = "ops_session_monitor_role_filter";
const AUTH_TOKEN_KEY = "ops_admin_token";
const AUTH_SESSION_KEY = "ops_admin_session";
const CHAT_MEMORY_MODE_KEY = "ops_chat_memory_mode";
/** 与 localStorage 不同：sessionStorage 按标签页隔离，避免「管理员页 + 普通用户控制台」互相覆盖 token。 */
function authStoreGet(key) {
  try {
    return sessionStorage.getItem(key);
  } catch (_) {
    return null;
  }
}
function authStoreSet(key, value) {
  try {
    sessionStorage.setItem(key, value);
  } catch (_) {}
}
function authStoreRemove(key) {
  try {
    sessionStorage.removeItem(key);
  } catch (_) {}
}
/** 历史版本把 token 放在 localStorage，多标签会串号；启动时清掉以免误读。 */
try {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_SESSION_KEY);
} catch (_) {}
/**
 * /chat 与 /admin 历史上使用不同 key；当用户在同一窗口从 /chat 跳到 /admin 时，
 * 没有 opener 可用，需要从 chat 存储主动迁移一次以复用登录态。
 */
(function seedAdminAuthFromChatStorageIfNeeded() {
  try {
    if (authStoreGet(AUTH_TOKEN_KEY)) return;
    const pairs = [
      [sessionStorage, "ops_chat_token", "ops_chat_session"],
      [localStorage, "ops_chat_token", "ops_chat_session"],
    ];
    for (const [store, kTok, kSess] of pairs) {
      let tok = null;
      let sess = null;
      try {
        tok = store.getItem(kTok);
        sess = store.getItem(kSess);
      } catch (_) {
        continue;
      }
      const t = String(tok || "").trim();
      const s = String(sess || "").trim();
      if (t && s) {
        authStoreSet(AUTH_TOKEN_KEY, t);
        authStoreSet(AUTH_SESSION_KEY, s);
        break;
      }
    }
  } catch (_) {}
})();
/** 从聊天页新开 /admin（审计、设置等）时，复用 opener 同一登录态（chat 或 admin token）。勿对 window.open 使用 noopener，否则读不到 opener。 */
(function seedAdminAuthFromOpenerIfNeeded() {
  try {
    if (authStoreGet(AUTH_TOKEN_KEY)) return;
    const op = window.opener;
    if (!op || op === window) return;
    if (String(location.origin) !== String(op.location.origin)) return;
    const pairs = [
      ["ops_admin_token", "ops_admin_session"],
      ["ops_chat_token", "ops_chat_session"],
    ];
    for (const [kTok, kSess] of pairs) {
      let tok = null;
      let sess = null;
      try {
        tok = op.sessionStorage.getItem(kTok) || op.localStorage.getItem(kTok);
        sess = op.sessionStorage.getItem(kSess) || op.localStorage.getItem(kSess);
      } catch (_) {
        continue;
      }
      const t = String(tok || "").trim();
      const s = String(sess || "").trim();
      if (t && s) {
        authStoreSet(AUTH_TOKEN_KEY, t);
        authStoreSet(AUTH_SESSION_KEY, s);
        break;
      }
    }
  } catch (_) {}
})();
/** 合并展示名与登录名（列表/团队页共用） */
function formatUserLabel(u) {
  const un = String(u.username ?? "").trim();
  const dn = String(u.display_name ?? "").trim();
  if (dn && un && dn.toLowerCase() !== un.toLowerCase()) {
    return `${dn} (${un})`;
  }
  return dn || un || "—";
}

function formatAuditActor(r) {
  const un = String(r.actor_username ?? "").trim();
  const dn = String(r.actor_display_name ?? "").trim();
  const id = String(r.actor_user_id ?? "").trim();
  if (dn && un && dn.toLowerCase() !== un.toLowerCase()) {
    return `${dn} (${un})`;
  }
  if (dn || un) return dn || un;
  return id ? id.slice(0, 8) + (id.length > 8 ? "…" : "") : "—";
}

function getRoute() {
  const raw = (location.hash || "#/stack").replace(/^#\//, "");
  const [pageRaw, queryRaw] = raw.split("?", 2);
  let page = (pageRaw || "stack").trim();
  if (page === "channels") page = "stack";
  if (page === "tenants") page = "users";
  const params = new URLSearchParams(queryRaw || "");
  return { page, params };
}

/** 当控制台挂在子路径（如 /gw/admin）时，把 /admin/api/... 解析为 /gw/admin/api/... */
function resolveAdminApiUrl(path) {
  const p = String(path || "");
  if (!p.startsWith("/admin/")) return p;
  const pathname = (location.pathname || "").replace(/\/+$/, "") || "/";
  const marker = "/admin";
  const pos = pathname.lastIndexOf(marker);
  if (pos <= 0) return p;
  return pathname.slice(0, pos) + p;
}

function resolveChatUrl() {
  const pathname = (location.pathname || "").replace(/\/+$/, "") || "/";
  const marker = "/admin";
  if (pathname.endsWith(marker)) {
    return `${pathname.slice(0, -marker.length) || ""}/chat`;
  }
  return "/chat";
}

function getStoredAuthToken() {
  return String(authStoreGet(AUTH_TOKEN_KEY) || "").trim();
}

/** 会话在服务端失效或本地缺 token 时清理，并下一帧回到登录（避免在 router 内部 await router 盖住登录页） */
let _reauthTimer = null;
function scheduleReauthAfter401(requestUrl) {
  const u = String(requestUrl || "");
  if (u.includes("/admin/api/auth/login") || u.includes("/admin/api/auth/bootstrap")) return;
  authStoreRemove(AUTH_TOKEN_KEY);
  authStoreRemove(AUTH_SESSION_KEY);
  state.authSession = null;
  // Coalesce: many parallel 401s must not remount login repeatedly (wipes username while typing).
  if (_reauthTimer != null) return;
  _reauthTimer = setTimeout(() => {
    _reauthTimer = null;
    const fn = state.reauthHandler;
    if (typeof fn === "function") fn();
  }, 0);
}

function isAuthRequiredError(err) {
  return !!(err && (err.authRequired === true || err.name === "AuthRequiredError"));
}

function _authRequiredError() {
  const err = new Error("auth_required");
  err.name = "AuthRequiredError";
  err.authRequired = true;
  return err;
}

function _haltAfter401() {
  // 401 means "login required". Re-auth is already scheduled; reject so page boots
  // (Promise.all / await) do not hang forever on a never-resolving promise.
  return Promise.reject(_authRequiredError());
}

async function apiGet(path) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { "accept": "application/json" };
  if (token) headers["authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { headers });
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
  return await res.json();
}

async function apiGetOptional(path) {
  try {
    return await apiGet(path);
  } catch (err) {
    console.warn(`apiGetOptional failed path=${String(path || "")} err=${String(err)}`);
    return null;
  }
}

async function apiGetNoHang(path) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { "accept": "application/json" };
  if (token) headers["authorization"] = `Bearer ${token}`;
  const res = await fetch(url, { headers });
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    // Returning null avoids Promise.all / await from hanging forever.
    return null;
  }
  if (!res.ok) throw new Error(`GET ${url} ${res.status}`);
  return await res.json();
}

async function apiPost(path, body) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { "content-type": "application/json", "accept": "application/json" };
  if (token) headers["authorization"] = `Bearer ${token}`;
  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body ?? {}),
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_) {
    data = null;
  }
  if (res.status === 401) {
    const isAuthEndpoint =
      url.includes("/admin/api/auth/login") || url.includes("/admin/api/auth/bootstrap");
    // Login/bootstrap must never hang on the never-resolving 401 sentinel.
    if (isAuthEndpoint) {
      return data && typeof data === "object" ? data : { ok: false, error: "unauthorized" };
    }
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) {
    const d = data && typeof data === "object" ? data : {};
    const detail = (d).detail != null ? String((d).detail) : "";
    const errKey = (d).error != null ? String((d).error) : "";
    const msg = detail || errKey || `POST ${url} ${res.status}`;
    throw new Error(msg);
  }
  return data ?? {};
}

/** Skills endpoints often return HTTP 200 with `{ ok: false, result: {...} }` on failure — treat as error for UX. */
function assertSkillMutationOk(r, fallbackMessage) {
  if (!r || r.ok !== false) return;
  const res = r.result && typeof r.result === "object" ? r.result : {};
  const code = res.error_code != null ? String(res.error_code).trim() : "";
  const detail = res.detail != null ? String(res.detail).trim() : "";
  const msg = [code, detail].filter(Boolean).join(": ") || String(fallbackMessage || "skill operation failed");
  throw new Error(msg);
}

async function apiRequest(method, path, body) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { "accept": "application/json" };
  if (token) headers["authorization"] = `Bearer ${token}`;
  if (body !== undefined && method !== "GET" && method !== "HEAD") {
    headers["content-type"] = "application/json";
  }
  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined && method !== "GET" && method !== "HEAD" ? JSON.stringify(body ?? {}) : undefined,
  });
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) {
    let msg = `${method} ${url} ${res.status}`;
    try {
      const j = await res.json();
      if (j && j.detail !== undefined) {
        msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      }
    } catch (_) {}
    throw new Error(msg);
  }
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) return {};
  return await res.json();
}

async function apiPostFormData(path, formData) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = {};
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(url, { method: "POST", headers, body: formData });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_) {
    data = null;
  }
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) {
    const d = data && typeof data === "object" ? data : {};
    const detail = d.detail != null ? String(d.detail) : "";
    const errKey = d.error != null ? String(d.error) : "";
    throw new Error(detail || errKey || `POST ${url} ${res.status}`);
  }
  return data ?? {};
}

async function apiDeleteJson(path) {
  const url = resolveAdminApiUrl(path);
  const token = getStoredAuthToken();
  const headers = { accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(url, { method: "DELETE", headers });
  if (res.status === 401) {
    scheduleReauthAfter401(url);
    return await _haltAfter401();
  }
  if (!res.ok) {
    let msg = `DELETE ${url} ${res.status}`;
    try {
      const j = await res.json();
      if (j && j.detail !== undefined) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (_) {}
    throw new Error(msg);
  }
  try {
    return await res.json();
  } catch (_) {
    return {};
  }
}

function _activeCopyCell() {
  return document.querySelector(".cell-copyable.cell-selected");
}

function _selectCopyCell(cell) {
  const prev = _activeCopyCell();
  if (prev && prev !== cell) prev.classList.remove("cell-selected");
  if (cell) cell.classList.add("cell-selected");
}

function _shouldIgnoreCopyShortcut(ev) {
  const t = ev && ev.target ? ev.target : null;
  if (!t || !(t instanceof HTMLElement)) return false;
  const tag = String(t.tagName || "").toLowerCase();
  if (t.isContentEditable) return true;
  return tag === "input" || tag === "textarea" || tag === "select";
}

function _installCellCopyKeyboardShortcut() {
  if (window.__adminCellCopyShortcutInstalled) return;
  window.__adminCellCopyShortcutInstalled = true;
  document.addEventListener("keydown", async (ev) => {
    if (_shouldIgnoreCopyShortcut(ev)) return;
    if (!(ev.ctrlKey || ev.metaKey) || String(ev.key || "").toLowerCase() !== "c") return;
    const active = _activeCopyCell();
    if (!active) return;
    try {
      const txt = String(active.getAttribute("data-copy-text") || active.getAttribute("title") || active.textContent || "");
      if (!txt.trim()) return;
      ev.preventDefault();
      await navigator.clipboard.writeText(txt);
      active.classList.add("cell-copied");
      setTimeout(() => active.classList.remove("cell-copied"), 2600);
    } catch (_) {
      // no-op
    }
  });
}

function attachCellCopyBehavior(cell, getCopyText) {
  if (!cell || cell.dataset.copyBound === "1") return;
  _installCellCopyKeyboardShortcut();
  cell.dataset.copyBound = "1";
  cell.classList.add("cell-copyable");
  cell.addEventListener("click", () => {
    _selectCopyCell(cell);
  });
  cell.addEventListener("dblclick", async () => {
    try {
      const txt = String(typeof getCopyText === "function" ? getCopyText() : (cell.textContent || ""));
      if (!txt) return;
      cell.setAttribute("data-copy-text", txt);
      await navigator.clipboard.writeText(txt);
      cell.classList.add("cell-copied");
      setTimeout(() => cell.classList.remove("cell-copied"), 2600);
    } catch (_) {
      // keep tooltip fallback when clipboard API unavailable
    }
  });
}

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === undefined || v === null) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else if (k === "disabled" && v === false) {
      e.removeAttribute("disabled");
    } else e.setAttribute(k, v);
  }
  for (const c of children) e.appendChild(c);
  if (String(tag || "").toLowerCase() === "td" && String(e.getAttribute("data-copy-disabled") || "") !== "1") {
    const txt = String(e.textContent || "").trim();
    if (txt) {
      if (!e.getAttribute("title")) e.setAttribute("title", txt);
      attachCellCopyBehavior(e, () => String(e.getAttribute("title") || e.textContent || ""));
    }
  }
  return e;
}

function tdCell(value, maxLen = 120) {
  const full = String(value ?? "");
  const shown = formatSystemLocalDateTime(full);
  const title = shown === full ? full : `${shown}\n${full}`;
  const td = el("td", { text: shortText(shown, maxLen), title });
  td.setAttribute("data-copy-text", shown);
  attachCellCopyBehavior(td, () => shown);
  return td;
}

function enableTableColumnResize(tableEl, columnIndexes = []) {
  if (!tableEl) return;
  const heads = Array.from(tableEl.querySelectorAll("thead th"));
  if (!heads.length) return;
  tableEl.classList.add("table--resizable");
  heads.forEach((th) => th.querySelectorAll(".table-col-resizer").forEach((x) => x.remove()));
  const enabled = new Set(Array.isArray(columnIndexes) ? columnIndexes : []);
  heads.forEach((th, idx) => {
    if (enabled.size && !enabled.has(idx)) return;
    const handle = document.createElement("span");
    handle.className = "table-col-resizer";
    handle.addEventListener("mousedown", (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const startX = ev.clientX;
      const startW = th.getBoundingClientRect().width;
      document.body.classList.add("col-resize-active");
      const onMove = (mv) => {
        const next = Math.max(72, Math.round(startW + (mv.clientX - startX)));
        th.style.width = `${next}px`;
      };
      const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.body.classList.remove("col-resize-active");
      };
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
    th.appendChild(handle);
  });
}

function setActive(page) {
  document.querySelectorAll(".nav__item").forEach((a) => {
    a.classList.toggle("nav__item--active", a.dataset.page === page);
  });
  document.getElementById("topTitle").textContent = ({
    stack: t("title.stack"),
    "scheduled-jobs": t("title.scheduledJobs"),
    users: t("title.users"),
    memory: t("title.memory"),
    models: t("title.models"),
    "api-grants": t("title.apiGrants"),
    audit: t("title.audit"),
    "session-monitor": t("title.sessionMonitor"),
    "admin-audit": t("title.adminAudit"),
    plugins: t("title.plugins"),
    skills: t("title.skills"),
    attachments: t("title.attachments"),
    "workspace-paths": t("title.workspacePaths"),
    profile: t("title.profile"),
  }[page] || page);
}

function mount(node) {
  const c = document.getElementById("content");
  c.innerHTML = "";
  c.appendChild(node);
}

function renderPageShell(opts = {}, children = []) {
  const title = String(opts.title || "").trim();
  const subtitle = String(opts.subtitle || "").trim();
  const actions = Array.isArray(opts.actions) ? opts.actions.filter(Boolean) : [];
  const sections = Array.isArray(opts.sections) ? opts.sections.filter((x) => x && x.id && x.label) : [];
  const head = [];
  if (title || subtitle || actions.length) {
    const left = [];
    if (title) left.push(el("h1", { class: "page-shell__title", text: title }));
    if (subtitle) left.push(el("div", { class: "page-shell__subtitle muted", text: subtitle }));
    head.push(
      el("div", { class: "page-shell__header" }, [
        el("div", { class: "page-shell__headline" }, left),
        el("div", { class: "page-shell__actions row" }, actions),
      ]),
    );
    if (sections.length > 1) {
      head.push(
        el(
          "div",
          { class: "page-shell__toc", role: "navigation", "aria-label": "page sections" },
          sections.map((s) =>
            el("button", {
              class: "page-shell__tocItem",
              type: "button",
              text: String(s.label),
              onclick: () => {
                const target = document.getElementById(String(s.id));
                if (!target) return;
                target.scrollIntoView({ behavior: "smooth", block: "start" });
              },
            }),
          ),
        ),
      );
    }
  }
  return el("section", { class: "page-shell" }, [...head, ...children.filter(Boolean)]);
}

function renderSectionCard(title, subtitle, bodyNodes = [], opts = {}) {
  const headlineKids = [el("div", { class: "card__title", text: title })];
  if (subtitle) headlineKids.push(el("div", { class: "card__subtitle muted", text: subtitle }));
  const headKids = [el("div", { class: "card__headline" }, headlineKids)];
  if (Array.isArray(opts.actions) && opts.actions.length) {
    headKids.push(el("div", { class: "card__actions row" }, opts.actions));
  }
  const nodes = [el("div", { class: "card__head" }, headKids)];
  bodyNodes.filter(Boolean).forEach((node) => nodes.push(node));
  const attrs = { class: "card section-card" };
  if (opts.id) attrs.id = String(opts.id);
  return el("div", attrs, nodes);
}

function renderMetaChips(entries) {
  const items = [];
  const src = entries && typeof entries === "object" ? entries : {};
  Object.keys(src).forEach((k) => {
    const v = src[k];
    if (v == null || v === "") return;
    items.push(el("span", { class: "meta-chip", text: `${k}=${v}` }));
  });
  return el("div", { class: "meta-line" }, items.length ? items : [el("span", { class: "muted", text: "—" })]);
}

function shortText(v, maxLen = 200) {
  const s = String(v ?? "");
  if (s.length <= maxLen) return s;
  return s.slice(0, Math.max(0, maxLen - 3)) + "...";
}

function formatSystemLocalDateTime(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  // Keep non-datetime strings unchanged.
  if (!/^\d{4}-\d{2}-\d{2}T/.test(raw)) return raw;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  const locale = state.currentLang === "zh" ? "zh-CN" : "en-US";
  try {
    return d.toLocaleString(locale, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch (_) {
    return raw;
  }
}

function formatIds(v) {
  if (!Array.isArray(v)) return "";
  const vals = v.map((x) => String(x ?? "").trim()).filter(Boolean);
  if (!vals.length) return "";
  if (vals.length > 4) return vals.slice(0, 4).join(", ") + ` (+${vals.length - 4})`;
  return vals.join(", ");
}

function yesNo(v) {
  return v ? "yes" : "no";
}

let runtimePrewarmReminder = "";
function markPrewarmReminder(reason) {
  const why = String(reason || "").trim();
  const base = t("stack.configChangedPrewarm");
  runtimePrewarmReminder = why ? `${base} [${why}]` : base;
}

/**
 * Compact row action menu (button + fixed popover).
 * Must NOT use nested &lt;details&gt; inside plugins-fold details — clicks get swallowed.
 * items: [{ label, onClick, danger?, disabled? }]
 */
function rowActions(label, items) {
  let menuEl = null;
  let onDoc = null;
  const close = () => {
    if (onDoc) {
      document.removeEventListener("click", onDoc, true);
      onDoc = null;
    }
    if (menuEl && menuEl.parentNode) menuEl.parentNode.removeChild(menuEl);
    menuEl = null;
  };
  const btn = el("button", {
    class: "chat-sess-more row-actions__btn",
    type: "button",
    text: String(label || "⋯"),
    title: "actions",
    "aria-label": "actions",
    onclick: (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      if (menuEl) {
        close();
        try {
          btn.blur();
        } catch (_) {}
        return;
      }
      const menu = el("div", { class: "chat-sess-menu-pop row-actions__menu u-overlay-fixed" });
      menu.style.visibility = "hidden";
      (Array.isArray(items) ? items : []).forEach((it) => {
        if (!it || !it.label) return;
        menu.appendChild(
          el("button", {
            class: "chat-sess-menu-item" + (it.danger ? " row-actions__item--danger" : ""),
            type: "button",
            text: String(it.label),
            disabled: !!it.disabled,
            onclick: async (e2) => {
              e2.preventDefault();
              e2.stopPropagation();
              close();
              try {
                btn.blur();
              } catch (_) {}
              if (typeof it.onClick !== "function") return;
              try {
                await it.onClick();
              } catch (err) {
                console.warn("row action failed", err);
                window.alert(String((err && err.message) || err || "action failed"));
              }
            },
          }),
        );
      });
      document.body.appendChild(menu);
      const rect = ev.currentTarget.getBoundingClientRect();
      const pad = 8;
      const mrect = menu.getBoundingClientRect();
      // Prefer opening to the left of the ⋯ (actions column is trailing).
      let left = rect.right - mrect.width;
      let top = rect.bottom + 4;
      if (left < pad) {
        left = Math.min(rect.left, window.innerWidth - pad - mrect.width);
      }
      if (top + mrect.height > window.innerHeight - pad) {
        top = Math.max(pad, rect.top - 4 - mrect.height);
      }
      left = Math.max(pad, Math.min(left, window.innerWidth - pad - mrect.width));
      menu.style.left = `${left}px`;
      menu.style.top = `${top}px`;
      menu.style.visibility = "visible";
      menuEl = menu;
      try {
        btn.blur();
      } catch (_) {}
      onDoc = (e3) => {
        if (menu.contains(e3.target) || btn.contains(e3.target)) return;
        close();
      };
      setTimeout(() => document.addEventListener("click", onDoc, true), 0);
    },
  });
  return btn;
}

/** Navigate/reload admin SPA without importing router (avoids cycles). */
function navigateAdmin() {
  const fn = state.navigate;
  if (typeof fn === "function") return fn();
  return Promise.resolve();
}

export {
  SESSION_MONITOR_ROLE_FILTER_KEY,
  AUTH_TOKEN_KEY,
  AUTH_SESSION_KEY,
  CHAT_MEMORY_MODE_KEY,
  authStoreGet,
  authStoreSet,
  authStoreRemove,
  formatUserLabel,
  formatAuditActor,
  getRoute,
  resolveAdminApiUrl,
  resolveChatUrl,
  getStoredAuthToken,
  scheduleReauthAfter401,
  _haltAfter401,
  isAuthRequiredError,
  apiGet,
  apiGetOptional,
  apiGetNoHang,
  apiPost,
  assertSkillMutationOk,
  apiRequest,
  apiPostFormData,
  apiDeleteJson,
  _activeCopyCell,
  _selectCopyCell,
  _shouldIgnoreCopyShortcut,
  _installCellCopyKeyboardShortcut,
  attachCellCopyBehavior,
  el,
  tdCell,
  enableTableColumnResize,
  setActive,
  mount,
  renderPageShell,
  renderSectionCard,
  renderMetaChips,
  shortText,
  formatSystemLocalDateTime,
  formatIds,
  yesNo,
  runtimePrewarmReminder,
  markPrewarmReminder,
  rowActions,
  navigateAdmin,
  state,
  t,
  tf,
  applyI18nStatic,
  toggleLang,
};
