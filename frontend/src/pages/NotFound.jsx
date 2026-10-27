import { useEffect } from "react";
import { SearchX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

// Shown for unknown URLs (the host rewrites every path to index.html, so they'd
// otherwise answer with the home page). noindex keeps them out of Google.
export default function NotFound() {
  const { t } = useI18n();

  useEffect(() => {
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex";
    document.head.appendChild(meta);
    document.title = `${t("notFoundTitle")} | SababaKids`;
    return () => meta.remove();
  }, [t]);

  return (
    <main className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="text-center max-w-sm" data-testid="not-found">
        <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
          <SearchX className="w-7 h-7 text-muted-foreground" />
        </div>
        <h1 className="font-heading font-bold text-xl">{t("notFoundTitle")}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t("notFoundText")}</p>
        <Button asChild className="mt-5 rounded-xl">
          <a href="/">{t("backHome")}</a>
        </Button>
      </div>
    </main>
  );
}
