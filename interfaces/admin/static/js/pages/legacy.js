import { state, t, el, apiGet, apiPost, apiRequest, formatUserLabel } from "../core.js";
import { profileShareableForGrant } from "./authz.js";

async function renderApiGrants() {
  const status = el("div", { class: "muted", text: "" });
  const profileSel = el("select", { class: "input" });
  const grantListEl = el("div", {});
  const grantUserSel = el("select", { class: "input" });
  const grantMsg = el("div", { class: "muted", text: "" });
  const grantBtn = el("button", { class: "btn btn--primary", text: t("models.grantsGrantBtn") });
  const tenantGrantStatus = el("span", { class: "muted", text: "" });

  let state = null;

  const VIS_KEYS = {
    builtin: "models.vis.builtin",
    owned: "models.vis.owned",
    grant_user: "models.vis.grantUser",
    grant_tenant: "models.vis.grantTenant",
    global: "models.vis.global",
    other_user: "models.vis.otherUser",
  };

  function visibilityTag(vr) {
    const k = VIS_KEYS[String(vr || "")];
    return k ? t(k) : "";
  }

  async function paintGrants() {
    grantMsg.textContent = "";
    const pid = String(profileSel.value || "").trim();
    if (!pid) {
      grantListEl.innerHTML = "";
      tenantGrantStatus.textContent = "";
      return;
    }
    try {
      const tg = await apiGet("/admin/api/models/grants/tenant?profile_id=" + encodeURIComponent(pid));
      tenantGrantStatus.textContent = tg.granted ? t("models.tenantGrantOn") : t("models.tenantGrantOff");
      const g = await apiGet("/admin/api/models/grants?profile_id=" + encodeURIComponent(pid));
      const rows = Array.isArray(g.grants) ? g.grants : [];
      grantListEl.innerHTML = "";
      if (!rows.length) {
        grantListEl.appendChild(el("div", { class: "muted", text: t("models.grantsEmpty") }));
        return;
      }
      rows.forEach((r) => {
        const disp = String(r.display_name || r.username || r.user_id || "").trim();
        const rev = el("button", { class: "btn", text: t("models.grantsRevoke"), onclick: async () => {
          try {
            await apiRequest(
              "DELETE",
              "/admin/api/models/grants?profile_id=" + encodeURIComponent(pid) + "&user_id=" + encodeURIComponent(String(r.user_id || "")),
              undefined,
            );
            await paintGrants();
          } catch (e) {
            grantMsg.textContent = String(e.message || e);
          }
        } });
        grantListEl.appendChild(el("div", { class: "row" }, [
          el("span", { text: disp || r.user_id }),
          rev,
        ]));
      });
    } catch (e) {
      grantMsg.textContent = String(e.message || e);
    }
  }

  const btnTenantGrant = el("button", {
    class: "btn btn--primary",
    text: t("models.grantTenantBtn"),
    onclick: async () => {
      const pid = String(profileSel.value || "").trim();
      if (!pid) return;
      try {
        await apiPost("/admin/api/models/grants/tenant", { profile_id: pid });
        await paintGrants();
      } catch (e) {
        grantMsg.textContent = String(e.message || e);
      }
    },
  });
  const btnTenantRevoke = el("button", {
    class: "btn",
    text: t("models.revokeTenantGrant"),
    onclick: async () => {
      const pid = String(profileSel.value || "").trim();
      if (!pid) return;
      try {
        await apiRequest(
          "DELETE",
          "/admin/api/models/grants/tenant?profile_id=" + encodeURIComponent(pid),
          undefined,
        );
        await paintGrants();
      } catch (e) {
        grantMsg.textContent = String(e.message || e);
      }
    },
  });
  const grantTenantRow = el("div", { class: "row", style: "flex-wrap:wrap;gap:8px;align-items:center;" }, [
    btnTenantGrant,
    btnTenantRevoke,
    tenantGrantStatus,
  ]);

  const membersBody = el("div", {});
  let membersLoaded = false;
  const membersDetails = el("details", { class: "details" });
  membersDetails.appendChild(el("summary", { text: t("models.membersTitle") }));
  membersDetails.appendChild(membersBody);
  const membersWrap = el("div", { class: "card" }, [membersDetails]);

  membersDetails.addEventListener("toggle", async () => {
    if (!membersDetails.open || membersLoaded) return;
    try {
      const r = await apiGet("/admin/api/models/members");
      membersLoaded = true;
      membersBody.innerHTML = "";
      const list = Array.isArray(r.members) ? r.members : [];
      if (!list.length) {
        membersBody.appendChild(el("div", { class: "muted", text: "—" }));
        return;
      }
      list.forEach((m) => {
        const names = (m.profiles || []).map((p) => {
          const nm = String(p.name || p.id || "").trim();
          const vr = p.visibility_reason ? ` (${visibilityTag(p.visibility_reason)})` : "";
          return nm + vr;
        });
        membersBody.appendChild(el("div", { class: "card", style: "margin-bottom:10px" }, [
          el("div", { class: "card__title", text: formatUserLabel(m) }),
          el("div", { class: "muted", text: names.filter(Boolean).length ? names.join("；") : "—" }),
        ]));
      });
    } catch (e) {
      membersLoaded = false;
      membersBody.appendChild(el("div", { class: "muted", text: String(e.message || e) }));
    }
  });

  async function ensureGrantUsers() {
    grantUserSel.innerHTML = "";
    const tid = String((state.authSession && state.authSession.tenant_id) || "").trim();
    if (!tid) return;
    try {
      const u = await apiGet("/admin/api/users?tenant_id=" + encodeURIComponent(tid) + "&limit=500");
      grantUserSel.appendChild(el("option", { value: "", text: "—" }));
      (u.users || []).forEach((x) => {
        const uid = String(x.id || "").trim();
        if (!uid) return;
        grantUserSel.appendChild(el("option", { value: uid, text: formatUserLabel(x) || uid }));
      });
    } catch (e) {
      grantMsg.textContent = String(e.message || e);
    }
  }

  function fillProfileSelect() {
    profileSel.innerHTML = "";
    const uid = String((state.authSession && state.authSession.user_id) || "").trim();
    const all = (state && Array.isArray(state.profiles)) ? state.profiles : [];
    const list = all.filter((p) => profileShareableForGrant(p, uid));
    if (!list.length) {
      profileSel.appendChild(el("option", { value: "", text: t("apiGrants.noShareable") }));
      profileSel.disabled = true;
      return;
    }
    profileSel.disabled = false;
    list.forEach((p) => {
      const own = String(p.owner_user_id || "").trim();
      const tag = own ? t("models.vis.owned") : t("models.vis.global");
      const name = String(p.name || p.id || "").trim();
      profileSel.appendChild(el("option", { value: String(p.id), text: `${name} (${tag})` }));
    });
  }

  profileSel.addEventListener("change", async () => {
    await paintGrants();
  });

  grantBtn.addEventListener("click", async () => {
    const pid = String(profileSel.value || "").trim();
    const uid = String(grantUserSel.value || "").trim();
    if (!pid || !uid) return;
    try {
      await apiPost("/admin/api/models/grants", { profile_id: pid, user_id: uid });
      await paintGrants();
    } catch (e) {
      grantMsg.textContent = String(e.message || e);
    }
  });

  async function refresh() {
    try {
      const data = await apiGet("/admin/api/models");
      state = data;
      status.textContent = "";
      if (!data || data.can_manage_llm_grants !== true) return;
      fillProfileSelect();
      await ensureGrantUsers();
      await paintGrants();
    } catch (e) {
      state = null;
      status.textContent = String(e.message || e);
    }
  }

  await refresh();

  const forbiddenCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("title.apiGrants") }),
    el("div", { class: "muted", text: t("apiGrants.forbidden") }),
    el("div", { class: "row" }, [
      el("a", { href: "#/models", text: t("apiGrants.openModels") }),
    ]),
  ]);

  if (!state || state.can_manage_llm_grants !== true) {
    const bits = [forbiddenCard];
    if (status.textContent) bits.push(el("div", { class: "card" }, [el("pre", { class: "pre", text: status.textContent })]));
    return el("div", {}, bits);
  }

  const introCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("title.apiGrants") }),
    el("div", { class: "muted", text: t("apiGrants.intro") }),
    status,
  ]);
  const pickCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("apiGrants.pickApi") }),
    el("div", { class: "row" }, [profileSel]),
  ]);
  const teamCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("apiGrants.teamSection") }),
    el("div", { class: "muted", text: t("apiGrants.teamHint") }),
    grantTenantRow,
  ]);
  const userCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("apiGrants.userSection") }),
    el("div", { class: "muted", text: t("apiGrants.userHint") }),
    el("div", { class: "row" }, [grantUserSel, grantBtn]),
    grantListEl,
    grantMsg,
  ]);

  return el("div", {}, [introCard, pickCard, teamCard, userCard, membersWrap]);
}


export { renderApiGrants };
