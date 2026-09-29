import { MapPin, Heart, Moon, Sun, Compass, Languages } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n, LANGS } from "@/lib/i18n";

export function Header({ locationLabel, favCount, dark, onToggleDark, onSavedClick }) {
  const { t, lang, setLang } = useI18n();
  return (
    <header className="sticky top-0 z-40 backdrop-blur-md bg-background/80 border-b border-border/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shrink-0 shadow-sm">
            <Compass className="w-5 h-5 text-primary-foreground" strokeWidth={2.4} />
          </div>
          <div className="min-w-0">
            <h1 className="font-heading font-extrabold text-lg leading-none tracking-tight" dir="ltr">
              Sababa<span className="text-primary">Kids</span>
            </h1>
            <div
              className="flex items-center gap-1 text-xs text-muted-foreground mt-0.5 truncate"
              data-testid="header-location-label"
            >
              <MapPin className="w-3 h-3 text-primary shrink-0" />
              <span className="truncate" dir="auto">{locationLabel || "Israel"}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <label className="relative flex items-center" title={t("language")}>
            <Languages className="w-4 h-4 absolute start-2 pointer-events-none text-muted-foreground" />
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              aria-label={t("language")}
              data-testid="lang-select"
              className="h-9 ps-7 pe-2 rounded-full bg-transparent text-sm font-semibold border border-border/60 hover:bg-muted cursor-pointer appearance-none"
            >
              {LANGS.map((l) => (
                <option key={l.id} value={l.id}>{l.short}</option>
              ))}
            </select>
          </label>
          <Button
            variant="ghost"
            size="sm"
            onClick={onSavedClick}
            aria-label={t("savedList")}
            className="relative rounded-full h-9 px-3"
            data-testid="header-saved-btn"
          >
            <Heart className="w-4 h-4" />
            {favCount > 0 && (
              <span
                className="absolute -top-0.5 -end-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-primary text-primary-foreground text-[10px] font-bold flex items-center justify-center"
                data-testid="header-fav-count"
              >
                {favCount}
              </span>
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleDark}
            aria-label={t("darkMode")}
            className="rounded-full h-9 w-9"
            data-testid="header-theme-toggle"
          >
            {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </Button>
        </div>
      </div>
    </header>
  );
}
