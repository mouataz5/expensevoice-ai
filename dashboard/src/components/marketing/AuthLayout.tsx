import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

export function AuthLayout({
  children,
  title,
  subtitle,
}: {
  children: React.ReactNode;
  title: string;
  subtitle?: string;
}) {
  const { t, i18n } = useTranslation();

  return (
    <div className="min-h-screen flex">
      <div
        className={cn(
          "hidden lg:flex lg:w-1/2 flex-col justify-between p-10 md:p-14 relative overflow-hidden",
          "bg-gradient-to-br from-primary/20 via-primary/8 to-background"
        )}
      >
        <div className="absolute top-0 right-0 w-64 h-64 bg-primary/15 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-accent/10 rounded-full blur-3xl translate-y-1/2 -translate-x-1/2" />
        <Link to="/" className="flex items-center gap-3 text-primary font-semibold text-xl relative z-10">
          <span className="flex w-10 h-10 items-center justify-center rounded-xl bg-primary/20">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />
            </svg>
          </span>
          Abes AgroTech
        </Link>
        <div className="space-y-6 relative z-10">
          <div className="h-1 w-20 rounded-full bg-primary/50" />
          <p className="text-muted-foreground max-w-sm text-lg leading-relaxed">
            {i18n.language === "ar"
              ? "منصة ذكية لإدارة المبيعات والمصاريف في الشركات الفلاحية."
              : "Plateforme intelligente pour la gestion des ventes et dépenses agricoles."}
          </p>
          <div className="flex gap-4 pt-2">
            <div className="w-2 h-2 rounded-full bg-primary/60" />
            <div className="w-2 h-2 rounded-full bg-primary/40" />
            <div className="w-2 h-2 rounded-full bg-primary/30" />
          </div>
        </div>
      </div>
      <div className="flex-1 flex flex-col justify-center p-6 md:p-12 bg-background">
        <div className="w-full max-w-md mx-auto">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6"
          >
            <span aria-hidden>←</span>
            {t("site.auth.backToSite")}
          </Link>
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-foreground">{title}</h1>
            {subtitle && <p className="text-muted-foreground mt-1">{subtitle}</p>}
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
