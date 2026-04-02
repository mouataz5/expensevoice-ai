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

const FEATURE_ICONS: Record<string, string> = {
  "site.features.f1": "mic",
  "site.features.f2": "scan",
  "site.features.f3": "bell",
  "site.features.f4": "audit",
  "site.features.f5": "file",
  "site.features.f6": "chart",
};

const STEPS = ["site.how.step1", "site.how.step2", "site.how.step3"] as const;

export default function Home() {
  const { t } = useTranslation();

  return (
    <>
      <section className="relative py-20 md:py-28 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/8 via-primary/3 to-transparent pointer-events-none" />
        <div className="absolute top-20 left-1/4 w-72 h-72 bg-primary/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-20 right-1/4 w-96 h-96 bg-accent/5 rounded-full blur-3xl pointer-events-none" />
        <div className="container mx-auto px-4 md:px-6 relative">
          <div className="max-w-4xl mx-auto text-center space-y-8">
            <div className="hero-badge">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              {t("site.trust.title")}
            </div>
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold text-foreground leading-[1.15] tracking-tight">
              {t("site.hero.title")}
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
              {t("site.hero.subtitle")}
            </p>
            <div className="flex flex-wrap justify-center gap-4 pt-6">
              <Link to="/auth/login">
                <Button size="lg" className="rounded-xl btn-cta px-8">
                  {t("site.hero.ctaStart")}
                </Button>
              </Link>
              <Link to="/contact">
                <Button size="lg" variant="outline" className="rounded-xl border-2">
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
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 md:gap-8">
            {FEATURE_KEYS.map((key) => (
              <FeatureCard key={key} titleKey={key} iconKey={FEATURE_ICONS[key]} />
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

      <section className="py-16 md:py-20 bg-gradient-to-r from-primary/10 via-primary/5 to-primary/10 border-y border-border/60">
        <div className="container mx-auto px-4 md:px-6">
          <div className="flex flex-wrap justify-center gap-8 md:gap-12 text-center">
            <div>
              <p className="text-3xl md:text-4xl font-bold text-primary">100%</p>
              <p className="text-sm text-muted-foreground mt-1">{t("site.trust.title")}</p>
            </div>
            <div className="w-px bg-border hidden md:block" />
            <div>
              <p className="text-3xl md:text-4xl font-bold text-primary">PDF/CSV</p>
              <p className="text-sm text-muted-foreground mt-1">{t("site.features.f5")}</p>
            </div>
            <div className="w-px bg-border hidden md:block" />
            <div>
              <p className="text-3xl md:text-4xl font-bold text-primary">RTL</p>
              <p className="text-sm text-muted-foreground mt-1">{t("site.services.s6")}</p>
            </div>
          </div>
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
