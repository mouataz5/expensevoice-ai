import { api } from "./client";

export async function fetchAllowedCategories(): Promise<string[]> {
  const res = await api.get("/api/policies/categories-public");
  return res.data.allowed ?? [];
}
