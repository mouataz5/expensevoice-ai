import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchPolicies, updatePolicy } from "../api/policies";

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

  if (q.isLoading) return <div>Loading policies...</div>;
  if (q.isError)
    return <div>Error loading policies (admin only)</div>;

  return (
    <div style={{ padding: 16, fontFamily: "system-ui" }}>
      <h2>Policies (Admin)</h2>

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 12,
          marginBottom: 16,
        }}
      >
        <h3>Limits</h3>
        <label>max_per_purchase</label>
        <input
          type="number"
          value={limits.max_per_purchase}
          onChange={(e) =>
            setLimits({
              ...limits,
              max_per_purchase: Number(e.target.value),
            })
          }
        />
        <br />
        <label>daily_limit_default</label>
        <input
          type="number"
          value={limits.daily_limit_default}
          onChange={(e) =>
            setLimits({
              ...limits,
              daily_limit_default: Number(e.target.value),
            })
          }
        />
        <br />
        <label>
          <input
            type="checkbox"
            checked={activeLimits}
            onChange={(e) => setActiveLimits(e.target.checked)}
          />
          Active
        </label>
        <br />
        <button
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
        </button>
      </section>

      <section
        style={{
          border: "1px solid #ddd",
          borderRadius: 10,
          padding: 12,
        }}
      >
        <h3>Categories</h3>
        <label>allowed (comma-separated)</label>
        <input
          value={categories}
          onChange={(e) => setCategories(e.target.value)}
          style={{ width: "100%" }}
        />
        <br />
        <label>
          <input
            type="checkbox"
            checked={activeCategories}
            onChange={(e) => setActiveCategories(e.target.checked)}
          />
          Active
        </label>
        <br />
        <button
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
        </button>
      </section>
    </div>
  );
}
