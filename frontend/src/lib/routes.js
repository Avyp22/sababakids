import CITIES from "@/lib/cities.json";
import SEO_CATS from "@/lib/seo-categories.json";

// Pages the app opens on: "/", "/<city>/" and "/<city>/<category>/" (the SEO pages
// prerendered by scripts/prerender-cities.js). Anything else is a "not found" page.
export function parseRoute(pathname) {
  const parts = pathname.replace(/\/index\.html$/, "/").split("/").filter(Boolean);
  if (parts.length === 0) return { found: true };
  const city = CITIES.find((c) => c.slug === parts[0]);
  if (!city || parts.length > 2) return { found: false };
  if (parts.length === 1) return { found: true, city };
  const cat = SEO_CATS.find((c) => c.slug === parts[1] && (!c.coastal || city.coastal));
  return cat ? { found: true, city, cat } : { found: false };
}

export const ROUTE = parseRoute(window.location.pathname);
