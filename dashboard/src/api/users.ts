import { api } from "./client";

export type UserMapItem = { id: string; email: string; role: string };

export async function fetchUsersMap(): Promise<UserMapItem[]> {
  const res = await api.get("/api/dashboard/users-map");
  return res.data;
}
