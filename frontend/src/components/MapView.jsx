import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { CATEGORY_MAP } from "@/lib/categories";

const CATEGORY_EMOJI = {
  park: "🌳", playground: "🛝", beach: "🏖️", museum: "🏛️", zoo: "🦁",
  aquarium: "🐠", water_park: "💦", amusement_park: "🎡", indoor_play: "🧸",
};

const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function pinIcon(activity) {
  const cat = CATEGORY_MAP[activity.category] || CATEGORY_MAP.all;
  const emoji = CATEGORY_EMOJI[activity.category] || "⭐";
  return L.divIcon({
    className: "map-pin",
    html: `<div class="map-pin-inner" style="background:${cat.color};font-size:15px;line-height:1">${emoji}</div>`,
    iconSize: [34, 34],
    iconAnchor: [17, 34],
    popupAnchor: [0, -34],
  });
}

export function MapView({ center, activities, onOpen }) {
  const mapRef = useRef(null);
  const containerRef = useRef(null);
  const layerRef = useRef(null);
  const circleRef = useRef(null);

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;
    const map = L.map(containerRef.current, {
      center: [center.lat, center.lng],
      zoom: 12,
      scrollWheelZoom: true,
      zoomControl: true,
    });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);
    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;
    setTimeout(() => map.invalidateSize(), 200);
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []); // eslint-disable-line

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.setView([center.lat, center.lng]);

    // center marker
    if (circleRef.current) circleRef.current.remove();
    circleRef.current = L.circleMarker([center.lat, center.lng], {
      radius: 8, color: "#E05A47", fillColor: "#E05A47", fillOpacity: 1, weight: 3,
    }).addTo(map);
  }, [center]);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;
    layer.clearLayers();
    const bounds = [[center.lat, center.lng]];
    activities.forEach((a) => {
      if (a.lat == null || a.lng == null) return;
      const marker = L.marker([a.lat, a.lng], { icon: pinIcon(a), title: a.name });
      const img = a.image
        ? `<img src="${escapeHtml(a.image)}" loading="lazy" style="width:100%;height:80px;object-fit:cover;border-radius:8px"/>`
        : "";
      marker.bindPopup(
        `<div style="font-family:'Plus Jakarta Sans',sans-serif;min-width:140px">
          ${img}
          <div dir="auto" style="font-weight:700;font-size:13px;margin-top:6px">${escapeHtml(a.name)}</div>
          <div style="font-size:11px;color:#64748b" dir="ltr">${a.distance_km ?? ""} km ${a.rating ? "· ★ " + a.rating : ""}</div>
        </div>`
      );
      marker.on("click", () => onOpen(a));
      marker.addTo(layer);
      bounds.push([a.lat, a.lng]);
    });
    if (bounds.length > 1) {
      try { map.fitBounds(bounds, { padding: [50, 50], maxZoom: 13 }); } catch (e) {}
    }
  }, [activities]); // eslint-disable-line

  return (
    <div
      ref={containerRef}
      data-testid="map-container"
      dir="ltr"
      className="w-full h-[calc(100vh-260px)] min-h-[420px] rounded-3xl overflow-hidden border border-border shadow-sm z-0"
    />
  );
}

export default MapView;
