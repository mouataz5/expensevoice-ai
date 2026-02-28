import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

interface SectionHeaderProps {
  titleKey: string;
  subtitleKey?: string;
  className?: string;
}

export function SectionHeader({ titleKey, subtitleKey, className }: SectionHeaderProps) {
  const { t } = useTranslation();
  return (
    <div className={cn("text-center space-y-2", className)}>
      <h2 className="text-2xl md:text-3xl font-bold text-foreground">
        {t(titleKey)}
      </h2>
      {subtitleKey && (
        <p className="text-muted-foreground max-w-2xl mx-auto">
          {t(subtitleKey)}
        </p>
      )}
    </div>
  );
}
