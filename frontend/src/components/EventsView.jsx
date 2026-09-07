import { Calendar, Clock, MapPin, Navigation } from "lucide-react";
import { EVENT_ICONS } from "@/lib/categories";
import { PriceBadge } from "@/components/ActivityCard";

export function EventsView({ events, loading }) {
  if (loading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-64 rounded-3xl bg-muted animate-pulse" />
        ))}
      </div>
    );
  }
  if (!events.length) {
    return <div className="text-center py-20 text-muted-foreground">No upcoming events in this area.</div>;
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {events.map((ev, i) => {
        const Icon = EVENT_ICONS[ev.category] || Calendar;
        const d = new Date(ev.date);
        return (
          <div
            key={ev.id}
            data-testid={`event-item-card-${ev.id}`}
            className="bg-card rounded-3xl overflow-hidden border border-border/70 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 animate-fade-up flex flex-col"
            style={{ animationDelay: `${i * 50}ms` }}
          >
            <div className="relative aspect-[16/9] bg-muted overflow-hidden">
              <img src={ev.image} alt={ev.name} className="w-full h-full object-cover" loading="lazy" />
              <div className="absolute top-3 left-3 flex flex-col items-center bg-white/95 backdrop-blur rounded-xl px-3 py-1.5 shadow">
                <span className="text-[10px] font-bold uppercase text-primary leading-none">
                  {d.toLocaleDateString("en-US", { month: "short" })}
                </span>
                <span className="text-xl font-heading font-extrabold leading-none text-slate-900">
                  {d.getDate()}
                </span>
              </div>
              <div className="absolute top-3 right-3">
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary text-primary-foreground text-xs font-bold">
                  <Icon className="w-3.5 h-3.5" /> {ev.category}
                </span>
              </div>
            </div>
            <div className="p-4 flex flex-col flex-1">
              <h3 className="font-heading font-bold text-base leading-snug">{ev.name}</h3>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2 flex-1">{ev.description}</p>
              <div className="mt-3 space-y-1 text-xs text-foreground/70">
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-primary" /> {ev.weekday} · {ev.time}
                </div>
                <div className="flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-primary" /> {ev.venue}, {ev.city}
                </div>
              </div>
              <div className="flex items-center gap-1.5 mt-3 flex-wrap">
                <PriceBadge price={ev.price} />
                {(ev.ages || []).map((a) => (
                  <span key={a} className="px-1.5 py-0.5 rounded-md bg-muted text-[10px] font-semibold text-muted-foreground">{a}</span>
                ))}
                {typeof ev.distance_km === "number" && (
                  <span className="flex items-center gap-0.5 text-[10px] font-semibold text-muted-foreground ml-auto">
                    <Navigation className="w-3 h-3" /> {ev.distance_km} km
                  </span>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground mt-2 italic">{ev.booking}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
