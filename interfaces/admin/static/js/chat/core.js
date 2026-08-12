import { state } from "./state.js";
import { t, applyI18nStatic, LANG_KEY, I18N } from "./i18n/index.js";

/* Standalone /chat page: same bearer + /admin/api/chat as admin SPA. */

const PAGE_SIZE = 35;
/** Initial / page size for session history (older messages load on scroll-up). */
const CHAT_MESSAGES_FETCH_LIMIT = 80;

/** Chat standalone: separate keys from /admin so two accounts can stay signed in on the same origin. */
const AUTH_TOKEN_KEY = "ops_chat_token";
const AUTH_SESSION_KEY = "ops_chat_session";
/** 与 URL 中 ?session_id= 联动：切换登录用户后丢弃旧 session，避免误开上一账号的链接会话 */
const CHAT_URL_SCOPE_KEY = "ops_chat_url_scope";
const CHAT_SPECIALIST_PREF_KEY = "ops_chat_specialist_pref";
const CHAT_INTERACTION_MODE_KEY = "ops_chat_interaction_mode";
const CHAT_MEMORY_MODE_KEY = "ops_chat_memory_mode";
const CHAT_EXECUTION_MODE_KEY = "ops_chat_execution_mode";
const CHAT_USER_MENU_MODE_KEY = "ops_chat_user_menu_mode";
const CHAT_REASONING_TOGGLE_KEY = "ops_chat_reasoning_toggle";
const EXECUTION_MODE_AGENT = "agent";
const EXECUTION_MODE_PLAN = "plan";
/** Default on: reasoning/tool fold matches streamed behavior; new browsers have no localStorage yet. */
const ADMIN_CHAT_SHOW_TOOL_OUTPUT_DEFAULT = true;
const REASONING_BLOCK_MAX_CHARS = 12000;
const CHAT_ENABLE_WIKI_EVENT_POLLER = false;

function _toolSummaryTitle(role) {
  const r = String(role || "").toLowerCase();
  if (r === "tool" || r === "function") return t("chat.toolResult");
  return t("chat.toolCall");
}

function _normalizeEventType(v) {
  return String(v || "").trim().toLowerCase();
}

function _isAssistantBodyEventType(eventType) {
  const et = _normalizeEventType(eventType);
  return !et || et === "assistant_text" || et === "assistant" || et === "scheduled_reminder";
}

function _parseEventPayload(raw) {
  let ep = raw;
  if (typeof ep === "string" && String(ep).trim()) {
    try {
      ep = JSON.parse(ep);
    } catch (_) {
      ep = null;
    }
  }
  return ep && typeof ep === "object" && !Array.isArray(ep) ? ep : null;
}

function _isScheduledProactiveMessage(m) {
  const eventType = _normalizeEventType(m && m.event_type);
  if (eventType === "scheduled_reminder") return true;
  const ep = _parseEventPayload(m && m.event_payload);
  if (ep && ep.scheduled_proactive) return true;
  const rc = String((ep && ep.reasoning_content) || "").trim();
  if (!rc) return false;
  if (!/定时主动提醒|定时任务模式|scheduled reminder|proactive reminder/i.test(rc)) return false;
  return eventType === "assistant_text" || eventType === "assistant" || !eventType;
}

function _messageTurnUuid(m) {
  return String((m && m.turn_uuid) || "").trim();
}

function _pushScheduledAssistantRow(rows, m, content, eventType) {
  const body = String(content || "").trim();
  const attsParsed = parseAttachments(m && m.attachments);
  if (!body && !attsParsed.length) return;
  const piece = {
    kind: "assistant_text",
    text: content,
    assistantEventType: eventType || "assistant_text",
  };
  if (attsParsed.length) piece.attachments = attsParsed;
  rows.push({
    role: "assistant",
    content: body,
    timestamp: (m && m.timestamp) != null ? m.timestamp : "",
    attachments: m && m.attachments ? m.attachments : null,
    _items: [piece],
    _message_ids: m && m.id != null ? [m.id] : [],
  });
}

function _collapsedBlockNode(title, text) {
  const raw = String(text || "");
  const clipped = raw.length > REASONING_BLOCK_MAX_CHARS ? raw.slice(0, REASONING_BLOCK_MAX_CHARS) : raw;
  const suffix =
    raw.length > REASONING_BLOCK_MAX_CHARS
      ? `\n\n[truncated ${raw.length - REASONING_BLOCK_MAX_CHARS} chars to keep UI responsive]`
      : "";
  const box = document.createElement("div");
  box.className = "chat-msg__reasoning-block";
  box.appendChild(el("div", { class: "chat-msg__reasoning-title", text: String(title || "") }));
  const pre = el("pre", { class: "chat-msg__reasoning-pre", text: (clipped + suffix) || "—" });
  box.appendChild(pre);
  if (raw.length > REASONING_BLOCK_MAX_CHARS) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn-sm";
    btn.style.marginTop = "6px";
    btn.textContent = t("chat.expandFull");
    btn.addEventListener("click", () => {
      btn.disabled = true;
      btn.textContent = t("chat.loadingDots");
      requestAnimationFrame(() => {
        pre.textContent = raw || "—";
        btn.remove();
      });
    });
    box.appendChild(btn);
  }
  return box;
}

function _appendCollapsedBundle(inner, items) {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return;
  const det = document.createElement("details");
  det.className = "chat-msg__reasoning";
  const sum = document.createElement("summary");
  sum.textContent = t("reasoning.summary");
  det.appendChild(sum);
  for (const it of list) {
    const title = String((it && it.title) || "");
    const text = String((it && it.text) || "");
    if (!text.trim()) continue;
    det.appendChild(_collapsedBlockNode(title || t("reasoning.summary"), text));
  }
  inner.appendChild(det);
}

function _appendAssistantTextSegments(inner, rawText, collapsedItems) {
  const sourceText = state.adminChatShowToolOutput
    ? decodeEscapedNewlines(rawText)
    : stripReasoningTagsFromText(decodeEscapedNewlines(rawText), { mode: "strict" });
  const segs = parseReasoningSegments(sourceText);
  const onlyText = segs.length === 1 && segs[0].type === "text";
  if (onlyText) {
    inner.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(segs[0].text) }));
    return;
  }
  for (const seg of segs) {
    if (seg.type === "text") {
      let body = String(seg.text || "");
      const prev = inner.lastElementChild;
      if (prev && prev.classList && prev.classList.contains("chat-msg__reasoning")) {
        body = body.replace(/^\s+/, "");
      }
      if (!body.trim()) continue;
      inner.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(body) }));
    } else {
      if (!state.adminChatShowToolOutput) continue;
      if (Array.isArray(collapsedItems)) {
        collapsedItems.push({ title: t("reasoning.summary"), text: seg.text || "—" });
      } else {
        _appendCollapsedBundle(inner, [{ title: t("reasoning.summary"), text: seg.text || "—" }]);
      }
    }
  }
}

function _normFoldDedupText(s) {
  return String(s || "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

/** True when ``processText`` is already covered by text already queued for the reasoning fold. */
function _foldProcessTextRedundant(processText, collapsedItems) {
  const p = _normFoldDedupText(processText);
  if (!p) return true;
  const hay = (Array.isArray(collapsedItems) ? collapsedItems : [])
    .map((x) => _normFoldDedupText((x && x.text) || ""))
    .join("\n\n");
  if (!hay) return false;
  if (hay.includes(p)) return true;
  return false;
}

/**
 * Prefer a single render of each attachment_id inside one aggregated bubble.
 * When both generate + save_deliverable_attachment persist the same id, keep the
 * deliverable row (or the first occurrence if none is marked deliverable).
 */
function _preferredAttachmentOwnerById(items) {
  const preferred = new Map();
  (Array.isArray(items) ? items : []).forEach((it, itemIdx) => {
    const list = parseAttachments(it && it.attachments);
    for (const att of list) {
      if (!att || typeof att !== "object") continue;
      const aid = String(att.attachment_id || att.attachmentId || "")
        .trim()
        .toLowerCase();
      if (!aid) continue;
      const prev = preferred.get(aid);
      if (prev === undefined) {
        preferred.set(aid, itemIdx);
        continue;
      }
      if (att.deliverable === true) {
        const prevAtts = parseAttachments((items[prev] && items[prev].attachments) || null);
        const prevAtt = prevAtts.find((a) => {
          const id = String((a && (a.attachment_id || a.attachmentId)) || "")
            .trim()
            .toLowerCase();
          return id === aid;
        });
        if (!(prevAtt && prevAtt.deliverable === true)) preferred.set(aid, itemIdx);
      }
    }
  });
  return preferred;
}

function _attachmentsForBubbleItem(raw, itemIdx, preferredById) {
  const list = parseAttachments(raw);
  if (!list.length) return null;
  const kept = [];
  for (const att of list) {
    if (!att || typeof att !== "object") continue;
    const aid = String(att.attachment_id || att.attachmentId || "")
      .trim()
      .toLowerCase();
    if (aid && preferredById instanceof Map) {
      const owner = preferredById.get(aid);
      if (owner != null && owner !== itemIdx) continue;
    }
    kept.push(att);
  }
  return kept.length ? kept : null;
}

async function _buildAggregatedAssistantBubble(tsIso, items) {
  const inner = el("div", { class: "chat-msg chat-msg--assistant chat-msg--rich" });
  const collapsedItems = [];
  const preferredAttOwner = _preferredAttachmentOwnerById(items);
  const itemList = Array.isArray(items) ? items : [];
  for (let itemIdx = 0; itemIdx < itemList.length; itemIdx++) {
    const it = itemList[itemIdx];
    const kind = String((it && it.kind) || "");
    const text = String((it && it.text) || "");
    const filteredAtts = _attachmentsForBubbleItem(it && it.attachments, itemIdx, preferredAttOwner);
    const hasInlineAtt = Array.isArray(filteredAtts) && filteredAtts.length > 0;
    if (
      !text.trim() &&
      !(kind === "tool_result" && hasInlineAtt) &&
      !(kind === "assistant_text" && hasInlineAtt)
    ) {
      continue;
    }
    if (kind === "assistant_text") {
      const aet = String((it && it.assistantEventType) || "assistant_text").toLowerCase();
      if (aet === "tool_call") {
        // Main-channel process notes belong in the reasoning fold only — never in visible body text.
        if (state.adminChatShowToolOutput) {
          const t0 = String(text || "").trim();
          if (t0 && !_foldProcessTextRedundant(t0, collapsedItems)) {
            collapsedItems.push({ title: t("reasoning.processNotes"), text: t0 });
          }
        }
        const attsAssistant = await renderAttachmentsEl(filteredAtts);
        if (attsAssistant) inner.appendChild(attsAssistant);
      } else {
        _appendAssistantTextSegments(inner, text, collapsedItems);
        const attsAssistant = await renderAttachmentsEl(filteredAtts);
        if (attsAssistant) inner.appendChild(attsAssistant);
      }
    } else if (kind === "reasoning") {
      if (state.adminChatShowToolOutput) collapsedItems.push({ title: t("reasoning.summary"), text });
    } else if (kind === "tool_call") {
      if (state.adminChatShowToolOutput) collapsedItems.push({ title: _toolSummaryTitle("tool_call"), text });
    } else if (kind === "tool_result") {
      if (state.adminChatShowToolOutput) collapsedItems.push({ title: _toolSummaryTitle("tool"), text });
      // 支持两类附件：base64（image/input_image）和引用型（image_ref）。
      // image_ref 需要异步拉取 blob，因此改为走 renderAttachmentsEl()。
      // Same attachment_id from generate + save_deliverable is shown once (prefer deliverable).
      const attsEl = await renderAttachmentsEl(filteredAtts);
      if (attsEl) inner.appendChild(attsEl);
    } else {
      inner.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(text) }));
    }
  }
  if (collapsedItems.length) {
    const det = document.createElement("details");
    det.className = "chat-msg__reasoning";
    const sum = document.createElement("summary");
    sum.textContent = t("reasoning.summary");
    det.appendChild(sum);
    for (const it of collapsedItems) {
      const title = String((it && it.title) || "");
      const text = String((it && it.text) || "");
      if (!text.trim()) continue;
      det.appendChild(_collapsedBlockNode(title || t("reasoning.summary"), text));
    }
    inner.insertBefore(det, inner.firstChild);
  }
  const hasVisible =
    !!inner.querySelector(".chat-msg__md, .chat-msg__reasoning, .chat-msg__wiki") ||
    !!inner.querySelector(".chat-att-wrap, img.chat-att-img, a.chat-att-ref__link, a.chat-att-ref__action, .chat-att-chip") ||
    String(inner.textContent || "").trim().length > 0;
  if (!hasVisible) {
    inner.appendChild(el("div", { class: "muted", text: t("chat.tools.hidden") }));
  }
  return wrapAssistantMessage(inner, tsIso);
}

