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
  const res = await api.get("/alerts");
  return res.data;
}

export async function resolveAlert(alertId: string) {
  const res = await api.post(`/alerts/${alertId}/resolve`);
  return res.data;
}

/** For notification center: count of critical unresolved + latest alerts */
export async function fetchNotifications(limit = 5): Promise<{
  count: number;
  items: AlertOut[];
}> {
  const res = await api.get("/alerts/notifications", { params: { limit } });
  return res.data;
}
