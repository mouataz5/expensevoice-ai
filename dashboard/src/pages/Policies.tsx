import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchPolicies, updatePolicy } from "../api/policies";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import TagInput from "@/components/TagInput";

const DEFAULT_CATEGORIES = ["vente_poulet", "achat_aliment", "materiel", "transport", "autre"];

export default function Policies() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["policies"], queryFn: fetchPolicies });

  const [limits, setLimits] = useState({ max_per_purchase: 500, daily_limit_default: 1500 });
  const [limitsActive, setLimitsActive] = useState(true);

  const [categories, setCategories] = useState<string[]>(DEFAULT_CATEGORIES);
  const [categoriesActive, setCategoriesActive] = useState(true);

  useEffect(() => {
    if (!q.data) return;
    const limitsP = q.data.find((p) => p.policy_type === "limits");
    const catP = q.data.find((p) => p.policy_type === "categories");

    if (limitsP) {
      setLimits({
        max_per_purchase: Number(limitsP.rule?.max_per_purchase ?? 500),
        daily_limit_default: Number(limitsP.rule?.daily_limit_default ?? 1500),
      });
      setLimitsActive(!!limitsP.is_active);
    }

    if (catP) {
      const raw = catP.rule?.allowed;
      const allowed = Array.isArray(raw) ? raw.filter((x): x is string => typeof x === "string") : [];
      setCategories(allowed.length ? allowed : DEFAULT_CATEGORIES);
      setCategoriesActive(!!catP.is_active);
    }
  }, [q.data]);

  const m = useMutation({
    mutationFn: ({ type, rule, active }: { type: string; rule: Record<string, unknown>; active: boolean }) =>
      updatePolicy(type, rule, active),
    onSuccess: () => {
      toast.success(t("policies.saved"));
      qc.invalidateQueries({ queryKey: ["policies"] });
    },
    onError: () => toast.error(t("policies.saveFail")),
  });

  const saveLimits = () =>
    m.mutate({ type: "limits", rule: limits, active: limitsActive });

  const saveCategories = () =>
    m.mutate({
      type: "categories",
      rule: { allowed: categories },
      active: categoriesActive,
    });

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-2xl font-semibold">{t("policies.title")}</div>
          <div className="text-sm text-muted-foreground">
            {t("policies.subtitle")}
          </div>
        </div>
        <Badge variant="secondary">{t("policies.admin")}</Badge>
      </div>

      {q.isLoading && (
        <div className="space-y-6">
          <div className="space-y-2">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-4 w-64" />
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Skeleton className="h-72 rounded-2xl" />
            <Skeleton className="h-72 rounded-2xl" />
          </div>
        </div>
      )}
      {!q.isLoading && q.isError && (
        <div className="text-sm text-destructive">
          {t("policies.error")}
        </div>
      )}

      {!q.isLoading && (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card className="rounded-2xl">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">{t("policies.limits")}</div>
                <div className="text-sm text-muted-foreground">{t("policies.limitsDesc")}</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">{t("policies.active")}</span>
                <Switch checked={limitsActive} onCheckedChange={setLimitsActive} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>{t("policies.maxPerPurchase")}</Label>
              <Input
                type="number"
                value={limits.max_per_purchase}
                onChange={(e) => setLimits({ ...limits, max_per_purchase: Number(e.target.value) })}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("policies.dailyLimit")}</Label>
              <Input
                type="number"
                value={limits.daily_limit_default}
                onChange={(e) => setLimits({ ...limits, daily_limit_default: Number(e.target.value) })}
              />
            </div>
            <Button className="rounded-xl" onClick={saveLimits} disabled={m.isPending}>
              {m.isPending ? t("policies.saving") : t("policies.saveLimits")}
            </Button>
          </CardContent>
        </Card>

        <Card className="rounded-2xl">
          <CardContent className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">{t("policies.categories")}</div>
                <div className="text-sm text-muted-foreground">{t("policies.categoriesDesc")}</div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">{t("policies.active")}</span>
                <Switch checked={categoriesActive} onCheckedChange={setCategoriesActive} />
              </div>
            </div>
            <div className="space-y-2">
              <Label>{t("policies.categories")}</Label>
              <TagInput value={categories} onChange={setCategories} placeholder={t("policies.addCategory")} />
            </div>
            <Button className="rounded-xl" onClick={saveCategories} disabled={m.isPending}>
              {m.isPending ? t("policies.saving") : t("policies.saveCategories")}
            </Button>
          </CardContent>
        </Card>
      </div>
      )}
    </div>
  );
}
