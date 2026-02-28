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
          "hidden lg:flex lg:w-1/2 flex-col justify-between p-8 md:p-12",
          "bg-gradient-to-br from-primary/15 via-primary/5 to-background"
        )}
      >
        <Link to="/" className="text-primary font-semibold text-lg">
          Abes AgroTech
        </Link>
        <div className="space-y-4">
          <div className="h-1 w-16 rounded-full bg-primary/40" />
          <p className="text-muted-foreground max-w-sm">
            {i18n.language === "ar"
              ? "منصة ذكية لإدارة المبيعات والمصاريف في الشركات الفلاحية."
              : "Plateforme intelligente pour la gestion des ventes et dépenses agricoles."}
          </p>
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
