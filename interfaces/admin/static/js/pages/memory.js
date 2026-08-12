import { t, el, tdCell, apiGet, apiPost, CHAT_MEMORY_MODE_KEY, navigateAdmin } from "../core.js";

async function renderMemory() {
  const route = getRoute();
  const tenantQ = route.params.get("tenant_id") || "";
  const userQ = route.params.get("user_id") || "";
  const buildQS = (limit = 50) => {
    const p = new URLSearchParams();
    p.set("limit", String(limit));
    if (tenantInput.value.trim()) p.set("tenant_id", tenantInput.value.trim());
    if (userInput.value.trim()) p.set("user_id", userInput.value.trim());
    return p.toString();
  };

  const tenantInput = el("input", { class: "input", placeholder: t("memory.tenantId"), value: tenantQ });
  const userInput = el("input", { class: "input", placeholder: t("memory.userId"), value: userQ });
  const status = el("div", { class: "muted", text: "" });
  const statsWrap = el("div", { class: "muted", text: "" });
  const hitsWrap = el("div");
  const itemsWrap = el("div");
  const wikiStatus = el("div", { class: "muted", text: "" });
  const memoryModeSelect = el("select", { class: "input", style: "max-width:320px;" });
  memoryModeSelect.appendChild(el("option", { value: "default", text: t("profile.memoryModeDefault") }));
  memoryModeSelect.appendChild(el("option", { value: "store_only", text: t("profile.memoryModeStoreOnly") }));
  const memoryCuratorSelect = el("select", { class: "input", style: "max-width:220px;" });
  memoryCuratorSelect.appendChild(el("option", { value: "1", text: t("profile.memoryCuratorEnabled") }));
  memoryCuratorSelect.appendChild(el("option", { value: "0", text: t("profile.memoryCuratorDisabled") }));

  const normalizeMemoryMode = (raw) => {
    const mm = String(raw || "").trim().toLowerCase();
    return mm === "store_only" ? "store_only" : "default";
  };

  const enabled = el("input", { type: "checkbox" });
  const backend = el("select", { class: "input" }, [
    el("option", { value: "sqlite", text: "sqlite" }),
  ]);
  const topk = el("input", { class: "input", type: "number", value: "5", min: "1", max: "20" });
  const writerEnabled = el("input", { type: "checkbox" });
  const ragMode = el("select", { class: "input" }, [
    el("option", { value: "keyword", text: "keyword" }),
    el("option", { value: "vector", text: "vector" }),
  ]);
  const embeddingMode = el("select", { class: "input" }, [
    el("option", { value: "", text: "openai(default/fallback)" }),
    el("option", { value: "openai", text: "openai" }),
    el("option", { value: "hash", text: "hash/offline" }),
  ]);
  const episodicTtlDays = el("input", { class: "input", type: "number", value: "90", min: "1", max: "3650" });
  const minConf = el("input", {
    class: "input",
    type: "number",
    value: "0.75",
    min: "0",
    max: "1",
    step: "0.05",
  });
  const btnSave = el("button", { class: "btn btn--primary", text: t("memory.save"), onclick: async () => {
    const saved = await apiPost("/admin/api/memory/config", {
      enabled: enabled.checked,
      backend: backend.value,
      top_k: Number(topk.value || 5),
      writer_enabled: writerEnabled.checked,
      write_min_confidence: Number(minConf.value || 0.75),
      rag_mode: String(ragMode.value || "keyword"),
      rag_embedding_mode: String(embeddingMode.value || ""),
      memory_episodic_ttl_days: Number(episodicTtlDays.value || 90),
    });
    localStorage.setItem(CHAT_MEMORY_MODE_KEY, normalizeMemoryMode(memoryModeSelect.value));
    await apiPost("/admin/api/chat/settings/specialist-flags", {
      flags: {
        generalist: true,
        memory: String(memoryCuratorSelect.value || "1") !== "0",
      },
    });
    status.textContent = JSON.stringify(saved.config || {});
  }});
  const btnReindex = el("button", { class: "btn", text: t("memory.reindex"), onclick: async () => {
    const resp = await apiPost("/admin/api/memory/reindex", {});
    status.textContent = `reindexed=${Number(resp.reindexed || 0)}`;
  }});
  const btnCleanup = el("button", { class: "btn btn--danger", text: t("memory.cleanup"), onclick: async () => {
    const resp = await apiPost("/admin/api/memory/cleanup-low-confidence", { max_confidence: 0.35 });
    status.textContent = `deleted=${Number(resp.deleted || 0)}`;
    navigateAdmin();
  }});

  const loadData = async () => {
    const qs = buildQS(50);
    const [cfgResp, hitsResp, itemsResp, statsResp] = await Promise.all([
      apiGet("/admin/api/memory/config"),
      apiGet("/admin/api/memory/hits?" + qs),
      apiGet("/admin/api/memory/items?" + qs),
      apiGet("/admin/api/memory/stats?" + qs),
    ]);
    const cfg = cfgResp.config || {};
    enabled.checked = !!cfg.enabled;
    backend.value = String(cfg.backend || "sqlite");
    topk.value = String(cfg.top_k || 5);
    writerEnabled.checked = !!cfg.writer_enabled;
    minConf.value = String(cfg.write_min_confidence ?? 0.75);
    ragMode.value = String(cfg.rag_mode || "keyword");
    embeddingMode.value = String(cfg.rag_embedding_mode || "");
    episodicTtlDays.value = String(cfg.memory_episodic_ttl_days || 90);
    memoryModeSelect.value = normalizeMemoryMode(localStorage.getItem(CHAT_MEMORY_MODE_KEY));
    try {
      const sf = await apiGet("/admin/api/chat/settings/specialist-flags");
      const flags = sf && sf.flags && typeof sf.flags === "object" ? sf.flags : {};
      memoryCuratorSelect.value = flags.memory === false ? "0" : "1";
    } catch (_) {
      memoryCuratorSelect.value = "1";
    }
    const hits = Array.isArray(hitsResp.hits) ? hitsResp.hits : [];
    const items = Array.isArray(itemsResp.items) ? itemsResp.items : [];
    const stats = (statsResp && statsResp.stats) || {};
    const srcText = Array.isArray(stats.top_sources) ? stats.top_sources.map((x) => `${x.source}:${x.count}`).join(", ") : "";
    statsWrap.textContent = `${t("memory.hitCount")}: ${Number(stats.hit_count || 0)} | ${t("memory.itemCount")}: ${Number(stats.item_count || 0)} | ${t("memory.avgScore")}: ${Number(stats.avg_score || 0).toFixed(3)} | ${t("memory.topSources")}: ${srcText || "-"}`;

    const hitBody = el("tbody");
    if (!hits.length) {
      hitBody.appendChild(el("tr", {}, [el("td", { text: t("memory.noData"), colspan: "6" })]));
    } else {
      hits.forEach((h) => {
        hitBody.appendChild(el("tr", {}, [
          tdCell(h.timestamp || "", 24),
          tdCell(h.tenant_id || "", 18),
          tdCell(h.user_id || "", 18),
          tdCell(h.query_text || "", 40),
          tdCell(h.memory_id || "", 18),
          tdCell(String(h.score || ""), 10),
        ]));
      });
    }
    hitsWrap.innerHTML = "";
    hitsWrap.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: t("table.timestamp") }),
        el("th", { text: "tenant_id" }),
        el("th", { text: "user_id" }),
        el("th", { text: "query" }),
        el("th", { text: "memory_id" }),
        el("th", { text: "score" }),
      ])]),
      hitBody,
    ])]));

    const itemBody = el("tbody");
    if (!items.length) {
      itemBody.appendChild(el("tr", {}, [el("td", { text: t("memory.noData"), colspan: "8" })]));
    } else {
      items.forEach((it) => {
        const btnDelete = el("button", { class: "btn btn--danger", text: t("memory.delete"), onclick: async () => {
          await apiPost("/admin/api/memory/delete", { memory_id: it.memory_id });
          await loadData();
        }});
        itemBody.appendChild(el("tr", {}, [
          tdCell(it.memory_id || "", 18),
          tdCell(it.tenant_id || "", 18),
          tdCell(it.user_id || "", 18),
          tdCell(it.memory_type || "", 14),
          tdCell(String(it.confidence ?? ""), 8),
          tdCell(it.content || "", 80),
          tdCell(it.updated_at || "", 24),
          el("td", {}, [btnDelete]),
        ]));
      });
    }
    itemsWrap.innerHTML = "";
    itemsWrap.appendChild(el("div", { class: "table-wrap" }, [el("table", { class: "table table--compact" }, [
      el("thead", {}, [el("tr", {}, [
        el("th", { text: "memory_id" }),
        el("th", { text: "tenant_id" }),
        el("th", { text: "user_id" }),
        el("th", { text: "type" }),
        el("th", { text: "confidence" }),
        el("th", { text: "content" }),
        el("th", { text: t("table.timestamp") }),
        el("th", { text: t("memory.delete") }),
      ])]),
      itemBody,
    ])]));

    try {
      const pluginsResp = await apiGet("/admin/api/plugins");
      const rows = Array.isArray(pluginsResp.plugins) ? pluginsResp.plugins : [];
      const wikiPlugin = rows.find((x) => String((x && x.plugin_name) || "").toLowerCase() === "memory-wiki");
      if (wikiPlugin) {
        wikiStatus.textContent = t("memory.wikiPluginFound", {
          name: String(wikiPlugin.plugin_name || "memory-wiki"),
          version: String(wikiPlugin.plugin_version || "-"),
        });
      } else {
        wikiStatus.textContent = t("memory.wikiPluginMissing");
      }
    } catch (_) {
      wikiStatus.textContent = t("memory.wikiPluginMissing");
    }
  };

  const btnApplyFilters = el("button", { class: "btn", text: t("memory.applyFilters"), onclick: async () => {
    const p = new URLSearchParams();
    if (tenantInput.value.trim()) p.set("tenant_id", tenantInput.value.trim());
    if (userInput.value.trim()) p.set("user_id", userInput.value.trim());
    location.hash = "#/memory" + (p.toString() ? ("?" + p.toString()) : "");
    await loadData();
  }});
  const btnClearFilters = el("button", { class: "btn", text: t("memory.clearFilters"), onclick: async () => {
    tenantInput.value = "";
    userInput.value = "";
    location.hash = "#/memory";
    await loadData();
  }});
  await loadData();

  return el("div", {}, [
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.config") }),
      el("div", { class: "row" }, [el("label", { text: t("memory.enabled") }), enabled]),
      el("div", { class: "row" }, [el("label", { text: t("memory.backend") }), backend]),
      el("div", { class: "row" }, [el("label", { text: t("memory.topk") }), topk]),
      el("div", { class: "row" }, [el("label", { text: t("memory.writerEnabled") }), writerEnabled]),
      el("div", { class: "row" }, [el("label", { text: "RAG mode" }), ragMode]),
      el("div", { class: "row" }, [el("label", { text: "Embedding mode" }), embeddingMode]),
      el("div", { class: "row" }, [el("label", { text: "Episodic TTL days" }), episodicTtlDays]),
      el("div", { class: "row" }, [el("label", { text: t("memory.minConfidence") }), minConf]),
      el("div", { class: "row" }, [btnSave, btnReindex, btnCleanup]),
      status,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.wikiCard") }),
      el("div", { class: "row" }, [el("label", { text: t("profile.memoryMode") }), memoryModeSelect]),
      el("div", { class: "row" }, [el("label", { text: t("profile.memoryCurator") }), memoryCuratorSelect]),
      el("div", { class: "row" }, [el("label", { text: t("memory.wikiStatus") }), wikiStatus]),
      el("div", { class: "row" }, [
        el("button", {
          class: "btn",
          text: t("memory.openPlugins"),
          onclick: () => {
            location.hash = "#/plugins";
          },
        }),
      ]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.filters") }),
      el("div", { class: "row" }, [tenantInput, userInput, btnApplyFilters, btnClearFilters]),
      statsWrap,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.hits") }),
      hitsWrap,
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card__title", text: t("memory.items") }),
      itemsWrap,
    ]),
  ]);
}


export { renderMemory };
