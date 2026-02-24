import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { fetchMe } from "../api/me";
import { useAuth } from "../auth/AuthContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("admin@company.com");
  const [password, setPassword] = useState("Admin12345!");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { setToken } = useAuth();
  const nav = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.post("/api/auth/login", { email, password });
      setToken(res.data.access_token);
      const me = await fetchMe();
      if (me.role === "employee") {
        nav("/employee/record");
      } else {
        nav("/stats");
      }
    } catch (err: unknown) {
      const axErr = err as { response?: { data?: { detail?: string } } };
      setError(axErr?.response?.data?.detail ?? t("login.failed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-md rounded-2xl">
        <CardContent className="p-6 space-y-5">
          <div className="space-y-1">
            <div className="text-2xl font-semibold">{t("login.title")}</div>
            <div className="text-sm text-muted-foreground">
              {t("login.subtitle")}
            </div>
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div className="space-y-2">
              <Label>{t("login.email")}</Label>
              <Input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
            </div>

            <div className="space-y-2">
              <Label>{t("login.password")}</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>

            {error && (
              <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-xl">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full rounded-xl" disabled={loading}>
              {loading ? t("login.signing_in") : t("login.sign_in")}
            </Button>
          </form>

          <div className="text-xs text-muted-foreground">
            {t("login.tip")}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
