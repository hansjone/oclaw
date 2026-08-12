import { PAGE_SIZE, CHAT_MESSAGES_FETCH_LIMIT, AUTH_TOKEN_KEY, CHAT_URL_SCOPE_KEY, CHAT_SPECIALIST_PREF_KEY, CHAT_INTERACTION_MODE_KEY, CHAT_MEMORY_MODE_KEY, CHAT_EXECUTION_MODE_KEY, CHAT_USER_MENU_MODE_KEY, CHAT_REASONING_TOGGLE_KEY, EXECUTION_MODE_AGENT, EXECUTION_MODE_PLAN, CHAT_ENABLE_WIKI_EVENT_POLLER, _normalizeEventType, _isAssistantBodyEventType, _buildRenderRows, _needsWsTextFallbackFromRenderRows, interactionModeLabel, specialistLabel, memoryModeShortLabel, showToast, updateJobsBadge, refreshJobsBadge, startJobsBadgePoller, openBackgroundJobsPanel, reasonLabel, fetchDynamicExpertStats, getSessionIdFromUrl, replaceSessionUrl, apiGet, apiPost, apiPatch, apiDelete, el, escapeHtml, formatChatSessionTitle, lookupChannelPeerName, refreshChannelPeerNameMap, dismissChatMenus, isChatStreaming, clearChatPageBlockers, attachChatMenuDismiss, bindChatImageViewer, bindChatMermaidViewer, renderMarkdownHtml, hydrateMermaidIn, extractWsAssistantText, decodeEscapedNewlines, createStreamStitcher, formatToolPanelText, extractSqlAuditPayload, extractToolImageItems, _sqlLimitSuffix, _renderExecutedSqlWithAddedHighlight, wrapAssistantMessage, wrapUserMessage, parseAttachments, appendMessageRow, buildChatBrandLogoNode, openAdminFromChat, fileToPayloadEntry, downloadExport, CHAT_ICON_CLIP, CHAT_ICON_SEND, CHAT_ICON_STOP, state, t } from "./core.js";

