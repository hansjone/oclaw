/* Standalone /chat page: same bearer + /admin/api/chat as admin SPA. */

const PAGE_SIZE = 35;

const I18N = {
  zh: {
    "chat.pageTitle": "oliver",
    "chat.backAdmin": "管理台",
    "chat.newSession": "开启新对话",
    "chat.send": "发送",
    "chat.stop": "停止",
    "chat.sessions": "会话",
    "chat.modelProfile": "模型",
    "chat.placeholder": "输入消息…",
    "chat.empty": "暂无消息",
    "chat.noSessions": "暂无会话，点击新建开始。",
    "chat.loading": "加载中…",
    "chat.sending": "发送中…",
    "chat.error": "请求失败",
    "chat.loadMore": "加载更多",
    "chat.sessionMenu": "会话操作",
    "chat.rename": "重命名",
    "chat.delete": "删除",
    "chat.copy": "复制",
    "chat.deleteMessage": "删除消息",
    "chat.deleteMessageConfirm": "删除这条消息？",
    "chat.copyOk": "已复制",
    "chat.copyFail": "复制失败",
    "chat.deleteConfirm": "删除此会话？",
    "chat.exportMd": "导出 Markdown",
    "chat.exportJson": "导出 JSON",
    "chat.fork": "复制会话",
    "chat.audit": "审计与追踪",
    "chat.myProfile": "设置",
    "chat.attach": "附件",
    "chat.tools": "推理",
    "chat.tools.hidden": "推理已隐藏",
    "chat.tools.visible": "推理已显示",
    "chat.compressHistory": "压缩历史",
    "chat.compressHistoryPrompt": "将本会话历史工具输出按回放策略写回压缩（不可逆）？建议仅在发现超大 tool_result/导出卡顿时使用。",
    "chat.compressHistoryOk": "压缩完成：扫描 {scanned} 条 tool 消息，重写 {rewritten} 条，超限压缩 {compacted} 条（已跳过 {skipped} 条已压缩）。",
    "chat.compressHistoryFail": "压缩失败：{error}",
    "chat.tools.off": "关",
    "chat.tools.on": "开",
    "chat.status.oclaw": "主控",
    "chat.status.agent": "专家",
    "chat.status.tool": "工具",
    "chat.status.plan": "规划",
    "chat.status.start": "启动",
    "chat.status.running": "执行中",
    "chat.status.end": "完成",
    "chat.status.error": "异常",
    "chat.marker.summary": "文件标记：指针 {p}，封套 {e}（封套内 {ep}）",
    "chat.marker.ttl": "TTL：turn {t} / session {s} / keep {k}",
    "chat.marker.reclaimed": "本轮回收 turn 标记 {n}",
    "chat.historyTruncated": "仅显示最近 {shown} 条，共 {total} 条",
    "reasoning.summary": "模型推理片段",
    "tool.streamTitle": "工具与进度（本轮）",
    "auth.login": "登录",
    "auth.logout": "退出登录",
    "auth.username": "用户名",
    "auth.password": "密码",
    "auth.invalid": "登录失败，请检查凭据",
    "auth.consoleAdminOnly": "仅管理员（admin 角色）可登录管理台。",
    "auth.chatLoginDenied": "当前账号无法使用对话（请联系管理员）。",
    "auth.disabled": "账号已被禁用，请联系管理员",
    "common.error": "错误",
    "lang.switch": "English",
    "chat.imageViewerClose": "关闭",
    "chat.imageViewerHint": "点击查看大图，空白处或 Esc 关闭",
    "chat.specialistLabel": "专家",
    "chat.modeLabel": "模式",
    "chat.modeComprehensive": "综合",
    "chat.modeExpert": "专家",
    "chat.specialistGeneralist": "通用",
    "chat.specialistOps": "运维",
    "chat.specialistImage": "图像",
    "chat.specialistMemory": "记忆",
    "chat.memoryModeLabel": "记忆模式",
    "chat.memoryModeDefault": "默认（可注入）",
    "chat.memoryModeStoreOnly": "仅记录不注入",
    "chat.memoryApplied": "记忆：{mode}",
    "chat.memoryModeDefaultShort": "默认",
    "chat.memoryModeStoreOnlyShort": "仅记录",
    "chat.wikiToastMerged": "Wiki 已收录：+{merged}（去重跳过 {skipped}）",
    "chat.wikiToastFailed": "Wiki 收录失败：{error}",
    "chat.wikiViewMerged": "查看 merged-turns",
    "chat.wikiViewTopic": "查看 topic：{topic}",
    "chat.wikiPreviewTitle": "Wiki 预览：{path}",
    "chat.wikiPreviewClose": "关闭",
    "chat.specialistManage": "专家开关",
    "chat.specialistManagePromptOn": "是否启用 memory 专家？",
    "chat.specialistManagePromptOff": "是否关闭 memory 专家？",
    "chat.specialistManageDenied": "无权限修改专家开关",
    "chat.attachmentLimits": "附件阈值",
    "chat.attachmentLimitsPrompt": "编辑附件阈值 JSON（留空恢复默认）",
    "chat.attachmentLimitsSaved": "附件阈值已更新",
    "chat.attachmentLimitsDenied": "无权限修改附件阈值",
    "chat.attachmentLimitsInvalidJson": "附件阈值 JSON 不合法",
    "chat.attachmentLimitsTitle": "附件阈值配置",
    "chat.attachmentLimitsRows": "最大读取行数",
    "chat.attachmentLimitsCols": "最大保留列数",
    "chat.attachmentLimitsCellChars": "单元格最大字符数",
    "chat.attachmentLimitsMaxSheets": "Excel 最大 Sheet 数",
    "chat.attachmentLimitsLargePreviewRows": "大表摘要预览行数",
    "chat.attachmentLimitsToolEnabled": "启用大表工具模式",
    "chat.attachmentLimitsToolMinRows": "触发工具模式最小行数",
    "chat.attachmentLimitsToolMaxBytes": "工具模式最大文件字节数",
    "chat.attachmentLimitsSqlTimeoutMs": "SQL 超时（毫秒）",
    "chat.attachmentLimitsReset": "恢复默认",
    "chat.attachmentLimitsCancel": "取消",
    "chat.attachmentLimitsSave": "保存",
    "chat.attachmentLimitsInvalidNumber": "请输入有效正整数",
    "chat.attachmentLimitsHighPreviewWarn": "大表摘要预览行数超过 200，可能显著增加 token 消耗。确认继续？",
    "chat.activeModelLabel": "模型",
    "chat.execApplied": "本轮执行：{mode} / {specialist}",
    "chat.dynamicStats": "动态专家近窗：命中 {dynamic}，回退 {fallback}",
    "chat.dynamicStatsDetail": "命中率 {rate}% · Top原因 {reason}",
    "chat.dynamicTopReasons": "原因分布 {items}",
    "chat.dynamicAllReasons": "查看完整分布",
    "chat.dynamicAllReasonsTitle": "完整原因分布",
    "chat.dispatchLabelsEdit": "编辑原因文案",
    "chat.dispatchLabelsPrompt": "编辑 dispatch reason 覆盖 JSON（留空清空）",
    "chat.dispatchLabelsSaved": "原因文案已更新",
    "chat.dispatchLabelsTitle": "编辑原因文案覆盖",
    "chat.dispatchLabelsSave": "保存",
    "chat.dispatchLabelsClear": "清空",
    "chat.dispatchLabelsCancel": "取消",
    "chat.dispatchLabelsInvalidJson": "JSON 格式不合法",
    "chat.dispatchLabelsEffectivePreview": "Effective 预览",
    "chat.dispatchLabelsDiffOnly": "仅显示变更项",
    "chat.dispatchLabelsExport": "导出 Effective",
    "chat.dispatchLabelsImport": "导入 JSON",
    "chat.dispatchLabelsRestoreDefaults": "恢复默认模板",
    "chat.dispatchLabelsUnsavedConfirm": "当前有未保存变更，确认关闭？",
    "chat.reason.manager_no_specialist_fallback": "无可用专家，回退通用",
    "chat.reason.dynamic_agent_build_failed": "动态专家构建失败",
    "chat.reason.manager_factory_failed": "专家执行器创建失败",
    "chat.reason.manager_route_missing": "全能者路由缺失",
    "chat.reason.manager_select_failed": "全能者决策失败",
    "chat.reason.manager_model_missing": "全能者模型不可用",
    "chat.reason.dynamic_agent_selected": "动态专家命中",
    "chat.modeComprehensiveShort": "综合",
    "chat.modeExpertShort": "专家",
    "chat.specialistGeneralistShort": "通用",
    "chat.specialistOpsShort": "运维",
    "chat.specialistImageShort": "图像",
    "chat.specialistMemoryShort": "记忆",
    "chat.specialistManagerSelfShort": "全能者",
    "chat.attachment.download": "下载",
    "chat.attachment.preview": "预览",
    "chat.attachment.previewLoading": "加载中…",
    "chat.attachment.previewError": "预览失败",
    "chat.attachment.previewEmpty": "（空内容）",
    "chat.attachmentAcl": "附件 ACL",
    "chat.attachmentAclBackfill": "回填 ACL",
    "chat.attachmentAclBackfillPrompt": "回填 attachment_acl（扫描历史消息 attachments）？建议先在低峰期执行。",
    "chat.attachmentAclBackfillOk": "回填完成：插入 {inserted} 条（扫描 {scanned_messages} 条消息）",
    "chat.attachmentAclBackfillFail": "回填失败：{error}",
  },
  en: {
    "chat.pageTitle": "oliver",
    "chat.backAdmin": "Admin console",
    "chat.newSession": "New chat",
    "chat.send": "Send",
    "chat.stop": "Stop",
    "chat.sessions": "Sessions",
    "chat.modelProfile": "Model",
    "chat.placeholder": "Message…",
    "chat.empty": "No messages yet",
    "chat.noSessions": "No sessions yet. Create one to start.",
    "chat.loading": "Loading…",
    "chat.sending": "Sending…",
    "chat.error": "Request failed",
    "chat.loadMore": "Load more",
    "chat.sessionMenu": "Session actions",
    "chat.rename": "Rename",
    "chat.delete": "Delete",
    "chat.copy": "Copy",
    "chat.deleteMessage": "Delete message",
    "chat.deleteMessageConfirm": "Delete this message?",
    "chat.copyOk": "Copied",
    "chat.copyFail": "Copy failed",
    "chat.deleteConfirm": "Delete this session?",
    "chat.exportMd": "Export Markdown",
    "chat.exportJson": "Export JSON",
    "chat.fork": "Duplicate chat",
    "chat.audit": "Audit & trace",
    "chat.myProfile": "Settings",
    "chat.attach": "Attach",
    "chat.tools": "Reasoning",
    "chat.tools.hidden": "Reasoning hidden",
    "chat.tools.visible": "Reasoning visible",
    "chat.compressHistory": "Compress history",
    "chat.compressHistoryPrompt": "Rewrite this session's historical tool outputs using replay-guard compaction (irreversible). Use only when a session is polluted by huge tool_result.",
    "chat.compressHistoryOk": "Compaction done: scanned {scanned} tool messages, rewritten {rewritten}, oversized compacted {compacted} (skipped {skipped} already compacted).",
    "chat.compressHistoryFail": "Compaction failed: {error}",
    "chat.tools.off": "Off",
    "chat.tools.on": "On",
    "chat.status.oclaw": "Controller",
    "chat.status.agent": "Agent",
    "chat.status.tool": "Tool",
    "chat.status.plan": "Plan",
    "chat.status.start": "Starting",
    "chat.status.running": "Running",
    "chat.status.end": "Done",
    "chat.status.error": "Error",
    "chat.marker.summary": "File markers: pointers {p}, envelope {e} (in-envelope {ep})",
    "chat.marker.ttl": "TTL: turn {t} / session {s} / keep {k}",
    "chat.marker.reclaimed": "Turn markers reclaimed {n}",
    "chat.historyTruncated": "Showing last {shown} of {total} messages",
    "reasoning.summary": "Model reasoning",
    "tool.streamTitle": "Tools & progress (this turn)",
    "auth.login": "Login",
    "auth.logout": "Logout",
    "auth.username": "Username",
    "auth.password": "Password",
    "auth.invalid": "Login failed",
    "auth.consoleAdminOnly": "Only users with the admin role may sign in to the console.",
    "auth.chatLoginDenied": "This account cannot use chat (contact an admin).",
    "auth.disabled": "Account is disabled",
    "common.error": "Error",
    "lang.switch": "中文",
    "chat.imageViewerClose": "Close",
    "chat.imageViewerHint": "Click image to enlarge; click outside or Esc to close",
    "chat.specialistLabel": "Specialist",
    "chat.modeLabel": "Mode",
    "chat.modeComprehensive": "Comprehensive",
    "chat.modeExpert": "Expert",
    "chat.specialistGeneralist": "Generalist",
    "chat.specialistOps": "Ops",
    "chat.specialistImage": "Image",
    "chat.specialistMemory": "Memory",
    "chat.memoryModeLabel": "Memory Mode",
    "chat.memoryModeDefault": "Default (inject allowed)",
    "chat.memoryModeStoreOnly": "Store only (no inject)",
    "chat.memoryApplied": "Memory: {mode}",
    "chat.memoryModeDefaultShort": "default",
    "chat.memoryModeStoreOnlyShort": "store_only",
    "chat.wikiToastMerged": "Wiki captured: +{merged} (dedup skipped {skipped})",
    "chat.wikiToastFailed": "Wiki capture failed: {error}",
    "chat.wikiViewMerged": "View merged-turns",
    "chat.wikiViewTopic": "View topic: {topic}",
    "chat.wikiPreviewTitle": "Wiki preview: {path}",
    "chat.wikiPreviewClose": "Close",
    "chat.specialistManage": "Specialist Toggle",
    "chat.specialistManagePromptOn": "Enable memory specialist?",
    "chat.specialistManagePromptOff": "Disable memory specialist?",
    "chat.specialistManageDenied": "Not authorized to change specialist flags",
    "chat.attachmentLimits": "Attachment limits",
    "chat.attachmentLimitsPrompt": "Edit attachment limits JSON (empty to restore defaults)",
    "chat.attachmentLimitsSaved": "Attachment limits updated",
    "chat.attachmentLimitsDenied": "Not authorized to change attachment limits",
    "chat.attachmentLimitsInvalidJson": "Invalid attachment limits JSON",
    "chat.attachmentLimitsTitle": "Attachment limits",
    "chat.attachmentLimitsRows": "Max rows read",
    "chat.attachmentLimitsCols": "Max columns kept",
    "chat.attachmentLimitsCellChars": "Max chars per cell",
    "chat.attachmentLimitsMaxSheets": "Max Excel sheets",
    "chat.attachmentLimitsLargePreviewRows": "Large-table preview rows",
    "chat.attachmentLimitsToolEnabled": "Enable large-table tool mode",
    "chat.attachmentLimitsToolMinRows": "Min rows to trigger tool mode",
    "chat.attachmentLimitsToolMaxBytes": "Max file bytes for tool mode",
    "chat.attachmentLimitsSqlTimeoutMs": "SQL timeout (ms)",
    "chat.attachmentLimitsReset": "Reset defaults",
    "chat.attachmentLimitsCancel": "Cancel",
    "chat.attachmentLimitsSave": "Save",
    "chat.attachmentLimitsInvalidNumber": "Please enter valid positive integers",
    "chat.attachmentLimitsHighPreviewWarn": "Large-table preview rows is above 200, which may significantly increase token usage. Continue?",
    "chat.activeModelLabel": "Model",
    "chat.execApplied": "Applied: {mode} / {specialist}",
    "chat.dynamicStats": "Dynamic experts (recent): hit {dynamic}, fallback {fallback}",
    "chat.dynamicStatsDetail": "Hit rate {rate}% · Top reason {reason}",
    "chat.dynamicTopReasons": "Reason mix {items}",
    "chat.dynamicAllReasons": "View full mix",
    "chat.dynamicAllReasonsTitle": "Full reason mix",
    "chat.dispatchLabelsEdit": "Edit reason labels",
    "chat.dispatchLabelsPrompt": "Edit dispatch reason override JSON (empty to clear)",
    "chat.dispatchLabelsSaved": "Reason labels updated",
    "chat.dispatchLabelsTitle": "Edit reason label overrides",
    "chat.dispatchLabelsSave": "Save",
    "chat.dispatchLabelsClear": "Clear",
    "chat.dispatchLabelsCancel": "Cancel",
    "chat.dispatchLabelsInvalidJson": "Invalid JSON format",
    "chat.dispatchLabelsEffectivePreview": "Effective preview",
    "chat.dispatchLabelsDiffOnly": "Show changed only",
    "chat.dispatchLabelsExport": "Export effective",
    "chat.dispatchLabelsImport": "Import JSON",
    "chat.dispatchLabelsRestoreDefaults": "Restore defaults template",
    "chat.dispatchLabelsUnsavedConfirm": "You have unsaved changes. Close anyway?",
    "chat.reason.manager_no_specialist_fallback": "No specialist; fallback to generalist",
    "chat.reason.dynamic_agent_build_failed": "Dynamic agent build failed",
    "chat.reason.manager_factory_failed": "Specialist executor factory failed",
    "chat.reason.manager_route_missing": "Manager route missing",
    "chat.reason.manager_select_failed": "Manager selection failed",
    "chat.reason.manager_model_missing": "Manager model missing",
    "chat.reason.dynamic_agent_selected": "Dynamic agent selected",
    "chat.modeComprehensiveShort": "Comprehensive",
    "chat.modeExpertShort": "Expert",
    "chat.specialistGeneralistShort": "Generalist",
    "chat.specialistOpsShort": "Ops",
    "chat.specialistImageShort": "Image",
    "chat.specialistMemoryShort": "Memory",
    "chat.specialistManagerSelfShort": "Manager",
    "chat.attachment.download": "Download",
    "chat.attachment.preview": "Preview",
    "chat.attachment.previewLoading": "Loading…",
    "chat.attachment.previewError": "Preview failed",
    "chat.attachment.previewEmpty": "(empty)",
    "chat.attachmentAcl": "Attachment ACL",
    "chat.attachmentAclBackfill": "Backfill ACL",
    "chat.attachmentAclBackfillPrompt": "Backfill attachment_acl by scanning historical message attachments? Recommended during off-peak hours.",
    "chat.attachmentAclBackfillOk": "Backfill done: inserted {inserted} rows (scanned {scanned_messages} messages)",
    "chat.attachmentAclBackfillFail": "Backfill failed: {error}",
  },
};