function _buildRenderRows(msgs) {
  const src = Array.isArray(msgs) ? msgs : [];
  const ordered = src
    .map((m, idx) => ({ m, idx }))
    .sort((a, b) => {
      const ta = Date.parse(String((a.m && a.m.timestamp) || "")) || 0;
      const tb = Date.parse(String((b.m && b.m.timestamp) || "")) || 0;
      if (ta !== tb) return ta - tb;
      const ia = parseInt(String((a.m && a.m.id) || "0"), 10);
      const ib = parseInt(String((b.m && b.m.id) || "0"), 10);
      if (Number.isFinite(ia) && Number.isFinite(ib) && ia !== ib) return ia - ib;
      return a.idx - b.idx;
    })
    .map((x) => x.m);
  const rows = [];
  let agg = null;
  const flush = () => {
    if (!agg) return;
    if (!Array.isArray(agg._items) || !agg._items.length) {
      agg = null;
      return;
    }
    rows.push(agg);
    agg = null;
  };
  for (const m of ordered) {
    const role = String((m && m.role) || "").toLowerCase();
    const content = String((m && m.content) || "");
    const eventType = _normalizeEventType(m && m.event_type);
    if (role === "user") {
      flush();
      rows.push(m);
      continue;
    }
    if (role === "assistant" || role === "tool" || role === "function") {
      const turnUuid = _messageTurnUuid(m);
      if (agg && turnUuid && agg._turn_uuid && turnUuid !== agg._turn_uuid) {
        flush();
      }
      if (role === "assistant" && _isScheduledProactiveMessage(m)) {
        flush();
        _pushScheduledAssistantRow(rows, m, content, eventType);
        continue;
      }
      if (!agg) {
        agg = {
          role: "assistant",
          content: "",
          timestamp: (m && m.timestamp) != null ? m.timestamp : "",
          attachments: null,
          _items: [],
          _message_ids: [],
          _turn_uuid: turnUuid,
        };
      } else if (turnUuid && !agg._turn_uuid) {
        agg._turn_uuid = turnUuid;
      }
      if (m && m.id != null) agg._message_ids.push(m.id);
      if (role === "assistant") {
        // thinking_mode_enabled: reasoning lives in event_payload.reasoning_content (no separate reasoning rows).
        const ep = _parseEventPayload(m && m.event_payload);
        if (ep) {
          const rc = String(ep.reasoning_content || "").trim();
          if (rc) {
            agg._items.push({ kind: "reasoning", text: rc });
          }
        }
        if (eventType === "reasoning") {
          if (String(content || "").trim()) {
            agg._items.push({ kind: "reasoning", text: content });
          }
        } else if (eventType === "tool_call") {
          const hasText = !!String(content || "").trim();
          const attsParsed = parseAttachments(m && m.attachments);
          if (hasText || attsParsed.length) {
            const piece = { kind: "assistant_text", text: content, assistantEventType: "tool_call" };
            if (attsParsed.length) piece.attachments = attsParsed;
            agg._items.push(piece);
          }
        } else if (_isAssistantBodyEventType(eventType)) {
          const hasText = !!String(content || "").trim();
          const attsParsed = parseAttachments(m && m.attachments);
          if (hasText || attsParsed.length) {
            const piece = {
              kind: "assistant_text",
              text: content,
              assistantEventType: eventType || "assistant_text",
            };
            if (attsParsed.length) piece.attachments = attsParsed;
            agg._items.push(piece);
          }
        }
        const tc = m.tool_calls;
        if (tc != null && tc !== "") {
          let line = "";
          try {
            line = typeof tc === "string" ? tc : JSON.stringify(tc, null, 0);
          } catch (_) {
            line = String(tc);
          }
          if (line) agg._items.push({ kind: "tool_call", text: line });
        }
        if (m.attachments) agg.attachments = m.attachments;
      } else {
        const hasToolText = !!String(content || "").trim();
        const toolAtts = parseAttachments(m && m.attachments);
        if (hasToolText || toolAtts.length) {
          const piece = { kind: "tool_result", text: content };
          if (toolAtts.length) piece.attachments = toolAtts;
          else if (m.attachments) piece.attachments = m.attachments;
          agg._items.push(piece);
          if (m.attachments) agg.attachments = m.attachments;
        }
      }
      continue;
    }
    flush();
    rows.push(m);
  }
  flush();
  return rows;
}

/** True when persisted history does not show a completed assistant reply for the latest turn (e.g. ends with user only). */
function _needsWsTextFallbackFromRenderRows(renderRows) {
  const rows = Array.isArray(renderRows) ? renderRows : [];
  if (!rows.length) return true;
  const last = rows[rows.length - 1];
  const lr = String((last && last.role) || "").toLowerCase();
  if (lr === "user") return true;
  if (lr !== "assistant") return true;
  const items = last && Array.isArray(last._items) ? last._items : [];
  for (const it of items) {
    const k = String((it && it.kind) || "").toLowerCase();
    if (k === "assistant_text" && String((it && it.text) || "").trim()) return false;
    if (k === "reasoning" && String((it && it.text) || "").trim()) return false;
    if (k === "tool_result") {
      if (String((it && it.text) || "").trim()) return false;
      if (Array.isArray(it.attachments) && it.attachments.length) return false;
    }
  }
  if (String((last && last.content) || "").trim()) return false;
  return true;
}

function interactionModeLabel(mode) {
  const m = String(mode || "").toLowerCase();
  if (m === "expert") return t("chat.modeExpertShort");
  return t("chat.modeComprehensiveShort");
}

function specialistLabel(specialist) {
  const s = String(specialist || "").toLowerCase();
  // Legacy manager / manager_self / main aliases display as generalist.
  if (s === "manager" || s === "manager_self" || s === "main" || s === "comprehensive") {
    return t("chat.specialistGeneralistShort");
  }
  if (s === "ops") return t("chat.specialistOpsShort");
  if (s === "image") return t("chat.specialistImageShort");
  if (s === "video") return t("chat.specialistVideoShort");
  if (s === "memory") return t("chat.specialistMemoryShort");
  return t("chat.specialistGeneralistShort");
}
function memoryModeShortLabel(memoryMode) {
  const mm = String(memoryMode || "default").toLowerCase();
  if (mm === "store_only") return t("chat.memoryModeStoreOnlyShort");
  return t("chat.memoryModeDefaultShort");
}

function _ensureToastHost() {
  let host = document.querySelector(".chat-toast-host");
  if (host) return host;
  host = el("div", { class: "chat-toast-host" });
  document.body.appendChild(host);
  return host;
}

function showToast(text, { kind = "info", ttlMs = 4200 } = {}) {
  const host = _ensureToastHost();
  const node = el("div", {
    class: kind === "error" ? "chat-toast chat-toast--error" : "chat-toast",
    text: String(text || ""),
  });
  host.appendChild(node);
  const kill = () => {
    try {
      node.style.opacity = "0";
      node.style.transform = "translateY(6px)";
    } catch (_) {}
    setTimeout(() => {
      try {
        node.remove();
      } catch (_) {}
    }, 220);
  };
  setTimeout(kill, Math.max(1200, Math.min(Number(ttlMs || 4200), 20000)));
  return node;
}

let _jobsPanelPollTimer = null;
let _jobsBadgePollTimer = null;

function _jobStatusLabel(status) {
  const s = String(status || "").trim().toLowerCase();
  const key = `chat.jobsStatus.${s}`;
  const labeled = t(key);
  return labeled === key ? s || "-" : labeled;
}

function _fmtJobTs(ts) {
  const n = Number(ts || 0);
  if (!n) return "-";
  try {
    return new Date(n * 1000).toLocaleString(state.currentLang === "zh" ? "zh-CN" : "en-US");
  } catch (_) {
    return String(n);
  }
}

function updateJobsBadge(runningCount) {
  const n = Math.max(0, parseInt(String(runningCount || 0), 10) || 0);
  if (state.jobsBtnLabelEl) {
    state.jobsBtnLabelEl.textContent = t("chat.jobs");
  }
  if (!state.jobsBadgeEl) return;
  state.jobsBadgeEl.textContent = String(n);
  state.jobsBadgeEl.hidden = false;
  state.jobsBadgeEl.setAttribute("aria-label", t("chat.jobsRunning", { n }));
  if (n > 0) {
    state.jobsBadgeEl.classList.add("chat-jobs-badge--hot");
    state.jobsBadgeEl.classList.remove("chat-jobs-badge--idle");
  } else {
    state.jobsBadgeEl.classList.remove("chat-jobs-badge--hot");
    state.jobsBadgeEl.classList.add("chat-jobs-badge--idle");
  }
  const btn = state.jobsBadgeEl.closest && state.jobsBadgeEl.closest(".chat-nav__jobs");
  if (btn) {
    if (n > 0) btn.classList.add("chat-nav__jobs--active");
    else btn.classList.remove("chat-nav__jobs--active");
    btn.title = t("chat.jobsRunning", { n });
  }
}

async function refreshJobsBadge() {
  try {
    const r = await apiGet("/admin/api/chat/jobs?limit=50");
    updateJobsBadge(r && r.running_count);
  } catch (_) {}
}

function startJobsBadgePoller() {
  stopJobsBadgePoller();
  refreshJobsBadge();
  // Keep sidebar count fresh without opening the panel.
  _jobsBadgePollTimer = setInterval(refreshJobsBadge, 4000);
}

function stopJobsBadgePoller() {
  if (_jobsBadgePollTimer) {
    clearInterval(_jobsBadgePollTimer);
    _jobsBadgePollTimer = null;
  }
}

async function openBackgroundJobsPanel() {
  document.querySelectorAll(".chat-jobs-backdrop").forEach((n) => n.remove());
  if (_jobsPanelPollTimer) {
    clearInterval(_jobsPanelPollTimer);
    _jobsPanelPollTimer = null;
  }

  const backdrop = el("div", {
    class: "chat-confirm-backdrop chat-jobs-backdrop u-z-modal",
  });
  const card = el("div", {
    class: "chat-confirm-card chat-jobs-card u-jobs-card",
  });
  const title = el("div", { class: "card__title", text: t("chat.jobsTitle") });
  const closeBtn = el("button", { type: "button", class: "btn", text: t("chat.jobsClose") });
  const refreshBtn = el("button", { type: "button", class: "btn", text: t("chat.jobsRefresh") });
  const killAllBtn = el("button", {
    type: "button",
    class: "btn btn--danger",
    text: t("chat.jobsKillAll"),
  });
  const head = el("div", { class: "row u-row-between" }, [
    title,
    el("div", { class: "row u-gap-8" }, [refreshBtn, killAllBtn, closeBtn]),
  ]);
  const hint = el("div", { class: "muted u-hint", text: t("chat.jobsHint") });
  const summary = el("div", { class: "muted u-fs-12" });
  const list = el("div", {
    class: "chat-jobs-list u-jobs-list",
  });

  const close = () => {
    if (_jobsPanelPollTimer) {
      clearInterval(_jobsPanelPollTimer);
      _jobsPanelPollTimer = null;
    }
    try {
      backdrop.remove();
    } catch (_) {}
    refreshJobsBadge();
  };
  closeBtn.addEventListener("click", close);
  backdrop.addEventListener("click", (ev) => {
    if (ev.target === backdrop) close();
  });

  const paint = async () => {
    list.innerHTML = "";
    list.appendChild(el("div", { class: "muted", text: t("chat.loading") }));
    try {
      const r = await apiGet("/admin/api/chat/jobs?limit=50");
      const jobs = Array.isArray(r && r.jobs) ? r.jobs : [];
      const running = Number((r && r.running_count) || 0);
      updateJobsBadge(running);
      summary.textContent = t("chat.jobsRunning", { n: running }) + ` · total ${Number((r && r.total) || jobs.length)}`;
      list.innerHTML = "";
      if (!jobs.length) {
        list.appendChild(el("div", { class: "muted", text: t("chat.jobsEmpty") }));
        return;
      }
      for (const job of jobs) {
        const status = String(job.status || "");
        const runningJob = status === "running";
        const row = el("div", { class: `chat-jobs-row chat-jobs-row--${status || "unknown"}` });
        const top = el("div", { class: "chat-jobs-row__top" }, [
          el("span", { class: "chat-jobs-row__name", text: String(job.name || job.job_id || "-") }),
          el("span", { class: `chat-jobs-pill chat-jobs-pill--${status}`, text: _jobStatusLabel(status) }),
        ]);
        const meta = el(
          "div",
          { class: "chat-jobs-row__meta muted" },
          [
            el("div", { text: `id: ${job.job_id || "-"}` }),
            el("div", { text: `pid: ${job.pid != null ? job.pid : "-"} · timeout: ${job.timeout_s || "-"}s` }),
            el("div", { text: `created: ${_fmtJobTs(job.created_at)} · finished: ${_fmtJobTs(job.finished_at)}` }),
            el("div", {
              class: "chat-jobs-row__cmd",
              text: String(job.command || ""),
              title: String(job.command || ""),
            }),
          ],
        );
        const actions = el("div", { class: "chat-jobs-row__actions row u-gap-8" });
        if (runningJob) {
          const killBtn = el("button", {
            type: "button",
            class: "btn btn--danger",
            text: t("chat.jobsKill"),
            onclick: async () => {
              if (!window.confirm(t("chat.jobsKillConfirm"))) return;
              killBtn.disabled = true;
              try {
                await apiPost(`/admin/api/chat/jobs/${encodeURIComponent(job.job_id)}/cancel`, {});
                await paint();
              } catch (e) {
                showToast(`${t("chat.error")}: ${String(e)}`, { kind: "error" });
              } finally {
                killBtn.disabled = false;
              }
            },
          });
          actions.appendChild(killBtn);
        } else {
          const purgeBtn = el("button", {
            type: "button",
            class: "btn",
            text: t("chat.jobsPurge"),
            onclick: async () => {
              if (!window.confirm(t("chat.jobsPurgeConfirm"))) return;
              purgeBtn.disabled = true;
              try {
                await apiDelete(`/admin/api/chat/jobs/${encodeURIComponent(job.job_id)}`);
                await paint();
              } catch (e) {
                showToast(`${t("chat.error")}: ${String(e)}`, { kind: "error" });
              } finally {
                purgeBtn.disabled = false;
              }
            },
          });
          actions.appendChild(purgeBtn);
        }
        const detailBtn = el("button", {
          type: "button",
          class: "btn",
          text: t("chat.logs"),
          onclick: async () => {
            detailBtn.disabled = true;
            try {
              const d = await apiGet(`/admin/api/chat/jobs/${encodeURIComponent(job.job_id)}?log_tail_chars=6000`);
              const pre = el("pre", {
                class: "chat-jobs-log",
                text:
                  `status=${d.status} exit=${d.exit_code}\n\n--- stdout ---\n${d.stdout_tail || ""}\n\n--- stderr ---\n${d.stderr_tail || ""}`,
              });
              const existing = row.querySelector(".chat-jobs-log");
              if (existing) existing.remove();
              row.appendChild(pre);
            } catch (e) {
              showToast(`${t("chat.error")}: ${String(e)}`, { kind: "error" });
            } finally {
              detailBtn.disabled = false;
            }
          },
        });
        actions.appendChild(detailBtn);
        row.appendChild(top);
        row.appendChild(meta);
        row.appendChild(actions);
        list.appendChild(row);
      }
    } catch (e) {
      list.innerHTML = "";
      list.appendChild(el("div", { class: "muted", text: `${t("chat.error")}: ${String(e)}` }));
    }
  };

  refreshBtn.addEventListener("click", () => paint());
  killAllBtn.addEventListener("click", async () => {
    if (!window.confirm(t("chat.jobsKillAllConfirm"))) return;
    killAllBtn.disabled = true;
    try {
      await apiPost("/admin/api/chat/jobs/cancel-running", {});
      await paint();
    } catch (e) {
      showToast(`${t("chat.error")}: ${String(e)}`, { kind: "error" });
    } finally {
      killAllBtn.disabled = false;
    }
  });

  card.appendChild(head);
  card.appendChild(hint);
  card.appendChild(summary);
  card.appendChild(list);
  backdrop.appendChild(card);
  document.body.appendChild(backdrop);
  await paint();
  _jobsPanelPollTimer = setInterval(paint, 4000);
}

