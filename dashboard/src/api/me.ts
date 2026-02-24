import { api } from "./client";

export type Me = { id: string; email: string; role: "admin" | "director" | "employee" };

export async function fetchMe(): Promise<Me> {
  const res = await api.get("/api/me");
  return res.data;
}
