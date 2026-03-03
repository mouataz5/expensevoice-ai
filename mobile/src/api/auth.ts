import { api } from "./client";
import { setStoredToken, clearStoredToken } from "../lib/secure-store";

export type User = { id: string; email: string; role: string };

export type LoginPayload = { email: string; password: string };

export async function login(payload: LoginPayload): Promise<{ access_token: string }> {
  const { data } = await api.post<{ access_token: string }>("/auth/login", payload);
  if (data.access_token) {
    await setStoredToken(data.access_token);
  }
  return data;
}

export async function logout(): Promise<void> {
  await clearStoredToken();
}

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>("/me");
  return data;
}
