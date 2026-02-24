import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

type AlertOut = {
  id: string;
  alert_type: string;
  message: string;
  severity: string;
  status: string;
  created_at: string;
};

async function fetchMyAlerts(): Promise<AlertOut[]> {
  const res = await api.get("/api/alerts/me");
  return res.data;
}

export default function EmployeeAlerts() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["my-alerts"], queryFn: fetchMyAlerts });

  return (
    <div className="space-y-6">
      <div>
        <div className="text-2xl font-semibold">
          {t("employee.myAlertsTitle")}
        </div>
        <div className="text-sm text-muted-foreground">
          {t("employee.myAlertsSubtitle")}
        </div>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-3">
          {q.isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-6 w-32" />
              <Skeleton className="h-20 w-full rounded-xl" />
              <Skeleton className="h-20 w-full rounded-xl" />
            </div>
          )}
          {q.isError && (
            <div className="text-sm text-destructive">
              {t("employee.alertsLoadError")}
            </div>
          )}

          {q.data?.length === 0 && !q.isLoading && (
            <div className="text-sm text-muted-foreground">
              {t("employee.noAlerts")}
            </div>
          )}

          {q.data?.map((a) => (
            <div key={a.id} className="border rounded-xl p-3">
              <div className="flex items-center justify-between">
                <div className="font-medium">{a.alert_type}</div>
                <Badge
                  variant={
                    a.severity === "critical" ? "destructive" : "secondary"
                  }
                >
                  {a.severity}
                </Badge>
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                {a.message}
              </div>
              <div className="text-xs text-muted-foreground mt-2">
                {a.status} •{" "}
                {new Date(a.created_at).toLocaleString()}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
