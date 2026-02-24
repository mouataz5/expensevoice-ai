import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../api/dashboard";
import { fetchUsersMap } from "../api/users";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
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

  const statsQ = useQuery({
    queryKey: ["stats", from, to],
    queryFn: () => fetchStats(from, to),
  });
  const mapQ = useQuery({ queryKey: ["users-map"], queryFn: fetchUsersMap });

  const trend = useMemo(() => {
    const s = statsQ.data?.daily_trend_last_14_days ?? [];
    return s.map((d) => ({
      date: d.date.slice(5),
      total: d.total_amount,
      count: d.count,
    }));
  }, [statsQ.data]);

  if (statsQ.isLoading)
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-4 w-56" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-2xl" />
          ))}
        </div>
        <Skeleton className="h-72 rounded-2xl" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Skeleton className="h-64 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </div>
    );
  if (statsQ.isError)
    return (
      <div className="text-sm text-destructive">{t("stats.error")}</div>
    );

  const stats = statsQ.data!;
  const userMap = new Map((mapQ.data ?? []).map((u) => [u.id, u]));

  const categoryBar = stats.by_category.map((c) => ({
    name: c.category ?? "—",
    total: c.total_amount,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="text-2xl font-semibold">{t("stats.overview")}</div>
          <div className="text-sm text-muted-foreground">
            {t("stats.filter")}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 items-end">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">{t("stats.from")}</div>
            <Input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="rounded-xl"
            />
          </div>
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">{t("stats.to")}</div>
            <Input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="rounded-xl"
            />
          </div>

          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="rounded-xl"
              onClick={() => {
                setFrom(daysAgoISO(6));
                setTo(todayISO());
              }}
            >
              {t("stats.last7")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="rounded-xl"
              onClick={() => {
                setFrom(daysAgoISO(13));
                setTo(todayISO());
              }}
            >
              {t("stats.last14")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="rounded-xl"
              onClick={() => {
                setFrom(startOfMonthISO());
                setTo(todayISO());
              }}
            >
              {t("stats.thisMonth")}
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi title={t("stats.todayAmount")} value={stats.total_amount_today} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.rangeAmount")} value={stats.total_amount_month} format="currency" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.todayCount")} value={stats.purchases_today} format="number" fmtTND={fmtTND} fmtNum={fmtNum} />
        <Kpi title={t("stats.rangeCount")} value={stats.purchases_month} format="number" fmtTND={fmtTND} fmtNum={fmtNum} />
      </div>

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
              {stats.top_users.map((u) => {
                const info = userMap.get(u.user_id);
                return (
                  <li
                    key={u.user_id}
                    className="flex items-center justify-between text-sm"
                  >
                    <div className="truncate">
                      {info ? info.email : u.user_id}
                      {info?.role && (
                        <span className="text-muted-foreground">
                          {" "}
                          — {info.role}
                        </span>
                      )}
                    </div>
                    <div className="text-muted-foreground">
                      {fmtTND.format(u.total_amount)} / {fmtNum.format(u.count)}
                    </div>
                  </li>
                );
              })}
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
