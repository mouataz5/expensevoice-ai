import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { SectionHeader } from "@/components/marketing/SectionHeader";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Contact() {
  const { t } = useTranslation();
  const [sending, setSending] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<{ name?: string; email?: string; message?: string }>({});

  const validate = () => {
    const e: typeof errors = {};
    if (!name.trim()) e.name = "Required";
    if (!email.trim()) e.email = "Required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) e.email = "Invalid email";
    if (!message.trim()) e.message = "Required";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setSending(true);
    setTimeout(() => {
      toast.success(t("site.contact.sendSuccess"));
      setName("");
      setEmail("");
      setMessage("");
      setSending(false);
    }, 500);
  };

  return (
    <div className="py-16 md:py-20">
      <div className="container mx-auto px-4 md:px-6">
        <SectionHeader titleKey="site.contact.title" subtitleKey="site.contact.subtitle" className="mb-12" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 max-w-5xl mx-auto">
          <Card className="rounded-2xl shadow-sm border-border/80 lg:col-span-2">
            <CardContent className="p-6 md:p-8">
              <form onSubmit={onSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label>{t("site.contact.name")}</Label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={t("site.contact.placeholderName")}
                    className="rounded-xl"
                  />
                  {errors.name && <p className="text-sm text-destructive">{errors.name}</p>}
                </div>
                <div className="space-y-2">
                  <Label>{t("site.contact.email")}</Label>
                  <Input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    type="email"
                    placeholder={t("site.contact.placeholderEmail")}
                    className="rounded-xl"
                  />
                  {errors.email && <p className="text-sm text-destructive">{errors.email}</p>}
                </div>
                <div className="space-y-2">
                  <Label>{t("site.contact.message")}</Label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder={t("site.contact.placeholderMessage")}
                    className="flex min-h-[120px] w-full rounded-xl border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  />
                  {errors.message && <p className="text-sm text-destructive">{errors.message}</p>}
                </div>
                <Button type="submit" className="rounded-xl" disabled={sending}>
                  {sending ? "..." : t("site.contact.send")}
                </Button>
              </form>
            </CardContent>
          </Card>
          <Card className="rounded-2xl shadow-sm border-border/80">
            <CardContent className="p-6">
              <h3 className="font-semibold text-foreground mb-3">{t("site.footer.contact")}</h3>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <span className="font-medium text-foreground">{t("site.contact.emailLabel")}:</span> contact@abesagrotech.com
                </li>
                <li>
                  <span className="font-medium text-foreground">{t("site.contact.whatsapp")}:</span> +216 XX XXX XXX
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
