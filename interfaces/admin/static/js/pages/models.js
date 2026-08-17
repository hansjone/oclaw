import { state, t, el, tdCell, apiGet, apiPost, apiRequest, resolveAdminApiUrl, getStoredAuthToken, renderPageShell, renderSectionCard, markPrewarmReminder } from "../core.js";
import { hasPermission } from "./authz.js";

async function renderModels() {
  const canPickActive = hasPermission("admin:read");
  const canConfigureBindings = canPickActive;
  const canConfigureChatUi = hasPermission("admin:tenant:write");
  const status = el("div", { class: "muted", text: "" });
  const isAdminPool = String((state.authSession && state.authSession.username) || "").trim().toLowerCase() === "administrator";
  // 与后端 _require_models_mutate 对齐：administrator 写全局池需 tenant:write；普通用户写自己的配置只需 admin:read
  const canMutateProfiles = isAdminPool ? hasPermission("admin:tenant:write") : canPickActive;
  const readonlyHint = el("div", {
    class: "muted",
    text: isAdminPool && !canMutateProfiles ? t("models.readonly") : "",
  });
  const activeSelect = el("select", { class: "input", disabled: !canPickActive });
  const chatModelSelectorVisibleCb = el("input", { type: "checkbox", disabled: !canConfigureChatUi });
  const bindingWrap = el("div", {});
  const opsAiSpecialistSelect = el("select", { class: "input", disabled: !canConfigureBindings });
  const opsAiProfileSelect = el("select", { class: "input", disabled: !canConfigureBindings });
  const modelsGrantsLinkRow = el("div", { class: "muted u-hidden" });
  const newName = el("input", { class: "input", placeholder: t("models.createNamePlaceholder") });
  const newMode = el("select", { class: "input", disabled: !canMutateProfiles }, [
    el("option", { value: "openai", text: t("models.mode.openai") }),
    el("option", { value: "anthropic", text: t("models.mode.anthropic") }),
    el("option", { value: "google", text: t("models.mode.google") }),
    el("option", { value: "ollama", text: t("models.mode.ollama") }),
    el("option", { value: "rule", text: t("models.mode.rule") }),
  ]);
  const profName = el("input", { class: "input" });
  const modeSel = el("select", { class: "input" });
  const modelInp = el("input", { class: "input" });
  const baseInp = el("input", { class: "input", placeholder: t("models.baseUrlPlaceholder") });
  const thinkingModeCb = el("input", { type: "checkbox" });
  const reasoningEffortSel = el("select", { class: "input", style: "max-width:180px" }, [
    el("option", { value: "", text: t("models.reasoningEffortDefault") }),
    el("option", { value: "low", text: t("models.reasoningEffortLow") }),
    el("option", { value: "medium", text: t("models.reasoningEffortMedium") }),
    el("option", { value: "high", text: t("models.reasoningEffortHigh") }),
  ]);
  const keyInp = el("input", { class: "input", type: "password", autocomplete: "off" });
  const rememberCb = el("input", { type: "checkbox" });
  const readonlyProfileHint = el("div", { class: "muted", text: "" });
  const builtinCap = el("div", { class: "muted", text: "" });
  const warnKey = el("div", { class: "muted", text: "" });
  const openaiHint = el("div", { class: "muted", text: "" });
  const ollamaHint = el("div", { class: "muted", text: "" });
  const evalMetrics = el("div", { class: "row" });
  const evalTableWrap = el("div");
  const evalDetails = el("details", { class: "details" });
  const evalSummary = el("summary", { text: t("models.evalToggle") });
  const evalInner = el("div", {});
  const expertsStatus = el("div", { class: "muted", text: "" });
  const expertsSelect = el("select", { class: "input" });
  const expertNewId = el("input", { class: "input", placeholder: "new expert id, e.g. qa" });
  const expertNewNameEn = el("input", { class: "input", placeholder: "English name (required)" });
  const expertNewNameZh = el("input", { class: "input", placeholder: t("models.phNameZh") });
  const expertRoleSel = el("select", { class: "input" }, [
    el("option", { value: "expert", text: "expert" }),
    el("option", { value: "system", text: "system" }),
  ]);
  const expertNameEn = el("input", { class: "input", placeholder: "English name (required)" });
  const expertNameZh = el("input", { class: "input", placeholder: t("models.phNameZh") });
  const expertSoul = el("textarea", { class: "input", rows: "5", placeholder: "SOUL.md (optional)" });
  const expertRoleSystem = el("textarea", { class: "input", rows: "5", placeholder: "ROLE_SYSTEM.md (optional)" });

  async function downloadEvalExport(format) {
    const fmt = format === "json" ? "json" : "csv";
    const url = resolveAdminApiUrl(`/admin/api/models/eval/export?format=${encodeURIComponent(fmt)}`);
    const token = getStoredAuthToken();
    const res = await fetch(url, {
      headers: {
        accept: fmt === "json" ? "application/json" : "text/csv",
        ...(token ? { authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) throw new Error(`export ${res.status}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    const name = fmt === "json" ? "agent_eval_logs.json" : "agent_eval_logs.csv";
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const btnEvalCsv = el("button", {
    class: "btn",
    text: t("models.evalDownloadCsv"),
    onclick: async () => {
      try {
        await downloadEvalExport("csv");
      } catch (e) {
        status.textContent = String(e.message || e);
      }
    },
  });
  const btnEvalJson = el("button", {
    class: "btn",
    text: t("models.evalDownloadJson"),
    onclick: async () => {
      try {
        await downloadEvalExport("json");
      } catch (e) {
        status.textContent = String(e.message || e);
      }
    },
  });
  const evalActionRow = el("div", { class: "row" }, [
    el("span", { class: "muted", text: t("models.evalLogsPreview") }),
    btnEvalCsv,
    btnEvalJson,
  ]);
  evalInner.appendChild(evalMetrics);
  evalInner.appendChild(evalActionRow);
  evalInner.appendChild(evalTableWrap);
  evalDetails.appendChild(evalSummary);
  evalDetails.appendChild(evalInner);

  let modelsState = null;
  let evalPack = null;
  let secretsStatus = null;
  let expertsState = { items: [] };

  const secretsStatusMsg = el("div", { class: "muted", text: "" });
  const secretsMigrateBtn = el("button", { class: "btn", text: t("secrets.migrateBtn") });
  const secretsCard = el("div", { class: "card u-hidden" }, [
    el("div", { class: "card__title", text: t("secrets.migrateTitle") }),
    el("div", { class: "muted", text: t("secrets.migrateHint") }),
    el("div", { class: "row" }, [secretsMigrateBtn]),
    secretsStatusMsg,
  ]);

  function fmtSecretsDone(s, p) {
    return t("secrets.migrateDone").replace("{s}", String(s)).replace("{p}", String(p));
  }

  function paintSecretsCard() {
    secretsStatusMsg.textContent = "";
    if (!secretsStatus || secretsStatus.ok !== true) {
      secretsCard.style.display = "none";
      return;
    }
    const n1 = intOr0(secretsStatus.legacy_b64_app_settings);
    const n2 = intOr0(secretsStatus.legacy_b64_llm_profiles);
    const total = n1 + n2;
    const canMigrate = hasPermission("admin:tenant:write");
    if (total <= 0) {
      secretsCard.style.display = "none";
      return;
    }
    secretsCard.style.display = "block";
    if (!canMigrate) {
      secretsMigrateBtn.disabled = true;
      secretsStatusMsg.textContent = t("secrets.migrateForbidden");
      return;
    }
    if (!secretsStatus.has_master_key) {
      secretsMigrateBtn.disabled = true;
      secretsStatusMsg.textContent = t("secrets.migrateNeedKey");
      return;
    }
    secretsMigrateBtn.disabled = false;
    secretsStatusMsg.textContent = `legacy: settings=${n1}, profiles=${n2}`;
  }

  const VIS_KEYS = {
    builtin: "models.vis.builtin",
    owned: "models.vis.owned",
    grant_user: "models.vis.grantUser",
    grant_tenant: "models.vis.grantTenant",
    global: "models.vis.global",
    other_user: "models.vis.otherUser",
  };

  function visibilityTag(vr) {
    const k = VIS_KEYS[String(vr || "")];
    return k ? t(k) : "";
  }

  function labelFor(pid) {
    const profiles = (modelsState && modelsState.profiles) || [];
    const p = profiles.find((x) => String(x.id) === String(pid));
    const base = (p && String(p.name || "").trim()) || pid;
    const vr = p && p.visibility_reason;
    if (!vr) return base;
    const tag = visibilityTag(vr);
    return tag ? `${base} (${tag})` : base;
  }

  function fillModeSelect(sel, modes, current) {
    sel.innerHTML = "";
    modes.forEach((m) => {
      const label =
        m === "openai"
          ? t("models.mode.openai")
          : m === "openai_responses"
            ? t("models.mode.openai_responses")
            : m === "anthropic"
              ? t("models.mode.anthropic")
              : m === "google"
                ? t("models.mode.google")
                : m === "ollama"
                  ? t("models.mode.ollama")
                  : t("models.mode.rule");
      sel.appendChild(el("option", {
        value: m,
        text: label,
      }));
    });
    if (modes.includes(current)) sel.value = current;
    else sel.value = modes[0];
  }

  async function refresh() {
    try {
      const data = await apiGet("/admin/api/models");
      modelsState = data;
      status.textContent = "";
      paint();
      try {
        secretsStatus = await apiGet("/admin/api/secrets/status");
      } catch (_) {
        secretsStatus = null;
      }
      paintSecretsCard();
      try {
        evalPack = await apiGet("/admin/api/models/eval?limit_logs=100");
        paintEval();
      } catch (ee) {
        evalPack = { ok: false, summary: {}, logs: [] };
        paintEval();
        status.textContent = [status.textContent, `${t("models.sectionEval")}: ${String(ee.message || ee)}`].filter(Boolean).join(" | ");
      }
      try {
        expertsState = await apiGet("/admin/api/experts");
      } catch (_) {
        expertsState = { ok: false, items: [] };
      }
      paintExperts();
    } catch (e) {
      modelsState = null;
      evalPack = null;
      secretsStatus = null;
      expertsState = { ok: false, items: [] };
      status.textContent = String(e.message || e);
    }
  }

  function currentExpertItem() {
    const items = Array.isArray(expertsState && expertsState.items) ? expertsState.items : [];
    const id = String(expertsSelect.value || "");
    return items.find((x) => String(x.id || "") === id) || null;
  }

  function fillExpertFields(item) {
    const files = (item && item.files && typeof item.files === "object") ? item.files : {};
    expertNameEn.value = String((item && item.display_name_en) || "");
    expertNameZh.value = String((item && item.display_name_zh) || "");
    expertRoleSel.value = String((item && item.role) || "expert");
    expertSoul.value = String(files["SOUL.md"] || "");
    expertRoleSystem.value = String(files["ROLE_SYSTEM.md"] || "");
    const isSystem = !!(item && (item.builtin || String(item.role || "") === "system"));
    expertRoleSel.disabled = isSystem;
    btnExpertDelete.disabled = isSystem;
  }

  function paintExperts() {
    const items = Array.isArray(expertsState && expertsState.items) ? expertsState.items : [];
    const prev = String(expertsSelect.value || "");
    expertsSelect.innerHTML = "";
    items.forEach((x) => {
      const id = String(x.id || "");
      if (!id) return;
      const isSystem = !!(x && (x.builtin || String(x.role || "") === "system"));
      const tail = isSystem ? " (system)" : "";
      const name = String(x.display_name_en || "").trim() || id;
      expertsSelect.appendChild(el("option", { value: id, text: `${name} [${id}]${tail}` }));
    });
    if (items.some((x) => String(x.id || "") === prev)) expertsSelect.value = prev;
    else if (items.length) expertsSelect.value = String(items[0].id || "");
    fillExpertFields(currentExpertItem());
  }

  secretsMigrateBtn.addEventListener("click", async () => {
    if (!hasPermission("admin:tenant:write")) {
      secretsStatusMsg.textContent = t("secrets.migrateForbidden");
      return;
    }
    secretsMigrateBtn.disabled = true;
    secretsStatusMsg.textContent = "";
    try {
      const res = await apiPost("/admin/api/secrets/migrate", {});
      if (res && res.ok) {
        const s = intOr0(res.migrated_app_settings);
        const p = intOr0(res.migrated_llm_profiles);
        secretsStatusMsg.textContent = (s + p) > 0 ? fmtSecretsDone(s, p) : t("secrets.migrateNoop");
      } else {
        secretsStatusMsg.textContent = String((res && (res.error || res.detail)) || "migrate_failed");
      }
      try {
        secretsStatus = await apiGet("/admin/api/secrets/status");
      } catch (_) {
        secretsStatus = null;
      }
      paintSecretsCard();
    } catch (e) {
      secretsStatusMsg.textContent = String(e.message || e);
      paintSecretsCard();
    } finally {
      secretsMigrateBtn.disabled = false;
    }
  });

  function paintBindings() {
    bindingWrap.innerHTML = "";
    if (!modelsState || !modelsState.bindings) return;
    const profiles = modelsState.profiles || [];
    const profileIds = profiles.map((p) => String(p.id));
    const roleIds = Array.isArray(modelsState.role_ids) ? modelsState.role_ids : [];
    roleIds.forEach((rid) => {
      const sel = el("select", { class: "input", disabled: !canConfigureBindings });
      sel.appendChild(el("option", { value: "", text: t("models.useGlobal") }));
      profiles.forEach((p) => {
        sel.appendChild(el("option", { value: String(p.id), text: labelFor(p.id) }));
      });
      const v = String(modelsState.bindings[rid] || "").trim();
      sel.value = profileIds.includes(v) ? v : "";
      sel.addEventListener("change", async () => {
        if (!canConfigureBindings) return;
        const next = Object.assign({}, modelsState.bindings);
        next[rid] = String(sel.value || "");
        try {
          await apiPost("/admin/api/models/bindings", { bindings: next });
          await refresh();
        } catch (e) {
          status.textContent = String(e.message || e);
        }
      });
      bindingWrap.appendChild(el("div", { class: "row" }, [
        el("label", { text: t("models.role." + rid) + " " }),
        sel,
      ]));
    });
  }

  function paintOpsAiBindings() {
    if (!modelsState || !modelsState.ops_ai_bindings) return;
    const profiles = modelsState.profiles || [];
    const profileIds = profiles.map((p) => String(p.id));
    const roleIds = (Array.isArray(modelsState.role_ids) ? modelsState.role_ids : []).filter((rid) => String(rid || "") !== "manager");

    const curSpecialist = String(opsAiSpecialistSelect.value || "").trim();
    opsAiSpecialistSelect.innerHTML = "";
    roleIds.forEach((rid) => {
      opsAiSpecialistSelect.appendChild(el("option", { value: String(rid), text: t("models.role." + rid) }));
    });
    if (roleIds.includes(curSpecialist)) opsAiSpecialistSelect.value = curSpecialist;
    else if (roleIds.length) opsAiSpecialistSelect.value = roleIds[0];

    const rid = String(opsAiSpecialistSelect.value || "").trim();
    opsAiProfileSelect.innerHTML = "";
    profiles.forEach((p) => {
      opsAiProfileSelect.appendChild(el("option", { value: String(p.id), text: labelFor(p.id) }));
    });
    const v = String((modelsState.ops_ai_bindings && modelsState.ops_ai_bindings[rid]) || "").trim();
    opsAiProfileSelect.value = profileIds.includes(v) ? v : "";
  }

  function paintEval() {
    evalMetrics.innerHTML = "";
    evalTableWrap.innerHTML = "";
    const summary = (evalPack && evalPack.summary) || {};
    const total = intOr0(summary.total);
    const sr = Number(summary.success_rate || 0);
    const p95 = intOr0(summary.p95_latency_ms);
    evalMetrics.appendChild(el("span", { text: `${t("models.evalTotal")}: ${total}  ` }));
    evalMetrics.appendChild(el("span", { text: `${t("models.evalSuccess")}: ${(sr * 100).toFixed(1)}%  ` }));
    evalMetrics.appendChild(el("span", { text: `${t("models.evalP95")}: ${p95} ms` }));
    const logs = Array.isArray(evalPack && evalPack.logs) ? evalPack.logs : [];
    if (!logs.length) {
      evalTableWrap.appendChild(el("div", { class: "muted", text: t("models.noEvalLogs") }));
      return;
    }
    const tbody = el("tbody");
    logs.forEach((r) => {
      tbody.appendChild(el("tr", {}, [
        tdCell(r.timestamp || "", 24),
        tdCell(r.session_id || "", 20),
        tdCell(r.specialist || "", 12),
        tdCell(r.task_kind || "", 14),
        tdCell(r.success ? "1" : "0", 4),
        tdCell(String(r.latency_ms ?? ""), 8),
        tdCell(String(r.notes || ""), 60),
      ]));
    });
    evalTableWrap.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: t("table.timestamp") }),
        el("th", { text: "session_id" }),
        el("th", { text: t("table.specialist") }),
        el("th", { text: "task_kind" }),
        el("th", { text: t("table.status") }),
        el("th", { text: t("table.durationMs") }),
        el("th", { text: "notes" }),
      ])]),
      tbody,
    ])]));
  }

  function intOr0(x) {
    const n = parseInt(String(x), 10);
    return Number.isFinite(n) ? n : 0;
  }

  function paint() {
    if (!modelsState) return;
    if (modelsState.ok !== true) {
      status.textContent = status.textContent || t("models.loadFailed");
      return;
    }
    const profiles = Array.isArray(modelsState.profiles) ? modelsState.profiles : [];
    const builtin = String(modelsState.builtin_ollama_profile_id || "");
    activeSelect.innerHTML = "";
    profiles.forEach((p) => {
      activeSelect.appendChild(el("option", { value: String(p.id), text: labelFor(p.id) }));
    });
    const aid = String(modelsState.active_llm_profile_id || "");
    if (profiles.some((p) => String(p.id) === aid)) activeSelect.value = aid;
    activeSelect.disabled = !canPickActive;
    chatModelSelectorVisibleCb.disabled = !canConfigureChatUi;
    chatModelSelectorVisibleCb.checked = modelsState.chat_model_selector_visible !== false;
    opsAiSpecialistSelect.disabled = !canConfigureBindings;
    opsAiProfileSelect.disabled = !canConfigureBindings;

    paintBindings();
    paintOpsAiBindings();

    const selProf = profiles.find((p) => String(p.id) === aid) || profiles[0] || {};
    const pid = String(selProf.id || "");
    const rowMutable = selProf.mutable !== false;
    const canEditFields = canMutateProfiles && rowMutable;
    readonlyProfileHint.textContent = rowMutable ? "" : t("models.profileReadonlyHint");
    const isBuiltin = pid === builtin;
    profName.value = String(selProf.name || "");
    const rawMode = String(selProf.mode || "openai").toLowerCase();
    const baseAllowedModes = ["openai", "anthropic", "google", "ollama", "rule"];
    const allowedModes = rawMode === "openai_responses" ? ["openai_responses", ...baseAllowedModes] : baseAllowedModes;
    const modeVal = allowedModes.includes(rawMode) ? rawMode : "openai";
    if (isBuiltin) {
      fillModeSelect(modeSel, ["ollama"], "ollama");
      modeSel.disabled = true;
      builtinCap.textContent = t("models.builtinLocked");
    } else {
      modeSel.disabled = !canEditFields;
      builtinCap.textContent = "";
      fillModeSelect(modeSel, allowedModes, modeVal);
    }
    modelInp.value = String(selProf.model || "");
    baseInp.value = String(selProf.base_url || "");
    thinkingModeCb.checked = !!selProf.thinking_mode_enabled;
    reasoningEffortSel.value = String(selProf.reasoning_effort || "");
    keyInp.value = String(modelsState.profile_secret || "");
    rememberCb.checked = !!selProf.has_key;

    profName.disabled = !canEditFields;
    modelInp.disabled = !canEditFields;
    baseInp.disabled = !canEditFields;
    thinkingModeCb.disabled = !canEditFields;
    reasoningEffortSel.disabled = !canEditFields;
    keyInp.disabled = !canEditFields;
    rememberCb.disabled = !canEditFields;

    const m = isBuiltin ? "ollama" : modeVal;
    warnKey.textContent = "";
    openaiHint.textContent = "";
    ollamaHint.textContent = "";
    if (m === "openai" || m === "openai_responses") {
      ollamaHint.textContent = "";
      if (modelsState.has_openai_api_key_env) openaiHint.textContent = t("models.openaiKeyHint");
      if (selProf.has_key && !String(keyInp.value || "").trim()) {
        warnKey.textContent = t("models.warnKeyInDb");
      }
    } else if (m === "google") {
      openaiHint.textContent = "";
      ollamaHint.textContent = "";
    } else if (m === "ollama") {
      ollamaHint.textContent = t("models.ollamaHint");
    }

    btnDelete.disabled = !canMutateProfiles || !rowMutable || pid === builtin;

    modelsGrantsLinkRow.innerHTML = "";
    if (modelsState.can_manage_llm_grants) {
      modelsGrantsLinkRow.style.display = "block";
      modelsGrantsLinkRow.appendChild(el("span", { text: `${t("models.grantsNavHint")} ` }));
      modelsGrantsLinkRow.appendChild(el("a", { href: "#/api-grants", text: t("models.linkApiGrants") }));
    } else {
      modelsGrantsLinkRow.style.display = "none";
    }

    paintEval();
  }

  activeSelect.addEventListener("change", async () => {
    if (!canPickActive) return;
    try {
      await apiPost("/admin/api/models/active", { profile_id: activeSelect.value });
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  });
  chatModelSelectorVisibleCb.addEventListener("change", async () => {
    if (!canConfigureChatUi) return;
    try {
      await apiPost("/admin/api/models/chat-ui", {
        chat_model_selector_visible: !!chatModelSelectorVisibleCb.checked,
      });
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  });
  opsAiSpecialistSelect.addEventListener("change", async () => {
    paintOpsAiBindings();
  });
  opsAiProfileSelect.addEventListener("change", async () => {
    if (!canConfigureBindings) return;
    try {
      const rid = String(opsAiSpecialistSelect.value || "").trim();
      const next = Object.assign({}, (modelsState && modelsState.ops_ai_bindings) || {});
      next[rid] = String(opsAiProfileSelect.value || "");
      await apiPost("/admin/api/models/ops-ai/bindings", { bindings: next });
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  });

  const btnCreate = el("button", { class: "btn btn--primary", text: t("models.createBtn"), onclick: async () => {
    if (!canMutateProfiles) return;
    try {
      await apiPost("/admin/api/models/profiles", {
        name: newName.value.trim() || t("models.newProfileDefault"),
        mode: newMode.value,
      });
      newName.value = "";
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  }});

  const btnSave = el("button", { class: "btn btn--primary", text: t("models.save"), onclick: async () => {
    if (!canMutateProfiles) return;
    const sel = (modelsState.profiles || []).find((p) => String(p.id) === String(modelsState.active_llm_profile_id || ""));
    if (sel && sel.mutable === false) return;
    const pid = String(modelsState.active_llm_profile_id || "");
    const builtin = String(modelsState.builtin_ollama_profile_id || "");
    try {
      let modeSave = modeSel.value;
      if (pid === builtin) modeSave = "ollama";
      await apiRequest("PATCH", "/admin/api/models/profiles/" + encodeURIComponent(pid), {
        name: profName.value.trim() || t("models.newProfileDefault"),
        mode: modeSave,
        model: modelInp.value.trim(),
        base_url: baseInp.value.trim(),
        thinking_mode_enabled: !!thinkingModeCb.checked,
        reasoning_effort: String(reasoningEffortSel.value || ""),
      });
      await apiRequest("POST", "/admin/api/models/profiles/" + encodeURIComponent(pid) + "/secret", {
        remember: rememberCb.checked,
        secret: keyInp.value,
      });
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  }});

  const btnDelete = el("button", { class: "btn btn--danger", text: t("models.delete"), onclick: async () => {
    if (!canMutateProfiles) return;
    const pid = String(modelsState.active_llm_profile_id || "");
    const builtin = String(modelsState.builtin_ollama_profile_id || "");
    if (pid === builtin) {
      status.textContent = t("models.cannotDeleteBuiltin");
      return;
    }
    if (!globalThis.confirm(t("models.deleteConfirm"))) return;
    try {
      await apiRequest("DELETE", "/admin/api/models/profiles/" + encodeURIComponent(pid), {});
      await refresh();
    } catch (e) {
      status.textContent = String(e.message || e);
    }
  }});

  const btnExpertCreate = el("button", {
    class: "btn btn--primary",
    text: "Create expert",
    onclick: async () => {
      if (!hasPermission("admin:tenant:write")) return;
      const eid = String(expertNewId.value || "").trim();
      if (!eid) {
        expertsStatus.textContent = "expert id required";
        return;
      }
      if (!String(expertNewNameEn.value || "").trim()) {
        expertsStatus.textContent = "English name is required";
        return;
      }
      if (!String(expertSoul.value || "").trim() && !String(expertRoleSystem.value || "").trim()) {
        expertsStatus.textContent = "SOUL.md or ROLE_SYSTEM.md is required";
        return;
      }
      try {
        const res = await apiPost("/admin/api/experts", {
          id: eid,
          display_name_en: String(expertNewNameEn.value || "").trim(),
          display_name_zh: String(expertNewNameZh.value || "").trim(),
          role: "expert",
          files: {
            "SOUL.md": expertSoul.value,
            "ROLE_SYSTEM.md": expertRoleSystem.value,
          },
        });
        if (!res || res.ok !== true) throw new Error(String((res && res.error) || "create_failed"));
        expertNewId.value = "";
        expertNewNameEn.value = "";
        expertNewNameZh.value = "";
        expertsStatus.textContent = "expert created";
        markPrewarmReminder("expert_created");
        await refresh();
        expertsSelect.value = String(res.created || "");
        fillExpertFields(currentExpertItem());
      } catch (e) {
        expertsStatus.textContent = String((e && e.message) || e);
      }
    },
  });

  const btnExpertSave = el("button", {
    class: "btn btn--primary",
    text: "Save expert files",
    onclick: async () => {
      if (!hasPermission("admin:tenant:write")) return;
      const item = currentExpertItem();
      if (!item) return;
      if (!String(expertNameEn.value || "").trim()) {
        expertsStatus.textContent = "English name is required";
        return;
      }
      if (!String(expertSoul.value || "").trim() && !String(expertRoleSystem.value || "").trim()) {
        expertsStatus.textContent = "SOUL.md or ROLE_SYSTEM.md is required";
        return;
      }
      try {
        const eid = String(item.id || "");
        const res = await apiRequest("PATCH", "/admin/api/experts/" + encodeURIComponent(eid), {
          display_name_en: String(expertNameEn.value || "").trim(),
          display_name_zh: String(expertNameZh.value || "").trim(),
          role: String(expertRoleSel.value || "expert"),
          files: {
            "SOUL.md": expertSoul.value,
            "ROLE_SYSTEM.md": expertRoleSystem.value,
          },
        });
        if (!res || res.ok !== true) throw new Error(String((res && res.error) || "update_failed"));
        expertsStatus.textContent = "expert saved";
        markPrewarmReminder("expert_updated");
        await refresh();
        expertsSelect.value = eid;
        fillExpertFields(currentExpertItem());
      } catch (e) {
        expertsStatus.textContent = String((e && e.message) || e);
      }
    },
  });

  const btnExpertDelete = el("button", {
    class: "btn btn--danger",
    text: "Delete expert",
    onclick: async () => {
      if (!hasPermission("admin:tenant:write")) return;
      const item = currentExpertItem();
      if (!item) return;
      if (item.builtin || String(item.role || "") === "system") {
        expertsStatus.textContent = "system expert cannot be deleted";
        return;
      }
      const eid = String(item.id || "");
      if (!globalThis.confirm(`Delete expert ${eid}?`)) return;
      try {
        const res = await apiRequest("DELETE", "/admin/api/experts/" + encodeURIComponent(eid), {});
        if (!res || res.ok !== true) throw new Error(String((res && res.error) || "delete_failed"));
        expertsStatus.textContent = "expert deleted";
        markPrewarmReminder("expert_deleted");
        await refresh();
      } catch (e) {
        expertsStatus.textContent = String((e && e.message) || e);
      }
    },
  });

  expertsSelect.addEventListener("change", () => {
    fillExpertFields(currentExpertItem());
  });

  await refresh();

  if (!modelsState) {
    return el("div", {}, [
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("title.models") }),
        el("div", { class: "muted", text: t("models.loadFailed") }),
        el("pre", { class: "pre", text: status.textContent || "" }),
      ]),
    ]);
  }

  if (modelsState.ok === true && Array.isArray(modelsState.profiles) && modelsState.profiles.length === 0) {
    const noProfBody = [
      el("div", { class: "card__title", text: t("title.models") }),
      el("div", { class: "muted", text: t("models.noProfiles") }),
    ];
    if (modelsState.db_path) {
      noProfBody.push(el("div", { class: "muted", text: `${t("models.dbPath")}: ${modelsState.db_path}` }));
    }
    noProfBody.push(status);
    return el("div", {}, [el("div", { class: "card" }, noProfBody)]);
  }

  if (modelsState.ok !== true) {
    return el("div", {}, [
      el("div", { class: "card" }, [
        el("div", { class: "card__title", text: t("title.models") }),
        el("div", { class: "muted", text: t("models.loadFailed") }),
        el("pre", { class: "pre", text: JSON.stringify(modelsState, null, 2) }),
        status,
      ]),
    ]);
  }

  const topBits = [readonlyHint, status, modelsGrantsLinkRow];
  if (modelsState.db_path) {
    topBits.push(el("div", { class: "muted", text: `${t("models.dbPath")}: ${modelsState.db_path}` }));
  }
  // Show secret migration helper when legacy secrets exist.
  topBits.push(secretsCard);

  return renderPageShell({
    title: t("title.models"),
    subtitle: t("models.subtitle"),
    sections: [
      { id: "models-overview", label: t("models.toc.overview") },
      { id: "models-bindings", label: t("models.toc.bindings") },
      { id: "models-ops-ai", label: t("models.toc.opsAi") },
      { id: "models-api", label: t("models.toc.api") },
      { id: "models-experts", label: "Experts" },
      { id: "models-eval", label: t("models.toc.eval") },
    ],
  }, [
    ...topBits,
    el("div", { class: "page-grid page-grid--two" }, [
      renderSectionCard(t("models.sectionActive"), "", [
        el("div", { class: "row" }, [el("label", { text: t("models.pickModel") }), activeSelect]),
        el("div", { class: "row" }, [el("label", { text: t("models.chatModelSelector") }), chatModelSelectorVisibleCb]),
        el("div", { class: "muted", text: t("models.chatModelSelectorHint") }),
      ], { id: "models-overview" }),
      renderSectionCard(t("models.sectionNew"), "", [
        el("div", { class: "row" }, [el("label", { text: t("models.profileName") }), newName]),
        el("div", { class: "row" }, [el("label", { text: t("models.mode") }), newMode]),
        el("div", { class: "row" }, [btnCreate]),
      ]),
    ]),
    renderSectionCard(t("models.sectionBindings"), t("models.agentBindingHelp"), [
      el("div", { class: "muted", text: t("models.bindingsExtraHint") }),
      el("div", { class: "muted", text: t("models.bindingsScopeHint") }),
      bindingWrap,
    ], { id: "models-bindings" }),
    renderSectionCard(t("models.opsAiTitle"), t("models.opsAiHint"), [
      el("div", { class: "row" }, [el("label", { text: t("models.labelSpecialist") }), opsAiSpecialistSelect]),
      el("div", { class: "row" }, [el("label", { text: t("models.labelApiProfile") }), opsAiProfileSelect]),
    ], { id: "models-ops-ai" }),
    renderSectionCard(t("models.sectionApi"), "", [
      builtinCap,
      readonlyProfileHint,
      el("div", { class: "row" }, [el("label", { text: t("models.profileName") }), profName]),
      el("div", { class: "row" }, [el("label", { text: t("models.mode") }), modeSel]),
      el("div", { class: "row" }, [el("label", { text: t("models.model") }), modelInp]),
      el("div", { class: "row" }, [el("label", { text: t("models.baseUrl") }), baseInp]),
      el("div", { class: "row" }, [el("label", { text: t("models.thinkMode") }), thinkingModeCb]),
      el("div", { class: "muted", text: t("models.thinkModeHint") }),
      el("div", { class: "row" }, [el("label", { text: t("models.reasoningEffort") }), reasoningEffortSel]),
      warnKey,
      openaiHint,
      ollamaHint,
      el("div", { class: "row" }, [el("label", { text: t("models.apiKey") }), keyInp]),
      el("div", { class: "row" }, [el("label", { text: t("models.rememberKey") }), rememberCb]),
      el("div", { class: "row" }, [btnSave]),
      el("div", { class: "row" }, [btnDelete]),
    ], { id: "models-api" }),
    renderSectionCard("Experts", "Runtime registry and workspace prompt files are split into two sections below.", [
      el("div", { class: "card u-pad-block" }, [
        el("div", { class: "card__title", text: "Runtime Expert Registry" }),
        el("div", { class: "row" }, [el("label", { text: "Existing" }), expertsSelect]),
        el("div", { class: "row" }, [btnExpertDelete]),
        el("div", { class: "row" }, [el("label", { text: "Create ID" }), expertNewId]),
        el("div", { class: "row" }, [el("label", { text: "Create Name(en)" }), expertNewNameEn]),
        el("div", { class: "row" }, [el("label", { text: "Create Name(zh)" }), expertNewNameZh]),
        el("div", { class: "row" }, [btnExpertCreate]),
        el("div", { class: "row" }, [el("label", { text: "Name(en)" }), expertNameEn]),
        el("div", { class: "row" }, [el("label", { text: "Name(zh)" }), expertNameZh]),
        el("div", { class: "row" }, [el("label", { text: "Role" }), expertRoleSel]),
      ]),
      el("div", { class: "card u-pad-block" }, [
        el("div", { class: "card__title", text: "Workspace Prompt Files" }),
        el("div", { class: "muted", text: "SOUL.md or ROLE_SYSTEM.md is required." }),
        el("div", { class: "row" }, [el("label", { text: "SOUL.md" }), expertSoul]),
        el("div", { class: "row" }, [el("label", { text: "ROLE_SYSTEM.md" }), expertRoleSystem]),
        el("div", { class: "row" }, [btnExpertSave]),
      ]),
      expertsStatus,
    ], { id: "models-experts" }),
    el("div", { class: "card section-card u-hidden", id: "models-eval" }, [evalDetails]),
  ]);
}

const PLUGINS_PAGE_SIZE = 15;


export { renderModels };
