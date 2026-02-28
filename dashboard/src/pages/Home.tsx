import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { SectionHeader } from "@/components/marketing/SectionHeader";
import { FeatureCard } from "@/components/marketing/FeatureCard";
import { CTA } from "@/components/marketing/CTA";

const FEATURE_KEYS = [
  "site.features.f1",
  "site.features.f2",
  "site.features.f3",
  "site.features.f4",
  "site.features.f5",
  "site.features.f6",
] as const;

const STEPS = ["site.how.step1", "site.how.step2", "site.how.step3"] as const;

export default function Home() {
  const { t } = useTranslation();

  return (
    <>
      <section className="relative py-16 md:py-24 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent pointer-events-none" />
        <div className="container mx-auto px-4 md:px-6 relative">
          <div className="max-w-3xl mx-auto text-center space-y-6">
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground leading-tight">
              {t("site.hero.title")}
            </h1>
            <p className="text-lg text-muted-foreground">{t("site.hero.subtitle")}</p>
            <div className="flex flex-wrap justify-center gap-3 pt-4">
              <Link to="/auth/login">
                <Button size="lg" className="rounded-xl">
                  {t("site.hero.ctaStart")}
                </Button>
              </Link>
              <Link to="/contact">
                <Button size="lg" variant="outline" className="rounded-xl">
                  {t("site.hero.ctaDemo")}
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="py-16 md:py-20 bg-card/50 border-y border-border/60">
        <div className="container mx-auto px-4 md:px-6">
          <SectionHeader titleKey="site.features.title" subtitleKey="site.features.subtitle" className="mb-12" />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURE_KEYS.map((key) => (
              <FeatureCard key={key} titleKey={key} />
            ))}
          </div>
        </div>
      </section>

      <section className="py-16 md:py-20">
        <div className="container mx-auto px-4 md:px-6">
          <SectionHeader titleKey="site.how.title" className="mb-12" />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {STEPS.map((key, i) => (
              <div key={key} className="text-center">
                <div className="w-12 h-12 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center mx-auto mb-3">
                  {i + 1}
                </div>
                <p className="font-medium text-foreground">{t(key)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="py-12 md:py-16 bg-primary/5 border-y border-border/60">
        <div className="container mx-auto px-4 md:px-6 text-center">
          <p className="text-xl font-semibold text-foreground">{t("site.trust.title")}</p>
        </div>
      </section>

      <CTA
        titleKey="site.cta.title"
        subtitleKey="site.cta.subtitle"
        primaryLabelKey="site.cta.btn"
        primaryHref="/auth/login"
        secondaryLabelKey="site.hero.ctaDemo"
        secondaryHref="/contact"
      />
    </>
  );
}