async function openWikiPreviewModal({ sessionId, path }) {
  const sid = String(sessionId || "");
  const p = String(path || "").replace(/\\/g, "/").replace(/^\//, "");
  if (!sid || !p) return;
  const backdrop = el("div", {
    class: "chat-confirm-backdrop u-z-modal",
  });
  const card = el("div", {
    class: "chat-confirm-card u-profile-card",
  });
  const title = el("div", { class: "card__title", text: t("chat.wikiPreviewTitle", { path: p }) });
  const closeBtn = el("button", { type: "button", class: "btn", text: t("chat.wikiPreviewClose") });
  const head = el("div", { class: "row u-row-between" }, [
    title,
    closeBtn,
  ]);
  const body = el("div", { class: "chat-msg__md", html: `<div class="muted">${escapeHtml(t("chat.loading"))}</div>` });
  const close = () => {
    try {
      backdrop.remove();
    } catch (_) {}
  };
  closeBtn.addEventListener("click", close);
  backdrop.addEventListener("click", (ev) => {
    if (ev.target === backdrop) close();
  });
  card.appendChild(head);
  card.appendChild(body);
  backdrop.appendChild(card);
  document.body.appendChild(backdrop);
  try {
    const resp = await apiGet(
      `/admin/api/chat/sessions/${encodeURIComponent(sid)}/wiki-file?path=${encodeURIComponent(p)}&max_chars=120000`,
    );
    body.innerHTML = renderMarkdownHtml(String((resp && resp.content) || ""));
  } catch (e) {
    body.innerHTML = `<div class="muted">${escapeHtml(`${t("chat.error")}: ${String(e)}`)}</div>`;
  }
}

function reasonLabel(reason) {
  const r = String(reason || "").trim();
  if (!r) return "-";
  const key = `chat.reason.${r}`;
  const localized = t(key);
  return localized === key ? r : localized;
}

async function fetchDynamicExpertStats() {
  try {
    const r = await apiGet("/admin/api/chat/admin/dynamic-expert-stats?limit=200");
    if (!r || !r.ok) return null;
    return {
      dynamic: parseInt(String(r.dynamic_used_count || "0"), 10) || 0,
      fallback: parseInt(String(r.fallback_generalist_count || "0"), 10) || 0,
      rate: Number(r.dynamic_used_rate || 0),
      reasons: r.dispatch_reasons && typeof r.dispatch_reasons === "object" ? r.dispatch_reasons : {},
      reasonLabels:
        r.dispatch_reason_labels && typeof r.dispatch_reason_labels === "object" ? r.dispatch_reason_labels : {},
    };
  } catch (_) {
    return null;
  }
}

async function getDispatchReasonLabelsConfig() {
  try {
    const r = await apiGet("/admin/api/chat/settings/dispatch-reason-labels");
    if (!r || !r.ok) return { overrides: {}, effective: {} };
    return {
      overrides: r.overrides && typeof r.overrides === "object" ? r.overrides : {},
      effective: r.effective && typeof r.effective === "object" ? r.effective : {},
    };
  } catch (_) {
    return { overrides: {}, effective: {} };
  }
}

async function setDispatchReasonLabelsConfig(overridesOrNull) {
  return await apiPost("/admin/api/chat/settings/dispatch-reason-labels", {
    overrides: overridesOrNull,
  });
}

async function openDispatchLabelsEditor(statusEl) {
  const cfg = await getDispatchReasonLabelsConfig();
  const initText = Object.keys(cfg.overrides || {}).length
    ? JSON.stringify(cfg.overrides, null, 2)
    : "";
  const backdrop = el("div", {
    class: "chat-confirm-backdrop u-z-modal-top",
  });
  const card = el("div", {
    class: "card u-json-card",
  });
  const title = el("div", { class: "card__title", text: t("chat.dispatchLabelsTitle") });
  const tip = el("div", { class: "muted", text: t("chat.dispatchLabelsPrompt") });
  const err = el("div", { class: "muted u-text-danger" });
  const ta = el("textarea", {
    class: "input u-mono-area",
  });
  ta.value = initText;
  const previewTitle = el("div", { class: "muted", text: t("chat.dispatchLabelsEffectivePreview") });
  const diffOnlyWrap = el("label", { class: "muted u-check-row" });
  const diffOnlyCb = el("input", { type: "checkbox" });
  diffOnlyWrap.appendChild(diffOnlyCb);
  diffOnlyWrap.appendChild(el("span", { text: t("chat.dispatchLabelsDiffOnly") }));
  const preview = el("textarea", {
    class: "input u-mono-area-sm",
    readonly: "readonly",
  });
  const btnSave = el("button", { type: "button", class: "btn btn--primary", text: t("chat.dispatchLabelsSave") });
  const btnClear = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsClear") });
  const btnDefaults = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsRestoreDefaults") });
  const btnExport = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsExport") });
  const btnImport = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsImport") });
  const btnCancel = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsCancel") });
  const fileInput = el("input", { class: "u-hidden", type: "file", accept: "application/json,.json" });
  const close = () => backdrop.remove();
  const saveCurrent = async () => {
    const raw = String(ta.value || "").trim();
    try {
      if (!raw) {
        await setDispatchReasonLabelsConfig(null);
      } else {
        const obj = JSON.parse(raw);
        await setDispatchReasonLabelsConfig(obj);
      }
      if (statusEl) statusEl.textContent = t("chat.dispatchLabelsSaved");
      close();
    } catch (e) {
      const msg = String(e || "");
      err.textContent = msg.toLowerCase().includes("json")
        ? t("chat.dispatchLabelsInvalidJson")
        : `${t("chat.error")}: ${msg}`;
    }
  };
  const hasUnsavedChanges = () => String(ta.value || "").trim() !== initText.trim();
  const closeWithGuard = () => {
    if (hasUnsavedChanges()) {
      if (!window.confirm(t("chat.dispatchLabelsUnsavedConfirm"))) return;
    }
    close();
  };
  const refreshPreview = () => {
    const raw = String(ta.value || "").trim();
    if (!raw) {
      preview.value = JSON.stringify(cfg.effective || {}, null, 2);
      return;
    }
    try {
      const userObj = JSON.parse(raw);
      const base = cfg.effective && typeof cfg.effective === "object" ? cfg.effective : {};
      const merged = { ...base };
      const changed = {};
      if (userObj && typeof userObj === "object") {
        for (const [k, v] of Object.entries(userObj)) {
          if (!v || typeof v !== "object") continue;
          const next = {
            zh: String((v && v.zh) || (merged[String(k)] && merged[String(k)].zh) || ""),
            en: String((v && v.en) || (merged[String(k)] && merged[String(k)].en) || ""),
          };
          const prev = merged[String(k)] && typeof merged[String(k)] === "object" ? merged[String(k)] : {};
          merged[String(k)] = next;
          if (String(next.zh || "") !== String(prev.zh || "") || String(next.en || "") !== String(prev.en || "")) {
            changed[String(k)] = next;
          }
        }
      }
      preview.value = JSON.stringify(diffOnlyCb.checked ? changed : merged, null, 2);
    } catch (_) {
      preview.value = t("chat.dispatchLabelsInvalidJson");
    }
  };
  ta.addEventListener("input", refreshPreview);
  diffOnlyCb.addEventListener("change", refreshPreview);
  refreshPreview();

  btnCancel.addEventListener("click", closeWithGuard);
  btnExport.addEventListener("click", () => {
    const raw = String(preview.value || "").trim();
    const content = raw || "{}";
    const blob = new Blob([content], { type: "application/json;charset=utf-8" });
    const a = document.createElement("a");
    const now = new Date();
    const ts = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}-${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}${String(now.getSeconds()).padStart(2, "0")}`;
    a.href = URL.createObjectURL(blob);
    a.download = `dispatch-reason-labels-effective-${ts}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });
  btnImport.addEventListener("click", () => fileInput.click());
  btnDefaults.addEventListener("click", () => {
    ta.value = JSON.stringify(cfg.effective || {}, null, 2);
    err.textContent = "";
    refreshPreview();
  });
  fileInput.addEventListener("change", async () => {
    const f = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!f) return;
    try {
      const txt = await f.text();
      const obj = JSON.parse(String(txt || ""));
      ta.value = JSON.stringify(obj, null, 2);
      err.textContent = "";
      refreshPreview();
    } catch (_) {
      err.textContent = t("chat.dispatchLabelsInvalidJson");
    }
  });
  btnClear.addEventListener("click", async () => {
    try {
      await setDispatchReasonLabelsConfig(null);
      if (statusEl) statusEl.textContent = t("chat.dispatchLabelsSaved");
      close();
    } catch (e) {
      err.textContent = `${t("chat.error")}: ${String(e)}`;
    }
  });
  btnSave.addEventListener("click", saveCurrent);
  ta.addEventListener("keydown", (ev) => {
    const isSave = (ev.ctrlKey || ev.metaKey) && String(ev.key || "").toLowerCase() === "s";
    if (!isSave) return;
    ev.preventDefault();
    saveCurrent();
  });

  card.appendChild(title);
  card.appendChild(tip);
  card.appendChild(el("div", { class: "u-h-8" }));
  card.appendChild(ta);
  card.appendChild(el("div", { class: "u-h-8" }));
  card.appendChild(previewTitle);
  card.appendChild(diffOnlyWrap);
  card.appendChild(preview);
  card.appendChild(el("div", { class: "u-h-8" }));
  card.appendChild(err);
  card.appendChild(
    el("div", { class: "row u-row-end-sm" }, [
      btnDefaults,
      btnImport,
      btnExport,
      btnClear,
      btnCancel,
      btnSave,
    ]),
  );
  backdrop.appendChild(card);
  backdrop.appendChild(fileInput);
  backdrop.addEventListener("click", (ev) => {
    if (ev.target === backdrop) closeWithGuard();
  });
  document.body.appendChild(backdrop);
}

function getSessionIdFromUrl() {
  return String(new URLSearchParams(location.search).get("session_id") || "").trim();
}

function forceReloginRequested() {
  return String(new URLSearchParams(location.search).get("force_relogin") || "").trim() === "1";
}

function clearAuthAndReloginFlagFromUrl() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_SESSION_KEY);
  state.authSession = null;
  const u = new URL(window.location.href);
  u.searchParams.delete("force_relogin");
  history.replaceState(null, "", `${u.pathname}${u.search}${u.hash}`);
}

function replaceSessionUrl(sessionId) {
  const path = "/chat";
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  history.replaceState(null, "", path + q);
}

function withTimeout(promise, ms, label) {
  let timer = null;
  const timeoutMs = Math.max(200, Number(ms) || 0);
  return Promise.race([
    Promise.resolve(promise),
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(label || `timeout:${timeoutMs}`)), timeoutMs);
    }),
  ]).finally(() => {
    if (timer) clearTimeout(timer);
  });
}

async function apiGet(path) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  const headers = { accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { headers });
  if (res.status === 401) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    state.authSession = null;
    setTimeout(() => boot().catch(() => {}), 0);
    return await new Promise(() => {});
  }
  if (!res.ok) throw new Error(`GET ${path} ${res.status}`);
  return await res.json();
}

async function apiPost(path, body) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  const headers = { "content-type": "application/json", accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, {
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
    const u = String(path || "");
    if (u.includes("/admin/api/auth/login") || u.includes("/admin/api/auth/bootstrap")) {
      return data && typeof data === "object" ? data : { ok: false, error: "unauthorized" };
    }
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    state.authSession = null;
    setTimeout(() => boot().catch(() => {}), 0);
    return await new Promise(() => {});
  }
  if (!res.ok) throw new Error(`POST ${path} ${res.status}`);
  return data ?? {};
}

async function apiPatch(path, body) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  const headers = { "content-type": "application/json", accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, {
    method: "PATCH",
    headers,
    body: JSON.stringify(body ?? {}),
  });
  if (res.status === 401) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    state.authSession = null;
    setTimeout(() => boot().catch(() => {}), 0);
    return await new Promise(() => {});
  }
  if (!res.ok) throw new Error(`PATCH ${path} ${res.status}`);
  return await res.json();
}

async function apiDelete(path) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  const headers = { accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { method: "DELETE", headers });
  if (res.status === 401) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    state.authSession = null;
    setTimeout(() => boot().catch(() => {}), 0);
    return await new Promise(() => {});
  }
  if (!res.ok) throw new Error(`DELETE ${path} ${res.status}`);
  return await res.json();
}

function el(tag, attrs = {}, children = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k === "html") e.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children) e.appendChild(c);
  return e;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Pretty-print channel session titles like `whatsapp|AI nms · Oliver · wa-default+86…@s.whatsapp.net`. */
