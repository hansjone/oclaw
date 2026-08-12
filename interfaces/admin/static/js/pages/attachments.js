import { t, el, apiGet, apiPost, renderPageShell, renderSectionCard } from "../core.js";

async function renderAttachments() {
  const status = el("div", { class: "muted", text: "" });
  const hint = el("div", { class: "muted", style: "line-height:1.45;", text: t("attachments.excelPolicyHint") });
  const loadBtn = el("button", { class: "btn", type: "button", text: t("action.refresh") });
  const saveBtn = el("button", { class: "btn btn--primary", type: "button", text: t("attachments.save") });
  const resetBtn = el("button", { class: "btn", type: "button", text: t("attachments.resetDefaults") });

  const rowInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const colInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const cellInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const maxSheetsInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const largePreviewRowsInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const toolEnabledInput = el("input", { type: "checkbox" });
  const toolMinRowsInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const toolMaxBytesInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const sqlTimeoutInput = el("input", { class: "input", type: "number", min: "100", max: "120000", step: "1" });
  const imageReplayCapInput = el("input", { class: "input", type: "number", min: "600", max: "30000", step: "1" });
  const videoReplayCapInput = el("input", { class: "input", type: "number", min: "600", max: "30000", step: "1" });
  const videoTranscriptChunkSizeInput = el("input", { class: "input", type: "number", min: "1", max: "8000", step: "1" });
  const videoTranscriptChunkOverlapInput = el("input", { class: "input", type: "number", min: "1", max: "4000", step: "1" });
  const archiveMaxDepthInput = el("input", { class: "input", type: "number", min: "1", max: "10", step: "1" });
  const archiveMaxFileCountInput = el("input", { class: "input", type: "number", min: "1", max: "20000", step: "1" });
  const archiveMaxEntryBytesInput = el("input", { class: "input", type: "number", min: "1", step: "1" });
  const archiveMaxTotalBytesInput = el("input", { class: "input", type: "number", min: "1", step: "1" });

  const clampTimeout = (raw, fallback = 8000) => {
    const n = parseInt(String(raw ?? "").trim(), 10);
    if (!Number.isFinite(n)) return fallback;
    return Math.max(100, Math.min(120000, n));
  };

  const parsePositiveInt = (v) => {
    const n = parseInt(String(v ?? "").trim(), 10);
    if (!Number.isFinite(n) || n < 1) return null;
    return n;
  };

  const readUiLimits = () => {
    const rows = parsePositiveInt(rowInput.value);
    const cols = parsePositiveInt(colInput.value);
    const chars = parsePositiveInt(cellInput.value);
    const maxSheets = parsePositiveInt(maxSheetsInput.value);
    const previewRows = parsePositiveInt(largePreviewRowsInput.value);
    const minRows = parsePositiveInt(toolMinRowsInput.value);
    const maxBytes = parsePositiveInt(toolMaxBytesInput.value);
    const sqlTimeoutMs = parsePositiveInt(sqlTimeoutInput.value);
    const imageReplayCapChars = parsePositiveInt(imageReplayCapInput.value);
    const videoReplayCapChars = parsePositiveInt(videoReplayCapInput.value);
    const videoTranscriptChunkSize = parsePositiveInt(videoTranscriptChunkSizeInput.value);
    const videoTranscriptChunkOverlap = parsePositiveInt(videoTranscriptChunkOverlapInput.value);
    const archiveMaxDepth = parsePositiveInt(archiveMaxDepthInput.value);
    const archiveMaxFileCount = parsePositiveInt(archiveMaxFileCountInput.value);
    const archiveMaxEntryBytes = parsePositiveInt(archiveMaxEntryBytesInput.value);
    const archiveMaxTotalBytes = parsePositiveInt(archiveMaxTotalBytesInput.value);
    if (
      rows === null ||
      cols === null ||
      chars === null ||
      maxSheets === null ||
      previewRows === null ||
      minRows === null ||
      maxBytes === null ||
      sqlTimeoutMs === null ||
      imageReplayCapChars === null ||
      videoReplayCapChars === null ||
      videoTranscriptChunkSize === null ||
      videoTranscriptChunkOverlap === null ||
      archiveMaxDepth === null ||
      archiveMaxFileCount === null ||
      archiveMaxEntryBytes === null ||
      archiveMaxTotalBytes === null
    ) {
      throw new Error(t("attachments.invalidNumber"));
    }
    if (previewRows > 200 && !window.confirm(t("attachments.highPreviewWarn"))) {
      throw new Error("cancelled");
    }
    return {
      max_rows_read: rows,
      max_columns: cols,
      max_cell_chars: chars,
      max_excel_sheets: maxSheets,
      large_table_preview_rows: previewRows,
      tool_mode_enabled: !!toolEnabledInput.checked,
      tool_mode_min_rows: minRows,
      tool_mode_max_bytes: maxBytes,
      sql_timeout_ms: clampTimeout(sqlTimeoutMs, 8000),
      image_result_replay_cap_chars: Math.max(600, Math.min(30000, imageReplayCapChars)),
      video_result_replay_cap_chars: Math.max(600, Math.min(30000, videoReplayCapChars)),
      video_transcript_chunk_size: Math.max(1, Math.min(8000, videoTranscriptChunkSize)),
      video_transcript_chunk_overlap: Math.max(1, Math.min(4000, videoTranscriptChunkOverlap)),
      archive_max_depth: Math.max(1, Math.min(10, archiveMaxDepth)),
      archive_max_file_count: Math.max(1, Math.min(20000, archiveMaxFileCount)),
      archive_max_entry_bytes: Math.max(1, archiveMaxEntryBytes),
      archive_max_total_uncompressed_bytes: Math.max(1, archiveMaxTotalBytes),
    };
  };

  const applyUiLimits = (limits) => {
    const l = limits && typeof limits === "object" ? limits : {};
    rowInput.value = String(l.max_rows_read || 5000);
    colInput.value = String(l.max_columns || 200);
    cellInput.value = String(l.max_cell_chars || 500);
    maxSheetsInput.value = String(l.max_excel_sheets || 50);
    largePreviewRowsInput.value = String(l.large_table_preview_rows || 20);
    toolEnabledInput.checked = !!l.tool_mode_enabled;
    toolMinRowsInput.value = String(l.tool_mode_min_rows || 5000);
    toolMaxBytesInput.value = String(l.tool_mode_max_bytes || 31457280);
    sqlTimeoutInput.value = String(clampTimeout(l.sql_timeout_ms, 8000));
    imageReplayCapInput.value = String(Math.max(600, Math.min(30000, parsePositiveInt(l.image_result_replay_cap_chars) || 4000)));
    videoReplayCapInput.value = String(Math.max(600, Math.min(30000, parsePositiveInt(l.video_result_replay_cap_chars) || 4000)));
    videoTranscriptChunkSizeInput.value = String(Math.max(1, Math.min(8000, parsePositiveInt(l.video_transcript_chunk_size) || 1600)));
    videoTranscriptChunkOverlapInput.value = String(Math.max(1, Math.min(4000, parsePositiveInt(l.video_transcript_chunk_overlap) || 200)));
    archiveMaxDepthInput.value = String(Math.max(1, Math.min(10, parsePositiveInt(l.archive_max_depth) || 2)));
    archiveMaxFileCountInput.value = String(Math.max(1, Math.min(20000, parsePositiveInt(l.archive_max_file_count) || 200)));
    archiveMaxEntryBytesInput.value = String(Math.max(1, parsePositiveInt(l.archive_max_entry_bytes) || 10485760));
    archiveMaxTotalBytesInput.value = String(Math.max(1, parsePositiveInt(l.archive_max_total_uncompressed_bytes) || 52428800));
  };

  const load = async () => {
    status.textContent = t("chat.loading");
    try {
      const r = await apiGet("/admin/api/chat/settings/attachment-limits");
      const limits = r && typeof r.limits === "object" ? r.limits : {};
      applyUiLimits(limits);
      status.textContent = "";
    } catch (_) {
      status.textContent = t("attachments.loadError");
    }
  };

  const save = async () => {
    status.textContent = t("chat.sending");
    try {
      const next = readUiLimits();
      await apiPost("/admin/api/chat/settings/attachment-limits", { limits: next });
      status.textContent = t("attachments.saved");
      setTimeout(() => {
        if (status.textContent === t("attachments.saved")) status.textContent = "";
      }, 1500);
    } catch (e) {
      if (String(e && e.message ? e.message : e) === "cancelled") {
        status.textContent = "";
        return;
      }
      status.textContent = `${t("common.error")}: ${String(e)}`;
    }
  };

  const reset = async () => {
    status.textContent = t("chat.sending");
    try {
      const resp = await apiPost("/admin/api/chat/settings/attachment-limits", { limits: null });
      const limits = resp && typeof resp.limits === "object" ? resp.limits : {};
      applyUiLimits(limits);
      status.textContent = t("attachments.saved");
      setTimeout(() => {
        if (status.textContent === t("attachments.saved")) status.textContent = "";
      }, 1500);
    } catch (e) {
      status.textContent = `${t("common.error")}: ${String(e)}`;
    }
  };

  loadBtn.addEventListener("click", load);
  saveBtn.addEventListener("click", save);
  resetBtn.addEventListener("click", reset);
  await load();

  const inputRow = (labelText, inputEl) =>
    el("div", { style: "display:grid;gap:6px;margin-top:8px;" }, [
      el("div", { class: "muted", text: labelText }),
      inputEl,
    ]);

  return renderPageShell({
    title: t("attachments.title"),
    subtitle: t("attachments.subtitle"),
    actions: [loadBtn, resetBtn, saveBtn],
    sections: [
      { id: "attach-overview", label: t("attachments.toc.overview") },
      { id: "attach-table", label: t("attachments.toc.table") },
      { id: "attach-media", label: t("attachments.toc.media") },
      { id: "attach-archive", label: t("attachments.toc.archive") },
    ],
  }, [
    renderSectionCard(t("attachments.card.policy"), t("attachments.excelPolicy"), [hint], { id: "attach-overview" }),
    el("div", { class: "page-grid page-grid--two" }, [
      renderSectionCard(t("attachments.card.tableMode"), "", [
        inputRow(t("attachments.maxRowsRead"), rowInput),
        inputRow(t("attachments.maxColumns"), colInput),
        inputRow(t("attachments.maxCellChars"), cellInput),
        inputRow(t("attachments.maxExcelSheets"), maxSheetsInput),
        inputRow(t("attachments.largePreviewRows"), largePreviewRowsInput),
        el("label", { class: "muted", style: "display:flex;gap:8px;align-items:center;margin-top:10px;cursor:pointer;" }, [
          toolEnabledInput,
          el("span", { text: t("attachments.toolModeEnabled") }),
        ]),
        inputRow(t("attachments.toolModeMinRows"), toolMinRowsInput),
        inputRow(t("attachments.toolModeMaxBytes"), toolMaxBytesInput),
        inputRow(t("attachments.sqlTimeoutMs"), sqlTimeoutInput),
        el("div", { class: "muted u-muted-block", text: t("attachments.sqlTimeoutHint") }),
      ], { id: "attach-table" }),
      renderSectionCard(t("attachments.card.media"), "", [
        inputRow(t("attachments.imageReplayCapChars"), imageReplayCapInput),
        el("div", { class: "muted u-muted-block", text: t("attachments.imageReplayCapHint") }),
        inputRow(t("attachments.videoReplayCapChars"), videoReplayCapInput),
        el("div", { class: "muted u-muted-block", text: t("attachments.videoReplayCapHint") }),
        inputRow(t("attachments.videoTranscriptChunkSize"), videoTranscriptChunkSizeInput),
        inputRow(t("attachments.videoTranscriptChunkOverlap"), videoTranscriptChunkOverlapInput),
        el("div", { class: "muted u-muted-block", text: t("attachments.videoTranscriptChunkHint") }),
      ], { id: "attach-media" }),
    ]),
    renderSectionCard(t("attachments.card.archive"), "", [
      inputRow(t("attachments.archiveMaxDepth"), archiveMaxDepthInput),
      inputRow(t("attachments.archiveMaxFileCount"), archiveMaxFileCountInput),
      inputRow(t("attachments.archiveMaxEntryBytes"), archiveMaxEntryBytesInput),
      inputRow(t("attachments.archiveMaxTotalBytes"), archiveMaxTotalBytesInput),
      el("div", { class: "muted u-muted-block", text: t("attachments.archivePolicyHint") }),
      el("div", { class: "u-h-8" }),
      status,
    ], { id: "attach-archive" }),
  ]);
}


export { renderAttachments };
