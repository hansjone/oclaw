import { t, tf, el, apiGet, apiPost, assertSkillMutationOk, shortText, renderPageShell, rowActions } from "../core.js";

function skillsFold(summaryText, innerNodes) {
  const det = el("details", { class: "details plugins-fold" });
  det.appendChild(el("summary", { text: summaryText }));
  const inner = el("div", { class: "plugins-fold__inner" });
  inner.addEventListener("click", (e) => e.stopPropagation());
  (innerNodes || []).forEach((n) => inner.appendChild(n));
  det.appendChild(inner);
  return det;
}

async function renderSkills() {
  document.querySelectorAll("[data-skill-modal]").forEach((n) => n.remove());
  document.querySelectorAll("body > .row-actions__menu, body > .chat-sess-menu-pop.row-actions__menu").forEach((n) => n.remove());
  const SKILL_AUDIT_RETRYABLE_ONLY_KEY = "ops_admin_skill_audit_retryable_only";
  const status = el("div", { class: "muted", text: "" });
  const rowsState = { items: [] };
  const auditState = { items: [] };
  const nameInp = el("input", { class: "input", placeholder: t("skills.ph.name") });
  const descInp = el("input", { class: "input", placeholder: t("skills.ph.description") });
  const bodyInp = el("textarea", { class: "input", rows: "4", placeholder: t("skills.ph.body") });
  const regInp = el("input", { class: "input", placeholder: t("skills.ph.registry") });
  const localDirInp = el("input", { class: "input", placeholder: t("skills.ph.localDir") });
  const marketStatus = el("div", { class: "muted", text: "" });
  const skillModeStatus = el("div", { class: "muted", text: "" });
  const skillPromptModeCb = el("input", { type: "checkbox" });
  const marketQ = el("input", { class: "input", placeholder: t("skills.ph.marketSearch") });
  const marketLimitInp = el("input", {
    class: "input",
    placeholder: t("skills.ph.limit"),
    value: "40",
    style: "max-width:120px;",
  });
  const marketTbody = el("tbody");
  const marketDetailPre = el("pre", { class: "muted pre", text: "" });
  let marketItems = [];

  const loadSkillMode = async () => {
    try {
      const r = await apiGet("/admin/api/skills/mode");
      skillPromptModeCb.checked = !!r.prompt_in_system;
      skillModeStatus.textContent = "";
    } catch (e) {
      skillModeStatus.textContent = `mode: ${String(e && e.message ? e.message : e)}`;
    }
  };
  const saveSkillMode = async () => {
    skillModeStatus.textContent = `${t("chat.loading")}...`;
    try {
      const r = await apiPost("/admin/api/skills/mode", {
        prompt_in_system: !!skillPromptModeCb.checked,
        market_provider: "clawhub",
      });
      skillPromptModeCb.checked = !!r.prompt_in_system;
      skillModeStatus.textContent = `saved: prompt=${String(!!r.prompt_in_system)} market=clawhub`;
    } catch (e) {
      skillModeStatus.textContent = `mode: ${String(e && e.message ? e.message : e)}`;
    }
  };

  const loadMarket = async (q) => {
    const qq = String(q || "").trim();
    const lim = Math.max(1, Math.min(200, parseInt(String(marketLimitInp.value || "40"), 10) || 40));
    marketStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet(
        `/admin/api/skills/market/search?q=${encodeURIComponent(qq)}&limit=${encodeURIComponent(String(lim))}`,
      );
      marketItems = Array.isArray(resp.items) ? resp.items : [];
      marketStatus.textContent = `results: ${marketItems.length}`;
      repaintMarket();
    } catch (e) {
      marketItems = [];
      marketStatus.textContent = `${t("common.error")}: ${String(e && e.message ? e.message : e)}`;
      repaintMarket();
    }
  };

  const loadMarketDetail = async (slug) => {
    const s = String(slug || "").trim();
    if (!s) return;
    marketDetailPre.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet(`/admin/api/skills/market/detail?slug=${encodeURIComponent(s)}`);
      marketDetailPre.textContent = JSON.stringify(resp.detail || {}, null, 2);
    } catch (e) {
      marketDetailPre.textContent = `${t("common.error")}: ${String(e && e.message ? e.message : e)}`;
    }
  };

  const installFromMarket = async (slug, version) => {
    const s = String(slug || "").trim();
    if (!s) return;
    marketStatus.textContent = `installing: ${s}...`;
    openSkillInstallModal(`Installing ${s}...`);
    try {
      const r = await apiPost("/admin/api/skills/market/install", {
        slug: s,
        version: version ? String(version) : undefined,
        overwrite: false,
      });
      assertSkillMutationOk(r, "Market install failed");
      status.textContent = `install-market success: ${JSON.stringify(r.result || {})}`;
      marketStatus.textContent = `installed: ${s}`;
      await refreshSkillsState();
      finishSkillInstallModal(true, `${s} installed successfully.`);
    } catch (e) {
      status.textContent = String(e && e.message ? e.message : e);
      marketStatus.textContent = `install failed: ${s}`;
      finishSkillInstallModal(false, `Install failed: ${String(e && e.message ? e.message : e)}`);
    }
  };

  const repaintMarket = () => {
    marketTbody.innerHTML = "";
    (marketItems || []).forEach((x) => {
      const slug = String(x.slug || "");
      const ver = String(x.version || "");
      const btnDetail = el("button", {
        class: "btn btn--small",
        text: t("skills.action.detail"),
        onclick: async () => await loadMarketDetail(slug),
      });
      const btnInstall = el("button", {
        class: "btn btn--small btn--primary",
        text: t("skills.action.install"),
        onclick: async () => await installFromMarket(slug, ver),
      });
      marketTbody.appendChild(
        el("tr", {}, [
          el("td", { text: slug }),
          el("td", { text: String(x.name || "") }),
          el("td", { text: ver }),
          el("td", { text: shortText(String(x.description || ""), 80) }),
          el("td", { class: "table__cell--actions", "data-copy-disabled": "1" }, [
            el("div", { class: "table__cell-actions" }, [btnInstall, btnDetail]),
          ]),
        ]),
      );
    });
  };

  const btnMarketSearch = el("button", {
    class: "btn",
    text: t("skills.action.search"),
    onclick: async () => await loadMarket(marketQ.value),
  });
  const btnMarketLatest = el("button", {
    class: "btn",
    text: t("skills.action.latest"),
    onclick: async () => await loadMarket(""),
  });

  // --- Binding ---
  const skillBindingState = { roles: [], names: [], mapping: {}, enabled: false };
  const skillBindingStatus = el("div", { class: "muted", text: "" });
  const skillBindingPersistHint = el("div", {
    class: "muted",
    style: "margin:6px 0;line-height:1.5;",
    text: t("skills.hint.bindingPersist"),
  });
  const skillBindingEnvHint = el("div", {
    class: "muted",
    style: "margin:6px 0;line-height:1.5;display:none;",
  });
  const skillEffectiveState = { items: [] };
  const skillBindingEnabledCb = el("input", { type: "checkbox" });
  const skillRoleSelect = el("select", { class: "input" }, []);
  const skillBindingListWrap = el("div");
  const skillBindingDashTbody = el("tbody");
  const skillEffectiveTbody = el("tbody");

  const renderSkillBindingDashboard = () => {
    skillBindingDashTbody.innerHTML = "";
    const roles = Array.isArray(skillBindingState.roles) ? skillBindingState.roles : [];
    const mapping = skillBindingState.mapping && typeof skillBindingState.mapping === "object" ? skillBindingState.mapping : {};
    roles.forEach((role) => {
      const direct = new Set(Array.isArray(mapping[role]) ? mapping[role].map((x) => String(x)) : []);
      const effective = new Set(Array.from(direct));
      skillBindingDashTbody.appendChild(
        el("tr", {}, [
          el("td", { text: role }),
          el("td", { text: String(direct.size) }),
          el("td", { text: String(effective.size) }),
        ]),
      );
    });
    if (!roles.length) {
      skillBindingDashTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "3" })]));
    }
  };

  const renderSkillEffectiveDashboard = () => {
    skillEffectiveTbody.innerHTML = "";
    const rows = Array.isArray(skillEffectiveState.items) ? skillEffectiveState.items : [];
    rows.forEach((x) => {
      const names = Array.isArray(x.names_preview)
        ? x.names_preview.map((v) => String(v || "").trim()).filter(Boolean)
        : [];
      const docsOnlyNames = Array.isArray(x.docs_only_names_preview)
        ? x.docs_only_names_preview.map((v) => String(v || "").trim()).filter(Boolean)
        : [];
      const previewText = names.slice(0, 6).join(", ");
      const namesCell = names.length
        ? el("details", {}, [
            el("summary", { text: previewText || "(empty)" }),
            el("div", { class: "muted u-mt-4 u-wrap-lh", text: names.join(", ") }),
          ])
        : el("span", { class: "muted", text: "-" });
      const docsOnlyCell = docsOnlyNames.length
        ? el("details", {}, [
            el("summary", { text: docsOnlyNames.slice(0, 4).join(", ") }),
            el("div", { class: "muted u-mt-4 u-wrap-lh", text: docsOnlyNames.join(", ") }),
          ])
        : el("span", { class: "muted", text: "-" });
      skillEffectiveTbody.appendChild(
        el("tr", {}, [
          el("td", { text: String(x.role || "") }),
          el("td", { text: String(x.total || 0) }),
          el("td", { text: String(x.workspace_total || 0) }),
          el("td", { text: String(x.workspace_direct || 0) }),
          el("td", { text: String(x.workspace_resolved_tool_match || 0) }),
          el("td", { text: String(x.workspace_docs_only || 0) }),
          el("td", { text: String(x.mcp_total || 0) }),
          el("td", { text: String(x.tool_total || 0) }),
          el("td", {}, [docsOnlyCell]),
          el("td", {}, [namesCell]),
        ]),
      );
    });
    if (!rows.length) {
      skillEffectiveTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "10" })]));
    }
  };

  const loadSkillEffective = async () => {
    try {
      const r = await apiGet("/admin/api/skills/effective");
      skillEffectiveState.items = Array.isArray(r.items) ? r.items : [];
      renderSkillEffectiveDashboard();
    } catch (e) {
      skillEffectiveState.items = [];
      renderSkillEffectiveDashboard();
      skillBindingStatus.textContent = `effective: ${String(e && e.message ? e.message : e)}`;
    }
  };

  const renderSkillBindingList = () => {
    const current = String(skillRoleSelect.value || "");
    const draft = skillBindingState.mapping;
    const existing = Array.isArray(draft[current]) ? draft[current].map((x) => String(x)) : [];
    const selected = new Set(existing);
    skillBindingListWrap.innerHTML = "";
    const skills =
      skillBindingState.names.length > 0
        ? skillBindingState.names
        : Array.isArray(rowsState.items)
          ? rowsState.items.map((x) => String(x.name || "").trim()).filter(Boolean)
          : [];
    if (!skills.length) {
      skillBindingListWrap.appendChild(el("div", { class: "muted", text: t("skills.hint.noSkills") }));
      return;
    }
    skills.forEach((nm) => {
      const cb = el("input", { type: "checkbox" });
      cb.checked = selected.has(nm);
      cb.addEventListener("change", () => {
        const prev = new Set(Array.isArray(draft[current]) ? draft[current].map((x) => String(x)) : []);
        if (cb.checked) prev.add(nm);
        else prev.delete(nm);
        draft[current] = Array.from(prev);
      });
      skillBindingListWrap.appendChild(el("label", { class: "row u-row-center" }, [cb, el("span", { text: nm })]));
    });
  };

  const applyBindingEnvHint = (r) => {
    if (r && r.enabled_env_present) {
      skillBindingEnvHint.style.display = "block";
      const stored = !!r.enabled_stored;
      const eff = !!r.enabled;
      skillBindingEnvHint.textContent = tf("skills.hint.bindingEnv", {
        stored: String(stored),
        effective: String(eff),
      });
    } else {
      skillBindingEnvHint.style.display = "none";
      skillBindingEnvHint.textContent = "";
    }
  };

  const loadSkillBinding = async () => {
    try {
      const r = await apiGet("/admin/api/skills/binding");
      skillBindingState.roles = Array.isArray(r.available_roles) ? r.available_roles : [];
      skillBindingState.names = (Array.isArray(r.installed_skills) ? r.installed_skills : [])
        .map((x) => String(x.name || "").trim())
        .filter(Boolean);
      skillBindingState.mapping = r.mapping && typeof r.mapping === "object" ? { ...r.mapping } : {};
      skillBindingState.enabled = !!r.enabled;
      skillBindingEnabledCb.checked = skillBindingState.enabled;
      applyBindingEnvHint(r);
      skillRoleSelect.innerHTML = "";
      skillBindingState.roles.forEach((role) => {
        skillRoleSelect.appendChild(el("option", { value: role, text: role }));
      });
      if (skillBindingState.roles.length && !skillRoleSelect.value) {
        skillRoleSelect.value = skillBindingState.roles[0];
      }
      renderSkillBindingList();
      renderSkillBindingDashboard();
      await loadSkillEffective();
      skillBindingStatus.textContent = "";
    } catch (e) {
      skillBindingStatus.textContent = `binding: ${String(e && e.message ? e.message : e)}`;
      skillBindingListWrap.innerHTML = "";
    }
  };
  skillRoleSelect.addEventListener("change", () => renderSkillBindingList());

  const btnSaveSkillBinding = el("button", {
    class: "btn btn--primary",
    text: t("skills.action.saveBinding"),
    onclick: async () => {
      try {
        const r = await apiPost("/admin/api/skills/binding", {
          enabled: !!skillBindingEnabledCb.checked,
          mapping: skillBindingState.mapping,
        });
        skillBindingState.mapping = r.mapping && typeof r.mapping === "object" ? { ...r.mapping } : {};
        skillBindingState.enabled = !!r.enabled;
        skillBindingEnabledCb.checked = skillBindingState.enabled;
        applyBindingEnvHint(r);
        skillBindingStatus.textContent = `saved: enabled=${String(r.enabled)}`;
        renderSkillBindingList();
        renderSkillBindingDashboard();
        await loadSkillEffective();
      } catch (e) {
        skillBindingStatus.textContent = String(e && e.message ? e.message : e);
      }
    },
  });

  // --- Diagnostics: internal tools ---
  const internalToolsState = { role: "", available_roles: [], tools: [], skipped_public: [], skipped_expert: [] };
  const lazyLoadState = { internalLoaded: false, llmLoaded: false, selfCheckLoaded: false, skillHealthLoaded: false };
  const internalToolsStatus = el("div", { class: "muted", text: "" });
  const internalRoleSelect = el("select", { class: "input" }, []);
  const internalToolsTbody = el("tbody");
  const internalSkippedPre = el("pre", { class: "muted pre", text: "" });

  const renderInternalTools = () => {
    internalToolsTbody.innerHTML = "";
    const rows = Array.isArray(internalToolsState.tools) ? internalToolsState.tools : [];
    rows.forEach((x) => {
      internalToolsTbody.appendChild(
        el("tr", {}, [
          el("td", { text: String(x.source || "") }),
          el("td", { text: String(x.name || "") }),
          el("td", { text: shortText(String(x.description || ""), 120) }),
          el("td", { text: String((Array.isArray(x.tags) ? x.tags.join(", ") : x.tags) || "") }),
          el("td", { text: String(x.read_only ? "1" : "0") }),
          el("td", { text: String(x.risk_level || "") }),
        ]),
      );
    });
    if (!rows.length) {
      internalToolsTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "6" })]));
    }
    internalSkippedPre.textContent = JSON.stringify(
      {
        skipped_public: Array.isArray(internalToolsState.skipped_public) ? internalToolsState.skipped_public : [],
        skipped_expert: Array.isArray(internalToolsState.skipped_expert) ? internalToolsState.skipped_expert : [],
      },
      null,
      2,
    );
  };

  const loadInternalToolsPreview = async (role) => {
    const r = String(role || internalRoleSelect.value || "").trim();
    if (!r) return;
    internalToolsStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet(`/admin/api/tools/internal/preview?role=${encodeURIComponent(r)}`);
      internalToolsState.role = String(resp.role || "");
      internalToolsState.available_roles = Array.isArray(resp.available_roles) ? resp.available_roles : [];
      internalToolsState.tools = Array.isArray(resp.tools) ? resp.tools : [];
      internalToolsState.skipped_public = Array.isArray(resp.skipped_public) ? resp.skipped_public : [];
      internalToolsState.skipped_expert = Array.isArray(resp.skipped_expert) ? resp.skipped_expert : [];
      internalToolsStatus.textContent = `role=${internalToolsState.role} tools=${internalToolsState.tools.length}`;
      renderInternalTools();
    } catch (e) {
      internalToolsState.tools = [];
      internalToolsStatus.textContent = `preview: ${String(e && e.message ? e.message : e)}`;
      renderInternalTools();
    }
  };

  const btnInternalPreview = el("button", {
    class: "btn btn--primary",
    text: t("skills.action.preview"),
    onclick: async () => await loadInternalToolsPreview(internalRoleSelect.value),
  });

  const internalToolsInner = [
    el("div", { class: "muted u-muted-block-lg", text: t("skills.hint.internalTools") }),
    internalToolsStatus,
    el("div", { class: "row u-row-wrap-mt" }, [
      el("label", { text: t("skills.label.role") }),
      internalRoleSelect,
      btnInternalPreview,
      el("button", {
        class: "btn",
        text: t("skills.action.clearCache"),
        onclick: async () => {
          try {
            await apiPost("/admin/api/tools/internal/reload", {});
            internalToolsStatus.textContent = "cache cleared";
            await loadInternalToolsPreview(internalRoleSelect.value);
          } catch (e) {
            internalToolsStatus.textContent = `reload: ${String(e && e.message ? e.message : e)}`;
          }
        },
      }),
    ]),
    el("div", { class: "table-wrap u-mt-8" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("skills.col.source") }),
            el("th", { text: t("skills.col.name") }),
            el("th", { text: t("skills.col.description") }),
            el("th", { text: t("skills.col.tags") }),
            el("th", { text: t("skills.col.readOnly") }),
            el("th", { text: t("skills.col.risk") }),
          ]),
        ]),
        internalToolsTbody,
      ]),
    ]),
    el("div", { class: "muted u-mt-8", text: t("skills.hint.skippedModules") }),
    internalSkippedPre,
  ];
  const internalToolsBox = skillsFold(t("skills.fold.internalTools"), internalToolsInner);

  // --- Diagnostics: LLM tools ---
  const llmToolsState = { role: "", tools_raw: [], tools_wired: [], removed_mcp_names: [], meta: {} };
  const llmToolsStatus = el("div", { class: "muted", text: "" });
  const llmRoleSelect = el("select", { class: "input" }, []);
  const llmTracePlanCb = el("input", { type: "checkbox" });
  const llmToolsTbody = el("tbody");
  const llmRemovedPre = el("pre", { class: "muted pre", text: "" });
  const llmModeBadge = el("span", { class: "badge badge--mode-restricted", text: "restricted" });
  const llmDiffPre = el("pre", { class: "muted pre", text: "" });
  const llmDiffTbody = el("tbody");
  const llmDiffTableWrap = el("div", { class: "table-wrap u-mt-8" }, [
    el("table", { class: "table table--compact" }, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", { text: t("skills.col.type") }),
          el("th", { text: t("skills.col.name") }),
          el("th", { text: t("skills.col.kind") }),
          el("th", { text: t("skills.col.details") }),
        ]),
      ]),
      llmDiffTbody,
    ]),
  ]);

  // --- Diagnostics: tools self-check ---
  const selfCheckStatus = el("div", { class: "muted", text: "" });
  const selfCheckSummary = el("div", { class: "muted", text: "" });
  const selfCheckTbody = el("tbody");
  const selfCheckState = { data: null };

  const renderSelfCheck = (data) => {
    const body = data && typeof data === "object" ? data : {};
    selfCheckState.data = body;
    const summary = body.summary && typeof body.summary === "object" ? body.summary : {};
    const rolesTotal = Number(body.roles_total || 0);
    const totalInternal = Number(summary.total_internal_tools || 0);
    const totalWired = Number(summary.total_wired_tools || 0);
    const items = Array.isArray(body.items) ? body.items : [];
    selfCheckSummary.textContent = `roles=${rolesTotal} internal=${totalInternal} wired=${totalWired}`;
    selfCheckTbody.innerHTML = "";
    items.forEach((x) => {
      const removedMcp = Number(x.removed_mcp_total || 0);
      const wired = Number(x.wired_count || 0);
      const mode = String(x.role_mode || "restricted");
      let health = "ok";
      if (mode === "forbidden" && wired === 0) health = "forbidden";
      else if (mode === "unrestricted") health = "unrestricted";
      else if (removedMcp > 0) health = "warning";
      const badgeCls =
        health === "warning"
          ? "badge badge--mode-restricted"
          : health === "forbidden"
            ? "badge badge--bad"
            : health === "unrestricted"
              ? "badge badge--mode-unrestricted"
              : "badge badge--ok";
      selfCheckTbody.appendChild(
        el("tr", {}, [
          el("td", { text: String(x.role || "") }),
          el("td", {}, [el("span", { class: badgeCls, text: health })]),
          el("td", { text: String(x.role_mode || "") }),
          el("td", { text: String(x.internal_count || 0) }),
          el("td", { text: String(x.raw_count || 0) }),
          el("td", { text: String(x.wired_count || 0) }),
          el("td", { text: String(x.removed_mcp_total || 0) }),
        ]),
      );
    });
    if (!items.length) selfCheckTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "8" })]));
  };

  const runSelfCheck = async () => {
    selfCheckStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet("/admin/api/tools/self-check");
      renderSelfCheck(resp);
      selfCheckStatus.textContent = "self-check complete";
    } catch (e) {
      selfCheckStatus.textContent = `self-check: ${String(e && e.message ? e.message : e)}`;
      renderSelfCheck({});
    }
  };

  const exportSelfCheckJson = () => {
    const data = selfCheckState.data;
    if (!data || typeof data !== "object") {
      selfCheckStatus.textContent = "no self-check data to export";
      return;
    }
    try {
      const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const a = document.createElement("a");
      a.href = url;
      a.download = `tools-self-check-${ts}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      selfCheckStatus.textContent = "self-check exported";
    } catch (e) {
      selfCheckStatus.textContent = `export failed: ${String(e && e.message ? e.message : e)}`;
    }
  };

  const selfCheckInner = [
    el("div", { class: "muted u-muted-block-lg", text: t("skills.hint.toolsSelfCheck") }),
    selfCheckStatus,
    el("div", { class: "row u-row-center-mt" }, [
      el("button", { class: "btn btn--primary", text: t("skills.action.runSelfCheck"), onclick: runSelfCheck }),
      el("button", { class: "btn", text: t("skills.action.exportSelfCheck"), onclick: exportSelfCheckJson }),
      selfCheckSummary,
    ]),
    el("div", { class: "table-wrap u-mt-8" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("skills.col.role") }),
            el("th", { text: t("skills.col.health") }),
            el("th", { text: t("skills.col.mode") }),
            el("th", { text: t("skills.col.internal") }),
            el("th", { text: t("skills.col.raw") }),
            el("th", { text: t("skills.col.wired") }),
            el("th", { text: t("skills.col.removedMcp") }),
          ]),
        ]),
        selfCheckTbody,
      ]),
    ]),
  ];
  const selfCheckBox = skillsFold(t("skills.fold.toolsSelfCheck"), selfCheckInner);

  // --- Diagnostics: skills health ---
  const skillHealthStatus = el("div", { class: "muted", text: "" });
  const skillHealthSummary = el("div", { class: "muted", text: "" });
  const skillHealthClassifyTbody = el("tbody");
  const skillHealthExecTbody = el("tbody");
  const skillHealthFailedOnlyCb = el("input", { type: "checkbox" });
  const skillHealthState = { data: null };

  const renderSkillHealthExecRows = () => {
    const body = skillHealthState.data && typeof skillHealthState.data === "object" ? skillHealthState.data : {};
    const checks = Array.isArray(body.execution_checks) ? body.execution_checks : [];
    const failedOnly = !!skillHealthFailedOnlyCb.checked;
    skillHealthExecTbody.innerHTML = "";
    checks
      .filter((x) => (failedOnly ? !x.ok : true))
      .slice(0, 30)
      .forEach((x) => {
        const ok = !!x.ok;
        const code = String(x.error_code || "");
        const truncated = !!x.output_truncated;
        skillHealthExecTbody.appendChild(
          el("tr", {}, [
            el("td", { text: String(x.name || "") }),
            el("td", {}, [
              ok
                ? el("span", { class: "badge badge--ok", text: "ok" })
                : el("span", { class: "badge badge--bad", text: "fail" }),
            ]),
            el("td", { text: code || "-" }),
            el("td", { text: truncated ? "1" : "0" }),
            el("td", {}, [
              el("button", {
                class: "btn",
                text: t("skills.action.testRunArgs"),
                disabled: !String(x.name || "").trim(),
                onclick: () => {
                  const nm = String(x.name || "").trim();
                  if (!nm) return;
                  openSkillTestRunModal(nm);
                },
              }),
            ]),
          ]),
        );
      });
    if (!skillHealthExecTbody.children.length) {
      skillHealthExecTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "5" })]));
    }
  };

  const renderSkillHealthCheck = (data) => {
    const body = data && typeof data === "object" ? data : {};
    skillHealthState.data = body;
    const counts = body.classification_counts && typeof body.classification_counts === "object" ? body.classification_counts : {};
    const skillsTotal = Number(body.skills_total || 0);
    const execTotal = Number(body.executable_total || 0);
    const checked = Number(body.execution_checked_total || 0);
    skillHealthSummary.textContent = `skills=${skillsTotal} executable=${execTotal} checked=${checked}`;
    skillHealthClassifyTbody.innerHTML = "";
    const countRows = Object.entries(counts).sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0));
    countRows.forEach(([k, v]) => {
      skillHealthClassifyTbody.appendChild(
        el("tr", {}, [el("td", { text: String(k || "") }), el("td", { text: String(Number(v || 0)) })]),
      );
    });
    if (!countRows.length) {
      skillHealthClassifyTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "2" })]));
    }
    renderSkillHealthExecRows();
  };
  skillHealthFailedOnlyCb.addEventListener("change", () => renderSkillHealthExecRows());

  const runSkillHealthCheck = async () => {
    skillHealthStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet("/admin/api/skills/self-check?include_execution=true");
      renderSkillHealthCheck(resp);
      skillHealthStatus.textContent = "skill self-check complete";
    } catch (e) {
      skillHealthStatus.textContent = `skill self-check: ${String(e && e.message ? e.message : e)}`;
      renderSkillHealthCheck({});
    }
  };

  const exportSkillHealthJson = () => {
    const data = skillHealthState.data;
    if (!data || typeof data !== "object") {
      skillHealthStatus.textContent = "no skills self-check data to export";
      return;
    }
    try {
      const blob = new Blob([`${JSON.stringify(data, null, 2)}\n`], { type: "application/json;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const ts = new Date().toISOString().replace(/[:.]/g, "-");
      const a = document.createElement("a");
      a.href = url;
      a.download = `skills-self-check-${ts}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      skillHealthStatus.textContent = "skills self-check exported";
    } catch (e) {
      skillHealthStatus.textContent = `export failed: ${String(e && e.message ? e.message : e)}`;
    }
  };

  const skillHealthInner = [
    el("div", { class: "muted u-muted-block-lg", text: t("skills.hint.skillHealth") }),
    skillHealthStatus,
    el("div", { class: "row u-row-center-mt" }, [
      el("button", {
        class: "btn btn--primary",
        text: t("skills.action.runSkillHealth"),
        onclick: runSkillHealthCheck,
      }),
      el("button", {
        class: "btn",
        text: t("skills.action.exportSkillHealth"),
        onclick: exportSkillHealthJson,
      }),
      el("label", { class: "row u-row-center" }, [
        skillHealthFailedOnlyCb,
        el("span", { class: "muted", text: t("skills.action.failedOnly") }),
      ]),
      skillHealthSummary,
    ]),
    el("div", { class: "row", style: "gap:12px;align-items:flex-start;flex-wrap:wrap;margin-top:8px;" }, [
      el("div", { class: "table-wrap", style: "min-width:280px;flex:1;" }, [
        el("div", { class: "muted u-mb-6", text: "classification_counts" }),
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [
            el("tr", {}, [el("th", { text: t("skills.col.code") }), el("th", { text: t("skills.col.count") })]),
          ]),
          skillHealthClassifyTbody,
        ]),
      ]),
      el("div", { class: "table-wrap", style: "min-width:360px;flex:2;" }, [
        el("div", { class: "muted u-mb-6", text: "execution_checks (top 30)" }),
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: t("skills.col.skill") }),
              el("th", { text: t("skills.col.status") }),
              el("th", { text: t("skills.col.errorCode") }),
              el("th", { text: t("skills.col.outputTruncated") }),
              el("th", { text: t("skills.col.action") }),
            ]),
          ]),
          skillHealthExecTbody,
        ]),
      ]),
    ]),
  ];
  const skillHealthBox = skillsFold(t("skills.fold.health"), skillHealthInner);

  const _renderLLMToolRows = (tools) => {
    llmToolsTbody.innerHTML = "";
    const rows = Array.isArray(tools) ? tools : [];
    rows.forEach((ent) => {
      const fn = ent && typeof ent === "object" ? ent.function : null;
      const name = fn && typeof fn === "object" ? String(fn.name || "") : "";
      const desc = fn && typeof fn === "object" ? String(fn.description || "") : "";
      const params = fn && typeof fn === "object" ? fn.parameters : null;
      llmToolsTbody.appendChild(
        el("tr", {}, [
          el("td", { text: name }),
          el("td", { text: shortText(desc, 140) }),
          el("td", { text: name.startsWith("mcp__") ? "mcp" : "internal" }),
          el("td", { text: params ? shortText(JSON.stringify(params), 120) : "" }),
        ]),
      );
    });
    if (!rows.length) {
      llmToolsTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "4" })]));
    }
  };

  const loadLLMToolsPreview = async (role) => {
    const r = String(role || llmRoleSelect.value || "").trim();
    if (!r) return;
    llmToolsStatus.textContent = `${t("chat.loading")}...`;
    try {
      const resp = await apiGet(`/admin/api/tools/llm/preview?role=${encodeURIComponent(r)}`);
      llmToolsState.role = String(resp.role || "");
      llmToolsState.tools_raw = Array.isArray(resp.tools_raw) ? resp.tools_raw : [];
      llmToolsState.tools_wired = Array.isArray(resp.tools_wired) ? resp.tools_wired : [];
      llmToolsState.removed_mcp_names = Array.isArray(resp.removed_mcp_names) ? resp.removed_mcp_names : [];
      llmToolsState.meta = resp && typeof resp === "object" ? resp : {};
      const mode = String(resp.role_mode || "restricted");
      llmModeBadge.textContent = mode;
      llmModeBadge.className = `badge badge--mode-${mode}`;
      llmToolsStatus.textContent = `role=${llmToolsState.role} raw=${llmToolsState.tools_raw.length} wired=${llmToolsState.tools_wired.length} mcp_enabled=${String(!!resp.mcp_enabled)}`;
      llmRemovedPre.textContent = JSON.stringify(
        {
          removed_mcp_names: llmToolsState.removed_mcp_names,
          role_mode: resp.role_mode,
          skipped_public: resp.skipped_public || [],
          skipped_expert: resp.skipped_expert || [],
        },
        null,
        2,
      );
      const _toMap = (arr) => {
        const m = new Map();
        (Array.isArray(arr) ? arr : []).forEach((ent) => {
          const fn = ent && typeof ent === "object" ? ent.function : null;
          const nm = fn && typeof fn === "object" ? String(fn.name || "") : "";
          if (!nm) return;
          const desc = fn && typeof fn === "object" ? String(fn.description || "") : "";
          const params = fn && typeof fn === "object" ? fn.parameters : null;
          m.set(nm, { description: desc, parameters: params });
        });
        return m;
      };
      const rawMap = _toMap(llmToolsState.tools_raw);
      const wiredMap = _toMap(llmToolsState.tools_wired);
      const rawNames = Array.from(rawMap.keys());
      const wiredNames = Array.from(wiredMap.keys());
      const rawSet = new Set(rawNames);
      const wiredSet = new Set(wiredNames);
      const removed = rawNames.filter((n) => !wiredSet.has(n)).sort();
      const added = wiredNames.filter((n) => !rawSet.has(n)).sort();
      const changed = [];
      wiredNames.forEach((n) => {
        if (!rawSet.has(n)) return;
        const a = rawMap.get(n) || {};
        const b = wiredMap.get(n) || {};
        const d0 = String(a.description || "");
        const d1 = String(b.description || "");
        const p0 = a.parameters ? JSON.stringify(a.parameters) : "";
        const p1 = b.parameters ? JSON.stringify(b.parameters) : "";
        if (d0 !== d1 || p0 !== p1) changed.push(n);
      });
      llmDiffPre.textContent = JSON.stringify(
        {
          added,
          removed,
          changed,
          counts: {
            raw: rawNames.length,
            wired: wiredNames.length,
            added: added.length,
            removed: removed.length,
            changed: changed.length,
          },
        },
        null,
        2,
      );

      llmDiffTbody.innerHTML = "";
      const _kind = (nm) => (String(nm || "").startsWith("mcp__") ? "mcp" : "internal");
      const _pushRow = (tp, nm, detailEl) => {
        llmDiffTbody.appendChild(
          el("tr", {}, [
            el("td", { text: tp }),
            el("td", { text: nm }),
            el("td", { text: _kind(nm) }),
            el("td", {}, [detailEl]),
          ]),
        );
      };
      const _detailsCompare = (nm) => {
        const a = rawMap.get(nm) || {};
        const b = wiredMap.get(nm) || {};
        const d0 = String(a.description || "");
        const d1 = String(b.description || "");
        const p0 = a.parameters ? JSON.stringify(a.parameters, null, 2) : "";
        const p1 = b.parameters ? JSON.stringify(b.parameters, null, 2) : "";
        return el("details", {}, [
          el("summary", { class: "u-drag", text: "compare" }),
          el("div", { class: "muted u-mt-6" }, [el("div", { text: "raw.description" }), el("pre", { class: "muted pre", text: d0 })]),
          el("div", { class: "muted u-mt-6" }, [el("div", { text: "wired.description" }), el("pre", { class: "muted pre", text: d1 })]),
          el("div", { class: "muted u-mt-6" }, [el("div", { text: "raw.parameters" }), el("pre", { class: "muted pre", text: p0 })]),
          el("div", { class: "muted u-mt-6" }, [el("div", { text: "wired.parameters" }), el("pre", { class: "muted pre", text: p1 })]),
        ]);
      };
      added.forEach((nm) => _pushRow("added", nm, el("span", { class: "muted", text: "present in wired only" })));
      removed.forEach((nm) => _pushRow("removed", nm, el("span", { class: "muted", text: "present in raw only" })));
      changed.sort().forEach((nm) => _pushRow("changed", nm, _detailsCompare(nm)));
      if (!added.length && !removed.length && !changed.length) {
        llmDiffTbody.appendChild(el("tr", {}, [el("td", { text: "-", colspan: "4" })]));
      }

      _renderLLMToolRows(llmToolsState.tools_wired);
    } catch (e) {
      llmToolsState.tools_wired = [];
      llmToolsStatus.textContent = `preview: ${String(e && e.message ? e.message : e)}`;
      llmRemovedPre.textContent = "";
      llmDiffPre.textContent = "";
      llmDiffTbody.innerHTML = "";
      _renderLLMToolRows([]);
    }
  };

  const btnLLMPreview = el("button", {
    class: "btn btn--primary",
    text: t("skills.action.preview"),
    onclick: async () => await loadLLMToolsPreview(llmRoleSelect.value),
  });
  const loadExposureTraceSetting = async () => {
    try {
      const resp = await apiGet("/admin/api/tools/exposure-trace-setting");
      llmTracePlanCb.checked = !!(resp && resp.enabled);
    } catch (_) {
      llmTracePlanCb.checked = false;
    }
  };
  const saveExposureTraceSetting = async () => {
    try {
      const resp = await apiPost("/admin/api/tools/exposure-trace-setting", { enabled: !!llmTracePlanCb.checked });
      llmTracePlanCb.checked = !!(resp && resp.enabled);
      llmToolsStatus.textContent = `trace_exposure_plan=${llmTracePlanCb.checked ? "on" : "off"}`;
    } catch (e) {
      llmToolsStatus.textContent = `trace setting: ${String(e && e.message ? e.message : e)}`;
    }
  };
  const btnLLMToggle = el("button", {
    class: "btn",
    text: t("skills.action.toggleRawWired"),
    onclick: () => {
      const showing = String(btnLLMToggle.dataset.showing || "wired");
      const next = showing === "wired" ? "raw" : "wired";
      btnLLMToggle.dataset.showing = next;
      _renderLLMToolRows(next === "wired" ? llmToolsState.tools_wired : llmToolsState.tools_raw);
    },
  });

  const llmToolsInner = [
    el("div", { class: "muted u-muted-block-lg", text: t("skills.hint.llmTools") }),
    llmToolsStatus,
    el("div", { class: "row u-row-wrap-mt" }, [
      el("label", { text: t("skills.label.role") }),
      llmRoleSelect,
      btnLLMPreview,
      btnLLMToggle,
      el("button", {
        class: "btn",
        text: t("skills.action.clearCache"),
        onclick: async () => {
          try {
            await apiPost("/admin/api/tools/internal/reload", {});
            llmToolsStatus.textContent = "cache cleared";
            await loadLLMToolsPreview(llmRoleSelect.value);
          } catch (e) {
            llmToolsStatus.textContent = `reload: ${String(e && e.message ? e.message : e)}`;
          }
        },
      }),
      el("span", { class: "muted", text: "role_mode:" }),
      llmModeBadge,
      el("label", { class: "row u-row-center" }, [
        llmTracePlanCb,
        el("span", { class: "muted", text: t("skills.action.traceExposure") }),
      ]),
      el("button", {
        class: "btn",
        text: t("skills.action.saveTrace"),
        onclick: saveExposureTraceSetting,
      }),
    ]),
    el("div", { class: "table-wrap u-mt-8" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("skills.col.name") }),
            el("th", { text: t("skills.col.description") }),
            el("th", { text: t("skills.col.kind") }),
            el("th", { text: t("skills.col.parameters") }),
          ]),
        ]),
        llmToolsTbody,
      ]),
    ]),
    el("div", { class: "muted u-mt-8", text: t("skills.hint.diffDiag") }),
    llmRemovedPre,
    el("div", { class: "muted u-mt-8", text: t("skills.hint.rawWiredDiff") }),
    llmDiffPre,
    llmDiffTableWrap,
  ];
  const llmToolsBox = skillsFold(t("skills.fold.llmTools"), llmToolsInner);

  // --- Installed table + audit + modals ---
  const tbody = el("tbody");
  const auditTbody = el("tbody");
  let skillTestRunName = "";

  const skillTestRunModal = el("div", { class: "session-monitor-modal u-hidden", "data-skill-modal": "testrun" });
  const skillTestRunTitle = el("div", { class: "card__title", text: t("skills.modal.testRun") });
  const skillTestRunArgs = el("textarea", {
    class: "input",
    rows: "8",
    style: "width:100%;min-width:0;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;",
    placeholder: "{}",
  });
  const skillInstallModal = el("div", { class: "session-monitor-modal u-hidden", "data-skill-modal": "install" });
  const skillInstallTitle = el("div", { class: "card__title", text: t("skills.modal.install") });
  const skillInstallMsg = el("div", { class: "muted", style: "line-height:1.5;" });

  const closeSkillInstallModal = () => {
    skillInstallModal.classList.add("u-hidden");
    skillInstallModal.style.display = "";
  };
  const openSkillInstallModal = (msg) => {
    skillInstallTitle.textContent = t("skills.modal.install");
    skillInstallMsg.textContent = String(msg || "");
    if (skillInstallModal.parentNode !== document.body) document.body.appendChild(skillInstallModal);
    skillInstallModal.classList.remove("u-hidden");
    skillInstallModal.style.display = "";
  };
  const finishSkillInstallModal = (ok, msg) => {
    skillInstallTitle.textContent = ok ? t("skills.modal.installOk") : t("skills.modal.installFail");
    skillInstallMsg.textContent = String(msg || "");
    setTimeout(() => {
      closeSkillInstallModal();
    }, 1200);
  };
  skillInstallModal.addEventListener("click", (e) => {
    if (e.target === skillInstallModal) closeSkillInstallModal();
  });
  skillInstallModal.appendChild(
    el("div", { class: "card session-monitor-modal__card", style: "width:min(560px,96vw);" }, [
      skillInstallTitle,
      skillInstallMsg,
      el("div", { class: "row u-row-end" }, [
        el("button", { class: "btn", text: t("skills.action.close"), onclick: closeSkillInstallModal }),
      ]),
    ]),
  );

  const closeSkillTestRunModal = () => {
    skillTestRunModal.classList.add("u-hidden");
    skillTestRunModal.style.display = "";
    skillTestRunName = "";
  };
  const openSkillTestRunModal = (name) => {
    skillTestRunName = String(name || "");
    skillTestRunTitle.textContent = tf("skills.modal.testRunNamed", { name: skillTestRunName });
    skillTestRunArgs.value = "{}";
    if (skillTestRunModal.parentNode !== document.body) document.body.appendChild(skillTestRunModal);
    skillTestRunModal.classList.remove("u-hidden");
    skillTestRunModal.style.display = "";
    setTimeout(() => skillTestRunArgs.focus(), 0);
  };
  skillTestRunModal.addEventListener("click", (e) => {
    if (e.target === skillTestRunModal) closeSkillTestRunModal();
  });
  const skillTestRunRunBtn = el("button", {
    class: "btn btn--primary",
    text: t("skills.action.run"),
    onclick: async () => {
      if (!skillTestRunName) return;
      let args = {};
      try {
        const raw = String(skillTestRunArgs.value || "").trim();
        args = raw ? JSON.parse(raw) : {};
      } catch (e) {
        status.textContent = `invalid json: ${String(e && e.message ? e.message : e)}`;
        return;
      }
      try {
        const r = await apiPost("/admin/api/skills/test-run", { name: skillTestRunName, args });
        status.textContent = `test-run: ${skillTestRunName} => ${JSON.stringify((r && r.result) || {}, null, 0)}`;
        closeSkillTestRunModal();
      } catch (e) {
        status.textContent = `test-run: ${String(e && e.message ? e.message : e)}`;
      }
    },
  });
  const skillTestRunCancelBtn = el("button", {
    class: "btn",
    text: t("skills.action.cancel"),
    onclick: closeSkillTestRunModal,
  });
  skillTestRunModal.appendChild(
    el("div", { class: "card session-monitor-modal__card", style: "width:min(760px,96vw);" }, [
      skillTestRunTitle,
      el("div", { class: "muted", style: "margin-bottom:8px;", text: t("skills.hint.testRunArgs") }),
      skillTestRunArgs,
      el("div", { class: "row u-row-end" }, [skillTestRunCancelBtn, skillTestRunRunBtn]),
    ]),
  );

  const retryableOnlyCb = el("input", { type: "checkbox" });
  const retryableOnlyStored = String(localStorage.getItem(SKILL_AUDIT_RETRYABLE_ONLY_KEY) || "")
    .trim()
    .toLowerCase();
  retryableOnlyCb.checked = retryableOnlyStored
    ? retryableOnlyStored !== "0" && retryableOnlyStored !== "false"
    : true;

  const _parseSourceFromAudit = (it) => {
    const d = it && typeof it.detail === "object" ? it.detail : {};
    const s = String(d.source || "").trim().toLowerCase();
    if (s === "local" || s === "registry" || s === "auto") return s;
    return "";
  };
  const _parseRetryTargetFromAudit = (it) => {
    const d = it && typeof it.detail === "object" ? it.detail : {};
    const inputTarget = String(d.input_target || "").trim();
    if (inputTarget) return inputTarget;
    return String((it && it.target_id) || "").trim();
  };
  const _isRetryableAudit = (it) => {
    const action = String((it && it.action) || "").trim().toLowerCase();
    if (action !== "skill_install_failed") return false;
    const src = _parseSourceFromAudit(it);
    const target = _parseRetryTargetFromAudit(it);
    return Boolean(src && target);
  };

  const loadRows = async () => {
    const data = await apiGet("/admin/api/skills");
    rowsState.items = Array.isArray(data.items) ? data.items : [];
  };
  const loadAudits = async () => {
    const data = await apiGet("/admin/api/admin-audit?limit=80");
    const items = Array.isArray(data.items) ? data.items : [];
    auditState.items = items.filter((x) => String(x.action || "").startsWith("skill_")).slice(0, 20);
  };

  const updateInstalledFoldTitle = () => {
    if (foldInstalledSummary) {
      foldInstalledSummary.textContent = tf("skills.fold.installed", { n: (rowsState.items || []).length });
    }
  };
  let foldInstalledSummary = null;

  const repaint = () => {
    const rows = rowsState.items || [];
    tbody.innerHTML = "";
    rows.forEach((x) => {
      const name = String(x.name || "");
      const enabled = !!x.enabled;
      const executable = !!x.executable;
      const runtime = x && typeof x.runtime === "object" ? x.runtime : null;
      const runtimeType = runtime && typeof runtime.type === "string" ? String(runtime.type) : "";
      const runtimeEntry = runtime && typeof runtime.entry === "string" ? String(runtime.entry) : "";
      const actions = rowActions("⋯", [
        {
          label: enabled ? t("skills.action.disable") : t("skills.action.enable"),
          onClick: async () => {
            await apiPost(enabled ? "/admin/api/skills/disable" : "/admin/api/skills/enable", { name });
            status.textContent = `${enabled ? "Disabled" : "Enabled"}: ${name}`;
            await loadRows();
            repaint();
          },
        },
        {
          label: t("skills.action.testRun"),
          disabled: !executable,
          onClick: () => openSkillTestRunModal(name),
        },
        {
          label: t("skills.action.repairDeps"),
          onClick: async () => {
            status.textContent = `repair deps: ${name}...`;
            const r = await apiPost("/admin/api/skills/repair-deps", { name });
            assertSkillMutationOk(r, "Repair deps failed");
            status.textContent = `repair deps: ${JSON.stringify((r && r.result) || {}, null, 0)}`;
            await loadRows();
            await loadAudits();
            repaint();
          },
        },
        {
          label: t("skills.action.uninstall"),
          danger: true,
          onClick: async () => {
            if (!confirm(tf("skills.confirm.uninstall", { name }))) return;
            status.textContent = `uninstalling: ${name}...`;
            const r = await apiPost("/admin/api/skills/uninstall", { name });
            assertSkillMutationOk(r, "Uninstall failed");
            status.textContent = `uninstall success: ${JSON.stringify((r && r.result) || {}, null, 0)}`;
            await loadRows();
            await loadAudits();
            repaint();
          },
        },
      ]);
      tbody.appendChild(
        el("tr", {}, [
          el("td", { text: name }),
          el("td", { text: String(x.description || "") }),
          el("td", { text: String(x.enabled ? "1" : "0") }),
          el("td", {}, [
            executable
              ? el("span", { class: "badge badge--ok", text: `${runtimeType || "runtime"}` })
              : el("span", { class: "muted", text: "docs-only" }),
          ]),
          el("td", { text: executable ? `${runtimeEntry}` : "-" }),
          el("td", { text: String(x.skill_dir || "") }),
          el("td", { class: "table__cell--actions", "data-copy-disabled": "1" }, [
            el("div", { class: "table__cell-actions" }, [actions]),
          ]),
        ]),
      );
    });
    updateInstalledFoldTitle();

    auditTbody.innerHTML = "";
    const auditRows = (auditState.items || []).filter((x) => (!retryableOnlyCb.checked ? true : _isRetryableAudit(x)));
    for (const x of auditRows) {
      const src = _parseSourceFromAudit(x);
      const isRetryable = _isRetryableAudit(x);
      const retryBtn = el("button", {
        class: "btn",
        text: t("skills.action.retry"),
        disabled: !isRetryable,
        onclick: async () => {
          try {
            const target = _parseRetryTargetFromAudit(x);
            if (!src || !target || !isRetryable) {
              status.textContent = "retry skipped: missing source/target";
              return;
            }
            const r = await apiPost("/admin/api/skills/retry-install", { source: src, target });
            assertSkillMutationOk(r, "Retry install failed");
            status.textContent = `retry: ${JSON.stringify(r.result || {})}`;
            await loadRows();
            await loadAudits();
            repaint();
          } catch (e) {
            status.textContent = String(e && e.message ? e.message : e);
          }
        },
      });
      auditTbody.appendChild(
        el("tr", {}, [
          el("td", { text: String(x.timestamp || "") }),
          el("td", { text: String(x.action || "") }),
          el("td", { text: String(x.target_id || "") }),
          el("td", { text: String(x.status || "") }),
          el("td", { text: shortText(JSON.stringify(x.detail || {}), 180) }),
          el("td", {}, [retryBtn]),
        ]),
      );
    }
  };

  const refreshSkillsState = async () => {
    await Promise.all([loadRows(), loadAudits(), loadSkillBinding()]);
    repaint();
    renderSkillBindingList();
  };

  try {
    await Promise.all([loadRows(), loadAudits(), loadSkillBinding(), loadSkillMode()]);
    const rolesForPreview = (
      Array.isArray(skillBindingState.roles) && skillBindingState.roles.length
        ? skillBindingState.roles
        : ["generalist", "ops", "memory"]
    ).map((x) => String(x));
    internalRoleSelect.innerHTML = "";
    rolesForPreview.forEach((role) => internalRoleSelect.appendChild(el("option", { value: role, text: role })));
    internalRoleSelect.value = rolesForPreview.includes("generalist") ? "generalist" : rolesForPreview[0];
    internalToolsStatus.textContent = t("skills.hint.expandToLoad");
    llmRoleSelect.innerHTML = "";
    rolesForPreview.forEach((role) => llmRoleSelect.appendChild(el("option", { value: role, text: role })));
    llmRoleSelect.value = internalRoleSelect.value;
    llmToolsStatus.textContent = t("skills.hint.expandToLoad");
    selfCheckStatus.textContent = t("skills.hint.expandToSelfCheck");
    skillHealthStatus.textContent = t("skills.hint.expandToSelfCheck");
  } catch (e) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("skills.title") }),
      el("div", { class: "muted", text: String(e && e.message ? e.message : e) }),
    ]);
  }
  repaint();

  const btnCreate = el("button", {
    class: "btn btn--primary",
    text: t("skills.action.create"),
    onclick: async () => {
      try {
        const r = await apiPost("/admin/api/skills/create", {
          name: String(nameInp.value || "").trim(),
          description: String(descInp.value || "").trim(),
          body_markdown: String(bodyInp.value || ""),
        });
        assertSkillMutationOk(r, "Create skill failed");
        status.textContent = `create: ${JSON.stringify(r.result || {})}`;
        await loadRows();
        await loadAudits();
        repaint();
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
      }
    },
  });
  const btnInstallRegistry = el("button", {
    class: "btn",
    text: t("skills.action.installRegistry"),
    onclick: async () => {
      const prev = btnInstallRegistry.textContent;
      btnInstallRegistry.disabled = true;
      btnInstallRegistry.textContent = t("skills.action.installing");
      status.textContent = "installing from registry...";
      openSkillInstallModal("Installing skill from registry...");
      try {
        const r = await apiPost("/admin/api/skills/install-registry", {
          archive_url: String(regInp.value || "").trim(),
        });
        assertSkillMutationOk(r, "Registry install failed");
        status.textContent = `install-registry success: ${JSON.stringify(r.result || {})}`;
        await refreshSkillsState();
        finishSkillInstallModal(true, "Registry skill installed successfully.");
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
        finishSkillInstallModal(false, `Install failed: ${String(e && e.message ? e.message : e)}`);
      } finally {
        btnInstallRegistry.disabled = false;
        btnInstallRegistry.textContent = prev;
      }
    },
  });
  const btnInstallLocal = el("button", {
    class: "btn",
    text: t("skills.action.installLocal"),
    onclick: async () => {
      const prev = btnInstallLocal.textContent;
      btnInstallLocal.disabled = true;
      btnInstallLocal.textContent = t("skills.action.installing");
      status.textContent = "installing from local dir...";
      openSkillInstallModal("Installing skill from local directory...");
      try {
        const r = await apiPost("/admin/api/skills/install", {
          source_dir: String(localDirInp.value || "").trim(),
        });
        assertSkillMutationOk(r, "Local install failed");
        status.textContent = `install-local success: ${JSON.stringify(r.result || {})}`;
        await refreshSkillsState();
        finishSkillInstallModal(true, "Local skill installed successfully.");
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
        finishSkillInstallModal(false, `Install failed: ${String(e && e.message ? e.message : e)}`);
      } finally {
        btnInstallLocal.disabled = false;
        btnInstallLocal.textContent = prev;
      }
    },
  });
  const btnRefresh = el("button", {
    class: "btn",
    text: t("skills.action.refresh"),
    onclick: async () => {
      try {
        await refreshSkillsState();
        status.textContent = "refreshed";
      } catch (e) {
        status.textContent = String(e && e.message ? e.message : e);
      }
    },
  });
  const btnRepairDepsAll = el("button", {
    class: "btn",
    text: t("skills.action.repairAllDeps"),
    onclick: async () => {
      const prev = btnRepairDepsAll.textContent;
      btnRepairDepsAll.disabled = true;
      btnRepairDepsAll.textContent = t("skills.action.repairing");
      try {
        const r = await apiPost("/admin/api/skills/repair-deps-all", {});
        const s = r && typeof r.summary === "object" ? r.summary : {};
        status.textContent = `repair all deps: total=${Number(s.total || 0)} ok=${Number(s.ok_count || 0)} warn=${Number(s.warn_count || 0)} fail=${Number(s.fail_count || 0)}`;
        await refreshSkillsState();
      } catch (e) {
        status.textContent = `repair all deps failed: ${String(e && e.message ? e.message : e)}`;
      } finally {
        btnRepairDepsAll.disabled = false;
        btnRepairDepsAll.textContent = prev;
      }
    },
  });
  retryableOnlyCb.addEventListener("change", () => {
    localStorage.setItem(SKILL_AUDIT_RETRYABLE_ONLY_KEY, retryableOnlyCb.checked ? "1" : "0");
    repaint();
  });

  const docsHint = el("div", { class: "muted", style: "margin-bottom:10px;line-height:1.5;" }, [
    el("div", { text: t("skills.docsTitle") }),
    el("div", { text: t("skills.docsTroubleshooting") }),
    el("div", { text: t("skills.docsTraceTaxonomy") }),
  ]);

  internalToolsBox.addEventListener("toggle", async () => {
    if (!internalToolsBox.open || lazyLoadState.internalLoaded) return;
    lazyLoadState.internalLoaded = true;
    await loadInternalToolsPreview(internalRoleSelect.value);
  });
  llmToolsBox.addEventListener("toggle", async () => {
    if (!llmToolsBox.open || lazyLoadState.llmLoaded) return;
    lazyLoadState.llmLoaded = true;
    await Promise.all([loadExposureTraceSetting(), loadLLMToolsPreview(llmRoleSelect.value)]);
  });
  selfCheckBox.addEventListener("toggle", async () => {
    if (!selfCheckBox.open || lazyLoadState.selfCheckLoaded) return;
    lazyLoadState.selfCheckLoaded = true;
    await runSelfCheck();
  });
  skillHealthBox.addEventListener("toggle", async () => {
    if (!skillHealthBox.open || lazyLoadState.skillHealthLoaded) return;
    lazyLoadState.skillHealthLoaded = true;
    await runSkillHealthCheck();
  });

  // --- Page folds ---
  const foldMode = skillsFold(t("skills.fold.mode"), [
    el("div", { class: "muted", text: t("skills.fold.modeHint") }),
    el("div", { class: "row", style: "gap:8px;align-items:center;flex-wrap:wrap;" }, [
      el("label", { class: "row u-row-center" }, [
        skillPromptModeCb,
        el("span", { text: t("skills.label.promptMode") }),
      ]),
      el("button", { class: "btn btn--primary", text: t("skills.action.save"), onclick: saveSkillMode }),
      skillModeStatus,
    ]),
    docsHint,
  ]);

  const foldMarket = skillsFold(t("skills.fold.market"), [
    el("div", { class: "row u-row-wrap-mb" }, [marketQ, marketLimitInp, btnMarketSearch, btnMarketLatest]),
    marketStatus,
    el("div", { class: "u-h-8" }),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("skills.col.slug") }),
            el("th", { text: t("skills.col.name") }),
            el("th", { text: t("skills.col.version") }),
            el("th", { text: t("skills.col.description") }),
            el("th", { text: t("skills.col.action") }),
          ]),
        ]),
        marketTbody,
      ]),
    ]),
    el("div", { class: "u-h-8" }),
    el("div", { class: "muted", text: t("skills.action.detail") }),
    marketDetailPre,
  ]);

  const foldLocalRegistry = skillsFold(t("skills.fold.localRegistry"), [
    el("div", { class: "muted", style: "margin-bottom:8px;line-height:1.5;" }, [
      el("div", { text: t("skills.hintLocalDir") }),
      el("div", { text: t("skills.hintRegistry") }),
    ]),
    el("div", { class: "row u-row-wrap-mb" }, [regInp, btnInstallRegistry]),
    el("div", { class: "row u-row-wrap-mb" }, [localDirInp, btnInstallLocal]),
  ]);

  const foldCreate = skillsFold(t("skills.fold.create"), [
    el("div", { class: "row u-row-wrap-mb" }, [nameInp, descInp]),
    el("div", { style: "margin-bottom:8px;" }, [bodyInp]),
    el("div", { class: "row u-row-wrap-mb" }, [btnCreate]),
  ]);

  const foldInstall = skillsFold(t("skills.fold.install"), [
    el("div", { class: "muted", text: t("skills.fold.installHint") }),
    foldMarket,
    foldLocalRegistry,
    foldCreate,
  ]);
  foldMarket.open = true;

  const foldAudit = skillsFold(t("skills.fold.audit"), [
    el("div", { class: "row", style: "gap:8px;align-items:center;" }, [
      el("label", { class: "row u-row-center" }, [
        retryableOnlyCb,
        el("span", { class: "muted", text: t("skills.action.retryableOnly") }),
      ]),
    ]),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("skills.col.timestamp") }),
            el("th", { text: t("skills.col.action") }),
            el("th", { text: t("skills.col.target") }),
            el("th", { text: t("skills.col.status") }),
            el("th", { text: t("skills.col.detail") }),
            el("th", { text: t("skills.col.retry") }),
          ]),
        ]),
        auditTbody,
      ]),
    ]),
  ]);

  const foldInstalled = skillsFold(tf("skills.fold.installed", { n: (rowsState.items || []).length }), [
    el("div", { class: "row u-row-wrap-mb" }, [btnRefresh, btnRepairDepsAll]),
    status,
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("skills.col.name") }),
            el("th", { text: t("skills.col.description") }),
            el("th", { text: t("skills.col.enabled") }),
            el("th", { text: t("skills.col.kind") }),
            el("th", { text: t("skills.col.runtimeEntry") }),
            el("th", { text: t("skills.col.path") }),
            el("th", { class: "table__cell--actions", text: t("skills.col.action") }),
          ]),
        ]),
        tbody,
      ]),
    ]),
    foldAudit,
  ]);
  foldInstalled.open = true;
  foldInstalledSummary = foldInstalled.querySelector("summary");

  const foldEffective = skillsFold(t("skills.fold.effective"), [
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("skills.col.role") }),
            el("th", { text: t("skills.col.totalEffective") }),
            el("th", { text: t("skills.col.workspace") }),
            el("th", { text: t("skills.col.directBind") }),
            el("th", { text: t("skills.col.workspaceResolved") }),
            el("th", { text: t("skills.col.workspaceDocsOnly") }),
            el("th", { text: t("skills.col.mcpConverted") }),
            el("th", { text: t("skills.col.otherTools") }),
            el("th", { text: t("skills.col.docsOnlyNames") }),
            el("th", { text: t("skills.col.namesPreview") }),
          ]),
        ]),
        skillEffectiveTbody,
      ]),
    ]),
  ]);

  const foldBindingDash = skillsFold(t("skills.fold.bindingDash"), [
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("skills.col.role") }),
            el("th", { text: t("skills.col.directSkills") }),
            el("th", { text: t("skills.col.effective") }),
          ]),
        ]),
        skillBindingDashTbody,
      ]),
    ]),
    foldEffective,
  ]);

  const foldBinding = skillsFold(t("skills.fold.binding"), [
    el("div", { class: "muted", text: t("skills.fold.bindingHint") }),
    skillBindingStatus,
    skillBindingPersistHint,
    skillBindingEnvHint,
    el("label", { class: "row", style: "gap:8px;align-items:center;margin-top:6px;" }, [
      skillBindingEnabledCb,
      el("span", { text: t("skills.label.enableBinding") }),
    ]),
    el("div", { class: "row u-row-wrap-mt" }, [
      el("label", { text: t("skills.label.role") }),
      skillRoleSelect,
      btnSaveSkillBinding,
    ]),
    skillBindingListWrap,
    foldBindingDash,
  ]);

  const foldDiagnostics = skillsFold(t("skills.fold.diagnostics"), [
    skillHealthBox,
    selfCheckBox,
    internalToolsBox,
    llmToolsBox,
  ]);

  return renderPageShell(
    {
      title: t("skills.title"),
      subtitle: t("skills.subtitle"),
      sections: [
        { id: "skills-mode", label: t("skills.toc.mode") },
        { id: "skills-install", label: t("skills.toc.install") },
        { id: "skills-installed", label: t("skills.toc.installed") },
        { id: "skills-binding", label: t("skills.toc.binding") },
        { id: "skills-diagnostics", label: t("skills.toc.diagnostics") },
      ],
    },
    [
      el("div", { class: "page-grid page-grid--single" }, [
        el("div", { id: "skills-mode" }, [foldMode]),
        el("div", { id: "skills-install" }, [foldInstall]),
        el("div", { id: "skills-installed" }, [foldInstalled]),
        el("div", { id: "skills-binding" }, [foldBinding]),
        el("div", { id: "skills-diagnostics" }, [foldDiagnostics]),
      ]),
    ],
  );
}

export { skillsFold, renderSkills };
