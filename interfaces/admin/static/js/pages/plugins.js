import { t, el, tdCell, apiGet, apiGetNoHang, apiPost, renderPageShell, markPrewarmReminder, tf, rowActions } from "../core.js";

const PLUGINS_PAGE_SIZE = 15;

function pluginsFold(summaryText, innerNodes) {
  const det = el("details", { class: "details plugins-fold" });
  det.appendChild(el("summary", { text: summaryText }));
  const inner = el("div", { class: "plugins-fold__inner" });
  // Keep interactive controls inside the fold from bubbling to <details>.
  inner.addEventListener("click", (e) => e.stopPropagation());
  innerNodes.forEach((n) => inner.appendChild(n));
  det.appendChild(inner);
  return det;
}

/** totalHolder.value = row count; pageRef.value = 1-based page */
function pluginsPagerBar(totalHolder, pageRef, onRepaint) {
  const wrap = el("div", {
    class: "row plugins-pager",
    style: "gap:8px;align-items:center;margin-top:6px;flex-wrap:wrap;",
  });
  const lab = el("span", { class: "muted", text: "" });
  const maxP = () => Math.max(1, Math.ceil(Math.max(0, totalHolder.value) / PLUGINS_PAGE_SIZE));
  const prevBtn = el("button", { class: "btn btn--small", text: t("plugins.prevPage") });
  const nextBtn = el("button", { class: "btn btn--small", text: t("plugins.nextPage") });
  const sync = () => {
    const total = totalHolder.value;
    let cur = pageRef.value;
    const mp = maxP();
    if (cur > mp) {
      cur = mp;
      pageRef.value = cur;
    }
    if (cur < 1) {
      cur = 1;
      pageRef.value = 1;
    }
    const start = total === 0 ? 0 : (cur - 1) * PLUGINS_PAGE_SIZE + 1;
    const end = Math.min(cur * PLUGINS_PAGE_SIZE, total);
    lab.textContent = total ? tf("plugins.pageRange", { start, end, total }) : t("plugins.noData");
    prevBtn.disabled = cur <= 1 || total === 0;
    nextBtn.disabled = cur >= mp || total === 0;
  };
  prevBtn.addEventListener("click", () => {
    if (pageRef.value > 1) {
      pageRef.value--;
      onRepaint();
      sync();
    }
  });
  nextBtn.addEventListener("click", () => {
    if (pageRef.value < maxP()) {
      pageRef.value++;
      onRepaint();
      sync();
    }
  });
  wrap.appendChild(prevBtn);
  wrap.appendChild(lab);
  wrap.appendChild(nextBtn);
  sync();
  return { wrap, sync };
}

function cursorCommandSummary(cursor) {
  if (!cursor || typeof cursor !== "object") return "-";
  const url = String(cursor.url || cursor.baseUrl || "").trim();
  if (url) return url;
  const cmd = String(cursor.command || "").trim();
  const args = Array.isArray(cursor.args) ? cursor.args.map((x) => String(x)).join(" ") : "";
  const line = (cmd + (args ? " " + args : "")).trim();
  return line || "-";
}

