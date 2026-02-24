import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchPolicies, updatePolicy } from "../api/policies";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function Policies() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["policies"], queryFn: fetchPolicies });
  const [limits, setLimits] = useState({
    max_per_purchase: 500,
    daily_limit_default: 1500,
  });
  const [categories, setCategories] = useState(
    "vente_poulet,achat_aliment,materiel,transport,autre"
  );
  const [activeLimits, setActiveLimits] = useState(true);
  const [activeCategories, setActiveCategories] = useState(true);

  useEffect(() => {
    if (!q.data) return;
    const limitsP = q.data.find((p) => p.policy_type === "limits");
    const catP = q.data.find((p) => p.policy_type === "categories");

    if (limitsP) {
      setLimits({
        max_per_purchase: Number(limitsP.rule?.max_per_purchase ?? 500),
        daily_limit_default: Number(
          limitsP.rule?.daily_limit_default ?? 1500
        ),
      });
      setActiveLimits(!!limitsP.is_active);
    }
    if (catP) {
      setCategories((catP.rule?.allowed ?? []).join(","));
      setActiveCategories(!!catP.is_active);
    }
  }, [q.data]);

  const m = useMutation({
    mutationFn: ({
      type,
      rule,
      active,
    }: {
      type: string;
      rule: Record<string, unknown>;
      active: boolean;
    }) => updatePolicy(type, rule, active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["policies"] }),
  });

  if (q.isLoading) return <div className="text-sm text-muted-foreground">Loading policies...</div>;
  if (q.isError)
    return <div className="text-sm text-destructive">Error loading policies (admin only)</div>;

  return (
    <div className="space-y-6">
      <div>
        <div className="text-2xl font-semibold">Policies (Admin)</div>
        <div className="text-sm text-muted-foreground">Limits and allowed categories</div>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-2">
            <h3 className="font-medium">Limits</h3>
            <Badge variant={activeLimits ? "default" : "secondary"}>
              {activeLimits ? "Active" : "Inactive"}
            </Badge>
          </div>
          <div className="grid gap-3 max-w-xs">
            <label className="text-sm text-muted-foreground">max_per_purchase</label>
            <Input
              type="number"
              value={limits.max_per_purchase}
              onChange={(e) =>
                setLimits({
                  ...limits,
                  max_per_purchase: Number(e.target.value),
                })
              }
            />
            <label className="text-sm text-muted-foreground">daily_limit_default</label>
            <Input
              type="number"
              value={limits.daily_limit_default}
              onChange={(e) =>
                setLimits({
                  ...limits,
                  daily_limit_default: Number(e.target.value),
                })
              }
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={activeLimits}
              onChange={(e) => setActiveLimits(e.target.checked)}
              className="rounded border-input"
            />
            Active
          </label>
          <Button
            onClick={() =>
              m.mutate({
                type: "limits",
                rule: limits,
                active: activeLimits,
              })
            }
            disabled={m.isPending}
          >
            Save Limits
          </Button>
        </CardContent>
      </Card>

      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-2">
            <h3 className="font-medium">Categories</h3>
            <Badge variant={activeCategories ? "default" : "secondary"}>
              {activeCategories ? "Active" : "Inactive"}
            </Badge>
          </div>
          <div>
            <label className="text-sm text-muted-foreground block mb-2">
              allowed (comma-separated)
            </label>
            <Input
              value={categories}
              onChange={(e) => setCategories(e.target.value)}
              className="w-full"
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={activeCategories}
              onChange={(e) => setActiveCategories(e.target.checked)}
              className="rounded border-input"
            />
            Active
          </label>
          <Button
            onClick={() =>
              m.mutate({
                type: "categories",
                rule: {
                  allowed: categories
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                },
                active: activeCategories,
              })
            }
            disabled={m.isPending}
          >
            Save Categories
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
