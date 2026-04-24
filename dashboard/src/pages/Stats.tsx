import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchStats } from "../api/dashboard";
import { createFarm, listFarms } from "../api/farms";
import { downloadFile } from "../api/download";
import { fetchUsersMap } from "../api/users";
import { fetchMe } from "../api/me";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/PageHeader";
import { Toolbar } from "@/components/Toolbar";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { SkeletonCard, SkeletonKpi } from "@/components/SkeletonCard";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
} from "recharts";

function getLocale(lng: string): string {
  if (lng === "ar") return "ar-TN";
  if (lng === "fr") return "fr-FR";
  return "en-GB";
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}
function startOfMonthISO() {
  const d = new Date();
  const first = new Date(d.getFullYear(), d.getMonth(), 1);
  return first.toISOString().slice(0, 10);
}
function daysAgoISO(n: number) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function Stats() {
  const { t, i18n } = useTranslation();
  const locale = getLocale(i18n.language);
  const fmtTND = useMemo(
    () => new Intl.NumberFormat(locale, { style: "currency", currency: "TND" }),
    [locale]
  );
  const fmtNum = useMemo(() => new Intl.NumberFormat(locale), [locale]);

  const [from, setFrom] = useState(startOfMonthISO());
  const [to, setTo] = useState(todayISO());
  const [selectedFarmId, setSelectedFarmId] = useState("");
  const [farmName, setFarmName] = useState("");
  const [farmFormError, setFarmFormError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const statsQ = useQuery({
    queryKey: ["stats", from, to, selectedFarmId || "all"],
    queryFn: () => fetchStats(from, to, selectedFarmId || undefined),
    retry: 2,
  });
  const farmsQ = useQuery({ queryKey: ["farms"], queryFn: listFarms, retry: 1 });
  const mapQ = useQuery({ queryKey: ["users-map"], queryFn: fetchUsersMap });
  const meQ = useQuery({ queryKey: ["me"], queryFn: fetchMe, retry: 1 });

  const createFarmM = useMutation({
    mutationFn: (name: string) => createFarm(name),
    onSuccess: async (farm) => {
      setFarmName("");
      setFarmFormError(null);
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      setSelectedFarmId(farm.id);
    },
    onError: (error: unknown) => {
      const statusCode = (error as { response?: { status?: number } })?.response?.status;
      setFarmFormError(statusCode === 409 ? t("stats.farmDuplicate") : t("stats.farmCreateError"));
    },
  });

  const trend = useMemo(() => {
    const s = statsQ.data?.daily_trend_last_14_days ?? [];
    return s.map((d) => ({
      date: (d.date && String(d.date).slice(0, 10).slice(5)) || "—",
      total: Number(d.total_amount) || 0,
      count: Number(d.count) || 0,
    }));
  }, [statsQ.data]);

  if (statsQ.isLoading)
    return (
      <div className="space-y-6">
        <div className="space-y-1">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-64" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonKpi key={i} />
          ))}
        </div>
        <SkeletonCard showChart className="h-64" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SkeletonCard lines={5} />
          <SkeletonCard showChart />
        </div>
      </div>
    );
  if (statsQ.isError) {
    const statusCode = (statsQ.error as { response?: { status?: number } })?.response?.status;
    return (
      <div className="space-y-4">
        <PageHeader title={t("stats.overview")} />
        <EmptyState
          title={t("stats.error")}
          description={
            statusCode === 403
              ? "هذه الصفحة للمدير أو الأدمن فقط."
              : "تحقق من اتصال الـ API وأنك مسجّل كمدير أو أدمن."
          }
          action={
            <Button variant="outline" className="rounded-xl" onClick={() => statsQ.refetch()}>
              إعادة المحاولة
            </Button>
          }
        />
      </div>
    );
  }

  const stats = statsQ.data;
  if (!stats)
    return (
      <div className="text-sm text-muted-foreground">
        {t("stats.loading")}
      </div>
    );

  const userMap = new Map((mapQ.data ?? []).map((u) => [u.id, u]));
  const byCategory = stats.by_category ?? [];
  const topUsers = stats.top_users ?? [];

  const categoryBar = byCategory.map((c) => ({
    name: c?.category ?? "—",
    total: Number(c?.total_amount) ?? 0,
  }));
  const canManageFarms = meQ.data?.role === "admin";

  const onCreateFarm = () => {
    const normalized = farmName.trim();
    if (normalized.length < 2) {
      setFarmFormError(t("stats.farmMinChars"));
      return;
    }
    setFarmFormError(null);
    createFarmM.mutate(normalized);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("stats.overview")}
        subtitle={t("stats.filter")}
        actions={
          <Button
            variant="outline"
            className="rounded-xl"
            onClick={() =>
              downloadFile(`/export/stats.pdf?from=${from}&to=${to}`, "stats.pdf")
            }
          >
            تنزيل تقرير PDF
          </Button>
        }
      />

      <Toolbar className="flex-wrap gap-3 items-end">
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">{t("stats.farm")}</div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant={!selectedFarmId ? "default" : "outline"}
              size="sm"
              className="rounded-xl"
              onClick={() => setSelectedFarmId("")}
            >
              {t("stats.global")}
            </Button>
            {(farmsQ.data ?? []).map((farm) => (
              <Button
                key={farm.id}
                variant={selectedFarmId === farm.id ? "default" : "outline"}
                size="sm"
                className="rounded-xl"
                onClick={() => setSelectedFarmId(farm.id)}
              >
                {farm.name}
              </Button>
            ))}
          </div>
        </div>
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">{t("stats.from")}</div>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <div className="space-y-1">
          <div className="text-xs text-muted-foreground">{t("stats.to")}</div>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
        <Button
          variant="outline"
          size="sm"
          className="rounded-xl"
          onClick={() => { setFrom(daysAgoISO(6)); setTo(todayISO()); }}
        >
          {t("stats.last7")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="rounded-xl"
          onClick={() => { setFrom(daysAgoISO(13)); setTo(todayISO()); }}
        >
          {t("stats.last14")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="rounded-xl"
          onClick={() => { setFrom(startOfMonthISO()); setTo(todayISO()); }}
        >
          {t("stats.thisMonth")}
        </Button>
        {canManageFarms ? (
          <div className="space-y-1 min-w-[240px]">
            <div className="text-xs text-muted-foreground">{t("stats.addFarm")}</div>
            <div className="flex gap-2">
              <Input
                value={farmName}
                onChange={(e) => setFarmName(e.target.value)}
                placeholder={t("stats.farmNamePlaceholder")}
              />
              <Button
                onClick={onCreateFarm}
                disabled={createFarmM.isPending}
                className="rounded-xl"
              >
                {createFarmM.isPending ? t("stats.creatingFarm") : t("stats.createFarm")}
              </Button>
            </div>
            {farmFormError ? <div className="text-xs text-destructive">{farmFormError}</div> : null}
          </div>
        ) : null}
      </Toolbar>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi title={t("stats.todayAmount")} value={Number(stats.total_amount_today) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.rangeAmount")} value={Number(stats.total_amount_month) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.todayCount")} value={Number(stats.purchases_today) ?? 0} format="number" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.rangeCount")} value={Number(stats.purchases_month) ?? 0} format="number" fmtTND={fmtTND} fmtNum={fmtNum} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi title={t("stats.cashInToday")} value={Number(stats.inflow_today) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.cashOutToday")} value={Number(stats.outflow_today) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.grossMargin")} value={Number(stats.gross_margin_month) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.netProfit")} value={Number(stats.net_profit_month) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi title={t("stats.fixedExpenses")} value={Number(stats.fixed_expenses_month) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.variableExpenses")} value={Number(stats.variable_expenses_month) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.poussinsSales")} value={Number(stats.poussins_sales_month) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.feedSales")} value={Number(stats.nourriture_sales_month) ?? 0} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
      </div>

      {(Number(stats.purchases_month) ?? 0) === 0 && (Number(stats.total_amount_month) ?? 0) === 0 && (
        <EmptyState
          title="لا توجد عمليات في الفترة المحددة"
          description="غيّر التواريخ أو سجّل عمليات جديدة."
        />
      )}

      <Card className="rounded-2xl">
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="font-medium">{t("stats.trend")}</div>
              <div className="text-sm text-muted-foreground">
                {from} ← {to}
              </div>
            </div>
            <Badge variant="secondary">{trend.length} {t("stats.days")}</Badge>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="total"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                  name={t("stats.rangeAmount")}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  strokeWidth={2}
                  dot={false}
                  stroke="hsl(var(--muted-foreground))"
                  name={t("stats.rangeCount")}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="rounded-2xl">
          <CardContent className="p-5">
            <div className="font-medium mb-3">{t("stats.topUsers")}</div>
            <ul className="space-y-2">
              {topUsers.map((u) => {
                const info = userMap.get(u?.user_id ?? "");
                return (
                  <li
                    key={u?.user_id ?? ""}
                    className="flex items-center justify-between text-sm"
                  >
                    <div className="truncate">
                      {info ? info.email : (u?.user_id ?? "—")}
                      {info?.role && (
                        <span className="text-muted-foreground">
                          {" "}
                          — {info.role}
                        </span>
                      )}
                    </div>
                    <div className="text-muted-foreground">
                      {fmtTND.format(Number(u?.total_amount) ?? 0)} / {fmtNum.format(Number(u?.count) ?? 0)}
                    </div>
                  </li>
                );
              })}
              {topUsers.length === 0 && (
                <li className="text-sm text-muted-foreground">—</li>
              )}
            </ul>
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardContent className="p-5">
            <div className="font-medium mb-3">{t("stats.byCategory")}</div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryBar}>
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(v: number) => fmtTND.format(v)} />
                  <Bar
                    dataKey="total"
                    fill="hsl(var(--primary))"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Kpi({
  title,
  value,
  format = "number",
  fmtTND,
  fmtNum,
}: {
  title: string;
  value: number;
  format?: "currency" | "number";
  fmtTND: Intl.NumberFormat;
  fmtNum: Intl.NumberFormat;
}) {
  const display = format === "currency" ? fmtTND.format(value) : fmtNum.format(value);
  return (
    <Card className="rounded-2xl">
      <CardContent className="p-5">
        <div className="text-sm text-muted-foreground">{title}</div>
        <div className="text-2xl font-semibold mt-1">{display}</div>
      </CardContent>
    </Card>
  );
}
