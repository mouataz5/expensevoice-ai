import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../api/dashboard";
import { fetchUsersMap } from "../api/users";

function Card({
  title,
  value,
}: {
  title: string;
  value: number;
}) {
  return (
    <div
      style={{
        border: "1px solid #ddd",
        borderRadius: 10,
        padding: 12,
        minWidth: 180,
      }}
    >
      <div style={{ color: "#555", fontSize: 12 }}>{title}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

export default function Stats() {
  const statsQ = useQuery({ queryKey: ["stats"], queryFn: fetchStats });
  const mapQ = useQuery({ queryKey: ["users-map"], queryFn: fetchUsersMap });

  if (statsQ.isLoading) return <div>Loading stats...</div>;
  if (statsQ.isError) return <div>Error loading stats</div>;

  const stats = statsQ.data!;
  const userMap = new Map((mapQ.data ?? []).map((u) => [u.id, u]));

  return (
    <div style={{ padding: 16, fontFamily: "system-ui" }}>
      <h2>Stats</h2>

      <div
        style={{ display: "flex", gap: 16, flexWrap: "wrap" }}
      >
        <Card title="Today amount" value={stats.total_amount_today} />
        <Card title="Month amount" value={stats.total_amount_month} />
        <Card title="Purchases today" value={stats.purchases_today} />
        <Card title="Purchases month" value={stats.purchases_month} />
      </div>

      <h3 style={{ marginTop: 24 }}>Top users (month)</h3>
      <ul>
        {stats.top_users.map((u) => {
          const info = userMap.get(u.user_id);
          return (
            <li key={u.user_id}>
              {info
                ? `${info.email} (${info.role})`
                : u.user_id}{" "}
              — total {u.total_amount} / count {u.count}
            </li>
          );
        })}
      </ul>

      <h3 style={{ marginTop: 24 }}>By category (month)</h3>
      <ul>
        {stats.by_category.map((c, idx) => (
          <li key={idx}>
            {c.category ?? "(none)"} — total {c.total_amount} / count{" "}
            {c.count}
          </li>
        ))}
      </ul>
    </div>
  );
}
