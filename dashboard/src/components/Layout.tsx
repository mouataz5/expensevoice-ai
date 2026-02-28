import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "../auth/AuthContext";
import { fetchMe } from "../api/me";
import { NotificationCenter } from "./NotificationCenter";
import { cn } from "@/lib/utils";

const BRAND_TITLE = "نظام عبّاس لإدارة الضيعة";
const BRAND_SUBTITLE_KEY = "common.dashboard" as const;

const navBase = [
  { to: "/stats", labelKey: "nav.stats" as const },
  { to: "/alerts", labelKey: "nav.alerts" as const },
  { to: "/audit", labelKey: "nav.audit" as const },
];

const navEmployee = [
  { to: "/employee/record", labelKey: "nav.record" as const },
  { to: "/employee/scan-invoice", labelKey: "nav.scanInvoice" as const },
  { to: "/employee/purchases", labelKey: "nav.myPurchases" as const },
  { to: "/employee/alerts", labelKey: "nav.myAlerts" as const },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { token, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const { t, i18n } = useTranslation();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  useEffect(() => {
    document.documentElement.dir = i18n.language === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  const meQ = useQuery({ queryKey: ["me"], queryFn: fetchMe, enabled: !!token });
  const role = meQ.data?.role;

  useEffect(() => {
    if (pathname === "/" && role === "employee") {
      navigate("/employee/record", { replace: true });
    }
  }, [pathname, role, navigate]);

  const nav =
    role === "employee"
      ? navEmployee.map((n) => ({ ...n, label: t(n.labelKey) }))
      : [
          ...navBase,
          ...(role === "director" || role === "admin"
            ? [
                { to: "/invoices" as const, labelKey: "nav.invoiceReview" as const },
                { to: "/settings" as const, labelKey: "nav.settings" as const },
              ]
            : []),
          ...(role === "admin"
            ? [
                { to: "/policies" as const, labelKey: "nav.policies" as const },
                { to: "/users" as const, labelKey: "nav.users" as const },
              ]
            : []),
        ].map((n) => ({ ...n, label: t(n.labelKey) }));

  return (
    <div className="min-h-screen bg-background">
      <div className="flex">
        {/* Sidebar: distinct surface, dynamic link backgrounds */}
        <aside className="hidden md:flex md:w-64 md:flex-col border-r border-border bg-card min-h-screen p-4 shadow-sm">
          <div className="text-xl font-semibold text-primary">{BRAND_TITLE}</div>
          <div className="text-sm text-muted-foreground mb-4">{t(BRAND_SUBTITLE_KEY)}</div>
          <Separator className="my-3" />
          <nav className="flex flex-col gap-1">
            {nav.map((n, index) => {
              const active = pathname.startsWith(n.to);
              const accentIndex = (index % 6) + 1;
              return (
                <Link
                  key={n.to}
                  to={n.to}
                  className={cn(
                    "sidebar-nav-link",
                    active && "active",
                    active && `nav-accent-${accentIndex}`
                  )}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto pt-4">
            {token && (
              <Button variant="outline" className="w-full rounded-xl" onClick={logout}>
                {t("nav.logout")}
              </Button>
            )}
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 flex flex-col min-h-screen">
          {/* Topbar: clear hierarchy, subtle gradient */}
          <header className="sticky top-0 z-10 bg-card/95 backdrop-blur-md border-b border-border shadow-sm">
            <div className="h-14 px-4 flex items-center justify-between">
              <div className="md:hidden font-semibold text-primary">{BRAND_TITLE}</div>
              <div className="flex items-center gap-2">
                {role === "director" || role === "admin" ? (
                  <NotificationCenter />
                ) : null}
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-xl"
                  onClick={() => {
                    const order = ["ar", "fr", "en"];
                    const idx = order.indexOf(i18n.language);
                    const next = order[(idx + 1) % order.length];
                    i18n.changeLanguage(next);
                  }}
                >
                  {i18n.language.toUpperCase()}
                </Button>
                {mounted && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-xl"
                      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                    >
                      {theme === "dark" ? t("common.theme_light") : t("common.theme_dark")}
                    </Button>
                  </>
                )}
                <span className="text-sm text-muted-foreground">
                  {role === "employee"
                    ? t("common.view_subtitle_employee")
                    : t("common.view_subtitle")}
                </span>
              </div>
            </div>
          </header>

          <div className="flex-1 content-area p-6 md:p-8 max-w-6xl w-full mx-auto min-h-0">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
