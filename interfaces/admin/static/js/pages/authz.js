import { state } from "../core.js";

function hasPermission(permission) {
  const role = String((state.authSession && state.authSession.role) || "");
  const perms = new Set(Array.isArray(state.authSession && state.authSession.permissions) ? state.authSession.permissions : []);
  if (role === "owner") return true;
  return perms.has(permission);
}

/** 与 models_api._can_manage_llm_grants 一致：仅控制台 administrator 用户可管理授权 */
function canManageApiGrants() {
  const un = String((state.authSession && state.authSession.username) || "").trim().toLowerCase();
  if (un !== "administrator") return false;
  const role = String((state.authSession && state.authSession.role) || "").trim();
  if (role === "owner") return true;
  return hasPermission("admin:tenant:write");
}

function isAdministratorUsername() {
  return String((state.authSession && state.authSession.username) || "").trim().toLowerCase() === "administrator";
}

/** 与 models_api._profile_shareable_for_admin_grant 一致 */
function profileShareableForGrant(p, sessionUserId) {
  if (!p || p.is_builtin) return false;
  const own = String(p.owner_user_id || "").trim();
  if (!own) return true;
  return own === String(sessionUserId || "").trim();
}


export { hasPermission, canManageApiGrants, isAdministratorUsername, profileShareableForGrant };
