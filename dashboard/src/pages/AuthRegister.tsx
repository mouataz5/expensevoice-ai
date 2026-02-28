import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { AuthLayout } from "@/components/marketing/AuthLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function AuthRegister() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      await new Promise((r) => setTimeout(r, 800));
      toast.info("Registration is not yet available. Please contact your administrator.");
    } catch {
      setError("An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout title={t("site.auth.register")} subtitle="">
      <form onSubmit={submit} className="space-y-4">
        <div className="space-y-2">
          <Label>{t("site.auth.email")}</Label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
            className="rounded-xl"
            required
          />
        </div>
        <div className="space-y-2">
          <Label>{t("site.auth.password")}</Label>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-xl"
            required
          />
        </div>
        <div className="space-y-2">
          <Label>{t("site.auth.confirmPassword")}</Label>
          <Input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="rounded-xl"
            required
          />
        </div>
        {error && (
          <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-xl">{error}</div>
        )}
        <Button type="submit" className="w-full rounded-xl" disabled={loading}>
          {loading ? "..." : t("site.auth.signUp")}
        </Button>
      </form>
      <p className="mt-6 text-sm text-muted-foreground text-center">
        {t("site.auth.hasAccount")}{" "}
        <Link to="/auth/login" className="text-primary font-medium hover:underline">
          {t("site.auth.signIn")}
        </Link>
      </p>
    </AuthLayout>
  );
}
