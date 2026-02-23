import { api } from "./client";

export type Policy = {
  id: string;
  policy_type: string;
  rule: Record<string, unknown>;
  is_active: boolean;
};

export async function fetchPolicies(): Promise<Policy[]> {
  const res = await api.get("/api/admin/policies");
  return res.data;
}

export async function updatePolicy(
  policyType: string,
  rule: Record<string, unknown>,
  is_active?: boolean
) {
  const res = await api.put(`/api/admin/policies/${policyType}`, {
    rule,
    is_active,
  });
  return res.data;
}
