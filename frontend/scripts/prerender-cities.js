/**
 * Post-build SEO step: one static page per city (/haifa/index.html, ...) with its
 * own title, description, canonical URL and readable content, plus sitemap.xml.
 * The React app then boots on that page and opens the matching city.
 *
 * When the backend answers, each page also lists the curated places near the city
 * and its upcoming family events, with schema.org Event data for Google. If the
 * backend is down the pages are still built, with the generic content only.
 *
 * Run automatically by the build (see package.json).
 */
const fs = require("fs");
const path = require("path");

const SITE = (process.env.PUBLIC_SITE_URL || "https://sababakids.onrender.com").replace(/\/$/, "");
const API = (process.env.REACT_APP_BACKEND_URL || process.env.VITE_BACKEND_URL || "").replace(/\/$/, "");
const BUILD = path.join(__dirname, "..", "build");
const cities = require("../src/lib/cities.json");

const PLACES_RADIUS_KM = 25;
const EVENTS_RADIUS_KM = 20;
const MAX_EVENTS = 15;

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function km(a, b) {
  const r = (d) => (d * Math.PI) / 180;
  const h = Math.sin(r(b.lat - a.lat) / 2) ** 2 +
    Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(r(b.lng - a.lng) / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

async function getJson(url, timeoutMs) {
  const res = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json();
}

// "+03:00" in summer, "+02:00" in winter.
function israelOffset(isoDate) {
  const name = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Jerusalem", timeZoneName: "longOffset" })
    .formatToParts(new Date(`${isoDate}T12:00:00Z`)).find((p) => p.type === "timeZoneName").value;
  return name.replace("GMT", "") || "+00:00";
}

function eventJsonLd(ev) {
  const start = /^\d{1,2}:\d{2}$/.test(ev.time || "")
    ? `${ev.date}T${ev.time.padStart(5, "0")}:00${israelOffset(ev.date)}`
    : ev.date;
  const data = {
    "@context": "https://schema.org",
    "@type": "Event",
    name: ev.name,
    startDate: start,
    eventStatus: "https://schema.org/EventScheduled",
    eventAttendanceMode: "https://schema.org/OfflineEventAttendanceMode",
    location: {
      "@type": "Place",
      name: ev.venue || ev.city,
      address: { "@type": "PostalAddress", addressLocality: ev.city || undefined, addressCountry: "IL" },
    },
  };
  if (ev.end_date) data.endDate = ev.end_date;
  if (ev.image) data.image = [ev.image];
  if (ev.description) data.description = ev.description;
  if (ev.ticket_url) data.url = ev.ticket_url;
  if (ev.family) data.typicalAgeRange = "2-12";
  // "</" inside a JSON string would close the <script> tag.
  return `<script type="application/ld+json">${JSON.stringify(data).replace(/</g, "\\u003c")}</script>`;
}

function cityPage(template, c, places, events) {
  const title = `פעילויות ואירועים לילדים ב${c.he} | Activités enfants à ${c.fr} | SababaKids`;
  const desc =
    `פארקים, חופים, מוזיאונים, מעיינות, הצגות ואירועים לילדים ב${c.he} ובסביבה. ` +
    `Parcs, plages, musées, spectacles et événements pour enfants à ${c.fr}. ` +
    `Kids activities and family events in ${c.en}.`;
  const url = `${SITE}/${c.slug}/`;

  const placesHtml = places.length
    ? `<h2>${esc(`מקומות מומלצים ב${c.he} ובסביבה`)}</h2><ul>` +
      places.map((p) => `<li><strong>${esc(p.name)}</strong> (${esc(p.city)}) — ${esc(p.description)}</li>`).join("") +
      `</ul>`
    : "";
  const eventsHtml = events.length
    ? `<h2>${esc(`אירועים קרובים לילדים ב${c.he}`)}</h2><ul>` +
      events.map((e) =>
        `<li><strong>${esc(e.name)}</strong> — ${esc(e.date)}${e.time ? ` ${esc(e.time)}` : ""}` +
        `${e.venue ? `, ${esc(e.venue)}` : ""}` +
        `${e.ticket_url ? ` <a href="${esc(e.ticket_url)}" rel="nofollow noopener">פרטים</a>` : ""}</li>`
      ).join("") +
      `</ul>`
    : "";

  const body =
    `<div id="root"><main style="max-width:720px;margin:40px auto;padding:0 16px;font-family:sans-serif">` +
    `<h1>${esc(`פעילויות לילדים ב${c.he}`)}</h1>` +
    `<p>${esc(desc)}</p>` +
    placesHtml +
    eventsHtml +
    `<h2>${esc("מה אפשר למצוא")}</h2>` +
    `<ul><li>${esc("פארקים וגני שעשועים")}</li><li>${esc("חופים ופארקי מים")}</li>` +
    `<li>${esc("מוזיאונים, גני חיות ואקווריומים")}</li><li>${esc("טבע ומעיינות")}</li>` +
    `<li>${esc("הצגות ילדים ואירועים עירוניים")}</li></ul>` +
    `<nav>${cities.filter((o) => o.slug !== c.slug).map((o) => `<a href="/${o.slug}/">${esc(o.he)}</a>`).join(" · ")}</nav>` +
    `</main></div>`;

  return template
    .replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
    .replace(/<meta name="description" content="[^"]*"\s*\/?>/, `<meta name="description" content="${esc(desc)}"/>`)
    .replace(/<meta property="og:title" content="[^"]*"\s*\/?>/, `<meta property="og:title" content="${esc(title)}"/>`)
    .replace(/<meta property="og:description" content="[^"]*"\s*\/?>/, `<meta property="og:description" content="${esc(desc)}"/>`)
    .replace(/<meta property="og:url" content="[^"]*"\s*\/?>/, `<meta property="og:url" content="${url}"/>`)
    .replace(/<link rel="canonical" href="[^"]*"\s*\/?>/, `<link rel="canonical" href="${url}"/>`)
    .replace("</head>", `${events.map(eventJsonLd).join("")}</head>`)
    .replace(/<div id="root"><\/div>/, body);
}

async function loadData() {
  const empty = { curated: [], events: {} };
  if (!API) {
    console.warn("prerender: no backend URL, city pages get generic content only");
    return empty;
  }
  try {
    await getJson(`${API}/api/health`, 90000); // the free Render backend may be asleep
    const curated = await getJson(`${API}/api/curated`, 30000)
      .then((d) => d.activities || [])
      .catch((e) => { console.warn(`prerender: curated places failed: ${e.message}`); return []; });
    const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jerusalem" });
    const events = {};
    for (const c of cities) {
      try {
        const q = `lat=${c.lat}&lng=${c.lng}&radius_km=${EVENTS_RADIUS_KM}&family_only=true`;
        const d = await getJson(`${API}/api/events?${q}`, 60000);
        events[c.slug] = (d.events || []).filter((e) => (e.end_date || e.date) >= today).slice(0, MAX_EVENTS);
      } catch (e) {
        console.warn(`prerender: events for ${c.slug} failed: ${e.message}`);
        events[c.slug] = [];
      }
    }
    return { curated, events };
  } catch (e) {
    console.warn(`prerender: backend unavailable (${e.message}), generic content only`);
    return empty;
  }
}

async function main() {
  const template = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");
  const { curated, events } = await loadData();

  let nEvents = 0;
  for (const c of cities) {
    const places = curated
      .filter((p) => p.lat != null && km(c, p) <= PLACES_RADIUS_KM)
      .sort((a, b) => km(c, a) - km(c, b));
    const evs = events[c.slug] || [];
    nEvents += evs.length;
    const dir = path.join(BUILD, c.slug);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "index.html"), cityPage(template, c, places, evs));
  }

  const today = new Date().toISOString().slice(0, 10);
  const urls = [`${SITE}/`, ...cities.map((c) => `${SITE}/${c.slug}/`)];
  fs.writeFileSync(
    path.join(BUILD, "sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
      urls.map((u) => `  <url><loc>${u}</loc><lastmod>${today}</lastmod><changefreq>daily</changefreq></url>`).join("\n") +
      `\n</urlset>\n`
  );
  fs.writeFileSync(path.join(BUILD, "robots.txt"), `User-agent: *\nAllow: /\nSitemap: ${SITE}/sitemap.xml\n`);
  console.log(`prerendered ${cities.length} city pages (${curated.length} curated places, ${nEvents} events) + sitemap.xml + robots.txt`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
