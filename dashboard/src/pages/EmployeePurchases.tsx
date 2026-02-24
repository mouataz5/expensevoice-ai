import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { listMyPurchases } from "../api/purchases";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

export default function EmployeePurchases() {
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ["my-purchases"], queryFn: listMyPurchases });

  return (
    <div className="space-y-6">
      <div>
        <div className="text-2xl font-semibold">
          {t("employee.myPurchasesTitle")}
        </div>
        <div className="text-sm text-muted-foreground">
          {t("employee.myPurchasesSubtitle")}
        </div>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="p-5">
          {q.isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-48 w-full rounded-xl" />
            </div>
          )}
          {q.isError && (
            <div className="text-sm text-destructive">
              {t("employee.loadError")}
            </div>
          )}

          {q.data && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("employee.status")}</TableHead>
                  <TableHead>{t("employee.product")}</TableHead>
                  <TableHead>{t("employee.category")}</TableHead>
                  <TableHead>{t("employee.quantity")}</TableHead>
                  <TableHead>{t("employee.unitPrice")}</TableHead>
                  <TableHead>{t("employee.total")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {q.data.map((p) => (
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
                  </TableRow>
                ))}
                {q.data.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="text-center text-muted-foreground"
                    >
                      {t("employee.noPurchases")}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
