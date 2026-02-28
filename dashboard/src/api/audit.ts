import { api } from "./client";

export type AuditRow = {
  id: string;
  actor_user_id: string;
  actor_role: string;
  action: string;
  entity_type: string;
  entity_id: string;
  message: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export async function fetchAudit(params?: {
  actor_user_id?: string;
  action?: string;
  entity_type?: string;
  from?: string;
  to?: string;
  limit?: number;
}): Promise<AuditRow[]> {
  const res = await api.get("/audit", { params });
  return res.data;
}
