import { useState, useEffect, useCallback } from "react";

const FAV_KEY = "sababakids_favorites";
const THEME_KEY = "sababakids_theme";
const PREFS_KEY = "sababakids_prefs";

function readJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
}

// Last search location + usual filters, so the app reopens where the family left it.
export function loadPrefs() {
  return readJson(PREFS_KEY, {});
}

export function savePrefs(patch) {
  writeJson(PREFS_KEY, { ...loadPrefs(), ...patch });
}

// Last search response, shown instantly on the next visit while the (possibly
// sleeping) backend answers. Only one entry is kept.
const LAST_SEARCH_KEY = "sababakids_last_search";
const LAST_SEARCH_MAX_AGE_MS = 24 * 3600 * 1000;

export function loadLastSearch(key) {
  const hit = readJson(LAST_SEARCH_KEY, null);
  return hit && hit.key === key && Date.now() - hit.at < LAST_SEARCH_MAX_AGE_MS ? hit.data : null;
}

export function saveLastSearch(key, data) {
  writeJson(LAST_SEARCH_KEY, { key, at: Date.now(), data });
}

export function useFavorites() {
  const [favorites, setFavorites] = useState(() => readJson(FAV_KEY, []));

  useEffect(() => {
    writeJson(FAV_KEY, favorites);
  }, [favorites]);

  const isFavorite = useCallback(
    (id) => favorites.some((f) => f.id === id),
    [favorites]
  );

  const toggleFavorite = useCallback((activity) => {
    setFavorites((prev) =>
      prev.some((f) => f.id === activity.id)
        ? prev.filter((f) => f.id !== activity.id)
        : [...prev, activity]
    );
  }, []);

  return { favorites, isFavorite, toggleFavorite };
}

export function useTheme() {
  const [dark, setDark] = useState(() => {
    let stored = null;
    try { stored = localStorage.getItem(THEME_KEY); } catch {}
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try { localStorage.setItem(THEME_KEY, dark ? "dark" : "light"); } catch {}
  }, [dark]);

  return { dark, setDark };
}
