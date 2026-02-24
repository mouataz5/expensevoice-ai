import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAudit } from "../api/audit";
import { fetchUsersMap } from "../api/users";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function sevBadgeForAction(action: string): "destructive" | "secondary" | "outline" {
  if (action.includes("policy")) return "destructive";
  if (action.includes("confirm")) return "secondary";
  return "outline";
}

export default function Audit() {
  const [qText, setQText] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 12;

  const auditQ = useQuery({
    queryKey: ["audit", from, to],
    queryFn: () =>
      fetchAudit({
        from: from || undefined,
        to: to || undefined,
        limit: 200,
      }),
  });

  const mapQ = useQuery({ queryKey: ["users-map"], queryFn: fetchUsersMap });

  const userMap = useMemo(
    () => new Map((mapQ.data ?? []).map((u) => [u.id, u])),
    [mapQ.data]
  );

  const filtered = useMemo(() => {
    const rows = auditQ.data ?? [];
    const s = qText.trim().toLowerCase();
    if (!s) return rows;
    return rows.filter((r) => {
      const text = `${r.action} ${r.entity_type} ${r.entity_id} ${r.message} ${r.actor_role}`.toLowerCase();
      return text.includes(s);
    });
  }, [auditQ.data, qText]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const pageRows = filtered.slice((page - 1) * pageSize, page * pageSize);

  return (
    <div className="space-y-6">
      <div>
        <div className="text-2xl font-semibold">سجل النشاط</div>
        <div className="text-sm text-muted-foreground">
          كل التغييرات المهمّة داخل النظام
        </div>
      </div>

      <Card className="rounded-2xl">
        <CardContent className="p-5 space-y-4">
          <div className="flex flex-wrap gap-2 items-end">
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">بحث</div>
              <Input
                className="rounded-xl w-72"
                placeholder="ابحث: confirm / policy / alert ..."
                value={qText}
                onChange={(e) => {
                  setQText(e.target.value);
                  setPage(1);
                }}
              />
            </div>

            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">من</div>
              <Input
                type="date"
                className="rounded-xl"
                value={from}
                onChange={(e) => {
                  setFrom(e.target.value);
                  setPage(1);
                }}
              />
            </div>

            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">إلى</div>
              <Input
                type="date"
                className="rounded-xl"
                value={to}
                onChange={(e) => {
                  setTo(e.target.value);
                  setPage(1);
                }}
              />
            </div>

            <Button
              variant="outline"
              className="rounded-xl"
              onClick={() => {
                setQText("");
                setFrom("");
                setTo("");
                setPage(1);
              }}
            >
              مسح الفلاتر
            </Button>

            <div className="text-sm text-muted-foreground ms-auto">
              {filtered.length} حدث
            </div>
          </div>

          {auditQ.isLoading && (
            <div className="text-sm text-muted-foreground">جاري التحميل...</div>
          )}
          {auditQ.isError && (
            <div className="text-sm text-destructive">
              تعذّر تحميل سجل النشاط
            </div>
          )}

          {auditQ.data && (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>الوقت</TableHead>
                    <TableHead>المستخدم</TableHead>
                    <TableHead>الدور</TableHead>
                    <TableHead>العملية</TableHead>
                    <TableHead>الكيان</TableHead>
                    <TableHead>رسالة</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pageRows.map((r) => {
                    const u = userMap.get(r.actor_user_id);
                    return (
                      <TableRow key={r.id}>
                        <TableCell className="text-xs text-muted-foreground">
                          {new Date(r.created_at).toLocaleString()}
                        </TableCell>
                        <TableCell className="text-sm">
                          {u?.email ?? r.actor_user_id}
                        </TableCell>
                        <TableCell>
                          <Badge variant="secondary">{r.actor_role}</Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={sevBadgeForAction(r.action)}>
                            {r.action}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm">
                          {r.entity_type}:{r.entity_id.slice(0, 8)}…
                        </TableCell>
                        <TableCell className="max-w-[420px] truncate text-sm">
                          {r.message}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                  {pageRows.length === 0 && (
                    <TableRow>
                      <TableCell
                        colSpan={6}
                        className="text-center text-muted-foreground"
                      >
                        لا توجد أحداث
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between pt-4">
                <div className="text-sm text-muted-foreground">
                  الصفحة {page} من {totalPages}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    className="rounded-xl"
                    disabled={page === 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    السابق
                  </Button>
                  <Button
                    variant="outline"
                    className="rounded-xl"
                    disabled={page === totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    التالي
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
