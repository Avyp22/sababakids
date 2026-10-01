import { Calendar, Clock, MapPin, Navigation, Ticket, CalendarPlus, Radio } from "lucide-react";
import { EVENT_ICONS } from "@/lib/categories";
import { PriceBadge } from "@/components/ActivityCard";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";
import { ReportButton } from "@/components/ReportButton";

// Google Calendar "add event" link, used when the source has no .ics file.
function googleCalendarUrl(ev) {
  const [y, m, d] = ev.date.split("-");
  const [hh, mm] = (ev.time || "10:00").split(":").map(Number);
  const pad = (n) => String(n).padStart(2, "0");
  const start = `${y}${m}${d}T${pad(hh)}${pad(mm)}00`;
  const endH = hh + 2;
  const end = `${y}${m}${d}T${pad(Math.min(endH, 23))}${pad(mm)}00`;
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: ev.name,
    dates: `${start}/${end}`,
    ctz: "Asia/Jerusalem",
    location: [ev.venue, ev.city].filter(Boolean).join(", "),
    details: ev.ticket_url || "",
  });
  return `https://calendar.google.com/calendar/render?${params}`;
}

export function EventsView({ events, loading, familyOnly }) {
  const { t, locale } = useI18n();
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
    return (
      <div className="text-center py-20 text-muted-foreground" data-testid="events-empty">
        {familyOnly ? t("noEventsFamily") : t("noEvents")}
      </div>
    );
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {events.map((ev, i) => {
        const Icon = EVENT_ICONS[ev.category] || Calendar;
        const d = new Date(`${ev.date}T12:00:00`);
        const weekday = d.toLocaleDateString(locale, { weekday: "long" });
        const calendarUrl = ev.ics_url || googleCalendarUrl(ev);
        return (
          <div
            key={ev.id}
            data-testid={`event-item-card-${ev.id}`}
            className="bg-card rounded-3xl overflow-hidden border border-border/70 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 animate-fade-up flex flex-col"
            style={{ animationDelay: `${Math.min(i, 12) * 45}ms` }}
          >
            <div className="relative aspect-[16/9] bg-muted overflow-hidden">
              {ev.image ? (
                <img src={ev.image} alt={ev.name} className="w-full h-full object-cover" loading="lazy" decoding="async"
                  onError={(e) => { e.currentTarget.style.display = "none"; }} />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-gradient-to-br from-primary/15 to-accent/20">
                  <Icon className="w-10 h-10 text-primary/70" />
                </div>
              )}
              <div className="absolute top-3 start-3 flex flex-col items-center bg-white/95 backdrop-blur rounded-xl px-3 py-1.5 shadow">
                <span className="text-[10px] font-bold uppercase text-primary leading-none">
                  {d.toLocaleDateString(locale, { month: "short" })}
                </span>
                <span className="text-xl font-heading font-extrabold leading-none text-slate-900">
                  {d.getDate()}
                </span>
              </div>
              <div className="absolute top-3 end-3">
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary text-primary-foreground text-xs font-bold">
                  <Icon className="w-3.5 h-3.5" /> {t(`ev_${ev.category}`)}
                </span>
              </div>
            </div>
            <div className="p-4 flex flex-col flex-1">
              <h3 className="font-heading font-bold text-base leading-snug" dir="auto">{ev.name}</h3>
              <p className="text-xs text-muted-foreground mt-1 line-clamp-2 flex-1" dir="auto">{ev.description}</p>
              <div className="mt-3 space-y-1 text-xs text-foreground/70">
                <div className="flex items-center gap-1.5">
                  <Clock className="w-3.5 h-3.5 text-primary shrink-0" /> {weekday}{ev.time ? ` · ${ev.time}` : ""}
                  {ev.end_date && (
                    <span> → {new Date(`${ev.end_date}T12:00:00`).toLocaleDateString(locale, { day: "numeric", month: "short" })}</span>
                  )}
                </div>
                <div className="flex items-center gap-1.5">
                  <MapPin className="w-3.5 h-3.5 text-primary shrink-0" />
                  <span className="line-clamp-1" dir="auto">{[ev.venue, ev.city].filter(Boolean).join(", ")}</span>
                </div>
              </div>
              <div className="flex items-center gap-1.5 mt-3 flex-wrap">
                <PriceBadge price={ev.price} />
                {ev.price_text && <span className="text-[10px] font-semibold text-muted-foreground" dir="ltr">{ev.price_text}</span>}
                {(ev.ages || []).map((a) => (
                  <span key={a} dir="ltr" className="px-1.5 py-0.5 rounded-md bg-muted text-[10px] font-semibold text-muted-foreground">{a}</span>
                ))}
                {typeof ev.distance_km === "number" && (
                  <span
                    className="flex items-center gap-0.5 text-[10px] font-semibold text-muted-foreground ms-auto"
                    dir="ltr"
                    title={ev.approx ? t("approx") : undefined}
                  >
                    <Navigation className="w-3 h-3" /> {ev.approx ? "≈ " : ""}{ev.distance_km} km
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 mt-3">
                {ev.ticket_url ? (
                  <Button asChild size="sm" className="rounded-xl h-9 gap-1.5" data-testid={`event-tickets-${ev.id}`}>
                    <a href={ev.ticket_url} target="_blank" rel="noopener noreferrer">
                      <Ticket className="w-3.5 h-3.5" /> {t("tickets")}
                    </a>
                  </Button>
                ) : <span />}
                <Button asChild size="sm" variant="outline" className="rounded-xl h-9 gap-1.5" data-testid={`event-calendar-${ev.id}`}>
                  <a href={calendarUrl} target="_blank" rel="noopener noreferrer">
                    <CalendarPlus className="w-3.5 h-3.5" /> {t("calendar")}
                  </a>
                </Button>
              </div>

              <div className="flex items-center gap-1.5 mt-3 pt-2 border-t border-border/60 text-[10px] text-muted-foreground flex-wrap">
                <Radio className="w-3 h-3 text-emerald-500" />
                <span>{t("live")} · {ev.source}</span>
                <ReportButton itemId={ev.id} kind="event" name={ev.name} className="ms-auto" />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