function formatChatSessionTitle(raw, peerNameHint) {
  const full = String(raw || "").trim();
  const badgeMap = {
    whatsapp: "WA",
    wechat: "WX",
    weixin: "WX",
    wecom: "WC",
    telegram: "TG",
    discord: "DC",
    slack: "SL",
    local: "Local",
  };
  if (!full) {
    return { channel: "local", badge: badgeMap.local, label: "—", sublabel: "", full: "" };
  }
  const m = full.match(/^(whatsapp|wechat|weixin|wecom|telegram|discord|slack)\|(.+)$/i);
  if (!m) {
    return { channel: "local", badge: badgeMap.local, label: full, sublabel: "", full };
  }
  const channel = String(m[1] || "").toLowerCase();
  const rest = String(m[2] || "").trim();
  const segments = rest
    .split(/\s*·\s*/)
    .map((s) => String(s || "").trim())
    .filter(Boolean);

  const isTech = (s) => /[+]/.test(s) || /@/.test(s) || /^wa-default/i.test(s);
  let techIdx = -1;
  for (let i = 0; i < segments.length; i += 1) {
    if (isTech(segments[i])) techIdx = i;
  }
  let labels = [];
  let tech = rest;
  if (techIdx >= 0) {
    labels = segments.slice(0, techIdx);
    tech = segments.slice(techIdx).join(" · ");
  } else if (segments.length > 1) {
    labels = segments.slice(0, -1);
    tech = segments[segments.length - 1] || "";
  }

  // Legacy titles buried group name after the JID: account+jid@domain+GroupName
  let techBody = String(tech || "").replace(/^wa-default\+/i, "");
  const plusParts = techBody.split("+").map((s) => String(s || "").trim()).filter(Boolean);
  const idParts = [];
  const legacyNames = [];
  for (const p of plusParts) {
    if (p.includes("@") || /^[0-9]{8,}$/.test(p) || /^[0-9a-f]{16,}$/i.test(p)) idParts.push(p);
    else legacyNames.push(p);
  }
  for (let i = legacyNames.length - 1; i >= 0; i -= 1) {
    const n = legacyNames[i];
    if (n && !labels.includes(n)) labels.unshift(n); // group name first
  }
  let idRaw = idParts.join("+") || (legacyNames.length ? "" : techBody);
  let idShort = idRaw
    .replace(/@s\.whatsapp\.net$/i, "")
    .replace(/@g\.us$/i, "")
    .replace(/@lid$/i, "")
    .replace(/@im\.bot[^\s]*/i, "")
    .replace(/@[^\s]+$/i, "");
  if (/^[0-9a-f]{20,}$/i.test(idShort)) idShort = `${idShort.slice(0, 8)}…`;
  else if (idShort.length > 18) idShort = `${idShort.slice(0, 16)}…`;

  const hint = String(peerNameHint || "").trim();
  if (hint && !labels.some((l) => l.toLowerCase() === hint.toLowerCase())) {
    // Prefer keeping server-provided group/nick labels; append contact hint when useful.
    if (!labels.length) labels.push(hint);
    else if (labels.length === 1 && labels[0] !== hint) labels.push(hint);
  }

  const badge = badgeMap[channel] || channel.slice(0, 2).toUpperCase();
  let label = "";
  if (labels.length) {
    label = labels.join(" · ");
    // DM / unknown: single nick still benefits from a short id.
    if (labels.length === 1 && idShort && labels[0] === hint) {
      label = `${labels[0]} · ${idShort}`;
    }
  } else {
    label = idShort || full;
  }
  return {
    channel,
    badge,
    label,
    sublabel: "",
    full,
    idKey: idRaw || techBody,
  };
}

function _peerNameLookupKeys(title, pretty) {
  const keys = [];
  const push = (v) => {
    const s = String(v || "").trim().toLowerCase();
    if (s) keys.push(s);
  };
  push(pretty && pretty.idKey);
  const raw = String(title || "");
  const m = raw.match(/^(whatsapp|wechat|weixin|wecom)\|(.+)$/i);
  if (m) {
    let body = String(m[2] || "");
    const segs = body.split(/\s*·\s*/).map((s) => String(s || "").trim()).filter(Boolean);
    let tech = body;
    for (let i = segs.length - 1; i >= 0; i -= 1) {
      if (/[+]/.test(segs[i]) || /@/.test(segs[i]) || /^wa-default/i.test(segs[i])) {
        tech = segs[i];
        break;
      }
    }
    push(tech);
    push(tech.replace(/^wa-default\+/i, ""));
    const noAt = tech.replace(/@.*$/, "");
    push(noAt);
    push(noAt.replace(/^wa-default\+/i, ""));
    // Drop trailing +GroupName legacy suffix for contact id matching.
    const core = noAt.replace(/^wa-default\+/i, "").split("+")[0] || "";
    push(core);
    push(core.replace(/\D/g, ""));
  }
  return keys;
}

let _channelPeerNameMap = new Map();

function lookupChannelPeerName(title, pretty) {
  for (const k of _peerNameLookupKeys(title, pretty)) {
    const hit = _channelPeerNameMap.get(k);
    if (hit) return hit;
  }
  return "";
}

async function refreshChannelPeerNameMap() {
  const next = new Map();
  try {
    const r = await apiGet("/admin/api/whatsapp/access");
    const contacts = Array.isArray(r && r.contacts) ? r.contacts : [];
    for (const c of contacts) {
      const name = String((c && c.push_name) || "").trim();
      if (!name) continue;
      const eid = String((c && c.external_user_id) || "").trim();
      const phone = String((c && c.phone) || "").trim();
      for (const raw of [eid, phone, eid.replace(/@.*$/, ""), phone.replace(/\D/g, "")]) {
        const k = String(raw || "").trim().toLowerCase();
        if (k) next.set(k, name);
      }
    }
  } catch (_) {}
  _channelPeerNameMap = next;
}

let _chatLightboxKeyHandler = null;
let _chatLightboxPrevOverflow = "";

function closeChatImageLightbox() {
  if (_chatLightboxKeyHandler) {
    document.removeEventListener("keydown", _chatLightboxKeyHandler);
    _chatLightboxKeyHandler = null;
  }
  document.querySelector(".chat-img-lightbox")?.remove();
  document.body.style.overflow = _chatLightboxPrevOverflow || "";
}

function dismissChatMenus() {
  document.querySelectorAll(".chat-sess-menu-pop, .chat-menu-scrim").forEach((n) => {
    try {
      n.remove();
    } catch (_) {}
  });
}

function isChatStreaming() {
  return !!document.querySelector(".chat-composer-shell--busy");
}

/** Remove full-screen layers on ``document.body`` that survive ``#app`` remounts (boot/lang/popstate). */
function clearChatPageBlockers() {
  closeChatImageLightbox();
  dismissChatMenus();
  document.body.style.overflow = "";
  document.querySelectorAll(".chat-confirm-backdrop").forEach((n) => {
    try {
      n.remove();
    } catch (_) {}
  });
}

function attachChatMenuDismiss(menu) {
  const scrim = el("div", {
    class: "chat-menu-scrim u-overlay-scrim",
  });
  const closeAll = () => {
    dismissChatMenus();
    document.removeEventListener("click", onDocClick, true);
    document.removeEventListener("keydown", onKey, true);
  };
  const onDocClick = (e) => {
    if (menu.contains(e.target)) return;
    closeAll();
  };
  const onKey = (e) => {
    if (e.key === "Escape") closeAll();
  };
  scrim.addEventListener("click", closeAll);
  document.body.appendChild(scrim);
  document.body.appendChild(menu);
  setTimeout(() => {
    document.addEventListener("click", onDocClick, true);
    document.addEventListener("keydown", onKey, true);
  }, 0);
  return closeAll;
}

function openChatImageLightbox(src, alt) {
  if (!src || !String(src).trim()) return;
  closeChatImageLightbox();
  _chatLightboxPrevOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  _chatLightboxKeyHandler = (ev) => {
    if (ev.key === "Escape") closeChatImageLightbox();
  };
  document.addEventListener("keydown", _chatLightboxKeyHandler);

  const backdrop = el("div", {
    class: "chat-img-lightbox",
    role: "dialog",
    "aria-modal": "true",
    "aria-label": t("chat.imageViewerHint"),
  });
  const inner = el("div", { class: "chat-img-lightbox__inner" });
  let scale = 1.0;
  const clamp = (v) => Math.max(0.2, Math.min(5.0, Number(v || 1)));
  const applyScale = () => {
    scale = clamp(scale);
    viewport.style.transform = `scale(${scale})`;
    zoomText.textContent = `${Math.round(scale * 100)}%`;
  };
  const fileStem = (() => {
    const raw = String(alt || "").trim() || "image";
    const safe = raw.replace(/[\\/:*?"<>|]+/g, "_").replace(/\s+/g, "_").slice(0, 64);
    return safe || "image";
  })();
  const ext = (() => {
    const s = String(src || "");
    if (/^data:image\/png/i.test(s)) return ".png";
    if (/^data:image\/webp/i.test(s)) return ".webp";
    if (/^data:image\/gif/i.test(s)) return ".gif";
    if (/^data:image\/bmp/i.test(s)) return ".bmp";
    if (/^data:image\/jpeg/i.test(s) || /^data:image\/jpg/i.test(s)) return ".jpg";
    return ".png";
  })();
  const toolbar = el("div", { class: "chat-mermaid-lightbox__toolbar" });
  const btnMinus = el("button", {
    type: "button",
    class: "chat-mermaid-lightbox__btn",
    text: "−",
    title: t("chat.zoomOut"),
    onclick: (e) => {
      e.stopPropagation();
      scale = clamp(scale - 0.1);
      applyScale();
    },
  });
  const btnReset = el("button", {
    type: "button",
    class: "chat-mermaid-lightbox__btn",
    text: "100%",
    title: t("chat.zoomReset"),
    onclick: (e) => {
      e.stopPropagation();
      scale = 1.0;
      applyScale();
      wrap.scrollLeft = 0;
      wrap.scrollTop = 0;
    },
  });
  const btnPlus = el("button", {
    type: "button",
    class: "chat-mermaid-lightbox__btn",
    text: "+",
    title: t("chat.zoomIn"),
    onclick: (e) => {
      e.stopPropagation();
      scale = clamp(scale + 0.1);
      applyScale();
    },
  });
  const zoomText = el("span", { class: "chat-mermaid-lightbox__zoom", text: "100%" });
  const saveBtn = el("a", {
    class: "chat-mermaid-lightbox__btn chat-img-lightbox__btn--icon",
    href: String(src),
    download: `${fileStem}${ext}`,
    text: "⤓",
    title: t("chat.imageViewerDownload"),
    "aria-label": t("chat.imageViewerDownload"),
    onclick: (e) => e.stopPropagation(),
  });
  const wrap = el("div", { class: "chat-img-lightbox__viewportWrap" });
  const viewport = el("div", { class: "chat-img-lightbox__viewport" });
  const big = el("img", {
    class: "chat-img-lightbox__img",
    src: String(src),
    alt: alt || "",
    decoding: "async",
  });
  const closeBtn = el("button", {
    type: "button",
    class: "chat-img-lightbox__close",
    text: "×",
    "aria-label": t("chat.imageViewerClose"),
    onclick: (e) => {
      e.stopPropagation();
      closeChatImageLightbox();
    },
  });
  // Keep native image context menu so users can right-click save.
  big.addEventListener("contextmenu", (e) => {
    e.stopPropagation();
  });
  toolbar.appendChild(btnMinus);
  toolbar.appendChild(btnReset);
  toolbar.appendChild(btnPlus);
  toolbar.appendChild(zoomText);
  toolbar.appendChild(saveBtn);
  viewport.appendChild(big);
  wrap.appendChild(viewport);
  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragScrollLeft = 0;
  let dragScrollTop = 0;
  const onDragStart = (e) => {
    if (e && e.target && e.target.closest && e.target.closest(".chat-mermaid-lightbox__toolbar")) return;
    dragging = true;
    wrap.classList.add("chat-img-lightbox__viewportWrap--dragging");
    dragStartX = Number(e.clientX || 0);
    dragStartY = Number(e.clientY || 0);
    dragScrollLeft = wrap.scrollLeft;
    dragScrollTop = wrap.scrollTop;
  };
  const onDragMove = (e) => {
    if (!dragging) return;
    const x = Number(e.clientX || 0);
    const y = Number(e.clientY || 0);
    wrap.scrollLeft = dragScrollLeft - (x - dragStartX);
    wrap.scrollTop = dragScrollTop - (y - dragStartY);
  };
  const onDragEnd = () => {
    dragging = false;
    wrap.classList.remove("chat-img-lightbox__viewportWrap--dragging");
  };
  wrap.addEventListener("mousedown", (e) => onDragStart(e));
  window.addEventListener("mousemove", (e) => onDragMove(e));
  window.addEventListener("mouseup", () => onDragEnd());
  wrap.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const dy = Number(e.deltaY || 0);
      const step = dy > 0 ? -0.08 : 0.08;
      scale = clamp(scale + step);
      applyScale();
    },
    { passive: false },
  );
  inner.appendChild(toolbar);
  inner.appendChild(closeBtn);
  inner.appendChild(wrap);
  backdrop.appendChild(inner);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeChatImageLightbox();
  });
  document.body.appendChild(backdrop);
  applyScale();
}

