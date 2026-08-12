import { t, tf, el, tdCell, apiGet, resolveAdminApiUrl, getStoredAuthToken, SESSION_MONITOR_ROLE_FILTER_KEY, formatAuditActor, renderPageShell, renderSectionCard, enableTableColumnResize } from "../core.js";

async function renderAdminAudit() {
  const action = el("input", { class: "input", placeholder: t("adminAudit.action") });
  const actor = el("input", { class: "input", placeholder: t("adminAudit.actor") });
  const status = el("input", { class: "input", placeholder: t("adminAudit.status") });
  const tbody = el("tbody");
  const pager = el("div", { class: "row", style: "gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px;" });
  const pageInfo = el("span", { class: "muted", text: tf("sessionMonitor.pageInfo", { page: 1, totalPages: 1 }) });
  const totalInfo = el("span", { class: "muted", text: tf("adminAudit.total", { total: 0 }) });
  const pageInput = el("input", {
    class: "input",
    type: "number",
    min: "1",
    step: "1",
    placeholder: t("adminAudit.jumpPlaceholder"),
    style: "width:90px;",
  });
  let page = 1;
  const pageSize = 50;
  let total = 0;
  const totalPages = () => Math.max(1, Math.ceil((Number(total) || 0) / pageSize));
  const setPager = () => {
    const tp = totalPages();
    pageInfo.textContent = tf("sessionMonitor.pageInfo", { page, totalPages: tp });
    totalInfo.textContent = tf("adminAudit.total", { total });
    pageInput.value = String(page);
    btnPrev.disabled = page <= 1;
    btnNext.disabled = page >= tp;
  };
  const load = async () => {
    const p = new URLSearchParams();
    p.set("limit", String(pageSize));
    p.set("offset", String((Math.max(1, page) - 1) * pageSize));
    if (action.value.trim()) p.set("action", action.value.trim());
    if (actor.value.trim()) p.set("actor_user_id", actor.value.trim());
    if (status.value.trim()) p.set("status", status.value.trim());
    const resp = await apiGet("/admin/api/admin-audit?" + p.toString());
    total = Math.max(0, Number(resp.total || 0) || 0);
    const rows = Array.isArray(resp.items) ? resp.items : [];
    tbody.innerHTML = "";
    if (!rows.length) {
      tbody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "8" })]));
      setPager();
      return;
    }
    rows.forEach((r) => {
      tbody.appendChild(el("tr", {}, [
        tdCell(r.timestamp || "", 24),
        tdCell(formatAuditActor(r), 28),
        tdCell(r.action || "", 20),
        tdCell(r.target_type || "", 16),
        tdCell(r.target_id || "", 24),
        tdCell(r.status || "", 12),
        tdCell(r.actor_tenant_id || "", 24),
        tdCell(JSON.stringify(r.detail || {}), 120),
      ]));
    });
    setPager();
  };
  const btn = el("button", {
    class: "btn btn--primary",
    text: t("audit.query"),
    onclick: async () => {
      page = 1;
      await load();
    },
  });
  const btnPrev = el("button", {
    class: "btn btn--small",
    text: t("sessionMonitor.pagePrev"),
    disabled: true,
    onclick: async () => {
      if (page <= 1) return;
      page -= 1;
      await load();
    },
  });
  const btnNext = el("button", {
    class: "btn btn--small",
    text: t("sessionMonitor.pageNext"),
    disabled: true,
    onclick: async () => {
      const tp = totalPages();
      if (page >= tp) return;
      page += 1;
      await load();
    },
  });
  const btnJump = el("button", {
    class: "btn btn--small",
    text: t("adminAudit.jump"),
    onclick: async () => {
      const tp = totalPages();
      let target = parseInt(String(pageInput.value || "").trim(), 10);
      if (!Number.isFinite(target)) target = page;
      target = Math.max(1, Math.min(tp, target));
      if (target === page) {
        setPager();
        return;
      }
      page = target;
      await load();
    },
  });
  pageInput.addEventListener("keydown", async (ev) => {
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    btnJump.click();
  });
  pager.appendChild(btnPrev);
  pager.appendChild(btnNext);
  pager.appendChild(pageInfo);
  pager.appendChild(totalInfo);
  pager.appendChild(pageInput);
  pager.appendChild(btnJump);
  await load();
  return el("div", {}, [
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("adminAudit.title") }),
      el("div", { class: "row" }, [action, actor, status, btn]),
      pager,
      el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("table.timestamp") }),
          el("th", { text: t("adminAudit.actor") }),
          el("th", { text: t("adminAudit.action") }),
          el("th", { text: "target_type" }),
          el("th", { text: "target_id" }),
          el("th", { text: t("adminAudit.status") }),
          el("th", { text: "tenant_id" }),
          el("th", { text: t("table.payload") }),
        ])]),
        tbody,
      ])]),
    ]),
  ]);
}

