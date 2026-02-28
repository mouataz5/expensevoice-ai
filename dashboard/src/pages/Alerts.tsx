import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchAlerts, resolveAlert } from "../api/alerts";
import { downloadFile } from "../api/download";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/PageHeader";
import { FilterToolbar } from "@/components/FilterToolbar";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonCard } from "@/components/SkeletonCard";
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from "recharts";

const PAGE_SIZE = 10;
const SEV_COLORS: Record<string, string> = {
  critical: "hsl(var(--destructive))",
  warning: "hsl(var(--warning))",
  info: "hsl(var(--accent))",
};

function sevVariant(sev: string): "destructive" | "warning" | "info" | "outline" {
  const s = sev.toLowerCase();
  if (s === "critical") return "destructive";
  if (s === "warning") return "warning";
  if (s === "info") return "info";
  return "outline";
}

export default function Alerts() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["alerts"], queryFn: fetchAlerts, retry: 2 });

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sevFilter, setSevFilter] = useState<string>("all");
  const [qText, setQText] = useState("");
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const list = Array.isArray(q.data) ? q.data : [];
    const byStatus = statusFilter === "all" ? list : list.filter((a) => (a?.status ?? "") === statusFilter);
    const bySev = sevFilter === "all" ? byStatus : byStatus.filter((a) => (a?.severity ?? "").toLowerCase() === sevFilter);
    const term = qText.toLowerCase().trim();
    if (!term) return bySev;
    return bySev.filter((a) => {
      const text = `${a?.alert_type ?? ""} ${a?.message ?? ""} ${a?.status ?? ""} ${a?.severity ?? ""}`.toLowerCase();
      return text.includes(term);
    });
  }, [q.data, statusFilter, sevFilter, qText]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageData = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const donutData = useMemo(() => {
    return (["critical", "warning", "info"] as const)
      .map((k) => ({
        name: k,
        value: filtered.filter((a) => (a?.severity ?? "").toLowerCase() === k).length,
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
        <PageHeader title={t("alerts.title")} subtitle={t("alerts.subtitle")} />
        <SkeletonCard showChart className="h-64" />
        <SkeletonCard lines={8} className="min-h-96" />
      </div>
    );

  return (
    <div className="space-y-6">
      <PageHeader title={t("alerts.title")} subtitle={t("alerts.subtitle")} />

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

      <Card>
        <CardContent className="p-5">
          {q.isError && (
            <div className="mb-4">
              <EmptyState
                title={t("alerts.error")}
                description={
                  ((q.error as { response?: { status?: number } })?.response?.status ?? 0) === 403
                    ? "هذه الصفحة للمدير أو الأدمن فقط."
                    : "تحقق من الاتصال أو جرّب إعادة المحاولة."
                }
                action={
                  <Button variant="outline" size="sm" className="rounded-xl" onClick={() => q.refetch()}>
                    إعادة المحاولة
                  </Button>
                }
              />
            </div>
          )}

          {q.data && !q.isError && (
            <>
              <FilterToolbar
                className="mb-4"
                search={qText}
                onSearchChange={(v) => { setQText(v); setPage(1); }}
                searchPlaceholder={t("alerts.search")}
                statusOptions={[
                  { value: "all", label: t("alerts.filter_all") },
                  { value: "new", label: t("alerts.filter_new") },
                  { value: "ack", label: t("alerts.filter_ack") },
                  { value: "resolved", label: t("alerts.filter_resolved") },
                ]}
                status={statusFilter}
                onStatusChange={(v) => { setStatusFilter(v); setPage(1); }}
                statusPlaceholder={t("alerts.status")}
                categoryOptions={["info", "warning", "critical"]}
                category={sevFilter}
                onCategoryChange={(v) => { setSevFilter(v); setPage(1); }}
                categoryPlaceholder={t("alerts.severity")}
                onClear={() => { setStatusFilter("all"); setSevFilter("all"); setQText(""); setPage(1); }}
                clearLabel={t("alerts.clear_filters")}
              >
                <span className="text-sm text-muted-foreground ms-auto">
                  {filtered.length} {t("alerts.results")}
                </span>
                <Button variant="outline" className="rounded-xl" onClick={() => downloadFile("/export/alerts.csv", "alerts.csv")}>
                  تنزيل CSV
                </Button>
                <Button variant="outline" className="rounded-xl" onClick={() => downloadFile("/export/alerts.pdf", "alerts.pdf")}>
                  تنزيل PDF
                </Button>
              </FilterToolbar>

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
                    <TableRow key={a?.id ?? ""}>
                      <TableCell>
                        <Badge variant={sevVariant(a?.severity ?? "")}>{a?.severity ?? "—"}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={(a?.status ?? "") === "resolved" ? "outline" : "secondary"}>
                          {a?.status ?? "—"}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-medium">{a?.alert_type ?? "—"}</TableCell>
                      <TableCell className="max-w-[520px] truncate">{a?.message ?? "—"}</TableCell>
                      <TableCell className="text-right">
                        {(a?.status ?? "") !== "resolved" && a?.id ? (
                          <Button
                            size="sm"
                            className="rounded-xl"
                            onClick={() => m.mutate(String(a.id))}
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
                        {(q.data?.length ?? 0) === 0 ? t("alerts.noAlerts") : t("alerts.noAlertsFilter")}
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
