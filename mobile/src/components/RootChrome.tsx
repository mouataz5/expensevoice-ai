import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocale } from "../context/LocaleContext";
import { useNetwork } from "../context/NetworkContext";
import { OfflineBanner } from "./ui/OfflineBanner";

export function RootChrome({ children }: { children: ReactNode }) {
  const { t } = useLocale();
  const qc = useQueryClient();
  const { refreshNetworkState } = useNetwork();

  const onRetry = () => {
    void refreshNetworkState();
    void qc.invalidateQueries();
  };

  return (
    <>
      <OfflineBanner message={t("offlineBannerMessage")} actionLabel={t("retry")} onRetry={onRetry} />
      {children}
    </>
  );
}
