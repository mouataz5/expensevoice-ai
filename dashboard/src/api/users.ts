import { api } from "./client";

export type UserMapItem = { id: string; email: string; role: string };

export type UserOut = UserMapItem & { is_active: boolean };

export async function fetchUsersMap(): Promise<UserMapItem[]> {
  const res = await api.get("/dashboard/users-map");
  return res.data;
}

/** Admin: list all users */
export async function fetchAdminUsers(): Promise<UserOut[]> {
  const res = await api.get("/admin/users");
  return res.data;
}

/** Admin: create user */
export async function createUser(payload: { email: string; password: string; role: string }): Promise<UserOut> {
  const res = await api.post("/admin/users", payload);
  return res.data;
}

/** Admin: update role and/or is_active */
export async function updateUser(
  userId: string,
  payload: { role?: string; is_active?: boolean }
): Promise<UserOut> {
  const res = await api.patch(`/admin/users/${userId}`, payload);
  return res.data;
}

/** Admin: reset user password */
export async function resetUserPassword(userId: string, newPassword: string): Promise<void> {
  await api.post(`/admin/users/${userId}/reset-password`, { new_password: newPassword });
}
