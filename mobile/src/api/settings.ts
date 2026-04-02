import { api } from "./client";

export type SettingsOut = {
  company_name: string;
  currency: string;
  logo_url: string | null;
  default_limits?: {
    max_per_purchase?: number;
    daily_limit_default?: number;
  };
  working_days: number[];
};

export async function fetchSettings(): Promise<SettingsOut> {
  const { data } = await api.get<SettingsOut>("/settings");
  return data;
}

export async function updateSettings(
  payload: Partial<SettingsOut>
): Promise<SettingsOut> {
  const { data } = await api.put<SettingsOut>("/settings", payload);
  return data;
}
