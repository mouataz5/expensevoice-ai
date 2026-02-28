import { useTranslation } from "react-i18next";
import { SectionHeader } from "@/components/marketing/SectionHeader";
import { Card, CardContent } from "@/components/ui/card";

export default function About() {
  const { t } = useTranslation();

  return (
    <div className="py-16 md:py-20">
      <div className="container mx-auto px-4 md:px-6">
        <SectionHeader titleKey="site.about.title" className="mb-14" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          <Card className="rounded-2xl shadow-sm border-border/80">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold text-primary mb-2">{t("site.about.mission")}</h3>
              <p className="text-muted-foreground">{t("site.about.missionText")}</p>
            </CardContent>
          </Card>
          <Card className="rounded-2xl shadow-sm border-border/80">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold text-primary mb-2">{t("site.about.vision")}</h3>
              <p className="text-muted-foreground">{t("site.about.visionText")}</p>
            </CardContent>
          </Card>
        </div>
        <div className="mt-12 max-w-2xl mx-auto">
          <Card className="rounded-2xl shadow-sm border-border/80">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold text-primary mb-2">{t("site.about.valuesTitle")}</h3>
              <p className="text-muted-foreground">{t("site.about.valuesText")}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
