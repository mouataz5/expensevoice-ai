import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface CTAProps {
  titleKey: string;
  subtitleKey: string;
  primaryLabelKey: string;
  primaryHref?: string;
  secondaryLabelKey?: string;
  secondaryHref?: string;
  className?: string;
}

export function CTA({
  titleKey,
  subtitleKey,
  primaryLabelKey,
  primaryHref = "/auth/login",
  secondaryLabelKey,
  secondaryHref = "/contact",
  className,
}: CTAProps) {
  const { t } = useTranslation();
  return (
    <section className={cn("py-20 md:py-28 relative overflow-hidden", className)}>
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-primary/5 to-transparent pointer-events-none" />
      <div className="container mx-auto px-4 md:px-6 text-center relative">
        <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
          {t(titleKey)}
        </h2>
        <p className="text-muted-foreground mb-10 max-w-lg mx-auto text-lg">
          {t(subtitleKey)}
        </p>
        <div className="flex flex-wrap justify-center gap-4">
          <Link to={primaryHref}>
            <Button size="lg" className="rounded-xl btn-cta px-10">
              {t(primaryLabelKey)}
            </Button>
          </Link>
          {secondaryLabelKey && (
            <Link to={secondaryHref}>
              <Button size="lg" variant="outline" className="rounded-xl border-2">
                {t(secondaryLabelKey)}
              </Button>
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
