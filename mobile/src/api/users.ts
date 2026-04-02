import { api } from "./client";

export type UserMapItem = { id: string; email: string; role: string };

export type UserOut = UserMapItem & { is_active: boolean };

/** Director: read-only list (dashboard users-map). */
export async function fetchUsersMap(): Promise<UserMapItem[]> {
  const { data } = await api.get<UserMapItem[]>("/dashboard/users-map");
  return data;
}

/** Admin: list all users. */
export async function fetchAdminUsers(): Promise<UserOut[]> {
  const { data } = await api.get<UserOut[]>("/admin/users");
  return data;
}

/** Admin: create user. */
export async function createUser(payload: {
  email: string;
  password: string;
  role: string;
}): Promise<UserOut> {
  const { data } = await api.post<UserOut>("/admin/users", payload);
  return data;
}

/** Admin: update user role and/or is_active. */
export async function updateUser(
  userId: string,
  payload: { role?: string; is_active?: boolean }
): Promise<UserOut> {
  const { data } = await api.patch<UserOut>(`/admin/users/${userId}`, payload);
  return data;
}

/** Admin: reset user password. */
export async function resetUserPassword(
  userId: string,
  newPassword: string
): Promise<void> {
  await api.post(`/admin/users/${userId}/reset-password`, {
    new_password: newPassword,
  });
}