async function renderSessionMonitor() {
  const userQ = el("input", { class: "input", placeholder: t("sessionMonitor.filterUser") });
  const sessQ = el("input", { class: "input", placeholder: t("sessionMonitor.filterSession") });
  const activeOnlyChk = el("input", { type: "checkbox" });
  const selectedHint = el("div", { class: "muted", text: t("sessionMonitor.selectUserFirst") });
  const userBody = el("tbody");
  const sessBody = el("tbody");
  const sessionPagerTop = el("div", { class: "row" });
  const sessionPagerBottom = el("div", { class: "row" });
  const detailBody = el("tbody");
  const detailStatus = el("div", { class: "muted", text: t("sessionMonitor.noMessages") });
  const detailPager = el("div", { class: "row" });
  const detailRoleFilter = el("select", { class: "input" });
  const detailModal = el("div", { class: "session-monitor-modal u-hidden" });
  const detailModalCard = el("div", { class: "session-monitor-modal__card" });
  const totalsWrap = el("div", { class: "row" });
  let selectedUserId = "";
  let selectedSessionId = "";
  let sessionLimit = 20;
  let sessionOffset = 0;
  let sessionTotal = 0;
  let detailMessages = [];
  let detailPage = 1;
  const detailPageSize = 20;
  let sessionMenuEl = null;

  const rebuildDetailRoleFilter = () => {
    const saved = String(localStorage.getItem(SESSION_MONITOR_ROLE_FILTER_KEY) || "").trim();
    const prev = String(detailRoleFilter.value || saved || "all");
    detailRoleFilter.innerHTML = "";
    detailRoleFilter.appendChild(el("option", { value: "all", text: t("sessionMonitor.roleAll") }));
    detailRoleFilter.appendChild(el("option", { value: "user", text: t("sessionMonitor.roleUser") }));
    detailRoleFilter.appendChild(el("option", { value: "assistant", text: t("sessionMonitor.roleAssistant") }));
    detailRoleFilter.appendChild(el("option", { value: "tool", text: t("sessionMonitor.roleTool") }));
    detailRoleFilter.value = ["all", "user", "assistant", "tool"].includes(prev) ? prev : "all";
  };

  const buildPageInfo = (page, totalPages) => tf("sessionMonitor.pageInfo", { page, totalPages });

  const downloadSessionExport = async (sessionId, format) => {
    const q = format === "json" ? "format=json" : "format=md";
    const path = `/admin/api/chat/sessions/${encodeURIComponent(sessionId)}/export?${q}`;
    const url = resolveAdminApiUrl(path);
    const tok = getStoredAuthToken();
    const res = await fetch(url, {
      headers: tok ? { authorization: `Bearer ${tok}` } : {},
    });
    if (!res.ok) throw new Error(`export_failed_${res.status}`);
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `chat-${String(sessionId || "").slice(0, 8)}.${format === "json" ? "json" : "md"}`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const closeSessionMenu = () => {
    if (sessionMenuEl && sessionMenuEl.parentNode) {
      sessionMenuEl.remove();
    }
    sessionMenuEl = null;
  };

  const closeDetailModal = () => {
    detailModal.style.display = "none";
  };

  const renderTotals = (totals) => {
    totalsWrap.innerHTML = "";
    const cards = [
      { key: "total_tokens_est", label: t("sessionMonitor.totalTokensEst") },
      { key: "active_sessions_30m", label: t("sessionMonitor.activeSessions30m") },
      { key: "active_logins_30m", label: t("sessionMonitor.activeLogins30m") },
      { key: "users_count", label: t("sessionMonitor.usersCount") },
    ];
    cards.forEach((c) => {
      totalsWrap.appendChild(
        el("div", { class: "kv", text: `${c.label}: ${String((totals && totals[c.key]) ?? 0)}` }),
      );
    });
  };

  const renderDetailPager = () => {
    detailPager.innerHTML = "";
    const role = String(detailRoleFilter.value || "all");
    const filtered = Array.isArray(detailMessages)
      ? detailMessages.filter((m) => {
          if (role === "all") return true;
          const r = String(m.role || "").toLowerCase();
          return role === "tool" ? r === "tool" || r === "function" : r === role;
        })
      : [];
    const total = filtered.length;
    const totalPages = Math.max(1, Math.ceil(total / detailPageSize));
    const info = el("span", { class: "muted", text: buildPageInfo(detailPage, totalPages) });
    const btnPrev = el("button", {
      class: "btn btn--small",
      text: t("sessionMonitor.pagePrev"),
      disabled: detailPage <= 1,
      onclick: () => {
        if (detailPage <= 1) return;
        detailPage -= 1;
        renderDetailMessages();
      },
    });
    const btnNext = el("button", {
      class: "btn btn--small",
      text: t("sessionMonitor.pageNext"),
      disabled: detailPage >= totalPages,
      onclick: () => {
        if (detailPage >= totalPages) return;
        detailPage += 1;
        renderDetailMessages();
      },
    });
    detailPager.appendChild(btnPrev);
    detailPager.appendChild(btnNext);
    detailPager.appendChild(info);
  };

  const renderDetailMessages = () => {
    detailBody.innerHTML = "";
    if (!selectedSessionId) {
      detailStatus.textContent = t("sessionMonitor.selectUserFirst");
      detailPager.innerHTML = "";
      return;
    }
    const role = String(detailRoleFilter.value || "all");
    const all = Array.isArray(detailMessages) ? detailMessages : [];
    const filtered = all.filter((m) => {
      if (role === "all") return true;
      const r = String(m.role || "").toLowerCase();
      return role === "tool" ? r === "tool" || r === "function" : r === role;
    });
    if (!filtered.length) {
      detailStatus.textContent = t("sessionMonitor.noMessages");
      detailPager.innerHTML = "";
      return;
    }
    const totalPages = Math.max(1, Math.ceil(filtered.length / detailPageSize));
    if (detailPage > totalPages) detailPage = totalPages;
    const start = (detailPage - 1) * detailPageSize;
    const rows = filtered.slice(start, start + detailPageSize);
    detailStatus.textContent = `session_id: ${selectedSessionId} | ${filtered.length}/${all.length}`;
    rows.forEach((m) => {
      detailBody.appendChild(
        el("tr", {}, [
          tdCell(m.id || "", 8),
          tdCell(m.role || "", 10),
          tdCell(m.content || "", 120),
          tdCell(m.timestamp || "", 24),
        ]),
      );
    });
    renderDetailPager();
  };

  const loadSessionDetail = async (sessionId, opts = {}) => {
    const openModal = Boolean(opts && opts.openModal);
    selectedSessionId = String(sessionId || "");
    detailPage = 1;
    detailBody.innerHTML = "";
    detailStatus.textContent = `${t("chat.loading")}...`;
    detailPager.innerHTML = "";
    if (!selectedSessionId) {
      detailStatus.textContent = t("sessionMonitor.noMessages");
      if (openModal) detailModal.style.display = "flex";
      return;
    }
    try {
      const resp = await apiGet(`/admin/api/chat/sessions/${encodeURIComponent(selectedSessionId)}/messages`);
      detailMessages = Array.isArray(resp.messages) ? resp.messages : [];
      renderDetailMessages();
    } catch (err) {
      detailMessages = [];
      detailBody.innerHTML = "";
      detailPager.innerHTML = "";
      detailStatus.textContent = `${t("chat.error")}: ${String(err && err.message ? err.message : err)}`;
    }
    if (openModal) detailModal.style.display = "flex";
  };

  const renderSessionPager = () => {
    const totalPages = Math.max(1, Math.ceil(Math.max(0, sessionTotal) / sessionLimit));
    const current = Math.floor(sessionOffset / sessionLimit) + 1;
    const row = el("div", { class: "row" }, [
      el("button", {
        class: "btn btn--small",
        text: t("sessionMonitor.pagePrev"),
        disabled: sessionOffset <= 0,
        onclick: async () => {
          if (sessionOffset <= 0) return;
          sessionOffset = Math.max(0, sessionOffset - sessionLimit);
          await loadSessions();
        },
      }),
      el("button", {
        class: "btn btn--small",
        text: t("sessionMonitor.pageNext"),
        disabled: sessionOffset + sessionLimit >= sessionTotal,
        onclick: async () => {
          if (sessionOffset + sessionLimit >= sessionTotal) return;
          sessionOffset += sessionLimit;
          await loadSessions();
        },
      }),
      el("span", { class: "muted", text: buildPageInfo(current, totalPages) }),
    ]);
    return row;
  };

  const updateSessionPagers = () => {
    sessionPagerTop.innerHTML = "";
    sessionPagerBottom.innerHTML = "";
    sessionPagerTop.appendChild(renderSessionPager());
    sessionPagerBottom.appendChild(renderSessionPager());
  };
  detailRoleFilter.addEventListener("change", () => {
    try {
      localStorage.setItem(SESSION_MONITOR_ROLE_FILTER_KEY, String(detailRoleFilter.value || "all"));
    } catch (_) {}
    detailPage = 1;
    renderDetailMessages();
  });

  const loadSessions = async () => {
    sessBody.innerHTML = "";
    if (!selectedUserId) {
      sessBody.appendChild(el("tr", {}, [el("td", { text: t("sessionMonitor.selectUserFirst"), colspan: "8" })]));
      selectedHint.textContent = t("sessionMonitor.selectUserFirst");
      sessionTotal = 0;
      updateSessionPagers();
      return;
    }
    const sp = new URLSearchParams();
    sp.set("user_id", selectedUserId);
    sp.set("limit", String(sessionLimit));
    sp.set("offset", String(sessionOffset));
    if (sessQ.value.trim()) sp.set("q", sessQ.value.trim());
    if (activeOnlyChk.checked) sp.set("active_only", "1");
    const resp = await apiGet("/admin/api/chat/admin/sessions?" + sp.toString());
    const rows = Array.isArray(resp.sessions) ? resp.sessions : [];
    sessionTotal = Number(resp.total || 0);
    selectedHint.textContent = `${t("table.userId")}: ${selectedUserId}`;
    if (!rows.length) {
      sessBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "8" })]));
      if (selectedSessionId && !rows.some((x) => String(x.session_id || "") === selectedSessionId)) {
        selectedSessionId = "";
        detailMessages = [];
        renderDetailMessages();
      }
      updateSessionPagers();
      return;
    }
    rows.forEach((r) => {
      const sid = String(r.session_id || "");
      const btnMore = el("button", {
        class: "chat-sess-more" + (sid === selectedSessionId ? " chat-sess-more--active" : ""),
        text: "⋯",
        title: t("chat.sessionMenu"),
        onclick: (ev) => {
          ev.stopPropagation();
          closeSessionMenu();
          const menu = el("div", { class: "chat-sess-menu-pop u-overlay-fixed" }, [
            el("button", {
              class: "chat-sess-menu-item",
              text: t("sessionMonitor.viewDetail"),
              onclick: async () => {
                closeSessionMenu();
                await loadSessionDetail(sid, { openModal: true });
              },
            }),
            el("button", {
              class: "chat-sess-menu-item",
              text: t("sessionMonitor.viewAudit"),
              onclick: () => {
                closeSessionMenu();
                location.hash = `#/audit?session_id=${encodeURIComponent(sid)}`;
              },
            }),
            el("button", {
              class: "chat-sess-menu-item",
              text: t("sessionMonitor.exportMd"),
              onclick: async () => {
                closeSessionMenu();
                await downloadSessionExport(sid, "md");
              },
            }),
            el("button", {
              class: "chat-sess-menu-item",
              text: t("sessionMonitor.exportJson"),
              onclick: async () => {
                closeSessionMenu();
                await downloadSessionExport(sid, "json");
              },
            }),
          ]);
          const rect = ev.currentTarget.getBoundingClientRect();
          document.body.appendChild(menu);
          // Clamp into viewport; flip above if near bottom.
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
          sessionMenuEl = menu;
          const close = (e) => {
            if (!menu.contains(e.target)) {
              closeSessionMenu();
              document.removeEventListener("click", close);
            }
          };
          setTimeout(() => document.addEventListener("click", close), 0);
        },
      });
      sessBody.appendChild(
        el(
          "tr",
          {
            "data-session-id": sid,
            class: sid === selectedSessionId ? "session-monitor-row--active" : "",
            onclick: async () => {
              selectedSessionId = sid;
              closeSessionMenu();
              const sessionRows = Array.from(sessBody.querySelectorAll("tr[data-session-id]"));
              sessionRows.forEach((tr) => {
                const curr = String(tr.getAttribute("data-session-id") || "");
                tr.classList.toggle("session-monitor-row--active", curr === selectedSessionId);
              });
            },
          },
          [
          tdCell(sid, 24),
          tdCell(r.title || "", 30),
          tdCell(r.username || "", 16),
          tdCell(r.message_count || "", 10),
          tdCell(r.last_message_at || "", 24),
          tdCell(r.is_active_30m ? "yes" : "no", 8),
          el("td", { class: "table__cell-actions" }, [btnMore]),
          ],
        ),
      );
    });
    updateSessionPagers();
  };

  const loadUsers = async () => {
    const p = new URLSearchParams();
    p.set("limit", "200");
    if (userQ.value.trim()) p.set("q", userQ.value.trim());
    const resp = await apiGet("/admin/api/chat/admin/user-stats?" + p.toString());
    renderTotals(resp.totals || {});
    const rows = Array.isArray(resp.users) ? resp.users : [];
    userBody.innerHTML = "";
    if (!rows.length) {
      userBody.appendChild(el("tr", {}, [el("td", { text: t("audit.empty"), colspan: "9" })]));
      selectedUserId = "";
      selectedSessionId = "";
      detailMessages = [];
      await loadSessions();
      return;
    }
    if (!selectedUserId || !rows.some((x) => String(x.user_id || "") === selectedUserId)) {
      selectedUserId = String(rows[0].user_id || "");
    }
    rows.forEach((r) => {
      const uid = String(r.user_id || "");
      const pickBtn = el("button", {
        class: "btn btn--small",
        "data-user-pick": "1",
        "data-user-id": uid,
        text: uid === selectedUserId ? "●" : "○",
        onclick: async () => {
          selectedUserId = uid;
          sessionOffset = 0;
          selectedSessionId = "";
          detailMessages = [];
          const pickBtns = Array.from(userBody.querySelectorAll("button[data-user-pick='1']"));
          pickBtns.forEach((btnEl) => {
            const id = String(btnEl.getAttribute("data-user-id") || "");
            btnEl.textContent = id === selectedUserId ? "●" : "○";
          });
          await loadSessions();
        },
      });
      userBody.appendChild(
        el("tr", {}, [
          el("td", {}, [pickBtn]),
          tdCell(r.username || "", 16),
          tdCell(r.display_name || "", 16),
          tdCell(r.role || "", 10),
          tdCell(r.sessions_count || "", 10),
          tdCell(r.active_sessions_30m || "", 10),
          tdCell(r.active_login_30m || "", 10),
          tdCell(r.total_tokens_est || "", 14),
          tdCell(r.last_message_at || "", 24),
        ]),
      );
    });
    await loadSessions();
  };

  const btnQueryUsers = el("button", { class: "btn btn--primary", text: t("audit.query"), onclick: loadUsers });
  const btnQuerySessions = el("button", {
    class: "btn",
    text: t("audit.query"),
    onclick: async () => {
      sessionOffset = 0;
      selectedSessionId = "";
      detailMessages = [];
      await loadSessions();
    },
  });
  const activeOnlyLabel = el("label", { class: "row" }, [
    activeOnlyChk,
    el("span", { class: "muted", text: t("sessionMonitor.activeSessions30m") }),
  ]);

  await loadUsers();
  rebuildDetailRoleFilter();
  const btnCloseDetail = el("button", {
    class: "btn btn--small",
    text: t("sessionMonitor.closeDetail"),
    onclick: () => {
      selectedSessionId = "";
      detailMessages = [];
      detailBody.innerHTML = "";
      detailStatus.textContent = t("sessionMonitor.noMessages");
      detailPager.innerHTML = "";
      closeDetailModal();
      loadSessions().catch(() => {});
    },
  });
  const detailTable = el("table", { class: "table table--compact session-monitor-detail-table" }, [
    el("thead", {}, [
      el("tr", {}, [
        el("th", { text: "id" }),
        el("th", { text: "role" }),
        el("th", { text: "content" }),
        el("th", { text: t("table.timestamp") }),
      ]),
    ]),
    detailBody,
  ]);
  detailModalCard.appendChild(
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("sessionMonitor.messages") }),
      el("div", { class: "row" }, [
        el("span", { class: "muted", text: t("sessionMonitor.roleFilter") }),
        detailRoleFilter,
        btnCloseDetail,
      ]),
      detailStatus,
      detailPager,
      el("div", { class: "table-wrap" }, [
        detailTable,
      ]),
    ]),
  );
  enableTableColumnResize(detailTable, [2, 3]);
  detailModal.appendChild(detailModalCard);
  detailModal.addEventListener("click", (ev) => {
    if (ev.target === detailModal) closeDetailModal();
  });
  return renderPageShell({
    title: t("title.sessionMonitor"),
    subtitle: "按用户、会话与消息详情进行巡检与导出",
    sections: [
      { id: "sm-totals", label: "总览" },
      { id: "sm-users", label: "用户" },
      { id: "sm-sessions", label: "会话" },
    ],
  }, [
    renderSectionCard(t("sessionMonitor.totals"), "", [totalsWrap], { id: "sm-totals" }),
    renderSectionCard(t("sessionMonitor.userStats"), "", [
      el("div", { class: "row" }, [userQ, btnQueryUsers]),
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact" }, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: "#" }),
              el("th", { text: t("table.username") }),
              el("th", { text: t("table.name") }),
              el("th", { text: t("tenants.role") }),
              el("th", { text: t("table.sessionsCount") }),
              el("th", { text: t("table.activeSessions30m") }),
              el("th", { text: t("table.activeLogins30m") }),
              el("th", { text: t("table.totalTokensEst") }),
              el("th", { text: t("table.timestamp") }),
            ]),
          ]),
          userBody,
        ]),
      ]),
    ], { id: "sm-users" }),
    renderSectionCard(t("sessionMonitor.sessions"), "", [
      el("div", { class: "row" }, [sessQ, activeOnlyLabel, btnQuerySessions]),
      selectedHint,
      sessionPagerTop,
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table table--compact session-monitor-session-table" }, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { text: "session_id" }),
              el("th", { text: t("table.name") }),
              el("th", { text: t("table.username") }),
              el("th", { text: "msg_count" }),
              el("th", { text: t("table.timestamp") }),
              el("th", { text: t("table.activeSessions30m") }),
              el("th", { text: t("table.action") }),
            ]),
          ]),
          sessBody,
        ]),
      ]),
      sessionPagerBottom,
    ], { id: "sm-sessions" }),
    detailModal,
  ]);
}


export { renderAdminAudit, renderSessionMonitor };