async function renderPlugins() {
  document.querySelectorAll("[data-mcp-edit-modal]").forEach((n) => n.remove());
  document.querySelectorAll("body > .row-actions__menu, body > .chat-sess-menu-pop.row-actions__menu").forEach((n) => n.remove());
  const defaultToolPolicy = {
    disable_tool_confirm: false,
    enforced_retry_mode: "first_round_only",
    tool_loop_state_machine: true,
    tool_signature_budget: 2,
    turn_max_tool_workers: 8,
    turn_max_tool_rounds: 100,
    turn_max_context_messages: 80,
    turn_runner_impl: "oclaw",
    sse_queue_maxsize: 2000,
    tool_log_max_chars: 200000,
    enable_mcp_tools: true,
    enable_plugin_tools: false,
    enable_run_command: true,
    tool_context_truncate_enabled: true,
    chat_show_ttft_debug: false,
    tool_llm_message_max_chars: 0,
    mcp_filesystem_extra_roots: "",
    mcp_env_allowlist: "",
    oclaw_retryable_error_codes: "",
    oclaw_retry_codes_strict_mode: false,
    wecom_longconn_workers: 2,
    wecom_longconn_inbound_queue_maxsize: 200,
  };
  const [p, mcp, mcpBinding, toolPolicyRaw] = await Promise.all([
    apiGetNoHang("/admin/api/plugins").then((r) => r || { plugins: [] }),
    apiGetNoHang("/admin/api/mcp/servers").then((r) => r || { servers: [] }),
    apiGetNoHang("/admin/api/mcp/binding").then(
      (r) =>
        r || {
          available_specialists: ["generalist"],
          servers: [],
          mapping: {},
        },
    ),
    apiGetNoHang("/admin/api/tool-policy"),
  ]);
  let toolPolicy = toolPolicyRaw && typeof toolPolicyRaw === "object" ? toolPolicyRaw : defaultToolPolicy;

  const pluginCatalog = Array.isArray(p.plugins) ? p.plugins : [];
  const pluginPageRef = { value: 1 };
  const pluginTotalHolder = { value: pluginCatalog.length };
  const pluginTbody = el("tbody");
  const buildPluginRow = (x) =>
    el("tr", {}, [
      el("td", { text: String(x.plugin_name || "") }),
      el("td", { text: String(x.plugin_version || "") }),
      el("td", { text: String(x.entry_point || "") }),
      el("td", { text: String(x.enabled ? 1 : 0) }),
    ]);
  const repaintPlugins = () => {
    pluginTbody.innerHTML = "";
    const start = (pluginPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    pluginCatalog.slice(start, start + PLUGINS_PAGE_SIZE).forEach((x) => {
      pluginTbody.appendChild(buildPluginRow(x));
    });
  };
  repaintPlugins();
  const pluginPager = pluginsPagerBar(pluginTotalHolder, pluginPageRef, repaintPlugins);

  const bindingStatus = el("div", { class: "muted", text: "" });
  const installStatus = el("div", { class: "muted", text: "" });
  const toolPolicyStatus = el("div", { class: "muted", text: "" });

  const turnMaxWorkersInput = el("input", {
    class: "input u-max-w-120",
    type: "number",
    min: "1",
    max: "32",
    value: String(Number(toolPolicy.turn_max_tool_workers || 8)),
  });
  const turnMaxRoundsInput = el("input", {
    class: "input u-max-w-120",
    type: "number",
    min: "1",
    max: "300",
    value: String(Number(toolPolicy.turn_max_tool_rounds || 100)),
  });
  const turnMaxCtxInput = el("input", {
    class: "input u-max-w-120",
    type: "number",
    min: "10",
    max: "400",
    value: String(Number(toolPolicy.turn_max_context_messages || 80)),
  });
  const sseQueueMaxsizeInput = el("input", {
    class: "input u-max-w-140",
    type: "number",
    min: "200",
    max: "50000",
    value: String(Number(toolPolicy.sse_queue_maxsize || 2000)),
  });
  const toolLogMaxCharsInput = el("input", {
    class: "input u-max-w-140",
    type: "number",
    min: "20000",
    max: "2000000",
    value: String(Number(toolPolicy.tool_log_max_chars || 200000)),
  });
  const enableMcpToolsCb = el("input", { type: "checkbox" });
  enableMcpToolsCb.checked = !!toolPolicy.enable_mcp_tools;
  const enablePluginToolsCb = el("input", { type: "checkbox" });
  enablePluginToolsCb.checked = !!toolPolicy.enable_plugin_tools;
  const enableRunCommandCb = el("input", { type: "checkbox" });
  enableRunCommandCb.checked = !!toolPolicy.enable_run_command;
  const toolContextTruncateCb = el("input", { type: "checkbox" });
  toolContextTruncateCb.checked = !!toolPolicy.tool_context_truncate_enabled;
  const chatShowTtftDebugCb = el("input", { type: "checkbox" });
  chatShowTtftDebugCb.checked = !!toolPolicy.chat_show_ttft_debug;
  const toolLlmMessageMaxCharsInput = el("input", {
    class: "input u-max-w-140",
    type: "number",
    min: "0",
    max: "500000",
    value: String(Number(toolPolicy.tool_llm_message_max_chars ?? 0)),
  });
  const mcpFilesystemExtraRootsInput = el("input", {
    class: "input",
    value: String(toolPolicy.mcp_filesystem_extra_roots || ""),
    placeholder: "D:\\work|D:\\docs",
  });
  const mcpEnvAllowlistInput = el("input", {
    class: "input",
    value: String(toolPolicy.mcp_env_allowlist || ""),
    placeholder: "BRAVE_API_KEY,GOOGLE_OAUTH_CREDENTIALS,...",
  });
  const oclawRetryableErrorCodesInput = el("input", {
    class: "input",
    value: String(toolPolicy.oclaw_retryable_error_codes || ""),
    placeholder: "provider_timeout,provider_rate_limited,...",
  });
  const oclawRetryCodesStrictModeCb = el("input", { type: "checkbox" });
  oclawRetryCodesStrictModeCb.checked = !!toolPolicy.oclaw_retry_codes_strict_mode;
  const wecomLongconnWorkersInput = el("input", {
    class: "input u-max-w-120",
    type: "number",
    min: "1",
    max: "8",
    value: String(Number(toolPolicy.wecom_longconn_workers || 2)),
  });
  const wecomLongconnInboundQueueInput = el("input", {
    class: "input u-max-w-140",
    type: "number",
    min: "20",
    max: "5000",
    value: String(Number(toolPolicy.wecom_longconn_inbound_queue_maxsize || 200)),
  });
  const saveToolPolicyBtn = el("button", {
    class: "btn",
    text: t("plugins.action.saveToolPolicy"),
    onclick: async () => {
      const r = await apiPost("/admin/api/tool-policy", {
        turn_max_tool_workers: Number(turnMaxWorkersInput.value || 8),
        turn_max_tool_rounds: Number(turnMaxRoundsInput.value || 100),
        turn_max_context_messages: Number(turnMaxCtxInput.value || 80),
        sse_queue_maxsize: Number(sseQueueMaxsizeInput.value || 2000),
        tool_log_max_chars: Number(toolLogMaxCharsInput.value || 200000),
        enable_mcp_tools: !!enableMcpToolsCb.checked,
        enable_plugin_tools: !!enablePluginToolsCb.checked,
        enable_run_command: !!enableRunCommandCb.checked,
        tool_context_truncate_enabled: !!toolContextTruncateCb.checked,
        chat_show_ttft_debug: !!chatShowTtftDebugCb.checked,
        tool_llm_message_max_chars: Number(toolLlmMessageMaxCharsInput.value || 0),
        mcp_filesystem_extra_roots: String(mcpFilesystemExtraRootsInput.value || ""),
        mcp_env_allowlist: String(mcpEnvAllowlistInput.value || ""),
        oclaw_retryable_error_codes: String(oclawRetryableErrorCodesInput.value || ""),
        oclaw_retry_codes_strict_mode: !!oclawRetryCodesStrictModeCb.checked,
        wecom_longconn_workers: Number(wecomLongconnWorkersInput.value || 2),
        wecom_longconn_inbound_queue_maxsize: Number(wecomLongconnInboundQueueInput.value || 200),
      });
      const unknownRetry = Array.isArray(r.unknown_retryable_error_codes) ? r.unknown_retryable_error_codes : [];
      if (unknownRetry.length) {
        toolPolicyStatus.textContent =
          `[tool-policy] saved with warnings: unknown_retryable_error_codes=${unknownRetry.join(", ")} | ` + JSON.stringify(r);
      } else {
        toolPolicyStatus.textContent = `[tool-policy] ` + JSON.stringify(r);
      }
      toolPolicyStatus.textContent += " | restart gateway/desktop to apply run_command toggle";
    },
  });

  const availableSpecialists =
    Array.isArray(mcpBinding.available_specialists) && mcpBinding.available_specialists.length
      ? mcpBinding.available_specialists.map((x) => String(x))
      : ["generalist"];
  let bindingServers = Array.isArray(mcpBinding.servers)
    ? mcpBinding.servers.filter((x) => x && String(x.server_id || "").trim())
    : [];
  let bindingDraft = mcpBinding.mapping && typeof mcpBinding.mapping === "object" ? { ...mcpBinding.mapping } : {};
  const allSpecialistIds = () => {
    const s = new Set(availableSpecialists.map((x) => String(x)));
    Object.keys(bindingDraft).forEach((k) => s.add(String(k)));
    return Array.from(s).sort();
  };
  let repaintExpertBindingDashboard = () => {};
  const specialistSelect = el(
    "select",
    { class: "input" },
    availableSpecialists.map((sp) => el("option", { value: sp, text: sp })),
  );
  const bindingListWrap = el("div");
  const bindingListRowsMount = el("div");
  const bindingListPagerMount = el("div");
  bindingListWrap.appendChild(bindingListRowsMount);
  bindingListWrap.appendChild(bindingListPagerMount);
  const bindingListPageRef = { value: 1 };
  const bindingListTotalHolder = { value: 0 };
  const bindingReverseWrap = el("div");
  const bindingReverseTableMount = el("div");
  const bindingReversePagerMount = el("div");
  bindingReverseWrap.appendChild(bindingReverseTableMount);
  bindingReverseWrap.appendChild(bindingReversePagerMount);
  const bindingReversePageRef = { value: 1 };
  const bindingReverseTotalHolder = { value: 0 };
  const flashInstalledRow = (sid) => {
    const row = document.getElementById(`mcp-installed-${sid}`);
    if (!row) {
      bindingStatus.textContent = `[binding] installed row not found: ${sid}`;
      return;
    }
    row.scrollIntoView({ behavior: "smooth", block: "center" });
    const oldBg = row.style.backgroundColor;
    row.style.backgroundColor = "rgba(255, 215, 0, 0.22)";
    setTimeout(() => {
      row.style.backgroundColor = oldBg || "";
    }, 1800);
  };
  const renderBindingReverse = () => {
    bindingReverseTotalHolder.value = bindingServers.length;
    const start = (bindingReversePageRef.value - 1) * PLUGINS_PAGE_SIZE;
    const slice = bindingServers.slice(start, start + PLUGINS_PAGE_SIZE);
    const rows = slice.map((srv) => {
      const sid = String(srv.server_id || "");
      const specialists = allSpecialistIds().filter((sp) => {
        const mapped = Array.isArray(bindingDraft[sp]) ? bindingDraft[sp].map((x) => String(x)) : [];
        return mapped.includes(sid);
      });
      const locateBtn = el("button", {
        class: "btn btn--small",
        text: t("plugins.action.locate"),
        onclick: () => flashInstalledRow(sid),
      });
      return el("tr", {}, [
        tdCell(sid, 38),
        tdCell(specialists.length ? specialists.join(", ") : "-", 62),
        el("td", {}, [locateBtn]),
      ]);
    });
    bindingReverseTableMount.innerHTML = "";
    bindingReverseTableMount.appendChild(
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: t("plugins.col.serverId") }),
              el("th", { text: t("plugins.col.boundSpecialists") }),
              el("th", { text: t("plugins.col.action") }),
            ]),
          ]),
          el("tbody", {}, rows.length ? rows : [el("tr", {}, [el("td", { text: "-", colspan: "3" })])]),
        ]),
      ]),
    );
    bindingReversePagerMount.innerHTML = "";
    const brBar = pluginsPagerBar(bindingReverseTotalHolder, bindingReversePageRef, renderBindingReverse);
    bindingReversePagerMount.appendChild(brBar.wrap);
    repaintExpertBindingDashboard();
  };
  const renderBindingList = () => {
    const current = String(specialistSelect.value || "");
    const existing = Array.isArray(bindingDraft[current]) ? bindingDraft[current].map((x) => String(x)) : [];
    const selected = new Set(existing);
    bindingListTotalHolder.value = bindingServers.length;
    const start = (bindingListPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    const slice = bindingServers.slice(start, start + PLUGINS_PAGE_SIZE);
    bindingListRowsMount.innerHTML = "";
    if (!bindingServers.length) {
      bindingListRowsMount.appendChild(el("div", { class: "muted", text: t("plugins.binding.empty") }));
      bindingListPagerMount.innerHTML = "";
      const blBar0 = pluginsPagerBar(bindingListTotalHolder, bindingListPageRef, renderBindingList);
      bindingListPagerMount.appendChild(blBar0.wrap);
      repaintExpertBindingDashboard();
      return;
    }
    slice.forEach((srv) => {
      const sid = String(srv.server_id || "");
      const cb = el("input", { type: "checkbox" });
      cb.checked = selected.has(sid);
      cb.addEventListener("change", () => {
        const prev = new Set(
          Array.isArray(bindingDraft[current]) ? bindingDraft[current].map((x) => String(x)) : [],
        );
        if (cb.checked) prev.add(sid);
        else prev.delete(sid);
        bindingDraft[current] = Array.from(prev);
        renderBindingReverse();
      });
      const label = `${sid}${srv.enabled ? "" : " (disabled)"}`;
      bindingListRowsMount.appendChild(el("label", { class: "row" }, [cb, el("span", { text: label })]));
    });
    bindingListPagerMount.innerHTML = "";
    const blBar = pluginsPagerBar(bindingListTotalHolder, bindingListPageRef, renderBindingList);
    bindingListPagerMount.appendChild(blBar.wrap);
    repaintExpertBindingDashboard();
  };
  specialistSelect.addEventListener("change", () => {
    bindingListPageRef.value = 1;
    bindingReversePageRef.value = 1;
    renderBindingList();
    renderBindingReverse();
  });
  const selectAllBindingBtn = el("button", {
    class: "btn",
    text: t("plugins.action.selectAll"),
    onclick: () => {
      const current = String(specialistSelect.value || "");
      bindingDraft[current] = bindingServers.map((x) => String(x.server_id || "")).filter((x) => x);
      renderBindingList();
      renderBindingReverse();
    },
  });
  const clearBindingBtn = el("button", {
    class: "btn",
    text: t("plugins.action.clear"),
    onclick: () => {
      const current = String(specialistSelect.value || "");
      bindingDraft[current] = [];
      renderBindingList();
      renderBindingReverse();
    },
  });
  const saveBindingBtn = el("button", {
    class: "btn",
    text: t("plugins.action.saveBinding"),
    onclick: async () => {
      const r = await apiPost("/admin/api/mcp/binding", { mapping: bindingDraft });
      bindingStatus.textContent = `[binding] ` + JSON.stringify(r);
      markPrewarmReminder("mcp_binding_changed");
      try {
        const fresh = await apiGet("/admin/api/mcp/binding");
        if (fresh && fresh.mapping && typeof fresh.mapping === "object") {
          bindingDraft = { ...fresh.mapping };
        }
        if (Array.isArray(fresh && fresh.servers)) {
          bindingServers = fresh.servers.filter((x) => x && String(x.server_id || "").trim());
        }
      } catch (_) {}
      renderBindingList();
      renderBindingReverse();
    },
  });
  renderBindingList();
  renderBindingReverse();

  const jsonInstallInput = el("textarea", {
    class: "input",
    placeholder:
      '{\n  "mcpServers": {\n    "my-server": { "command": "npx", "args": ["-y", "mcp-fetch-server"] }\n  }\n}',
    rows: "10",
  });
  const installBtn = el("button", {
    class: "btn",
    text: t("plugins.action.install"),
    onclick: async () => {
      const raw = String(jsonInstallInput.value || "").trim();
      if (!raw) {
        installStatus.textContent = "[install] empty JSON";
        return;
      }
      let parsed;
      try {
        parsed = JSON.parse(raw);
      } catch (err) {
        installStatus.textContent = `[install] invalid JSON: ${String((err && err.message) || err || "parse_failed")}`;
        return;
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        installStatus.textContent = "[install] body must be a JSON object containing mcpServers";
        return;
      }
      if (!parsed.mcpServers || typeof parsed.mcpServers !== "object") {
        installStatus.textContent = "[install] mcpServers required";
        return;
      }
      installStatus.textContent = "[install] installing...";
      try {
        const res = await apiPost("/admin/api/mcp/install", parsed);
        installStatus.textContent = JSON.stringify(res);
        if (res && res.ok) {
          markPrewarmReminder("mcp_installed");
          await softReloadMcpServers();
        }
      } catch (err) {
        installStatus.textContent = `[install] failed: ${String((err && err.message) || err || "install_failed")}`;
      }
    },
  });
  const mcpExportJsonBtn = el("button", {
    class: "btn",
    text: t("plugins.action.exportJson"),
    title: t("plugins.action.exportJsonTitle"),
    onclick: async () => {
      let r;
      try {
        r = await apiGet("/admin/api/mcp/export");
      } catch (err) {
        installStatus.textContent = "[export] " + String((err && err.message) || err);
        return;
      }
      if (!r || r.ok !== true || !r.document) {
        installStatus.textContent = "[export] failed: " + JSON.stringify(r);
        return;
      }
      const text = JSON.stringify(r.document, null, 2) + "\n";
      const blob = new Blob([text], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "mcp_registry_migrated.json";
      a.click();
      URL.revokeObjectURL(a.href);
      installStatus.textContent =
        "[export] downloaded mcp_registry_migrated.json" + (r.local_path ? " ; on server: " + r.local_path : "");
    },
  });

  let mcpServerList = Array.isArray(mcp.servers) ? mcp.servers : [];
  const expertBindingDashTbody = el("tbody");
  repaintExpertBindingDashboard = () => {
    expertBindingDashTbody.innerHTML = "";
    const ids = allSpecialistIds();
    if (!ids.length) {
      expertBindingDashTbody.appendChild(el("tr", {}, [el("td", { class: "muted", text: "—", colspan: "3" })]));
      return;
    }
    ids.forEach((sp) => {
      const sids = new Set((bindingDraft[sp] || []).map(String).filter(Boolean));
      let toolCnt = 0;
      mcpServerList.forEach((row) => {
        const rsid = String(row.server_id || "");
        if (!sids.has(rsid)) return;
        const tools = Array.isArray(row.tools) ? row.tools : [];
        toolCnt += tools.length;
      });
      expertBindingDashTbody.appendChild(
        el("tr", {}, [tdCell(sp, 28), tdCell(String(sids.size), 10), tdCell(String(toolCnt), 12)]),
      );
    });
  };
  repaintExpertBindingDashboard();

  let editingServer = null;
  const editModal = el("div", { class: "session-monitor-modal u-hidden", "data-mcp-edit-modal": "1" });
  const editTitle = el("div", { class: "card__title", text: t("plugins.edit.title") });
  const editServerIdLab = el("div", { class: "muted", text: "" });
  const editCursorInput = el("textarea", {
    class: "input",
    rows: "12",
    placeholder: '{ "command": "npx", "args": ["-y", "..."] }',
  });
  const editEnabledCb = el("input", { type: "checkbox" });
  const editTimeoutInput = el("input", {
    class: "input u-max-w-120",
    type: "number",
    min: "1",
    max: "600",
    value: "30",
  });
  const editStatus = el("div", { class: "muted", text: "" });
  const closeEditModal = () => {
    editingServer = null;
    editStatus.textContent = "";
    editModal.classList.add("u-hidden");
    editModal.style.display = "";
  };
  const openEditModal = (row) => {
    if (!row) return;
    editingServer = row;
    const sid = String(row.server_id || "");
    editTitle.textContent = tf("plugins.edit.titleNamed", { sid });
    editServerIdLab.textContent = `${t("plugins.col.serverId")}: ${sid}`;
    const cursor = row.cursor && typeof row.cursor === "object" ? row.cursor : {};
    editCursorInput.value = JSON.stringify(cursor, null, 2);
    editEnabledCb.checked = !!row.enabled;
    editTimeoutInput.value = String(Number(row.timeout_s || 30));
    editStatus.textContent = "";
    if (editModal.parentNode !== document.body) document.body.appendChild(editModal);
    editModal.classList.remove("u-hidden");
    editModal.style.display = "";
    setTimeout(() => editCursorInput.focus(), 0);
  };
  editModal.addEventListener("click", (e) => {
    if (e.target === editModal) closeEditModal();
  });
  const editSaveBtn = el("button", {
    class: "btn btn--primary",
    text: t("plugins.action.save"),
    onclick: async () => {
      if (!editingServer) return;
      const sid = String(editingServer.server_id || "").trim();
      if (!sid) return;
      let parsed;
      try {
        parsed = JSON.parse(String(editCursorInput.value || "").trim() || "{}");
      } catch (err) {
        editStatus.textContent = `[edit] invalid JSON: ${String((err && err.message) || err || "parse_failed")}`;
        return;
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        editStatus.textContent = "[edit] Cursor config must be a JSON object";
        return;
      }
      editStatus.textContent = "[edit] saving...";
      try {
        const r = await apiPost("/admin/api/mcp/config", {
          server_id: sid,
          server: parsed,
          enabled: !!editEnabledCb.checked,
          timeout_s: Number(editTimeoutInput.value || 30),
        });
        editStatus.textContent = JSON.stringify(r);
        if (r && r.ok) {
          closeEditModal();
          markPrewarmReminder("mcp_config_updated");
          await softReloadMcpServers();
          repaintExpertBindingDashboard();
        }
      } catch (err) {
        editStatus.textContent = `[edit] failed: ${String((err && err.message) || err || "save_failed")}`;
      }
    },
  });
  editModal.appendChild(
    el("div", { class: "card session-monitor-modal__card", style: "width:min(720px,96vw);" }, [
      editTitle,
      editServerIdLab,
      el("div", { class: "muted", text: t("plugins.edit.configHint") }),
      editCursorInput,
      el("div", { class: "row", style: "align-items:center;gap:10px;flex-wrap:wrap;" }, [
        el("label", { class: "kv" }, [editEnabledCb, document.createTextNode(` ${t("plugins.edit.enabled")}`)]),
        el("label", { text: "timeout_s" }),
        editTimeoutInput,
      ]),
      editStatus,
      el("div", { class: "row u-row-end", style: "gap:8px;margin-top:10px;" }, [
        el("button", { class: "btn", text: t("plugins.action.cancel"), onclick: closeEditModal }),
        editSaveBtn,
      ]),
    ]),
  );

  const mcpInstalledPageRef = { value: 1 };
  const mcpInstalledTotalHolder = { value: mcpServerList.length };
  const mcpInstalledTbody = el("tbody");
  let foldInstalledSummary = null;
  const softReloadMcpServers = async () => {
    const resp = await apiGet("/admin/api/mcp/servers");
    mcpServerList = Array.isArray(resp.servers) ? resp.servers : [];
    bindingServers = mcpServerList.filter((x) => x && String(x.server_id || "").trim());
    mcpInstalledTotalHolder.value = mcpServerList.length;
    if (foldInstalledSummary) {
      foldInstalledSummary.textContent = tf("plugins.fold.installed", { n: mcpServerList.length });
    }
    repaintMcpInstalled();
    mcpInstalledPager.sync();
    renderBindingList();
    renderBindingReverse();
  };
  const buildMcpInstalledRow = (x) => {
    const sid = String(x.server_id || "");
    const cursor = x.cursor && typeof x.cursor === "object" ? x.cursor : {};
    const actions = rowActions("⋯", [
      {
        label: t("plugins.action.edit"),
        onClick: () => openEditModal(x),
      },
      {
        label: x.enabled ? t("plugins.action.disable") : t("plugins.action.enable"),
        onClick: async () => {
          await apiPost("/admin/api/mcp/toggle", { server_id: sid, enabled: !x.enabled });
          markPrewarmReminder("mcp_toggled");
          installStatus.textContent = `[toggle:${sid}] enabled=${!x.enabled ? 1 : 0}`;
          await softReloadMcpServers();
        },
      },
      {
        label: t("plugins.action.health"),
        onClick: async () => {
          const r = await apiPost("/admin/api/mcp/healthcheck", { server_id: sid });
          installStatus.textContent = `[health:${sid}] ` + JSON.stringify(r);
          await softReloadMcpServers();
        },
      },
      {
        label: t("plugins.action.syncTools"),
        onClick: async () => {
          const r = await apiPost("/admin/api/mcp/tools/sync", { server_id: sid });
          installStatus.textContent = `[sync:${sid}] ` + JSON.stringify(r);
          await softReloadMcpServers();
        },
      },
      {
        label: t("plugins.action.delete"),
        danger: true,
        onClick: async () => {
          if (!window.confirm(tf("plugins.confirm.delete", { sid }))) return;
          const r = await apiPost("/admin/api/mcp/delete", { server_id: sid });
          installStatus.textContent = `[delete:${sid}] ` + JSON.stringify(r);
          markPrewarmReminder("mcp_deleted");
          await softReloadMcpServers();
        },
      },
    ]);
    const tools = Array.isArray(x.tools) ? x.tools.map((t0) => String(t0.tool_name || "")).join(", ") : "";
    const healthObj = x.health && typeof x.health === "object" ? x.health : {};
    const healthStatus = String(healthObj.status || "-");
    const healthDetail = healthObj.detail && typeof healthObj.detail === "object" ? healthObj.detail : {};
    const healthErrCode = String(healthDetail.error_code || "");
    const healthErrMsg = String(healthDetail.error || "");
    const healthText = healthErrCode ? `${healthStatus}:${healthErrCode}` : healthStatus;
    const healthTitle =
      healthErrCode || healthErrMsg
        ? `${healthErrCode || "error"} ${healthErrMsg}`.trim()
        : healthDetail.synced_tools != null
          ? `synced_tools=${Number(healthDetail.synced_tools || 0)}`
          : healthStatus;
    return el("tr", { id: `mcp-installed-${sid}` }, [
      tdCell(sid, 28),
      tdCell(cursorCommandSummary(cursor), 56),
      tdCell(tools || "-", 48),
      tdCell(String(x.enabled ? 1 : 0), 8),
      el("td", { text: healthText, title: healthTitle }),
      el("td", { class: "table__cell--actions", "data-copy-disabled": "1" }, [
        el("div", { class: "table__cell-actions" }, [actions]),
      ]),
    ]);
  };
  const repaintMcpInstalled = () => {
    mcpInstalledTbody.innerHTML = "";
    const start = (mcpInstalledPageRef.value - 1) * PLUGINS_PAGE_SIZE;
    mcpServerList.slice(start, start + PLUGINS_PAGE_SIZE).forEach((x) => {
      mcpInstalledTbody.appendChild(buildMcpInstalledRow(x));
    });
  };
  repaintMcpInstalled();
  const mcpInstalledPager = pluginsPagerBar(mcpInstalledTotalHolder, mcpInstalledPageRef, repaintMcpInstalled);

  const foldToolPolicy = pluginsFold(tf("plugins.fold.toolPolicy", { n: pluginCatalog.length }), [
    el("div", { class: "muted", text: t("plugins.fold.toolPolicyHint") }),
    el("div", { class: "row" }, [el("label", { text: "Turn max tool workers (1-32)" }), turnMaxWorkersInput]),
    el("div", { class: "row" }, [el("label", { text: "Turn max tool rounds (1-300)" }), turnMaxRoundsInput]),
    el("div", { class: "row" }, [el("label", { text: "Turn max context messages (10-400)" }), turnMaxCtxInput]),
    el("div", { class: "row" }, [el("label", { text: "SSE queue maxsize (200-50000)" }), sseQueueMaxsizeInput]),
    el("div", { class: "row" }, [el("label", { text: "Tool log max chars (20000-2000000)" }), toolLogMaxCharsInput]),
    el("div", { class: "row" }, [
      el("label", { class: "kv" }, [enableMcpToolsCb, document.createTextNode(" Enable MCP tools")]),
    ]),
    el("div", { class: "row" }, [
      el("label", { class: "kv" }, [enablePluginToolsCb, document.createTextNode(" Enable plugin tools")]),
    ]),
    el("div", { class: "row" }, [
      el("label", { class: "kv" }, [enableRunCommandCb, document.createTextNode(" Enable run_command (high-risk)")]),
    ]),
    el("div", { class: "row" }, [
      el("label", { class: "kv" }, [
        toolContextTruncateCb,
        document.createTextNode(" Compress tool result in agent context (50 chars + hint)"),
      ]),
    ]),
    el("div", { class: "row" }, [
      el("label", { class: "kv" }, [
        chatShowTtftDebugCb,
        document.createTextNode(" Show TTFT debug timings in chat status"),
      ]),
    ]),
    el("div", { class: "row" }, [
      el("label", { text: "Tool message max chars to LLM (0=unlimited, 4096-500000 recommended)" }),
      toolLlmMessageMaxCharsInput,
    ]),
    el("div", {
      class: "muted",
      text: "Set 0 to disable truncation. If some gateways return 400 for oversized tool messages, set back to 24000.",
    }),
    el("div", { class: "row" }, [
      el("label", { text: "MCP filesystem extra roots (| separated)" }),
      mcpFilesystemExtraRootsInput,
    ]),
    el("div", { class: "row" }, [el("label", { text: "MCP env allowlist (comma separated)" }), mcpEnvAllowlistInput]),
    el("div", { class: "row" }, [
      el("label", { text: "oclaw retryable error codes (comma separated)" }),
      oclawRetryableErrorCodesInput,
    ]),
    el("div", { class: "row" }, [
      el("label", { class: "kv" }, [
        oclawRetryCodesStrictModeCb,
        document.createTextNode(" Strict mode: reject unknown retry codes"),
      ]),
    ]),
    el("div", { class: "row" }, [el("label", { text: "WeCom longconn workers (1-8)" }), wecomLongconnWorkersInput]),
    el("div", { class: "row" }, [
      el("label", { text: "WeCom inbound queue maxsize (20-5000)" }),
      wecomLongconnInboundQueueInput,
    ]),
    el("div", { class: "row" }, [saveToolPolicyBtn]),
    toolPolicyStatus,
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("table.name") }),
            el("th", { text: t("table.version") }),
            el("th", { text: t("table.entryPoint") }),
            el("th", { text: t("table.enabled") }),
          ]),
        ]),
        pluginTbody,
      ]),
    ]),
    pluginPager.wrap,
  ]);

  const foldMcpInstall = pluginsFold(t("plugins.fold.installCursor"), [
    el("div", { class: "muted", text: t("plugins.fold.installCursorHint") }),
    jsonInstallInput,
    el("div", { class: "row", style: "flex-wrap:wrap;gap:8px;align-items:center;" }, [
      installBtn,
      mcpExportJsonBtn,
    ]),
    el("div", { class: "muted", text: t("plugins.fold.migrateHint") }),
  ]);

  const foldMcpInstalled = pluginsFold(tf("plugins.fold.installed", { n: mcpServerList.length }), [
    installStatus,
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("plugins.col.serverId") }),
            el("th", { text: t("plugins.col.commandUrl") }),
            el("th", { text: t("plugins.col.tools") }),
            el("th", { text: t("plugins.col.enabled") }),
            el("th", { text: t("plugins.col.health") }),
            el("th", { class: "table__cell--actions", text: t("tenants.rowActions") }),
          ]),
        ]),
        mcpInstalledTbody,
      ]),
    ]),
    mcpInstalledPager.wrap,
  ]);
  foldMcpInstalled.open = true;
  foldInstalledSummary = foldMcpInstalled.querySelector("summary");

  const foldExpertBindingDash = pluginsFold(t("plugins.fold.bindingDash"), [
    el("div", {
      class: "muted",
      text: t("plugins.fold.bindingDashHint"),
    }),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table table--compact" }, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", { text: t("plugins.colSpecialist") }),
            el("th", { text: t("plugins.colBoundMcp") }),
            el("th", { text: t("plugins.colTools") }),
          ]),
        ]),
        expertBindingDashTbody,
      ]),
    ]),
  ]);

  const foldMcpBinding = pluginsFold(t("plugins.fold.bindingEdit"), [
    el("div", { class: "muted", text: t("plugins.binding.hint") }),
    el("div", { class: "row" }, [
      el("label", { text: t("plugins.binding.specialist") }),
      specialistSelect,
      selectAllBindingBtn,
      clearBindingBtn,
      saveBindingBtn,
    ]),
    bindingListWrap,
    el("div", { class: "muted", text: t("plugins.binding.reverse") }),
    bindingReverseWrap,
    bindingStatus,
  ]);

  return renderPageShell(
    {
      title: t("plugins.title"),
      subtitle: tf("plugins.subtitle", { n: PLUGINS_PAGE_SIZE }),
      sections: [
        { id: "plugins-tool-policy", label: t("plugins.toc.policy") },
        { id: "plugins-install", label: t("plugins.toc.install") },
        { id: "plugins-instances", label: t("plugins.toc.instances") },
        { id: "plugins-binding", label: t("plugins.toc.binding") },
      ],
    },
    [
      el("div", { class: "page-grid page-grid--single" }, [
        el("div", { id: "plugins-tool-policy" }, [foldToolPolicy]),
        el("div", { id: "plugins-install" }, [foldMcpInstall]),
        el("div", { id: "plugins-instances" }, [foldMcpInstalled]),
        foldExpertBindingDash,
        el("div", { id: "plugins-binding" }, [foldMcpBinding]),
      ]),
    ],
  );
}

export { pluginsFold, pluginsPagerBar, renderPlugins };
