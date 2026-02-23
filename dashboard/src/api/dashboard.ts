import { api } from "./client";

export type DashboardStats = {
  total_amount_today: number;
  total_amount_month: number;
  purchases_today: number;
  purchases_month: number;
  by_category: {
    category: string | null;
    total_amount: number;
    count: number;
  }[];
  top_users: {
    user_id: string;
    email?: string;
    total_amount: number;
    count: number;
  }[];
  daily_trend_last_14_days: {
    date: string;
    total_amount: number;
    count: number;
  }[];
};

export async function fetchStats(): Promise<DashboardStats> {
  const res = await api.get("/api/dashboard/stats");
  return res.data;
}
