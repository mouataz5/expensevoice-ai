import { api } from "./client";

export type FarmOut = {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
};

export async function listFarms(): Promise<FarmOut[]> {
  const { data } = await api.get<FarmOut[]>("/farms");
  return data;
}
