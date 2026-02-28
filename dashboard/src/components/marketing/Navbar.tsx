import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const BRAND = "Abes AgroTech";

const navLinks = [
  { to: "/", key: "site.nav.home" },
  { to: "/about", key: "site.nav.about" },
  { to: "/services", key: "site.nav.services" },
  { to: "/contact", key: "site.nav.contact" },
] as const;

export function Navbar() {
  const { t, i18n } = useTranslation();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleLang = () => {
    const next = i18n.language === "ar" ? "fr" : "ar";
    i18n.changeLanguage(next);
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border/80 bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
      <div className="container mx-auto flex h-16 items-center justify-between px-4 md:px-6">
        <Link to="/" className="flex items-center gap-2 font-semibold text-primary">
          <span className="text-xl">{BRAND}</span>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {navLinks.map(({ to, key }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                "px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                location.pathname === to
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/70"
              )}
            >
              {t(key)}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            className="rounded-xl font-medium"
            onClick={toggleLang}
          >
            {i18n.language === "ar" ? "FR" : "AR"}
          </Button>
          <Link to="/auth/login">
            <Button className="rounded-xl">{t("site.nav.login")}</Button>
          </Link>

          <button
            type="button"
            className="md:hidden p-2 rounded-lg hover:bg-muted"
            onClick={() => setMobileOpen((o) => !o)}
            aria-label="Menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div className="md:hidden border-t border-border bg-card px-4 py-3 flex flex-col gap-1">
          {navLinks.map(({ to, key }) => (
            <Link
              key={to}
              to={to}
              className={cn(
                "px-3 py-2 rounded-lg text-sm font-medium",
                location.pathname === to ? "bg-primary/10 text-primary" : "text-muted-foreground"
              )}
              onClick={() => setMobileOpen(false)}
            >
              {t(key)}
            </Link>
          ))}
        </div>
      )}
    </header>
  );
}
