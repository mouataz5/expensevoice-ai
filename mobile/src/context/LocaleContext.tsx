import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { I18nManager } from "react-native";
import type { Locale } from "../i18n/translations";
import { translations } from "../i18n/translations";

type LocaleContextValue = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
  isRTL: boolean;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

const STORAGE_KEY = "abes_locale";

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("ar");

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    const rtl = l === "ar";
    if (I18nManager.isRTL !== rtl) {
      I18nManager.forceRTL(rtl);
      // Note: app restart may be required for RTL to apply fully on some devices
    }
  }, []);

  const t = useCallback(
    (key: string) => translations[locale][key] ?? key,
    [locale]
  );

  useEffect(() => {
    const rtl = locale === "ar";
    if (I18nManager.isRTL !== rtl) {
      I18nManager.forceRTL(rtl);
    }
  }, [locale]);

  const value: LocaleContextValue = {
    locale,
    setLocale,
    t,
    isRTL: locale === "ar",
  };

  return (
    <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>
  );
}

export function useLocale() {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useLocale must be used within LocaleProvider");
  return ctx;
}
