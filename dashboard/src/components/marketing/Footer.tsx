import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

const navLinks = [
  { to: "/", key: "site.nav.home" },
  { to: "/about", key: "site.nav.about" },
  { to: "/services", key: "site.nav.services" },
  { to: "/contact", key: "site.nav.contact" },
  { to: "/auth/login", key: "site.nav.login" },
] as const;

export function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="border-t border-border bg-card/95">
      <div className="container mx-auto px-4 py-14 md:px-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          <div className="space-y-4">
            <div className="flex items-center gap-2 font-semibold text-lg text-primary">
              <span className="flex w-8 h-8 items-center justify-center rounded-lg bg-primary/15">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />
                </svg>
              </span>
              Abes AgroTech
            </div>
            <p className="text-sm text-muted-foreground max-w-xs">
              {t("site.footer.desc")}
            </p>
          </div>
          <div>
            <div className="font-medium text-foreground mb-3">{t("site.footer.links")}</div>
            <ul className="space-y-2">
              {navLinks.map(({ to, key }) => (
                <li key={to}>
                  <Link to={to} className="text-sm text-muted-foreground hover:text-primary transition-colors">
                    {t(key)}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <div className="font-medium text-foreground mb-3">{t("site.footer.contact")}</div>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>{t("site.contact.emailLabel")}: contact@abesagrotech.com</li>
              <li>{t("site.contact.whatsapp")}: +216 XX XXX XXX</li>
            </ul>
          </div>
        </div>
        <div className="mt-8 pt-8 border-t border-border text-center text-sm text-muted-foreground">
          © {new Date().getFullYear()} Abes AgroTech. {t("site.footer.copyright")}
        </div>
      </div>
    </footer>
  );
}
