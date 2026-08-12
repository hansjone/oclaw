import { state, t, el, apiGet, apiRequest, apiPostFormData, apiDeleteJson, resolveAdminApiUrl, getStoredAuthToken, authStoreGet, authStoreSet, AUTH_SESSION_KEY } from "../core.js";

async function renderProfile() {
  const status = el("div", { class: "muted", text: "" });
  const dnInput = el("input", { class: "input", type: "text", maxlength: "120" });
  const metaUser = el("div", { class: "muted pre", text: "" });
  const metaIds = el("div", { class: "muted pre", text: "" });
  const avatarPreview = el("img", {
    class: "profile-avatar-preview u-hidden u-avatar-chip",
    alt: "",
  });
  const avatarRow = el("div", { class: "row", style: "align-items:center;gap:16px;flex-wrap:wrap;" }, [
    el("div", {}, [avatarPreview]),
    el("div", { style: "min-width:200px;flex:1;" }, [
      el("div", { class: "muted", style: "margin-bottom:6px;", text: t("profile.avatar") }),
      el("div", { class: "muted", style: "margin-bottom:8px;font-size:12px;line-height:1.4;", text: t("profile.avatarHint") }),
    ]),
  ]);
  const fileInput = el("input", { class: "u-hidden", type: "file", accept: "image/png,image/jpeg,image/jpg,image/webp,image/gif" });
  const chooseBtn = el("button", { class: "btn", type: "button", text: t("profile.chooseImage") });
  const removeBtn = el("button", { class: "btn", type: "button", text: t("profile.removeAvatar") });
  const saveBtn = el("button", { class: "btn btn--primary", type: "button", text: t("profile.save") });
  const chatBtn = el("button", { class: "btn", type: "button", text: t("profile.openChat") });

  function showBuiltinDefaultAvatar() {
    try {
      const prev = avatarPreview.dataset.blobUrl;
      if (prev) URL.revokeObjectURL(prev);
    } catch (_) {}
    delete avatarPreview.dataset.blobUrl;
    avatarPreview.src = resolveAdminApiUrl("/admin/assets/default-user-avatar.svg");
    avatarPreview.style.objectFit = "contain";
    avatarPreview.style.padding = "5px";
    avatarPreview.style.background = "rgba(255,255,255,0.08)";
    avatarPreview.style.display = "block";
  }

  /** <img> cannot send Authorization; load avatar via fetch + blob */
  async function refreshAvatarBlob(p) {
    const aid = p && String(p.avatar_attachment_id || "").trim();
    if (!aid) {
      showBuiltinDefaultAvatar();
      return;
    }
    try {
      const tok = getStoredAuthToken();
      const u = resolveAdminApiUrl(`/admin/api/chat/attachments/${encodeURIComponent(aid)}`);
      const res = await fetch(u, { headers: tok ? { authorization: `Bearer ${tok}` } : {} });
      if (!res.ok) throw new Error("avatar fetch");
      const blob = await res.blob();
      try {
        const prev = avatarPreview.dataset.blobUrl;
        if (prev) URL.revokeObjectURL(prev);
      } catch (_) {}
      const url = URL.createObjectURL(blob);
      avatarPreview.dataset.blobUrl = url;
      avatarPreview.src = url;
      avatarPreview.style.objectFit = "cover";
      avatarPreview.style.padding = "0";
      avatarPreview.style.background = "transparent";
      avatarPreview.style.display = "block";
    } catch (_) {
      showBuiltinDefaultAvatar();
    }
  }

  async function load() {
    status.textContent = t("chat.loading");
    try {
      const r = await apiGet("/admin/api/chat/profile");
      if (!r || !r.ok || !r.profile) throw new Error("profile");
      const p = r.profile;
      dnInput.value = String(p.display_name || "");
      metaUser.textContent = `${t("profile.username")}: ${String(p.username || "—")}\n${t("profile.role")}: ${String(p.role || "—")}`;
      metaIds.textContent = `${t("profile.userId")}: ${String(p.id || "—")}\n${t("profile.tenantId")}: ${String(p.tenant_id || "—")}\n${t("profile.createdAt")}: ${String(p.created_at || "—")}`;
      await refreshAvatarBlob(p);
      status.textContent = "";
    } catch (e) {
      status.textContent = `${t("profile.loadError")}: ${String(e && e.message ? e.message : e)}`;
    }
  }

  chooseBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", async () => {
    const f = fileInput.files && fileInput.files[0];
    fileInput.value = "";
    if (!f) return;
    status.textContent = t("chat.sending");
    try {
      const fd = new FormData();
      fd.append("file", f, f.name || "avatar.png");
      const r = await apiPostFormData("/admin/api/chat/profile/avatar", fd);
      if (!r || !r.ok) throw new Error("upload");
      status.textContent = t("profile.saved");
      await load();
    } catch (e) {
      status.textContent = `${t("profile.uploadError")}: ${String(e && e.message ? e.message : e)}`;
    }
  });
  removeBtn.addEventListener("click", async () => {
    status.textContent = t("chat.sending");
    try {
      await apiDeleteJson("/admin/api/chat/profile/avatar");
      status.textContent = t("profile.saved");
      await load();
    } catch (e) {
      status.textContent = String(e && e.message ? e.message : e);
    }
  });
  saveBtn.addEventListener("click", async () => {
    status.textContent = t("chat.sending");
    try {
      await apiRequest("PATCH", "/admin/api/chat/profile", { display_name: dnInput.value.trim() });
      status.textContent = t("profile.saved");
      await load();
      try {
        const sess = JSON.parse(authStoreGet(AUTH_SESSION_KEY) || "{}");
        if (sess && typeof sess === "object") {
          sess.display_name = dnInput.value.trim();
          authStoreSet(AUTH_SESSION_KEY, JSON.stringify(sess));
          state.authSession = sess;
        }
      } catch (_) {}
    } catch (e) {
      status.textContent = String(e && e.message ? e.message : e);
    }
  });
  chatBtn.addEventListener("click", () => {
    window.location.assign(resolveChatUrl());
  });

  await load();

  const profileCard = el("div", { class: "card" }, [
    el("div", { class: "card__title", text: t("title.profile") }),
    el("div", { class: "muted", style: "margin-bottom:10px;line-height:1.45;", text: t("profile.help") }),
    el("div", { class: "row" }, [el("label", { text: t("profile.displayName") }), dnInput]),
    el("div", { class: "u-h-8" }),
    avatarRow,
    el("div", { class: "row", style: "margin-top:10px;gap:8px;flex-wrap:wrap;" }, [fileInput, chooseBtn, removeBtn]),
    el("div", { class: "row", style: "margin-top:12px;gap:8px;flex-wrap:wrap;" }, [saveBtn, chatBtn]),
    el("div", { class: "u-h-8" }),
    el("div", { style: "margin-top:14px" }, [metaUser]),
    el("div", { class: "u-mt-6" }, [metaIds]),
    el("div", { class: "muted u-mt-10" }, [status]),
  ]);
  return el("div", {}, [profileCard]);
}


export { renderProfile };
