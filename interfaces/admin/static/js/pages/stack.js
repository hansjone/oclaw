import { t, el, tdCell, apiGet, apiGetNoHang, apiPost, apiDeleteJson, formatSystemLocalDateTime, renderMetaChips, navigateAdmin, tf, runtimePrewarmReminder, clearPrewarmReminder } from "../core.js";

async function renderStack() {
  const results = await Promise.allSettled([
    apiGetNoHang("/admin/api/runtime/scan-artifacts"),
    apiGetNoHang("/admin/api/runtime/prewarm/status"),
    apiGetNoHang("/admin/api/runtime/prewarm/prompts?role=generalist"),
    apiGetNoHang("/admin/api/chat/settings/specialist-flags"),
    apiGetNoHang("/admin/api/chat/settings/channel-dispatch/weixin"),
    apiGetNoHang("/admin/api/chat/settings/channel-dispatch/whatsapp"),
    apiGetNoHang("/admin/api/whatsapp/groups?tenant_id=default"),
    apiGetNoHang("/admin/api/whatsapp/access?tenant_id=default"),
    apiGetNoHang("/admin/api/whatsapp/session"),
  ]);
  const scanResp = results[0].status === "fulfilled" ? results[0].value : null;
  const prewarmStatusResp = results[1].status === "fulfilled" ? results[1].value : null;
  const prewarmPromptsResp = results[2].status === "fulfilled" ? results[2].value : null;
  const channelSpecResp = results[3].status === "fulfilled" ? results[3].value : null;
  const weixinDispatchResp = results[4].status === "fulfilled" ? results[4].value : null;
  const whatsappDispatchResp = results[5].status === "fulfilled" ? results[5].value : null;
  const whatsappGroupsResp = results[6].status === "fulfilled" ? results[6].value : null;
  const whatsappAccessResp = results[7].status === "fulfilled" ? results[7].value : null;
  const whatsappSessionResp = results[8].status === "fulfilled" ? results[8].value : null;

  // If auth failed (401), show a gentle message instead of an infinite spinner.
  if (!channelSpecResp && !weixinDispatchResp && !prewarmStatusResp) {
    return el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("title.stack") || "Stack" }),
      el("div", { class: "muted", text: t("common.notLoggedIn") }),
    ]);
  }
  const availableDispatchSpecialists = Array.isArray(channelSpecResp && channelSpecResp.available_specialists) && channelSpecResp.available_specialists.length
    ? channelSpecResp.available_specialists.map((x) => String(x || "").trim()).filter(Boolean)
    : ["generalist"];
  const createChannelDispatchCard = (channel, title, initial) => {
    const curMode = String((initial && initial.interaction_mode) || "expert").trim() || "expert";
    const curSpecialist = String((initial && initial.specialist) || "generalist").trim() || "generalist";
    const curLang = String((initial && initial.lang) || "auto").trim().toLowerCase() || "auto";
    const specialistSel = el("select", { class: "input" }, availableDispatchSpecialists.map((sid) =>
      el("option", { value: sid, text: sid, selected: sid === curSpecialist ? "selected" : undefined }),
    ));
    const langSel = el("select", { class: "input" }, [
      el("option", { value: "auto", text: t("common.auto"), selected: curLang === "auto" ? "selected" : undefined }),
      el("option", { value: "zh", text: t("common.chinese"), selected: curLang === "zh" ? "selected" : undefined }),
      el("option", { value: "en", text: t("common.english"), selected: curLang === "en" ? "selected" : undefined }),
    ]);
    const status = renderMetaChips({ mode: curMode, specialist: curSpecialist, lang: curLang });
    const paintStatus = (obj) => {
      const fresh = renderMetaChips(obj);
      status.replaceChildren(...Array.from(fresh.childNodes));
    };
    const saveExpertBtn = el("button", {
      class: "btn btn--primary",
      text: t("wa.bindSpecialist"),
      onclick: async () => {
        const specialist = String(specialistSel.value || "generalist").trim() || "generalist";
        const lang = String(langSel.value || "auto").trim().toLowerCase() || "auto";
        const resp = await apiPost(`/admin/api/chat/settings/channel-dispatch/${encodeURIComponent(channel)}`, {
          interaction_mode: "expert",
          specialist,
          lang,
        });
        paintStatus({
          mode: String(resp.interaction_mode || "expert"),
          specialist: String(resp.specialist || specialist),
          lang: String(resp.lang || lang),
        });
      },
    });
    return el("div", { class: "card" }, [
      el("div", { class: "card__head" }, [
        el("div", { class: "card__headline" }, [
          el("div", { class: "card__title", text: title }),
          el("div", {
            class: "card__subtitle",
            text: t("wa.channelExpertOnly"),
          }),
        ]),
      ]),
      el("div", { class: "form-inline" }, [
        el("div", { class: "form-inline__field" }, [
          el("label", { text: t("wa.specialist") }),
          specialistSel,
        ]),
        el("div", { class: "form-inline__field" }, [
          el("label", { text: t("wa.lang") }),
          langSel,
        ]),
        el("div", { class: "form-inline__actions" }, [saveExpertBtn]),
      ]),
      status,
    ]);
  };
  const weixinDispatchCard = createChannelDispatchCard("weixin", "Weixin dispatch", weixinDispatchResp || {});
  const whatsappDispatchCard = createChannelDispatchCard("whatsapp", "WhatsApp dispatch", whatsappDispatchResp || {});
  let waSessionLatest = whatsappSessionResp && typeof whatsappSessionResp === "object" ? whatsappSessionResp : {};
  let waSessionBindInProgress = false;
  const waSessionHintAlert = el("div", { class: "alert alert--warning u-hidden", text: "" });
  const paintWaSession = (st) => {
    const s = st && typeof st === "object" ? st : {};
    waSessionLatest = s;
    const lifecycle = String(s.lifecycle || "unbound").trim() || "unbound";
    const lifeLabel = t(`wa.lifecycle.${lifecycle}`) || lifecycle;
    const chips = renderMetaChips({
      lifecycle: lifeLabel,
      connection: String(s.connection || "-"),
      phone: String(s.phone || "-"),
      sidecar: s.sidecar_running ? `pid ${s.pid || "-"}` : "stopped",
      reconnect: Number(s.reconnect_attempt || 0),
    });
    waSessionStatus.replaceChildren(...Array.from(chips.childNodes));
    const detailBits = [
      s.display_name ? `name=${s.display_name}` : "",
      s.me ? `me=${s.me}` : "",
      s.last_error ? `err=${String(s.last_error).slice(0, 120)}` : "",
      s.last_disconnect_reason ? `disconnect=${s.last_disconnect_reason}` : "",
      s.bridge_updated_at ? `updated=${s.bridge_updated_at}` : "",
    ].filter(Boolean);
    waSessionDetail.textContent = detailBits.join(" | ") || (s.installed ? "" : t("wa.sessionNotInstalled"));
    if (lifecycle === "needs_rebind" || lifecycle === "logged_out") {
      waSessionHintAlert.textContent = t("wa.sessionNeedsRebind");
      waSessionHintAlert.classList.remove("u-hidden");
    } else {
      waSessionHintAlert.textContent = "";
      waSessionHintAlert.classList.add("u-hidden");
    }
    const qrUrl = String(s.qr_data_url || "").trim();
    const awaiting = lifecycle === "awaiting_scan" || waSessionBindInProgress;
    waSessionQrWrap.style.display = awaiting ? "" : "none";
    waSessionQrHint.textContent = awaiting
      ? (s.qr_stale ? t("wa.sessionQrStale") : t("wa.sessionScanHint"))
      : "";
    if (awaiting && qrUrl) {
      waSessionQrImg.src = qrUrl;
      waSessionQrImg.style.display = "";
      waSessionQrWaiting.style.display = "none";
    } else if (awaiting) {
      waSessionQrImg.removeAttribute("src");
      waSessionQrImg.style.display = "none";
      waSessionQrWaiting.style.display = "";
      waSessionQrWaiting.textContent = t("wa.sessionQrWaiting");
    } else {
      waSessionQrImg.removeAttribute("src");
      waSessionQrImg.style.display = "none";
      waSessionQrWaiting.style.display = "none";
    }
    const bindModes = new Set(["unbound", "logged_out", "awaiting_scan", "needs_rebind"]);
    if (waSessionBindBtn) {
      waSessionBindBtn.textContent = bindModes.has(lifecycle)
        ? t("wa.sessionBind")
        : t("wa.sessionRebind");
      waSessionBindBtn.disabled = Boolean(waSessionBindInProgress);
    }
  };
  const waSessionStatus = el("div", { class: "muted" });
  const waSessionDetail = el("div", { class: "muted u-mt-8" });
  const waSessionBindBtn = el("button", {
    class: "btn btn--primary",
    text: t("wa.sessionBind"),
  });
  const waSessionQrImg = el("img", {
    alt: "WhatsApp QR",
    style: "width:240px;height:240px;background:#fff;border:1px solid var(--border, #ddd);display:none;",
  });
  const waSessionQrWaiting = el("div", { class: "muted", style: "display:none;" });
  const waSessionQrHint = el("div", { class: "card__hint" });
  const waSessionQrWrap = el("div", { class: "u-mt-10", style: "display:none;" }, [
    waSessionQrHint,
    waSessionQrImg,
    waSessionQrWaiting,
  ]);
  const waSessionActionStatus = el("div", { class: "muted u-mt-8", text: "" });
  const pollWaSession = async (opts = {}) => {
    const maxMs = Number(opts.maxMs || 60000);
    const stepMs = Number(opts.stepMs || 2000);
    const stopWhen = opts.stopWhen || ((st) => {
      const life = String((st && st.lifecycle) || "");
      return ["online", "awaiting_scan", "needs_rebind", "logged_out", "bound_stopped", "unbound"].includes(life);
    });
    waSessionActionStatus.textContent = t("wa.sessionPolling");
    let waited = 0;
    let latest = waSessionLatest;
    while (waited < maxMs) {
      const st = await apiGet("/admin/api/whatsapp/session");
      paintWaSession(st);
      latest = st;
      if (stopWhen(st)) break;
      await new Promise((r) => setTimeout(r, stepMs));
      waited += stepMs;
    }
    waSessionActionStatus.textContent = "";
    return latest;
  };
  const withWaSessionAction = async (fn, opts = {}) => {
    waSessionActionStatus.textContent = "…";
    try {
      const resp = await fn();
      const st = (resp && resp.status) || resp || {};
      paintWaSession(st.ok === false && !st.lifecycle ? (await apiGet("/admin/api/whatsapp/session")) : st);
      if (resp && resp.ok === false) {
        waSessionActionStatus.textContent = String(resp.error || resp.stderr || "failed");
      } else {
        waSessionActionStatus.textContent = "ok";
      }
      if (opts.poll !== false && resp && resp.ok !== false) {
        await pollWaSession(opts.poll || {});
      }
      return resp;
    } catch (err) {
      waSessionActionStatus.textContent = String(err);
      throw err;
    }
  };
  const waSessionRefreshBtn = el("button", {
    class: "btn",
    text: t("wa.sessionRefresh"),
    onclick: async () => {
      await withWaSessionAction(async () => apiGet("/admin/api/whatsapp/session"), { poll: false });
    },
  });
  const waSessionStartBtn = el("button", {
    class: "btn",
    text: t("wa.sessionStart"),
    onclick: async () => {
      await withWaSessionAction(async () => apiPost("/admin/api/whatsapp/session/start", {}));
    },
  });
  const waSessionStopBtn = el("button", {
    class: "btn",
    text: t("wa.sessionStop"),
    onclick: async () => {
      await withWaSessionAction(async () => apiPost("/admin/api/whatsapp/session/stop", { force: true }), { poll: false });
    },
  });
  const waSessionBindBtnClick = async () => {
    const curLife = String((waSessionLatest && waSessionLatest.lifecycle) || "").trim();
    const autoClear = ["needs_rebind", "logged_out"].includes(curLife);
    const needClear = autoClear || (curLife && !["unbound", "awaiting_scan"].includes(curLife));
    if (needClear && !autoClear && !window.confirm(t("wa.sessionRebindConfirm"))) return;
    waSessionBindInProgress = true;
    paintWaSession(waSessionLatest);
    try {
      await withWaSessionAction(async () => apiPost("/admin/api/whatsapp/session/bind", {
        clear_auth: Boolean(needClear),
      }), {
        poll: {
          maxMs: 120000,
          stopWhen: (st) => {
            const life = String((st && st.lifecycle) || "");
            if (life === "online") return true;
            return life === "awaiting_scan" && Boolean(st && (st.qr_data_url || st.qr));
          },
        },
      });
    } finally {
      waSessionBindInProgress = false;
      paintWaSession(waSessionLatest);
    }
  };
  waSessionBindBtn.onclick = waSessionBindBtnClick;
  const waSessionUnbindBtn = el("button", {
    class: "btn btn--danger",
    text: t("wa.sessionUnbind"),
    onclick: async () => {
      if (!window.confirm(t("wa.sessionUnbindConfirm"))) return;
      await withWaSessionAction(async () => apiPost("/admin/api/whatsapp/session/unbind", {}), { poll: false });
    },
  });
  const whatsappSessionCard = el("div", { class: "card" }, [
    el("div", { class: "card__head" }, [
      el("div", { class: "card__headline" }, [
        el("div", { class: "card__title", text: t("wa.sessionTitle") }),
        el("div", { class: "card__subtitle", text: t("wa.sessionHint") }),
      ]),
      el("div", { class: "card__actions" }, [
        waSessionRefreshBtn,
        waSessionStartBtn,
        waSessionStopBtn,
        waSessionBindBtn,
        waSessionUnbindBtn,
      ]),
    ]),
    waSessionStatus,
    waSessionHintAlert,
    waSessionDetail,
    waSessionQrWrap,
    waSessionActionStatus,
  ]);
  paintWaSession(whatsappSessionResp || {});
  if (whatsappSessionResp && whatsappSessionResp.sidecar_running) {
    const initLife = String(whatsappSessionResp.lifecycle || "");
    if (["connecting", "bound_offline"].includes(initLife)) {
      void pollWaSession({ maxMs: 30000 });
    }
  }
  const waGroups = Array.isArray(whatsappGroupsResp && whatsappGroupsResp.items) ? whatsappGroupsResp.items : [];
  const waBinding = (whatsappGroupsResp && whatsappGroupsResp.binding) || {};
  const waGroupSel = el(
    "select",
    { class: "input" },
    [
      el("option", { value: "", text: t("wa.selectGroup") }),
      ...waGroups.map((g) => {
        const jid = String((g && g.group_jid) || "").trim();
        const name = String((g && g.group_name) || "").trim();
        const label = name ? `${name} (${jid})` : jid;
        return el("option", {
          value: jid,
          text: label || jid,
          selected: jid && jid === String(waBinding.group_jid || "") ? "selected" : undefined,
        });
      }),
    ],
  );
  const waBindingStatus = el("div", {
    class: "muted",
    text: waBinding.group_jid
      ? `binding=${waBinding.group_jid} enabled=${Boolean(waBinding.enabled)}`
      : (t("wa.noAlertGroup")),
  });
  const waAccessCfg = (whatsappAccessResp && whatsappAccessResp.config) || {};
  const waContacts = Array.isArray(whatsappAccessResp && whatsappAccessResp.contacts) ? whatsappAccessResp.contacts : [];
  const waPending = Array.isArray(whatsappAccessResp && whatsappAccessResp.pending) ? whatsappAccessResp.pending : [];
  const waDenied = Array.isArray(whatsappAccessResp && whatsappAccessResp.denied) ? whatsappAccessResp.denied : [];
  const waPhoneDisplay = (row) => {
    const phone = String((row && row.phone) || "").trim();
    if (phone) return phone;
    const jid = String((row && row.external_user_id) || "").trim();
    const base = jid.split("@")[0] || "";
    const digits = base.replace(/\D/g, "");
    return digits || base || "-";
  };
  const waAccessModeSel = el("select", { class: "input" }, [
    el("option", {
      value: "blacklist",
      text: t("wa.blacklistMode"),
      selected: String(waAccessCfg.access_mode || "blacklist") === "blacklist" ? "selected" : undefined,
    }),
    el("option", {
      value: "whitelist",
      text: t("wa.whitelistMode"),
      selected: String(waAccessCfg.access_mode || "") === "whitelist" ? "selected" : undefined,
    }),
  ]);
  const waAccessLangSel = el("select", { class: "input" }, [
    el("option", { value: "en", text: "English", selected: String(waAccessCfg.lang || "en") === "en" ? "selected" : undefined }),
    el("option", { value: "zh", text: t("common.chinese"), selected: String(waAccessCfg.lang || "") === "zh" ? "selected" : undefined }),
  ]);
  const waCounts = { admin: 0, whitelist: 0, blacklist: 0 };
  waContacts.forEach((c) => {
    const lt = String((c && c.list_type) || "").trim().toLowerCase();
    if (lt === "admin") waCounts.admin += 1;
    else if (lt === "whitelist") waCounts.whitelist += 1;
    else if (lt === "blacklist") waCounts.blacklist += 1;
  });
  const waAccessStatus = renderMetaChips({
    mode: String(waAccessCfg.access_mode || "blacklist"),
    lang: String(waAccessCfg.lang || "en"),
    admin: waCounts.admin,
    whitelist: waCounts.whitelist,
    blacklist: waCounts.blacklist,
    pending: waPending.length,
    denied: waDenied.length,
  });
  const waContactFilterSel = el("select", { class: "input" }, [
    el("option", { value: "all", text: t("common.all") }),
    el("option", { value: "admin", text: t("common.admin") }),
    el("option", { value: "whitelist", text: t("common.whitelist") }),
    el("option", { value: "blacklist", text: t("common.blacklist") }),
  ]);
  const waContactsTbody = el("tbody", {});
  const waContactPhone = (row) => {
    const phone = String((row && row.phone) || "").trim();
    if (phone) return phone;
    return waPhoneDisplay(row);
  };
  const waSaveContact = async (phone, pushName, listType) => {
    const phoneVal = String(phone || "").trim();
    const list_type = String(listType || "").trim().toLowerCase();
    if (!phoneVal) return;
    if (!list_type) {
      window.alert(t("common.selectType"));
      return;
    }
    try {
      const resp = await apiPost("/admin/api/whatsapp/access/contacts", {
        phone: phoneVal,
        push_name: String(pushName || "").trim(),
        list_type,
      });
      if (!resp || resp.ok === false) {
        window.alert(String((resp && resp.error) || (t("common.updateFailed"))));
        return;
      }
      navigateAdmin();
    } catch (err) {
      window.alert(String(err));
    }
  };
  const renderWaContactRows = (filterValue) => {
    const filter = String(filterValue || "all").trim().toLowerCase() || "all";
    const rows = waContacts
      .filter((c) => {
        const lt = String((c && c.list_type) || "").trim().toLowerCase();
        if (filter === "all") return true;
        return lt === filter;
      })
      .map((c) => {
        const name = String((c && c.push_name) || "");
        const lt = String((c && c.list_type) || "").trim().toLowerCase();
        const phone = waContactPhone(c);
        const typeSel = el("select", { class: "input" }, [
          el("option", { value: "admin", text: t("common.admin") }),
          el("option", { value: "whitelist", text: t("common.whitelist") }),
          el("option", { value: "blacklist", text: t("common.blacklist") }),
        ]);
        typeSel.value = lt || "whitelist";
        const actionBtns = [
          el("button", {
            class: "btn",
            text: t("common.update"),
            onclick: async () => {
              await waSaveContact(phone, name, String(typeSel.value || "").trim());
            },
          }),
        ];
        if (lt === "blacklist") {
          actionBtns.push(el("span", { text: " " }));
          actionBtns.push(el("button", {
            class: "btn btn--primary",
            text: t("wa.addWhitelist"),
            onclick: async () => {
              await waSaveContact(phone, name, "whitelist");
            },
          }));
        }
        actionBtns.push(el("span", { text: " " }));
        actionBtns.push(el("button", {
          class: "btn btn--danger",
          text: t("common.remove"),
          onclick: async () => {
            try {
              const resp = await apiDeleteJson(
                `/admin/api/whatsapp/access/contacts?phone=${encodeURIComponent(phone)}`,
              );
              if (resp && resp.deleted === false) {
                window.alert(t("wa.contactNotFound"));
                return;
              }
              navigateAdmin();
            } catch (err) {
              window.alert(String(err));
            }
          },
        }));
        return el("tr", {}, [
          el("td", { "data-copy-disabled": "1" }, [typeSel]),
          el("td", { text: name || "-" }),
          el("td", { text: phone || "-" }),
          el("td", { "data-copy-disabled": "1" }, actionBtns),
        ]);
      });
    waContactsTbody.replaceChildren(
      ...(rows.length
        ? rows
        : [el("tr", {}, [el("td", { colspan: "4", text: t("wa.noContacts") })])]),
    );
  };
  waContactFilterSel.addEventListener("change", () => {
    renderWaContactRows(String(waContactFilterSel.value || "all"));
  });
  renderWaContactRows("all");
  const waContactPhoneInput = el("input", { class: "input", placeholder: t("wa.phonePlaceholder") });
  const waContactNameInput = el("input", { class: "input", placeholder: t("wa.namePlaceholder") });
  const waContactTypeSel = el("select", { class: "input" }, [
    el("option", { value: "admin", text: t("common.admin") }),
    el("option", { value: "whitelist", text: t("common.whitelist") }),
    el("option", { value: "blacklist", text: t("common.blacklist") }),
  ]);
  const waPendingPickSel = el(
    "select",
    { class: "input" },
    [
      el("option", { value: "", text: t("wa.pickPending") }),
      ...waPending.map((p, idx) => {
        const phone = waPhoneDisplay(p);
        const name = String((p && p.push_name) || "").trim();
        const label = name ? `${name} (${phone})` : phone;
        return el("option", { value: String(idx), text: label || phone });
      }),
    ],
  );
  waPendingPickSel.addEventListener("change", () => {
    const idx = Number(String(waPendingPickSel.value || "").trim());
    if (!Number.isFinite(idx) || idx < 0 || idx >= waPending.length) return;
    const picked = waPending[idx] || {};
    const phone = waPhoneDisplay(picked);
    const name = String((picked && picked.push_name) || "").trim();
    if (phone && phone !== "-") waContactPhoneInput.value = phone;
    waContactNameInput.value = name || "";
  });
  const waResolvePending = async (pendingId, action) => {
    if (!pendingId) return;
    try {
      const resp = await apiPost("/admin/api/whatsapp/access/pending/resolve", {
        pending_id: pendingId,
        action,
      });
      if (!resp || resp.ok === false) {
        window.alert(String((resp && resp.error) || (t("common.requestFailed"))));
        return;
      }
      navigateAdmin();
    } catch (err) {
      window.alert(String(err));
    }
  };
  const waDeletePending = async (pendingId) => {
    if (!pendingId) return;
    try {
      const resp = await apiDeleteJson(
        `/admin/api/whatsapp/access/pending?pending_id=${encodeURIComponent(pendingId)}`,
      );
      if (!resp || resp.ok === false) {
        window.alert(String((resp && resp.error) || (t("common.deleteFailed"))));
        return;
      }
      navigateAdmin();
    } catch (err) {
      window.alert(String(err));
    }
  };
  const waDeniedRows = waDenied.map((p) => {
    const pendingId = String((p && p.id) || "").trim();
    const phone = waPhoneDisplay(p);
    const name = String((p && p.push_name) || "").trim();
    return el("tr", {}, [
      el("td", { text: name || "-" }),
      el("td", { text: phone }),
      el("td", { text: String((p && p.request_text) || "").slice(0, 80) }),
      el("td", { text: String((p && p.resolved_at) || p.created_at || "") }),
      el("td", {}, [
        el("button", {
          class: "btn btn--primary",
          text: t("wa.addWhitelist"),
          onclick: async () => { await waResolvePending(pendingId, "approve"); },
        }),
        el("span", { text: " " }),
        el("button", {
          class: "btn btn--danger",
          text: t("common.delete"),
          onclick: async () => { await waDeletePending(pendingId); },
        }),
      ]),
    ]);
  });
  const waPendingRows = waPending.map((p) => {
    const pendingId = String((p && p.id) || "").trim();
    return el("tr", {}, [
      el("td", { text: String((p && p.push_name) || "-") }),
      el("td", { text: waPhoneDisplay(p) }),
      el("td", { text: String((p && p.external_user_id) || "") }),
      el("td", { text: String((p && p.request_text) || "").slice(0, 80) }),
      el("td", { text: String((p && p.created_at) || "") }),
      el("td", {}, [
        el("button", {
          class: "btn btn--primary",
          text: t("wa.approve"),
          onclick: async () => { await waResolvePending(pendingId, "approve"); },
        }),
        el("span", { text: " " }),
        el("button", {
          class: "btn",
          text: t("wa.deny"),
          onclick: async () => { await waResolvePending(pendingId, "deny"); },
        }),
        el("span", { text: " " }),
        el("button", {
          class: "btn btn--danger",
          text: t("common.delete"),
          onclick: async () => { await waDeletePending(pendingId); },
        }),
      ]),
    ]);
  });
  const whatsappAccessCard = el("div", { class: "card" }, [
    el("div", { class: "card__head" }, [
      el("div", { class: "card__headline" }, [
        el("div", { class: "card__title", text: t("wa.accessTitle") }),
        el("div", {
          class: "card__subtitle",
          text: t("wa.accessHint"),
        }),
      ]),
    ]),
    el("div", { class: "form-inline" }, [
      el("div", { class: "form-inline__field" }, [
        el("label", { text: t("common.mode") }),
        waAccessModeSel,
      ]),
      el("div", { class: "form-inline__field" }, [
        el("label", { text: t("wa.messageLang") }),
        waAccessLangSel,
      ]),
      el("div", { class: "form-inline__actions" }, [
        el("button", {
          class: "btn btn--primary",
          text: t("wa.saveConfig"),
          onclick: async () => {
            const resp = await apiPost("/admin/api/whatsapp/access/config", {
              tenant_id: "default",
              access_mode: String(waAccessModeSel.value || "blacklist"),
              lang: String(waAccessLangSel.value || "en"),
            });
            const cfg = (resp && resp.config) || {};
            waAccessStatus.replaceChildren(
              ...Array.from(
                renderMetaChips({
                  mode: String(cfg.access_mode || "blacklist"),
                  lang: String(cfg.lang || "en"),
                  admin: waCounts.admin,
                  whitelist: waCounts.whitelist,
                  blacklist: waCounts.blacklist,
                  pending: waPending.length,
                  denied: waDenied.length,
                }).childNodes,
              ),
            );
          },
        }),
      ]),
    ]),
    waAccessStatus,
    el("div", { class: "form-inline" }, [
      el("div", { class: "form-inline__field" }, [
        el("label", { text: t("wa.filter") }),
        waContactFilterSel,
      ]),
    ]),
    el("div", { class: "form-inline" }, [
      el("div", { class: "form-inline__field form-inline__field--wide" }, [waPendingPickSel]),
    ]),
    el("div", { class: "form-inline" }, [
      el("div", { class: "form-inline__field" }, [waContactPhoneInput]),
      el("div", { class: "form-inline__field" }, [waContactNameInput]),
      el("div", { class: "form-inline__field" }, [waContactTypeSel]),
      el("div", { class: "form-inline__actions" }, [
        el("button", {
          class: "btn",
          text: t("wa.addContact"),
          onclick: async () => {
            const phone = String(waContactPhoneInput.value || "").trim();
            if (!phone) return;
            try {
              const resp = await apiPost("/admin/api/whatsapp/access/contacts", {
                phone,
                push_name: String(waContactNameInput.value || "").trim(),
                list_type: String(waContactTypeSel.value || "whitelist"),
              });
              if (!resp || resp.ok === false) {
                window.alert(String((resp && resp.error) || (t("wa.addFailed"))));
                return;
              }
              navigateAdmin();
            } catch (err) {
              window.alert(String(err));
            }
          },
        }),
      ]),
    ]),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("wa.colType") }),
          el("th", { text: t("wa.colName") }),
          el("th", { text: t("wa.colPhone") }),
          el("th", { text: t("wa.colAction") }),
        ])]),
        waContactsTbody,
      ]),
    ]),
    el("div", { class: "card__title", text: t("wa.pendingTitle") }),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("wa.colName") }),
          el("th", { text: t("wa.colPhone") }),
          el("th", { text: "JID" }),
          el("th", { text: t("wa.colMessage") }),
          el("th", { text: t("wa.colTime") }),
          el("th", { text: t("wa.colAction") }),
        ])]),
        el("tbody", {}, waPendingRows.length ? waPendingRows : [el("tr", {}, [el("td", { colspan: "6", text: t("wa.nonePending") })])]),
      ]),
    ]),
    el("div", { class: "card__title", text: t("wa.deniedTitle") }),
    el("div", { class: "card__hint", text: t("wa.deniedHint") }),
    el("div", { class: "table-wrap" }, [
      el("table", { class: "table" }, [
        el("thead", {}, [el("tr", {}, [
          el("th", { text: t("wa.colName") }),
          el("th", { text: t("wa.colPhone") }),
          el("th", { text: t("wa.colMessage") }),
          el("th", { text: t("wa.colDeniedAt") }),
          el("th", { text: t("wa.colAction") }),
        ])]),
        el("tbody", {}, waDeniedRows.length ? waDeniedRows : [el("tr", {}, [el("td", { colspan: "5", text: t("wa.noneDenied") })])]),
      ]),
    ]),
  ]);
  const whatsappAlertBindingCard = el("div", { class: "card" }, [
    el("div", { class: "card__head" }, [
      el("div", { class: "card__headline" }, [
        el("div", { class: "card__title", text: t("wa.alertGroupTitle") }),
        el("div", {
          class: "card__subtitle",
          text: t("wa.alertGroupHint"),
        }),
      ]),
    ]),
    el("div", { class: "form-inline" }, [
      el("div", { class: "form-inline__field form-inline__field--wide" }, [waGroupSel]),
      el("div", { class: "form-inline__actions" }, [
        el("button", {
          class: "btn btn--primary",
          text: t("wa.saveBinding"),
          onclick: async () => {
            const group_jid = String(waGroupSel.value || "").trim();
            if (!group_jid) return;
            const picked = waGroups.find((g) => String((g && g.group_jid) || "").trim() === group_jid) || {};
            const resp = await apiPost("/admin/api/whatsapp/alert-binding", {
              tenant_id: "default",
              group_jid,
              group_name: String((picked && picked.group_name) || ""),
              enabled: true,
            });
            const b = (resp && resp.binding) || {};
            waBindingStatus.textContent = b.group_jid
              ? `binding=${b.group_jid} enabled=${Boolean(b.enabled)}`
              : (t("wa.bindFailed"));
          },
        }),
        el("button", {
          class: "btn",
          text: t("wa.testPush"),
          onclick: async () => {
            const resp = await apiPost("/admin/api/whatsapp/alert-binding/test", { tenant_id: "default" });
            waBindingStatus.textContent = resp && resp.ok
              ? `test ok outbound_id=${String(resp.outbound_id || "")}`
              : `test failed: ${String((resp && resp.error) || "unknown")}`;
          },
        }),
      ]),
    ]),
    waBindingStatus,
  ]);
  const scanItems = Array.isArray(scanResp && scanResp.items) ? scanResp.items : [];
  const scanDir = String((scanResp && scanResp.dir) || "");
  const scanStatus = el("div", { class: "muted", text: "" });
  const keepLatestInput = el("input", { class: "input", type: "number", value: "20", min: "0", max: "500" });
  const maxAgeDaysInput = el("input", { class: "input", type: "number", value: "7", min: "0", max: "3650" });
  const btnCleanScan = el("button", {
    class: "btn btn--danger",
    text: t("stack.clearScanCache"),
    onclick: async () => {
      const resp = await apiPost("/admin/api/runtime/scan-artifacts/cleanup", {});
      scanStatus.textContent = `removed=${Number((resp && resp.removed) || 0)}`;
      navigateAdmin();
    },
  });
  const btnPruneScan = el("button", {
    class: "btn",
    text: t("stack.clearByPolicy"),
    onclick: async () => {
      const keepLatest = Number(keepLatestInput.value || 20);
      const maxAgeDays = Number(maxAgeDaysInput.value || 7);
      const resp = await apiPost("/admin/api/runtime/scan-artifacts/prune", {
        keep_latest: Number.isFinite(keepLatest) ? keepLatest : 20,
        max_age_days: Number.isFinite(maxAgeDays) ? maxAgeDays : 7,
      });
      scanStatus.textContent = `removed=${Number((resp && resp.removed) || 0)} keep_latest=${Number((resp && resp.keep_latest) || 0)} max_age_days=${Number((resp && resp.max_age_days) || 0)}`;
      navigateAdmin();
    },
  });
  const scanRows = scanItems.length
    ? scanItems.map((x) => el("tr", {}, [
        tdCell(String(x.name || ""), 26),
        tdCell(String(x.bytes || 0), 12),
        tdCell(String(x.modified_at || ""), 28),
      ]))
    : [el("tr", {}, [el("td", { class: "muted", text: "—", colspan: "3" })])];
  const prewarmInfo = prewarmStatusResp && typeof prewarmStatusResp === "object" ? prewarmStatusResp : {};
  const prewarmLast = prewarmInfo.last && typeof prewarmInfo.last === "object" ? prewarmInfo.last : {};
  const prewarmHistory = Array.isArray(prewarmInfo.history) ? prewarmInfo.history : [];
  const freeze = prewarmInfo.freeze && typeof prewarmInfo.freeze === "object" ? prewarmInfo.freeze : {};
  const prewarmStatus = el("div", { class: "muted", text: "" });
  const btnPrewarm = el("button", {
    class: "btn btn--primary",
    text: t("stack.prewarmNow"),
    onclick: async () => {
      prewarmStatus.textContent = t("stack.prewarmSubmitting");
      const resp = await apiPost("/admin/api/runtime/prewarm", { mode: "async", reason: "admin_manual" });
      if (!(resp && resp.accepted)) {
        prewarmStatus.textContent = `[prewarm] accepted=${Boolean(resp && resp.accepted)}`;
        return;
      }
      prewarmStatus.textContent =
        t("auto.prewarm_running_in_background_refreshing_this_page_when_");
      clearPrewarmReminder();
      const maxWaitMs = 120000;
      const stepMs = 400;
      let waited = 0;
      while (waited < maxWaitMs) {
        await new Promise((r) => setTimeout(r, stepMs));
        waited += stepMs;
        const st = await apiGet("/admin/api/runtime/prewarm/status");
        if (!(st && st.running)) break;
      }
      await navigateAdmin();
    },
  });
  const prewarmSummary = [
    `running=${Boolean(prewarmInfo.running)}`,
    `last_ok=${Boolean(prewarmLast.ok)}`,
    `elapsed_ms=${Number(prewarmLast.elapsed_ms || 0)}`,
    `freeze_enabled=${Boolean(freeze.enabled)}`,
    `frozen=${Boolean(freeze.frozen)}`,
    `last_warm=${
      Number(freeze.last_warm_ts_ms || 0) > 0
        ? formatSystemLocalDateTime(new Date(Number(freeze.last_warm_ts_ms || 0)).toISOString())
        : "-"
    }`,
  ].join(" | ");
  const historyRows = prewarmHistory.length
    ? prewarmHistory.slice(0, 20).map((x) =>
        el("tr", {}, [
          tdCell(formatSystemLocalDateTime(new Date(Number(x.finished_at_ms || 0)).toISOString()), 24),
          tdCell(String(x.reason || "-"), 20),
          tdCell(String(Boolean(x.ok)), 8),
          tdCell(String(Number(x.elapsed_ms || 0)), 10),
          tdCell(String(x.error || "-"), 38),
        ]))
    : [el("tr", {}, [el("td", { class: "muted", text: "—", colspan: "5" })])];
  const promptsSectionBody = el("div");
  const promptsRoleSelect = el("select", { class: "input" }, [
    el("option", { value: "generalist", text: "generalist (default)" }),
    el("option", { value: "", text: t("stack.allRoles") }),
  ]);
  const renderPromptCards = (resp) => {
    const promptsObj = resp && typeof resp === "object" ? resp : {};
    const promptsMap = promptsObj.prompts && typeof promptsObj.prompts === "object" ? promptsObj.prompts : {};
    const promptRoleCards = Object.keys(promptsMap)
    .sort((a, b) => String(a).localeCompare(String(b)))
    .map((rid) => {
      const item = promptsMap[rid] && typeof promptsMap[rid] === "object" ? promptsMap[rid] : {};
      const finalSystem = String(item.system_prompt || "");
      return el("div", { class: "card u-mt-10" }, [
        el("div", { class: "card__title", text: `role: ${rid}` }),
        el("div", {}, [
          el("div", { class: "muted", text: "system_prompt" }),
          el("textarea", {
            class: "input",
            rows: "12",
            readonly: "readonly",
            text: finalSystem,
            style: "width:100%;box-sizing:border-box;",
          }),
        ]),
      ]);
      });
    promptsSectionBody.innerHTML = "";
    if (promptRoleCards.length) {
      promptRoleCards.forEach((n) => promptsSectionBody.appendChild(n));
    } else {
      promptsSectionBody.appendChild(el("div", { class: "muted", text: "-" }));
    }
  };
  const btnReloadPrompts = el("button", {
    class: "btn",
    text: t("stack.reloadPrompts"),
    onclick: async () => {
      const role = String(promptsRoleSelect.value || "").trim();
      const q = role ? `?role=${encodeURIComponent(role)}` : "";
      const resp = await apiGet(`/admin/api/runtime/prewarm/prompts${q}`);
      renderPromptCards(resp);
    },
  });
  promptsRoleSelect.addEventListener("change", async () => {
    const role = String(promptsRoleSelect.value || "").trim();
    const q = role ? `?role=${encodeURIComponent(role)}` : "";
    const resp = await apiGet(`/admin/api/runtime/prewarm/prompts${q}`);
    renderPromptCards(resp);
  });
  renderPromptCards(prewarmPromptsResp);
  return el("div", { class: "page-shell" }, [
    el("div", { class: "page-grid page-grid--two" }, [
      weixinDispatchCard,
      whatsappDispatchCard,
    ]),
    whatsappSessionCard,
    whatsappAccessCard,
    whatsappAlertBindingCard,
    el("div", { class: "card" }, [
      el("div", { class: "card__head" }, [
        el("div", { class: "card__headline" }, [
          el("div", { class: "card__title", text: t("stack.prewarmTitle") }),
          el("div", { class: "card__subtitle", text: prewarmSummary }),
        ]),
        el("div", { class: "card__actions" }, [btnPrewarm]),
      ]),
      runtimePrewarmReminder ? el("div", { class: "alert alert--warning", text: runtimePrewarmReminder }) : null,
      el(
        "div",
        {
          class: "card__hint",
          text:
            t("auto.after_any_skill_tool_role_prompt_change_run_prewarm_imme"),
        },
      ),
      prewarmStatus,
    ].filter(Boolean)),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("stack.prewarmHistory") }),
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", { text: "finished_at" }),
            el("th", { text: "reason" }),
            el("th", { text: "ok" }),
            el("th", { text: "elapsed_ms" }),
            el("th", { text: "error" }),
          ])]),
          el("tbody", {}, historyRows),
        ]),
      ]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__head" }, [
        el("div", { class: "card__headline" }, [
          el("div", { class: "card__title", text: t("stack.prewarmedPrompts") }),
          el("div", {
            class: "card__subtitle",
            text: t("stack.prewarmedPromptsHint"),
          }),
        ]),
      ]),
      el("div", { class: "form-inline" }, [
        el("div", { class: "form-inline__field" }, [
          el("label", { text: t("stack.roleFilter") }),
          promptsRoleSelect,
        ]),
        el("div", { class: "form-inline__actions" }, [btnReloadPrompts]),
      ]),
      promptsSectionBody,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__head" }, [
        el("div", { class: "card__headline" }, [
          el("div", { class: "card__title", text: t("stack.scanCacheTitle") }),
          el("div", { class: "card__subtitle", text: tf("stack.scanCacheSubtitle", { dir: scanDir || "-" }) }),
        ]),
      ]),
      el("div", { class: "form-inline" }, [
        el("div", { class: "form-inline__field" }, [
          el("label", { text: "keep_latest" }),
          keepLatestInput,
        ]),
        el("div", { class: "form-inline__field" }, [
          el("label", { text: "max_age_days" }),
          maxAgeDaysInput,
        ]),
        el("div", { class: "form-inline__actions" }, [btnPruneScan, btnCleanScan]),
      ]),
      scanStatus,
      el("div", { class: "table-wrap" }, [
        el("table", { class: "table" }, [
          el("thead", {}, [el("tr", {}, [el("th", { text: "name" }), el("th", { text: "bytes" }), el("th", { text: "modified_at" })])]),
          el("tbody", {}, scanRows),
        ]),
      ]),
    ]),
  ]);
}


export { renderStack };
