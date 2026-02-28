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
    <section className={cn("py-16 md:py-20", className)}>
      <div className="container mx-auto px-4 md:px-6 text-center">
        <h2 className="text-2xl md:text-3xl font-bold text-foreground mb-2">
          {t(titleKey)}
        </h2>
        <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
          {t(subtitleKey)}
        </p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link to={primaryHref}>
            <Button size="lg" className="rounded-xl">
              {t(primaryLabelKey)}
            </Button>
          </Link>
          {secondaryLabelKey && (
            <Link to={secondaryHref}>
              <Button size="lg" variant="outline" className="rounded-xl">
                {t(secondaryLabelKey)}
              </Button>
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}
