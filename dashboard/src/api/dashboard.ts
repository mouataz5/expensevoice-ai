import { api } from "./client";

export type DashboardStats = {
  total_amount_today: number;
  total_amount_month: number; // used as "range total"
  purchases_today: number;
  purchases_month: number; // used as "range count"
  inflow_today?: number;
  outflow_today?: number;
  inflow_month?: number;
  outflow_month?: number;
  gross_margin_month?: number;
  net_profit_month?: number;
  fixed_expenses_month?: number;
  variable_expenses_month?: number;
  poussins_sales_month?: number;
  nourriture_sales_month?: number;
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

export async function fetchStats(
  from?: string,
  to?: string,
  farmId?: string
): Promise<DashboardStats> {
  const params: Record<string, string> = {};
  if (from) params.from = from;
  if (to) params.to = to;
  if (farmId) params.farm_id = farmId;

  const res = await api.get("/dashboard/stats", { params });
  return res.data;
}
