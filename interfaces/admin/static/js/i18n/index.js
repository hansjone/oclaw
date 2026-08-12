import messagesZh from "./messages-zh.js";
import messagesEn from "./messages-en.js";
import { state } from "../state.js";

export const I18N = {
  zh: messagesZh,
  en: messagesEn,
};

export const LANG_KEY = "ops_admin_lang";

export function t(key) {
  return (I18N[state.currentLang] && I18N[state.currentLang][key]) || (I18N.en && I18N.en[key]) || key;
}

export function tf(key, vars = {}) {
  const template = t(key);
  return template.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}

export function applyI18nStatic() {
  document.documentElement.lang = state.currentLang === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    node.textContent = t(key);
  });
  const langBtn = document.getElementById("btnLang");
  if (langBtn) langBtn.textContent = t("lang.switch");
  const themeSel = document.getElementById("adminThemeSelect");
  if (themeSel && window.OclawAdminTheme) {
    try {
      themeSel.value = OclawAdminTheme.currentAdminTheme();
    } catch (_) {}
  }
}

export function toggleLang() {
  state.currentLang = state.currentLang === "zh" ? "en" : "zh";
  localStorage.setItem(LANG_KEY, state.currentLang);
}
