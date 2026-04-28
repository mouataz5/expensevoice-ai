import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { downloadInvoicePdf, listMyInvoices } from "../api/invoices";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/PageHeader";
import { FilterToolbar } from "@/components/FilterToolbar";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonCard } from "@/components/SkeletonCard";
import { EmployeeHero, EmployeePage, EmployeeSectionCard } from "@/components/employee/EmployeeShell";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const READY_STATUSES = new Set(["ready", "ready_for_review", "approved"]);

export default function EmployeeInvoices() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["my-invoices"], queryFn: () => listMyInvoices({ limit: 200 }) });
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const list = q.data ?? [];
    const byStatus =
      statusFilter === "all" ? list : list.filter((inv) => (inv.status ?? "").toLowerCase() === statusFilter);
    const term = search.trim().toLowerCase();
    if (!term) return byStatus;
    return byStatus.filter(
      (inv) =>
        (inv.invoice_number ?? "").toLowerCase().includes(term) ||
        (inv.supplier_name ?? "").toLowerCase().includes(term)
    );
  }, [q.data, statusFilter, search]);

  const statusTone = (status: string) => {
    const s = (status ?? "").toLowerCase();
    if (s === "approved" || s === "ready") return "info";
    if (s.includes("processing")) return "warning";
    if (s.includes("rejected") || s.includes("failed")) return "destructive";
    return "secondary";
  };

  return (
    <EmployeePage>
      <EmployeeHero
        eyebrow="Employee Dashboard"
        title={t("employee.myInvoicesTitle")}
        subtitle={t("employee.myInvoicesSubtitle")}
        meta={[{ label: t("employee.results"), value: filtered.length }]}
      />
      <PageHeader title={t("employee.myInvoicesTitle")} subtitle={t("employee.myInvoicesSubtitle")} />

      <EmployeeSectionCard>
          {q.isLoading && <SkeletonCard lines={6} />}
          {q.isError && (
            <EmptyState
              title={t("employee.invoicesLoadError")}
              action={
                <Button variant="outline" className="rounded-xl" onClick={() => q.refetch()}>
                  {t("common.retry")}
                </Button>
              }
            />
          )}

          {q.data && q.data.length === 0 && !q.isLoading && !q.isError && (
            <EmptyState title={t("employee.noInvoices")} description={t("employee.myInvoicesSubtitle")} />
          )}

          {q.data && q.data.length > 0 && !q.isLoading && !q.isError && (
            <>
              <FilterToolbar
                className="mb-4"
                search={search}
                onSearchChange={setSearch}
                searchPlaceholder={t("employee.searchInvoices")}
                statusOptions={[
                  { value: "all", label: t("employee.filter_all") },
                  { value: "processing", label: "Processing" },
                  { value: "ready", label: "Ready" },
                  { value: "approved", label: t("employee.filter_approved") },
                  { value: "rejected", label: "Rejected" },
                ]}
                status={statusFilter}
                onStatusChange={setStatusFilter}
                statusPlaceholder={t("employee.status")}
                onClear={() => {
                  setStatusFilter("all");
                  setSearch("");
                }}
                clearLabel={t("alerts.clear_filters")}
              >
                <span className="text-sm text-muted-foreground ms-auto">
                  {filtered.length} {t("employee.results")}
                </span>
              </FilterToolbar>

              {filtered.length > 0 && (
                <div className="rounded-xl border border-border overflow-hidden bg-card">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("employee.status")}</TableHead>
                      <TableHead>{t("employee.invoiceNumber")}</TableHead>
                      <TableHead>{t("employee.supplier")}</TableHead>
                      <TableHead>{t("employee.total")}</TableHead>
                      <TableHead>{t("employee.details")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((inv) => (
                      <TableRow key={inv.id} className="hover:bg-muted/30">
                        <TableCell>
                          <Badge variant={statusTone(inv.status)}>{inv.status}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">{inv.invoice_number ?? "-"}</TableCell>
                        <TableCell>{inv.supplier_name ?? "-"}</TableCell>
                        <TableCell>{inv.total_ttc ?? 0}</TableCell>
                        <TableCell className="space-x-2">
                          <Link className="underline text-primary text-sm" to={`/employee/invoices/${inv.id}`}>
                            {t("employee.view")}
                          </Link>
                          {READY_STATUSES.has(inv.status) ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-xl"
                              onClick={() => void downloadInvoicePdf(inv.id)}
                            >
                              PDF
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                </div>
              )}
              {filtered.length === 0 && q.data && q.data.length > 0 && (
                <EmptyState title={t("employee.noInvoicesFilter")} description={t("employee.myInvoicesSubtitle")} />
              )}
            </>
          )}
      </EmployeeSectionCard>
    </EmployeePage>
  );
}
