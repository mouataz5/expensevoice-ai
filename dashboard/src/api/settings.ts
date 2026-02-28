import { api } from "./client";

export type SettingsOut = {
  company_name: string;
  currency: string;
  logo_url: string | null;
  default_limits: { max_per_purchase?: number; daily_limit_default?: number };
  working_days: number[]; // 0=Mon .. 6=Sun (ISO)
};

export async function fetchSettings(): Promise<SettingsOut> {
  const res = await api.get<SettingsOut>("/settings");
  return res.data;
}

export async function updateSettings(
  payload: Partial<SettingsOut>
): Promise<SettingsOut> {
  const res = await api.put<SettingsOut>("/settings", payload);
  return res.data;
}
