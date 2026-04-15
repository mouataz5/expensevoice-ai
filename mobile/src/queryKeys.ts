/** Canonical React Query keys for cache sync across screens. */
export const queryKeys = {
  purchasesMe: ["purchases", "me"] as const,
  purchasesAll: ["purchases", "all"] as const,
  purchasesMeFiltered: (params: unknown) => ["purchases", "me", params] as const,
  purchasesAllFiltered: (params: unknown) => ["purchases", "all", params] as const,
  purchaseDetail: (id: string) => ["purchase", id] as const,
  purchaseAlerts: (id: string) => ["purchase", id, "alerts"] as const,
  allowedCategories: ["policies", "categories-public"] as const,
  policiesActive: ["policies", "active"] as const,
  auditList: ["audit"] as const,
  invoicesMe: ["invoices", "me"] as const,
  invoicesMeFiltered: (params: unknown) => ["invoices", "me", params] as const,
  invoicesAllFiltered: (params: unknown) => ["invoices", "all", params] as const,
  alertsMe: ["alerts", "me"] as const,
  invoiceDetail: (id: string) => ["invoice", id] as const,
  farms: ["farms"] as const,
};
