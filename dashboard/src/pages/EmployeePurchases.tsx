import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { listMyPurchases } from "../api/purchases";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/PageHeader";
import { FilterToolbar } from "@/components/FilterToolbar";
import { EmptyState } from "@/components/EmptyState";
import { SkeletonCard } from "@/components/SkeletonCard";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function EmployeePurchases() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["my-purchases"], queryFn: listMyPurchases });
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const list = q.data ?? [];
    const byStatus =
      statusFilter === "all" ? list : list.filter((p) => (p.status ?? "").toLowerCase() === statusFilter);
    const term = search.trim().toLowerCase();
    if (!term) return byStatus;
    return byStatus.filter(
      (p) =>
        (p.product_name ?? "").toLowerCase().includes(term) ||
        (p.category ?? "").toLowerCase().includes(term)
    );
  }, [q.data, statusFilter, search]);

  return (
    <div className="space-y-6">
      <PageHeader title={t("employee.myPurchasesTitle")} subtitle={t("employee.myPurchasesSubtitle")} />

      <Card>
        <CardContent className="p-5">
          {q.isLoading && <SkeletonCard lines={6} />}
          {q.isError && (
            <EmptyState
              title={t("employee.loadError")}
              action={<Button variant="outline" className="rounded-xl" onClick={() => q.refetch()}>{t("common.retry")}</Button>}
            />
          )}

          {q.data && q.data.length === 0 && !q.isLoading && !q.isError && (
            <EmptyState title={t("employee.noPurchases")} description={t("employee.myPurchasesSubtitle")} />
          )}

          {q.data && q.data.length > 0 && !q.isLoading && !q.isError && (
            <>
              <FilterToolbar
                className="mb-4"
                search={search}
                onSearchChange={setSearch}
                searchPlaceholder={t("employee.searchPurchases")}
                statusOptions={[
                  { value: "all", label: t("employee.filter_all") },
                  { value: "pending", label: t("employee.filter_pending") },
                  { value: "approved", label: t("employee.filter_approved") },
                ]}
                status={statusFilter}
                onStatusChange={setStatusFilter}
                statusPlaceholder={t("employee.status")}
                onClear={() => { setStatusFilter("all"); setSearch(""); }}
                clearLabel={t("alerts.clear_filters")}
              >
                <span className="text-sm text-muted-foreground ms-auto">{filtered.length} {t("employee.results")}</span>
              </FilterToolbar>
          {filtered.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("employee.status")}</TableHead>
                  <TableHead>{t("employee.product")}</TableHead>
                  <TableHead>{t("employee.category")}</TableHead>
                  <TableHead>{t("employee.quantity")}</TableHead>
                  <TableHead>{t("employee.unitPrice")}</TableHead>
                  <TableHead>{t("employee.total")}</TableHead>
                  <TableHead>{t("employee.details")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell>
                      <Badge variant="secondary">{p.status}</Badge>
                    </TableCell>
                    <TableCell className="font-medium">
                      {p.product_name}
                    </TableCell>
                    <TableCell>{p.category ?? "-"}</TableCell>
                    <TableCell>{p.quantity}</TableCell>
                    <TableCell>{p.unit_price}</TableCell>
                    <TableCell>{p.total_amount}</TableCell>
                    <TableCell>
                      <Link className="underline text-sm text-primary hover:underline" to={`/purchases/${p.id}`}>
                        {t("employee.view")}
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {filtered.length === 0 && q.data && q.data.length > 0 && (
            <EmptyState title={t("employee.noPurchasesFilter")} description={t("employee.myPurchasesSubtitle")} />
          )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
