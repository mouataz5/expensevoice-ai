import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useTheme } from "next-themes";
import { useAuth } from "../auth/AuthContext";
import { fetchMe } from "../api/me";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { EmployeeHero, EmployeePage, EmployeeSectionCard } from "@/components/employee/EmployeeShell";

export default function EmployeeProfile() {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const { logout } = useAuth();
  const meQ = useQuery({ queryKey: ["me"], queryFn: fetchMe });

  return (
    <EmployeePage>
      <EmployeeHero
        eyebrow="Employee Dashboard"
        title={t("employee.profileTitle")}
        subtitle={t("employee.profileSubtitle")}
        meta={[
          { label: "Email", value: meQ.data?.email ?? "-" },
          { label: "Role", value: meQ.data?.role ?? "-" },
        ]}
      />
      <PageHeader title={t("employee.profileTitle")} subtitle={t("employee.profileSubtitle")} />

      <EmployeeSectionCard title={t("employee.profileAccount")}>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div className="rounded-xl border border-border p-3">
            <div className="text-muted-foreground">Email</div>
            <div className="font-medium mt-1">{meQ.data?.email ?? "-"}</div>
          </div>
          <div className="rounded-xl border border-border p-3">
            <div className="text-muted-foreground">Role</div>
            <div className="font-medium mt-1">{meQ.data?.role ?? "-"}</div>
          </div>
        </div>
      </EmployeeSectionCard>

      <EmployeeSectionCard title={t("employee.profilePreferences")}>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="rounded-xl"
            onClick={() => {
              const order = ["ar", "fr", "en"];
              const idx = order.indexOf(i18n.language);
              const next = order[(idx + 1) % order.length];
              void i18n.changeLanguage(next);
            }}
          >
            {t("employee.profileLanguage")}: {i18n.language.toUpperCase()}
          </Button>
          <Button
            variant="outline"
            className="rounded-xl"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? t("common.theme_light") : t("common.theme_dark")}
          </Button>
        </div>
      </EmployeeSectionCard>

      <EmployeeSectionCard title="Support">
        <div className="rounded-xl border border-border bg-muted/20 p-3 text-sm text-muted-foreground">
          support@abesagrotech.tn
        </div>
      </EmployeeSectionCard>

      <EmployeeSectionCard title={t("employee.profileSession")}>
        <Button variant="destructive" className="rounded-xl" onClick={logout}>
          {t("nav.logout")}
        </Button>
      </EmployeeSectionCard>
    </EmployeePage>
  );
}