const LANG_KEY = "ops_admin_lang";
let currentLang = (localStorage.getItem(LANG_KEY) || "zh").toLowerCase();
if (!I18N[currentLang]) currentLang = "zh";
/** Chat standalone: separate keys from /admin so two accounts can stay signed in on the same origin. */
const AUTH_TOKEN_KEY = "ops_chat_token";
const AUTH_SESSION_KEY = "ops_chat_session";
/** 与 URL 中 ?session_id= 联动：切换登录用户后丢弃旧 session，避免误开上一账号的链接会话 */
const CHAT_URL_SCOPE_KEY = "ops_chat_url_scope";
const CHAT_SPECIALIST_PREF_KEY = "ops_chat_specialist_pref";
const CHAT_INTERACTION_MODE_KEY = "ops_chat_interaction_mode";
const CHAT_MEMORY_MODE_KEY = "ops_chat_memory_mode";
const CHAT_REASONING_TOGGLE_KEY = "ops_chat_reasoning_toggle";
const ADMIN_CHAT_SHOW_TOOL_OUTPUT_DEFAULT = false;
const REASONING_BLOCK_MAX_CHARS = 12000;
const CHAT_ENABLE_WIKI_EVENT_POLLER = false;
const _rt = String(localStorage.getItem(CHAT_REASONING_TOGGLE_KEY) || "").trim().toLowerCase();
let adminChatShowToolOutput = _rt
  ? ["1", "true", "yes", "on"].includes(_rt)
  : ADMIN_CHAT_SHOW_TOOL_OUTPUT_DEFAULT;