function openChatMermaidLightbox(svg) {
  const raw = String(svg || "").trim();
  if (!raw) return;
  closeChatImageLightbox();
  _chatLightboxPrevOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  _chatLightboxKeyHandler = (ev) => {
    if (ev.key === "Escape") closeChatImageLightbox();
  };
  document.addEventListener("keydown", _chatLightboxKeyHandler);

  const backdrop = el("div", {
    class: "chat-img-lightbox",
    role: "dialog",
    "aria-modal": "true",
    "aria-label": "Mermaid diagram viewer",
  });
  const inner = el("div", { class: "chat-img-lightbox__inner" });
  let scale = 1.0;
  const clamp = (v) => Math.max(0.2, Math.min(3.0, Number(v || 1)));
  const applyScale = () => {
    scale = clamp(scale);
    viewport.style.transform = `scale(${scale})`;
    zoomText.textContent = `${Math.round(scale * 100)}%`;
  };
  const closeBtn = el("button", {
    type: "button",
    class: "chat-img-lightbox__close",
    text: "×",
    "aria-label": t("chat.imageViewerClose"),
    onclick: (e) => {
      e.stopPropagation();
      closeChatImageLightbox();
    },
  });
  const toolbar = el("div", { class: "chat-mermaid-lightbox__toolbar" });
  const btnMinus = el("button", {
    type: "button",
    class: "chat-mermaid-lightbox__btn",
    text: "−",
    onclick: (e) => {
      e.stopPropagation();
      scale = clamp(scale - 0.1);
      applyScale();
    },
  });
  const btnPlus = el("button", {
    type: "button",
    class: "chat-mermaid-lightbox__btn",
    text: "+",
    onclick: (e) => {
      e.stopPropagation();
      scale = clamp(scale + 0.1);
      applyScale();
    },
  });
  const btnReset = el("button", {
    type: "button",
    class: "chat-mermaid-lightbox__btn",
    text: "100%",
    onclick: (e) => {
      e.stopPropagation();
      scale = 1.0;
      applyScale();
    },
  });
  const zoomText = el("span", { class: "chat-mermaid-lightbox__zoom", text: "100%" });
  toolbar.appendChild(btnMinus);
  toolbar.appendChild(btnReset);
  toolbar.appendChild(btnPlus);
  toolbar.appendChild(zoomText);

  const wrap = el("div", { class: "chat-mermaid-lightbox__svg" });
  const viewport = el("div", { class: "chat-mermaid-lightbox__viewport" });
  viewport.innerHTML = raw;
  wrap.appendChild(viewport);
  // Drag-to-pan (scroll) inside the zoomable viewport.
  let dragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragScrollLeft = 0;
  let dragScrollTop = 0;
  const onDragStart = (e) => {
    // Ignore drags started on toolbar/buttons.
    if (e && e.target && e.target.closest && e.target.closest(".chat-mermaid-lightbox__toolbar")) return;
    dragging = true;
    wrap.classList.add("chat-mermaid-lightbox__svg--dragging");
    dragStartX = Number(e.clientX || 0);
    dragStartY = Number(e.clientY || 0);
    dragScrollLeft = wrap.scrollLeft;
    dragScrollTop = wrap.scrollTop;
  };
  const onDragMove = (e) => {
    if (!dragging) return;
    const x = Number(e.clientX || 0);
    const y = Number(e.clientY || 0);
    wrap.scrollLeft = dragScrollLeft - (x - dragStartX);
    wrap.scrollTop = dragScrollTop - (y - dragStartY);
  };
  const onDragEnd = () => {
    dragging = false;
    wrap.classList.remove("chat-mermaid-lightbox__svg--dragging");
  };
  wrap.addEventListener("mousedown", (e) => onDragStart(e));
  window.addEventListener("mousemove", (e) => onDragMove(e));
  window.addEventListener("mouseup", () => onDragEnd());
  wrap.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const dy = Number(e.deltaY || 0);
      const step = dy > 0 ? -0.08 : 0.08;
      scale = clamp(scale + step);
      applyScale();
    },
    { passive: false },
  );
  inner.appendChild(closeBtn);
  inner.appendChild(toolbar);
  inner.appendChild(wrap);
  backdrop.appendChild(inner);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeChatImageLightbox();
  });
  document.body.appendChild(backdrop);
  applyScale();
}

function bindChatImageViewer(messagesEl) {
  messagesEl.addEventListener("click", (ev) => {
    const img = ev.target && ev.target.closest && ev.target.closest("img");
    if (!img || !messagesEl.contains(img)) return;
    const src = img.currentSrc || img.getAttribute("src") || "";
    if (!src.trim()) return;
    ev.preventDefault();
    ev.stopPropagation();
    openChatImageLightbox(src, img.getAttribute("alt") || "");
  });
}

function bindChatMermaidViewer(messagesEl) {
  messagesEl.addEventListener("click", (ev) => {
    const svg = ev.target && ev.target.closest && ev.target.closest(".mermaid svg");
    if (!svg || !messagesEl.contains(svg)) return;
    ev.preventDefault();
    ev.stopPropagation();
    openChatMermaidLightbox(svg.outerHTML || "");
  });
}

/** Keep markdown output safe but allow images (USE_PROFILES html strips img in many DOMPurify builds). */
function renderMarkdownHtml(src) {
  const raw = String(src ?? "");
  if (typeof marked !== "undefined" && typeof DOMPurify !== "undefined") {
    const html =
      typeof marked.parse === "function"
        ? marked.parse(raw, { breaks: true, mangle: false, headerIds: false })
        : marked(raw, { breaks: true });
    const opts = {
      ADD_TAGS: ["img", "picture", "source"],
      ADD_ATTR: ["src", "alt", "title", "loading", "class", "width", "height", "decoding", "referrerpolicy", "sizes", "srcset"],
    };
    try {
      return DOMPurify.sanitize(html, opts);
    } catch (_) {
      return DOMPurify.sanitize(html);
    }
  }
  return `<div class="chat-msg__plain">${escapeHtml(raw).replace(/\n/g, "<br/>")}</div>`;
}

let _mermaidBootstrapped = false;
let _mermaidRetryTimer = null;
window.__oclawHydrateMermaidAll = () => {
  try {
    const root = document.getElementById("app") || document.body;
    hydrateMermaidIn(root);
  } catch (_) {}
};
function hydrateMermaidIn(root) {
  const host = root && root.querySelectorAll ? root : null;
  if (!host) return;
  const codeNodes = host.querySelectorAll("pre > code.language-mermaid, pre > code.lang-mermaid");
  for (const code of codeNodes) {
    const pre = code.parentElement;
    if (!pre || !pre.parentElement) continue;
    const txt = String(code.textContent || "").trim();
    if (!txt) continue;
    const box = document.createElement("div");
    box.className = "mermaid";
    box.setAttribute("data-mermaid-raw", txt);
    box.textContent = txt;
    pre.parentElement.replaceChild(box, pre);
  }
  const _attachFallback = (node, errText = "") => {
    if (!node || node.querySelector(".mermaid-fallback")) return;
    const raw = String(node.getAttribute("data-mermaid-raw") || "").trim() || String(node.textContent || "").trim();
    const msg = String(errText || "").trim();
    node.innerHTML = `<div class="mermaid-fallback">${msg ? `<div class="mermaid-fallback__err">${escapeHtml(msg)}</div>` : ""}<pre>${escapeHtml(raw)}</pre></div>`;
  };
  if (typeof mermaid === "undefined") {
    if (_mermaidRetryTimer != null) return;
    _mermaidRetryTimer = setTimeout(() => {
      _mermaidRetryTimer = null;
      try {
        window.__oclawHydrateMermaidAll();
      } catch (_) {}
    }, 350);
    return;
  }
  try {
    if (!_mermaidBootstrapped && typeof mermaid.initialize === "function") {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "loose",
        theme: "base",
        themeVariables: {
          background: "transparent",
          primaryColor: "#1f2937",
          primaryBorderColor: "#94a3b8",
          primaryTextColor: "#e5e7eb",
          lineColor: "#94a3b8",
          textColor: "#e5e7eb",
          fontFamily: "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
        },
      });
      _mermaidBootstrapped = true;
    }
    const nodes = Array.from(host.querySelectorAll(".mermaid")).filter((n) => n && n.isConnected);
    if (!nodes.length) return;
    // Mermaid skips already processed nodes. In streaming / rerender scenarios, DOM can be replaced.
    // Remove the marker so Mermaid treats these nodes as fresh.
    for (const n of nodes) {
      try {
        n.removeAttribute("data-processed");
      } catch (_) {}
    }
    if (typeof mermaid.run === "function") {
      Promise.resolve(mermaid.run({ nodes }))
        .then(() => {
          for (const n of nodes) {
            if (!n || !n.isConnected) continue;
            if (!n.querySelector("svg")) _attachFallback(n, "Mermaid render failed (no svg output)");
          }
        })
        .catch((e) => {
          const msg = String((e && e.message) || e || "Mermaid render failed");
          for (const n of nodes) _attachFallback(n, msg);
        });
    } else if (typeof mermaid.init === "function") {
      try {
        mermaid.init(undefined, nodes);
        for (const n of nodes) {
          if (!n || !n.isConnected) continue;
          if (!n.querySelector("svg")) _attachFallback(n, "Mermaid render failed (no svg output)");
        }
      } catch (e) {
        const msg = String((e && e.message) || e || "Mermaid render failed");
        for (const n of nodes) _attachFallback(n, msg);
      }
    }
  } catch (e) {
    const msg = String((e && e.message) || e || "Mermaid render failed");
    const nodes = host.querySelectorAll(".mermaid");
    for (const n of nodes) _attachFallback(n, msg);
  }
}

const RE_REDACTED_THINKING = new RegExp("<redacted_thinking>\\s*([\\s\\S]*?)\\s*</redacted_thinking>", "i");
const RE_THINK_TAG = new RegExp("<think\\s*>\\s*([\\s\\S]*?)\\s*</think\\s*>", "i");
const RE_THINKING_TAG = new RegExp("<thinking\\s*>\\s*([\\s\\S]*?)\\s*</thinking\\s*>", "i");
const RE_THOUGHT_TAG = new RegExp("<thought\\s*>\\s*([\\s\\S]*?)\\s*</thought\\s*>", "i");

function _findEarliestReasoningBlock(remaining) {
  let best = null;
  for (const re of [RE_REDACTED_THINKING, RE_THINK_TAG, RE_THINKING_TAG, RE_THOUGHT_TAG]) {
    const m = re.exec(remaining);
    re.lastIndex = 0;
    if (!m) continue;
    const start = m.index;
    if (!best || start < best.start) {
      best = { start, end: start + m[0].length, inner: (m[1] || "").trim() };
    }
  }
  return best;
}

function parseReasoningSegments(raw) {
  const parts = [];
  let remaining = String(raw ?? "");
  while (remaining.length) {
    const hit = _findEarliestReasoningBlock(remaining);
    if (!hit) {
      parts.push({ type: "text", text: remaining });
      break;
    }
    if (hit.start > 0) parts.push({ type: "text", text: remaining.slice(0, hit.start) });
    parts.push({ type: "reasoning", text: hit.inner });
    remaining = remaining.slice(hit.end);
  }
  return parts.length ? parts : [{ type: "text", text: "" }];
}

// Oclaw-style: strip <think>/<thinking>/<final> blocks from visible text,
// while keeping code fences intact. This avoids "reasoning leaking" into正文 and
// handles truncated streams (unfinished tags) safely.
const _OC_QUICK_TAG_RE = /<\s*\/?\s*(?:(?:antml:)?(?:think(?:ing)?|thought)|antthinking|final)\b/i;
const _OC_FINAL_TAG_RE = /<\s*\/?\s*final\b[^<>]*>/gi;
const _OC_THINKING_TAG_RE = /<\s*(\/?)\s*(?:(?:antml:)?(?:think(?:ing)?|thought)|antthinking)\b[^<>]*>/gi;

