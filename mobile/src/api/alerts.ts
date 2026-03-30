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

/** Admin/Director: list all alerts. */
export async function listAllAlerts(): Promise<AlertOut[]> {
  const { data } = await api.get<AlertOut[]>("/alerts");
  return data;
}

export async function resolveAlert(alertId: string): Promise<void> {
  await api.post(`/alerts/${alertId}/resolve`);
}

export async function getAlert(id: string): Promise<AlertOut> {
  const { data } = await api.get<AlertOut>(`/alerts/${id}`);
  return data;
}
