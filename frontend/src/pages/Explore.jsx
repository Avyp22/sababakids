import { useState, useEffect, useCallback, useMemo } from "react";
import { toast } from "sonner";
import { LayoutGrid, Map as MapIcon, Calendar, Heart, Compass, SearchX, Loader2 } from "lucide-react";
import { Header } from "@/components/Header";
import { FiltersBar } from "@/components/FiltersBar";
import { ActivityCard } from "@/components/ActivityCard";
import { ActivityDetail } from "@/components/ActivityDetail";
import { MapView } from "@/components/MapView";
import { EventsView } from "@/components/EventsView";
import { searchActivities, getEvents } from "@/lib/api";
import { useFavorites, useTheme } from "@/lib/store";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "list", label: "Explore", icon: LayoutGrid },
  { id: "map", label: "Map", icon: MapIcon },
  { id: "events", label: "Events", icon: Calendar },
  { id: "saved", label: "Saved", icon: Heart },
];

export default function Explore() {
  const { dark, setDark } = useTheme();
  const { favorites, isFavorite, toggleFavorite } = useFavorites();

  const [tab, setTab] = useState("list");
  const [locationInput, setLocationInput] = useState("Tel Aviv");
  const [radius, setRadius] = useState(10);
  const [category, setCategory] = useState("all");
  const [ages, setAges] = useState([]);
  const [setting, setSetting] = useState("all");
  const [price, setPrice] = useState("all");
  const [gpsCoords, setGpsCoords] = useState(null);
  const [gpsLoading, setGpsLoading] = useState(false);

  const [center, setCenter] = useState({ lat: 32.0853, lng: 34.7818, label: "Tel Aviv" });
  const [activities, setActivities] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [googleEnabled, setGoogleEnabled] = useState(false);

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
      setGoogleEnabled(data.google_enabled);
    } catch (e) {
      toast.error("Could not load activities. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [radius, category, ages, setting, price, gpsCoords, locationInput]);

  // Re-run when filters change
  useEffect(() => { runSearch(); }, [radius, category, ages, setting, price, gpsCoords]); // eslint-disable-line

  // Load events for current center
  useEffect(() => {
    let active = true;
    setEventsLoading(true);
    getEvents({ lat: center.lat, lng: center.lng, radius_km: Math.max(radius * 3, 60) })
      .then((d) => { if (active) setEvents(d.events); })
      .catch(() => {})
      .finally(() => { if (active) setEventsLoading(false); });
    return () => { active = false; };
  }, [center.lat, center.lng]); // eslint-disable-line

  const handleUseGps = () => {
    if (!navigator.geolocation) return toast.error("Geolocation not supported on this device.");
    setGpsLoading(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocationInput("My location");
        setGpsLoading(false);
        toast.success("Using your current location");
      },
      () => {
        setGpsLoading(false);
        toast.error("Couldn't get your location. Try typing a city instead.");
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  };

  const onManualSearch = () => {
    setGpsCoords(null);
    runSearch();
  };

  const openDetail = (a) => { setSelected(a); setDetailOpen(true); };

  const savedList = useMemo(() => favorites, [favorites]);
  const gridData = tab === "saved" ? savedList : activities;

  return (
    <div className="min-h-screen bg-background pb-20 md:pb-0">
      <Header
        locationLabel={center.label}
        favCount={favorites.length}
        dark={dark}
        onToggleDark={() => setDark(!dark)}
        onSavedClick={() => setTab("saved")}
      />

      <FiltersBar
        locationInput={locationInput}
        setLocationInput={setLocationInput}
        onSearch={onManualSearch}
        onUseGps={handleUseGps}
        gpsLoading={gpsLoading}
        radius={radius} setRadius={setRadius}
        category={category} setCategory={setCategory}
        ages={ages} toggleAge={toggleAge}
        setting={setting} setSetting={setSetting}
        price={price} setPrice={setPrice}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-5">
        {/* Desktop tabs + result count */}
        <div className="flex items-center justify-between mb-5 gap-3">
          <div className="hidden md:flex bg-muted rounded-2xl p-1">
            {TABS.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  data-testid={`tab-${t.id}`}
                  className={cn(
                    "flex items-center gap-2 px-4 h-10 rounded-xl text-sm font-semibold transition-colors",
                    tab === t.id ? "bg-card shadow-sm text-primary" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {t.label}
                  {t.id === "saved" && favorites.length > 0 && (
                    <span className="text-xs bg-primary text-primary-foreground rounded-full px-1.5">{favorites.length}</span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="text-sm text-muted-foreground" data-testid="result-summary">
            {tab === "events" ? (
              <span>{events.length} upcoming events</span>
            ) : tab === "saved" ? (
              <span>{savedList.length} saved</span>
            ) : loading ? (
              <span className="flex items-center gap-1.5"><Loader2 className="w-3.5 h-3.5 animate-spin" /> Searching…</span>
            ) : (
              <span><b className="text-foreground">{activities.length}</b> activities near <b className="text-foreground">{center.label}</b></span>
            )}
          </div>
        </div>

        {googleEnabled === false && tab !== "events" && (
          <div className="mb-4 text-xs text-muted-foreground bg-accent/10 border border-accent/20 rounded-xl px-3 py-2" data-testid="google-notice">
            Showing curated Israeli activities. Add a Google Maps API key to include live nearby places.
          </div>
        )}

        {/* Content */}
        {tab === "map" ? (
          <MapView center={center} activities={activities} onOpen={openDetail} />
        ) : tab === "events" ? (
          <EventsView events={events} loading={eventsLoading} />
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
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-card/95 backdrop-blur-lg border-t border-border px-2 py-2 flex justify-around">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-testid={`nav-${t.id}`}
              className={cn(
                "flex flex-col items-center gap-0.5 px-3 py-1 rounded-xl relative transition-colors",
                tab === t.id ? "text-primary" : "text-muted-foreground"
              )}
            >
              <Icon className="w-5 h-5" />
              <span className="text-[10px] font-semibold">{t.label}</span>
              {t.id === "saved" && favorites.length > 0 && (
                <span className="absolute top-0 right-1 w-4 h-4 bg-primary text-primary-foreground text-[9px] rounded-full flex items-center justify-center font-bold">{favorites.length}</span>
              )}
            </button>
          );
        })}
      </nav>
    </div>
  );
}

function EmptyState({ tab }) {
  const saved = tab === "saved";
  return (
    <div className="text-center py-20 animate-fade-up" data-testid="empty-state">
      <div className="w-16 h-16 rounded-2xl bg-muted flex items-center justify-center mx-auto mb-4">
        {saved ? <Heart className="w-7 h-7 text-muted-foreground" /> : <SearchX className="w-7 h-7 text-muted-foreground" />}
      </div>
      <h3 className="font-heading font-bold text-lg">
        {saved ? "No saved activities yet" : "No activities match your filters"}
      </h3>
      <p className="text-sm text-muted-foreground mt-1 max-w-xs mx-auto">
        {saved
          ? "Tap the heart on any activity to build your family trip list."
          : "Try widening the radius or clearing some filters."}
      </p>
    </div>
  );
}
