import { api } from "./client";

export async function fetchAllowedCategories(): Promise<string[]> {
  const res = await api.get("/policies/categories-public");
  return res.data.allowed ?? [];
}
