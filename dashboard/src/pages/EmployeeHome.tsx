import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { listMyPurchases } from "../api/purchases";
import { listMyInvoices } from "../api/invoices";
import { api } from "../api/client";
import {
  EmployeeKpiCard,
  EmployeePage,
} from "@/components/employee/EmployeeShell";

type AlertOut = {
  id: string;
  status: string;
};

async function fetchMyAlerts(): Promise<AlertOut[]> {
  const res = await api.get("/alerts/me");
  return res.data;
}

function todayIsoPrefix() {
  return new Date().toISOString().slice(0, 10);
}

export default function EmployeeHome() {
  const { t } = useTranslation();
  const purchasesQ = useQuery({ queryKey: ["my-purchases"], queryFn: listMyPurchases });
  const invoicesQ = useQuery({ queryKey: ["my-invoices"], queryFn: () => listMyInvoices({ limit: 200 }) });
  const alertsQ = useQuery({ queryKey: ["my-alerts"], queryFn: fetchMyAlerts });

  const summary = useMemo(() => {
    const purchases = purchasesQ.data ?? [];
    const invoices = invoicesQ.data ?? [];
    const alerts = alertsQ.data ?? [];
    const today = todayIsoPrefix();

    const todayPurchases = purchases.filter((p) => p.created_at?.startsWith(today));
    const pendingPurchases = purchases.filter((p) => (p.status ?? "").toLowerCase().includes("pending")).length;
    const unresolvedAlerts = alerts.filter((a) => (a.status ?? "").toLowerCase() !== "resolved").length;
    const pendingInvoices = invoices.filter((i) => !["approved", "ready"].includes((i.status ?? "").toLowerCase())).length;

    return {
      todayPurchases: todayPurchases.length,
      todayAmount: todayPurchases.reduce((sum, p) => sum + Number(p.total_amount ?? 0), 0),
      pendingPurchases,
      unresolvedAlerts,
      pendingInvoices,
    };
  }, [purchasesQ.data, invoicesQ.data, alertsQ.data]);

  return (
    <EmployeePage className="space-y-8">
      <div className="rounded-2xl border border-emerald-100/70 bg-gradient-to-l from-emerald-100/70 via-emerald-50/60 to-white p-6 text-right shadow-sm">
        <div className="inline-flex items-center rounded-full bg-emerald-200/80 px-3 py-1 text-xs font-semibold text-emerald-900 mb-3">
          Home Dashboard • Modern UI
        </div>
        <h2 className="text-2xl font-bold text-emerald-900">{t("employee.homeTitle")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("employee.homeSubtitle")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-4 space-y-5">
          <div className="rounded-2xl border border-border/60 bg-card p-5 shadow-sm">
            <h3 className="text-base font-semibold text-foreground mb-3">{t("employee.quickActions")}</h3>
            <div className="grid grid-cols-1 gap-2">
              <Link to="/employee/record" className="rounded-xl border border-border bg-background px-4 py-3 text-sm font-medium hover:bg-accent transition-all hover:-translate-y-0.5 hover:shadow-sm">🎤 {t("nav.record")}</Link>
              <Link to="/employee/scan-invoice" className="rounded-xl border border-border bg-background px-4 py-3 text-sm font-medium hover:bg-accent transition-all hover:-translate-y-0.5 hover:shadow-sm">🧾 {t("nav.scanInvoice")}</Link>
              <Link to="/employee/purchases" className="rounded-xl border border-border bg-background px-4 py-3 text-sm font-medium hover:bg-accent transition-all hover:-translate-y-0.5 hover:shadow-sm">📦 {t("nav.myPurchases")}</Link>
              <Link to="/employee/invoices" className="rounded-xl border border-border bg-background px-4 py-3 text-sm font-medium hover:bg-accent transition-all hover:-translate-y-0.5 hover:shadow-sm">📄 {t("nav.myInvoices")}</Link>
              <Link to="/employee/alerts" className="rounded-xl border border-border bg-background px-4 py-3 text-sm font-medium hover:bg-accent transition-all hover:-translate-y-0.5 hover:shadow-sm">🔔 {t("nav.myAlerts")}</Link>
              <Link to="/employee/profile" className="rounded-xl border border-border bg-background px-4 py-3 text-sm font-medium hover:bg-accent transition-all hover:-translate-y-0.5 hover:shadow-sm">👤 {t("nav.profileEmployee")}</Link>
            </div>
          </div>

          <div className="rounded-2xl border border-primary/20 bg-primary/5 p-5 text-sm text-primary shadow-sm">
            {t("employee.pendingInvoices")}: <span className="font-semibold">{summary.pendingInvoices}</span>
          </div>
        </div>

        <div className="lg:col-span-8 space-y-5">
          <div className="rounded-2xl border border-border/60 bg-card p-8 shadow-sm relative overflow-hidden text-center">
            <div className="pointer-events-none absolute -top-16 -right-16 h-48 w-48 rounded-full bg-emerald-200/30 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-16 -left-16 h-48 w-48 rounded-full bg-emerald-900/10 blur-3xl" />
            <div className="relative">
              <h3 className="text-xl font-semibold text-foreground">{t("employee.homeSubtitle")}</h3>
              <p className="text-sm text-muted-foreground mt-2 max-w-xl mx-auto">
                متابعة العمليات اليومية، التنبيهات، وحالة الفواتير من مكان واحد.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <EmployeeKpiCard label={`📌 ${t("employee.todayPurchases")}`} value={summary.todayPurchases} className="rounded-2xl" />
            <EmployeeKpiCard label={`💵 ${t("employee.todayAmount")}`} value={summary.todayAmount} className="rounded-2xl" />
            <EmployeeKpiCard label={`⏳ ${t("employee.pendingPurchases")}`} value={summary.pendingPurchases} className="rounded-2xl" />
            <EmployeeKpiCard label={`🚨 ${t("employee.unresolvedAlerts")}`} value={summary.unresolvedAlerts} className="rounded-2xl" />
          </div>
        </div>
      </div>
    </EmployeePage>
  );
}
