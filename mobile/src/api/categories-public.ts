import { api } from "./client";

export async function fetchAllowedCategories(): Promise<string[]> {
  const { data } = await api.get<{ allowed?: string[] }>("/policies/categories-public");
  return data.allowed ?? [];
}