function _findCodeFenceRegions(text) {
  const regions = [];
  const re = /```/g;
  let start = null;
  for (;;) {
    const m = re.exec(text);
    if (!m) break;
    if (start == null) start = m.index;
    else {
      regions.push([start, m.index + 3]);
      start = null;
    }
  }
  return regions;
}

function _isInsideRegion(idx, regions) {
  for (const [a, b] of regions) {
    if (idx >= a && idx < b) return true;
  }
  return false;
}

function stripReasoningTagsFromText(text, { mode = "strict" } = {}) {
  const raw = String(text || "");
  if (!raw || !_OC_QUICK_TAG_RE.test(raw)) return raw;
  _OC_QUICK_TAG_RE.lastIndex = 0;

  // Remove <final> tags (but keep content).
  let cleaned = raw;
  if (_OC_FINAL_TAG_RE.test(cleaned)) {
    _OC_FINAL_TAG_RE.lastIndex = 0;
    const fences = _findCodeFenceRegions(cleaned);
    const matches = [];
    for (const m of cleaned.matchAll(_OC_FINAL_TAG_RE)) {
      const idx = m.index ?? 0;
      matches.push({ idx, len: m[0].length, inCode: _isInsideRegion(idx, fences) });
    }
    for (let i = matches.length - 1; i >= 0; i -= 1) {
      const mm = matches[i];
      if (mm.inCode) continue;
      cleaned = cleaned.slice(0, mm.idx) + cleaned.slice(mm.idx + mm.len);
    }
  } else {
    _OC_FINAL_TAG_RE.lastIndex = 0;
  }

  const fences = _findCodeFenceRegions(cleaned);
  _OC_THINKING_TAG_RE.lastIndex = 0;
  let out = "";
  let last = 0;
  let inThinking = false;
  for (const m of cleaned.matchAll(_OC_THINKING_TAG_RE)) {
    const idx = m.index ?? 0;
    const isClose = m[1] === "/";
    if (_isInsideRegion(idx, fences)) continue;
    if (!inThinking) {
      out += cleaned.slice(last, idx);
      if (!isClose) inThinking = true;
    } else if (isClose) {
      inThinking = false;
    }
    last = idx + m[0].length;
  }
  if (!inThinking || mode === "preserve") out += cleaned.slice(last);
  return out;
}

function extractThinkingFromText(text) {
  const raw = String(text || "");
  if (!raw) return "";
  const blocks = [];
  for (const re of [RE_REDACTED_THINKING, RE_THINK_TAG, RE_THINKING_TAG, RE_THOUGHT_TAG]) {
    const rr = new RegExp(re.source, "gi");
    for (const m of raw.matchAll(rr)) {
      const inner = String(m[1] || "").trim();
      if (inner) blocks.push(inner);
    }
  }
  return blocks.join("\n");
}

function extractWsAssistantText(message) {
  if (!message || typeof message !== "object") return "";
  const m = message;
  if (typeof m.content === "string") return decodeEscapedNewlines(String(m.content || ""));
  if (typeof m.text === "string") return decodeEscapedNewlines(String(m.text || ""));
  const c = Array.isArray(m.content) ? m.content : [];
  const parts = c
    .map((x) => {
      if (!x || typeof x !== "object") return "";
      if (String(x.type || "") === "text") return decodeEscapedNewlines(String(x.text || ""));
      return "";
    })
    .filter(Boolean);
  return parts.join("\n");
}

function decodeEscapedNewlines(text) {
  return String(text || "").replace(/\\n/g, "\n").replace(/\\N/g, "\n");
}

function normalizeStreamText(raw) {
  return String(raw || "")
    .replace(/^\s*\n+/, "")
    .replace(/\n{3,}/g, "\n\n");
}

// Streaming surface should be smooth and avoid newline explosions.
function normalizeStreamDisplayText(raw) {
  return String(raw || "")
    .replace(/\r/g, "")
    .replace(/^\s*\n+/, "")
    .replace(/\n+/g, " ")
    .replace(/[ \t]{2,}/g, " ")
    .trimStart();
}

// Streaming-only: user prefers a more "natural" flow without many newlines.
function normalizeStreamBodyForUi(raw) {
  return String(raw || "")
    .replace(/^\s*\n+/, "")
    .replace(/\r/g, "")
    // Collapse pathological newline runs but keep paragraph breaks.
    // 3+ newlines => 2 newlines; trim leading newlines.
    .replace(/\n{3,}/g, "\n\n");
}

// Oclaw-style streaming stitcher: reduce boundary artifacts without destroying layout.
function createStreamStitcher() {
  let prevTail = "";
  return {
    push(delta) {
      let s = String(delta || "");
      if (!s) return "";
      s = s.replace(/\r/g, "");
      // If previous ended with newline and delta starts with newline(s), drop the leading ones.
      if (prevTail.endsWith("\n") && s.startsWith("\n")) {
        s = s.replace(/^\n+/, "\n");
      }
      // If previous ended with a space and delta starts with space/newline, trim the head.
      if (/[ \t]$/.test(prevTail) && /^[ \t\n]/.test(s)) {
        s = s.replace(/^[ \t\n]+/, " ");
      }
      // Avoid 3+ newlines caused by chunk boundaries.
      s = s.replace(/\n{3,}/g, "\n\n");
      prevTail = (prevTail + s).slice(-12);
      return s;
    },
  };
}

function formatToolPanelText(name, payload, options = {}) {
  const streamMode = !!(options && options.streamMode);
  const truncateToolPanel = (s) => {
    const raw = String(s || "").trim();
    if (streamMode) return raw;
    const maxChars = 4000;
    if (raw.length <= maxChars) return raw;
    return `${raw.slice(0, maxChars)}\n\n${t("chat.truncatedNote", { n: raw.length - maxChars })}`;
  };
  const n = String(name || "").trim() || "tool";
  const p = payload && typeof payload === "object" ? payload : {};
  if (String(p.phase || "") === "call" && (p.tool_name != null || p.arguments !== undefined)) {
    const tn = String(p.tool_name || "").trim() || "tool";
    let argsStr = "";
    try {
      argsStr =
        p.arguments && typeof p.arguments === "object"
          ? JSON.stringify(p.arguments, null, 2)
          : String(p.arguments ?? "");
    } catch (_) {
      argsStr = String(p.arguments ?? "");
    }
    const tid = String(p.tool_call_id || "").trim();
    const head = t("chat.callBracket", { name: tn });
    return normalizeStreamText([head, tid ? `tool_call_id: ${tid}` : "", "", argsStr].filter(Boolean).join("\n"));
  }
  const r = p.result && typeof p.result === "object" ? p.result : p;
  // SQL audit payload: keep line breaks and key fields visible.
  if (r && typeof r === "object" && (r.input_sql || r.executed_sql || r.sql_guard)) {
    const guard = r.sql_guard && typeof r.sql_guard === "object" ? r.sql_guard : {};
    const lines = [
      `${n}`,
      `[SQL] input`,
      String(r.input_sql || ""),
      "",
      `[SQL] executed`,
      String(r.executed_sql || ""),
      "",
      `[Guard]`,
      `readonly_enforced=${String(!!guard.readonly_enforced)}`,
      `multi_statement_forbidden=${String(!!guard.multi_statement_forbidden)}`,
      `auto_limit_applied=${String(!!guard.auto_limit_applied)}`,
      `result_row_cap=${String(guard.result_row_cap != null ? guard.result_row_cap : "")}`,
      `engine=${String(r.engine || "")}`,
      `rows_returned=${String(r.rows_returned != null ? r.rows_returned : "")}`,
    ];
    return truncateToolPanel(lines.join("\n").trim());
  }
  let body = "";
  // Prefer human-readable text from tool content blocks when available.
  try {
    const content = Array.isArray(r.content) ? r.content : [];
    const textBlock = content.find((x) => x && typeof x === "object" && String(x.type || "") === "text");
    const text = textBlock ? String(textBlock.text || "") : "";
    if (text.trim()) body = text;
  } catch (_) {}
  if (!body) {
    try {
      body = JSON.stringify(r, null, 2);
    } catch (_) {
      body = String(r || "");
    }
  }
  body = normalizeStreamText(body);
  return `${n}\n${truncateToolPanel(body)}`.trim();
}

function extractSqlAuditPayload(payload) {
  const p = payload && typeof payload === "object" ? payload : {};
  const r = p.result && typeof p.result === "object" ? p.result : p;
  if (!r || typeof r !== "object") return null;
  const inputSql = String(r.input_sql || "");
  const executedSql = String(r.executed_sql || "");
  if (!inputSql && !executedSql && !(r.sql_guard && typeof r.sql_guard === "object")) return null;
  const guard = r.sql_guard && typeof r.sql_guard === "object" ? r.sql_guard : {};
  return {
    inputSql,
    executedSql,
    guard,
    engine: String(r.engine || ""),
    rowsReturned: r.rows_returned != null ? Number(r.rows_returned) : null,
  };
}

function extractToolImageItems(payload) {
  const _toObj = (v) => {
    if (v && typeof v === "object") return v;
    if (typeof v !== "string") return null;
    const s = String(v || "").trim();
    if (!s) return null;
    try {
      const j = JSON.parse(s);
      return j && typeof j === "object" ? j : null;
    } catch (_) {
      return null;
    }
  };
  const p = _toObj(payload) || {};
  const cands = [p, _toObj(p.payload), _toObj(p.result), _toObj(p.payload && p.payload.result), _toObj(p.result && p.result.result)].filter(Boolean);
  const out = [];
  for (const cand of cands) {
    const content = Array.isArray(cand.content) ? cand.content : [];
    for (const item of content) {
      if (!item || typeof item !== "object") continue;
      const typ = String(item.type || "").trim().toLowerCase();
      if (typ === "image" || typ === "input_image") {
        const srcObj = item.source && typeof item.source === "object" ? item.source : {};
        const b64 = String(item.image_base64 || item.data || srcObj.data || "").trim();
        if (!b64) continue;
        const mime = String(item.mime_type || item.mime || srcObj.media_type || "image/png").trim() || "image/png";
        out.push({ type: "image", src: `data:${mime};base64,${b64.replace(/\s/g, "")}` });
        continue;
      }
      if (typ === "image_url") {
        const urlObj = item.image_url && typeof item.image_url === "object" ? item.image_url : {};
        const url = String(item.url || item.image_url || urlObj.url || "").trim();
        if (!url) continue;
        out.push({ type: "image_url", src: url });
      }
    }
  }
  // Fallback: direct attachment-like payload shape.
  const direct = _toObj(p.attachments);
  const atts = Array.isArray(direct) ? direct : [];
  for (const a of atts) {
    if (!a || typeof a !== "object") continue;
    const t = String(a.type || "").toLowerCase();
    if (t === "image" || t === "input_image") {
      const b64 = String(a.image_base64 || a.data || "").trim();
      if (!b64) continue;
      const mime = String(a.mime || a.mime_type || "image/png").trim() || "image/png";
      out.push({ type: "image", src: `data:${mime};base64,${b64.replace(/\s/g, "")}` });
    } else if (t === "image_url") {
      const src = String(a.url || a.image_url || "").trim();
      if (src) out.push({ type: "image_url", src });
    }
  }
  // De-dup by src.
  const uniq = [];
  const seen = new Set();
  for (const it of out) {
    const k = String((it && it.src) || "");
    if (!k || seen.has(k)) continue;
    seen.add(k);
    uniq.push(it);
  }
  return uniq;
}

function _sqlLimitSuffix(inputSql, executedSql) {
  const a = String(inputSql || "").trim();
  const b = String(executedSql || "").trim();
  if (!a || !b || b.length <= a.length) return "";
  const lowerA = a.toLowerCase();
  const lowerB = b.toLowerCase();
  if (lowerB.startsWith(lowerA)) {
    const suffix = b.slice(a.length);
    if (/^\s*limit\s+\d+\s*$/i.test(suffix)) return suffix.trim();
  }
  return "";
}

function _tokenizeSqlForDiff(sqlText) {
  const s = String(sqlText || "");
  return s.match(/\s+|[^\s]+/g) || [];
}

function _renderExecutedSqlWithAddedHighlight(inputSql, executedSql) {
  const a = _tokenizeSqlForDiff(inputSql);
  const b = _tokenizeSqlForDiff(executedSql);
  if (!a.length) return escapeHtml(String(executedSql || ""));
  // LCS-based diff: mark tokens present only in executed SQL.
  const m = a.length;
  const n = b.length;
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  let i = 0;
  let j = 0;
  const out = [];
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      out.push(escapeHtml(b[j]));
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      i += 1;
    } else {
      out.push(
        `<span style="background:#ecfdf5;color:#065f46;border-radius:3px;padding:0 2px;">${escapeHtml(b[j])}</span>`,
      );
      j += 1;
    }
  }
  while (j < n) {
    out.push(
      `<span style="background:#ecfdf5;color:#065f46;border-radius:3px;padding:0 2px;">${escapeHtml(b[j])}</span>`,
    );
    j += 1;
  }
  return out.join("");
}

function formatChatTimestamp(iso) {
  const s = String(iso || "").trim();
  if (!s) return "";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  const loc = state.currentLang === "zh" ? "zh-CN" : "en-US";
  try {
    return d.toLocaleString(loc, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch (_) {
    return s;
  }
}

function prependMessageTime(node, tsIso) {
  const txt = formatChatTimestamp(tsIso);
  if (!txt || !node) return;
  node.insertBefore(el("div", { class: "chat-msg__time", text: txt }), node.firstChild);
}

const CHAT_BOT_LOGO_SRC = "/admin/brand-assets/logo.svg";
const CHAT_BOT_LOGO_FALLBACK_SRC = "/admin/assets/oliver.svg";
/** 内置默认用户头像（与助手头像同尺寸与底栏样式，SVG） */
const DEFAULT_USER_AVATAR_SRC = "/admin/assets/default-user-avatar.svg";


async function loadMeProfile() {
  try {
    const r = await apiGet("/admin/api/chat/profile");
    state.meProfile = r && r.ok && r.profile ? r.profile : null;
  } catch (_) {
    state.meProfile = null;
  }
}

function buildBotAvatarImg() {
  const img = el("img", {
    class: "chat-avatar chat-avatar--bot",
    src: CHAT_BOT_LOGO_SRC,
    alt: "",
    loading: "lazy",
  });
  img.addEventListener(
    "error",
    () => {
      if (img.dataset.logoFallbackApplied === "1") return;
      img.dataset.logoFallbackApplied = "1";
      img.src = CHAT_BOT_LOGO_FALLBACK_SRC;
    },
    { once: true },
  );
  return img;
}

function buildUserAvatarSlot() {
  const wrap = el("div", { class: "chat-avatar-slot" });
  const cur = el("img", {
    class: "chat-avatar chat-avatar--img chat-avatar--userBuiltin",
    src: DEFAULT_USER_AVATAR_SRC,
    alt: "",
    loading: "lazy",
  });
  wrap.appendChild(cur);
  const aid = state.meProfile && String(state.meProfile.avatar_attachment_id || "").trim();
  if (aid) {
    fetchAttachmentBlobUrl(aid).then((url) => {
      if (!url || !cur.parentNode) return;
      cur.classList.remove("chat-avatar--userBuiltin");
      cur.classList.add("chat-avatar--userPhoto");
      cur.src = url;
    });
  }
  return wrap;
}

function wrapAssistantMessage(innerRoot, tsIso) {
  const col = el("div", { class: "chat-msg-col chat-msg-col--assistant" });
  prependMessageTime(col, tsIso);
  col.appendChild(innerRoot);
  const row = el("div", { class: "chat-row chat-row--assistant" });
  row.appendChild(buildBotAvatarImg());
  row.appendChild(col);
  return row;
}

function wrapUserMessage(innerRoot, tsIso) {
  const col = el("div", { class: "chat-msg-col chat-msg-col--user" });
  prependMessageTime(col, tsIso);
  col.appendChild(innerRoot);
  const row = el("div", { class: "chat-row chat-row--user" });
  row.appendChild(col);
  row.appendChild(buildUserAvatarSlot());
  return row;
}

async function buildMessageBubble(role, content, tsIso) {
  const r = String(role || "").toLowerCase();
  const rawText = decodeEscapedNewlines(String(content ?? ""));
  const text =
    r === "assistant" && !state.adminChatShowToolOutput ? stripReasoningTagsFromText(rawText, { mode: "strict" }) : rawText;
  let inner;
  if (r === "user") {
    inner = el("div", { class: "chat-msg chat-msg--user" });
    inner.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(text) }));
    return wrapUserMessage(inner, tsIso);
  }
  if (r === "tool" || r === "function") {
    inner = el("div", { class: "chat-msg chat-msg--tool" });
    inner.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(text) }));
    return wrapAssistantMessage(inner, tsIso);
  }
  if (r !== "assistant") {
    inner = el("div", { class: "chat-msg chat-msg--assistant" });
    inner.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(text) }));
    return wrapAssistantMessage(inner, tsIso);
  }
  const segs = parseReasoningSegments(text);
  const onlyText = segs.length === 1 && segs[0].type === "text";
  if (onlyText) {
    inner = el("div", { class: "chat-msg chat-msg--assistant" });
    inner.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(segs[0].text) }));
  } else {
    inner = el("div", { class: "chat-msg chat-msg--assistant chat-msg--rich" });
    const collapsedItems = [];
    for (const seg of segs) {
      if (seg.type === "text") {
        let body = String(seg.text || "");
        const prev = inner.lastElementChild;
        if (prev && prev.classList && prev.classList.contains("chat-msg__reasoning")) {
          body = body.replace(/^\s+/, "");
        }
        if (!body.trim()) continue;
        inner.appendChild(el("div", { class: "chat-msg__md", html: renderMarkdownHtml(body) }));
      } else {
        if (state.adminChatShowToolOutput) collapsedItems.push({ title: t("reasoning.summary"), text: seg.text || "—" });
      }
    }
    if (collapsedItems.length) {
      const det = document.createElement("details");
      det.className = "chat-msg__reasoning";
      const sum = document.createElement("summary");
      sum.textContent = t("reasoning.summary");
      det.appendChild(sum);
      for (const it of collapsedItems) {
        const title = String((it && it.title) || "");
        const text = String((it && it.text) || "");
        if (!text.trim()) continue;
        det.appendChild(_collapsedBlockNode(title || t("reasoning.summary"), text));
      }
      inner.insertBefore(det, inner.firstChild);
    }
  }
  const hasVisible =
    !!inner.querySelector(".chat-msg__md, .chat-msg__reasoning, .chat-msg__wiki") ||
    String(inner.textContent || "").trim().length > 0;
  if (!hasVisible) {
    inner.appendChild(el("div", { class: "muted", text: t("chat.tools.hidden") }));
  }
  return wrapAssistantMessage(inner, tsIso);
}

const _blobUrlCache = new Map();
const _attachmentTextPreviewCache = new Map();

async function fetchAttachmentBlobUrl(attachmentId) {
  const aid = String(attachmentId || "").trim();
  if (!aid) return null;
  if (_blobUrlCache.has(aid)) return _blobUrlCache.get(aid);
  const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  const res = await fetch(`/admin/api/chat/attachments/${encodeURIComponent(aid)}`, {
    headers: token ? { authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) return null;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  _blobUrlCache.set(aid, url);
  return url;
}

async function fetchAttachmentTextPreview(attachmentId, maxChars = 1800) {
  const aid = String(attachmentId || "").trim();
  if (!aid) return "";
  if (_attachmentTextPreviewCache.has(aid)) return _attachmentTextPreviewCache.get(aid) || "";
  const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  const res = await fetch(`/admin/api/chat/attachments/${encodeURIComponent(aid)}`, {
    headers: token ? { authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`preview_http_${res.status}`);
  const blob = await res.blob();
  const txt = String(await blob.text());
  const out = txt.length > maxChars ? `${txt.slice(0, maxChars)}\n…` : txt;
  _attachmentTextPreviewCache.set(aid, out);
  return out;
}

function parseAttachments(raw) {
  if (raw == null || raw === "") return [];
  if (Array.isArray(raw)) return raw.filter((x) => x && typeof x === "object");
  if (typeof raw === "object" && !Array.isArray(raw)) {
    return [raw];
  }
  if (typeof raw === "string") {
    const s = raw.trim();
    if (!s || s === "null") return [];
    try {
      const j = JSON.parse(s);
      if (Array.isArray(j)) return j.filter((x) => x && typeof x === "object");
      if (j && typeof j === "object") return [j];
    } catch (_) {
      return [];
    }
  }
  return [];
}

async function renderAttachmentsEl(raw) {
  const list = parseAttachments(raw);
  if (!list.length) return null;
  const wrap = el("div", { class: "chat-att-wrap" });
  const isTextLikeMime = (mime) => {
    const m = String(mime || "").trim().toLowerCase();
    if (!m) return false;
    if (m.startsWith("text/")) return true;
    return (
      m.includes("json") ||
      m.includes("xml") ||
      m.includes("yaml") ||
      m.includes("yml") ||
      m.includes("csv") ||
      m.includes("javascript") ||
      m.includes("typescript")
    );
  };
  const buildRefCard = async (att, typ) => {
    const aid = String(att.attachment_id || att.attachmentId || "").trim();
    const mime = String(att.mime || att.mime_type || "application/octet-stream").trim();
    const name = String(att.name || `${typ || "attachment"}`).trim();
    const bytes = Number(att.bytes || 0);
    const sizeLabel = bytes > 0 ? `${Math.round((bytes / 1024) * 10) / 10} KB` : "";
    const card = el("div", { class: "chat-att-ref" });
    if (aid) card.title = `id: ${aid}`;
    card.appendChild(el("div", { class: "chat-att-ref__name", text: name }));
    card.appendChild(el("div", { class: "chat-att-ref__meta", text: `${typ} · ${mime}${sizeLabel ? ` · ${sizeLabel}` : ""}` }));
    const actions = el("div", { class: "chat-att-ref__actions" });
    if (aid) {
      const url = await fetchAttachmentBlobUrl(aid);
      if (url) {
        actions.appendChild(
          el("a", {
            class: "chat-att-ref__action",
            href: url,
            target: "_blank",
            rel: "noopener noreferrer",
            download: name || undefined,
            text: t("chat.attachment.download"),
          }),
        );
        if (String(typ || "") === "video_ref" && mime.toLowerCase().startsWith("video/")) {
          card.appendChild(
            el("video", {
              class: "chat-att-video u-media-preview",
              controls: true,
              preload: "metadata",
              src: url,
            }),
          );
        }
      }
    } else {
      const remote = String(att.url || "").trim();
      if (remote && String(typ || "") === "video_ref" && mime.toLowerCase().startsWith("video/")) {
        card.appendChild(
          el("video", {
            class: "chat-att-video u-media-preview",
            controls: true,
            preload: "metadata",
            src: remote,
          }),
        );
        actions.appendChild(
          el("a", {
            class: "chat-att-ref__action",
            href: remote,
            target: "_blank",
            rel: "noopener noreferrer",
            text: t("chat.attachment.download"),
          }),
        );
      }
    }
    const canPreviewText = !!aid && (String(typ || "") === "text_ref" || isTextLikeMime(mime));
    if (canPreviewText) {
      const preview = el("button", {
        type: "button",
        class: "chat-att-ref__action",
        text: t("chat.attachment.preview"),
      });
      const pre = el("pre", { class: "chat-att-ref__preview" });
      preview.addEventListener("click", async () => {
        if (!pre.hidden) {
          pre.hidden = true;
          preview.textContent = t("chat.attachment.preview");
          return;
        }
        preview.disabled = true;
        preview.textContent = t("chat.attachment.previewLoading");
        try {
          const txt = await fetchAttachmentTextPreview(aid);
          pre.textContent = txt || t("chat.attachment.previewEmpty");
        } catch (_) {
          pre.textContent = t("chat.attachment.previewError");
        } finally {
          pre.hidden = false;
          preview.disabled = false;
          preview.textContent = t("chat.attachment.preview");
        }
      });
      actions.appendChild(preview);
      card.appendChild(actions);
      card.appendChild(pre);
    } else if (actions.childNodes.length) {
      card.appendChild(actions);
    }
    return card;
  };
  for (const att of list) {
    if (!att || typeof att !== "object") continue;
    const typ = String(att.type || "");
    if (typ === "image_ref") {
      const aid = String(att.attachment_id || att.attachmentId || "").trim();
      const url = aid ? await fetchAttachmentBlobUrl(aid) : null;
      if (url) {
        const img = el("img", { class: "chat-att-img", src: url, alt: String(att.name || "") });
        wrap.appendChild(img);
      } else {
        wrap.appendChild(el("span", { class: "chat-att-chip", text: String(att.name || "image") }));
      }
    } else if (typ === "relay_pointer") {
      let aid = String(att.attachment_id || att.attachmentId || "").trim();
      if (!aid) {
        const p = String(att.pointer_uri || "").trim();
        const m = p.match(/^relay:\/\/attachments\/[^/]+\/([a-f0-9]{8,64})$/i);
        if (m && m[1]) aid = String(m[1]).toLowerCase();
      }
      const mime = String(att.mime || att.mime_type || "").toLowerCase();
      const url = aid ? await fetchAttachmentBlobUrl(aid) : null;
      if (url && (!mime || mime.startsWith("image/"))) {
        const img = el("img", { class: "chat-att-img", src: url, alt: String(att.name || att.rel_path || "relay image") });
        wrap.appendChild(img);
      } else {
        const title = String(att.name || att.rel_path || att.pointer_uri || "relay pointer");
        wrap.appendChild(el("span", { class: "chat-att-chip", text: `📎 ${title}` }));
      }
    } else if (typ === "image_url") {
      const src = String(att.url || att.image_url || "").trim();
      if (!src) continue;
      const img = el("img", {
        class: "chat-att-img",
        src,
        alt: String(att.name || "generated image"),
        decoding: "async",
        referrerPolicy: "no-referrer",
      });
      img.addEventListener(
        "error",
        () => {
          try {
            const parent = img.parentNode;
            if (!parent) return;
            parent.replaceChild(
              el("a", {
                class: "chat-att-ref__action",
                href: src,
                target: "_blank",
                rel: "noopener noreferrer",
                text:
                  t("chat.imageBlockedHint"),
              }),
              img,
            );
          } catch (_) {}
        },
        { once: true },
      );
      wrap.appendChild(img);
    } else if (typ === "video_ref" || typ === "text_ref" || typ === "binary_ref") {
      wrap.appendChild(await buildRefCard(att, typ));
    } else if (typ === "image" || typ === "input_image") {
      const b64 = att.image_base64 || att.data;
      const mime = String(att.mime || "image/jpeg");
      if (b64) {
        const src = `data:${mime};base64,${String(b64).replace(/\s/g, "")}`;
        wrap.appendChild(el("img", { class: "chat-att-img", src, alt: String(att.name || "") }));
      } else {
        wrap.appendChild(el("span", { class: "chat-att-chip", text: String(att.name || "image") }));
      }
    } else {
      const maybeAid = String(att.attachment_id || att.attachmentId || "").trim();
      if (maybeAid) wrap.appendChild(await buildRefCard(att, typ || "attachment_ref"));
      else wrap.appendChild(el("span", { class: "chat-att-chip", text: `📄 ${String(att.name || "file")}` }));
    }
  }
  return wrap.children.length ? wrap : null;
}

async function appendMessageRow(messagesEl, m, options = {}) {
  const role = String(m.role || "");
  const content = String(m.content || "");
  const ts = m.timestamp != null ? m.timestamp : "";
  const bubble = Array.isArray(m._items)
    ? await _buildAggregatedAssistantBubble(ts, m._items)
    : await buildMessageBubble(role, content, ts);
  // For aggregated assistant bubbles, attachments should be rendered inline
  // at tool_result positions, not appended at bubble tail.
  const att = Array.isArray(m._items) ? null : await renderAttachmentsEl(m.attachments);
  if (att) {
    const innerBubble = bubble.querySelector(".chat-msg-col .chat-msg");
    if (innerBubble) innerBubble.appendChild(att);
    else bubble.appendChild(att);
  }
  const colNode = bubble.querySelector(".chat-msg-col");
  const innerBubble = bubble.querySelector(".chat-msg-col .chat-msg");
  if (innerBubble) {
    const copyText = (() => {
      const v = String(innerBubble.innerText || "").trim();
      return v;
    })();
    const ids = Array.isArray(m._message_ids) ? m._message_ids.filter((x) => x != null) : (m.id != null ? [m.id] : []);
    const canDelete = ids.length === 1 && typeof options.onDeleteMessage === "function";
    if (copyText || canDelete) {
      const bar = el("div", { class: "chat-msg__actions" });
      if (copyText) {
        bar.appendChild(
          el("button", {
            type: "button",
            class: "chat-msg__action-btn",
            text: "⧉",
            title: t("chat.copy"),
            "aria-label": t("chat.copy"),
            onclick: async (e) => {
              e.preventDefault();
              e.stopPropagation();
              try {
                await navigator.clipboard.writeText(copyText);
                if (typeof options.onActionStatus === "function") options.onActionStatus(t("chat.copyOk"));
              } catch (_) {
                if (typeof options.onActionStatus === "function") options.onActionStatus(t("chat.copyFail"));
              }
            },
          }),
        );
      }
      if (canDelete) {
        bar.appendChild(
          el("button", {
            type: "button",
            class: "chat-msg__action-btn chat-msg__action-btn--danger",
            text: "🗑",
            title: t("chat.deleteMessage"),
            "aria-label": t("chat.deleteMessage"),
            onclick: async (e) => {
              e.preventDefault();
              e.stopPropagation();
              let ok = false;
              if (typeof options.onConfirm === "function") {
                ok = await options.onConfirm(t("chat.deleteMessageConfirm"));
              } else {
                ok = window.confirm(t("chat.deleteMessageConfirm"));
              }
              if (!ok) return;
              await options.onDeleteMessage(ids[0]);
            },
          }),
        );
      }
      if (colNode) colNode.appendChild(bar);
      else innerBubble.appendChild(bar);
    }
  }
  if (options.prependBefore && options.prependBefore.parentNode === messagesEl) {
    messagesEl.insertBefore(bubble, options.prependBefore);
  } else if (options.prepend) {
    messagesEl.insertBefore(bubble, messagesEl.firstChild);
  } else {
    messagesEl.appendChild(bubble);
  }
  hydrateMermaidIn(bubble);
}

function mount(node) {
  clearChatPageBlockers();
  const c = document.getElementById("app");
  c.innerHTML = "";
  c.appendChild(node);
}

function buildChatBrandLogoNode() {
  const img = el("img", {
    class: "chat-nav__brandLogo",
    src: CHAT_BOT_LOGO_SRC,
    alt: "site logo",
  });
  img.addEventListener(
    "error",
    () => {
      if (img.dataset.logoFallbackApplied === "1") return;
      img.dataset.logoFallbackApplied = "1";
      img.src = CHAT_BOT_LOGO_FALLBACK_SRC;
    },
    { once: true },
  );
  return el("div", { class: "chat-nav__brandWrap" }, [img]);
}

function resolveAdminHashUrl(hashPath, sessionId) {
  const path = (location.pathname || "").replace(/\/+$/, "") || "/";
  const cleanHash = String(hashPath || "").replace(/^#?\/?/, "");
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  if (path.endsWith("/chat")) {
    const base = path.slice(0, -5);
    return base.endsWith("/admin") ? `${base}#/${cleanHash}${q}` : `${base}/admin#/${cleanHash}${q}`;
  }
  return `/admin#/${cleanHash}${q}`;
}

