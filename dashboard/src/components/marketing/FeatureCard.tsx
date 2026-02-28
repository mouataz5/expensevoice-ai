import { useTranslation } from "react-i18next";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface FeatureCardProps {
  titleKey: string;
  icon?: React.ReactNode;
  className?: string;
}

export function FeatureCard({ titleKey, icon, className }: FeatureCardProps) {
  const { t } = useTranslation();
  return (
    <Card className={cn("rounded-2xl shadow-sm border-border/80 hover:border-primary/20 transition-colors", className)}>
      <CardContent className="p-6">
        {icon && <div className="mb-3 text-primary">{icon}</div>}
        <h3 className="font-semibold text-foreground">{t(titleKey)}</h3>
      </CardContent>
    </Card>
  );
}
