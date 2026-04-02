/** Canonical React Query keys for cache sync across screens. */
export const queryKeys = {
  purchasesMe: ["purchases", "me"] as const,
  purchaseDetail: (id: string) => ["purchase", id] as const,
  purchaseAlerts: (id: string) => ["purchase", id, "alerts"] as const,
  allowedCategories: ["policies", "categories-public"] as const,
  policiesActive: ["policies", "active"] as const,
  auditList: ["audit"] as const,
  invoicesMe: ["invoices", "me"] as const,
  alertsMe: ["alerts", "me"] as const,
  invoiceDetail: (id: string) => ["invoice", id] as const,
};
