import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAlerts, resolveAlert } from "../api/alerts";

export default function Alerts() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["alerts"], queryFn: fetchAlerts });

  const m = useMutation({
    mutationFn: (id: string) => resolveAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  if (q.isLoading) return <div>Loading alerts...</div>;
  if (q.isError) return <div>Error loading alerts</div>;

  return (
    <div style={{ padding: 16, fontFamily: "system-ui" }}>
      <h2>Alerts</h2>
      <ul style={{ paddingLeft: 16 }}>
        {q.data!.map((a) => (
          <li key={a.id} style={{ marginBottom: 12 }}>
            <b>{a.severity.toUpperCase()}</b> [{a.status}] — {a.alert_type}
            <div>{a.message}</div>
            {a.status !== "resolved" && (
              <button
                onClick={() => m.mutate(a.id)}
                disabled={m.isPending}
              >
                Resolve
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
