/**
 * Settings page — company name, currency, logo URL, default limits, working days.
 * Stored in database. Director/Admin can view; only Admin can save.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchSettings, updateSettings, type SettingsOut } from "../api/settings";
import { fetchMe } from "../api/me";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonCard } from "@/components/SkeletonCard";

const WEEKDAYS = [
  { value: 0, key: "mon" },
  { value: 1, key: "tue" },
  { value: 2, key: "wed" },
  { value: 3, key: "thu" },
  { value: 4, key: "fri" },
  { value: 5, key: "sat" },
  { value: 6, key: "sun" },
];

export default function Settings() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const meQ = useQuery({ queryKey: ["me"], queryFn: fetchMe });
  const isAdmin = meQ.data?.role === "admin";

  const q = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const [companyName, setCompanyName] = useState("");
  const [currency, setCurrency] = useState("TND");
  const [logoUrl, setLogoUrl] = useState("");
  const [maxPerPurchase, setMaxPerPurchase] = useState(500);
  const [dailyLimitDefault, setDailyLimitDefault] = useState(1500);
  const [workingDays, setWorkingDays] = useState<number[]>([0, 1, 2, 3, 4]);

  useEffect(() => {
    if (!q.data) return;
    const s = q.data as SettingsOut;
    setCompanyName(s.company_name ?? "");
    setCurrency(s.currency ?? "TND");
    setLogoUrl(s.logo_url ?? "");
    setMaxPerPurchase(Number(s.default_limits?.max_per_purchase ?? 500));
    setDailyLimitDefault(Number(s.default_limits?.daily_limit_default ?? 1500));
    setWorkingDays(Array.isArray(s.working_days) ? s.working_days : [0, 1, 2, 3, 4]);
  }, [q.data]);

  const updateM = useMutation({
    mutationFn: (payload: Partial<SettingsOut>) => updateSettings(payload),
    onSuccess: () => {
      toast.success(t("settings.saved"));
      qc.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e: { response?: { status?: number } }) => {
      if (e?.response?.status === 403) {
        toast.error(t("settings.adminOnly"));
      } else {
        toast.error(t("settings.saveFail"));
      }
    },
  });

  const handleSave = () => {
    updateM.mutate({
      company_name: companyName || undefined,
      currency: currency || undefined,
      logo_url: logoUrl || null,
      default_limits: {
        max_per_purchase: maxPerPurchase,
        daily_limit_default: dailyLimitDefault,
      },
      working_days: workingDays,
    });
  };

  const toggleDay = (day: number) => {
    setWorkingDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort((a, b) => a - b)
    );
  };

  if (q.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />
        <SkeletonCard lines={6} />
      </div>
    );
  }

  if (q.isError) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("settings.title")} subtitle={t("settings.subtitle")} />
        <EmptyState
          title={t("settings.loadError")}
          action={
            <Button variant="outline" className="rounded-xl" onClick={() => q.refetch()}>
              {t("common.retry")}
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("settings.title")}
        subtitle={t("settings.subtitle")}
        actions={
          <Button
            className="rounded-xl"
            disabled={!isAdmin || updateM.isPending}
            onClick={handleSave}
          >
            {updateM.isPending ? t("settings.saving") : t("settings.save")}
          </Button>
        }
      />

      {!isAdmin && (
        <p className="text-sm text-muted-foreground">
          {t("settings.viewOnly")}
        </p>
      )}

      <Card>
        <CardContent className="p-6 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>{t("settings.companyName")}</Label>
              <Input
                className="rounded-xl"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="نظام عبّاس لإدارة الضيعة"
                disabled={!isAdmin}
              />
            </div>
            <div className="space-y-2">
              <Label>{t("settings.currency")}</Label>
              <Input
                className="rounded-xl"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                placeholder="TND"
                disabled={!isAdmin}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>{t("settings.logoUrl")}</Label>
            <Input
              className="rounded-xl"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://..."
              disabled={!isAdmin}
            />
            <p className="text-xs text-muted-foreground">
              {t("settings.logoUrlHint")}
            </p>
          </div>

          <div>
            <h3 className="font-medium mb-3">{t("settings.defaultLimits")}</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>{t("settings.maxPerPurchase")}</Label>
                <Input
                  type="number"
                  className="rounded-xl"
                  value={maxPerPurchase}
                  onChange={(e) => setMaxPerPurchase(Number(e.target.value))}
                  min={0}
                  disabled={!isAdmin}
                />
              </div>
              <div className="space-y-2">
                <Label>{t("settings.dailyLimitDefault")}</Label>
                <Input
                  type="number"
                  className="rounded-xl"
                  value={dailyLimitDefault}
                  onChange={(e) => setDailyLimitDefault(Number(e.target.value))}
                  min={0}
                  disabled={!isAdmin}
                />
              </div>
            </div>
          </div>

          <div>
            <h3 className="font-medium mb-3">{t("settings.workingDays")}</h3>
            <div className="flex flex-wrap gap-3">
              {WEEKDAYS.map(({ value, key }) => (
                <label
                  key={value}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={workingDays.includes(value)}
                    onChange={() => toggleDay(value)}
                    disabled={!isAdmin}
                    className="rounded border-border"
                  />
                  <span className="text-sm">{t(`settings.days.${key}`)}</span>
                </label>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
