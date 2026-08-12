import { t, tf, el, tdCell, apiGet, apiPost, apiRequest, resolveAdminApiUrl, getStoredAuthToken, formatSystemLocalDateTime } from "../core.js";
import { hasPermission } from "./authz.js";

function formatScheduledJobDelivery(job) {
  const d = (job && job.delivery && typeof job.delivery === "object") ? job.delivery : {};
  const parts = [];
  if (d.weixin && d.weixin.enabled) parts.push(t("scheduledJobs.deliveryWeixin"));
  if (d.whatsapp && d.whatsapp.enabled) parts.push(t("scheduledJobs.deliveryWhatsapp"));
  return parts.length ? parts.join(" + ") : "—";
}

function formatScheduledJobPlaybook(job) {
  const steps = Number(job && job.steps_n != null ? job.steps_n : 0) || 0;
  if (job && job.playbook) return tf("scheduledJobs.playbookYes", { n: String(steps) });
  if (job && job.has_recipe) return tf("scheduledJobs.playbookPartial", { n: String(steps) });
  return t("scheduledJobs.playbookNo");
}

function buildScheduledJobDeliveryPayload(job, waChatId) {
  const existing = (job && job.delivery && typeof job.delivery === "object") ? job.delivery : {};
  const wa = existing.whatsapp && typeof existing.whatsapp === "object" ? { ...existing.whatsapp } : {};
  const wx =
    existing.weixin && typeof existing.weixin === "object"
      ? { ...existing.weixin }
      : { enabled: true, fixed: true };
  const chat = String(waChatId || "").trim();
  wa.enabled = Boolean(chat);
  wa.chat_id = chat;
  wa.target_type = chat.includes("@g.us") ? "group" : "direct";
  if (wx.enabled === undefined) wx.enabled = true;
  return { whatsapp: wa, weixin: wx };
}

