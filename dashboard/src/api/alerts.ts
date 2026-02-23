import { api } from "./client";

export type AlertOut = {
  id: string;
  purchase_id: string;
  alert_type: string;
  message: string;
  severity: string;
  status: string;
  created_at: string;
};

export async function fetchAlerts(): Promise<AlertOut[]> {
  const res = await api.get("/api/alerts");
  return res.data;
}

export async function resolveAlert(alertId: string) {
  const res = await api.post(`/api/alerts/${alertId}/resolve`);
  return res.data;
}
