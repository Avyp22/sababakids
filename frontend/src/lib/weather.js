// Today's forecast from Open-Meteo (free, no key, CORS enabled).
const cache = new Map();

export async function getWeather(lat, lng) {
  const key = `${lat.toFixed(2)},${lng.toFixed(2)}`;
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < 30 * 60 * 1000) return hit.data;
  const params = new URLSearchParams({
    latitude: lat.toFixed(3),
    longitude: lng.toFixed(3),
    current: "temperature_2m,precipitation,weather_code",
    daily: "temperature_2m_max,precipitation_probability_max",
    timezone: "Asia/Jerusalem",
    forecast_days: "1",
  });
  const res = await fetch(`https://api.open-meteo.com/v1/forecast?${params}`);
  if (!res.ok) throw new Error(`weather ${res.status}`);
  const j = await res.json();
  const data = {
    now: Math.round(j.current?.temperature_2m),
    raining: (j.current?.precipitation || 0) > 0.1,
    max: Math.round(j.daily?.temperature_2m_max?.[0]),
    rainChance: j.daily?.precipitation_probability_max?.[0] ?? 0,
    code: j.current?.weather_code ?? 0,
  };
  cache.set(key, { at: Date.now(), data });
  return data;
}

// What to suggest: "rain" (go indoors), "hot" (indoors / water), or "nice".
export function weatherAdvice(w) {
  if (!w) return null;
  if (w.raining || w.rainChance >= 60) return "rain";
  if (w.max >= 32) return "hot";
  return "nice";
}

export function weatherEmoji(w) {
  if (!w) return "";
  if (w.raining || w.rainChance >= 60) return "🌧️";
  if (w.max >= 32) return "🥵";
  if (w.code <= 1) return "☀️";
  if (w.code <= 3) return "⛅";
  return "🌥️";
}
