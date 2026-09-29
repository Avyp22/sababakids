import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  Heart, Star, MapPin, Clock, Navigation, ExternalLink, Check,
} from "lucide-react";
import { CATEGORY_MAP, catLabel } from "@/lib/categories";
import { SettingBadge, PriceBadge, OpenNowBadge, SourceTag } from "@/components/ActivityCard";
import { useI18n, FEATURE_LABELS } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function ActivityDetail({ activity, open, onClose, isFavorite, onToggleFavorite }) {
  const { t, lang, rtl } = useI18n();
  if (!activity) return null;
  const cat = CATEGORY_MAP[activity.category] || CATEGORY_MAP.all;
  const Icon = cat.icon;
  const fav = isFavorite(activity.id);
  const mapsUrl =
    activity.google_maps_uri ||
    `https://www.google.com/maps/search/?api=1&query=${activity.lat},${activity.lng}`;
  const wazeUrl = `https://waze.com/ul?ll=${activity.lat},${activity.lng}&navigate=yes`;
  // Curated descriptions are English-only; Google results get a translated line.
  const description = activity.source === "google" ? t("googleResult") : activity.description;
  const hours = activity.source === "google" && activity.hours === "See Google Maps for hours" ? null : activity.hours;

  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent
        side={rtl ? "left" : "right"}
        className="w-full sm:max-w-md p-0 overflow-y-auto"
        data-testid="activity-detail-drawer"
      >
        <div className="relative aspect-[16/11] bg-muted">
          {activity.image ? (
            <img src={activity.image} alt={activity.name} className="w-full h-full object-cover" onError={(e) => { e.currentTarget.style.display = "none"; }} />
          ) : (
            <div className="w-full h-full flex items-center justify-center" style={{ background: `linear-gradient(135deg, ${cat.color}22, ${cat.color}66)` }}>
              <Icon className="w-14 h-14" style={{ color: cat.color }} />
            </div>
          )}
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
          <div className="absolute bottom-4 start-4 end-4">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/90 text-xs font-bold w-fit mb-2" style={{ color: cat.color }}>
              <Icon className="w-3.5 h-3.5" />
              {catLabel(t, cat.id)}
            </div>
            <h2 className="font-heading font-extrabold text-2xl text-white leading-tight drop-shadow" dir="auto">
              {activity.name}
            </h2>
          </div>
          <button
            onClick={() => onToggleFavorite(activity)}
            aria-label={t("tabSaved")}
            aria-pressed={fav}
            data-testid="detail-save-favorite"
            className="absolute top-4 end-[4.5rem] w-11 h-11 rounded-full bg-white/90 backdrop-blur flex items-center justify-center hover:scale-110 transition-transform"
          >
            <Heart className={cn("w-5 h-5", fav ? "fill-primary text-primary" : "text-slate-600")} />
          </button>
        </div>

        <SheetHeader className="sr-only">
          <SheetTitle>{activity.name}</SheetTitle>
          <SheetDescription>{t("detailsFor", { name: activity.name })}</SheetDescription>
        </SheetHeader>

        <div className="p-5 space-y-5">
          <div className="flex items-center gap-2 flex-wrap">
            {activity.rating && (
              <span className="flex items-center gap-1 text-sm font-bold text-amber-500">
                <Star className="w-4 h-4 fill-amber-400 text-amber-400" />
                {activity.rating}
                <span className="text-muted-foreground font-medium">({activity.reviews})</span>
              </span>
            )}
            <SettingBadge setting={activity.setting} />
            <PriceBadge price={activity.price} />
            <OpenNowBadge openNow={activity.open_now} />
            {typeof activity.distance_km === "number" && (
              <span className="flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                <Navigation className="w-3.5 h-3.5" /> {t("kmAway", { km: activity.distance_km })}
              </span>
            )}
          </div>

          <p className="text-sm leading-relaxed text-foreground/80" dir={activity.source === "google" ? undefined : "ltr"}>
            {description}
          </p>

          <div className="space-y-2 text-sm">
            <div className="flex items-start gap-2">
              <MapPin className="w-4 h-4 text-primary mt-0.5 shrink-0" />
              <span dir="auto">{activity.address || activity.city}</span>
            </div>
            <div className="flex items-start gap-2">
              <Clock className="w-4 h-4 text-primary mt-0.5 shrink-0" />
              <span dir="auto">{hours || t("hoursUnknown")}</span>
            </div>
          </div>

          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-2">{t("goodForAges")}</p>
            <div className="flex gap-1.5 flex-wrap">
              {(activity.ages || []).map((a) => (
                <span key={a} className="px-2.5 py-1 rounded-lg bg-secondary/10 text-secondary text-xs font-bold border border-secondary/20">
                  {t("years", { a })}
                </span>
              ))}
            </div>
          </div>

          {activity.features?.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground mb-2">{t("whatsHere")}</p>
              <div className="grid grid-cols-2 gap-1.5">
                {activity.features.map((f) => (
                  <div key={f} className="flex items-center gap-1.5 text-xs text-foreground/80">
                    <Check className="w-3.5 h-3.5 text-secondary shrink-0" />
                    {FEATURE_LABELS[f]?.[lang] || f}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 pt-2">
            <Button asChild variant="outline" className="rounded-xl h-11 gap-2">
              <a href={wazeUrl} target="_blank" rel="noopener noreferrer" data-testid="detail-waze-btn">
                <Navigation className="w-4 h-4" /> Waze
              </a>
            </Button>
            <Button asChild className="rounded-xl h-11 gap-2">
              <a href={mapsUrl} target="_blank" rel="noopener noreferrer" data-testid="detail-maps-btn">
                <ExternalLink className="w-4 h-4" /> Google Maps
              </a>
            </Button>
          </div>

          <div className="flex justify-end">
            <SourceTag source={activity.source} />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
