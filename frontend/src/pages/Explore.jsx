import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { toast } from "sonner";
import { LayoutGrid, Map as MapIcon, Calendar, Heart, SearchX, Loader2, Share2, LocateFixed, X } from "lucide-react";
import { Header } from "@/components/Header";
import { FiltersBar } from "@/components/FiltersBar";
import { ActivityCard } from "@/components/ActivityCard";
import { ActivityDetail } from "@/components/ActivityDetail";
import { EventsView } from "@/components/EventsView";
import { searchActivities, getEvents } from "@/lib/api";
import { useFavorites, useTheme, loadPrefs, savePrefs } from "@/lib/store";
import { useI18n } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// Leaflet is only downloaded when the Map tab is opened.
const MapView = lazy(() => import("@/components/MapView"));

const TABS = [
  { id: "list", label: "tabExplore", icon: LayoutGrid },
  { id: "map", label: "tabMap", icon: MapIcon },
  { id: "events", label: "tabEvents", icon: Calendar },
  { id: "saved", label: "tabSaved", icon: Heart },
];

const DEFAULT_CENTER = { lat: 32.0853, lng: 34.7818, label: "Tel Aviv" };

export default function Explore() {
  const { t } = useI18n();
  const { dark, setDark } = useTheme();
  const { favorites, isFavorite, toggleFavorite } = useFavorites();
  const [prefs] = useState(loadPrefs);

  const [tab, setTab] = useState("list");
  const [locationInput, setLocationInput] = useState(prefs.location || "Tel Aviv");
  const [radius, setRadius] = useState(prefs.radius || 10);
  const [category, setCategory] = useState(prefs.category || "all");
  const [ages, setAges] = useState(prefs.ages || []);
  const [setting, setSetting] = useState("all");
  const [price, setPrice] = useState("all");
  const [gpsCoords, setGpsCoords] = useState(null);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [showGpsPrompt, setShowGpsPrompt] = useState(!prefs.location);

  const [center, setCenter] = useState(DEFAULT_CENTER);
  const [activities, setActivities] = useState([]);
  const [events, setEvents] = useState([]);
  const [eventSources, setEventSources] = useState([]);
  const [familyOnly, setFamilyOnly] = useState(prefs.familyOnly ?? true);
  const [loading, setLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [googleDown, setGoogleDown] = useState(false);

  const toggleAge = (id) =>
    setAges((prev) => (prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]));

  const runSearch = useCallback(async () => {
    setLoading(true);
    try {
      const payload = {
        radius_km: radius, category, ages, setting, price,
        ...(gpsCoords ? { lat: gpsCoords.lat, lng: gpsCoords.lng } : { location: locationInput }),
      };
      const data = await searchActivities(payload);
      setActivities(data.activities);
      setCenter(data.center);
      setGoogleDown(!data.google_enabled || (data.google_errors || []).length > 0);
      if (!gpsCoords) savePrefs({ location: locationInput });
    } catch (e) {
      toast.error(t("loadError"));
    } finally {
      setLoading(false);
    }
  }, [radius, category, ages, setting, price, gpsCoords, locationInput, t]);

  // Re-run when filters change
  useEffect(() => { runSearch(); }, [radius, category, ages, setting, price, gpsCoords]); // eslint-disable-line

  // Remember the user's usual filters
  useEffect(() => { savePrefs({ radius, category, ages, familyOnly }); }, [radius, category, ages, familyOnly]);

  // Load events for current center
  useEffect(() => {
    let active = true;
    setEventsLoading(true);
    getEvents({ lat: center.lat, lng: center.lng, radius_km: Math.max(radius * 3, 60), family_only: familyOnly })
      .then((d) => { if (active) { setEvents(d.events); setEventSources(d.live_sources || []); } })
      .catch(() => {})
      .finally(() => { if (active) setEventsLoading(false); });
    return () => { active = false; };
  }, [center.lat, center.lng, familyOnly]); // eslint-disable-line

  const handleUseGps = useCallback((silent = false) => {
    if (!navigator.geolocation) {
      if (!silent) toast.error(t("gpsUnsupported"));
      return;
    }
    setGpsLoading(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocationInput(t("myLocation"));
        setGpsLoading(false);
        setShowGpsPrompt(false);
        if (!silent) toast.success(t("gpsOk"));
      },
      () => {
        setGpsLoading(false);
        if (!silent) toast.error(t("gpsFail"));
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 300000 }
    );
  }, [t]);

  // If the user already allowed location access, use it straight away.
  useEffect(() => {
    if (prefs.location || !navigator.permissions?.query) return;
    navigator.permissions.query({ name: "geolocation" })
      .then((st) => { if (st.state === "granted") handleUseGps(true); })
      .catch(() => {});
  }, []); // eslint-disable-line

  const onManualSearch = () => {
    setShowGpsPrompt(false);
    // Clearing GPS coords re-triggers the search effect; otherwise search directly.
    if (gpsCoords) setGpsCoords(null);
    else runSearch();
  };

  const openDetail = (a) => { setSelected(a); setDetailOpen(true); };

  const shareFavorites = () => {
    if (!favorites.length) return;
    const lines = favorites.map((a, i) => {
      const maps = a.google_maps_uri || `https://www.google.com/maps/search/?api=1&query=${a.lat},${a.lng}`;
      return `${i + 1}. ${a.name} (${a.city || a.address})\n   ${maps}`;
    });
    const text = `👨‍👩‍👧‍👦 ${t("shareIntro")}\n\n${lines.join("\n\n")}\n\n${window.location.origin}`;
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, "_blank");
    toast.success(t("shareOpening"));
  };

  const centerLabel = center.label === "Your location" ? t("yourLocation") : center.label;
  const gridData = tab === "saved" ? favorites : activities;

  return (
    <div className="min-h-screen bg-background pb-20 md:pb-0">
      <Header
        locationLabel={centerLabel}
        favCount={favorites.length}
        dark={dark}
        onToggleDark={() => setDark(!dark)}
        onSavedClick={() => setTab("saved")}
      />

      <FiltersBar
        locationInput={locationInput}
        setLocationInput={setLocationInput}
        onSearch={onManualSearch}
        onUseGps={() => handleUseGps(false)}
        gpsLoading={gpsLoading}
        radius={radius} setRadius={setRadius}
        category={category} setCategory={setCategory}
        ages={ages} toggleAge={toggleAge}
        setting={setting} setSetting={setSetting}
        price={price} setPrice={setPrice}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-5">
        {showGpsPrompt && !gpsCoords && (
          <div className="mb-4 flex items-center gap-3 bg-primary/10 border border-primary/20 rounded-2xl px-4 py-3" data-testid="gps-prompt">
            <LocateFixed className="w-5 h-5 text-primary shrink-0" />
            <p className="text-sm font-medium flex-1">{t("gpsPrompt")}</p>
            <Button size="sm" className="rounded-xl" onClick={() => handleUseGps(false)} disabled={gpsLoading}>
              {t("gpsPromptBtn")}
            </Button>
            <button onClick={() => setShowGpsPrompt(false)} aria-label="close" className="text-muted-foreground">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Desktop tabs + result count */}
        <div className="flex items-center justify-between mb-5 gap-3">
          <div className="hidden md:flex bg-muted rounded-2xl p-1">
            {TABS.map((tb) => {
              const Icon = tb.icon;
              return (
                <button
                  key={tb.id}
                  onClick={() => setTab(tb.id)}
                  data-testid={`tab-${tb.id}`}
                  className={cn(
                    "flex items-center gap-2 px-4 h-10 rounded-xl text-sm font-semibold transition-colors",
                    tab === tb.id ? "bg-card shadow-sm text-primary" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {t(tb.label)}
                  {tb.id === "saved" && favorites.length > 0 && (
                    <span className="text-xs bg-primary text-primary-foreground rounded-full px-1.5">{favorites.length}</span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="text-sm text-muted-foreground" data-testid="result-summary">
            {tab === "events" ? (
              <span>{t("upcomingEvents", { n: events.length })}</span>
            ) : tab === "saved" ? (
              <span>{t("savedCount", { n: favorites.length })}</span>
            ) : loading ? (
              <span className="flex items-center gap-1.5"><Loader2 className="w-3.5 h-3.5 animate-spin" /> {t("searching")}</span>
            ) : (
              <span>{t("activitiesNear", { n: activities.length, place: centerLabel })}</span>
            )}
          </div>
        </div>

        {googleDown && !loading && (tab === "list" || tab === "map") && (
          <div className="mb-4 text-xs text-muted-foreground bg-accent/10 border border-accent/20 rounded-xl px-3 py-2" data-testid="google-notice">
            {t("curatedOnly")}
          </div>
        )}

        {tab === "saved" && favorites.length > 0 && (
          <div className="mb-4 flex items-center justify-between gap-3 bg-secondary/10 border border-secondary/20 rounded-2xl px-4 py-3 flex-wrap">
            <p className="text-sm font-medium text-foreground/80">{t("shareHint")}</p>
            <Button onClick={shareFavorites} className="rounded-xl gap-2 bg-[#25D366] hover:bg-[#1ebe5b] text-white" data-testid="btn-share-whatsapp">
              <Share2 className="w-4 h-4" /> {t("shareWhatsapp")}
            </Button>
          </div>
        )}

        {tab === "events" && (
          <div className="mb-4 flex items-center justify-between gap-3 flex-wrap">
            <div className="text-xs text-muted-foreground flex items-center gap-1.5" data-testid="events-source-note">
              {eventSources.length > 0 && (
                <><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> {t("liveFrom", { sources: eventSources.join(", ") })}</>
              )}
            </div>
            <div className="flex bg-muted rounded-full p-0.5" role="group">
              {[true, false].map((v) => (
                <button
                  key={String(v)}
                  onClick={() => setFamilyOnly(v)}
                  aria-pressed={familyOnly === v}
                  data-testid={v ? "toggle-family-only" : "toggle-all-events"}
                  className={cn(
                    "px-3 h-8 rounded-full text-xs font-semibold transition-colors",
                    familyOnly === v ? "bg-card shadow-sm text-foreground" : "text-muted-foreground"
                  )}
                >
                  {v ? `👨‍👩‍👧 ${t("familyOnly")}` : t("allEvents")}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Content */}
        {tab === "map" ? (
          <Suspense fallback={<div className="h-[420px] rounded-3xl bg-muted animate-pulse" />}>
            <MapView center={center} activities={activities} onOpen={openDetail} />
          </Suspense>
        ) : tab === "events" ? (
          <EventsView events={events} loading={eventsLoading} familyOnly={familyOnly} />
        ) : loading && tab === "list" ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-72 rounded-3xl bg-muted animate-pulse" />
            ))}
          </div>
        ) : gridData.length === 0 ? (
          <EmptyState tab={tab} />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" data-testid="activities-grid">
            {gridData.map((a, i) => (
              <ActivityCard
                key={a.id}
                activity={a}
                index={i}
                isFavorite={isFavorite}
                onToggleFavorite={toggleFavorite}
                onOpen={openDetail}
              />
            ))}
          </div>
        )}
      </main>

      <ActivityDetail
        activity={selected}
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        isFavorite={isFavorite}
        onToggleFavorite={toggleFavorite}
      />

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-card/95 backdrop-blur-lg border-t border-border px-2 py-2 flex justify-around">
        {TABS.map((tb) => {
          const Icon = tb.icon;
          return (
            <button
              key={tb.id}
              onClick={() => setTab(tb.id)}
              data-testid={`nav-${tb.id}`}
              aria-current={tab === tb.id ? "page" : undefined}
              className={cn(
                "flex flex-col items-center gap-0.5 px-3 py-1 rounded-xl relative transition-colors",
                tab === tb.id ? "text-primary" : "text-muted-foreground"
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-semibold">{t(tb.label)}</span>
              {tb.id === "saved" && favorites.length > 0 && (
                <span className="absolute top-0 end-1 w-4 h-4 bg-primary text-primary-foreground text-[9px] rounded-full flex items-center justify-center font-bold">{favorites.length}</span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

function EmptyState({ tab }) {
  const { t } = useI18n();
  const saved = tab === "saved";
  return (
    <div className="text-center py-20 animate-fade-up" data-testid="empty-state">
      <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
        {saved ? <Heart className="w-7 h-7 text-muted-foreground" /> : <SearchX className="w-7 h-7 text-muted-foreground" />}
      </div>
      <h3 className="font-heading font-bold text-lg">
        {saved ? t("noSaved") : t("noMatch")}
      </h3>
      <p className="text-sm text-muted-foreground mt-1 max-w-xs mx-auto">
        {saved ? t("noSavedHint") : t("noMatchHint")}
      </p>
    </div>
  );
}
