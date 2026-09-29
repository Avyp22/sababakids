import { useState } from "react";
import { Search, LocateFixed, SlidersHorizontal, ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { CATEGORIES, AGE_GROUPS, catLabel } from "@/lib/categories";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function FiltersBar({
  locationInput, setLocationInput, onSearch, onUseGps, gpsLoading,
  radius, setRadius, category, setCategory, ages, toggleAge,
  setting, setSetting, price, setPrice,
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const activeCount = ages.length + (setting !== "all") + (price !== "all");

  return (
    <div className="bg-card/60 border-b border-border/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 md:py-4 space-y-3 md:space-y-4">
        {/* Search row */}
        <form
          onSubmit={(e) => { e.preventDefault(); onSearch(); }}
          className="flex gap-2"
        >
          <div className="relative flex-1 min-w-0">
            <Search className="absolute start-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              value={locationInput}
              onChange={(e) => setLocationInput(e.target.value)}
              placeholder={t("searchPlaceholder")}
              aria-label={t("searchPlaceholder")}
              dir="auto"
              className="ps-10 h-11 md:h-12 rounded-2xl bg-background text-base"
              data-testid="search-location-input"
            />
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={onUseGps}
            disabled={gpsLoading}
            aria-label={t("myLocation")}
            className="h-11 md:h-12 rounded-2xl gap-2 shrink-0 px-3 md:px-4"
            data-testid="btn-use-gps"
          >
            <LocateFixed className={cn("w-4 h-4", gpsLoading && "animate-spin")} />
            <span className="hidden sm:inline">{t("myLocation")}</span>
          </Button>
          <Button
            type="submit"
            aria-label={t("search")}
            className="h-11 md:h-12 rounded-2xl px-3 md:px-6 gap-2 shrink-0"
            data-testid="btn-search"
          >
            <Search className="w-4 h-4" />
            <span className="hidden sm:inline">{t("search")}</span>
          </Button>
        </form>

        {/* Category pills + mobile filters toggle */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            data-testid="btn-toggle-filters"
            className={cn(
              "md:hidden flex items-center gap-1.5 px-3 h-9 rounded-full text-sm font-semibold border shrink-0 transition-colors",
              open || activeCount ? "bg-secondary text-secondary-foreground border-secondary" : "bg-background border-border"
            )}
          >
            <SlidersHorizontal className="w-4 h-4" />
            {t("filters")}
            {activeCount > 0 && <span className="text-xs">({activeCount})</span>}
            <ChevronDown className={cn("w-3.5 h-3.5 transition-transform", open && "rotate-180")} />
          </button>
          <div className="flex gap-2 overflow-x-auto no-scrollbar -mx-1 px-1 py-0.5 min-w-0">
            {CATEGORIES.map((c) => {
              const Icon = c.icon;
              const active = category === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setCategory(c.id)}
                  data-testid={`filter-category-${c.id}`}
                  aria-pressed={active}
                  className={cn(
                    "flex items-center gap-1.5 px-3.5 h-9 rounded-full text-sm font-semibold whitespace-nowrap border transition-all duration-200",
                    active
                      ? "bg-primary text-primary-foreground border-primary shadow-sm"
                      : "bg-background border-border hover:border-primary/50 text-foreground/80"
                  )}
                >
                  <Icon className="w-4 h-4" style={active ? {} : { color: c.color }} />
                  {catLabel(t, c.id)}
                </button>
              );
            })}
          </div>
        </div>

        {/* Secondary filters: always shown on desktop, collapsible on mobile */}
        <div className={cn("flex-wrap items-center gap-x-6 gap-y-3 md:flex", open ? "flex" : "hidden")}>
          {/* Radius */}
          <div className="flex items-center gap-3 min-w-[220px] flex-1 max-w-xs">
            <SlidersHorizontal className="w-4 h-4 text-muted-foreground shrink-0" />
            <div className="flex-1">
              <div className="flex justify-between text-xs font-medium text-muted-foreground mb-1">
                <span>{t("radius")}</span>
                <span className="text-primary font-bold" data-testid="radius-value" dir="ltr">{radius} km</span>
              </div>
              <Slider
                min={1} max={50} step={1}
                value={[radius]}
                onValueChange={(v) => setRadius(v[0])}
                onValueCommit={onSearch}
                aria-label={t("radius")}
                data-testid="radius-slider"
              />
            </div>
          </div>

          {/* Ages */}
          <div className="flex items-center gap-1.5" data-testid="age-filter-group">
            <span className="text-xs font-medium text-muted-foreground me-1">{t("age")}</span>
            {AGE_GROUPS.map((a) => {
              const active = ages.includes(a.id);
              return (
                <button
                  key={a.id}
                  onClick={() => toggleAge(a.id)}
                  data-testid={`filter-age-${a.id}`}
                  aria-pressed={active}
                  dir="ltr"
                  className={cn(
                    "px-2.5 h-8 rounded-lg text-xs font-semibold border transition-colors",
                    active
                      ? "bg-secondary text-secondary-foreground border-secondary"
                      : "bg-background border-border text-foreground/70 hover:border-secondary/50"
                  )}
                >
                  {a.sub}
                </button>
              );
            })}
          </div>

          <Segmented
            label={t("setting")}
            testid="filter-setting"
            value={setting}
            onChange={setSetting}
            options={[
              { id: "all", label: t("all") },
              { id: "indoor", label: t("indoor") },
              { id: "outdoor", label: t("outdoor") },
            ]}
          />

          <Segmented
            label={t("price")}
            testid="filter-price"
            value={price}
            onChange={setPrice}
            options={[
              { id: "all", label: t("all") },
              { id: "free", label: t("free") },
              { id: "paid", label: t("paid") },
            ]}
          />
        </div>
      </div>
    </div>
  );
}

function Segmented({ label, options, value, onChange, testid }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs font-medium text-muted-foreground me-1">{label}</span>
      <div className="flex bg-muted rounded-lg p-0.5">
        {options.map((o) => (
          <button
            key={o.id}
            onClick={() => onChange(o.id)}
            data-testid={`${testid}-${o.id}`}
            aria-pressed={value === o.id}
            className={cn(
              "px-2.5 h-7 rounded-md text-xs font-semibold transition-colors",
              value === o.id ? "bg-card shadow-sm text-foreground" : "text-muted-foreground"
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