function openAdminFromChat(hashPath, sessionId) {
  const target = resolveAdminHashUrl(hashPath, sessionId);
  // Keep navigation in the same window so desktop shell feels native.
  window.location.assign(target);
}

function syncAuthUserLabel() {
  const user = document.getElementById("authUser");
  if (!user) return;
  user.innerHTML = "";
  const name = String((state.authSession && (state.authSession.display_name || state.authSession.username || state.authSession.user_id)) || "");
  const isAdminViewer = String((state.authSession && state.authSession.username) || "")
    .trim()
    .toLowerCase() === "administrator";
  if (!name) return;
  const openUserMenu = (anchorEl) => {
    clearChatPageBlockers();
    const items = [
      el("button", {
        type: "button",
        class: "chat-sess-menu-item",
        "data-menu-action": "profile",
        text: t("chat.myProfile"),
      }),
      el("button", {
        type: "button",
        class: "chat-sess-menu-item",
        "data-menu-action": "jobs",
        text: t("chat.jobs"),
      }),
    ];
    items.push(el("div", { class: "chat-sess-menu-sep" }));
    items.push(
      el("div", { class: "muted u-menu-label", text: t("theme.label") }),
    );
    const themeSelMenu = el("select", {
      class: "input u-menu-select",
    });
    try {
      (window.OclawAdminTheme && window.OclawAdminTheme.THEMES ? window.OclawAdminTheme.THEMES : ["netx"]).forEach((tid) => {
        themeSelMenu.appendChild(el("option", { value: tid, text: t(`theme.${tid}`) }));
      });
      themeSelMenu.value = window.OclawAdminTheme ? window.OclawAdminTheme.currentAdminTheme() : "netx";
    } catch (_) {}
    themeSelMenu.addEventListener("change", () => {
      try {
        if (window.OclawAdminTheme) window.OclawAdminTheme.persistAdminTheme(themeSelMenu.value);
      } catch (_) {}
    });
    items.push(themeSelMenu);
    const bridge = window.__chatUserMenuPrefs;
    if (bridge && typeof bridge === "object") {
      items.push(el("div", { class: "chat-sess-menu-sep" }));
      items.push(el("div", { class: "muted u-menu-label", text: t("chat.modeLabel") }));
      const modeSel = el("select", { class: "input u-menu-select" });
      try {
        const rows = Array.isArray(bridge.getModeOptions && bridge.getModeOptions()) ? bridge.getModeOptions() : [];
        rows.forEach((r) => modeSel.appendChild(el("option", { value: String(r.value || ""), text: String(r.label || r.value || "") })));
        modeSel.value = String((bridge.getModeValue && bridge.getModeValue()) || "");
      } catch (_) {}
      modeSel.addEventListener("change", async () => {
        const v = modeSel.value;
        try {
          modeSel.disabled = true;
          if (bridge.setModeValue) await bridge.setModeValue(v);
        } catch (_) {
          // errors are surfaced by saveUserGlobalModePreference()
        } finally {
          modeSel.disabled = false;
        }
      });
      items.push(modeSel);
      const reasonWrap = el("label", { class: "switch-wrap u-switch-menu" }, [
        el("input", { type: "checkbox", class: "switch-input" }),
        el("span", { class: "switch-slider" }),
        el("span", { class: "muted", text: t("chat.tools") }),
      ]);
      const reasonCb = reasonWrap.querySelector("input.switch-input");
      try {
        reasonCb.checked = !!(bridge.getReasoningVisible && bridge.getReasoningVisible());
      } catch (_) {}
      reasonCb.addEventListener("change", () => {
        try {
          Promise.resolve(bridge.setReasoningVisible && bridge.setReasoningVisible(!!reasonCb.checked)).catch(() => {});
        } catch (_) {}
      });
      items.push(reasonWrap);
    }
    items.push(el("div", { class: "chat-sess-menu-sep" }));
    items.push(
      el("button", {
        type: "button",
        class: "chat-sess-menu-item",
        "data-menu-action": "lang",
        text: t("lang.switch"),
      }),
    );
    items.push(el("div", { class: "chat-sess-menu-sep" }));
    items.push(
      el("button", {
        type: "button",
        class: "chat-sess-menu-item",
        "data-menu-action": "logout",
        text: t("auth.logout"),
      }),
    );
    const menu = el("div", {
      class: "chat-sess-menu-pop u-pop-menu",
    }, items);
    // Inline position/z-index: chat.html used to override class z-index below the scrim.
    menu.style.position = "fixed";
    menu.style.zIndex = "300";
    const rect = (anchorEl || moreBtn).getBoundingClientRect();
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
  };
  const nameBtn = el("button", {
    type: "button",
    class: "chat-sess-btn",
    text: name,
    title: name,
    onclick: (ev) => {
      ev.stopPropagation();
      openUserMenu(ev.currentTarget);
    },
  });
  const moreBtn = el("button", {
    type: "button",
    class: "chat-sess-more",
    text: "⋯",
    title: t("chat.sessionMenu"),
    onclick: (ev) => {
      ev.stopPropagation();
      openUserMenu(ev.currentTarget);
    },
  });
  const row = el("div", { class: "chat-user-row" }, [nameBtn, moreBtn]);
  user.appendChild(row);
}

