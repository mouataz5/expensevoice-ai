import { api } from "./client";

export type PolicyOut = {
  id: string;
  policy_type: string;
  rule: Record<string, unknown>;
  is_active: boolean;
};

/** Active policies (director / admin read). */
export async function fetchActivePolicies(): Promise<PolicyOut[]> {
  const { data } = await api.get<PolicyOut[]>("/policies/active");
  return data;
}
