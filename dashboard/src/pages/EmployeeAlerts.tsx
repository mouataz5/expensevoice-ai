import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { resolveAlert } from "../api/alerts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonCard } from "@/components/SkeletonCard";
import { EmployeeHero, EmployeePage, EmployeeSectionCard } from "@/components/employee/EmployeeShell";

type AlertOut = {
  id: string;
  purchase_id?: string | null;
  alert_type: string;
  message: string;
  severity: string;
  status: string;
  created_at: string;
};

async function fetchMyAlerts(): Promise<AlertOut[]> {
  const res = await api.get("/alerts/me");
  return res.data;
}

export default function EmployeeAlerts() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["my-alerts"], queryFn: fetchMyAlerts, retry: 2 });
  const resolveM = useMutation({
    mutationFn: (id: string) => resolveAlert(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["my-alerts"] });
      void qc.invalidateQueries({ queryKey: ["my-purchases"] });
    },
  });

  function severityVariant(sev: string): "destructive" | "warning" | "info" | "secondary" {
    const s = (sev ?? "").toLowerCase();
    if (s === "critical") return "destructive";
    if (s === "warning") return "warning";
    if (s === "info") return "info";
    return "secondary";
  }

  const grouped = {
    urgent: (q.data ?? []).filter((a) => ["critical", "high"].includes((a.severity ?? "").toLowerCase()) && (a.status ?? "").toLowerCase() !== "resolved"),
    open: (q.data ?? []).filter((a) => !["critical", "high"].includes((a.severity ?? "").toLowerCase()) && (a.status ?? "").toLowerCase() !== "resolved"),
    resolved: (q.data ?? []).filter((a) => (a.status ?? "").toLowerCase() === "resolved"),
  };

  const renderAlertCard = (a: AlertOut) => (
    <div key={a?.id ?? ""} className="border border-border rounded-2xl p-4 bg-card hover:bg-primary/5 transition-all hover:-translate-y-0.5">
      <div className="flex items-center justify-between">
        <div className="font-medium">{a?.alert_type ?? "—"}</div>
        <Badge variant={severityVariant(a?.severity ?? "")}>
          {a?.severity ?? "—"}
        </Badge>
      </div>
      <div className="text-sm text-muted-foreground mt-1">
        {a?.message ?? "—"}
      </div>
      <div className="text-xs text-muted-foreground mt-2">
        {a?.status ?? "—"} •{" "}
        {a?.created_at ? new Date(a.created_at).toLocaleString() : "—"}
      </div>
      {(a?.status ?? "").toLowerCase() !== "resolved" ? (
        <div className="mt-3 flex items-center gap-2">
          {a.purchase_id ? (
            <Link to={`/purchases/${a.purchase_id}`} className="text-sm underline text-primary">
              {t("employee.view")}
            </Link>
          ) : null}
          <Button
            size="sm"
            variant="outline"
            className="rounded-xl"
            onClick={() => resolveM.mutate(a.id)}
            disabled={resolveM.isPending}
          >
            {t("alerts.resolve")}
          </Button>
        </div>
      ) : null}
    </div>
  );

  return (
    <EmployeePage>
      <EmployeeHero
        eyebrow="Employee Dashboard"
        title={t("employee.myAlertsTitle")}
        subtitle={t("employee.myAlertsSubtitle")}
        meta={[
          {
            label: t("employee.results"),
            value: (q.data ?? []).filter((a) => (a.status ?? "").toLowerCase() !== "resolved").length,
          },
        ]}
      />
      <PageHeader title={t("employee.myAlertsTitle")} subtitle={t("employee.myAlertsSubtitle")} />

      <EmployeeSectionCard>
          {q.isLoading && <SkeletonCard lines={4} />}
          {q.isError && (
            <EmptyState
              title={t("employee.alertsLoadError")}
              action={<Button variant="outline" className="rounded-xl" onClick={() => q.refetch()}>{t("common.retry")}</Button>}
            />
          )}

          {q.data?.length === 0 && !q.isLoading && !q.isError && (
            <EmptyState title={t("employee.noAlerts")} description={t("employee.myAlertsSubtitle")} />
          )}

          {q.data && q.data.length > 0 && (
            <div className="space-y-5">
              {grouped.urgent.length > 0 ? (
                <div className="space-y-3">
                  <div className="text-sm font-semibold text-destructive">Urgent ({grouped.urgent.length})</div>
                  {grouped.urgent.map(renderAlertCard)}
                </div>
              ) : null}
              {grouped.open.length > 0 ? (
                <div className="space-y-3">
                  <div className="text-sm font-semibold text-primary">Open ({grouped.open.length})</div>
                  {grouped.open.map(renderAlertCard)}
                </div>
              ) : null}
              {grouped.resolved.length > 0 ? (
                <div className="space-y-3">
                  <div className="text-sm font-semibold text-muted-foreground">Resolved ({grouped.resolved.length})</div>
                  {grouped.resolved.map(renderAlertCard)}
                </div>
              ) : null}
            </div>
          )}
      </EmployeeSectionCard>
    </EmployeePage>
  );
}
