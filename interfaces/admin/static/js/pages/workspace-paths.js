import { state, t, el, apiGet, apiPost, formatUserLabel } from "../core.js";
import { hasPermission } from "./authz.js";

async function renderWorkspacePaths() {
  const sessionTid = String((state.authSession && state.authSession.tenant_id) || "").trim();
  const sessionUid = String((state.authSession && state.authSession.user_id) || "").trim();
  const canUserRead = hasPermission("admin:user:read");
  const canWsRead = hasPermission("admin:workspace_paths:read");
  const canWsWrite = hasPermission("admin:workspace_paths:write");
  const selfService = !canUserRead && canWsRead;
  if (!sessionTid || (!canUserRead && !canWsRead)) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.workspacePaths") }),
      el("div", { class: "muted", text: t("common.forbidden") }),
    ]);
  }
  if (selfService && !sessionUid) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.workspacePaths") }),
      el("div", { class: "muted", text: t("tenants.noSessionTenant") }),
    ]);
  }
  let allTenants = [];
  try {
    const allTenantsResp = await apiGet("/admin/api/tenants");
    allTenants = allTenantsResp.tenants || [];
  } catch (_) {
    allTenants = [{ id: sessionTid, name: "", created_at: "" }];
  }
  if (!allTenants.length) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.workspacePaths") }),
      el("div", { class: "muted", text: t("tenants.noTenants") }),
    ]);
  }
  const tenantSel = el("select", { class: "input" });
  for (const item of allTenants) {
    const optLabel = String(item.name || "").trim() || String(item.id || "").slice(0, 8);
    tenantSel.appendChild(el("option", { value: String(item.id || ""), text: optLabel }));
  }
  const preferredIdx = allTenants.findIndex((x) => String(x.id || "") === sessionTid);
  tenantSel.selectedIndex = preferredIdx >= 0 ? preferredIdx : 0;
  if (selfService) {
    tenantSel.disabled = true;
    tenantSel.title = t("workspacePaths.selfOnly");
  }
  const userSel = el("select", { class: "input" });
  const selfUserLabel = el("div", {
    class: "muted",
    text: formatUserLabel({
      username: state.authSession && state.authSession.username,
      display_name: state.authSession && state.authSession.display_name,
    }) + (sessionUid ? ` · ${sessionUid.slice(0, 8)}…` : ""),
  });
  if (selfService) {
    userSel.style.display = "none";
  }
  const extraInput = el("textarea", {
    class: "input",
    rows: "4",
    placeholder: "D:\\\\|E:\\\\|D:\\\\repos\\\\other",
    style: "min-height:88px;font-family:monospace;",
  });
  const allowAnyCb = el("input", { type: "checkbox" });
  const allowHighToolsCb = el("input", { type: "checkbox" });
  const status = el("div", { class: "muted", text: "" });
  const canWrite = hasPermission("admin:user:write") || canWsWrite;
  const canTogglePublicHigh = hasPermission("admin:user:write");
  if (!canTogglePublicHigh) {
    allowHighToolsCb.disabled = true;
  }

  const getEffectiveTid = () => (selfService ? sessionTid : String(tenantSel.value || ""));
  const getEffectiveUid = () => (selfService ? sessionUid : String(userSel.value || ""));

  const loadUsers = async () => {
    if (selfService) return;
    const tid = String(tenantSel.value || "");
    userSel.innerHTML = "";
    if (!tid) return;
    const resp = await apiGet(
      "/admin/api/users?tenant_id=" +
        encodeURIComponent(tid) +
        "&include_inactive=1&q=&limit=500",
    );
    const users = Array.isArray(resp.users) ? resp.users : [];
    for (const u of users) {
      const id = String(u.id || "");
      if (!id) continue;
      const label = formatUserLabel(u);
      userSel.appendChild(el("option", { value: id, text: label }));
    }
    if (userSel.options.length) userSel.selectedIndex = 0;
  };

  const loadPolicy = async () => {
    const tid = getEffectiveTid();
    const uid = getEffectiveUid();
    if (!tid || !uid) {
      status.textContent = "";
      return;
    }
    status.textContent = "…";
    try {
      const r = await apiGet(
        "/admin/api/users/workspace-path-policy?tenant_id=" +
          encodeURIComponent(tid) +
          "&user_id=" +
          encodeURIComponent(uid),
      );
      if (!r.ok) {
        status.textContent = String(r.error || "error");
        return;
      }
      const pol = r.policy || {};
      extraInput.value = String(pol.extra_roots || "");
      allowAnyCb.checked = !!pol.allow_any_path;
      allowHighToolsCb.checked = !!r.public_tools_allow_high;
      status.textContent = (r.from_db ? t("workspacePaths.fromDb") + " · " : "") + JSON.stringify(pol);
    } catch (e) {
      status.textContent = String(e && e.message ? e.message : e);
    }
  };

  tenantSel.addEventListener("change", async () => {
    await loadUsers();
    await loadPolicy();
  });
  userSel.addEventListener("change", () => {
    loadPolicy();
  });

  await loadUsers();
  await loadPolicy();

  const loadBtn = el("button", {
    class: "btn",
    text: t("workspacePaths.load"),
    onclick: () => loadPolicy(),
  });
  const saveBtn = el("button", {
    class: "btn btn--primary",
    text: t("workspacePaths.save"),
    disabled: canWrite ? undefined : "disabled",
    onclick: async () => {
      if (!canWrite) return;
      const tid = getEffectiveTid();
      const uid = getEffectiveUid();
      if (!tid || !uid) return;
      status.textContent = "…";
      try {
        const payload = {
          tenant_id: tid,
          user_id: uid,
          extra_roots: extraInput.value,
          allow_any_path: !!allowAnyCb.checked,
        };
        if (canTogglePublicHigh) {
          payload.public_tools_allow_high = !!allowHighToolsCb.checked;
        }
        const r = await apiPost("/admin/api/users/workspace-path-policy", payload);
        if (!r.ok) {
          status.textContent = String(r.error || "error");
          return;
        }
        await loadPolicy();
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
      }
    },
  });

  const userRowChildren = selfService ? [selfUserLabel] : [userSel];
  const cardParts = [
    el("div", { class: "card__title", text: t("title.workspacePaths") }),
    el("div", { class: "muted", text: t("workspacePaths.help") }),
  ];
  if (selfService) {
    cardParts.push(el("div", { class: "muted u-mt-6", text: t("workspacePaths.selfOnly") }));
  }
  cardParts.push(
    el("div", { class: "u-h-10" }),
    el("div", { class: "row" }, [
      el("label", { text: t("workspacePaths.tenant") }),
      tenantSel,
    ]),
    el("div", { class: "row" }, [
      el("label", { text: t("workspacePaths.user") }),
      ...userRowChildren,
    ]),
    el("div", { class: "row" }, [el("label", { text: t("workspacePaths.extraRoots") })]),
    extraInput,
    el("label", { class: "row", style: "align-items:center;gap:8px;margin-top:8px;" }, [
      allowAnyCb,
      el("span", { text: t("workspacePaths.allowAny") }),
    ]),
    el("div", { class: "muted u-muted-block", text: t("workspacePaths.allowAnyHint") }),
    el("label", { class: "row", style: "align-items:center;gap:8px;margin-top:10px;" }, [
      allowHighToolsCb,
      el("span", { text: t("workspacePaths.allowHighTools") }),
    ]),
    el("div", { class: "muted u-muted-block", text: t("workspacePaths.allowHighToolsHint") }),
    el("div", { class: "row", style: "margin-top:10px;gap:8px;" }, [loadBtn, saveBtn]),
    el("div", { class: "muted u-mt-8" }, [el("span", { text: t("workspacePaths.status") + ": " }), status]),
  );
  return el("div", { class: "card" }, cardParts);
}


export { renderWorkspacePaths };
