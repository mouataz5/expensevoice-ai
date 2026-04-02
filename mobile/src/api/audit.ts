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
  from?: string;
  to?: string;
  limit?: number;
}): Promise<AuditRow[]> {
  const { data } = await api.get<AuditRow[]>("/audit", { params });
  return data;
}
