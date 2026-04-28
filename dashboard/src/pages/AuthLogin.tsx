import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { fetchMe } from "../api/me";
import { useAuth } from "../auth/AuthContext";
import { AuthLayout } from "@/components/marketing/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function AuthLogin() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("admin@company.com");
  const [password, setPassword] = useState("Admin12345!");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { setToken } = useAuth();
  const nav = useNavigate();
  const queryClient = useQueryClient();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.post("/auth/login", { email, password });
      setToken(res.data.access_token);
      await queryClient.invalidateQueries({ queryKey: ["me"] });
      const me = await fetchMe();
      if (me.role === "employee") nav("/employee/home");
      else nav("/stats");
    } catch (err: unknown) {
      const axErr = err as { response?: { data?: { detail?: string } } };
      setError(axErr?.response?.data?.detail ?? t("login.failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title={t("site.auth.login")} subtitle={t("login.subtitle")}>
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label>{t("site.auth.email")}</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="rounded-xl"
          />
        </div>
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <Label>{t("site.auth.password")}</Label>
            <Link
              to="#"
              className="text-xs text-muted-foreground hover:text-primary"
              onClick={(e) => e.preventDefault()}
            >
              {t("site.auth.forgotPassword")}
            </Link>
          </div>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-xl"
          />
        </div>
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-xl">{error}</div>
        )}
        <Button type="submit" className="w-full rounded-xl" disabled={loading}>
          {loading ? t("login.signing_in") : t("site.auth.signIn")}
        </Button>
      </form>
      <p className="mt-6 text-sm text-muted-foreground text-center">
        {t("site.auth.noAccount")}{" "}
        <Link to="/auth/register" className="text-primary font-medium hover:underline">
          {t("site.auth.signUp")}
        </Link>
      </p>
      <p className="mt-2 text-xs text-muted-foreground">{t("login.tip")}</p>
    </AuthLayout>
  );
}