let authSession = null;

function _toolSummaryTitle(role) {
  const r = String(role || "").toLowerCase();
  if (r === "tool" || r === "function") return "工具结果";
  return "工具调用";
}

function _normalizeEventType(v) {
  return String(v || "").trim().toLowerCase();
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
    btn.textContent = currentLang === "zh" ? "展开全文（可能较慢）" : "Load full text (may be slow)";
    btn.addEventListener("click", () => {
      btn.disabled = true;
      btn.textContent = currentLang === "zh" ? "加载中..." : "Loading...";
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
  const sourceText = adminChatShowToolOutput
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
      if (!adminChatShowToolOutput) continue;
      if (Array.isArray(collapsedItems)) {
        collapsedItems.push({ title: t("reasoning.summary"), text: seg.text || "—" });
      } else {
        _appendCollapsedBundle(inner, [{ title: t("reasoning.summary"), text: seg.text || "—" }]);
      }
    }
  }
}

async function _buildAggregatedAssistantBubble(tsIso, items) {
  const inner = el("div", { class: "chat-msg chat-msg--assistant chat-msg--rich" });
  const collapsedItems = [];
  const _inlineImageHtmlFromAttachments = (raw) => {
    const list = parseAttachments(raw);
    if (!Array.isArray(list) || !list.length) return "";
    const blocks = [];
    for (const att of list) {
      if (!att || typeof att !== "object") continue;
      const typ = String(att.type || "").toLowerCase();
      if (typ === "image" || typ === "input_image") {
        const b64 = String(att.image_base64 || att.data || "").trim();
        if (!b64) continue;
        const mime = String(att.mime || att.mime_type || "image/png").trim() || "image/png";
        const src = `data:${mime};base64,${b64.replace(/\s/g, "")}`;
        blocks.push(`<div class="chat-att-wrap"><img class="chat-att-img" src="${escapeHtml(src)}" alt="tool image" /></div>`);
      } else if (typ === "image_url") {
        const src = String(att.url || att.image_url || "").trim();
        if (!src) continue;
        blocks.push(`<div class="chat-att-wrap"><img class="chat-att-img" src="${escapeHtml(src)}" alt="tool image" /></div>`);
      }
    }
    return blocks.join("");
  };
  for (const it of items || []) {
    const kind = String((it && it.kind) || "");
    const text = String((it && it.text) || "");
    const hasInlineAtt = !!(it && it.attachments);
    if (!text.trim() && !(kind === "tool_result" && hasInlineAtt)) continue;
    if (kind === "assistant_text") {
      _appendAssistantTextSegments(inner, text, collapsedItems);
    } else if (kind === "reasoning") {
      if (adminChatShowToolOutput) collapsedItems.push({ title: t("reasoning.summary"), text });
    } else if (kind === "tool_call") {
      if (adminChatShowToolOutput) collapsedItems.push({ title: _toolSummaryTitle("tool_call"), text });
    } else if (kind === "tool_result") {
      if (adminChatShowToolOutput) collapsedItems.push({ title: _toolSummaryTitle("tool"), text });
      // 支持两类附件：base64（image/input_image）和引用型（image_ref）。
      // image_ref 需要异步拉取 blob，因此改为走 renderAttachmentsEl()。
      const attsEl = await renderAttachmentsEl(it && it.attachments);
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
      if (!agg) {
        agg = {
          role: "assistant",
          content: "",
          timestamp: (m && m.timestamp) != null ? m.timestamp : "",
          attachments: null,
          _items: [],
          _message_ids: [],
        };
      }
      if (m && m.id != null) agg._message_ids.push(m.id);
      if (role === "assistant") {
        if (eventType === "reasoning") {
          if (String(content || "").trim()) {
            agg._items.push({ kind: "reasoning", text: content });
          }
        } else if (String(content || "").trim()) {
          agg._items.push({ kind: "assistant_text", text: content });
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
      } else if (String(content || "").trim()) {
        agg._items.push({ kind: "tool_result", text: content, attachments: m.attachments || null });
        if (m.attachments) agg.attachments = m.attachments;
      }
      continue;
    }
    flush();
    rows.push(m);
  }
  flush();
  return rows;
}

function t(key, vars) {
  let s = (I18N[currentLang] && I18N[currentLang][key]) || (I18N.en && I18N.en[key]) || key;
  if (vars && typeof s === "string") {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}

function interactionModeLabel(mode) {
  const m = String(mode || "").toLowerCase();
  if (m === "expert") return t("chat.modeExpertShort");
  return t("chat.modeComprehensiveShort");
}

function specialistLabel(specialist) {
  const s = String(specialist || "").toLowerCase();
  if (s === "manager") return currentLang === "zh" ? "主控" : "Manager";
  if (s === "manager_self") return t("chat.specialistManagerSelfShort");
  if (s === "ops") return t("chat.specialistOpsShort");
  if (s === "image") return t("chat.specialistImageShort");
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
  host = el("div", {
    class: "chat-toast-host",
    style:
      "position:fixed;right:14px;bottom:14px;z-index:9999;display:flex;flex-direction:column;gap:8px;max-width:420px;pointer-events:none;",
  });
  document.body.appendChild(host);
  return host;
}

function showToast(text, { kind = "info", ttlMs = 4200 } = {}) {
  const host = _ensureToastHost();
  const bg = kind === "error" ? "rgba(160,40,40,0.96)" : "rgba(30,30,30,0.92)";
  const node = el("div", {
    class: "chat-toast",
    text: String(text || ""),
    style:
      `pointer-events:auto;padding:10px 12px;border-radius:10px;color:#fff;box-shadow:0 8px 24px rgba(0,0,0,.35);` +
      `background:${bg};font-size:12.5px;line-height:1.35;white-space:pre-wrap;`,
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

async function openWikiPreviewModal({ sessionId, path }) {
  const sid = String(sessionId || "");
  const p = String(path || "").replace(/\\/g, "/").replace(/^\//, "");
  if (!sid || !p) return;
  const backdrop = el("div", {
    class: "chat-confirm-backdrop",
    style: "z-index:9998;",
  });
  const card = el("div", {
    class: "chat-confirm-card",
    style: "max-width:980px;width:92vw;max-height:78vh;overflow:auto;",
  });
  const title = el("div", { class: "card__title", text: t("chat.wikiPreviewTitle", { path: p }) });
  const closeBtn = el("button", { type: "button", class: "btn", text: t("chat.wikiPreviewClose") });
  const head = el("div", { class: "row", style: "gap:8px;justify-content:space-between;align-items:center;" }, [
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
    style:
      "position:fixed;inset:0;background:rgba(0,0,0,0.35);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;",
  });
  const card = el("div", {
    class: "card",
    style: "width:min(860px,96vw);max-height:86vh;overflow:auto;padding:12px;",
  });
  const title = el("div", { class: "card__title", text: t("chat.dispatchLabelsTitle") });
  const tip = el("div", { class: "muted", text: t("chat.dispatchLabelsPrompt") });
  const err = el("div", { class: "muted", style: "color:#dc2626;" });
  const ta = el("textarea", {
    class: "input",
    style: "width:100%;min-height:320px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;",
  });
  ta.value = initText;
  const previewTitle = el("div", { class: "muted", text: t("chat.dispatchLabelsEffectivePreview") });
  const diffOnlyWrap = el("label", { class: "muted", style: "display:flex;gap:6px;align-items:center;cursor:pointer;" });
  const diffOnlyCb = el("input", { type: "checkbox" });
  diffOnlyWrap.appendChild(diffOnlyCb);
  diffOnlyWrap.appendChild(el("span", { text: t("chat.dispatchLabelsDiffOnly") }));
  const preview = el("textarea", {
    class: "input",
    style:
      "width:100%;min-height:220px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f8fafc;",
    readonly: "readonly",
  });
  const btnSave = el("button", { type: "button", class: "btn btn--primary", text: t("chat.dispatchLabelsSave") });
  const btnClear = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsClear") });
  const btnDefaults = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsRestoreDefaults") });
  const btnExport = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsExport") });
  const btnImport = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsImport") });
  const btnCancel = el("button", { type: "button", class: "btn", text: t("chat.dispatchLabelsCancel") });
  const fileInput = el("input", { type: "file", accept: "application/json,.json", style: "display:none" });
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
  card.appendChild(el("div", { style: "height:8px;" }));
  card.appendChild(ta);
  card.appendChild(el("div", { style: "height:8px;" }));
  card.appendChild(previewTitle);
  card.appendChild(diffOnlyWrap);
  card.appendChild(preview);
  card.appendChild(el("div", { style: "height:8px;" }));
  card.appendChild(err);
  card.appendChild(
    el("div", { class: "row", style: "gap:8px;justify-content:flex-end;margin-top:8px;" }, [
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

function applyI18nStatic() {
  document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    node.textContent = t(key);
  });
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
  authSession = null;
  const u = new URL(window.location.href);
  u.searchParams.delete("force_relogin");
  history.replaceState(null, "", `${u.pathname}${u.search}${u.hash}`);
}

function replaceSessionUrl(sessionId) {
  const path = "/chat";
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  history.replaceState(null, "", path + q);
}

async function apiGet(path) {
  const token = localStorage.getItem(AUTH_TOKEN_KEY) || "";
  const headers = { accept: "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { headers });
  if (res.status === 401) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    authSession = null;
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
  if (res.status === 401) {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    authSession = null;
    setTimeout(() => boot().catch(() => {}), 0);
    return await new Promise(() => {});
  }
  if (!res.ok) throw new Error(`POST ${path} ${res.status}`);
  return await res.json();
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
    authSession = null;
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
    authSession = null;
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
  inner.appendChild(closeBtn);
  inner.appendChild(big);
  backdrop.appendChild(inner);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeChatImageLightbox();
  });
  document.body.appendChild(backdrop);
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

function _findEarliestReasoningBlock(remaining) {
  let best = null;
  for (const re of [RE_REDACTED_THINKING, RE_THINK_TAG]) {
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
  for (const re of [RE_REDACTED_THINKING, RE_THINK_TAG]) {
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
    return `${raw.slice(0, maxChars)}\n\n…（为保证界面性能，已截断 ${raw.length - maxChars} 字符）`;
  };
  const n = String(name || "").trim() || "tool";
  const p = payload && typeof payload === "object" ? payload : {};
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
  const loc = currentLang === "zh" ? "zh-CN" : "en-US";
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

const CHAT_BOT_LOGO_SRC = "/admin/assets/oliver.svg";
/** 内置默认用户头像（与助手头像同尺寸与底栏样式，SVG） */
const DEFAULT_USER_AVATAR_SRC = "/admin/assets/default-user-avatar.svg";

let meProfile = null;

async function loadMeProfile() {
  try {
    const r = await apiGet("/admin/api/chat/profile");
    meProfile = r && r.ok && r.profile ? r.profile : null;
  } catch (_) {
    meProfile = null;
  }
}

function buildBotAvatarImg() {
  return el("img", {
    class: "chat-avatar chat-avatar--bot",
    src: CHAT_BOT_LOGO_SRC,
    alt: "",
    loading: "lazy",
  });
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
  const aid = meProfile && String(meProfile.avatar_attachment_id || "").trim();
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
    r === "assistant" && !adminChatShowToolOutput ? stripReasoningTagsFromText(rawText, { mode: "strict" }) : rawText;
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
        if (adminChatShowToolOutput) collapsedItems.push({ title: t("reasoning.summary"), text: seg.text || "—" });
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
    card.appendChild(el("div", { class: "chat-att-ref__name", text: name }));
    card.appendChild(el("div", { class: "chat-att-ref__meta", text: `${typ} · ${mime}${sizeLabel ? ` · ${sizeLabel}` : ""}` }));
    if (aid) card.appendChild(el("div", { class: "chat-att-ref__meta", text: `id: ${aid.slice(0, 16)}...` }));
    if (aid) {
      const url = await fetchAttachmentBlobUrl(aid);
      if (url) {
        card.appendChild(
          el("a", {
            class: "chat-att-ref__link",
            href: url,
            target: "_blank",
            rel: "noopener noreferrer",
            download: name || undefined,
            text: t("chat.attachment.download"),
          }),
        );
      }
    }
    const canPreviewText = !!aid && (String(typ || "") === "text_ref" || isTextLikeMime(mime));
    if (canPreviewText) {
      const preview = el("button", {
        type: "button",
        class: "chat-att-ref__btn",
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
      card.appendChild(preview);
      card.appendChild(pre);
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
      const img = el("img", { class: "chat-att-img", src, alt: "" });
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
  messagesEl.appendChild(bubble);
  hydrateMermaidIn(bubble);
}

function mount(node) {
  const c = document.getElementById("app");
  c.innerHTML = "";
  c.appendChild(node);
}

function buildChatBrandLogoNode() {
  return el("div", { class: "chat-nav__brandWrap" }, [
    el("img", {
      class: "chat-nav__brandLogo",
      src: "/admin/assets/oliver.svg",
      alt: "oliver logo",
    }),
  ]);
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
  const name = String((authSession && (authSession.display_name || authSession.username || authSession.user_id)) || "");
  const isAdminViewer = String((authSession && authSession.username) || "")
    .trim()
    .toLowerCase() === "administrator";
  if (!name) return;
  const nameBtn = el("button", {
    type: "button",
    class: "chat-sess-btn",
    text: name,
    title: name,
  });
  const moreBtn = el("button", {
    type: "button",
    class: "chat-sess-more",
    text: "⋯",
    title: t("chat.sessionMenu"),
    onclick: (ev) => {
      ev.stopPropagation();
      document.querySelectorAll(".chat-sess-menu-pop").forEach((n) => n.remove());
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
          "data-menu-action": "lang",
          text: t("lang.switch"),
        }),
        el("button", {
          type: "button",
          class: "chat-sess-menu-item",
          "data-menu-action": "dispatchLabels",
          text: t("chat.dispatchLabelsEdit"),
        }),
      ];
      if (isAdminViewer) {
        items.push(el("div", { class: "chat-sess-menu-sep" }));
        items.push(
          el("button", {
            type: "button",
            class: "chat-sess-menu-item",
            "data-menu-action": "attachmentAclBackfill",
            text: t("chat.attachmentAclBackfill"),
          }),
        );
      }
      items.push(el("div", { class: "chat-sess-menu-sep" }));
      items.push(
        el("button", {
          type: "button",
          class: "chat-sess-menu-item",
          "data-menu-action": "logout",
          text: t("auth.logout"),
        }),
      );
      const menu = el("div", { class: "chat-sess-menu-pop", style: "position:fixed;" }, items);
      const rect = moreBtn.getBoundingClientRect();
      menu.style.left = `${Math.min(rect.left, window.innerWidth - 220)}px`;
      menu.style.top = `${Math.max(8, rect.top - 92)}px`;
      document.body.appendChild(menu);
      const close = (e) => {
        if (!menu.contains(e.target)) {
          menu.remove();
          document.removeEventListener("click", close);
        }
      };
      setTimeout(() => document.addEventListener("click", close), 0);
    },
  });
  const row = el("div", { class: "chat-user-row" }, [nameBtn, moreBtn]);
  user.appendChild(row);
}

async function fileToPayloadEntry(file) {
  const buf = await file.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = "";
  for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
  const data_base64 = btoa(binary);
  return { name: file.name || "file", data_base64 };
}

async function renderLogin() {
  applyI18nStatic();
  const username = el("input", { class: "input", placeholder: t("auth.username") });
  const password = el("input", { class: "input", type: "password", placeholder: t("auth.password") });
  const status = el("div", { class: "muted", text: "" });
  const doLogin = async () => {
    const resp = await apiPost("/admin/api/auth/login", {
      tenant_id: "",
      username: username.value.trim().toLowerCase(),
      password: password.value.trim(),
      purpose: "chat",
    });
    if (!resp.ok || !resp.token) {
      const err = String(resp.error || "");
      status.textContent =
        err === "user_disabled"
          ? t("auth.disabled")
          : err === "admin_role_required"
            ? t("auth.chatLoginDenied")
            : t("auth.invalid");
      return;
    }
    localStorage.setItem(AUTH_TOKEN_KEY, String(resp.token));
    localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(resp.session || {}));
    authSession = resp.session || null;
    await boot();
  };
  const onEnterLogin = (ev) => {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    doLogin();
  };
  username.addEventListener("keydown", onEnterLogin);
  password.addEventListener("keydown", onEnterLogin);
  const btn = el("button", {
    class: "btn btn--primary",
    text: t("auth.login"),
    onclick: doLogin,
  });
  const card = el("div", { class: "card", style: "max-width:440px;width:100%" }, [
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

let _statusReasonPairs = [];

async function renderChatUi() {
  let sessionId = getSessionIdFromUrl();
  try {
    const curScope = JSON.stringify({
      t: String((authSession && authSession.tenant_id) || ""),
      u: String((authSession && authSession.user_id) || ""),
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
  const fileInput = el("input", { type: "file", multiple: "multiple", style: "display:none", accept: "*/*" });
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
  const toolToggleCb = el("input", { type: "checkbox", class: "switch-input" });
  const toolToggleWrap = el("label", { class: "switch-wrap", title: t("chat.tools.visible") }, [
    toolToggleCb,
    el("span", { class: "switch-slider" }),
    el("span", { class: "muted", text: t("chat.tools") }),
  ]);
  const MAIN_MODE_VALUE = "comprehensive";
  const EXCLUDED_SPECIALISTS = new Set(["main", "memory", "manager_self", "pycache", "__pycache__"]);
  let specialistCatalog = [];
  const modeSelect = el("select", {
    class: "input",
    style: "min-width:120px;max-width:160px;padding:6px 8px;",
  });
  const modeOptionLabel = (v) => {
    const key = String(v || "").trim().toLowerCase();
    if (key === MAIN_MODE_VALUE) return t("chat.modeComprehensive");
    if (key === "generalist") return t("chat.specialistGeneralist");
    const row = specialistCatalog.find((x) => String(x.id || "").toLowerCase() === key);
    if (!row) return key || t("chat.modeComprehensive");
    const zh = String(row.display_name_zh || "").trim();
    const en = String(row.display_name_en || "").trim();
    return currentLang === "zh" ? (zh || en || key) : (en || zh || key);
  };
  const isSelectableSpecialist = (v) => {
    const key = String(v || "").trim().toLowerCase();
    if (!key || key === MAIN_MODE_VALUE) return false;
    if (key === "generalist") return true;
    return specialistCatalog.some((x) => String(x.id || "").toLowerCase() === key);
  };
  const persistModeSelection = () => {
    const v = String(modeSelect.value || MAIN_MODE_VALUE).toLowerCase();
    localStorage.setItem(CHAT_INTERACTION_MODE_KEY, v);
    if (v !== MAIN_MODE_VALUE) localStorage.setItem(CHAT_SPECIALIST_PREF_KEY, v);
  };
  const applyModeOptions = () => {
    const prev = String(modeSelect.value || localStorage.getItem(CHAT_INTERACTION_MODE_KEY) || MAIN_MODE_VALUE).toLowerCase();
    modeSelect.innerHTML = "";
    modeSelect.appendChild(el("option", { value: MAIN_MODE_VALUE, text: modeOptionLabel(MAIN_MODE_VALUE) }));
    modeSelect.appendChild(el("option", { value: "generalist", text: modeOptionLabel("generalist") }));
    specialistCatalog.forEach((x) => {
      const sid = String(x.id || "").toLowerCase();
      if (!sid || sid === "generalist") return;
      modeSelect.appendChild(el("option", { value: sid, text: modeOptionLabel(sid) }));
    });
    if (Array.from(modeSelect.options).some((o) => String(o.value || "") === prev)) modeSelect.value = prev;
    else modeSelect.value = MAIN_MODE_VALUE;
  };
  const _im = String(localStorage.getItem(CHAT_INTERACTION_MODE_KEY) || MAIN_MODE_VALUE).toLowerCase();
  modeSelect.value = _im;
  const _mm = String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default").toLowerCase();
  localStorage.setItem(CHAT_MEMORY_MODE_KEY, _mm === "store_only" ? "store_only" : "default");
  modeSelect.addEventListener("change", () => {
    persistModeSelection();
    saveSessionModePreference();
  });
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
  const refreshActiveModelText = async () => {
    try {
      const ms = await apiGet("/admin/api/models");
      const profiles = Array.isArray(ms.profiles) ? ms.profiles : [];
      const aid = String(ms.active_llm_profile_id || "");
      const p = profiles.find((x) => String(x.id || "") === aid) || null;
      const modelName = String((p && p.model) || "").trim() || "-";
      activeModelText.textContent = `${t("chat.activeModelLabel")}: ${modelName}`;
    } catch (_) {
      activeModelText.textContent = `${t("chat.activeModelLabel")}: -`;
    }
  };
  const loadSessionModePreference = async () => {
    if (!activeId) return;
    try {
      const resp = await apiGet(`/admin/api/chat/sessions/${encodeURIComponent(activeId)}/mode`);
      const m = String((resp && resp.interaction_mode) || "").toLowerCase();
      const s = String((resp && resp.specialist) || "").toLowerCase();
      const mm = String((resp && resp.memory_mode) || "").toLowerCase();
      if (m === "comprehensive") modeSelect.value = MAIN_MODE_VALUE;
      else if (m === "expert" && isSelectableSpecialist(s)) modeSelect.value = s;
      if (["default", "store_only"].includes(mm)) localStorage.setItem(CHAT_MEMORY_MODE_KEY, mm);
      persistModeSelection();
      const mml = String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default").toLowerCase();
      localStorage.setItem(CHAT_MEMORY_MODE_KEY, mml === "store_only" ? "store_only" : "default");
    } catch (_) {}
  };
  const saveSessionModePreference = async () => {
    if (!activeId) return;
    try {
      const modeVal = String(modeSelect.value || MAIN_MODE_VALUE).toLowerCase();
      const isMain = modeVal === MAIN_MODE_VALUE;
      await apiPost(`/admin/api/chat/sessions/${encodeURIComponent(activeId)}/mode`, {
        interaction_mode: isMain ? "comprehensive" : "expert",
        specialist: isMain ? "generalist" : modeVal,
        memory_mode: String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default"),
      });
    } catch (_) {}
  };
  await refreshActiveModelText();
  const composerMetaBar = el("div", { class: "row", style: "gap:8px;padding:2px 4px 6px;align-items:center;" }, [
    el("span", { class: "muted", text: t("chat.modeLabel") }),
    modeSelect,
    toolToggleWrap,
    el("button", {
      type: "button",
      class: "btn",
      style: "padding:4px 8px;min-height:auto;font-size:12px;",
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
    }),
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
  let showToolOutput = adminChatShowToolOutput;
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
      card.appendChild(el("div", { class: "row", style: "gap:8px;justify-content:flex-end;margin-top:10px;" }, [btnCancel, btnOk]));
      backdrop.appendChild(card);
      document.body.appendChild(backdrop);
    });
  const promptChatText = (message, initialValue = "") =>
    new Promise((resolve) => {
      const backdrop = el("div", { class: "chat-confirm-backdrop" });
      const card = el("div", { class: "chat-confirm-card" });
      const text = el("div", { class: "chat-confirm-text", text: String(message || "") });
      const input = el("input", {
        class: "input",
        type: "text",
        value: String(initialValue || ""),
        style: "width:100%;margin-top:10px;",
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
      card.appendChild(el("div", { class: "row", style: "gap:8px;justify-content:flex-end;margin-top:10px;" }, [btnCancel, btnOk]));
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
            const btnRow = el("div", { class: "row", style: "gap:8px;flex-wrap:wrap;margin-top:8px;" });
            for (const a of acts) {
              btnRow.appendChild(
                el("button", {
                  type: "button",
                  class: "btn",
                  style: "padding:4px 8px;min-height:auto;font-size:12px;",
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
          title: currentLang === "zh" ? "移除" : "Remove",
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
  const syncToolToggleBtn = () => {
    toolToggleCb.checked = !!showToolOutput;
    toolToggleWrap.title = showToolOutput ? t("chat.tools.visible") : t("chat.tools.hidden");
  };
  toolToggleCb.addEventListener("change", () => {
    showToolOutput = !!toolToggleCb.checked;
    adminChatShowToolOutput = showToolOutput;
    localStorage.setItem(CHAT_REASONING_TOGGLE_KEY, showToolOutput ? "1" : "0");
    syncToolToggleBtn();
    const isStreaming = composerShell.classList.contains("chat-composer-shell--busy");
    if (isStreaming) {
      // Avoid clearing active stream bubble mid-turn (loadMessagesForActive() resets messagesEl).
      statusBar.textContent = `${showToolOutput ? t("chat.tools.visible") : t("chat.tools.hidden")} · ${
        currentLang === "zh" ? "本轮结束后应用到历史消息" : "applies to history after current turn"
      }`;
      return;
    }
    statusBar.textContent = showToolOutput ? t("chat.tools.visible") : t("chat.tools.hidden");
    loadMessagesForActive().catch(() => {});
  });
  syncToolToggleBtn();
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
        el("div", { class: "muted", style: "padding:10px 0 10px 8px", text: t("chat.noSessions") }),
      );
      return;
    }
    for (const s of sessions) {
      const sid = String(s.id || "");
      const title = String(s.title || sid || "");
      const row = el("div", { class: "chat-sess-row" + (idsMatch(activeId, sid) ? " chat-sess-row--active" : "") });
      const btn = el("button", {
        class: "chat-sess-btn" + (idsMatch(activeId, sid) ? " chat-sess-btn--active" : ""),
        text: title,
        onclick: () => {
          activeId = sid;
          replaceSessionUrl(sid);
          paintSessions();
          Promise.all([loadMessagesForActive(), loadSessionModePreference()]).catch((e) => {
            statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
          });
          startWikiPoller();
        },
      });
      const more = el("button", {
        type: "button",
        class: "chat-sess-more" + (idsMatch(activeId, sid) ? " chat-sess-more--active" : ""),
        text: "⋯",
        title: t("chat.sessionMenu"),
        onclick: (ev) => {
          ev.stopPropagation();
          document.querySelectorAll(".chat-sess-menu-pop").forEach((n) => n.remove());
          const menu = openSessionMenu(sid, title);
          const rect = more.getBoundingClientRect();
          menu.style.position = "fixed";
          document.body.appendChild(menu);
          // Clamp into viewport; flip above if near bottom.
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
          const close = (e) => {
            if (!menu.contains(e.target)) {
              menu.remove();
              document.removeEventListener("click", close);
            }
          };
          setTimeout(() => document.addEventListener("click", close), 0);
        },
      });
      row.appendChild(btn);
      row.appendChild(more);
      sessionsListEl.appendChild(row);
    }
    if (sessions.length < sessionTotal) {
      const lm = el("button", {
        class: "btn",
        style: "width:100%;margin-top:8px",
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

  const loadMessagesForActive = async () => {
    loadMessagesForActive._rid = (loadMessagesForActive._rid || 0) + 1;
    const rid = loadMessagesForActive._rid;
    shouldFollowMessages = true;
    if (!activeId) {
      messagesEl.innerHTML = "";
      statusBar.textContent = sessions.length ? "" : t("chat.noSessions");
      if (!sessions.length) messagesEl.appendChild(el("div", { class: "muted", text: t("chat.empty") }));
      return;
    }
    statusBar.textContent = t("chat.loading");
    try {
      const resp = await apiGet(`/admin/api/chat/sessions/${encodeURIComponent(activeId)}/messages`);
      if (rid !== loadMessagesForActive._rid) return;
      const msgs = Array.isArray(resp.messages) ? resp.messages : [];
      const renderRows = _buildRenderRows(msgs);
      const total = intOr(resp.message_count, msgs.length);
      messagesEl.innerHTML = "";
      if (total > msgs.length) {
        messagesEl.appendChild(
          el("div", {
            class: "muted chat-msg-cap",
            text: t("chat.historyTruncated", { shown: msgs.length, total }),
          }),
        );
      }
      if (!renderRows.length) {
        messagesEl.appendChild(el("div", { class: "muted", text: t("chat.empty") }));
      } else {
        for (const m of renderRows) {
          await appendMessageRow(messagesEl, m, rowRenderOptions);
        }
      }
      statusBar.textContent = "";
      scrollMessagesToBottom(true);
    } catch (e) {
      // Keep existing message list on reload failure (e.g. toggle reload races),
      // so users don't perceive "messages disappeared".
      statusBar.textContent = `${t("chat.error")}: ${String(e)}`;
    }
  };

  const reloadSessionsOnly = async () => {
    const resp = await apiGet(`/admin/api/chat/sessions?limit=${PAGE_SIZE}&offset=0`);
    sessions = Array.isArray(resp.sessions) ? resp.sessions : [];
    sessionTotal = intOr(resp.total, sessions.length);
    paintSessions();
  };

  const refreshSessions = async () => {
    statusBar.textContent = t("chat.loading");
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
    async sendSessionSend({ sessionId, text, attachments, interactionMode, specialist, memoryMode, idempotencyKey, signal, onEvent }) {
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
    if (!("content" in m) && !("text" in m)) return null;
    return m;
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
      const resp = await apiGet(`/admin/api/chat/sessions/${encodeURIComponent(activeId)}/messages`);
      const msgs = Array.isArray(resp && resp.messages) ? resp.messages : [];
      if (!msgs.length) return false;
      let last = null;
      for (let i = msgs.length - 1; i >= 0; i--) {
        const m = msgs[i];
        if (String((m && m.role) || "").toLowerCase() !== "assistant") continue;
        // Recovery should only accept visible assistant body, not intermediate
        // reasoning/tool-call events; otherwise we may terminate on a partial line.
        const et = String((m && m.event_type) || "").trim().toLowerCase();
        if (et && et !== "assistant_text" && et !== "assistant") continue;
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
            if (!showToolOutput && !images.length) continue;
            flushTextBuf();
            const audit = seg.sqlAudit && typeof seg.sqlAudit === "object" ? seg.sqlAudit : null;
            if (showToolOutput) {
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
      const liveTag = currentLang === "zh" ? "[实时全量]" : "[LIVE FULL]";
      const key = `${name}:${++toolSeq}`;
      const rawPayload = p.payload != null ? p.payload : p;
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
      chatStreamSegments.push({ type: "tool", key, title: `${name} ${liveTag}`, body, sqlAudit, images });
    };
    const appendFinalAssistant = async (message, fallbackText) => {
      const normalized = _normalizeAssistantMessage(message, { requireRole: false, requireContentArray: false });
      if (normalized && !_isSilentReplyStream(extractWsAssistantText(normalized))) {
        const norm = {
          ...normalized,
          role: "assistant",
          content: extractWsAssistantText(normalized),
          timestamp: normalized.timestamp != null ? normalized.timestamp : new Date().toISOString(),
          tool_calls: normalized.tool_calls != null ? normalized.tool_calls : normalized.toolCalls,
        };
        const rows = _buildRenderRows([norm]);
        const last = rows && rows.length ? rows[rows.length - 1] : null;
        if (last) {
          if (streamRow && streamRow.parentNode) streamRow.remove();
          await appendMessageRow(messagesEl, last, rowRenderOptions);
          scrollMessagesToBottom(true);
          return true;
        }
      }
      const t0 = String(fallbackText || "").trim();
      if (t0 && !_isSilentReplyStream(t0)) {
        if (streamRow && streamRow.parentNode) streamRow.remove();
        await appendMessageRow(messagesEl, {
          role: "assistant",
          content: decodeEscapedNewlines(t0),
          timestamp: new Date().toISOString(),
        }, rowRenderOptions);
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
          interactionMode: String(modeSelect.value || MAIN_MODE_VALUE).toLowerCase() === MAIN_MODE_VALUE ? "comprehensive" : "expert",
          idempotencyKey: String(turnId || ""),
          specialist: String(modeSelect.value || MAIN_MODE_VALUE).toLowerCase() === MAIN_MODE_VALUE
            ? "generalist"
            : (isSelectableSpecialist(String(modeSelect.value || "").toLowerCase())
              ? String(modeSelect.value || "generalist").toLowerCase()
              : "generalist"),
          memoryMode: String(localStorage.getItem(CHAT_MEMORY_MODE_KEY) || "default"),
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
              } else if (sawStreamToolRefAttachments) {
                // Streaming UI cannot render image_ref/relay_pointer; recover from persisted history so images appear
                // without requiring a manual refresh.
                try {
                  if (streamRow && streamRow.parentNode) streamRow.remove();
                } catch (_) {}
                await loadMessagesForActive();
                scrollMessagesToBottom(true);
                ok = true;
              } else {
                ok = await appendFinalAssistant(payload.message, chatStream || extractWsAssistantText(payload.message || {}));
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
                  currentLang === "zh"
                    ? "请求超时，已从历史补齐本轮结果。"
                    : "Request timed out; recovered this turn from history.";
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
                currentLang === "zh"
                  ? "WS流式中断，已从历史补齐本轮结果。"
                  : "WS stream interrupted; recovered this turn from history.";
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
    if (filesSnapshot.length) {
      statusBar.textContent = currentLang === "zh" ? "准备附件中…" : "Preparing attachments…";
      attPayload = await Promise.all(filesSnapshot.map((f) => fileToPayloadEntry(f)));
      pendingFiles = [];
      syncPendingUi();
    }
    const userText =
      textRaw ||
      (hasFiles ? (currentLang === "zh" ? "（已上传附件）" : "(attachment uploaded)") : "");
    /** 发送过程中用本地 blob 预览，避免只显示文件名直到回合结束再拉历史 */
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
      const turnId = `idem_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
      statusBar.textContent = currentLang === "zh" ? "连接中…" : "Connecting…";
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
          ? ` · 阶段(A→G:${Number.isFinite(segA2G) ? `${segA2G}ms` : "-"} / G→M:${Number.isFinite(segG2M) ? `${segG2M}ms` : "-"} / M→F:${Number.isFinite(segM2F) ? `${segM2F}ms` : "-"})` +
            `${Number.isFinite(ttftTotal) ? ` · TTFT=${ttftTotal}ms` : ""}`
          : "";
      const phaseText =
        Number.isFinite(localStartToRunning)
          ? (() => {
              return Number.isFinite(localRunningToFirst)
                ? ` · 阶段耗时(启动→执行)=${localStartToRunning}ms (执行→首字)=${localRunningToFirst}ms`
                : ` · 阶段耗时(启动→执行)=${localStartToRunning}ms`;
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
        _statusReasonPairs = pairs.slice();
        const top5 = pairs
          .slice(0, 5)
          .map(([k, n]) => `${String((stats.reasonLabels && stats.reasonLabels[k]) || reasonLabel(k))}:${n}`)
          .join(", ");
        const ratePct = Math.round((Number(stats.rate || 0) * 1000)) / 10;
        const topReasonLabel = String((stats.reasonLabels && stats.reasonLabels[topReason]) || reasonLabel(topReason));
        const topReasonText = t("chat.dynamicStatsDetail", { rate: ratePct, reason: topReasonLabel });
        const topMixText = t("chat.dynamicTopReasons", { items: top5 || "-" });
        statusBar.textContent = `${baseText}${memoryText}${routeText}${markerText}${ttftText}${phaseText} · ${t("chat.dynamicStats", { dynamic: stats.dynamic, fallback: stats.fallback })} · ${topReasonText} · ${topMixText} · ${t("chat.dynamicAllReasons")}${transportTag ? ` · transport=${transportTag}` : ""}`;
      } else {
        _statusReasonPairs = [];
      statusBar.textContent = `${baseText}${memoryText}${routeText}${markerText}${ttftText}${phaseText}${transportTag ? ` · transport=${transportTag}` : ""}`;
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
      el("div", { class: "muted", style: "font-size:12px;line-height:1.2;padding:10px 12px 0;" }, [activeModelText]),
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
  if (!_statusReasonPairs.length) return;
  document.querySelectorAll(".chat-sess-menu-pop").forEach((n) => n.remove());
  const items = _statusReasonPairs.map(([k, n]) => `${reasonLabel(k)}: ${n}`).join("\n");
  const pop = el("div", { class: "chat-sess-menu-pop", style: "position:fixed;max-width:420px;white-space:pre-wrap;line-height:1.4;" }, [
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

async function syncLangFromServer() {
  try {
    const r = await apiGet("/admin/api/chat/settings/ui-lang");
    if (r && r.lang && (r.lang === "zh" || r.lang === "en")) {
      currentLang = r.lang;
      localStorage.setItem(LANG_KEY, currentLang);
    }
  } catch (_) {}
}

async function boot() {
  applyI18nStatic();
  if (forceReloginRequested()) {
    clearAuthAndReloginFlagFromUrl();
  }
  try {
    authSession = JSON.parse(localStorage.getItem(AUTH_SESSION_KEY) || "null");
  } catch (_) {
    authSession = null;
  }
  const tok = String(localStorage.getItem(AUTH_TOKEN_KEY) || "").trim();
  if (!authSession || !tok) {
    // Ensure stale overlays from previous chat UI never block login inputs.
    closeChatImageLightbox();
    document.querySelectorAll(".chat-sess-menu-pop").forEach((n) => n.remove());
    document.body.style.overflow = "";
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_SESSION_KEY);
    authSession = null;
    try {
      await apiPost("/admin/api/auth/bootstrap", {});
    } catch (_) {}
    mount(await renderLogin());
    applyI18nStatic();
    syncAuthUserLabel();
    return;
  }
  await syncLangFromServer();
  await loadMeProfile();
  try {
    mount(await renderChatUi());
  } catch (err) {
    mount(
      el("div", { class: "chat-app--login" }, [
        el("div", { class: "card", style: "max-width:520px;width:100%" }, [
          el("div", { class: "card__title", text: t("common.error") }),
          el("div", { class: "pre", text: String(err) }),
        ]),
      ]),
    );
  }
  applyI18nStatic();
  syncAuthUserLabel();
}

document.body.addEventListener("click", async (e) => {
  const menuBtn = e.target.closest && e.target.closest(".chat-sess-menu-item[data-menu-action]");
  if (menuBtn) {
    const action = String(menuBtn.getAttribute("data-menu-action") || "");
    document.querySelectorAll(".chat-sess-menu-pop").forEach((n) => n.remove());
    if (action === "profile") {
      openAdminFromChat("profile");
      return;
    }
    if (action === "logout") {
      try {
        await apiPost("/admin/api/auth/logout", {});
      } catch (_) {}
      localStorage.removeItem(AUTH_TOKEN_KEY);
      localStorage.removeItem(AUTH_SESSION_KEY);
      try {
        localStorage.removeItem(CHAT_URL_SCOPE_KEY);
      } catch (_) {}
      authSession = null;
      await boot();
      return;
    }
    if (action === "lang") {
      currentLang = currentLang === "zh" ? "en" : "zh";
      localStorage.setItem(LANG_KEY, currentLang);
      try {
        await apiPost("/admin/api/chat/settings/ui-lang", { lang: currentLang });
      } catch (_) {}
      await boot();
      return;
    }
    if (action === "dispatchLabels") {
      const status = document.querySelector(".chat-status");
      await openDispatchLabelsEditor(status);
      return;
    }
    if (action === "attachmentAclBackfill") {
      const status = document.querySelector(".chat-status");
      if (!(await confirmChatAction(t("chat.attachmentAclBackfillPrompt")))) return;
      try {
        const res = await apiPost("/admin/api/chat/admin/attachments/acl/backfill", {});
        const ok = !!(res && (res.ok === true || res.ok === 1));
        if (ok) {
          if (status) status.textContent = t("chat.attachmentAclBackfillOk", res);
        } else {
          const err = String((res && (res.error || res.detail)) || "backfill_failed");
          if (status) status.textContent = t("chat.attachmentAclBackfillFail", { error: err });
        }
      } catch (err) {
        if (status) status.textContent = t("chat.attachmentAclBackfillFail", { error: String(err) });
      }
      return;
    }
  }
  
});

window.addEventListener("popstate", () => {
  if (authSession) boot().catch(() => {});
});

boot().catch((err) => {
  mount(
    el("div", { class: "chat-app--login" }, [
      el("div", { class: "card", style: "max-width:520px;width:100%" }, [
        el("div", { class: "card__title", text: t("common.error") }),
        el("div", { class: "pre", text: String(err) }),
      ]),
    ]),
  );
});
