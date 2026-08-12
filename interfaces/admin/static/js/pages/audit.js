import { t, el, tdCell, apiGet, formatIds, yesNo } from "../core.js";

async function renderAudit(initialSessionId = "") {
  const input = el("input", { class: "input", placeholder: t("audit.sessionIdPlaceholder") });
  const resultWrap = el("div");
  let selectedTraceId = "";
  const onlyFailures = el("input", { type: "checkbox" });
  const formatTracePayload = (row) => {
    const et = String((row && row.event_type) || "");
    const p = (row && typeof row.payload === "object" && row.payload) ? row.payload : {};
    if (et === "tool_wire_filter") {
      const before = Number(p.tools_before || 0);
      const after = Number(p.tools_after || 0);
      const hidden = Number(p.hidden_total || 0);
      const hiddenMcp = Number(p.hidden_mcp_total || 0);
      const preview = Array.isArray(p.hidden_mcp_preview) ? p.hidden_mcp_preview.slice(0, 8).join(", ") : "";
      const head = `wire_filter before=${before} after=${after} hidden=${hidden} hidden_mcp=${hiddenMcp}`;
      return preview ? `${head} | mcp: ${preview}` : head;
    }
    if (et === "llm_first_token") {
      const ms = Number(p.first_token_ms || 0);
      return `ttft_ms=${ms}`;
    }
    if (et === "memory_retrieval_finished") {
      return `memory short=${Number(p.short_term_count || 0)} semantic=${Number(p.semantic_hit_count || 0)} enabled=${Boolean(p.enabled)}`;
    }
    if (et === "router_decision") {
      return `route mode=${String(p.mode || "")} reason=${String(p.reason || "")}`;
    }
    if (et === "run_started") {
      return `run_started run_id=${String(p.run_id || "")} max_attempts=${Number(p.max_attempts || 0)}`;
    }
    if (et === "attempt_started") {
      return `attempt_started run_id=${String(p.run_id || "")} no=${Number(p.attempt_no || 0)}`;
    }
    if (et === "attempt_finished") {
      return `attempt_finished run_id=${String(p.run_id || "")} no=${Number(p.attempt_no || 0)} status=${String(p.status || "")}`;
    }
    if (et === "run_retry") {
      return `run_retry run_id=${String(p.run_id || "")} next_attempt=${Number(p.next_attempt_no || 0)}`;
    }
    if (et === "run_compact") {
      return `run_compact run_id=${String(p.run_id || "")} count=${Number(p.compact_count || 0)}`;
    }
    if (et === "run_finished") {
      return `run_finished run_id=${String(p.run_id || "")} status=${String(p.status || "")} attempts=${Number(p.attempts || 0)}`;
    }
    if (et === "task_enqueued" || et === "task_claimed" || et === "task_finished" || et === "task_failed") {
      return `${et} task_id=${String(p.task_id || "")} ok=${p.ok === undefined ? "-" : Boolean(p.ok)}`;
    }
    if (et === "turn_stage" && String(p.stage || "") === "finish") {
      const ttft = p.first_token_ms;
      const elapsed = Number(p.turn_elapsed_ms || 0);
      const tools = Number(p.tool_trace_count || 0);
      return `finish ttft_ms=${ttft === null || ttft === undefined ? "-" : Number(ttft)} elapsed_ms=${elapsed} tools=${tools}`;
    }
    return JSON.stringify(p || {});
  };
  const auditColumnDefs = [
    { key: "timestamp", label: t("table.timestamp"), getter: (r) => r.timestamp || "", maxLen: 24 },
    { key: "specialist", label: t("table.specialist"), getter: (r) => r.specialist || "", maxLen: 24 },
    { key: "action", label: t("table.action"), getter: (r) => r.action || "", maxLen: 24 },
    { key: "status", label: t("table.statusText"), getter: (r) => r.status || "", maxLen: 16 },
    { key: "reason", label: t("table.reason"), getter: (r) => r.reason || "", maxLen: 40 },
    { key: "duration", label: t("table.durationMs"), getter: (r) => String(r.duration_ms || ""), maxLen: 20 },
    {
      key: "noOutput",
      label: t("table.noOutputAttachment"),
      getter: (r) => yesNo(((r.payload && typeof r.payload === "object") ? r.payload.no_output_attachment : false)),
      maxLen: 8,
    },
    {
      key: "attachments",
      label: "attachments",
      getter: (r) => {
        const payload = (r && typeof r.payload === "object" && r.payload) ? r.payload : {};
        const routeIds = formatIds(payload.attachment_ids);
        const inIds = formatIds(payload.input_attachment_ids);
        const outIds = formatIds(payload.output_attachment_ids);
        const outUrls = formatIds(payload.output_attachment_urls);
        return [routeIds ? `route:${routeIds}` : "", inIds ? `in:${inIds}` : "", outIds ? `out:${outIds}` : "", outUrls ? `url:${outUrls}` : ""]
          .filter(Boolean)
          .join(" | ") || "-";
      },
      maxLen: 120,
    },
    {
      key: "payload",
      label: t("table.payload"),
      getter: (r) => JSON.stringify(r.payload || {}),
      maxLen: 120,
    },
  ];
  const traceColumnDefs = [
    { key: "timestamp", label: t("table.timestamp"), getter: (r) => r.timestamp || "", maxLen: 24 },
    { key: "eventType", label: t("table.eventType"), getter: (r) => r.event_type || "", maxLen: 28 },
    { key: "traceId", label: t("table.traceId"), getter: (r) => r.trace_id || "", maxLen: 20 },
    { key: "spanId", label: t("table.spanId"), getter: (r) => r.span_id || "", maxLen: 20 },
    { key: "parentSpanId", label: t("table.parentSpanId"), getter: (r) => r.parent_span_id || "", maxLen: 20 },
    {
      key: "errorCode",
      label: "error_code",
      getter: (r) => String((r.payload && r.payload.error_code) || ""),
      maxLen: 32,
    },
    { key: "payload", label: t("table.payload"), getter: (r) => formatTracePayload(r), maxLen: 120 },
  ];
  const auditVisible = new Set(auditColumnDefs.map((x) => x.key));
  const traceVisible = new Set(traceColumnDefs.map((x) => x.key));

  const buildColumnToggleRow = (defs, visibleSet) => {
    const wrap = el("div", { class: "row" });
    defs.forEach((d) => {
      const cb = el("input", { type: "checkbox" });
      cb.checked = visibleSet.has(d.key);
      cb.addEventListener("change", () => {
        if (cb.checked) visibleSet.add(d.key);
        else visibleSet.delete(d.key);
      });
      wrap.appendChild(el("label", { class: "kv" }, [cb, document.createTextNode(" " + d.label)]));
    });
    return wrap;
  };

  const auditColsToggle = buildColumnToggleRow(auditColumnDefs, auditVisible);
  const traceColsToggle = buildColumnToggleRow(traceColumnDefs, traceVisible);
  const runQuery = async () => {
    const sid = input.value.trim();
    const a = await apiGet("/admin/api/audit" + (sid ? ("?session_id=" + encodeURIComponent(sid)) : ""));
    const tr = await apiGet("/admin/api/trace" + (sid ? ("?session_id=" + encodeURIComponent(sid)) : ""));
    const tasks = await apiGet("/admin/api/oclaw/tasks?" + (sid ? ("session_id=" + encodeURIComponent(sid) + "&") : "") + "limit=120");
    const runs = await apiGet("/admin/api/oclaw/runs?" + (sid ? ("session_id=" + encodeURIComponent(sid) + "&") : "") + "limit=80&include_attempts=1");
    const health = await apiGet(
      "/admin/api/audit/session-health?" + (sid ? ("session_id=" + encodeURIComponent(sid) + "&limit=20") : "limit=40"),
    );
    const auditRows = Array.isArray(a.audit) ? a.audit : [];
    const traceRows = Array.isArray(tr.trace) ? tr.trace : [];
    const traceIds = Array.from(new Set(traceRows.map((r) => String(r.trace_id || "")).filter(Boolean)));
    if (selectedTraceId && !traceIds.includes(selectedTraceId)) selectedTraceId = "";
    const filteredByTrace = selectedTraceId ? traceRows.filter((r) => String(r.trace_id || "") === selectedTraceId) : traceRows;
    const filteredTraceRows = onlyFailures.checked
      ? filteredByTrace.filter((r) => {
          const p = (r && typeof r.payload === "object") ? r.payload : {};
          return p.ok === false || String(p.error_code || "").trim() !== "";
        })
      : filteredByTrace;
    const auditBody = el("tbody");
    const visibleAuditCols = auditColumnDefs.filter((c) => auditVisible.has(c.key));
    if (!auditRows.length) {
      auditBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: String(Math.max(1, visibleAuditCols.length)) })]));
    } else {
      auditRows.forEach((r) => {
        const row = el("tr");
        visibleAuditCols.forEach((c) => row.appendChild(tdCell(c.getter(r), c.maxLen || 120)));
        auditBody.appendChild(row);
      });
    }
    const traceBody = el("tbody");
    const visibleTraceCols = traceColumnDefs.filter((c) => traceVisible.has(c.key));
    if (!filteredTraceRows.length) {
      traceBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: String(Math.max(1, visibleTraceCols.length)) })]));
    } else {
      filteredTraceRows.forEach((r) => {
        const row = el("tr");
        visibleTraceCols.forEach((c) => row.appendChild(tdCell(c.getter(r), c.maxLen || 120)));
        traceBody.appendChild(row);
      });
    }
    const pre = el("div", { class: "pre", text: JSON.stringify({ audit: a, trace: tr, health }, null, 2) });
    resultWrap.innerHTML = "";
    const healthItems = Array.isArray(health.items) ? health.items : [];
    const healthRows = healthItems.map((x) => el("tr", {}, [
      tdCell(String(x.session_id || ""), 26),
      tdCell(String(x.title || ""), 26),
      tdCell(String(x.assistant_count || 0), 8),
      tdCell(String(x.tool_count || 0), 8),
      tdCell(String(x.mcp_tool_count || 0), 8),
      tdCell(String(x.last_tool_at || "-"), 20),
      tdCell(String(x.status || ""), 20),
    ]));
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "Session Tool Health" }),
      el("div", { class: "muted", text: `warn=${Number(health.warn_count || 0)} (assistant replied but no tool uses)` }),
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "session_id" }),
          el("th", { text: "title" }),
          el("th", { text: "assistant_msgs" }),
          el("th", { text: "tool_uses" }),
          el("th", { text: "mcp_calls" }),
          el("th", { text: "last_tool_at" }),
          el("th", { text: "status" }),
        ])]),
        el("tbody", {}, healthRows.length ? healthRows : [el("tr", {}, [el("td", { text: "-", colspan: "7" })])]),
      ])]),
    ]));
    const taskRows = Array.isArray(tasks.tasks) ? tasks.tasks : [];
    const queued = Number((tasks.counts || {}).queued || 0);
    const claimed = Number((tasks.counts || {}).claimed || 0);
    const done = Number((tasks.counts || {}).done || 0);
    const failed = Number((tasks.counts || {}).failed || 0);
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "oclaw Tasks" }),
      el("div", { class: "muted", text: `queued=${queued} claimed=${claimed} done=${done} failed=${failed}` }),
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "task_id" }),
          el("th", { text: "status" }),
          el("th", { text: "attempt_count" }),
          el("th", { text: "session_id" }),
          el("th", { text: "updated_at" }),
          el("th", { text: "last_error" }),
        ])]),
        el(
          "tbody",
          {},
          taskRows.length
            ? taskRows.slice(0, 80).map((x) => el("tr", {}, [
                tdCell(String(x.id || ""), 24),
                tdCell(String(x.status || ""), 10),
                tdCell(String(x.attempt_count || 0), 10),
                tdCell(String(x.session_id || ""), 20),
                tdCell(String(x.updated_at || ""), 22),
                tdCell(String(x.last_error || ""), 40),
              ]))
            : [el("tr", {}, [el("td", { text: "-", colspan: "6" })])],
        ),
      ])]),
    ]));
    const runRows = Array.isArray(runs.runs) ? runs.runs : [];
    const runRunning = Number((runs.counts || {}).running || 0);
    const runSuccess = Number((runs.counts || {}).success || 0);
    const runFailed = Number((runs.counts || {}).failed || 0);
    const rp = (runs && typeof runs.retry_policy === "object" && runs.retry_policy) ? runs.retry_policy : {};
    const effRetryCodes = Array.isArray(rp.effective_retryable_error_codes) ? rp.effective_retryable_error_codes.join(", ") : "";
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "oclaw Runs" }),
      el("div", { class: "muted", text: `running=${runRunning} success=${runSuccess} failed=${runFailed}` }),
      el("div", { class: "muted", text: effRetryCodes ? `retryable_error_codes=${effRetryCodes}` : "" }),
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "run_id" }),
          el("th", { text: "status" }),
          el("th", { text: "session_id" }),
          el("th", { text: "attempts" }),
          el("th", { text: "updated_at" }),
        ])]),
        el(
          "tbody",
          {},
          runRows.length
            ? runRows.slice(0, 60).map((x) => {
                const attempts = Array.isArray(x.attempts) ? x.attempts : [];
                const attemptSummary = attempts.length
                  ? attempts.map((a) => `${Number(a.attempt_no || 0)}:${String(a.status || "")}`).join(" | ")
                  : "-";
                return el("tr", {}, [
                  tdCell(String(x.run_id || ""), 24),
                  tdCell(String(x.status || ""), 10),
                  tdCell(String(x.session_id || ""), 20),
                  tdCell(attemptSummary, 60),
                  tdCell(String(x.updated_at || ""), 22),
                ]);
              })
            : [el("tr", {}, [el("td", { text: "-", colspan: "5" })])],
        ),
      ])]),
    ]));

    const deliveryRows = auditRows
      .filter((r) => r && typeof r === "object" && r.action === "specialist_step")
      .map((r) => {
        const payload = (r && typeof r.payload === "object" && r.payload) ? r.payload : {};
        const d = (payload && typeof payload.specialist_delivery === "object" && payload.specialist_delivery)
          ? payload.specialist_delivery
          : null;
        if (!d) return null;
        const traces = Array.isArray(d.tool_traces) ? d.tool_traces : [];
        const toolsText = traces.length
          ? traces
              .map((x) => `${String(x.name || "")}(ok=${Boolean(x.ok)}, ${Number(x.latency_ms || 0)}ms)`)
              .join(" | ")
          : "-";
        return {
          timestamp: String(r.timestamp || ""),
          specialist: String(r.specialist || d.specialist || ""),
          stepId: String(d.step_id || payload.step_id || ""),
          answer: String(d.answer_text || ""),
          tools: toolsText,
          notes: String(d.notes || ""),
        };
      })
      .filter(Boolean);
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: "Specialist Delivery Timeline" }),
      el("div", { class: "muted", text: t("audit.specialistSummaryHint") }),
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: "timestamp" }),
          el("th", { text: "specialist" }),
          el("th", { text: "step_id" }),
          el("th", { text: "answer_for_user" }),
          el("th", { text: "tools_executed_inside_specialist" }),
          el("th", { text: "notes" }),
        ])]),
        el(
          "tbody",
          {},
          deliveryRows.length
            ? deliveryRows.map((x) =>
                el("tr", {}, [
                  tdCell(x.timestamp, 24),
                  tdCell(x.specialist, 14),
                  tdCell(x.stepId, 20),
                  tdCell(x.answer, 120),
                  tdCell(x.tools, 120),
                  tdCell(x.notes, 24),
                ]),
              )
            : [el("tr", {}, [el("td", { text: "-", colspan: "6" })])],
        ),
      ])]),
    ]));

    // Turn summary (group by trace_id) for quick navigation.
    if (traceIds.length) {
      const sel = el("select", { class: "input" });
      sel.appendChild(el("option", { value: "", text: `trace_id (${traceIds.length})` }));
      traceIds.forEach((tid) => sel.appendChild(el("option", { value: tid, text: tid })));
      sel.value = selectedTraceId;
      const summary = el("div", { class: "muted", text: "" });
      const failSummary = el("div", { class: "muted", text: "" });
      const recomputeSummary = () => {
        const rows = filteredTraceRows;
        const counts = {};
        rows.forEach((r) => {
          const et = String(r.event_type || "");
          counts[et] = (counts[et] || 0) + 1;
        });
        const get = (k) => Number(counts[k] || 0);
        summary.textContent = [
          `route_decided=${get("route_decided")}`,
          `plan_created=${get("plan_created")}`,
          `tool_wire_filter=${get("tool_wire_filter")}`,
          `llm_first_token=${get("llm_first_token")}`,
          `llm_called=${get("llm_called")}`,
          `llm_result=${get("llm_result")}`,
          `tool_use_called=${get("tool_called")}`,
          `tool_result=${get("tool_result")}`,
        ].join(" | ");
        const agg = {};
        rows.forEach((r) => {
          const p = (r && typeof r.payload === "object") ? r.payload : {};
          const ec = String(p.error_code || "").trim();
          if (!ec) return;
          agg[ec] = (agg[ec] || 0) + 1;
        });
        const parts = Object.entries(agg).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k, v]) => `${k}:${v}`);
        failSummary.textContent = parts.length ? `Failure summary: ${parts.join(" | ")}` : "Failure summary: -";
      };
      sel.addEventListener("change", () => {
        selectedTraceId = String(sel.value || "");
        runQuery();
      });
      recomputeSummary();
      resultWrap.appendChild(el("div", { class: "card" }, [
        el("div", { class: "card__title", text: "Turn summary" }),
        el("div", { class: "row" }, [sel, el("label", { class: "kv" }, [onlyFailures, document.createTextNode(" only failures")])]),
        summary,
        failSummary,
      ]));
    }
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("audit.auditTable") }),
      el("div", { class: "muted", text: t("audit.columns") }),
      auditColsToggle,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, auditColumnDefs.filter((c) => auditVisible.has(c.key)).map((c) => el("th", { text: c.label })))]),
        auditBody,
      ])]),
    ]));
    resultWrap.appendChild(el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("audit.traceTable") }),
      el("div", { class: "muted", text: t("audit.columns") }),
      traceColsToggle,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, traceColumnDefs.filter((c) => traceVisible.has(c.key)).map((c) => el("th", { text: c.label })))]),
        traceBody,
      ])]),
    ]));
    const details = el("details", { class: "details" }, [
      el("summary", { text: t("audit.rawJson") }),
      pre,
    ]);
    resultWrap.appendChild(el("div", { class: "card" }, [details]));
  };
  const btn = el("button", { class: "btn btn--primary", text: t("audit.query"), onclick: async () => {
    await runQuery();
  }});
  onlyFailures.addEventListener("change", runQuery);
  auditColsToggle.addEventListener("change", runQuery);
  traceColsToggle.addEventListener("change", runQuery);
  const card = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("audit.title") }),
    el("div", { class: "row" }, [input, btn]),
    el("div", { class: "muted", text: t("audit.note") }),
  ]);
  if (initialSessionId) {
    input.value = initialSessionId;
    await runQuery();
  }
  return el("div", {}, [card, resultWrap]);
}


export { renderAudit };
