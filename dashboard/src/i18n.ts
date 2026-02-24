import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import ar from "./i18n/ar.json";
import fr from "./i18n/fr.json";
import en from "./i18n/en.json";

const saved = (typeof localStorage !== "undefined" && localStorage.getItem("lang")) || "ar";

const applyDir = (lng: string) => {
  const dir = lng === "ar" ? "rtl" : "ltr";
  document.documentElement.lang = lng;
  document.documentElement.dir = dir;
};

i18n.use(initReactI18next).init({
  resources: {
    ar: { translation: ar as Record<string, unknown> },
    fr: { translation: fr as Record<string, unknown> },
    en: { translation: en as Record<string, unknown> },
  },
  lng: saved,
  fallbackLng: "ar",
  interpolation: { escapeValue: false },
});

applyDir(i18n.language);

i18n.on("languageChanged", (lng: string) => {
  if (typeof localStorage !== "undefined") localStorage.setItem("lang", lng);
  applyDir(lng);
});

export default i18n;
