import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchAlerts, resolveAlert } from "../api/alerts";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export default function Alerts() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["alerts"], queryFn: fetchAlerts });
  const m = useMutation({
    mutationFn: (id: string) => resolveAlert(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });

  if (q.isLoading) return <div className="text-sm text-muted-foreground">Loading alerts...</div>;
  if (q.isError) return <div className="text-sm text-destructive">Error loading alerts</div>;

  const alerts = q.data!;

  return (
    <div className="space-y-6">
      <div>
        <div className="text-2xl font-semibold">Alerts</div>
        <div className="text-sm text-muted-foreground">Policy violations and resolutions</div>
      </div>

      <div className="space-y-4">
        {alerts.length === 0 ? (
          <Card className="rounded-2xl">
            <CardContent className="p-8 text-center text-muted-foreground">
              No alerts at the moment.
            </CardContent>
          </Card>
        ) : (
          alerts.map((a) => (
            <Card key={a.id} className="rounded-2xl">
              <CardContent className="p-5">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <Badge
                    variant={
                      a.severity === "high" || a.severity === "critical"
                        ? "destructive"
                        : "secondary"
                    }
                  >
                    {a.severity.toUpperCase()}
                  </Badge>
                  <Badge variant="outline">{a.status}</Badge>
                  <span className="text-sm font-medium">{a.alert_type}</span>
                </div>
                <p className="text-sm text-muted-foreground mb-3">{a.message}</p>
                {a.status !== "resolved" && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => m.mutate(a.id)}
                    disabled={m.isPending}
                  >
                    Resolve
                  </Button>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
