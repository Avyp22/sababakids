import { Search, LocateFixed, SlidersHorizontal } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { CATEGORIES, AGE_GROUPS } from "@/lib/categories";
import { cn } from "@/lib/utils";

export function FiltersBar({
  locationInput, setLocationInput, onSearch, onUseGps, gpsLoading,
  radius, setRadius, category, setCategory, ages, toggleAge,
  setting, setSetting, price, setPrice,
}) {
  return (
    <div className="bg-card/60 border-b border-border/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 space-y-4">
        {/* Search row */}
        <form
          onSubmit={(e) => { e.preventDefault(); onSearch(); }}
          className="flex flex-col sm:flex-row gap-2"
        >
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              value={locationInput}
              onChange={(e) => setLocationInput(e.target.value)}
              placeholder="Search a city or address in Israel…"
              className="pl-10 h-12 rounded-2xl bg-background text-base"
              data-testid="search-location-input"
            />
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={onUseGps}
              disabled={gpsLoading}
              className="h-12 rounded-2xl gap-2 shrink-0"
              data-testid="btn-use-gps"
            >
              <LocateFixed className={cn("w-4 h-4", gpsLoading && "animate-spin")} />
              <span className="hidden sm:inline">My location</span>
            </Button>
            <Button
              type="submit"
              className="h-12 rounded-2xl px-6 gap-2 shrink-0"
              data-testid="btn-search"
            >
              <Search className="w-4 h-4" />
              Search
            </Button>
          </div>
        </form>

        {/* Category pills */}
        <div className="flex gap-2 overflow-x-auto no-scrollbar -mx-1 px-1 py-0.5">
          {CATEGORIES.map((c) => {
            const Icon = c.icon;
            const active = category === c.id;
            return (
              <button
                key={c.id}
                onClick={() => setCategory(c.id)}
                data-testid={`filter-category-${c.id}`}
                className={cn(
                  "flex items-center gap-1.5 px-3.5 h-9 rounded-full text-sm font-semibold whitespace-nowrap border transition-all duration-200",
                  active
                    ? "bg-primary text-primary-foreground border-primary shadow-sm scale-[1.03]"
                    : "bg-background border-border hover:border-primary/50 text-foreground/80"
                )}
              >
                <Icon className="w-4 h-4" style={active ? {} : { color: c.color }} />
                {c.label}
              </button>
            );
          })}
        </div>

        {/* Secondary filters */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          {/* Radius */}
          <div className="flex items-center gap-3 min-w-[220px] flex-1 max-w-xs">
            <SlidersHorizontal className="w-4 h-4 text-muted-foreground shrink-0" />
            <div className="flex-1">
              <div className="flex justify-between text-xs font-medium text-muted-foreground mb-1">
                <span>Radius</span>
                <span className="text-primary font-bold" data-testid="radius-value">{radius} km</span>
              </div>
              <Slider
                min={1} max={50} step={1}
                value={[radius]}
                onValueChange={(v) => setRadius(v[0])}
                onValueCommit={onSearch}
                data-testid="radius-slider"
              />
            </div>
          </div>

          {/* Ages */}
          <div className="flex items-center gap-1.5" data-testid="age-filter-group">
            <span className="text-xs font-medium text-muted-foreground mr-1">Age</span>
            {AGE_GROUPS.map((a) => {
              const active = ages.includes(a.id);
              return (
                <button
                  key={a.id}
                  onClick={() => toggleAge(a.id)}
                  data-testid={`filter-age-${a.id}`}
                  title={`${a.label} (${a.sub})`}
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

          {/* Setting */}
          <Segmented
            label="Setting"
            testid="filter-setting"
            value={setting}
            onChange={setSetting}
            options={[
              { id: "all", label: "All" },
              { id: "indoor", label: "Indoor" },
              { id: "outdoor", label: "Outdoor" },
            ]}
          />

          {/* Price */}
          <Segmented
            label="Price"
            testid="filter-price"
            value={price}
            onChange={setPrice}
            options={[
              { id: "all", label: "All" },
              { id: "free", label: "Free" },
              { id: "paid", label: "Paid" },
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
      <span className="text-xs font-medium text-muted-foreground mr-1">{label}</span>
      <div className="flex bg-muted rounded-lg p-0.5">
        {options.map((o) => (
          <button
            key={o.id}
            onClick={() => onChange(o.id)}
            data-testid={`${testid}-${o.id}`}
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
