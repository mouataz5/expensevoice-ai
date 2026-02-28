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
    <footer className="border-t border-border bg-card">
      <div className="container mx-auto px-4 py-12 md:px-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="space-y-3">
            <div className="font-semibold text-lg text-primary">Abes AgroTech</div>
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
