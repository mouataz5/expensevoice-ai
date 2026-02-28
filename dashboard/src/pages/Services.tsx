import { useTranslation } from "react-i18next";
import { SectionHeader } from "@/components/marketing/SectionHeader";
import { Card, CardContent } from "@/components/ui/card";

const SERVICES = [
  { title: "site.services.s1", desc: "site.services.s1d" },
  { title: "site.services.s2", desc: "site.services.s2d" },
  { title: "site.services.s3", desc: "site.services.s3d" },
  { title: "site.services.s4", desc: "site.services.s4d" },
  { title: "site.services.s5", desc: "site.services.s5d" },
  { title: "site.services.s6", desc: "site.services.s6d" },
] as const;

export default function Services() {
  const { t } = useTranslation();

  return (
    <div className="py-16 md:py-20">
      <div className="container mx-auto px-4 md:px-6">
        <SectionHeader titleKey="site.services.title" subtitleKey="site.services.subtitle" className="mb-12" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {SERVICES.map(({ title, desc }) => (
            <Card
              key={title}
              className="rounded-2xl shadow-sm border-border/80 hover:border-primary/20 transition-colors"
            >
              <CardContent className="p-6">
                <h3 className="font-semibold text-foreground mb-2">{t(title)}</h3>
                <p className="text-sm text-muted-foreground">{t(desc)}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
