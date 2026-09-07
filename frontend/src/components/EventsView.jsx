import { Calendar, Clock, MapPin, Navigation, Ticket, CalendarPlus, Radio } from "lucide-react";
import { EVENT_ICONS } from "@/lib/categories";
import { PriceBadge } from "@/components/ActivityCard";
import { Button } from "@/components/ui/button";

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
        const live = ev.source && ev.source !== "SababaKids picks";
        return (
          <div
            key={ev.id}
            data-testid={`event-item-card-${ev.id}`}
            className="bg-card rounded-3xl overflow-hidden border border-border/70 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 animate-fade-up flex flex-col"
            style={{ animationDelay: `${Math.min(i, 12) * 45}ms` }}
          >
            <div className="relative aspect-[16/9] bg-muted overflow-hidden">
              {ev.image ? (
                <img src={ev.image} alt={ev.name} className="w-full h-full object-cover" loading="lazy"
                  onError={(e) => { e.currentTarget.style.display = "none"; }} />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/15 to-accent/20">
                  <Icon className="w-10 h-10 text-primary/70" />
                </div>
              )}
              <div className="absolute top-3 left-3 flex flex-col items-center bg-white/95 backdrop-blur rounded-xl px-3 py-1.5 shadow">
                <span className="text-[10px] font-bold uppercase text-primary leading-none">
                  {d.toLocaleDateString("en-US", { month: "short" })}
                </span>
                <span className="text-xl font-heading font-extrabold leading-none text-slate-900">
                  {d.getDate()}
                </span>
              </div>
              <div className="absolute top-3 right-3">
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary text-primary-foreground text-xs font-bold capitalize">
                  <Icon className="w-3.5 h-3.5" /> {ev.category}
                </span>
              </div>
            </div>
            <div className="p-4 flex flex-col flex-1">
              <h3 className="font-heading font-bold text-base leading-snug" dir="auto">{ev.name}</h3>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2 flex-1" dir="auto">{ev.description}</p>
              <div className="mt-3 space-y-1 text-xs text-foreground/70">
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-primary shrink-0" /> {ev.weekday}{ev.time ? ` · ${ev.time}` : ""}
                </div>
                <div className="flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-primary shrink-0" /> <span className="line-clamp-1" dir="auto">{ev.venue}, {ev.city}</span>
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

              {(ev.ticket_url || ev.ics_url) && (
                <div className="grid grid-cols-2 gap-2 mt-3">
                  {ev.ticket_url ? (
                    <Button asChild size="sm" className="rounded-xl h-9 gap-1.5" data-testid={`event-tickets-${ev.id}`}>
                      <a href={ev.ticket_url} target="_blank" rel="noopener noreferrer">
                        <Ticket className="w-3.5 h-3.5" /> Tickets
                      </a>
                    </Button>
                  ) : <span />}
                  {ev.ics_url && (
                    <Button asChild size="sm" variant="outline" className="rounded-xl h-9 gap-1.5" data-testid={`event-calendar-${ev.id}`}>
                      <a href={ev.ics_url} target="_blank" rel="noopener noreferrer">
                        <CalendarPlus className="w-3.5 h-3.5" /> Calendar
                      </a>
                    </Button>
                  )}
                </div>
              )}

              <div className="flex items-center gap-1.5 mt-3 pt-2 border-t border-border/60 text-[10px] text-muted-foreground">
                {live && <Radio className="w-3 h-3 text-emerald-500" />}
                <span>{live ? "Live · " : ""}{ev.source}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