async function renderScheduledJobs() {
  let scheduledJobMenuEl = null;
  let editingJob = null;
  const canWrite = hasPermission("admin:runtime:write");
  const closeScheduledJobMenu = () => {
    if (scheduledJobMenuEl && scheduledJobMenuEl.parentNode) {
      scheduledJobMenuEl.remove();
    }
    scheduledJobMenuEl = null;
  };

  const status = el("select", { class: "input input--compact" }, [
    el("option", { value: "", text: t("scheduledJobs.all") }),
    el("option", { value: "active", text: t("scheduledJobs.statusActive") }),
    el("option", { value: "paused", text: t("scheduledJobs.statusPaused") }),
  ]);
  const tbody = el("tbody", {});
  const runsTbody = el("tbody", {});
  const runsEmpty = el("div", { class: "muted", text: t("scheduledJobs.noRuns") });
  const runsTable = el("div", { class: "table-wrap" }, [
    el("table", { class: "table table--compact" }, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", { text: t("scheduledJobs.colJob") }),
          el("th", { text: t("scheduledJobs.colRunStatus") }),
          el("th", { text: t("scheduledJobs.colFailClass") }),
          el("th", { text: t("scheduledJobs.colFinished") }),
          el("th", { text: t("scheduledJobs.colError") }),
        ]),
      ]),
      runsTbody,
    ]),
  ]);
  const runsBox = el("div", {}, [runsEmpty, runsTable]);
  runsTable.style.display = "none";
  const statsBox = el("div", { class: "muted", text: "" });
  const attentionBox = el("div", { class: "muted", text: "" });
  const msg = el("div", { class: "muted", text: "" });
  const weixinInfo = el("div", { class: "muted", text: "" });

  const failClassLabel = (fc) => {
    const key = `scheduledJobs.failClass.${String(fc || "").trim()}`;
    const labeled = t(key);
    return labeled === key ? String(fc || "—") : labeled;
  };

  const renderRunsTable = (items, jobNameFallback) => {
    const rows = Array.isArray(items) ? items : [];
    runsTbody.replaceChildren();
    if (!rows.length) {
      runsEmpty.style.display = "";
      runsTable.style.display = "none";
      runsEmpty.textContent = t("scheduledJobs.noRuns");
      return;
    }
    runsEmpty.style.display = "none";
    runsTable.style.display = "";
    for (const run of rows.slice(0, 30)) {
      const st = String(run.status || "");
      const fc = String(run.failure_class || "");
      const err = String(run.error || "").trim();
      const name = String(run.job_name || jobNameFallback || run.job_id || "—");
      const finished = run.finished_at
        ? formatSystemLocalDateTime(String(run.finished_at))
        : (run.created_at ? formatSystemLocalDateTime(String(run.created_at)) : "—");
      const statusCell = el("td", { text: st || "—" });
      if (st.toLowerCase() === "failed" || st.toLowerCase() === "error") {
        statusCell.style.color = "var(--danger, #c44)";
      } else if (st.toLowerCase() === "success") {
        statusCell.style.color = "var(--success, #2a7)";
      }
      runsTbody.appendChild(
        el("tr", {}, [
          el("td", { text: name.slice(0, 40) }),
          statusCell,
          el("td", { text: fc ? failClassLabel(fc) : "—" }),
          el("td", { text: finished }),
          el("td", { text: err ? err.slice(0, 120) : "—" }),
        ])
      );
    }
  };

  const loadStats = async () => {
    try {
      const stats = await apiGet("/admin/api/scheduled-jobs/stats?recent_limit=80");
      const finished = Number(stats.recent_success || 0) + Number(stats.recent_failed || 0);
      const pct = Number(stats.recent_fail_rate_pct || 0);
      const classes = stats.recent_fail_classes || {};
      const classParts = Object.keys(classes).map((k) => `${failClassLabel(k)} ${classes[k]}`);
      statsBox.textContent = [
        tf("scheduledJobs.statsFailRate", {
          pct: String(pct),
          failed: String(stats.recent_failed || 0),
          finished: String(finished),
        }),
        classParts.length
          ? `${t("scheduledJobs.statsClasses")}: ${classParts.join(" · ")}`
          : t("scheduledJobs.statsNone"),
        tf("scheduledJobs.statsJobsFailed", { n: String((stats.jobs_last_failed || []).length) }),
      ].join("  |  ");
      const failedJobs = stats.jobs_last_failed || [];
      if (!failedJobs.length) {
        attentionBox.textContent = "";
      } else {
        attentionBox.textContent =
          `${t("scheduledJobs.attentionTitle")}: ` +
          failedJobs
            .slice(0, 8)
            .map((j) => `${j.name || j.id}${j.last_run_at ? ` @ ${formatSystemLocalDateTime(String(j.last_run_at))}` : ""}`)
            .join(" · ");
      }
      const fails = stats.recent_failures || [];
      if (fails.length) {
        renderRunsTable(fails, "");
        return true;
      }
      return false;
    } catch (e) {
      statsBox.textContent = String(e && e.message ? e.message : e);
      return false;
    }
  };

  const field = (label, control, wide) =>
    el("div", { class: wide ? "form-field form-field--full" : "form-field" }, [
      el("label", { class: "form-field__label", text: label }),
      control,
    ]);

  const editModal = el("div", { class: "session-monitor-modal u-hidden" });
  const editTitle = el("div", { class: "card__title", text: t("scheduledJobs.editTitle") });
  const editNameInput = el("input", { class: "input", placeholder: t("scheduledJobs.phName") });
  const editKindInput = el("select", { class: "input" }, [
    el("option", { value: "cron", text: "cron" }),
    el("option", { value: "once", text: "once" }),
    el("option", { value: "interval", text: "interval" }),
  ]);
  const editExprInput = el("input", { class: "input", placeholder: t("scheduledJobs.phExpr") });
  const editPromptInput = el("textarea", { class: "input", rows: "5", placeholder: t("scheduledJobs.phPrompt") });
  const editSpecialistInput = el("input", { class: "input", placeholder: t("scheduledJobs.phSpecialist") });
  const editWaChatInput = el("input", { class: "input", placeholder: t("scheduledJobs.phWhatsapp") });
  const editWeixinInfo = el("div", { class: "muted", text: "" });
  const closeEditModal = () => {
    editingJob = null;
    editModal.style.display = "none";
  };
  const openEditModal = (job) => {
    if (!job || !job.id) return;
    editingJob = job;
    editTitle.textContent = `${t("scheduledJobs.editTitle")}: ${String(job.name || job.id)}`;
    editNameInput.value = String(job.name || "");
    editKindInput.value = String(job.schedule_kind || "cron");
    editExprInput.value = String(job.schedule_expr || "");
    editPromptInput.value = String(job.prompt_text || "");
    editSpecialistInput.value = String(job.specialist || "generalist");
    const wa = job.delivery && job.delivery.whatsapp ? job.delivery.whatsapp : {};
    editWaChatInput.value = String(wa.chat_id || "");
    const wx = job.delivery && job.delivery.weixin ? job.delivery.weixin : {};
    editWeixinInfo.textContent = wx.external_user_id
      ? tf("scheduledJobs.weixinFixed", { id: String(wx.external_user_id) })
      : weixinInfo.textContent || t("scheduledJobs.weixinMissing");
    editModal.style.display = "flex";
    setTimeout(() => editNameInput.focus(), 0);
  };
  editModal.addEventListener("click", (e) => {
    if (e.target === editModal) closeEditModal();
  });
  const editSaveBtn = el("button", {
    class: "btn btn--primary",
    text: t("action.save"),
    onclick: async () => {
      if (!editingJob || !editingJob.id) return;
      const name = String(editNameInput.value || "").trim();
      const promptText = String(editPromptInput.value || "").trim();
      const scheduleExpr = String(editExprInput.value || "").trim();
      if (!name || !promptText || !scheduleExpr) {
        msg.textContent = t("scheduledJobs.requiredFields");
        return;
      }
      try {
        await apiRequest("PATCH", `/admin/api/scheduled-jobs/${encodeURIComponent(String(editingJob.id))}`, {
          name,
          schedule_kind: editKindInput.value,
          schedule_expr: scheduleExpr,
          prompt_text: promptText,
          specialist: String(editSpecialistInput.value || "generalist").trim() || "generalist",
          delivery: buildScheduledJobDeliveryPayload(editingJob, editWaChatInput.value),
        });
        closeEditModal();
        msg.textContent = t("scheduledJobs.updated");
        await loadJobs();
      } catch (e) {
        msg.textContent = String(e && e.message ? e.message : e);
      }
    },
  });
  const editModalCard = el("div", { class: "card session-monitor-modal__card", style: "width:min(640px,96vw);" }, [
    editTitle,
    editWeixinInfo,
    el("div", { class: "form-stack" }, [
      field(t("scheduledJobs.fieldName"), editNameInput, true),
      el("div", { class: "form-grid" }, [
        field(t("scheduledJobs.fieldKind"), editKindInput),
        field(t("scheduledJobs.fieldExpr"), editExprInput),
      ]),
      field(t("scheduledJobs.fieldPrompt"), editPromptInput, true),
      el("div", { class: "form-grid" }, [
        field(t("scheduledJobs.fieldSpecialist"), editSpecialistInput),
        field(t("scheduledJobs.fieldWhatsapp"), editWaChatInput),
      ]),
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn", text: t("scheduledJobs.cancel"), onclick: closeEditModal }),
        editSaveBtn,
      ]),
    ]),
  ]);
  editModal.appendChild(editModalCard);

  async function loadLatestRuns(items) {
    const jobs = Array.isArray(items) ? items : [];
    if (!jobs.length) {
      renderRunsTable([], "");
      return;
    }
    const withLast = jobs.filter((j) => String(j.last_run_at || "").trim());
    const target = withLast.length ? withLast[0] : jobs[0];
    if (!target || !target.id) {
      renderRunsTable([], "");
      return;
    }
    const runs = await apiGet(`/admin/api/scheduled-jobs/${encodeURIComponent(String(target.id))}/runs?limit=10`);
    const runItems = (runs.items || []).map((r) => ({ ...r, job_name: target.name || target.id }));
    renderRunsTable(runItems, String(target.name || target.id || ""));
  }

  async function loadJobs() {
    closeScheduledJobMenu();
    msg.textContent = t("scheduledJobs.loading");
    const st = String(status.value || "").trim();
    const q = st ? `?status=${encodeURIComponent(st)}` : "";
    const resp = await apiGet(`/admin/api/scheduled-jobs${q}`);
    tbody.replaceChildren();
    for (const job of resp.items || []) {
      const jobId = String(job.id || "");
      const btnMore = el("button", {
        class: "chat-sess-more",
        text: "⋯",
        title: t("scheduledJobs.menuTitle"),
        onclick: (ev) => {
          ev.stopPropagation();
          closeScheduledJobMenu();
          const menu = el("div", { class: "chat-sess-menu-pop u-overlay-fixed" }, [
            el("button", {
              class: "chat-sess-menu-item",
              text: t("scheduledJobs.viewRuns"),
              onclick: async () => {
                closeScheduledJobMenu();
                const runs = await apiGet(`/admin/api/scheduled-jobs/${encodeURIComponent(jobId)}/runs`);
                const runItems = (runs.items || []).map((r) => ({ ...r, job_name: job.name || jobId }));
                renderRunsTable(runItems, String(job.name || jobId));
              },
            }),
            ...(canWrite
              ? [
                  el("button", {
                    class: "chat-sess-menu-item",
                    text: t("scheduledJobs.edit"),
                    onclick: () => {
                      closeScheduledJobMenu();
                      openEditModal(job);
                    },
                  }),
                ]
              : []),
            el("button", {
              class: "chat-sess-menu-item",
              text: job.status === "active" ? t("scheduledJobs.pause") : t("scheduledJobs.resume"),
              onclick: async () => {
                closeScheduledJobMenu();
                const path =
                  job.status === "active"
                    ? `/admin/api/scheduled-jobs/${encodeURIComponent(jobId)}/pause`
                    : `/admin/api/scheduled-jobs/${encodeURIComponent(jobId)}/resume`;
                await apiPost(path, {});
                await loadJobs();
              },
            }),
            el("button", {
              class: "chat-sess-menu-item",
              text: t("scheduledJobs.runNow"),
              onclick: async () => {
                closeScheduledJobMenu();
                const out = await apiPost(`/admin/api/scheduled-jobs/${encodeURIComponent(jobId)}/run-now`, {});
                if (out && out.skipped) {
                  msg.textContent = t("scheduledJobs.skippedOverlap");
                } else {
                  msg.textContent = t("scheduledJobs.triggered");
                }
                await loadJobs();
              },
            }),
            ...(canWrite
              ? [
                  el("button", {
                    class: "chat-sess-menu-item",
                    text: t("scheduledJobs.delete"),
                    onclick: async () => {
                      closeScheduledJobMenu();
                      if (!window.confirm(t("scheduledJobs.deleteConfirm"))) return;
                      await fetch(resolveAdminApiUrl(`/admin/api/scheduled-jobs/${encodeURIComponent(jobId)}`), {
                        method: "DELETE",
                        headers: { authorization: `Bearer ${getStoredAuthToken()}`, accept: "application/json" },
                      });
                      await loadJobs();
                    },
                  }),
                ]
              : []),
          ]);
          const rect = ev.currentTarget.getBoundingClientRect();
          document.body.appendChild(menu);
          const mrect = menu.getBoundingClientRect();
          const pad = 8;
          let left = rect.left - 120;
          let top = rect.bottom + 4;
          if (top + mrect.height > window.innerHeight - pad) {
            top = rect.top - 4 - mrect.height;
          }
          left = Math.max(pad, Math.min(left, window.innerWidth - pad - mrect.width));
          top = Math.max(pad, Math.min(top, window.innerHeight - pad - mrect.height));
          menu.style.left = `${left}px`;
          menu.style.top = `${top}px`;
          scheduledJobMenuEl = menu;
          const close = (e) => {
            if (!menu.contains(e.target)) {
              closeScheduledJobMenu();
              document.removeEventListener("click", close);
            }
          };
          setTimeout(() => document.addEventListener("click", close), 0);
        },
      });
      const lastStatus = String(job.last_run_status || "").trim();
      const lastRun = job.last_run_at
        ? `${formatSystemLocalDateTime(String(job.last_run_at))}${lastStatus ? ` (${lastStatus})` : ""}`
        : "—";
      const lastCell = el("td", { text: lastRun });
      if (lastStatus.toLowerCase() === "failed") {
        lastCell.style.color = "var(--danger, #c44)";
      } else if (lastStatus.toLowerCase() === "success") {
        lastCell.style.color = "var(--success, #2a7)";
      }
      const tr = el("tr", {}, [
        tdCell(job.name || "", 24),
        tdCell(`${job.schedule_kind}:${job.schedule_expr}`, 28),
        tdCell(formatScheduledJobPlaybook(job), 18),
        tdCell(job.status || "", 10),
        tdCell(job.next_run_at || "—", 20),
        lastCell,
        tdCell(job.specialist || "", 14),
        tdCell(formatScheduledJobDelivery(job), 12),
        el("td", { class: "table__cell--actions" }, [
          el("div", { class: "table__cell-actions" }, [btnMore]),
        ]),
      ]);
      tbody.appendChild(tr);
    }
    msg.textContent = tf("scheduledJobs.count", { count: String((resp.items || []).length) });
    const showedFails = await loadStats();
    if (!showedFails) {
      await loadLatestRuns(resp.items || []);
    }
  }

  const nameInput = el("input", { class: "input", placeholder: t("scheduledJobs.phName") });
  const kindInput = el("select", { class: "input" }, [
    el("option", { value: "cron", text: "cron" }),
    el("option", { value: "once", text: "once" }),
    el("option", { value: "interval", text: "interval" }),
  ]);
  const exprInput = el("input", { class: "input", placeholder: t("scheduledJobs.phExpr") });
  const promptInput = el("textarea", { class: "input", rows: "5", placeholder: t("scheduledJobs.phPrompt") });
  const specialistInput = el("input", { class: "input", placeholder: t("scheduledJobs.phSpecialist"), value: "generalist" });
  const waChatInput = el("input", { class: "input", placeholder: t("scheduledJobs.phWhatsapp") });

  async function loadMeta() {
    const meta = await apiGet("/admin/api/scheduled-jobs/meta/targets");
    const wx = meta.weixin_binding || {};
    weixinInfo.textContent = wx.external_user_id
      ? tf("scheduledJobs.weixinFixed", { id: String(wx.external_user_id) })
      : t("scheduledJobs.weixinMissing");
  }

  await loadMeta();
  await loadJobs();

  const createCardChildren = [
    el("div", { class: "card__title", text: t("scheduledJobs.createTitle") }),
    weixinInfo,
    el("div", { class: "form-stack" }, [
      field(t("scheduledJobs.fieldName"), nameInput, true),
      el("div", { class: "form-grid" }, [
        field(t("scheduledJobs.fieldKind"), kindInput),
        field(t("scheduledJobs.fieldExpr"), exprInput),
      ]),
      field(t("scheduledJobs.fieldPrompt"), promptInput, true),
      el("div", { class: "form-grid" }, [
        field(t("scheduledJobs.fieldSpecialist"), specialistInput),
        field(t("scheduledJobs.fieldWhatsapp"), waChatInput),
      ]),
      el("div", { class: "form-actions" }, [
        el("button", {
          class: "btn btn--primary",
          text: t("scheduledJobs.create"),
          onclick: async () => {
            await apiPost("/admin/api/scheduled-jobs", {
              name: nameInput.value,
              schedule_kind: kindInput.value,
              schedule_expr: exprInput.value,
              prompt_text: promptInput.value,
              specialist: specialistInput.value,
              whatsapp_chat_id: waChatInput.value,
              delivery: buildScheduledJobDeliveryPayload(null, waChatInput.value),
            });
            await loadJobs();
          },
        }),
      ]),
    ]),
  ];

  return el("div", {}, [
    editModal,
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.scheduledJobs") }),
      el("div", { class: "row", style: "gap:8px;align-items:center;flex-wrap:wrap;" }, [
        status,
        el("button", { class: "btn", text: t("action.refresh"), onclick: () => loadJobs() }),
        msg,
      ]),
      el("div", { class: "card__title", style: "margin-top:10px;font-size:13px;", text: t("scheduledJobs.statsTitle") }),
      statsBox,
      attentionBox,
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact" }, [
          el("colgroup", {}, [
            el("col", { style: "width:14%" }),
            el("col", { style: "width:14%" }),
            el("col", { class: "u-w-12p" }),
            el("col", { style: "width:8%" }),
            el("col", { class: "u-w-12p" }),
            el("col", { class: "u-w-12p" }),
            el("col", { style: "width:8%" }),
            el("col", { style: "width:10%" }),
            el("col", { style: "width:10%" }),
          ]),
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: t("scheduledJobs.colName") }),
              el("th", { text: t("scheduledJobs.colSchedule") }),
              el("th", { text: t("scheduledJobs.colPlaybook") }),
              el("th", { text: t("scheduledJobs.colStatus") }),
              el("th", { text: t("scheduledJobs.colNextRun") }),
              el("th", { text: t("scheduledJobs.colLastRun") }),
              el("th", { text: t("scheduledJobs.colSpecialist") }),
              el("th", { text: t("scheduledJobs.colDelivery") }),
              el("th", { text: t("scheduledJobs.colActions") }),
            ]),
          ]),
          tbody,
        ]),
      ]),
    ]),
    ...(canWrite ? [el("div", { class: "card" }, createCardChildren)] : []),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: `${t("scheduledJobs.runHistory")} · ${t("scheduledJobs.runHistoryHint")}` }),
      runsBox,
    ]),
  ]);
}


export { formatScheduledJobDelivery, formatScheduledJobPlaybook, buildScheduledJobDeliveryPayload, renderScheduledJobs };