async function fileToPayloadEntry(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => {
      const dataUrl = String(r.result || "");
      const idx = dataUrl.indexOf(",");
      const data_base64 = idx >= 0 ? dataUrl.slice(idx + 1) : dataUrl;
      resolve({ name: file.name || "file", data_base64 });
    };
    r.onerror = () => reject(r.error || new Error("file_read_failed"));
    r.readAsDataURL(file);
  });
}

async function renderLogin() {
  applyI18nStatic();
  const username = el("input", { class: "input", placeholder: t("auth.username") });
  const password = el("input", { class: "input", type: "password", placeholder: t("auth.password") });
  const status = el("div", { class: "muted", text: "" });
  const btn = el("button", {
    class: "btn btn--primary",
    type: "button",
    text: t("auth.login"),
  });
  let busy = false;
  const setBusy = (on) => {
    busy = !!on;
    btn.disabled = busy;
    btn.textContent = busy ? t("auth.loggingIn") : t("auth.login");
  };
  const doLogin = async () => {
    if (busy) return;
    setBusy(true);
    status.textContent = t("auth.loggingIn");
    try {
      const resp = await apiPost("/admin/api/auth/login", {
        tenant_id: "",
        username: username.value.trim().toLowerCase(),
        password: password.value.trim(),
        purpose: "chat",
      });
      if (!resp || !resp.ok || !resp.token) {
        const err = String((resp && resp.error) || "");
        status.textContent =
          err === "user_disabled"
            ? t("auth.disabled")
            : err === "admin_role_required"
              ? t("auth.chatLoginDenied")
              : t("auth.invalid");
        setBusy(false);
        return;
      }
      localStorage.setItem(AUTH_TOKEN_KEY, String(resp.token));
      localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(resp.session || {}));
      state.authSession = resp.session || null;
      mount(
        el("div", { class: "chat-app--login" }, [
          el("div", { class: "card u-modal-card-sm" }, [
            el("div", { class: "card__title", text: t("auth.login") }),
            el("div", { class: "muted", text: t("chat.loading") }),
          ]),
        ]),
      );
      await new Promise((resolve) => requestAnimationFrame(() => resolve()));
      await boot();
    } catch (err) {
      status.textContent = String((err && err.message) || err || t("auth.invalid"));
      setBusy(false);
    }
  };
  const onEnterLogin = (ev) => {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    doLogin();
  };
  username.addEventListener("keydown", onEnterLogin);
  password.addEventListener("keydown", onEnterLogin);
  btn.addEventListener("click", (ev) => {
    ev.preventDefault();
    doLogin();
  });
  const card = el("div", { class: "card u-modal-card-sm" }, [
    el("div", { class: "card__title", text: t("auth.login") }),
    el("div", { class: "chat-login-fields" }, [username, password]),
    el("div", { class: "row chat-login-actions" }, [btn]),
    status,
  ]);
  setTimeout(() => {
    try {
      username.focus();
    } catch (_) {}
  }, 0);
  return el("div", { class: "chat-app--login" }, [card]);
}

async function downloadExport(sessionId, format) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  const q = format === "json" ? "format=json" : "format=md";
  const url = `/admin/api/chat/sessions/${encodeURIComponent(sessionId)}/export?${q}`;
  const res = await fetch(url, { headers: token ? { authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new Error(String(res.status));
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `chat-${sessionId.slice(0, 8)}.${format === "json" ? "json" : "md"}`;
  a.click();
  URL.revokeObjectURL(a.href);
}

const CHAT_ICON_CLIP =
  '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>';
const CHAT_ICON_SEND =
  '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 5.5 19 17.5h-5.25V19H10v-1.5H5L12 5.5z"/></svg>';
const CHAT_ICON_STOP =
  '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/></svg>';



export {
  PAGE_SIZE,
  CHAT_MESSAGES_FETCH_LIMIT,
  AUTH_TOKEN_KEY,
  AUTH_SESSION_KEY,
  CHAT_URL_SCOPE_KEY,
  CHAT_SPECIALIST_PREF_KEY,
  CHAT_INTERACTION_MODE_KEY,
  CHAT_MEMORY_MODE_KEY,
  CHAT_EXECUTION_MODE_KEY,
  CHAT_USER_MENU_MODE_KEY,
  CHAT_REASONING_TOGGLE_KEY,
  EXECUTION_MODE_AGENT,
  EXECUTION_MODE_PLAN,
  ADMIN_CHAT_SHOW_TOOL_OUTPUT_DEFAULT,
  REASONING_BLOCK_MAX_CHARS,
  CHAT_ENABLE_WIKI_EVENT_POLLER,
  _toolSummaryTitle,
  _normalizeEventType,
  _isAssistantBodyEventType,
  _parseEventPayload,
  _isScheduledProactiveMessage,
  _messageTurnUuid,
  _pushScheduledAssistantRow,
  _collapsedBlockNode,
  _appendCollapsedBundle,
  _appendAssistantTextSegments,
  _normFoldDedupText,
  _foldProcessTextRedundant,
  _preferredAttachmentOwnerById,
  _attachmentsForBubbleItem,
  _buildAggregatedAssistantBubble,
  _buildRenderRows,
  _needsWsTextFallbackFromRenderRows,
  interactionModeLabel,
  specialistLabel,
  memoryModeShortLabel,
  _ensureToastHost,
  showToast,
  _jobsPanelPollTimer,
  _jobsBadgePollTimer,
  _jobStatusLabel,
  _fmtJobTs,
  updateJobsBadge,
  refreshJobsBadge,
  startJobsBadgePoller,
  stopJobsBadgePoller,
  openBackgroundJobsPanel,
  openWikiPreviewModal,
  reasonLabel,
  fetchDynamicExpertStats,
  getDispatchReasonLabelsConfig,
  setDispatchReasonLabelsConfig,
  openDispatchLabelsEditor,
  getSessionIdFromUrl,
  forceReloginRequested,
  clearAuthAndReloginFlagFromUrl,
  replaceSessionUrl,
  withTimeout,
  apiGet,
  apiPost,
  apiPatch,
  apiDelete,
  el,
  escapeHtml,
  formatChatSessionTitle,
  _peerNameLookupKeys,
  _channelPeerNameMap,
  lookupChannelPeerName,
  refreshChannelPeerNameMap,
  _chatLightboxKeyHandler,
  _chatLightboxPrevOverflow,
  closeChatImageLightbox,
  dismissChatMenus,
  isChatStreaming,
  clearChatPageBlockers,
  attachChatMenuDismiss,
  openChatImageLightbox,
  openChatMermaidLightbox,
  bindChatImageViewer,
  bindChatMermaidViewer,
  renderMarkdownHtml,
  _mermaidBootstrapped,
  _mermaidRetryTimer,
  hydrateMermaidIn,
  RE_REDACTED_THINKING,
  RE_THINK_TAG,
  RE_THINKING_TAG,
  RE_THOUGHT_TAG,
  _findEarliestReasoningBlock,
  parseReasoningSegments,
  _OC_QUICK_TAG_RE,
  _OC_FINAL_TAG_RE,
  _OC_THINKING_TAG_RE,
  _findCodeFenceRegions,
  _isInsideRegion,
  stripReasoningTagsFromText,
  extractThinkingFromText,
  extractWsAssistantText,
  decodeEscapedNewlines,
  normalizeStreamText,
  normalizeStreamDisplayText,
  normalizeStreamBodyForUi,
  createStreamStitcher,
  formatToolPanelText,
  extractSqlAuditPayload,
  extractToolImageItems,
  _sqlLimitSuffix,
  _tokenizeSqlForDiff,
  _renderExecutedSqlWithAddedHighlight,
  formatChatTimestamp,
  prependMessageTime,
  CHAT_BOT_LOGO_SRC,
  CHAT_BOT_LOGO_FALLBACK_SRC,
  DEFAULT_USER_AVATAR_SRC,
  loadMeProfile,
  buildBotAvatarImg,
  buildUserAvatarSlot,
  wrapAssistantMessage,
  wrapUserMessage,
  buildMessageBubble,
  _blobUrlCache,
  _attachmentTextPreviewCache,
  fetchAttachmentBlobUrl,
  fetchAttachmentTextPreview,
  parseAttachments,
  renderAttachmentsEl,
  appendMessageRow,
  mount,
  buildChatBrandLogoNode,
  resolveAdminHashUrl,
  openAdminFromChat,
  syncAuthUserLabel,
  fileToPayloadEntry,
  renderLogin,
  downloadExport,
  CHAT_ICON_CLIP,
  CHAT_ICON_SEND,
  CHAT_ICON_STOP,
  state,
  t,
  applyI18nStatic,
  LANG_KEY,
  I18N,
};
