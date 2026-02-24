import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "../auth/AuthContext";
import { fetchMe } from "../api/me";

const navBase = [
  { to: "/stats", labelKey: "nav.stats" as const },
  { to: "/alerts", labelKey: "nav.alerts" as const },
];

const navEmployee = [
  { to: "/employee/record", labelKey: "nav.record" as const },
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
          ...(role === "admin"
            ? [{ to: "/policies" as const, labelKey: "nav.policies" as const }]
            : []),
        ].map((n) => ({ ...n, label: t(n.labelKey) }));

  return (
    <div className="min-h-screen bg-background">
      <div className="flex">
        {/* Sidebar */}
        <aside className="hidden md:flex md:w-64 md:flex-col border-r min-h-screen p-4">
          <div className="text-xl font-semibold">ExpenseVoice</div>
          <div className="text-sm text-muted-foreground mb-4">{t("common.dashboard")}</div>
          <Separator className="my-3" />
          <nav className="flex flex-col gap-2">
            {nav.map((n) => {
              const active = pathname.startsWith(n.to);
              return (
                <Link
                  key={n.to}
                  to={n.to}
                  className={[
                    "rounded-xl px-3 py-2 text-sm",
                    active ? "bg-muted font-medium" : "hover:bg-muted/60",
                  ].join(" ")}
                >
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="mt-auto pt-4">
            {token && (
              <Button variant="outline" className="w-full" onClick={logout}>
                {t("nav.logout")}
              </Button>
            )}
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1">
          {/* Topbar */}
          <header className="sticky top-0 z-10 bg-background/80 backdrop-blur border-b">
            <div className="h-14 px-4 flex items-center justify-between">
              <div className="md:hidden font-semibold">ExpenseVoice</div>
              <div className="flex items-center gap-2">
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

          <div className="p-4 md:p-6 max-w-6xl mx-auto">{children}</div>
        </main>
      </div>
    </div>
  );
}
