import { Heart, Star, MapPin, Navigation, Home, Sun } from "lucide-react";
import { CATEGORY_MAP } from "@/lib/categories";
import { cn } from "@/lib/utils";

export function ActivityCard({ activity, index, isFavorite, onToggleFavorite, onOpen }) {
  const cat = CATEGORY_MAP[activity.category] || CATEGORY_MAP.all;
  const Icon = cat.icon;
  const fav = isFavorite(activity.id);

  return (
    <div
      onClick={() => onOpen(activity)}
      data-testid={`activity-card-${activity.id}`}
      className="group bg-card rounded-3xl overflow-hidden border border-border/70 hover:border-primary/40 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 cursor-pointer animate-fade-up flex flex-col"
      style={{ animationDelay: `${Math.min(index, 12) * 45}ms` }}
    >
      <div className="relative aspect-[16/10] overflow-hidden bg-muted">
        <img
          src={activity.image}
          alt={activity.name}
          loading="lazy"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/45 via-transparent to-transparent" />

        <div className="absolute top-3 left-3 flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/90 backdrop-blur text-xs font-bold" style={{ color: cat.color }}>
          <Icon className="w-3.5 h-3.5" />
          {cat.label}
        </div>

        <button
          onClick={(e) => { e.stopPropagation(); onToggleFavorite(activity); }}
          data-testid={`btn-save-favorite-${activity.id}`}
          className="absolute top-3 right-3 w-9 h-9 rounded-full bg-white/90 backdrop-blur flex items-center justify-center hover:scale-110 active:scale-95 transition-transform"
        >
          <Heart className={cn("w-4.5 h-4.5 transition-colors", fav ? "fill-primary text-primary" : "text-slate-600")} />
        </button>

        {typeof activity.distance_km === "number" && (
          <div className="absolute bottom-3 left-3 flex items-center gap-1 px-2.5 py-1 rounded-full bg-black/55 backdrop-blur text-white text-xs font-semibold">
            <Navigation className="w-3 h-3" />
            {activity.distance_km} km
          </div>
        )}
      </div>

      <div className="p-4 flex flex-col flex-1">
        <h3 className="font-heading font-bold text-base leading-snug line-clamp-1">{activity.name}</h3>
        <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1 line-clamp-1">
          <MapPin className="w-3 h-3 shrink-0" />
          {activity.address || activity.city}
        </p>

        <div className="flex items-center gap-1.5 mt-2.5 flex-wrap">
          {activity.rating && (
            <span className="flex items-center gap-0.5 text-xs font-bold text-amber-500">
              <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
              {activity.rating}
            </span>
          )}
          <SettingBadge setting={activity.setting} />
          <PriceBadge price={activity.price} />
        </div>

        <div className="flex gap-1 mt-3 flex-wrap">
          {(activity.ages || []).map((a) => (
            <span key={a} className="px-1.5 py-0.5 rounded-md bg-muted text-[10px] font-semibold text-muted-foreground">
              {a}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SettingBadge({ setting }) {
  if (!setting) return null;
  const indoor = setting === "indoor";
  return (
    <span
      className={cn(
        "flex items-center gap-0.5 px-1.5 py-0.5 rounded-md text-[10px] font-bold",
        indoor ? "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300"
               : "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300"
      )}
    >
      {indoor ? <Home className="w-2.5 h-2.5" /> : <Sun className="w-2.5 h-2.5" />}
      {indoor ? "Indoor" : "Outdoor"}
    </span>
  );
}

export function PriceBadge({ price }) {
  if (!price) return null;
  const free = price === "free";
  return (
    <span
      className={cn(
        "px-1.5 py-0.5 rounded-md text-[10px] font-bold",
        free ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
             : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
      )}
    >
      {free ? "FREE" : "PAID"}
    </span>
  );
}
