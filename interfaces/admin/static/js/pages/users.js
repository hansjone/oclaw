import { state, t, tf, el, tdCell, apiGet, apiPost, formatUserLabel, formatSystemLocalDateTime, navigateAdmin } from "../core.js";
import { hasPermission } from "./authz.js";

async function renderUserManagement() {
  const sessionTid = String((state.authSession && state.authSession.tenant_id) || "").trim();
  if (!sessionTid) {
    return el("div", {}, [
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("users.title") }),
        el("div", { class: "muted", text: t("tenants.noSessionTenant") }),
      ]),
    ]);
  }

  let allTenants = [];
  try {
    const allTenantsResp = await apiGet("/admin/api/tenants");
    allTenants = allTenantsResp.tenants || [];
  } catch (err) {
    if (!hasPermission("admin:user:read")) {
      return el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("common.error") }),
        el("div", { class: "pre", text: String(err) }),
      ]);
    }
    allTenants = [{ id: sessionTid, name: "", created_at: "" }];
  }

  if (!allTenants.length) {
    return el("div", {}, [
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("users.title") }),
        el("div", { class: "muted", text: t("tenants.noTenants") }),
      ]),
    ]);
  }

  const status = el("div", { class: "muted", text: "" });

  const tenantRows = allTenants.map((x) => {
    const tid = String(x.id || "");
    const isLoginHome = tid === sessionTid;
    const tname = String(x.name || "").trim() || tid.slice(0, 8);
    const canDelete = allTenants.length > 1 && tid !== sessionTid;
    const btnDel = el("button", {
      type: "button",
      class: "btn btn--danger",
      text: t("tenants.deleteTenant"),
      disabled: canDelete ? undefined : "disabled",
      title: canDelete
        ? undefined
        : allTenants.length <= 1
          ? t("tenants.deleteDisabledLast")
          : t("tenants.deleteDisabledCurrent"),
      onclick: async (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (!canDelete) return;
        if (!window.confirm(tf("tenants.deleteTenantConfirm", { name: tname }))) return;
        status.textContent = "";
        try {
          const resp = await apiPost("/admin/api/tenants/delete", { tenant_id: tid });
          if (!resp.ok) {
            const err = String(resp.error || "error");
            status.textContent =
              err === "last_tenant_cannot_delete"
                ? t("tenants.errLastTenant")
                : err === "cannot_delete_current_tenant"
                  ? t("tenants.errCannotDeleteCurrentTenant")
                  : err;
            return;
          }
          if (!Number(resp.deleted || 0)) {
            status.textContent = t("tenants.errTenantDeleteMiss");
            return;
          }
          await navigateAdmin();
        } catch (err) {
          status.textContent = String(err && err.message ? err.message : err);
        }
      },
    });
    return el("tr", {}, [
      el("td", { text: String(x.name || "") }),
      el("td", { text: formatSystemLocalDateTime(String(x.created_at || "")) }),
      el("td", {
        class: isLoginHome ? "" : "muted",
        text: isLoginHome ? t("tenants.scopeLoginHome") : "—",
      }),
      el("td", {}, [btnDel]),
    ]);
  });

  const selector = el("select", { class: "input" });
  for (const item of allTenants) {
    const optLabel = String(item.name || "").trim() || String(item.id || "").slice(0, 8);
    selector.appendChild(el("option", { value: String(item.id || ""), text: optLabel }));
  }
  const preferredIdx = allTenants.findIndex((x) => String(x.id || "") === sessionTid);
  selector.selectedIndex = preferredIdx >= 0 ? preferredIdx : 0;

  const bindingsBody = el("tbody");
  const codesBody = el("tbody");

  const searchInput = el("input", { class: "input", placeholder: t("users.search") });
  const userStatus = el("div", { class: "muted", text: "" });
  const userBody = el("tbody");
  const accountStatus = el("div", { class: "muted", text: "" });
  const selectedUserField = el("input", {
    class: "input input--readonly",
    readonly: "readonly",
    placeholder: t("users.wecomUserEmpty"),
  });
  const accountBody = el("tbody");
  const accountChannelInput = el("select", { class: "input" }, [
    el("option", { value: "wecom", text: "wecom" }),
    el("option", { value: "weixin", text: "weixin" }),
    el("option", { value: "whatsapp", text: "whatsapp" }),
  ]);
  const accountIdInput = el("input", { class: "input", placeholder: t("users.wecomBotId") });
  const accountNameInput = el("input", { class: "input", placeholder: t("users.wecomInstanceName") });
  const botSecretInput = el("input", { class: "input", type: "password", placeholder: t("users.wecomBotSecret") });
  const botSecretField = el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: t("users.wecomBotSecret") }), botSecretInput]);
  const clearBotChk = el("input", { type: "checkbox" });
  const clearBotField = el("label", { class: "kv row--wecom-form__chk" }, [clearBotChk, document.createTextNode(" " + t("users.clearBotSecret"))]);
  const accountActiveInput = el("input", { type: "checkbox" });
  const accountSpecialistInput = el("select", { class: "input" }, [el("option", { value: "generalist", text: "generalist" })]);
  accountActiveInput.checked = true;
  let selectedUserId = "";
  let selectedUsername = "";
  let selectedDisplayName = "";
  let availableAccountSpecialists = ["generalist"];

  const refreshSelectedUserField = () => {
    if (!selectedUserId) {
      selectedUserField.value = "";
      return;
    }
    const who = formatUserLabel({ username: selectedUsername, display_name: selectedDisplayName });
    selectedUserField.value = who;
  };

  const clearWecomForm = () => {
    accountIdInput.value = "";
    accountNameInput.value = "";
    botSecretInput.value = "";
    clearBotChk.checked = false;
    accountActiveInput.checked = true;
    accountSpecialistInput.value = "generalist";
  };
  const currentAccountChannel = () => String(accountChannelInput.value || "wecom").trim().toLowerCase() || "wecom";
  const refreshAccountFormByChannel = () => {
    const isWecom = currentAccountChannel() === "wecom";
    botSecretField.style.display = isWecom ? "" : "none";
    clearBotField.style.display = isWecom ? "" : "none";
  };
  const setAccountSpecialistOptions = (specialists) => {
    const opts = Array.isArray(specialists) && specialists.length
      ? specialists.map((x) => String(x || "").trim()).filter(Boolean)
      : ["generalist"];
    const uniq = Array.from(new Set(["generalist", ...opts]));
    availableAccountSpecialists = uniq;
    const old = String(accountSpecialistInput.value || "generalist").trim() || "generalist";
    accountSpecialistInput.innerHTML = "";
    uniq.forEach((sid) => {
      accountSpecialistInput.appendChild(el("option", { value: sid, text: sid, selected: sid === old ? "selected" : undefined }));
    });
    if (!uniq.includes(old)) accountSpecialistInput.value = "generalist";
  };

  const newUserName = el("input", { class: "input", placeholder: t("users.createNamePlaceholder") });
  const newUserRole = el("select", { class: "input" }, [
    el("option", { value: "member", text: "member" }),
    el("option", { value: "admin", text: "admin" }),
    el("option", { value: "guest", text: "guest" }),
    el("option", { value: "owner", text: "owner" }),
  ]);
  const newUserPassword = el("input", { class: "input", type: "password", placeholder: t("auth.password") });

  const getTenantId = () => String(selector.value || "");

  const mergeWecomBindingAndInstances = (bindings, items) => {
    const byAid = new Map();
    for (const it of items) {
      const aid = String(it.account_id || "").trim();
      if (aid) byAid.set(aid, it);
    }
    const seen = new Set();
    const out = [];
    for (const b of bindings) {
      const aid = String(b.account_id || "").trim();
      if (!aid || seen.has(aid)) continue;
      seen.add(aid);
      out.push({ binding: b, instance: byAid.get(aid) || null });
    }
    for (const it of items) {
      const aid = String(it.account_id || "").trim();
      if (!aid || seen.has(aid)) continue;
      out.push({ binding: null, instance: it });
    }
    return out;
  };

  const prefillFromMerged = (m) => {
    const inst = m.instance;
    const bind = m.binding;
    const aid = inst ? String(inst.account_id || "").trim() : String(bind?.account_id || "").trim();
    accountIdInput.value = aid;
    const nameFromInst = inst ? String(inst.name || "").trim() : "";
    const nameFromBind = bind ? String(bind.account_name || "").trim() : "";
    accountNameInput.value = nameFromInst || nameFromBind;
    if (inst) {
      accountActiveInput.checked = !!inst.is_active;
    } else {
      accountActiveInput.checked = true;
    }
    const specialist = String(((inst && inst.config) || {}).specialist || "generalist").trim().toLowerCase() || "generalist";
    accountSpecialistInput.value = availableAccountSpecialists.includes(specialist) ? specialist : "generalist";
    accountStatus.textContent =
      tf("users.accountModeExpert", { specialist });
    botSecretInput.value = "";
    clearBotChk.checked = false;
  };

  const loadAccounts = async () => {
    accountBody.innerHTML = "";
    clearWecomForm();
    const tenantId = getTenantId();
    if (!selectedUserId) {
      accountStatus.textContent = "";
      accountBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "10" })]));
      return;
    }
    const ch = currentAccountChannel();
    const bindUrl = `/admin/api/bindings?tenant_id=${encodeURIComponent(tenantId)}&channel=${encodeURIComponent(ch)}&user_id=${encodeURIComponent(selectedUserId)}`;
    const accUrl = `/admin/api/user-channel-accounts?tenant_id=${encodeURIComponent(tenantId)}&user_id=${encodeURIComponent(selectedUserId)}&channel=${encodeURIComponent(ch)}&include_inactive=1`;
    const [bindResp, accResp] = await Promise.all([ch === "wecom" ? apiGet(bindUrl) : Promise.resolve({ bindings: [] }), apiGet(accUrl)]);
    const bindings = Array.isArray(bindResp && bindResp.bindings) ? bindResp.bindings : [];
    const items = Array.isArray(accResp.items) ? accResp.items : [];
    const merged = ch === "wecom" ? mergeWecomBindingAndInstances(bindings, items) : items.map((it) => ({ binding: null, instance: it }));
    accountStatus.textContent = "";
    if (!merged.length) {
      accountBody.appendChild(el("tr", {}, [el("td", { text: t("users.noBindingsForUser"), colspan: "10" })]));
      return;
    }
    merged.forEach((m) => {
      const inst = m.instance;
      const bind = m.binding;
      const accountId = inst ? String(inst.account_id || "") : String(bind?.account_id || "");
      const displayName = (inst && String(inst.name || "").trim()) || (bind && String(bind.account_name || "").trim()) || "";
      const extUid = bind ? String(bind.external_user_id || "") : "";
      const ts = (inst && String(inst.updated_at || "").trim()) || (bind && String(bind.created_at || "").trim()) || "";
      const cfg = (inst && inst.config && typeof inst.config === "object") ? inst.config : {};
      const modeText = String(cfg.interaction_mode || "expert");
      const specialistText = String(cfg.specialist || "generalist");
      const btnFill = el("button", {
        class: "btn",
        text: t("users.loadForm"),
        onclick: (e) => {
          e.stopPropagation();
          prefillFromMerged(m);
        },
      });
      const deleteCell = el("td", {});
      if (inst) {
        const btnBindExpert = el("button", {
          class: "btn btn--primary",
          text: t("wa.bindSpecialist"),
          onclick: async (e) => {
            e.stopPropagation();
            const specialist = String(accountSpecialistInput.value || "generalist").trim() || "generalist";
            await apiPost("/admin/api/user-channel-accounts/upsert", {
              tenant_id: tenantId,
              user_id: selectedUserId,
              channel: ch,
              account_id: accountId,
              name: displayName,
              is_active: !!inst.is_active,
              config: { interaction_mode: "expert", specialist },
            });
            await loadAccounts();
          },
        });
        const btnDeleteAccount = el("button", { class: "btn btn--danger", text: t("users.accountDelete"), onclick: async (e) => {
          e.stopPropagation();
          await apiPost("/admin/api/user-channel-accounts/delete", {
            tenant_id: tenantId,
            user_id: selectedUserId,
            channel: ch,
            account_id: accountId,
          });
          await loadAccounts();
        }});
        deleteCell.appendChild(btnBindExpert);
        deleteCell.appendChild(btnDeleteAccount);
      } else {
        deleteCell.appendChild(document.createTextNode("—"));
      }
      accountBody.appendChild(el("tr", {}, [
        tdCell(accountId, 22),
        tdCell(displayName, 16),
        tdCell(extUid || "—", 18),
        tdCell(inst ? (ch === "wecom" ? (inst.has_bot_secret ? "Y" : "-") : "-") : "—", 4),
        tdCell(inst ? (inst.is_active ? "1" : "0") : "—", 4),
        tdCell(modeText || "expert", 8),
        tdCell(specialistText || "generalist", 10),
        tdCell(ts, 20),
        el("td", {}, [btnFill]),
        deleteCell,
      ]));
    });
  };

  const btnSaveAccount = el("button", { class: "btn", text: t("users.accountSave"), onclick: async () => {
    if (!selectedUserId) {
      accountStatus.textContent = "select user first";
      return;
    }
    const aid = accountIdInput.value.trim();
    if (!aid) {
      accountStatus.textContent = t("users.botIdRequired");
      return;
    }
    const tenantId = getTenantId();
    const ch = currentAccountChannel();
    const specialist = String(accountSpecialistInput.value || "generalist").trim() || "generalist";
    const resp = await apiPost("/admin/api/user-channel-accounts/upsert", {
      tenant_id: tenantId,
      user_id: selectedUserId,
      channel: ch,
      account_id: aid,
      name: accountNameInput.value.trim(),
      wecom_mode: ch === "wecom" ? "bot_api" : undefined,
      bot_secret: botSecretInput.value.trim(),
      clear_bot_secret: !!clearBotChk.checked,
      is_active: !!accountActiveInput.checked,
      config: {
        interaction_mode: "expert",
        specialist,
      },
    });
    accountStatus.textContent = resp.ok ? "ok" : String(resp.error || "error");
    if (resp.ok) {
      botSecretInput.value = "";
      clearBotChk.checked = false;
      await loadAccounts();
      await loadList();
    }
  }});
  accountChannelInput.addEventListener("change", async () => {
    clearWecomForm();
    refreshAccountFormByChannel();
    await loadAccounts();
  });

  const loadList = async () => {
    if (!hasPermission("admin:user:read")) {
      userBody.innerHTML = "";
      userBody.appendChild(el("tr", {}, [el("td", { text: t("users.needUserRead"), colspan: "7" })]));
      return;
    }
    const tenantId = getTenantId();
    const tMeta = allTenants.find((r) => String(r.id || "") === tenantId) || {};
    const sessionTenantName = String(tMeta.name || "").trim();
    const q = encodeURIComponent(searchInput.value.trim());
    const resp = await apiGet(`/admin/api/users?tenant_id=${encodeURIComponent(tenantId)}&include_inactive=1&q=${q}&limit=300`);
    const users = Array.isArray(resp.users) ? resp.users : [];
    userBody.innerHTML = "";
    if (!users.length) {
      userBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "7" })]));
      return;
    }
    users.forEach((u) => {
      const newRole = el("select", { class: "input" }, [
        el("option", { value: "member", text: "member" }),
        el("option", { value: "admin", text: "admin" }),
        el("option", { value: "guest", text: "guest" }),
        el("option", { value: "owner", text: "owner" }),
      ]);
      newRole.value = String(u.role || "member");
      const pwd = el("input", { class: "input", type: "password", placeholder: t("users.passwordOptional") });
      const btnToggle = el("button", { class: "btn", text: u.is_active ? t("users.disable") : t("users.enable"), onclick: async () => {
        await apiPost("/admin/api/users/update", {
          tenant_id: tenantId,
          user_id: u.id,
          is_active: !u.is_active,
        });
        await loadList();
      }});
      const btnUpdate = el("button", { class: "btn", text: t("users.update"), onclick: async () => {
        await apiPost("/admin/api/users/update", {
          tenant_id: tenantId,
          user_id: u.id,
          role: newRole.value,
          password: pwd.value.trim() || undefined,
        });
        await loadList();
      }});
      const btnDelete = el("button", { class: "btn btn--danger", text: t("users.delete"), onclick: async (e) => {
        e.stopPropagation();
        if (!window.confirm(t("users.deleteConfirm"))) return;
        await apiPost("/admin/api/users/delete", { tenant_id: tenantId, user_id: u.id });
        await loadList();
      }});
      const actionWrap = el("div", { class: "table__cell-actions" }, [btnToggle, btnUpdate, btnDelete]);
      const tr = el("tr", {}, [
        tdCell(sessionTenantName || "—", 14),
        tdCell(formatUserLabel(u), 28),
        tdCell(u.role || "", 10),
        tdCell(u.is_active ? "1" : "0", 4),
        el("td", { class: "table__cell--form" }, [newRole]),
        el("td", { class: "table__cell--form" }, [pwd]),
        el("td", { class: "table__cell--actions" }, [actionWrap]),
      ]);
      tr.style.cursor = "pointer";
      tr.addEventListener("click", async (e) => {
        if (e.target && e.target.closest && e.target.closest("button,select,input")) return;
        selectedUserId = String(u.id || "");
        selectedUsername = String(u.username || "");
        selectedDisplayName = String(u.display_name || "");
        refreshSelectedUserField();
        await loadAccounts();
      });
      userBody.appendChild(tr);
    });
  };

  const btnCreateUser = el("button", { class: "btn btn--primary", text: t("users.create"), onclick: async () => {
    if (!hasPermission("admin:user:write")) {
      userStatus.textContent = "forbidden";
      return;
    }
    try {
      const raw = newUserName.value.trim();
      if (!raw) {
        userStatus.textContent = t("users.createNameRequired");
        return;
      }
      const resp = await apiPost("/admin/api/users/create", {
        tenant_id: getTenantId(),
        username: raw,
        display_name: raw,
        role: newUserRole.value,
        password: newUserPassword.value.trim(),
      });
      userStatus.textContent = resp.ok ? "ok" : String(resp.error || "error");
      if (resp.ok) {
        newUserName.value = "";
        newUserPassword.value = "";
        await loadList();
        await loadBindingsAndCodes();
      }
    } catch (e) {
      userStatus.textContent = String(e && e.message ? e.message : e);
    }
  }});

  const btnSearchUsers = el("button", { class: "btn", text: t("audit.query"), onclick: loadList });

  const createName = el("input", { class: "input", placeholder: t("tenants.createPlaceholder") });
  const btnCreateTenant = el("button", { class: "btn", text: t("tenants.create"), onclick: async () => {
    if (!hasPermission("admin:tenant:write")) {
      status.textContent = "forbidden";
      return;
    }
    await apiPost("/admin/api/tenants/create", { name: createName.value.trim() || "Team" });
    await navigateAdmin();
  }});

  const roleInput = el("select", { class: "input" }, [
    el("option", { value: "member", text: "member" }),
    el("option", { value: "admin", text: "admin" }),
    el("option", { value: "guest", text: "guest" }),
  ]);
  const codeInput = el("input", { class: "input", placeholder: t("tenants.codeOptional") });
  const btnCreateCode = el("button", { class: "btn", text: t("tenants.createCode"), onclick: async () => {
    const tid = String(selector.value || "");
    await apiPost("/admin/api/bind-codes/create", {
      tenant_id: tid,
      role: roleInput.value || "member",
      code: codeInput.value.trim(),
    });
    codeInput.value = "";
    await loadBindingsAndCodes();
  }});
  const btnDeleteUnbound = el("button", { class: "btn btn--danger", text: t("tenants.deleteUnbound"), onclick: async () => {
    const tid = String(selector.value || "");
    const resp = await apiPost("/admin/api/users/delete-unbound", { tenant_id: tid, channel: "wecom" });
    status.textContent = tf("tenants.deleteUnboundResult", {
      deleted: Number(resp.deleted || 0),
      orphan: Number(resp.orphan_users || 0),
      bound: Number(resp.bound_users || 0),
      total: Number(resp.users_total || 0),
    });
    await loadBindingsAndCodes();
    await loadList();
  }});

  const loadBindingsAndCodes = async () => {
    const tid = String(selector.value || "");
    const [bindingsResp, codesResp] = await Promise.all([
      apiGet("/admin/api/bindings?tenant_id=" + encodeURIComponent(tid) + "&channel=wecom"),
      apiGet("/admin/api/bind-codes?tenant_id=" + encodeURIComponent(tid)),
    ]);
    const bindings = bindingsResp.bindings || [];
    const codes = codesResp.codes || [];

    const bindingTenantLabel = (tenantId) => {
      const id = String(tenantId || "");
      const meta = allTenants.find((x) => String(x.id || "") === id);
      const name = String(meta && meta.name ? meta.name : "").trim();
      return name || id.slice(0, 8) || "—";
    };
    const bindingUserLabel = (b) =>
      formatUserLabel({
        username: String(b.username != null && b.username !== "" ? b.username : b.user_id || ""),
        display_name: String(b.display_name || ""),
      });

    bindingsBody.innerHTML = "";
    if (!bindings.length) {
      bindingsBody.appendChild(el("tr", {}, [el("td", { text: t("tenants.noBindings"), colspan: "6" })]));
    } else {
      bindings.forEach((b) => {
        bindingsBody.appendChild(el("tr", {}, [
          el("td", { text: bindingTenantLabel(b.tenant_id) }),
          el("td", { text: bindingUserLabel(b) }),
          el("td", { text: String(b.channel || "") }),
          el("td", { text: String(b.account_id || "") }),
          el("td", { text: String(b.account_name || "") }),
          el("td", { text: String(b.external_user_id || "") }),
        ]));
      });
    }

    codesBody.innerHTML = "";
    if (!codes.length) {
      codesBody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "6" })]));
    } else {
      codes.forEach((c) => {
        const codeText = String(c.code || "");
        const isUsed = Boolean(c.used_at);
        const btnDeleteCode = el("button", { class: "btn btn--danger", text: t("tenants.deleteCode"), onclick: async () => {
          if (!window.confirm(t("tenants.codeDeleteConfirm"))) return;
          await apiPost("/admin/api/bind-codes/delete", { tenant_id: tid, code: codeText });
          status.textContent = tf("tenants.codeDeleted", { code: codeText });
          await loadBindingsAndCodes();
        }});
        codesBody.appendChild(el("tr", {}, [
          el("td", { text: codeText }),
          el("td", { text: String(c.role || "") }),
          el("td", { text: isUsed ? t("tenants.codeUsed") : t("tenants.codeUnused") }),
          el("td", { text: String(c.used_by_external_user_id || "") }),
          el("td", { text: formatSystemLocalDateTime(String(c.created_at || "")) }),
          el("td", {}, [btnDeleteCode]),
        ]));
      });
    }
  };
  selector.addEventListener("change", () => {
    selectedUserId = "";
    selectedUsername = "";
    selectedDisplayName = "";
    refreshSelectedUserField();
    Promise.all([loadBindingsAndCodes(), loadList(), loadAccounts()]).catch((err) => {
      mount(el("div", { class: "card" }, [el("div", { class: "card__title", text: t("common.error") }), el("div", { class: "pre", text: String(err) })]));
    });
  });
  await loadBindingsAndCodes();
  try {
    const sf = await apiGet("/admin/api/chat/settings/specialist-flags");
    setAccountSpecialistOptions(sf.available_specialists || ["generalist"]);
  } catch (_) {
    setAccountSpecialistOptions(["generalist"]);
  }
  await loadList();
  refreshSelectedUserField();
  refreshAccountFormByChannel();
  await loadAccounts();

  const tenantsListHint = allTenants.length > 1
    ? el("div", { class: "muted u-mt-8", text: t("tenants.allTenantsHint") })
    : el("div", {});

  return el("div", {}, [
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("tenants.title") }),
      el("div", { class: "row" }, [createName, btnCreateTenant]),
      el("div", { class: "row" }, [el("label", { text: t("tenants.select") }), selector]),
      el("div", { class: "muted u-mt-6", text: t("tenants.scopeHint") }),
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("tenants.colTenantName") }),
          el("th", { text: t("table.createdAt") }),
          el("th", { text: t("tenants.colScope") }),
          el("th", { text: t("tenants.rowActions") }),
        ])]),
        el("tbody", {}, tenantRows),
      ]),
      status,
      tenantsListHint,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("users.title") }),
      el("div", { class: "row" }, [searchInput, btnSearchUsers]),
      el("div", { class: "row" }, [newUserName, newUserRole, newUserPassword, btnCreateUser]),
      userStatus,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact table--users-mgmt" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("tenants.colTenantName") }),
          el("th", { text: t("users.colUser") }),
          el("th", { text: t("tenants.role") }),
          el("th", { text: t("users.colActive") }),
          el("th", { text: t("users.colSetRole") }),
          el("th", { text: t("users.passwordOptional") }),
          el("th", { text: t("tenants.rowActions") }),
        ])]),
        userBody,
      ])]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("users.wecomAccounts") }),
      el("div", {}, [el("div", { class: "muted", text: t("users.wecomUserLabel") }), selectedUserField]),
      el("div", { class: "muted", style: "margin-bottom:8px", text: t("users.accountLoadHint") }),
      el("div", { class: "row row--wecom-form" }, [
        el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: "channel" }), accountChannelInput]),
        el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: t("users.wecomBotId") }), accountIdInput]),
        el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: t("users.wecomInstanceName") }), accountNameInput]),
        el("div", { class: "row--wecom-form__field" }, [el("div", { class: "muted", text: t("wa.specialist") }), accountSpecialistInput]),
        botSecretField,
        el("label", { class: "kv row--wecom-form__chk" }, [accountActiveInput, document.createTextNode(" " + t("users.accountActive"))]),
        clearBotField,
        btnSaveAccount,
      ]),
      accountStatus,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("users.wecomBotId") }),
          el("th", { text: t("users.wecomInstanceName") }),
          el("th", { text: t("table.externalUserId") }),
          el("th", { text: t("users.hasBotSecret") }),
          el("th", { text: t("users.accountActive") }),
          el("th", { text: t("common.mode") }),
          el("th", { text: t("table.specialist") }),
          el("th", { text: t("table.timestamp") }),
          el("th", { text: t("users.loadForm") }),
          el("th", { text: t("users.accountActions") }),
        ])]),
        accountBody,
      ])]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("tenants.bindings") }),
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("tenants.title") }),
          el("th", { text: t("tenants.users") }),
          el("th", { text: t("table.channel") }),
          el("th", { text: "account_id" }),
          el("th", { text: "account_name" }),
          el("th", { text: t("table.externalUserId") }),
        ])]),
        bindingsBody,
      ]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("tenants.bindCodes") }),
      el("div", { class: "row" }, [
        el("label", { text: t("tenants.role") }),
        roleInput,
        codeInput,
        btnCreateCode,
        btnDeleteUnbound,
      ]),
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "code" }),
          el("th", { text: t("tenants.role") }),
          el("th", { text: t("tenants.codeStatus") }),
          el("th", { text: t("tenants.codeUsedBy") }),
          el("th", { text: t("table.createdAt") }),
          el("th", { text: t("tenants.deleteCode") }),
        ])]),
        codesBody,
      ]),
    ]),
  ]);
}


export { renderUserManagement };