async function renderChatUi() {
  let sessionId = getSessionIdFromUrl();
  try {
    const curScope = JSON.stringify({
      t: String((state.authSession && state.authSession.tenant_id) || ""),
      u: String((state.authSession && state.authSession.user_id) || ""),
    });
    const prev = localStorage.getItem(CHAT_URL_SCOPE_KEY) || "";
    if (prev && prev !== curScope) {
      replaceSessionUrl("");
      sessionId = "";
    }
    localStorage.setItem(CHAT_URL_SCOPE_KEY, curScope);
  } catch (_) {}
  const statusBar = el("div", { class: "chat-status", text: t("chat.loading") });
  const sessionsListEl = el("div", { class: "chat-sessions__list" });
  const loadMoreWrap = el("div", { class: "chat-load-more" });
  const messagesEl = el("div", { class: "chat-messages" });
  bindChatImageViewer(messagesEl);
  bindChatMermaidViewer(messagesEl);
  const AUTO_SCROLL_BOTTOM_GAP_PX = 56;
  let shouldFollowMessages = true;
  let autoScrollRaf = 0;
  let autoScrollTimer = 0;
  const isNearBottom = () => {
    const remaining = messagesEl.scrollHeight - (messagesEl.scrollTop + messagesEl.clientHeight);
    return remaining <= AUTO_SCROLL_BOTTOM_GAP_PX;
  };
  const scheduleFollowScroll = (force = false) => {
    if (!force && !shouldFollowMessages) return;
    if (autoScrollRaf) cancelAnimationFrame(autoScrollRaf);
    if (autoScrollTimer) clearTimeout(autoScrollTimer);
    autoScrollRaf = requestAnimationFrame(() => {
      messagesEl.scrollTop = messagesEl.scrollHeight;
      autoScrollRaf = requestAnimationFrame(() => {
        if (force || shouldFollowMessages) messagesEl.scrollTop = messagesEl.scrollHeight;
      });
    });
    // Some async markdown/image/UI post-processing happens after RAF.
    autoScrollTimer = setTimeout(() => {
      if (force || shouldFollowMessages) messagesEl.scrollTop = messagesEl.scrollHeight;
      autoScrollTimer = 0;
    }, 60);
  };
  const scrollMessagesToBottom = (force = false) => {
    scheduleFollowScroll(force);
  };
  messagesEl.addEventListener("scroll", () => {
    shouldFollowMessages = isNearBottom();
    if (messagesEl.scrollTop <= 80) {
      loadOlderMessagesForActive().catch(() => {});
    }
  });
  messagesEl.addEventListener(
    "load",
    (ev) => {
      const target = ev && ev.target;
      if (!target || target.tagName !== "IMG") return;
      scrollMessagesToBottom();
    },
    true,
  );
  const messagesMutationObserver = new MutationObserver(() => {
    scheduleFollowScroll(false);
  });
  messagesMutationObserver.observe(messagesEl, {
    childList: true,
    subtree: true,
    characterData: true,
  });
  const textarea = el("textarea", {
    class: "chat-composer__field",
    rows: "1",
    placeholder: t("chat.placeholder"),
  });
  const fileInput = el("input", { class: "u-hidden", type: "file", multiple: "multiple", accept: "*/*" });
  const attachBtn = el("button", {
    type: "button",
    class: "chat-composer-iconbtn",
    html: CHAT_ICON_CLIP,
    title: t("chat.attach"),
    "aria-label": t("chat.attach"),
  });
  const pendingFilesEl = el("div", { class: "chat-pending-files" });
  const btnSend = el("button", {
    type: "button",
    class: "chat-composer-send",
    html: CHAT_ICON_SEND,
    title: t("chat.send"),
    "aria-label": t("chat.send"),
  });
  const btnStop = el("button", {
    type: "button",
    class: "chat-composer-stop",
    html: CHAT_ICON_STOP,
    title: t("chat.stop"),
    "aria-label": t("chat.stop"),
    disabled: "disabled",
  });
  const composerShell = el("div", { class: "chat-composer-shell" });
  const MAIN_MODE_VALUE = "generalist";
  const EXCLUDED_SPECIALISTS = new Set(["main", "memory", "manager_self", "pycache", "__pycache__", "comprehensive"]);
  let specialistCatalog = [];
  /** Hidden: mode is global-only (⋯ menu). Kept for specialist option list in `publishUserMenuPrefsBridge`. */
  const modeSelect = el("select", {
    class: "input u-hidden",
    "aria-hidden": "true",
    tabIndex: -1,
  });
  let globalMenuModeValue = String(localStorage.getItem(CHAT_USER_MENU_MODE_KEY) || MAIN_MODE_VALUE).toLowerCase();
  if (globalMenuModeValue === "comprehensive" || globalMenuModeValue === "main") globalMenuModeValue = MAIN_MODE_VALUE;
  const modelSelectBtn = el("button", {
    type: "button",
    class: "chat-composer-chip chat-composer-chip--select",
    title: t("chat.activeModelLabel"),
    text: "-",
  });
  const modelSelectWrap = el("div", { class: "chat-model-select" }, [modelSelectBtn]);
  let modelSelectNameToId = new Map();
  let modelSelectOptions = [];
  let modelSelectedKey = "";
  const syncModelSelectBtn = () => {
    const hit = modelSelectOptions.find((o) => o.key === modelSelectedKey);
    modelSelectBtn.textContent = String((hit && hit.label) || "-");
  };
  const openModelSelectMenu = (anchorEl) => {
    dismissChatMenus();
    const items = modelSelectOptions.length
      ? modelSelectOptions.map((opt) =>
          el("button", {
            type: "button",
            class:
              "chat-sess-menu-item" +
              (opt.key === modelSelectedKey ? " chat-sess-menu-item--active" : ""),
            text: opt.label,
            onclick: async (ev) => {
              ev.stopPropagation();
              dismissChatMenus();
              const key = String(opt.key || "").trim();
              if (!key || key === modelSelectedKey) return;
              modelSelectedKey = key;
              syncModelSelectBtn();
              const pid = String(modelSelectNameToId.get(key) || "").trim();
              if (!pid) return;
              try {
                await apiPost("/admin/api/models/active", { profile_id: pid });
                await refreshActiveModelText();
              } catch (e) {
                statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
              }
            },
          }),
        )
      : [el("div", { class: "chat-sess-menu-item muted", text: "-" })];
    const menu = el("div", { class: "chat-sess-menu-pop chat-model-select-pop u-pop-menu" }, items);
    menu.style.position = "fixed";
    menu.style.zIndex = "300";
    const rect = (anchorEl || modelSelectBtn).getBoundingClientRect();
    attachChatMenuDismiss(menu);
    const mrect = menu.getBoundingClientRect();
    const pad = 8;
    let left = rect.left;
    let top = rect.bottom + 6;
    if (top + mrect.height > window.innerHeight - pad) {
      top = Math.max(pad, rect.top - 6 - mrect.height);
    }
    left = Math.max(pad, Math.min(left, window.innerWidth - pad - mrect.width));
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.style.minWidth = `${Math.max(168, Math.ceil(rect.width))}px`;
  };
  modelSelectBtn.addEventListener("click", (ev) => {
    ev.stopPropagation();
    if (modelSelectBtn.disabled) return;
    openModelSelectMenu(ev.currentTarget);
  });
  const normalizeExecutionMode = (v) => {
    const raw = String(v || "").trim().toLowerCase();
    return raw === EXECUTION_MODE_PLAN ? EXECUTION_MODE_PLAN : EXECUTION_MODE_AGENT;
  };
  const executionModeLabel = (v) =>
    normalizeExecutionMode(v) === EXECUTION_MODE_PLAN ? t("chat.execModePlan") : t("chat.execModeAgent");
  let currentExecutionMode = normalizeExecutionMode(localStorage.getItem(CHAT_EXECUTION_MODE_KEY) || EXECUTION_MODE_AGENT);
  const execSelect = el("select", {
    class: "input u-select-exec",
  });
  const refreshExecutionSelect = () => {
    const prev = normalizeExecutionMode(execSelect.value || currentExecutionMode);
    execSelect.innerHTML = "";
    execSelect.appendChild(el("option", { value: EXECUTION_MODE_AGENT, text: t("chat.execModeAgent") }));
    execSelect.appendChild(el("option", { value: EXECUTION_MODE_PLAN, text: t("chat.execModePlan") }));
    execSelect.value = prev;
  };
  const setExecutionMode = (v, { persistLocal = true, saveSession = true } = {}) => {
    currentExecutionMode = normalizeExecutionMode(v);
    if (persistLocal) localStorage.setItem(CHAT_EXECUTION_MODE_KEY, currentExecutionMode);
    refreshExecutionSelect();
    execSelect.value = currentExecutionMode;
    if (saveSession && activeId) saveSessionModePreference();
  };
  execSelect.addEventListener("change", () => {
    setExecutionMode(execSelect.value, { persistLocal: true, saveSession: true });
  });
  refreshExecutionSelect();
  execSelect.value = currentExecutionMode;
  const execSelectWrap = el("span", { class: "chat-exec-mode-wrap u-inline-flex" }, [
    execSelect,
  ]);
  const refreshExecUi = () => {
    // Plan mode removed; keep agent execution only.
    execSelectWrap.style.display = "none";
  };
  const modeOptionLabel = (v) => {
    const key = String(v || "").trim().toLowerCase();
    if (key === "generalist") return t("chat.specialistGeneralist");
    const row = specialistCatalog.find((x) => String(x.id || "").toLowerCase() === key);
    if (!row) return key || t("chat.specialistGeneralist");
    const zh = String(row.display_name_zh || "").trim();
    const en = String(row.display_name_en || "").trim();
    return state.currentLang === "zh" ? (zh || en || key) : (en || zh || key);
  };
  const isSelectableSpecialist = (v) => {
    const key = String(v || "").trim().toLowerCase();
    if (!key || key === "comprehensive" || key === "main") return false;
    if (key === "generalist") return true;
    return specialistCatalog.some((x) => String(x.id || "").toLowerCase() === key);
  };
  const persistModeSelection = () => {
    const v = String(globalMenuModeValue || MAIN_MODE_VALUE).toLowerCase();
    localStorage.setItem(CHAT_INTERACTION_MODE_KEY, "expert");
    localStorage.setItem(CHAT_USER_MENU_MODE_KEY, v);
    localStorage.setItem(CHAT_SPECIALIST_PREF_KEY, v);
  };
  const syncHiddenModeSelectFromGlobal = () => {
    const g = String(globalMenuModeValue || MAIN_MODE_VALUE).toLowerCase();
    if (Array.from(modeSelect.options || []).some((o) => String(o.value || "") === g)) modeSelect.value = g;
    else modeSelect.value = MAIN_MODE_VALUE;
  };
  const applyModeOptions = () => {
    let prev = String(globalMenuModeValue || MAIN_MODE_VALUE).toLowerCase();
    if (prev === "comprehensive" || prev === "main") prev = MAIN_MODE_VALUE;
    modeSelect.innerHTML = "";
    modeSelect.appendChild(el("option", { value: "generalist", text: modeOptionLabel("generalist") }));
    specialistCatalog.forEach((x) => {
      const sid = String(x.id || "").toLowerCase();
      if (!sid || sid === "generalist") return;
      modeSelect.appendChild(el("option", { value: sid, text: modeOptionLabel(sid) }));
    });
    if (Array.from(modeSelect.options).some((o) => String(o.value || "") === prev)) {
      modeSelect.value = prev;
      globalMenuModeValue = prev;
    } else {
      modeSelect.value = MAIN_MODE_VALUE;
      globalMenuModeValue = MAIN_MODE_VALUE;
    }
  };
  const _mm = String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default").toLowerCase();
  localStorage.setItem(CHAT_MEMORY_MODE_KEY, _mm === "store_only" ? "store_only" : "default");
  const loadSpecialistCatalog = async () => {
    try {
      const r = await apiGet("/admin/api/experts");
      const items = Array.isArray(r && r.items) ? r.items : [];
      specialistCatalog = items
        .filter((x) => {
          const id = String((x && x.id) || "").trim().toLowerCase();
          if (!id || EXCLUDED_SPECIALISTS.has(id)) return false;
          const role = String((x && x.role) || "").trim().toLowerCase();
          return role === "expert" || id === "generalist";
        })
        .map((x) => ({
          id: String(x.id || "").trim().toLowerCase(),
          display_name_en: String(x.display_name_en || "").trim(),
          display_name_zh: String(x.display_name_zh || "").trim(),
        }));
    } catch (_) {
      specialistCatalog = [];
    }
    applyModeOptions();
  };
  await loadSpecialistCatalog();
  const activeModelText = el("span", { class: "muted", text: `${t("chat.activeModelLabel")}: -` });
  const applyModelSelectorVisibility = (modelsState) => {
    const show = !(modelsState && modelsState.chat_model_selector_visible === false);
    modelSelectWrap.style.display = show ? "" : "none";
    modelSelectBtn.disabled = !show;
  };
  const refreshActiveModelText = async () => {
    try {
      const ms = await apiGet("/admin/api/models");
      applyModelSelectorVisibility(ms);
      const profiles = Array.isArray(ms.profiles) ? ms.profiles : [];
      const aid = String(ms.active_llm_profile_id || "");
      const p = profiles.find((x) => String(x.id || "") === aid) || null;
      const modelName = String((p && p.model) || "").trim() || "-";
      activeModelText.textContent = `${t("chat.activeModelLabel")}: ${modelName}`;
      modelSelectNameToId = new Map();
      modelSelectOptions = [];
      const usedKeys = new Set();
      profiles.forEach((row) => {
        const pid = String(row && row.id ? row.id : "");
        if (!pid) return;
        const rawName = String(row.name || "").trim();
        const keyBase = rawName || pid;
        let key = keyBase;
        let n = 2;
        while (usedKeys.has(key)) {
          key = `${keyBase}#${n}`;
          n += 1;
        }
        usedKeys.add(key);
        modelSelectNameToId.set(key, pid);
        modelSelectOptions.push({
          key,
          id: pid,
          label: String(row.model || row.name || pid),
        });
      });
      if (p) {
        const firstKey = Array.from(modelSelectNameToId.keys()).find((k) => modelSelectNameToId.get(k) === aid) || "";
        modelSelectedKey = firstKey || "";
      } else if (modelSelectOptions.length > 0) {
        modelSelectedKey = String(modelSelectOptions[0].key || "");
      } else {
        modelSelectedKey = "";
      }
      syncModelSelectBtn();
    } catch (_) {
      applyModelSelectorVisibility(null);
      activeModelText.textContent = `${t("chat.activeModelLabel")}: -`;
      modelSelectNameToId = new Map();
      modelSelectOptions = [];
      modelSelectedKey = "";
      syncModelSelectBtn();
    }
  };
  const loadSessionModePreference = async () => {
    if (!activeId) {
      setExecutionMode(currentExecutionMode, { persistLocal: true, saveSession: false });
      refreshExecUi();
      return;
    }
    try {
      const resp = await apiGet(`/admin/api/chat/sessions/${encodeURIComponent(activeId)}/mode`);
      const m = String((resp && resp.interaction_mode) || "").toLowerCase();
      const s = String((resp && resp.specialist) || "").toLowerCase();
      const mm = String((resp && resp.memory_mode) || "").toLowerCase();
      const em = String((resp && resp.execution_mode) || "").toLowerCase();
      const gm = resp && resp.global_menu && typeof resp.global_menu === "object" ? resp.global_menu : null;
      if (gm) {
        const gIm = String(gm.interaction_mode || "").toLowerCase();
        const gSp = String(gm.specialist || "").toLowerCase();
        if (isSelectableSpecialist(gSp)) globalMenuModeValue = gSp;
        else if (isSelectableSpecialist(gIm)) globalMenuModeValue = gIm;
        else globalMenuModeValue = MAIN_MODE_VALUE;
      } else {
        try {
          const ur = await apiGet("/admin/api/chat/user-mode");
          if (ur && ur.ok) {
            const gum = String((ur.interaction_mode || "").toLowerCase());
            const gus = String((ur.specialist || "").toLowerCase());
            if (isSelectableSpecialist(gus)) globalMenuModeValue = gus;
            else if (isSelectableSpecialist(gum)) globalMenuModeValue = gum;
            else globalMenuModeValue = MAIN_MODE_VALUE;
          }
        } catch (_) {
          if (m === "expert" && isSelectableSpecialist(s)) globalMenuModeValue = s;
          else if (isSelectableSpecialist(s)) globalMenuModeValue = s;
          else globalMenuModeValue = MAIN_MODE_VALUE;
        }
      }
      localStorage.setItem(CHAT_USER_MENU_MODE_KEY, String(globalMenuModeValue || MAIN_MODE_VALUE).toLowerCase());
      syncHiddenModeSelectFromGlobal();
      if (["default", "store_only"].includes(mm)) localStorage.setItem(CHAT_MEMORY_MODE_KEY, mm);
      setExecutionMode(em, { persistLocal: true, saveSession: false });
      persistModeSelection();
      const mml = String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default").toLowerCase();
      localStorage.setItem(CHAT_MEMORY_MODE_KEY, mml === "store_only" ? "store_only" : "default");
      refreshExecUi();
      publishUserMenuPrefsBridge();
    } catch (_) {
      setExecutionMode(currentExecutionMode, { persistLocal: true, saveSession: false });
      refreshExecUi();
    }
  };
  const saveUserGlobalModePreference = async () => {
    try {
      const modeVal = String(globalMenuModeValue || MAIN_MODE_VALUE).toLowerCase();
      const specialist = isSelectableSpecialist(modeVal) ? modeVal : MAIN_MODE_VALUE;
      const resp = await apiPost("/admin/api/chat/user-mode", {
        interaction_mode: "expert",
        specialist,
      });
      localStorage.setItem(CHAT_USER_MENU_MODE_KEY, specialist);
      globalMenuModeValue = specialist;
      if (!resp || resp.ok === false) {
        const detail = String((resp && (resp.error || resp.detail)) || "unknown_error");
        throw new Error(detail);
      }
      // Hard-verify persistence: session switches reload mode from server.
      // If server didn't persist, the UI will "snap back" to defaults.
      try {
        const ur = await apiGet("/admin/api/chat/user-mode");
        if (ur && ur.ok) {
          const gum = String((ur.interaction_mode || "").toLowerCase());
          const gus = String((ur.specialist || "").toLowerCase());
          if (gum !== "expert" || gus !== specialist) {
            const msg =
              t("chat.modeNotPinned", { mode: gum || "-", specialist: gus || "-", want: specialist });
            showToast(msg, { kind: "error", ttlMs: 8000 });
          }
        }
      } catch (_) {}
    } catch (e) {
      // If persistence fails, user will observe "mode resets after reload/restart".
      // Surface this instead of silently swallowing.
      try {
        const msg =
          t("chat.saveModeFailed", { error: String(e || "").slice(0, 180) || "unknown" });
        showToast(msg, { kind: "error", ttlMs: 6500 });
      } catch (_) {}
    }
  };
  const saveSessionModePreference = async () => {
    if (!activeId) return;
    try {
      await apiPost(`/admin/api/chat/sessions/${encodeURIComponent(activeId)}/mode`, {
        memory_mode: String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default"),
        execution_mode: String(currentExecutionMode || EXECUTION_MODE_AGENT),
      });
    } catch (_) {}
  };
  await refreshActiveModelText();
  refreshExecUi();
  const compressBtn = el("button", {
    type: "button",
    class: "chat-composer-chip",
    text: t("chat.compressHistory"),
    onclick: async () => {
      const sid = String(activeId || "");
      if (!sid) return;
      if (!(await confirmChatAction(t("chat.compressHistoryPrompt")))) return;
      try {
        const resp = await apiPost(`/admin/api/chat/sessions/${encodeURIComponent(sid)}/compress-history`, {});
        const r = resp && resp.result ? resp.result : {};
        if (!resp || !resp.ok) {
          const err = String((resp && (resp.error || resp.detail)) || "failed");
          showToast(t("chat.compressHistoryFail", { error: err.slice(0, 180) }), { kind: "error", ttlMs: 6500 });
          return;
        }
        showToast(
          t("chat.compressHistoryOk", {
            scanned: String(Number(r.scanned_tool_messages || 0)),
            rewritten: String(Number(r.rewritten_all_tool_messages || 0)),
            compacted: String(Number(r.compacted_tool_messages || 0)),
            skipped: String(Number(r.skipped_already_guarded || 0)),
          }),
          { kind: "info", ttlMs: 6500 },
        );
        // Reload messages so UI reflects compacted history.
        loadMessagesForActive().catch(() => {});
      } catch (e) {
        showToast(t("chat.compressHistoryFail", { error: String(e || "failed").slice(0, 180) }), { kind: "error", ttlMs: 6500 });
      }
    },
  });
  const composerMetaBar = el("div", { class: "chat-composer-meta" }, [
    execSelectWrap,
    modelSelectWrap,
    compressBtn,
  ]);

  const fitComposerTextarea = () => {
    textarea.style.height = "auto";
    const h = Math.min(Math.max(textarea.scrollHeight, 44), 200);
    textarea.style.height = `${h}px`;
  };
  const syncSendEnabled = () => {
    const ok = String(textarea.value || "").trim().length > 0 || pendingFiles.length > 0;
    btnSend.disabled = !ok;
  };
  textarea.addEventListener("input", () => {
    fitComposerTextarea();
    syncSendEnabled();
  });
  requestAnimationFrame(() => {
    fitComposerTextarea();
    syncSendEnabled();
  });

  let sessions = [];
  let sessionTotal = 0;
  let pendingFiles = [];
  let activeId = sessionId;
  let showToolOutput = state.adminChatShowToolOutput;
  let wikiPollTimerId = null;
  let wikiAfterFinishedAt = {};

  const idsMatch = (a, b) => String(a || "") === String(b || "");
  const confirmChatAction = (message) =>
    new Promise((resolve) => {
      const backdrop = el("div", { class: "chat-confirm-backdrop" });
      const card = el("div", { class: "chat-confirm-card" });
      const text = el("div", { class: "chat-confirm-text", text: String(message || "") });
      const btnCancel = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsCancel") });
      const btnOk = el("button", { type: "button", class: "btn btn--primary", text: t("chat.delete") });
      const close = (ok) => {
        try {
          backdrop.remove();
        } catch (_) {}
        resolve(!!ok);
      };
      btnCancel.addEventListener("click", () => close(false));
      btnOk.addEventListener("click", () => close(true));
      backdrop.addEventListener("click", (ev) => {
        if (ev.target === backdrop) close(false);
      });
      card.appendChild(text);
      card.appendChild(el("div", { class: "row u-row-end" }, [btnCancel, btnOk]));
      backdrop.appendChild(card);
      document.body.appendChild(backdrop);
    });
  const promptChatText = (message, initialValue = "") =>
    new Promise((resolve) => {
      const backdrop = el("div", { class: "chat-confirm-backdrop" });
      const card = el("div", { class: "chat-confirm-card" });
      const text = el("div", { class: "chat-confirm-text", text: String(message || "") });
      const input = el("input", {
        class: "input u-w-full-mt-10",
        type: "text",
        value: String(initialValue || ""),
      });
      const btnCancel = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsCancel") });
      const btnOk = el("button", { type: "button", class: "btn btn--primary", text: t("chat.dispatchLabelsSave") });
      const close = (ok) => {
        if (backdrop.parentNode) backdrop.parentNode.removeChild(backdrop);
        resolve(ok ? String(input.value || "") : null);
      };
      btnCancel.addEventListener("click", () => close(false));
      btnOk.addEventListener("click", () => close(true));
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") {
          ev.preventDefault();
          close(true);
        } else if (ev.key === "Escape") {
          ev.preventDefault();
          close(false);
        }
      });
      backdrop.addEventListener("click", (ev) => {
        if (ev.target === backdrop) close(false);
      });
      card.appendChild(text);
      card.appendChild(input);
      card.appendChild(el("div", { class: "row u-row-end" }, [btnCancel, btnOk]));
      backdrop.appendChild(card);
      document.body.appendChild(backdrop);
      setTimeout(() => {
        try {
          input.focus();
          input.select();
        } catch (_) {}
      }, 0);
    });

  const adoptCreatedSession = (resp) => {
    const s = resp && resp.session ? resp.session : {};
    const sid = String(s.id || "");
    if (!sid) throw new Error("no_session_id");
    sessions = [s, ...sessions.filter((x) => !idsMatch(x.id, sid))];
    sessionTotal += 1;
    activeId = sid;
    replaceSessionUrl(sid);
    wikiAfterFinishedAt[String(sid)] = "";
  };

  const _summarizeWikiEvent = (ev) => {
    const status = String(ev && ev.status ? ev.status : "");
    const ok = !!(ev && ev.ok);
    const result = (ev && ev.result) || {};
    if (status !== "done" || !ok) {
      const err = String((result && (result.error || result.last_error)) || (ev && ev.error) || "failed");
      return { kind: "error", text: t("chat.wikiToastFailed", { error: err.slice(0, 180) || "failed" }), actions: [] };
    }
    const dm = result.dedupMerge || {};
    const merged = Number(dm.merged_count || 0) || 0;
    const skipped = Number(dm.skipped_dup || 0) || 0;
    const topicCounts = dm.topic_counts && typeof dm.topic_counts === "object" ? dm.topic_counts : {};
    let topTopic = "";
    let topN = -1;
    for (const [k, v] of Object.entries(topicCounts)) {
      const n = Number(v || 0) || 0;
      if (n > topN) {
        topN = n;
        topTopic = String(k || "");
      }
    }
    const actions = [];
    return { kind: "info", text: t("chat.wikiToastMerged", { merged: String(merged), skipped: String(skipped) }), actions };
  };

  const pollWikiEvents = async () => {
    if (!CHAT_ENABLE_WIKI_EVENT_POLLER) return;
    const sid = String(activeId || "");
    if (!sid) return;
    const after = String((wikiAfterFinishedAt && wikiAfterFinishedAt[sid]) || "");
    try {
      const q = after ? `?after=${encodeURIComponent(after)}&limit=20` : "?limit=20";
      const resp = await apiGet(`/admin/api/chat/sessions/${encodeURIComponent(sid)}/wiki-events${q}`);
      if (!resp || !resp.ok) return;
      const events = Array.isArray(resp.events) ? resp.events : [];
      if (!events.length) return;
      for (const ev of events) {
        const fin = String((ev && ev.finished_at) || "");
        if (fin && (!wikiAfterFinishedAt[sid] || fin > wikiAfterFinishedAt[sid])) {
          wikiAfterFinishedAt[sid] = fin;
        }
        const msg = _summarizeWikiEvent(ev);
        if (msg && msg.text) {
          const node = showToast(msg.text, { kind: msg.kind, ttlMs: 6500 });
          const acts = Array.isArray(msg.actions) ? msg.actions : [];
          if (acts.length) {
            const btnRow = el("div", { class: "row u-row-wrap-mt-loose" });
            for (const a of acts) {
              btnRow.appendChild(
                el("button", {
                  type: "button",
                  class: "btn u-btn-compact",
                  text: String(a.label || "View"),
                  onclick: (e) => {
                    e.stopPropagation();
                    try {
                      if (typeof a.onClick === "function") a.onClick();
                    } catch (_) {}
                  },
                }),
              );
            }
            node.appendChild(btnRow);
          }
        }
      }
    } catch (_) {}
  };

  const startWikiPoller = () => {
    if (!CHAT_ENABLE_WIKI_EVENT_POLLER) return;
    if (wikiPollTimerId != null) return;
    wikiPollTimerId = setInterval(pollWikiEvents, 2200);
    // kick once
    pollWikiEvents().catch(() => {});
  };

  const stopWikiPoller = () => {
    if (wikiPollTimerId != null) {
      clearInterval(wikiPollTimerId);
      wikiPollTimerId = null;
    }
  };

  const syncPendingUi = () => {
    pendingFilesEl.innerHTML = "";
    pendingFiles.forEach((f, i) => {
      const row = el("div", { class: "chat-pending-row" }, [
        el("span", { class: "muted", text: f.name }),
        el("button", {
          type: "button",
          class: "chat-pending-remove",
          text: "×",
          title: t("chat.remove"),
          onclick: () => {
            pendingFiles.splice(i, 1);
            syncPendingUi();
          },
        }),
      ]);
      pendingFilesEl.appendChild(row);
    });
    syncSendEnabled();
  };

  attachBtn.addEventListener("click", () => fileInput.click());
  const setReasoningVisible = (next, { showStatus = true } = {}) => {
    showToolOutput = !!next;
    state.adminChatShowToolOutput = showToolOutput;
    localStorage.setItem(CHAT_REASONING_TOGGLE_KEY, showToolOutput ? "1" : "0");
    const isStreaming = composerShell.classList.contains("chat-composer-shell--busy");
    if (showStatus && isStreaming) {
      // Avoid clearing active stream bubble mid-turn (loadMessagesForActive() resets messagesEl).
      statusBar.textContent = `${showToolOutput ? t("chat.tools.visible") : t("chat.tools.hidden")} · ${
        t("chat.applyAfterTurn")
      }`;
      return;
    }
    if (showStatus) statusBar.textContent = showToolOutput ? t("chat.tools.visible") : t("chat.tools.hidden");
    loadMessagesForActive().catch(() => {});
  };
  const publishUserMenuPrefsBridge = () => {
    try {
      window.__chatUserMenuPrefs = {
        getModeOptions: () =>
          Array.from(modeSelect.options || []).map((o) => ({
            value: String(o.value || ""),
            label: String(o.text || o.label || o.value || ""),
          })),
        getModeValue: () => String(globalMenuModeValue || MAIN_MODE_VALUE).toLowerCase(),
        setModeValue: async (v) => {
          const next = String(v || "").toLowerCase();
          if (!Array.from(modeSelect.options || []).some((o) => String(o.value || "") === next)) return;
          globalMenuModeValue = next;
          localStorage.setItem(CHAT_USER_MENU_MODE_KEY, globalMenuModeValue);
          syncHiddenModeSelectFromGlobal();
          await saveUserGlobalModePreference();
          refreshExecUi();
          publishUserMenuPrefsBridge();
        },
        getReasoningVisible: () => !!showToolOutput,
        setReasoningVisible: async (v) => {
          setReasoningVisible(!!v, { showStatus: true });
        },
      };
    } catch (_) {}
  };
  publishUserMenuPrefsBridge();
  fileInput.addEventListener("change", () => {
    const fs = fileInput.files;
    if (!fs || !fs.length) return;
    for (const f of fs) pendingFiles.push(f);
    fileInput.value = "";
    syncPendingUi();
  });

  const openSessionMenu = (sid, title) => {
    const menu = document.createElement("div");
    menu.className = "chat-sess-menu-pop";
    const mk = (label, fn) =>
      el("button", {
        type: "button",
        class: "chat-sess-menu-item",
        text: label,
        onclick: async (ev) => {
          ev.stopPropagation();
          menu.remove();
          await fn();
        },
      });
    menu.appendChild(
      mk(t("chat.rename"), async () => {
        const nv = await promptChatText(t("chat.rename"), title);
        if (nv == null) return;
        try {
          await apiPatch(`/admin/api/chat/sessions/${encodeURIComponent(sid)}`, { title: nv.trim() });
          await refreshSessions();
        } catch (e) {
          statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
        }
      }),
    );
    menu.appendChild(
      mk(t("chat.delete"), async () => {
        if (!(await confirmChatAction(t("chat.deleteConfirm")))) return;
        try {
          const r = await apiDelete(`/admin/api/chat/sessions/${encodeURIComponent(sid)}`);
          const next = String(r.next_session_id || "");
          if (idsMatch(activeId, sid)) {
            activeId = next;
            replaceSessionUrl(activeId);
          }
          await refreshSessions();
        } catch (e) {
          statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
        }
      }),
    );
    menu.appendChild(
      mk(t("chat.exportMd"), async () => {
        try {
          await downloadExport(sid, "md");
        } catch (e) {
          statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
        }
      }),
    );
    menu.appendChild(
      mk(t("chat.exportJson"), async () => {
        try {
          await downloadExport(sid, "json");
        } catch (e) {
          statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
        }
      }),
    );
    menu.appendChild(
      mk(t("chat.fork"), async () => {
        try {
          const r = await apiPost(`/admin/api/chat/sessions/${encodeURIComponent(sid)}/fork`, {});
          const ns = r.session || {};
          const nid = String(ns.id || "");
          if (!nid) return;
          activeId = nid;
          replaceSessionUrl(nid);
          await refreshSessions();
        } catch (e) {
          statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
        }
      }),
    );
    menu.appendChild(
      mk(t("chat.audit"), () => {
        openAdminFromChat("audit", sid);
      }),
    );
    return menu;
  };

  const paintSessions = () => {
    sessionsListEl.innerHTML = "";
    loadMoreWrap.innerHTML = "";
    if (!sessions.length) {
      sessionsListEl.appendChild(
        el("div", { class: "muted u-empty-pad", text: t("chat.noSessions") }),
      );
      return;
    }
    for (const s of sessions) {
      const sid = String(s.id || "");
      const title = String(s.title || sid || "");
      const peerHint = String(s.peer_name || s.peer_display_name || "").trim();
      let pretty = formatChatSessionTitle(title, peerHint);
      if (!pretty.sublabel && pretty.channel) {
        const looked = lookupChannelPeerName(title, pretty);
        if (looked) pretty = formatChatSessionTitle(title, looked);
      }
      const row = el("div", { class: "chat-sess-row" + (idsMatch(activeId, sid) ? " chat-sess-row--active" : "") });
      const btnChildren = [];
      if (pretty.badge) {
        btnChildren.push(
          el("span", {
            class: `chat-sess-badge chat-sess-badge--${pretty.channel || "other"}`,
            text: pretty.badge,
          }),
        );
      }
      const labelKids = [el("span", { class: "chat-sess-btn__name", text: pretty.label })];
      if (pretty.sublabel) {
        labelKids.push(el("span", { class: "chat-sess-btn__id", text: pretty.sublabel }));
      }
      btnChildren.push(el("span", { class: "chat-sess-btn__label" }, labelKids));
      const btn = el(
        "button",
        {
          class: "chat-sess-btn" + (idsMatch(activeId, sid) ? " chat-sess-btn--active" : ""),
          title: pretty.full || title,
          onclick: () => {
            activeId = sid;
            replaceSessionUrl(sid);
            paintSessions();
            Promise.all([loadMessagesForActive(), loadSessionModePreference()]).catch((e) => {
              statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
            });
            startWikiPoller();
          },
        },
        btnChildren,
      );
      const more = el("button", {
        type: "button",
        class: "chat-sess-more" + (idsMatch(activeId, sid) ? " chat-sess-more--active" : ""),
        text: "⋯",
        title: t("chat.sessionMenu"),
        onclick: (ev) => {
          ev.stopPropagation();
          clearChatPageBlockers();
          const menu = openSessionMenu(sid, title);
          menu.style.position = "fixed";
          menu.style.zIndex = "300";
          const rect = more.getBoundingClientRect();
          attachChatMenuDismiss(menu);
          const mrect = menu.getBoundingClientRect();
          const pad = 8;
          let left = rect.left;
          let top = rect.bottom + 4;
          if (top + mrect.height > window.innerHeight - pad) {
            top = rect.top - 4 - mrect.height;
          }
          left = Math.max(pad, Math.min(left, window.innerWidth - pad - mrect.width));
          top = Math.max(pad, Math.min(top, window.innerHeight - pad - mrect.height));
          menu.style.left = `${left}px`;
          menu.style.top = `${top}px`;
        },
      });
      row.appendChild(btn);
      row.appendChild(more);
      sessionsListEl.appendChild(row);
    }
    if (sessions.length < sessionTotal) {
      const lm = el("button", {
        class: "btn u-w-full-mt-8",
        text: t("chat.loadMore"),
        onclick: async () => {
          try {
            statusBar.textContent = t("chat.loading");
            const off = sessions.length;
            const resp = await apiGet(
              `/admin/api/chat/sessions?limit=${PAGE_SIZE}&offset=${off}`,
            );
            const next = Array.isArray(resp.sessions) ? resp.sessions : [];
            sessionTotal = intOr(resp.total, sessionTotal);
            sessions = sessions.concat(next);
            statusBar.textContent = "";
            paintSessions();
          } catch (e) {
            statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
          }
        },
      });
      loadMoreWrap.appendChild(lm);
    }
  };

  function intOr(v, d) {
    const n = parseInt(String(v), 10);
    return Number.isFinite(n) ? n : d;
  }

  const handleDeleteMessage = async (messageId) => {
    const sid = String(activeId || "").trim();
    const mid = parseInt(String(messageId || 0), 10);
    if (!sid || !Number.isFinite(mid) || mid <= 0) return;
    await apiDelete(`/admin/api/chat/sessions/${encodeURIComponent(sid)}/messages/${mid}`);
    await loadMessagesForActive();
  };

  const rowRenderOptions = {
    onDeleteMessage: handleDeleteMessage,
    onConfirm: confirmChatAction,
    onActionStatus: (msg) => {
      statusBar.textContent = String(msg || "");
    },
  };

  let historyHasMore = false;
  let historyOldestId = 0;
  let historyLoadedCount = 0;
  let historyTotal = 0;
  let historyLoadingOlder = false;
  let historyCapEl = null;

  const ensureHistoryCap = () => {
    if (!historyHasMore && historyLoadedCount > 0 && historyTotal > 0 && historyLoadedCount >= historyTotal) {
      if (historyCapEl && historyCapEl.parentNode) historyCapEl.remove();
      historyCapEl = null;
      return;
    }
    if (!historyHasMore && !historyLoadingOlder) {
      if (historyCapEl && historyCapEl.parentNode) historyCapEl.remove();
      historyCapEl = null;
      return;
    }
    if (!historyCapEl) historyCapEl = el("div", { class: "muted chat-msg-cap" });
    historyCapEl.textContent = historyLoadingOlder
      ? t("chat.loadingOlder")
      : t("chat.historyTruncated", {
          shown: String(historyLoadedCount || 0),
          total: String(historyTotal || historyLoadedCount || 0),
        });
    if (historyCapEl.parentNode !== messagesEl) {
      messagesEl.insertBefore(historyCapEl, messagesEl.firstChild);
    }
  };

  const loadMessagesForActive = async (opts = {}) => {
    loadMessagesForActive._rid = (loadMessagesForActive._rid || 0) + 1;
    const rid = loadMessagesForActive._rid;
    shouldFollowMessages = true;
    historyHasMore = false;
    historyOldestId = 0;
    historyLoadedCount = 0;
    historyTotal = 0;
    historyLoadingOlder = false;
    if (!activeId) {
      loadMessagesForActive._needsWsTextFallback = true;
      messagesEl.innerHTML = "";
      historyCapEl = null;
      statusBar.textContent = sessions.length ? "" : t("chat.noSessions");
      if (!sessions.length) messagesEl.appendChild(el("div", { class: "muted", text: t("chat.empty") }));
      return 0;
    }
    statusBar.textContent = t("chat.loading");
    loadMessagesForActive._needsWsTextFallback = true;
    try {
      const resp = await apiGet(
        `/admin/api/chat/sessions/${encodeURIComponent(activeId)}/messages?limit=${CHAT_MESSAGES_FETCH_LIMIT}`,
      );
      if (rid !== loadMessagesForActive._rid) return 0;
      const msgs = Array.isArray(resp.messages) ? resp.messages : [];
      const renderRows = _buildRenderRows(msgs);
      loadMessagesForActive._needsWsTextFallback = _needsWsTextFallbackFromRenderRows(renderRows);
      historyTotal = intOr(resp.message_count, msgs.length);
      historyLoadedCount = msgs.length;
      historyHasMore = !!resp.has_more;
      historyOldestId = msgs.length ? intOr(msgs[0].id, 0) : 0;
      // End-of-turn hydrate: if the server returns nothing renderable yet (PG commit lag, transient API
      // glitch) but the caller still has a live stream worth keeping, do not wipe messagesEl — that
      // caused "stream flashes then entire dialog is empty" when reasoning/tool-output mode reloads.
      if (!renderRows.length && opts.keepDomIfNoHistoryRows) {
        statusBar.textContent = "";
        return 0;
      }
      messagesEl.innerHTML = "";
      historyCapEl = null;
      ensureHistoryCap();
      if (!renderRows.length) {
        messagesEl.appendChild(el("div", { class: "muted", text: t("chat.empty") }));
      } else {
        for (const m of renderRows) {
          await appendMessageRow(messagesEl, m, rowRenderOptions);
        }
      }
      statusBar.textContent = "";
      scrollMessagesToBottom(true);
      return renderRows.length;
    } catch (e) {
      // Keep existing message list on reload failure (e.g. toggle reload races),
      // so users don't perceive "messages disappeared".
      loadMessagesForActive._needsWsTextFallback = true;
      statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
      return -1;
    }
  };

  const loadOlderMessagesForActive = async () => {
    if (!activeId || !historyHasMore || historyLoadingOlder || !historyOldestId) return 0;
    if (isChatStreaming()) return 0;
    historyLoadingOlder = true;
    ensureHistoryCap();
    const prevHeight = messagesEl.scrollHeight;
    const prevTop = messagesEl.scrollTop;
    const rid = loadMessagesForActive._rid || 0;
    try {
      const resp = await apiGet(
        `/admin/api/chat/sessions/${encodeURIComponent(activeId)}/messages?limit=${CHAT_MESSAGES_FETCH_LIMIT}&before_id=${encodeURIComponent(String(historyOldestId))}`,
      );
      if (rid !== loadMessagesForActive._rid) return 0;
      const msgs = Array.isArray(resp.messages) ? resp.messages : [];
      if (!msgs.length) {
        historyHasMore = false;
        ensureHistoryCap();
        return 0;
      }
      const renderRows = _buildRenderRows(msgs);
      historyTotal = intOr(resp.message_count, historyTotal);
      historyLoadedCount += msgs.length;
      historyHasMore = !!resp.has_more;
      historyOldestId = intOr(msgs[0].id, historyOldestId);
      ensureHistoryCap();
      const anchor = historyCapEl && historyCapEl.parentNode === messagesEl ? historyCapEl.nextSibling : messagesEl.firstChild;
      for (const m of renderRows) {
        await appendMessageRow(messagesEl, m, { ...rowRenderOptions, prependBefore: anchor });
      }
      const delta = messagesEl.scrollHeight - prevHeight;
      messagesEl.scrollTop = prevTop + delta;
      return renderRows.length;
    } catch (e) {
      if (typeof showToast === "function") {
        showToast(`${t("chat.error")}: ${String(e)}`, { kind: "error", ttlMs: 4500 });
      }
      return -1;
    } finally {
      historyLoadingOlder = false;
      ensureHistoryCap();
    }
  };

  const reloadSessionsOnly = async () => {
    await refreshChannelPeerNameMap().catch(() => {});
    const resp = await apiGet(`/admin/api/chat/sessions?limit=${PAGE_SIZE}&offset=0`);
    sessions = Array.isArray(resp.sessions) ? resp.sessions : [];
    sessionTotal = intOr(resp.total, sessions.length);
    paintSessions();
  };

  const refreshSessions = async () => {
    statusBar.textContent = t("chat.loading");
    await refreshChannelPeerNameMap().catch(() => {});
    const resp = await apiGet(`/admin/api/chat/sessions?limit=${PAGE_SIZE}&offset=0`);
    sessions = Array.isArray(resp.sessions) ? resp.sessions : [];
    sessionTotal = intOr(resp.total, sessions.length);
    // URL 里的 session_id 可能属于其他账号或已删除；若不在当前用户列表中则丢弃，避免 GET …/messages 404。
    const activeInList =
      Boolean(activeId) &&
      sessions.length > 0 &&
      sessions.some((s) => idsMatch(s.id, activeId));
    if (activeId && !activeInList) {
      activeId = "";
      replaceSessionUrl("");
    }
    if (!activeId && sessions.length) {
      activeId = String(sessions[0].id || "");
      replaceSessionUrl(activeId);
    }
    if (!activeId && sessions.length === 0) {
      try {
        const resp = await apiPost("/admin/api/chat/sessions", {});
        adoptCreatedSession(resp);
      } catch (e) {
        statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
      }
    }
    paintSessions();
    await loadMessagesForActive();
    await loadSessionModePreference();
    if (!activeId) {
      stopWikiPoller();
    } else {
      startWikiPoller();
    }
    if (!String(statusBar.textContent || "").includes(t("chat.error"))) statusBar.textContent = "";
  };

  const btnNew = el("button", {
    type: "button",
    class: "chat-nav__new",
    title: `${t("chat.newSession")}`,
    onclick: async () => {
      try {
        statusBar.textContent = t("chat.loading");
        const resp = await apiPost("/admin/api/chat/sessions", {});
        adoptCreatedSession(resp);
        await loadSessionModePreference();
        paintSessions();
        messagesEl.innerHTML = "";
        messagesEl.appendChild(el("div", { class: "muted", text: t("chat.empty") }));
        statusBar.textContent = "";
      } catch (e) {
        statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
      }
    },
  });
  btnNew.appendChild(el("span", { class: "chat-nav__newGlyph", "aria-hidden": "true" }));
  btnNew.appendChild(
    el("span", {
      class: "chat-nav__newLabel",
      "data-i18n": "chat.newSession",
      text: t("chat.newSession"),
    }),
  );

  const jobsBadge = el("span", { class: "chat-jobs-badge chat-jobs-badge--idle", text: "0" });
  state.jobsBadgeEl = jobsBadge;
  const jobsLabel = el("span", { class: "chat-nav__jobsLabel", text: t("chat.jobs") });
  state.jobsBtnLabelEl = jobsLabel;
  const btnJobs = el("button", {
    type: "button",
    class: "chat-nav__jobs",
    title: t("chat.jobsRunning", { n: 0 }),
    onclick: () => {
      openBackgroundJobsPanel().catch((e) => showToast(`${t("chat.error")}: ${String(e)}`, { kind: "error" }));
    },
  });
  btnJobs.appendChild(jobsLabel);
  btnJobs.appendChild(jobsBadge);
  startJobsBadgePoller();
  // Immediate paint so count is visible before first interval tick.
  updateJobsBadge(0);
  refreshJobsBadge();

  class OclawWsChatTransport {
    constructor({ tokenProvider }) {
      this.tokenProvider = tokenProvider;
      this.ws = null;
      this.reqSeq = 0;
      this.msgQueue = [];
      this.waiters = [];
      this.lastSeq = 0;
      this._sessionSubscriptions = new Set();
      this._reconnectBaseMs = 500;
      this._reconnectCapMs = 5000;
      this._maxReconnectAttempts = 4;
    }
    _isOpen() {
      return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
    _wsUrl() {
      const origin = String(window.location.origin || "").trim();
      if (origin.startsWith("http://") || origin.startsWith("https://")) {
        const wsOrigin = origin.replace(/^http/i, "ws");
        return `${wsOrigin}/ws`;
      }
      const u = new URL(window.location.href);
      u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
      u.pathname = "/ws";
      u.search = "";
      u.hash = "";
      return u.toString();
    }
    _nextReqId() {
      this.reqSeq += 1;
      return `req_${Date.now()}_${this.reqSeq}`;
    }
    async _openAndHandshake() {
      if (this._isOpen()) return;
      let lastErr = null;
      for (let i = 0; i <= this._maxReconnectAttempts; i += 1) {
        try {
          await this._openAndHandshakeOnce();
          await this._restoreSubscriptions();
          return;
        } catch (err) {
          lastErr = err;
          this.close();
          if (i >= this._maxReconnectAttempts) break;
          const delay = Math.min(this._reconnectCapMs, this._reconnectBaseMs * Math.pow(2, i));
          const jitter = Math.floor(Math.random() * 150);
          await new Promise((resolve) => setTimeout(resolve, delay + jitter));
        }
      }
      throw lastErr || new Error("ws_open_failed");
    }
    async _openAndHandshakeOnce() {
      const token = String(this.tokenProvider() || "");
      const wsUrl = this._wsUrl();
      const ws = new WebSocket(wsUrl);
      this.ws = ws;
      this.msgQueue = [];
      this.waiters = [];
      ws.addEventListener("message", (ev) => {
        let parsed = null;
        try {
          parsed = JSON.parse(String(ev.data || "{}"));
        } catch (_) {
          parsed = null;
        }
        if (!parsed) return;
        if (parsed && parsed.type === "event" && Number.isFinite(Number(parsed.seq))) {
          this.lastSeq = Math.max(this.lastSeq, Number(parsed.seq) || 0);
        }
        const waiter = this.waiters.shift();
        if (waiter) {
          waiter.resolve(parsed);
        } else {
          this.msgQueue.push(parsed);
        }
      });
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error(`ws_open_timeout:${wsUrl}`)), 7000);
        ws.onopen = () => {
          clearTimeout(timer);
          resolve();
        };
        ws.onerror = () => {
          clearTimeout(timer);
          reject(new Error(`ws_open_failed:${wsUrl}`));
        };
      });
      const challenge = await this._recv();
      if (!(challenge && challenge.type === "event" && challenge.event === "connect.challenge")) {
        throw new Error("ws_invalid_challenge");
      }
      const reqId = this._nextReqId();
      ws.send(
        JSON.stringify({
          type: "req",
          id: reqId,
          method: "connect",
          params: {
            minProtocol: 3,
            maxProtocol: 3,
            lastSeq: Number(this.lastSeq || 0),
            client: { id: "webchat-ui", version: "0.1", platform: navigator.platform || "web", mode: "webchat" },
            role: "operator",
            scopes: ["operator.read", "operator.write"],
            auth: token ? { token } : {},
          },
        }),
      );
      const res = await this._recv();
      if (!res || res.type !== "res" || res.id !== reqId || !res.ok) {
        throw new Error(`ws_connect_failed:${JSON.stringify((res && res.error) || {})}`);
      }
    }
    async _sendReqAndAwait(method, params) {
      await this._openAndHandshake();
      const reqId = this._nextReqId();
      this.ws.send(JSON.stringify({ type: "req", id: reqId, method: String(method || ""), params: params || {} }));
      for (;;) {
        const msg = await this._recv();
        if (msg && msg.type === "res" && msg.id === reqId) {
          if (!msg.ok) throw new Error(`ws_req_failed:${JSON.stringify(msg.error || {})}`);
          return msg.payload || {};
        }
      }
    }
    async _restoreSubscriptions() {
      const items = Array.from(this._sessionSubscriptions);
      for (let i = 0; i < items.length; i += 1) {
        const key = String(items[i] || "");
        if (!key) continue;
        await this._sendReqAndAwait("sessions.messages.subscribe", { sessionKey: key });
      }
    }
    _trackSessionSubscription(sessionId) {
      const key = String(sessionId || "").trim();
      if (!key) return;
      this._sessionSubscriptions.add(key);
    }
    _recv() {
      const ws = this.ws;
      if (!ws) return Promise.reject(new Error("ws_not_connected"));
      if (this.msgQueue.length) return Promise.resolve(this.msgQueue.shift());
      return new Promise((resolve, reject) => {
        const onErr = () => {
          cleanup();
          reject(new Error("ws_receive_failed"));
        };
        const onClose = () => {
          cleanup();
          reject(new Error("ws_closed"));
        };
        const cleanup = () => {
          ws.removeEventListener("error", onErr);
          ws.removeEventListener("close", onClose);
          this.waiters = this.waiters.filter((w) => w.resolve !== resolve);
        };
        this.waiters.push({ resolve, reject });
        ws.addEventListener("error", onErr);
        ws.addEventListener("close", onClose);
      });
    }
    close() {
      if (this.ws) {
        try {
          this.ws.close(1000, "done");
        } catch (_) {}
        this.ws = null;
      }
    }
    async sendSessionSend({
      sessionId,
      text,
      attachments,
      interactionMode,
      specialist,
      memoryMode,
      executionMode,
      idempotencyKey,
      signal,
      onEvent,
    }) {
      await this._openAndHandshake();
      this._trackSessionSubscription(sessionId);
      await this._sendReqAndAwait("sessions.messages.subscribe", { sessionKey: String(sessionId || "") });
      const stableIdempotencyKey = String(idempotencyKey || `idem_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
      const reqId = this._nextReqId();
      const req = {
        type: "req",
        id: reqId,
        method: "chat.send",
        params: {
          sessionKey: String(sessionId || ""),
          message: String(text || ""),
          attachments: Array.isArray(attachments) ? attachments : [],
          idempotencyKey: stableIdempotencyKey,
          thinking: "default",
          interaction_mode: String(interactionMode || "expert"),
          specialist: String(specialist || "generalist"),
          memory_mode: String(memoryMode || "default"),
          execution_mode: String(executionMode || "agent"),
          lang: state.currentLang === "en" ? "en" : "zh",
        },
      };
      this.ws.send(JSON.stringify(req));
      let doneMeta = null;
      let retriedAfterReconnect = false;
      while (true) {
        if (signal && signal.aborted) throw new DOMException("Aborted", "AbortError");
        let msg = null;
        try {
          msg = await this._recv();
        } catch (err) {
          const em = String((err && err.message) || err || "").toLowerCase();
          if (!retriedAfterReconnect && (em.includes("ws_closed") || em.includes("ws_receive_failed"))) {
            retriedAfterReconnect = true;
            await this._openAndHandshake();
            this.ws.send(JSON.stringify(req));
            continue;
          }
          throw err;
        }
        if (
          msg &&
          msg.type === "event" &&
          (msg.event === "chat" ||
            msg.event === "session.message" ||
            msg.event === "agent.event" ||
            msg.event === "session.tool" ||
            msg.event === "session.marker" ||
            msg.event === "session.turn_started") &&
          typeof onEvent === "function"
        ) {
          const payload = msg.payload || {};
          onEvent({ event: String(msg.event || ""), payload });
          const d = msg.event === "chat" ? { phase: String(payload.state || "") } : {};
          const phase = String(d.phase || "");
          if (phase === "final" || phase === "error" || phase === "aborted") {
            return doneMeta;
          }
          continue;
        }
        if (msg && msg.type === "res" && msg.id === reqId) {
          if (!msg.ok) throw new Error(`ws_req_failed:${JSON.stringify(msg.error || {})}`);
          const p = msg.payload || {};
          doneMeta = {
            interaction_mode: String(p.interactionMode || interactionMode || ""),
            execution_mode: String(p.executionMode || executionMode || EXECUTION_MODE_AGENT || ""),
            selected_specialist: String(p.selectedSpecialist || specialist || ""),
            dispatch_reason: String(p.dispatchReason || ""),
            manager_selected_specialist: String(p.managerSelectedSpecialist || ""),
            requested_specialist: String(p.requestedSpecialist || ""),
            dynamic_agent_used: !!p.dynamicAgentUsed,
            dynamic_agent_name: String(p.dynamicAgentName || ""),
            relay_pointer_count: Number(p.relayPointerCount || 0) || 0,
            relay_envelope_present: !!p.relayEnvelopePresent,
            relay_envelope_pointer_count: Number(p.relayEnvelopePointerCount || 0) || 0,
            relay_ttl_turn_count: Number(p.relayTtlTurnCount || 0) || 0,
            relay_ttl_session_count: Number(p.relayTtlSessionCount || 0) || 0,
            relay_ttl_keep_count: Number(p.relayTtlKeepCount || 0) || 0,
            ttft: p.ttft && typeof p.ttft === "object" ? p.ttft : null,
            reply: String(p.reply || ""),
          };
          if (String(p.status || "") === "started") {
            continue;
          }
          // Oclaw-style: response ack does not terminate the stream.
          // Wait strictly for chat final/aborted/error or session.message assistant.
          continue;
        }
        if (msg && msg.type === "event" && msg.event === "chat") {
          const p = msg.payload || {};
          const d = { phase: String(p.state || "") };
          const phase = String(d.phase || "");
          if (phase === "final" || phase === "error" || phase === "aborted") {
            return doneMeta;
          }
        }
      }
    }
    async sendChatAbort({ sessionId, runId }) {
      // Abort should use the same WS connection when possible.
      await this._openAndHandshake();
      const reqId = this._nextReqId();
      this.ws.send(
        JSON.stringify({
          type: "req",
          id: reqId,
          method: "chat.abort",
          params: { sessionKey: String(sessionId || ""), runId: runId ? String(runId) : undefined },
        }),
      );
      for (;;) {
        const msg = await this._recv();
        if (msg && msg.type === "res" && msg.id === reqId) {
          if (!msg.ok) throw new Error(`ws_req_failed:${JSON.stringify(msg.error || {})}`);
          return msg.payload || {};
        }
      }
    }
  }

  let currentStreamAbortController = null;
  let currentWsTransport = null;
  let currentAbortMeta = { sessionId: "", runId: "" };
  // Disable WS send inactivity timeout by default (0 = disabled).
  // Some gateways can legitimately stream slower than 3 minutes.
  const WS_CHAT_SEND_TIMEOUT_MS = 0;
  const isAbortError = (err) => {
    const name = String(err && err.name ? err.name : "");
    const msg = String(err && err.message ? err.message : err || "");
    return name === "AbortError" || msg.toLowerCase().includes("aborted");
  };

  const _silentReplyPattern = /^\s*NO_REPLY\s*$/;
  const _isSilentReplyStream = (text) => _silentReplyPattern.test(String(text || ""));
  const _normalizeAssistantMessage = (message, { requireRole = false, requireContentArray = false } = {}) => {
    if (!message || typeof message !== "object") return null;
    const m = message;
    const role = String(m.role || "").toLowerCase();
    if (requireRole && role !== "assistant") return null;
    if (requireContentArray && !Array.isArray(m.content)) return null;
    const hasRootAttachments = m.attachments != null && m.attachments !== "";
    if (!("content" in m) && !("text" in m) && !hasRootAttachments) return null;
    return m;
  };
  const _expandAssistantMessageForRender = (message) => {
    if (!message || typeof message !== "object") return [];
    const mesAttParsed = parseAttachments(message.attachments);
    const mesAtt = mesAttParsed.length ? mesAttParsed : null;
    const srcEventType = _normalizeEventType(message.event_type || message.eventType);
    const fallbackEventType = srcEventType === "tool_call" ? "tool_call" : "assistant_text";
    const base = {
      role: "assistant",
      id: message.id,
      timestamp: message.timestamp != null ? message.timestamp : new Date().toISOString(),
    };
    const out = [];
    let ep = message.event_payload;
    if (typeof ep === "string" && String(ep).trim()) {
      try {
        ep = JSON.parse(ep);
      } catch (_) {
        ep = null;
      }
    }
    if (ep && typeof ep === "object" && !Array.isArray(ep)) {
      const rc = decodeEscapedNewlines(String(ep.reasoning_content || "")).trim();
      if (rc) out.push({ ...base, content: rc, event_type: "reasoning" });
    }
    const contentItems = Array.isArray(message.content) ? message.content : [];
    for (const item of contentItems) {
      if (!item || typeof item !== "object") continue;
      const typ = String(item.type || "").toLowerCase();
      if (typ === "reasoning" || typ === "reasoning_text" || typ === "thinking" || typ === "thought") {
        const reasoningText = decodeEscapedNewlines(String(item.text || item.content || item.summary || "")).trim();
        if (reasoningText) out.push({ ...base, content: reasoningText, event_type: "reasoning" });
        continue;
      }
      const textBody = decodeEscapedNewlines(
        String(item.text || item.output_text || item.content || item.value || ""),
      ).trim();
      if (!textBody) continue;
      if (typ === "text" || typ === "output_text" || typ === "assistant_text" || !typ) {
        out.push({ ...base, content: textBody, event_type: "assistant_text" });
      }
    }
    const textFallback = decodeEscapedNewlines(
      typeof message.content === "string" ? message.content : typeof message.text === "string" ? message.text : "",
    ).trim();
    const hasBodyText = out.some((row) => {
      const et = _normalizeEventType(row.event_type);
      return _isAssistantBodyEventType(et) || et === "tool_call";
    });
    if (textFallback && !hasBodyText) {
      out.push({ ...base, content: textFallback, event_type: fallbackEventType });
    }
    if (!out.length && (textFallback || (mesAtt && mesAtt.length))) {
      return [
        {
          ...base,
          content: textFallback,
          event_type: fallbackEventType,
          tool_calls: message.tool_calls != null ? message.tool_calls : message.toolCalls,
          ...(mesAtt && mesAtt.length ? { attachments: mesAtt } : {}),
        },
      ];
    }
    if (out.length) {
      const _isBodyRow = (row) => {
        const et = _normalizeEventType(row && row.event_type);
        return _isAssistantBodyEventType(et) || et === "tool_call";
      };
      let attachIdx = out.length - 1;
      for (let i = out.length - 1; i >= 0; i -= 1) {
        if (_isBodyRow(out[i])) {
          attachIdx = i;
          break;
        }
      }
      out[attachIdx] = {
        ...out[attachIdx],
        tool_calls: message.tool_calls != null ? message.tool_calls : message.toolCalls,
      };
      // Avoid duplicating blobs: attach WS/API root attachments to the latest body row only.
      if (mesAtt && mesAtt.length) {
        for (let i = out.length - 1; i >= 0; i -= 1) {
          if (_isBodyRow(out[i])) {
            out[i] = { ...out[i], attachments: mesAtt };
            break;
          }
        }
      }
      return out;
    }
    return [];
  };

  const sendMessageStream = async (userText, attachmentPayload, turnId) => {
    const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
    const turnStartedAtMs = Date.now();
    let streamBubble = null;
    let streamRow = null;
    let doneMeta = null;
    let chatStream = "";
    let chatRunId = null;
    let chatStreamSegments = [];
    let renderRafId = null;
    let renderPending = false;
    let transportUsed = "ws";
    let typingRafId = null;
    let typingTimerId = null;
    let streamStatusTimerId = null;
    let streamStatusBase = "oclaw";
    let streamDisplayTarget = "";
    let streamDisplayShown = "";
    let streamTextBuffer = "";
    const streamStitcher = createStreamStitcher();
    let streamMermaidTimerId = null;
    let perCharNewlineMode = false;
    let perCharNewlineScore = 0;
    let toolSeq = 0;
    let hasRealStreamText = false;
    let sawWsChatEvent = false;
    let sawWsTerminalEvent = false;
    let sawStreamToolRefAttachments = false;
    let markerState = { p: 0, e: false, ep: 0, t: 0, s: 0, k: 0, reclaimed: 0 };
    let turnAcceptedAtMs = null;
    let phaseRunningAtMs = null;
    let firstDeltaAtMs = null;
    const _numOrNull = (v) => {
      if (v === null || v === undefined) return null;
      const n = Number(v);
      return Number.isFinite(n) ? n : null;
    };
    const _sleep = (ms) =>
      new Promise((resolve) => {
        setTimeout(resolve, Math.max(0, Number(ms) || 0));
      });
    const _recoverLatestAssistantFromHistory = async () => {
      const resp = await apiGet(
        `/admin/api/chat/sessions/${encodeURIComponent(activeId)}/messages?limit=${CHAT_MESSAGES_FETCH_LIMIT}`,
      );
      const msgs = Array.isArray(resp && resp.messages) ? resp.messages : [];
      if (!msgs.length) return false;
      let last = null;
      for (let i = msgs.length - 1; i >= 0; i--) {
        const m = msgs[i];
        if (String((m && m.role) || "").toLowerCase() !== "assistant") continue;
        // Recovery should only accept visible assistant body, not intermediate
        // reasoning/tool-call events; otherwise we may terminate on a partial line.
        const et = String((m && m.event_type) || "").trim().toLowerCase();
        if (et && !_isAssistantBodyEventType(et)) continue;
        if (!String((m && m.content) || "").trim()) continue;
        {
          last = m;
          break;
        }
      }
      if (!last) return false;
      const tsRaw = String((last && last.timestamp) || "");
      const tsMs = tsRaw ? Date.parse(tsRaw) : NaN;
      const fresh = Number.isFinite(tsMs) ? tsMs >= turnStartedAtMs - 1500 : true;
      if (!fresh) return false;
      await loadMessagesForActive();
      return true;
    };
    const ensureStreamBubble = () => {
      if (streamBubble) return streamBubble;
      const inner = el("div", { class: "chat-msg chat-msg--assistant" });
      inner.appendChild(el("div", { class: "chat-msg__stream-status", text: `${t("chat.status.oclaw")}...` }));
      inner.appendChild(el("div", { class: "chat-msg__md", html: "" }));
      streamRow = wrapAssistantMessage(inner, new Date().toISOString());
      streamBubble = inner;
      messagesEl.appendChild(streamRow);
      return streamBubble;
    };
    const _labelPhase = (phase) => {
      const p = String(phase || "").toLowerCase();
      if (!p) return "oclaw";
      if (p.includes("plan")) return "plan";
      if (p.includes("tool")) return "tool";
      if (p.includes("agent")) return "agent";
      if (p.includes("core")) return "oclaw";
      if (p.includes("manager")) return "oclaw";
      if (p === "start") return "start";
      if (p === "running") return "running";
      if (p === "end") return "end";
      if (p === "error") return "error";
      if (p === "started") return "oclaw";
      if (p === "delta") return "agent";
      return p;
    };
    const _statusLabel = (key) => {
      const k = String(key || "").trim();
      if (!k) return t("chat.status.oclaw");
      const dictKey = `chat.status.${k}`;
      const localized = t(dictKey);
      if (localized !== dictKey) return localized;
      return k;
    };
    const _setStreamStatusBase = (phase) => {
      streamStatusBase = _labelPhase(phase);
      _setDynamicStreamStatus();
    };
    const _setDynamicStreamStatus = () => {
      const bubble = ensureStreamBubble();
      const statusEl = bubble.querySelector(".chat-msg__stream-status");
      if (!statusEl) return;
      const dots = ".".repeat((Math.floor(Date.now() / 400) % 3) + 1);
      const baseLabel = _statusLabel(streamStatusBase);
      const elapsedMs = turnAcceptedAtMs ? Math.max(0, Date.now() - Number(turnAcceptedAtMs || 0)) : 0;
      const elapsedText = elapsedMs > 0 ? ` ${Math.round(elapsedMs / 100) / 10}s` : "";
      statusEl.textContent = `${baseLabel}${elapsedText}${dots}`;
    };
    const _startDynamicStreamStatus = () => {
      _setDynamicStreamStatus();
      if (streamStatusTimerId != null) return;
      streamStatusTimerId = setInterval(_setDynamicStreamStatus, 400);
    };
    const _stopDynamicStreamStatus = () => {
      if (streamStatusTimerId != null) {
        clearInterval(streamStatusTimerId);
        streamStatusTimerId = null;
      }
    };
    const _markStreamTerminal = (phase, noteText) => {
      const bubble = ensureStreamBubble();
      const statusEl = bubble.querySelector(".chat-msg__stream-status");
      if (statusEl) statusEl.textContent = _statusLabel(_labelPhase(phase));
      const md = bubble.querySelector(".chat-msg__md");
      if (md && !String(md.textContent || "").trim() && String(noteText || "").trim()) {
        md.innerHTML = `<div class="chat-msg__plain">${escapeHtml(String(noteText || ""))}</div>`;
      }
    };
    const _composeStreamPlainText = () => {
      const chunks = [];
      for (const seg of chatStreamSegments) {
        if (!seg || seg.type !== "text") continue;
        const txt = String(seg.text || "");
        if (txt) chunks.push(txt);
      }
      // Keep 1:1 character mapping with original text segments.
      // Never inject separators here; otherwise typewriter offsets drift.
      return decodeEscapedNewlines(chunks.join(""));
    };
    const _normalizeStreamTargetForRender = (raw) => {
      let s = String(raw || "").replace(/\r/g, "");
      if (!s) return "";
      // Streaming-only guard: some gateways emit per-char newlines in delta chunks,
      // producing vertical "one character per line" layout.
      const lines = s.split("\n");
      if (lines.length >= 4) {
        let short = 0;
        let nonEmpty = 0;
        let totalLen = 0;
        for (const ln of lines) {
          const t = String(ln || "");
          if (!t) continue;
          nonEmpty += 1;
          totalLen += t.length;
          if (t.length <= 2) short += 1;
        }
        const avgLen = nonEmpty ? totalLen / nonEmpty : 0;
        const shortRatio = nonEmpty ? short / nonEmpty : 0;
        if (shortRatio >= 0.75 && avgLen <= 2.0) {
          // Join characters back for live display.
          s = lines.join("");
        } else {
          // Fallback: if newline density is abnormally high, collapse line breaks for live view.
          const nl = lines.length - 1;
          if (nl >= 8 && nl >= Math.floor(s.length * 0.2)) {
            s = s.replace(/\n+/g, "");
          }
        }
      }
      return s;
    };
    const _renderStreamCompositeNow = () => {
      const bubble = ensureStreamBubble();
      const md = bubble.querySelector(".chat-msg__md");
      if (md) {
        const blocks = [];
        if (markerState.p > 0 || markerState.e || markerState.ep > 0) {
          blocks.push(
            `<div class="chat-msg__stream-status">${escapeHtml(
              t("chat.marker.summary", {
                p: String(markerState.p || 0),
                e: markerState.e ? "1" : "0",
                ep: String(markerState.ep || 0),
              }),
            )}</div>`,
          );
          blocks.push(
            `<div class="chat-msg__stream-status">${escapeHtml(
              t("chat.marker.ttl", {
                t: String(markerState.t || 0),
                s: String(markerState.s || 0),
                k: String(markerState.k || 0),
              }),
            )}</div>`,
          );
          if ((Number(markerState.reclaimed || 0) || 0) > 0) {
            blocks.push(
              `<div class="chat-msg__stream-status">${escapeHtml(
                t("chat.marker.reclaimed", { n: String(markerState.reclaimed || 0) }),
              )}</div>`,
            );
          }
        }
        let textIdx = 0;
        let textBuf = "";
        const flushTextBuf = () => {
          if (!String(textBuf || "").trim()) {
            textBuf = "";
            return;
          }
          blocks.push(
            `<div class="chat-msg__plain">${escapeHtml(decodeEscapedNewlines(textBuf)).replace(/\\n/g, "<br/>")}</div>`,
          );
          textBuf = "";
        };
        for (const seg of chatStreamSegments) {
          if (!seg) continue;
          if (seg.type === "text") {
            const full = String(seg.text || "");
            if (!full) continue;
            const showLen = Math.max(0, Math.min(full.length, streamDisplayShown.length - textIdx));
            const shown = full.slice(0, showLen);
            textIdx += full.length;
            if (!shown) continue;
            textBuf += shown;
            continue;
          }
          if (seg.type === "tool") {
            const title = String(seg.title || "tool");
            const body = String(seg.body || "");
            const images = Array.isArray(seg.images) ? seg.images : [];
            // Live stream: always render tool cards from session.tool so过程态完整；showToolOutput 仍用于历史聚合气泡。
            flushTextBuf();
            const audit = seg.sqlAudit && typeof seg.sqlAudit === "object" ? seg.sqlAudit : null;
            if (audit) {
              const guard = audit.guard && typeof audit.guard === "object" ? audit.guard : {};
              const autoLimit = _sqlLimitSuffix(audit.inputSql, audit.executedSql);
              const executedDiffHtml = _renderExecutedSqlWithAddedHighlight(audit.inputSql, audit.executedSql);
              blocks.push(
                `<details class="chat-msg__reasoning"><summary>${escapeHtml(title)} · SQL audit</summary>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:8px;">
  <div><div class="muted" style="margin-bottom:4px;">input SQL</div><pre class="chat-msg__reasoning-pre">${escapeHtml(String(audit.inputSql || ""))}</pre></div>
  <div><div class="muted" style="margin-bottom:4px;">executed SQL (added highlighted)</div><pre class="chat-msg__reasoning-pre">${executedDiffHtml}</pre></div>
</div>
${autoLimit ? `<div style="margin-top:8px;"><span class="muted">auto-added clause:</span> <code style="background:#fff7ed;color:#9a3412;padding:2px 6px;border-radius:4px;">${escapeHtml(autoLimit)}</code></div>` : ""}
<div class="muted" style="margin-top:8px;line-height:1.5;">
  readonly_enforced=${escapeHtml(String(!!guard.readonly_enforced))} ·
  multi_statement_forbidden=${escapeHtml(String(!!guard.multi_statement_forbidden))} ·
  auto_limit_applied=${escapeHtml(String(!!guard.auto_limit_applied))} ·
  result_row_cap=${escapeHtml(String(guard.result_row_cap != null ? guard.result_row_cap : ""))} ·
  engine=${escapeHtml(String(audit.engine || ""))} ·
  rows_returned=${escapeHtml(String(audit.rowsReturned != null ? audit.rowsReturned : ""))}
</div>
</details>`,
              );
            } else {
              blocks.push(
                `<details class="chat-msg__reasoning"><summary>${escapeHtml(title)}</summary><pre class="chat-msg__reasoning-pre">${escapeHtml(body)}</pre></details>`,
              );
            }
            for (const im of images) {
              const src = String((im && im.src) || "").trim();
              if (!src) continue;
              blocks.push(`<div class="chat-att-wrap"><img class="chat-att-img" src="${escapeHtml(src)}" alt="tool image" /></div>`);
            }
          }
        }
        const currentShown = streamDisplayShown.slice(textIdx);
        if (String(currentShown || "").trim()) textBuf += currentShown;
        flushTextBuf();
        md.innerHTML = blocks.join("");
      }
      scrollMessagesToBottom();
    };
    const _maybeScheduleStreamMermaidHydrate = () => {
      // Mermaid render is expensive and can crash if DOM is re-written mid-run.
      // For streaming, only hydrate when we see a complete mermaid fence block.
      const bubble = streamBubble;
      if (!bubble) return;
      const md = bubble.querySelector(".chat-msg__md");
      if (!md) return;
      const raw = String(streamDisplayShown || "");
      if (!raw.includes("```mermaid")) return;
      // Require a closed fence to avoid parsing partial streams.
      if (!/```mermaid[\s\S]*?\n```/m.test(raw)) return;
      if (streamMermaidTimerId != null) clearTimeout(streamMermaidTimerId);
      streamMermaidTimerId = setTimeout(() => {
        streamMermaidTimerId = null;
        try {
          hydrateMermaidIn(md);
        } catch (_) {}
      }, 180);
    };
    const renderStreamComposite = () => {
      if (renderPending) return;
      renderPending = true;
      renderRafId = requestAnimationFrame(() => {
        renderPending = false;
        renderRafId = null;
        _renderStreamCompositeNow();
        _maybeScheduleStreamMermaidHydrate();
      });
    };
    const _scheduleTypingTick = () => {
      if (typingRafId != null) return;
      typingRafId = requestAnimationFrame(() => {
        typingRafId = null;
        if (streamDisplayShown === streamDisplayTarget) {
          renderStreamComposite();
          return;
        }
        const remain = streamDisplayTarget.length - streamDisplayShown.length;
        if (remain <= 0) {
          streamDisplayShown = streamDisplayTarget;
          renderStreamComposite();
          return;
        }
        // Adaptive typing speed: when backlog grows, catch up quickly
        // to avoid fragmented/laggy streaming and end-of-turn text bursts.
        const step = Math.max(4, Math.min(180, Math.ceil(remain / 10)));
        streamDisplayShown = streamDisplayTarget.slice(0, streamDisplayShown.length + step);
        renderStreamComposite();
        if (typingTimerId != null) {
          clearTimeout(typingTimerId);
          typingTimerId = null;
        }
        typingTimerId = setTimeout(() => {
          typingTimerId = null;
          _scheduleTypingTick();
        }, 14);
      });
    };
    const _sanitizeStreamDelta = (delta) => {
      let s = streamStitcher.push(delta);
      if (!s) return "";
      // Detect and suppress "one char per line" noise early in the stream.
      // Typical pattern: "好\n问\n题\n" or chunks like "好\n".
      const nl = (s.match(/\n/g) || []).length;
      const nonNlLen = s.replace(/\n/g, "").length;
      if (nl > 0 && nonNlLen > 0 && nonNlLen <= 2 && nl >= nonNlLen) {
        perCharNewlineScore += 1;
      } else if (nonNlLen >= 4 && nl === 0) {
        perCharNewlineScore = Math.max(0, perCharNewlineScore - 1);
      }
      if (!perCharNewlineMode && perCharNewlineScore >= 3) perCharNewlineMode = true;
      if (perCharNewlineMode) {
        // Drop all newlines in this mode; rely on natural wrapping.
        s = s.replace(/\n+/g, "");
      }
      return s;
    };
    const appendStreamTextChunk = (chunk) => {
      const piece = _sanitizeStreamDelta(chunk);
      if (!piece) return;
      streamTextBuffer = `${streamTextBuffer}${piece}`;
      chatStream = streamTextBuffer;
      // Keep strict chronological order: append text deltas as independent segments.
      chatStreamSegments.push({ type: "text", text: piece });
      streamDisplayTarget = _normalizeStreamTargetForRender(_composeStreamPlainText());
      _scheduleTypingTick();
    };
    const appendToolSegment = (payload) => {
      const p = payload && typeof payload === "object" ? payload : {};
      const name = String(p.name || "tool");
      const liveTag = t("chat.liveFull");
      const key = `${name}:${++toolSeq}`;
      const rawPayload = p.payload != null ? p.payload : p;
      const titleTool =
        rawPayload && typeof rawPayload === "object" && String(rawPayload.tool_name || "").trim()
          ? String(rawPayload.tool_name || "").trim()
          : "";
      const displayName =
        name === "tool_use_call" && titleTool
          ? `${t("chat.call")} · ${titleTool}`
          : name;
      const body = formatToolPanelText(name, rawPayload, { streamMode: true });
      const sqlAudit = extractSqlAuditPayload(rawPayload);
      const images = extractToolImageItems(rawPayload);
      const _containsRefAttachments = (obj, depth = 0) => {
        if (!obj || typeof obj !== "object" || depth > 4) return false;
        // Common case: { attachments: [...] }
        if (Array.isArray(obj.attachments)) {
          for (const att of obj.attachments) {
            if (!att || typeof att !== "object") continue;
            const typ = String(att.type || "").toLowerCase();
            if (!typ) continue;
            if (typ.endsWith("_ref") || typ === "relay_pointer") return true;
          }
        }
        // Recurse a few common container keys first.
        const keys = ["result", "payload", "message", "data", "output"];
        for (const k of keys) {
          if (k in obj && _containsRefAttachments(obj[k], depth + 1)) return true;
        }
        // Shallow scan other object values (bounded).
        let scanned = 0;
        for (const v of Object.values(obj)) {
          if (scanned++ > 12) break;
          if (_containsRefAttachments(v, depth + 1)) return true;
        }
        return false;
      };
      if (_containsRefAttachments(rawPayload)) sawStreamToolRefAttachments = true;
      chatStreamSegments.push({
        type: "tool",
        key,
        title: `${displayName} ${liveTag}`.trim(),
        body,
        sqlAudit,
        images,
      });
    };
    const appendFinalAssistant = async (message, fallbackText) => {
      const wsAttachments =
        message && typeof message === "object" && message.attachments != null ? message.attachments : null;
      const normalized = _normalizeAssistantMessage(message, { requireRole: false, requireContentArray: false });
      if (normalized) {
        const rows = _buildRenderRows(_expandAssistantMessageForRender(normalized));
        const last = rows && rows.length ? rows[rows.length - 1] : null;
        if (last) {
          if (wsAttachments != null && (last.attachments == null || last.attachments === "")) {
            last.attachments = wsAttachments;
          }
          if (streamRow && streamRow.parentNode) streamRow.remove();
          await appendMessageRow(messagesEl, last, rowRenderOptions);
          scrollMessagesToBottom(true);
          return true;
        }
      }
      const t0 = String(fallbackText || "").trim();
      if (t0 && !_isSilentReplyStream(t0)) {
        if (streamRow && streamRow.parentNode) streamRow.remove();
        await appendMessageRow(
          messagesEl,
          {
            role: "assistant",
            content: decodeEscapedNewlines(t0),
            timestamp: new Date().toISOString(),
            ...(wsAttachments != null ? { attachments: wsAttachments } : {}),
          },
          rowRenderOptions,
        );
        scrollMessagesToBottom(true);
        return true;
      }
      return false;
    };
    btnStop.disabled = false;
    btnSend.disabled = true;
    composerShell.classList.add("chat-composer-shell--busy");
    const abortController = new AbortController();
    currentStreamAbortController = abortController;
    currentAbortMeta = { sessionId: String(activeId || ""), runId: "" };
    // End-of-turn reload gating: avoid clearing/repainting messagesEl after we already
    // finalized the stream bubble in-place (prevents end "flash").
    let turnFinalized = false;
    let turnStreamedEnough = false;
    try {
      const transport = new OclawWsChatTransport({
        tokenProvider: () => token,
      });
      currentWsTransport = transport;
      try {
        // Immediate assistant placeholder bubble with dynamic status.
        ensureStreamBubble();
        _startDynamicStreamStatus();
        let wsLastActivityAt = Date.now();
        const wsSendPromise = transport.sendSessionSend({
          sessionId: activeId,
          text: userText,
          attachments: attachmentPayload,
          interactionMode: "expert",
          idempotencyKey: String(turnId || ""),
          specialist: isSelectableSpecialist(String(globalMenuModeValue || "").toLowerCase())
            ? String(globalMenuModeValue || "generalist").toLowerCase()
            : "generalist",
          memoryMode: String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default"),
          executionMode: String(currentExecutionMode || EXECUTION_MODE_AGENT),
          signal: abortController.signal,
          onEvent: async (frame) => {
            wsLastActivityAt = Date.now();
            const eventName = String((frame && frame.event) || "");
            const payload = (frame && frame.payload) || {};
            if (eventName === "agent.event") {
              try {
                const stream = String((payload && payload.stream) || "");
                const data = (payload && payload.data) || {};
                const phase = String((data && data.phase) || "").toLowerCase();
                if (stream === "lifecycle") {
                  if (phase === "start" && !turnAcceptedAtMs) {
                    turnAcceptedAtMs = Date.now();
                  }
                  if (phase === "running" && !phaseRunningAtMs) {
                    phaseRunningAtMs = Date.now();
                  }
                }
              } catch (_) {}
              _setStreamStatusBase((payload && (payload.stream || payload.event || payload.type)) || "agent");
              return;
            }
            if (eventName === "session.marker") {
              const action = String(payload.action || "").toLowerCase();
              markerState = {
                p: Number(payload.relayPointerCount || markerState.p || 0) || 0,
                e: payload.relayEnvelopePresent != null ? !!payload.relayEnvelopePresent : !!markerState.e,
                ep: Number(payload.relayEnvelopePointerCount || markerState.ep || 0) || 0,
                t: Number(payload.relayTtlTurnCount || markerState.t || 0) || 0,
                s: Number(payload.relayTtlSessionCount || markerState.s || 0) || 0,
                k: Number(payload.relayTtlKeepCount || markerState.k || 0) || 0,
                reclaimed:
                  action === "turn_reclaimed"
                    ? Number(payload.reclaimedTurnPointers || payload.relayTtlTurnCount || 0) || 0
                    : Number(markerState.reclaimed || 0) || 0,
              };
              renderStreamComposite();
              return;
            }
            if (eventName === "session.turn_started") {
              turnAcceptedAtMs = Number(payload.acceptedAt || Date.now()) || Date.now();
              if (payload.runId) {
                chatRunId = String(payload.runId);
                currentAbortMeta = { sessionId: String(activeId || ""), runId: String(chatRunId || "") };
              }
              _setStreamStatusBase("start");
              return;
            }
            if (eventName === "session.tool") {
              _setStreamStatusBase("tool");
              // Keep strict order: tool card appears exactly where tool event arrives.
              appendToolSegment(payload);
              streamDisplayTarget = _normalizeStreamTargetForRender(_composeStreamPlainText());
              _scheduleTypingTick();
              return;
            }
            if (eventName !== "chat") return;
            sawWsChatEvent = true;
            const state = String(payload.state || "");
            if (state) _setStreamStatusBase(state);
            if (payload.runId && !chatRunId) chatRunId = String(payload.runId);
            if (chatRunId) currentAbortMeta = { sessionId: String(activeId || ""), runId: String(chatRunId || "") };
            if (chatRunId && payload.runId && String(payload.runId) !== chatRunId && state !== "final") return;
            if (state === "delta") {
              if (!firstDeltaAtMs) firstDeltaAtMs = Date.now();
              const next = extractWsAssistantText(payload.message);
              const d = String(payload.delta || "");
              if (d && !_isSilentReplyStream(d)) {
                appendStreamTextChunk(decodeEscapedNewlines(d));
                hasRealStreamText = true;
              } else if (typeof next === "string" && next && !_isSilentReplyStream(next)) {
                // Fallback when gateway doesn't include delta.
                // Prefer monotonic append from snapshot deltas.
                const snapshot = decodeEscapedNewlines(next);
                if (snapshot.startsWith(streamTextBuffer)) {
                  appendStreamTextChunk(snapshot.slice(streamTextBuffer.length));
                } else if (!streamTextBuffer.startsWith(snapshot)) {
                  appendStreamTextChunk(snapshot);
                }
                hasRealStreamText = true;
              }
              return;
            }
            if (state === "final") {
              sawWsTerminalEvent = true;
              _stopDynamicStreamStatus();
              streamDisplayShown = streamDisplayTarget;
              const hasStreamToolImages = chatStreamSegments.some(
                (seg) => seg && seg.type === "tool" && Array.isArray(seg.images) && seg.images.length > 0,
              );
              let ok = false;
              if (hasStreamToolImages) {
                // Keep stream bubble as final UI when it already contains image blocks.
                renderStreamComposite();
                _markStreamTerminal("end", t("chat.status.end"));
                ok = true;
              } else if (state.adminChatShowToolOutput || sawStreamToolRefAttachments) {
                // Hydrate from history for reasoning / tool panels / ref attachments. If the DB has not
                // yet persisted the assistant reply (or only has the user row), n>0 used to skip
                // appendFinalAssistant and removed the stream bubble — leaving an empty pane like the
                // user screenshot. Use _needsWsTextFallback when WS still holds usable text.
                const hadStream =
                  hasRealStreamText ||
                  (Array.isArray(chatStreamSegments) && chatStreamSegments.length > 0) ||
                  !!String(chatStream || "").trim();
                const fbLine = extractWsAssistantText(payload.message || {}) || chatStream;
                const fbTrim = String(fbLine || "").trim();
                const fbOk = !!fbTrim && !_isSilentReplyStream(fbTrim);
                const n = await loadMessagesForActive({ keepDomIfNoHistoryRows: hadStream });
                const needWsFallback =
                  hadStream && fbOk && (n < 0 || !!loadMessagesForActive._needsWsTextFallback);
                if (n >= 0) {
                  try {
                    if (streamRow && streamRow.parentNode) streamRow.remove();
                  } catch (_) {}
                }
                if (needWsFallback) {
                  if (n < 0) {
                    try {
                      if (streamRow && streamRow.parentNode) streamRow.remove();
                    } catch (_) {}
                  }
                  ok = await appendFinalAssistant(payload.message, fbLine);
                } else if (n > 0) {
                  ok = true;
                } else {
                  ok = n === 0;
                }
                scrollMessagesToBottom(true);
              } else {
                ok = await appendFinalAssistant(
                  payload.message,
                  extractWsAssistantText(payload.message || {}) || chatStream,
                );
              }
              if (!ok) _markStreamTerminal("end", t("chat.status.end"));
              chatStream = "";
              streamTextBuffer = "";
              chatRunId = null;
              sawStreamToolRefAttachments = false;
              const streamedEnough = hasRealStreamText || chatStreamSegments.length > 0 || sawWsChatEvent;
              turnFinalized = true;
              turnStreamedEnough = streamedEnough;
              chatStreamSegments = [];
              if (streamMermaidTimerId != null) {
                clearTimeout(streamMermaidTimerId);
                streamMermaidTimerId = null;
              }
              // Avoid end-of-turn flash: only reload history when stream had no usable content.
              if (!streamedEnough) {
                setTimeout(() => {
                  loadMessagesForActive().catch(() => {});
                }, 350);
              }
              if (!ok) statusBar.textContent = "";
              return;
            }
            if (state === "aborted") {
              sawWsTerminalEvent = true;
              _stopDynamicStreamStatus();
              streamDisplayShown = streamDisplayTarget;
              const ok = await appendFinalAssistant(payload.message, chatStream);
              if (!ok) _markStreamTerminal("error", "aborted");
              turnFinalized = true;
              turnStreamedEnough = hasRealStreamText || chatStreamSegments.length > 0 || sawWsChatEvent;
              chatStream = "";
              streamTextBuffer = "";
              chatRunId = null;
              chatStreamSegments = [];
              if (streamMermaidTimerId != null) {
                clearTimeout(streamMermaidTimerId);
                streamMermaidTimerId = null;
              }
              return;
            }
            if (state === "error") {
              sawWsTerminalEvent = true;
              _stopDynamicStreamStatus();
              _markStreamTerminal("error", String(payload.errorMessage || "chat error"));
              turnFinalized = true;
              turnStreamedEnough = hasRealStreamText || chatStreamSegments.length > 0 || sawWsChatEvent;
              chatStream = "";
              streamTextBuffer = "";
              chatRunId = null;
              chatStreamSegments = [];
              if (streamMermaidTimerId != null) {
                clearTimeout(streamMermaidTimerId);
                streamMermaidTimerId = null;
              }
              statusBar.textContent = `${t("chat.error")}: ${String(payload.errorMessage || "chat error")}`;
            }
          },
        });
        let wsWatchdog = 0;
        const wsSendObserved = wsSendPromise.finally(() => {
          if (wsWatchdog) {
            clearInterval(wsWatchdog);
            wsWatchdog = 0;
          }
        });
        if (Number(WS_CHAT_SEND_TIMEOUT_MS || 0) > 0) {
          const wsInactivityTimeoutPromise = new Promise((_, reject) => {
            wsWatchdog = setInterval(() => {
              if (Date.now() - wsLastActivityAt > WS_CHAT_SEND_TIMEOUT_MS) {
                if (wsWatchdog) {
                  clearInterval(wsWatchdog);
                  wsWatchdog = 0;
                }
                reject(new Error(`ws_send_timeout:${WS_CHAT_SEND_TIMEOUT_MS}`));
              }
            }, 1000);
          });
          doneMeta = await Promise.race([wsSendObserved, wsInactivityTimeoutPromise]);
        } else {
          doneMeta = await wsSendObserved;
        }
        if (doneMeta && typeof doneMeta === "object") doneMeta.__transport = "ws";
        if (doneMeta && typeof doneMeta === "object") {
          const startToRunning =
            turnAcceptedAtMs && phaseRunningAtMs ? Math.max(0, Number(phaseRunningAtMs) - Number(turnAcceptedAtMs)) : null;
          const runningToFirst =
            phaseRunningAtMs && firstDeltaAtMs ? Math.max(0, Number(firstDeltaAtMs) - Number(phaseRunningAtMs)) : null;
          doneMeta.__phase_start_to_running_ms = Number.isFinite(Number(startToRunning)) ? Number(startToRunning) : null;
          doneMeta.__phase_running_to_first_ms = Number.isFinite(Number(runningToFirst)) ? Number(runningToFirst) : null;
        }
      } finally {
        transport.close();
        if (currentWsTransport === transport) currentWsTransport = null;
      }
      setTimeout(() => {
        reloadSessionsOnly().catch(() => {});
      }, 250);
      return doneMeta;
    } catch (e) {
      if (isAbortError(e)) return doneMeta;
      const emsg = String(e && e.message ? e.message : e || "").toLowerCase();
      const wsLikeFailure =
        emsg.includes("ws_") ||
        emsg.includes("websocket") ||
        emsg.includes("receive_failed") ||
        emsg.includes("closed") ||
        emsg.includes("timeout");
      if (wsLikeFailure) {
        // Only short-circuit when a terminal event was already received.
        // If we only saw partial deltas and WS drops, we must attempt recovery.
        if (sawWsTerminalEvent) {
          // If the stream bubble was already finalized with usable content, do NOT
          // repaint messagesEl (prevents end-of-turn flash). Only reload when we
          // have nothing usable and need to recover from persisted history.
          if (!turnFinalized || !turnStreamedEnough) {
            setTimeout(() => {
              loadMessagesForActive().catch(() => {});
            }, 350);
          }
          return doneMeta;
        }
        // WS timeout may happen while backend still computes and persists final reply.
        // Try recovering from persisted history before surfacing a hard error.
        if (emsg.includes("ws_send_timeout")) {
          try {
            for (let i = 0; i < 12; i++) {
              if (await _recoverLatestAssistantFromHistory()) {
                statusBar.textContent =
                  t("chat.timeoutRecovered");
                return doneMeta || { __transport: "ws_timeout_history_recovered" };
              }
              await _sleep(600 + i * 400);
            }
          } catch (_) {
            // fall through to generic ws-like failure recovery
          }
        }
        // WS may time out/close while backend persists final message slightly later.
        // Poll history briefly before surfacing hard failure.
        try {
          for (let i = 0; i < 6; i++) {
            if (await _recoverLatestAssistantFromHistory()) {
              statusBar.textContent =
                t("chat.wsInterruptedRecovered");
              return doneMeta || { __transport: "ws_history_recovered" };
            }
            await _sleep(500 + i * 350);
          }
        } catch (_) {
          // fall through to original error
        }
      }
      throw e;
    } finally {
      if (typingRafId != null) {
        try {
          cancelAnimationFrame(typingRafId);
        } catch (_) {}
        typingRafId = null;
      }
      if (typingTimerId != null) {
        try {
          clearTimeout(typingTimerId);
        } catch (_) {}
        typingTimerId = null;
      }
      _stopDynamicStreamStatus();
      if (renderRafId != null) {
        try {
          cancelAnimationFrame(renderRafId);
        } catch (_) {}
        renderRafId = null;
        renderPending = false;
      }
      btnStop.disabled = true;
      btnSend.disabled = false;
      syncSendEnabled();
      composerShell.classList.remove("chat-composer-shell--busy");
      if (currentStreamAbortController === abortController) currentStreamAbortController = null;
    }
  };

  btnStop.addEventListener("click", async () => {
    if (currentStreamAbortController) currentStreamAbortController.abort();
    try {
      const sid = String(currentAbortMeta.sessionId || activeId || "");
      if (sid) {
        const tpt = currentWsTransport;
        if (tpt && typeof tpt.sendChatAbort === "function") {
          await tpt.sendChatAbort({ sessionId: sid, runId: currentAbortMeta.runId || "" });
        }
      }
    } catch (_) {
      // ignore abort rpc errors; local abort still stops UI
    }
    statusBar.textContent = "";
  });

  btnSend.addEventListener("click", async () => {
    if (btnSend.disabled) return;
    const textRaw = String(textarea.value || "").trim();
    const hasFiles = pendingFiles.length > 0;
    if (!textRaw && !hasFiles) return;
    if (!activeId) {
      try {
        statusBar.textContent = t("chat.loading");
        const resp = await apiPost("/admin/api/chat/sessions", {});
        adoptCreatedSession(resp);
        paintSessions();
        statusBar.textContent = "";
      } catch (e) {
        statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
        return;
      }
    }
    if (!activeId) return;
    const filesSnapshot = pendingFiles.slice();
    btnSend.disabled = true;
    statusBar.textContent = t("chat.sending");
    let attPayload = null;
    const userText =
      textRaw ||
      (hasFiles ? (t("chat.attachmentUploaded")) : "");
    /** 发送过程中用本地 blob 预览；先插入气泡再编码，避免大图 base64 阻塞主线程时长时间只有「准备附件」无预览 */
    const previewBlobUrls = [];
    try {
      textarea.value = "";
      const innerUser = el("div", { class: "chat-msg chat-msg--user" });
      innerUser.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(userText) }));
      if (filesSnapshot.length) {
        const wrap = el("div", { class: "chat-att-wrap" });
        for (const f of filesSnapshot) {
          const u = URL.createObjectURL(f);
          previewBlobUrls.push(u);
          wrap.appendChild(
            el("img", {
              class: "chat-att-img",
              src: u,
              alt: String(f.name || ""),
              title: String(f.name || ""),
            }),
          );
        }
        innerUser.appendChild(wrap);
      }
      const userWrap = wrapUserMessage(innerUser, new Date().toISOString());
      messagesEl.appendChild(userWrap);
      scrollMessagesToBottom(true);
      fitComposerTextarea();
      if (filesSnapshot.length) {
        await new Promise((resolve) => requestAnimationFrame(() => resolve()));
        statusBar.textContent = t("chat.encodingAttachments");
        attPayload = await Promise.all(filesSnapshot.map((f) => fileToPayloadEntry(f)));
        pendingFiles = [];
        syncPendingUi();
      }
      const turnId = `idem_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
      statusBar.textContent = t("chat.connecting");
      const doneMeta = await sendMessageStream(userText, attPayload, turnId);
      const transportTag = (doneMeta && doneMeta.__transport) || "";
      const mRaw = String((doneMeta && doneMeta.interaction_mode) || "").toLowerCase();
      const m = interactionModeLabel(mRaw);
      const s = specialistLabel(
        mRaw === "expert"
          ? (doneMeta && doneMeta.selected_specialist)
          : (doneMeta && (doneMeta.manager_selected_specialist || doneMeta.selected_specialist || doneMeta.requested_specialist)),
      );
      const baseText = t("chat.execApplied", { mode: m, specialist: s });
      const memoryModeNow = String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default").toLowerCase();
      const memoryText = ` · ${t("chat.memoryApplied", { mode: memoryModeShortLabel(memoryModeNow) })}`;
      const execModeFromServer = String((doneMeta && doneMeta.execution_mode) || "").trim().toLowerCase();
      const effectiveExecMode = execModeFromServer === EXECUTION_MODE_PLAN ? EXECUTION_MODE_PLAN : currentExecutionMode;
      const execText = ` · ${t("chat.execModeApplied", { mode: executionModeLabel(effectiveExecMode) })}`;
      const reason = reasonLabel(doneMeta && doneMeta.dispatch_reason);
      const dyn = doneMeta && doneMeta.dynamic_agent_used ? ` · dynamic=${String(doneMeta.dynamic_agent_name || "1")}` : "";
      const routeText = reason && reason !== "-" ? ` · ${reason}${dyn}` : dyn;
      const markerText =
        doneMeta && ((Number(doneMeta.relay_pointer_count || 0) || 0) > 0 || doneMeta.relay_envelope_present)
          ? ` · ${t("chat.marker.summary", {
              p: String(Number(doneMeta.relay_pointer_count || 0) || 0),
              e: doneMeta.relay_envelope_present ? "1" : "0",
              ep: String(Number(doneMeta.relay_envelope_pointer_count || 0) || 0),
            })} · ${t("chat.marker.ttl", {
              t: String(Number(doneMeta.relay_ttl_turn_count || 0) || 0),
              s: String(Number(doneMeta.relay_ttl_session_count || 0) || 0),
              k: String(Number(doneMeta.relay_ttl_keep_count || 0) || 0),
            })}`
          : "";
      const ttftObj = doneMeta && doneMeta.ttft && typeof doneMeta.ttft === "object" ? doneMeta.ttft : null;
      const localStartToRunningRaw = doneMeta && doneMeta.__phase_start_to_running_ms;
      const localRunningToFirstRaw = doneMeta && doneMeta.__phase_running_to_first_ms;
      const localStartToRunning =
        typeof localStartToRunningRaw === "number"
          ? localStartToRunningRaw
          : (() => {
              const n = Number(localStartToRunningRaw);
              return Number.isFinite(n) ? n : null;
            })();
      const localRunningToFirst =
        typeof localRunningToFirstRaw === "number"
          ? localRunningToFirstRaw
          : (() => {
              const n = Number(localRunningToFirstRaw);
              return Number.isFinite(n) ? n : null;
            })();
      const segA2G = ttftObj && ttftObj.accepted_to_gateway_ms != null ? Number(ttftObj.accepted_to_gateway_ms) : null;
      const segG2M =
        ttftObj && ttftObj.gateway_to_model_start_ms != null
          ? Number(ttftObj.gateway_to_model_start_ms)
          : (Number.isFinite(localStartToRunning) ? localStartToRunning : null);
      const segM2F =
        ttftObj && ttftObj.model_start_to_first_token_ms != null
          ? Number(ttftObj.model_start_to_first_token_ms)
          : (Number.isFinite(localRunningToFirst) ? localRunningToFirst : null);
      const ttftTotal =
        ttftObj && ttftObj.accepted_to_first_token_ms != null
          ? Number(ttftObj.accepted_to_first_token_ms)
          : (Number.isFinite(segG2M) && Number.isFinite(segM2F) ? Number(segG2M) + Number(segM2F) : null);
      const ttftText =
        Number.isFinite(ttftTotal) || Number.isFinite(segA2G) || Number.isFinite(segG2M) || Number.isFinite(segM2F)
          ? t("chat.stageSeg", {
              a2g: Number.isFinite(segA2G) ? `${segA2G}ms` : "-",
              g2m: Number.isFinite(segG2M) ? `${segG2M}ms` : "-",
              m2f: Number.isFinite(segM2F) ? `${segM2F}ms` : "-",
            }) + `${Number.isFinite(ttftTotal) ? ` · TTFT=${ttftTotal}ms` : ""}`
          : "";
      const phaseText =
        Number.isFinite(localStartToRunning)
          ? (() => {
              return Number.isFinite(localRunningToFirst)
                ? t("chat.stageLocalBoth", { start: localStartToRunning, first: localRunningToFirst })
                : t("chat.stageLocalStart", { start: localStartToRunning });
            })()
          : "";
      const stats = await fetchDynamicExpertStats();
      if (stats) {
        let topReason = "-";
        let topCount = -1;
        const pairs = [];
        for (const [k, v] of Object.entries(stats.reasons || {})) {
          const n = parseInt(String(v || "0"), 10) || 0;
          pairs.push([String(k || "-"), n]);
          if (n > topCount) {
            topCount = n;
            topReason = String(k || "-");
          }
        }
        pairs.sort((a, b) => b[1] - a[1]);
        state.statusReasonPairs = pairs.slice();
        const top5 = pairs
          .slice(0, 5)
          .map(([k, n]) => `${String((stats.reasonLabels && stats.reasonLabels[k]) || reasonLabel(k))}:${n}`)
          .join(", ");
        const ratePct = Math.round((Number(stats.rate || 0) * 1000)) / 10;
        const topReasonLabel = String((stats.reasonLabels && stats.reasonLabels[topReason]) || reasonLabel(topReason));
        const topReasonText = t("chat.dynamicStatsDetail", { rate: ratePct, reason: topReasonLabel });
        const topMixText = t("chat.dynamicTopReasons", { items: top5 || "-" });
        statusBar.textContent = `${baseText}${memoryText}${execText}${routeText}${markerText}${ttftText}${phaseText} · ${t("chat.dynamicStats", { dynamic: stats.dynamic, fallback: stats.fallback })} · ${topReasonText} · ${topMixText} · ${t("chat.dynamicAllReasons")}${transportTag ? ` · transport=${transportTag}` : ""}`;
      } else {
        state.statusReasonPairs = [];
      statusBar.textContent = `${baseText}${memoryText}${execText}${routeText}${markerText}${ttftText}${phaseText}${transportTag ? ` · transport=${transportTag}` : ""}`;
      }
    } catch (e) {
      statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
    } finally {
      previewBlobUrls.forEach((u) => {
        try {
          URL.revokeObjectURL(u);
        } catch (_) {}
      });
      btnSend.disabled = false;
    }
  });

  textarea.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      btnSend.click();
    }
  });

  try {
    await refreshSessions();
  } catch (e) {
    statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
    sessionsListEl.innerHTML = "";
    messagesEl.innerHTML = "";
  }
  composerShell.appendChild(pendingFilesEl);
  composerShell.appendChild(composerMetaBar);
  composerShell.appendChild(
    el("div", { class: "chat-composer-row" }, [
      attachBtn,
      textarea,
      el("div", { class: "chat-composer-actions" }, [btnStop, btnSend]),
    ]),
  );

  const navFooter = el("div", { class: "chat-nav__footer" }, [
    btnJobs,
    el("div", { id: "authUser", class: "chat-nav__user" }),
  ]);

  return el("div", { class: "chat-layout chat-app" }, [
    el("div", { class: "chat-nav" }, [
      el("div", { class: "chat-nav__top" }, [
        buildChatBrandLogoNode(),
      ]),
      el("div", { class: "chat-nav__toolbar" }, [btnNew]),
      el("div", { class: "chat-nav__scroll" }, [sessionsListEl, loadMoreWrap]),
      navFooter,
    ]),
    el("div", { class: "chat-main" }, [
      messagesEl,
      statusBar,
      el("div", { class: "chat-composer" }, [fileInput, composerShell]),
    ]),
  ]);
}

document.body.addEventListener("click", (e) => {
  const node = e.target;
  if (!node || !node.closest) return;
  const status = node.closest(".chat-status");
  if (!status) return;
  if (!state.statusReasonPairs.length) return;
  document.querySelectorAll(".chat-sess-menu-pop").forEach((n) => n.remove());
  const items = state.statusReasonPairs.map(([k, n]) => `${reasonLabel(k)}: ${n}`).join("\n");
  const pop = el("div", { class: "chat-sess-menu-pop u-pop-tip" }, [
    el("div", { class: "chat-sess-menu-item", text: t("chat.dynamicAllReasonsTitle") }),
    el("div", { class: "chat-sess-menu-item", text: items || "-" }),
  ]);
  const rect = status.getBoundingClientRect();
  pop.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - 440))}px`;
  pop.style.top = `${Math.max(8, rect.top - 180)}px`;
  document.body.appendChild(pop);
  const close = (ev) => {
    if (!pop.contains(ev.target)) {
      pop.remove();
      document.removeEventListener("click", close);
    }
  };
  setTimeout(() => document.addEventListener("click", close), 0);
});


export { renderChatUi };
