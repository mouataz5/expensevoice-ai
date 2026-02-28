import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonCard } from "@/components/SkeletonCard";

type AlertOut = {
  id: string;
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
  const q = useQuery({ queryKey: ["my-alerts"], queryFn: fetchMyAlerts, retry: 2 });

  function severityVariant(sev: string): "destructive" | "warning" | "info" | "secondary" {
    const s = (sev ?? "").toLowerCase();
    if (s === "critical") return "destructive";
    if (s === "warning") return "warning";
    if (s === "info") return "info";
    return "secondary";
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t("employee.myAlertsTitle")} subtitle={t("employee.myAlertsSubtitle")} />

      <Card>
        <CardContent className="p-5 space-y-3">
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

          {q.data && q.data.length > 0 && q.data.map((a) => (
            <div key={a?.id ?? ""} className="border border-border rounded-2xl p-4 hover:bg-primary/5 transition-colors">
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
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
