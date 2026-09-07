import { useState, useEffect, useCallback } from "react";

const FAV_KEY = "sababakids_favorites";
const THEME_KEY = "sababakids_theme";

export function useFavorites() {
  const [favorites, setFavorites] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(FAV_KEY)) || [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(FAV_KEY, JSON.stringify(favorites));
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
    const stored = localStorage.getItem(THEME_KEY);
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem(THEME_KEY, dark ? "dark" : "light");
  }, [dark]);

  return { dark, setDark };
}
