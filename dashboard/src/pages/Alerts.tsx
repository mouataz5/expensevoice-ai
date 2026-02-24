import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchAlerts, resolveAlert } from "../api/alerts";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from "recharts";

const PAGE_SIZE = 10;
const SEV_COLORS: Record<string, string> = {
  critical: "hsl(var(--destructive))",
  warning: "hsl(38 92% 50%)",
  info: "hsl(210 40% 96%)",
};

function sevVariant(sev: string): "destructive" | "secondary" | "outline" {
  const s = sev.toLowerCase();
  if (s === "critical") return "destructive";
  if (s === "warning") return "secondary";
  return "outline";
}

export default function Alerts() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["alerts"], queryFn: fetchAlerts });

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sevFilter, setSevFilter] = useState<string>("all");
  const [qText, setQText] = useState("");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const list = q.data ?? [];
    const byStatus = statusFilter === "all" ? list : list.filter((a) => a.status === statusFilter);
    const bySev = sevFilter === "all" ? byStatus : byStatus.filter((a) => a.severity.toLowerCase() === sevFilter);
    const term = qText.toLowerCase().trim();
    if (!term) return bySev;
    return bySev.filter((a) => {
      const text = `${a.alert_type} ${a.message} ${a.status} ${a.severity}`.toLowerCase();
      return text.includes(term);
    });
  }, [q.data, statusFilter, sevFilter, qText]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const donutData = useMemo(() => {
    return (["critical", "warning", "info"] as const)
      .map((k) => ({
        name: k,
        value: filtered.filter((a) => a.severity.toLowerCase() === k).length,
        fill: SEV_COLORS[k] ?? "hsl(var(--muted-foreground))",
      }))
      .filter((x) => x.value > 0);
  }, [filtered]);

  const m = useMutation({
    mutationFn: (id: string) => resolveAlert(id),
    onSuccess: () => {
      toast.success(t("alerts.resolved_ok"));
      qc.invalidateQueries({ queryKey: ["alerts"] });
    },
    onError: () => toast.error(t("alerts.resolved_fail")),
  });

  if (q.isLoading)
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-72" />
        </div>
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );

  return (
    <div className="space-y-6">
      <div>
        <div className="text-2xl font-semibold">{t("alerts.title")}</div>
        <div className="text-sm text-muted-foreground">{t("alerts.subtitle")}</div>
      </div>

      {donutData.length > 0 && (
        <Card className="rounded-2xl">
          <CardContent className="p-5">
            <div className="font-medium mb-3">{t("alerts.severityDist")}</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                  >
                    {donutData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="rounded-2xl">
        <CardContent className="p-5">
          {q.isError && <div className="text-sm text-destructive mb-4">{t("alerts.error")}</div>}

          {q.data && (
            <>
              <div className="flex flex-wrap items-center gap-3 mb-4">
                <Input
                  className="rounded-xl max-w-sm"
                  placeholder={t("alerts.search")}
                  value={qText}
                  onChange={(e) => {
                    setQText(e.target.value);
                    setPage(1);
                  }}
                />
                <div className="w-48">
                  <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
                    <SelectTrigger className="rounded-xl">
                      <SelectValue placeholder={t("alerts.status")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t("alerts.filter_all")}</SelectItem>
                      <SelectItem value="new">{t("alerts.filter_new")}</SelectItem>
                      <SelectItem value="ack">{t("alerts.filter_ack")}</SelectItem>
                      <SelectItem value="resolved">{t("alerts.filter_resolved")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="w-48">
                  <Select value={sevFilter} onValueChange={(v) => { setSevFilter(v); setPage(1); }}>
                    <SelectTrigger className="rounded-xl">
                      <SelectValue placeholder={t("alerts.severity")} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t("alerts.filter_all")}</SelectItem>
                      <SelectItem value="info">{t("alerts.filter_info")}</SelectItem>
                      <SelectItem value="warning">{t("alerts.filter_warning")}</SelectItem>
                      <SelectItem value="critical">{t("alerts.filter_critical")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="text-sm text-muted-foreground">
                  {filtered.length} {t("alerts.results")}
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("alerts.severity")}</TableHead>
                    <TableHead>{t("alerts.status")}</TableHead>
                    <TableHead>{t("alerts.type")}</TableHead>
                    <TableHead>{t("alerts.message")}</TableHead>
                    <TableHead className="text-right">{t("alerts.action")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pageData.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell>
                        <Badge variant={sevVariant(a.severity)}>{a.severity}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={a.status === "resolved" ? "outline" : "secondary"}>
                          {a.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium">{a.alert_type}</TableCell>
                      <TableCell className="max-w-[520px] truncate">{a.message}</TableCell>
                      <TableCell className="text-right">
                        {a.status !== "resolved" ? (
                          <Button
                            size="sm"
                            className="rounded-xl"
                            onClick={() => m.mutate(a.id)}
                            disabled={m.isPending}
                          >
                            {t("alerts.resolve")}
                          </Button>
                        ) : (
                          <span className="text-sm text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {pageData.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-muted-foreground">
                        {q.data.length === 0 ? t("alerts.noAlerts") : t("alerts.noAlertsFilter")}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              {filtered.length > 0 && (
                <div className="flex items-center justify-between mt-4">
                  <div className="text-sm text-muted-foreground">
                    {t("alerts.page")} {page} {t("alerts.of")} {totalPages}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-xl"
                      disabled={page === 1}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      {t("alerts.prev")}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-xl"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      {t("alerts.next")}
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
