import { api } from "./client";

export type AlertOut = {
  id: string;
  purchase_id: string;
  alert_type: string;
  severity: string;
  status: string;
  message: string;
  created_at: string;
};

export async function listMyAlerts(): Promise<AlertOut[]> {
  const { data } = await api.get<AlertOut[]>("/alerts/me");
  return data;
}

export async function getAlert(id: string): Promise<AlertOut> {
  const { data } = await api.get<AlertOut>(`/alerts/${id}`);
  return data;
}
