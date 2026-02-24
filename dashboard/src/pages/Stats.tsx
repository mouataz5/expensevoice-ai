import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../api/dashboard";
import { fetchUsersMap } from "../api/users";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip } from "recharts";

export default function Stats() {
  const statsQ = useQuery({ queryKey: ["stats"], queryFn: fetchStats });
  const mapQ = useQuery({ queryKey: ["users-map"], queryFn: fetchUsersMap });

  if (statsQ.isLoading) return <div className="text-sm text-muted-foreground">Loading stats...</div>;
  if (statsQ.isError) return <div className="text-sm text-destructive">Error loading stats</div>;

  const stats = statsQ.data!;
  const userMap = new Map((mapQ.data ?? []).map(u => [u.id, u]));

  const trend = stats.daily_trend_last_14_days.map(d => ({
    date: d.date.slice(5), // MM-DD
    total: d.total_amount,
    count: d.count,
  }));

  return (
    <div className="space-y-6">
      <div>
        <div className="text-2xl font-semibold">Overview</div>
        <div className="text-sm text-muted-foreground">Last 14 days + month summary</div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi title="Today amount" value={stats.total_amount_today} />
        <Kpi title="Month amount" value={stats.total_amount_month} />
        <Kpi title="Purchases today" value={stats.purchases_today} />
        <Kpi title="Purchases month" value={stats.purchases_month} />
      </div>

      <Card className="rounded-2xl">
        <CardContent className="p-5">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="font-medium">Daily amount trend</div>
              <div className="text-sm text-muted-foreground">Last 14 days</div>
            </div>
            <Badge variant="secondary">{trend.length} days</Badge>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend}>
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="total" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="rounded-2xl">
          <CardContent className="p-5">
            <div className="font-medium mb-3">Top users (month)</div>
            <ul className="space-y-2">
              {stats.top_users.map((u) => {
                const info = userMap.get(u.user_id);
                return (
                  <li key={u.user_id} className="flex items-center justify-between text-sm">
                    <div className="truncate">
                      {info ? info.email : u.user_id}
                      {info?.role && <span className="text-muted-foreground"> — {info.role}</span>}
                    </div>
                    <div className="text-muted-foreground">
                      {u.total_amount} / {u.count}
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardContent className="p-5">
            <div className="font-medium mb-3">By category (month)</div>
            <ul className="space-y-2">
              {stats.by_category.map((c, idx) => (
                <li key={idx} className="flex items-center justify-between text-sm">
                  <div className="truncate">{c.category ?? "(none)"}</div>
                  <div className="text-muted-foreground">
                    {c.total_amount} / {c.count}
                  </div>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Kpi({ title, value }: { title: string; value: number }) {
  return (
    <Card className="rounded-2xl">
      <CardContent className="p-5">
        <div className="text-sm text-muted-foreground">{title}</div>
        <div className="text-2xl font-semibold mt-1">{value}</div>
      </CardContent>
    </Card>
  );
}
