/**
 * User Management — Admin only.
 * List users, add user, change role, enable/disable, reset password.
 */
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { fetchMe } from "../api/me";
import {
  fetchAdminUsers,
  createUser,
  updateUser,
  resetUserPassword,
  type UserOut,
} from "../api/users";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/PageHeader";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

const ROLES = ["employee", "director", "admin"] as const;

export default function Users() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const meQ = useQuery({ queryKey: ["me"], queryFn: fetchMe });
  const [addOpen, setAddOpen] = useState(false);
  const [addEmail, setAddEmail] = useState("");
  const [addPassword, setAddPassword] = useState("");
  const [addRole, setAddRole] = useState<string>("employee");
  const [resettingId, setResettingId] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const q = useQuery({
    queryKey: ["admin-users"],
    queryFn: fetchAdminUsers,
    enabled: meQ.data?.role === "admin",
  });

  useEffect(() => {
    if (meQ.isSuccess && meQ.data?.role !== "admin") {
      navigate("/stats", { replace: true });
    }
  }, [meQ.isSuccess, meQ.data?.role, navigate]);

  const createM = useMutation({
    mutationFn: (payload: { email: string; password: string; role: string }) =>
      createUser(payload),
    onSuccess: () => {
      toast.success(t("users.created"));
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      setAddOpen(false);
      setAddEmail("");
      setAddPassword("");
      setAddRole("employee");
    },
    onError: (e: { response?: { data?: { detail?: string } } }) => {
      toast.error(e?.response?.data?.detail ?? t("users.createFail"));
    },
  });

  const updateM = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { role?: string; is_active?: boolean } }) =>
      updateUser(id, payload),
    onSuccess: () => {
      toast.success(t("users.updated"));
      qc.invalidateQueries({ queryKey: ["admin-users"] });
    },
    onError: () => toast.error(t("users.updateFail")),
  });

  const resetM = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      resetUserPassword(id, password),
    onSuccess: () => {
      toast.success(t("users.passwordReset"));
      setResettingId(null);
      setNewPassword("");
    },
    onError: () => toast.error(t("users.resetFail")),
  });

  const handleRoleChange = (user: UserOut, role: string) => {
    if (!ROLES.includes(role as (typeof ROLES)[number])) return;
    updateM.mutate({ id: user.id, payload: { role } });
  };

  const handleActiveChange = (user: UserOut, isActive: boolean) => {
    updateM.mutate({ id: user.id, payload: { is_active: isActive } });
  };

  if (q.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("users.title")} subtitle={t("users.subtitle")} />
        <SkeletonCard lines={8} />
      </div>
    );
  }

  if (q.isError) {
    return (
      <div className="space-y-6">
        <PageHeader title={t("users.title")} subtitle={t("users.subtitle")} />
        <EmptyState
          title={t("users.loadError")}
          action={<Button variant="outline" className="rounded-xl" onClick={() => q.refetch()}>{t("common.retry")}</Button>}
        />
      </div>
    );
  }

  const users = q.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("users.title")}
        subtitle={t("users.subtitle")}
        actions={
          <Button
            className="rounded-xl"
            onClick={() => setAddOpen(true)}
          >
            {t("users.addUser")}
          </Button>
        }
      />

      {addOpen && (
        <Card>
          <CardContent className="p-5 space-y-4">
            <h3 className="font-medium">{t("users.addUser")}</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>{t("users.email")}</Label>
                <Input
                  type="email"
                  className="rounded-xl"
                  value={addEmail}
                  onChange={(e) => setAddEmail(e.target.value)}
                  placeholder="user@example.com"
                />
              </div>
              <div className="space-y-2">
                <Label>{t("users.password")}</Label>
                <Input
                  type="password"
                  className="rounded-xl"
                  value={addPassword}
                  onChange={(e) => setAddPassword(e.target.value)}
                  placeholder="••••••••"
                />
              </div>
              <div className="space-y-2">
                <Label>{t("users.role")}</Label>
                <Select value={addRole} onValueChange={setAddRole}>
                  <SelectTrigger className="rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLES.map((r) => (
                      <SelectItem key={r} value={r}>{r}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                className="rounded-xl"
                disabled={!addEmail.trim() || !addPassword || createM.isPending}
                onClick={() =>
                  createM.mutate({
                    email: addEmail.trim(),
                    password: addPassword,
                    role: addRole,
                  })
                }
              >
                {createM.isPending ? t("users.creating") : t("users.create")}
              </Button>
              <Button variant="outline" className="rounded-xl" onClick={() => setAddOpen(false)}>
                {t("common.cancel")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-5">
          {users.length === 0 ? (
            <EmptyState title={t("users.noUsers")} description={t("users.subtitle")} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("users.email")}</TableHead>
                  <TableHead>{t("users.role")}</TableHead>
                  <TableHead>{t("users.status")}</TableHead>
                  <TableHead>{t("users.actions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell className="font-medium">{u.email}</TableCell>
                    <TableCell>
                      <Select
                        value={u.role}
                        onValueChange={(v) => handleRoleChange(u, v)}
                        disabled={updateM.isPending}
                      >
                        <SelectTrigger className="rounded-xl w-32">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((r) => (
                            <SelectItem key={r} value={r}>{r}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Switch
                          checked={u.is_active ?? true}
                          onCheckedChange={(v) => handleActiveChange(u, v)}
                          disabled={updateM.isPending}
                        />
                        <Badge variant={u.is_active ?? true ? "info" : "secondary"}>
                          {u.is_active ?? true ? t("users.active") : t("users.disabled")}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>
                      {resettingId === u.id ? (
                        <div className="flex items-center gap-2">
                          <Input
                            type="password"
                            className="rounded-xl w-36"
                            placeholder={t("users.newPassword")}
                            value={newPassword}
                            onChange={(e) => setNewPassword(e.target.value)}
                          />
                          <Button
                            size="sm"
                            className="rounded-xl"
                            disabled={!newPassword || resetM.isPending}
                            onClick={() =>
                              resetM.mutate({ id: u.id, password: newPassword })
                            }
                          >
                            {t("users.reset")}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="rounded-xl"
                            onClick={() => { setResettingId(null); setNewPassword(""); }}
                          >
                            {t("common.cancel")}
                          </Button>
                        </div>
                      ) : (
                        <Button
                          size="sm"
                          variant="outline"
                          className="rounded-xl"
                          onClick={() => setResettingId(u.id)}
                        >
                          {t("users.resetPassword")}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
