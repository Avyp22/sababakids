/**
 * Post-build SEO step. Writes static pages that search engines can read without
 * running JavaScript, plus sitemap.xml and robots.txt:
 *   /<city>/              one page per city (the app then opens on that city)
 *   /<city>/<category>/   city x category ("parks in Haifa"), app opens filtered
 *   /events/<id>/         one standalone page per upcoming family event
 *
 * When the backend answers, pages list the curated places near the city and the
 * upcoming family events, with schema.org Event data. Live Google results are not
 * written into the pages (Google's terms forbid storing them): the app loads them
 * on top. If the backend is down the pages are still built with generic content.
 *
 * Run automatically by the build (see package.json).
 */
const fs = require("fs");
const path = require("path");

const SITE = (process.env.PUBLIC_SITE_URL || "https://sababakids.onrender.com").replace(/\/$/, "");
const API = (process.env.REACT_APP_BACKEND_URL || process.env.VITE_BACKEND_URL || "").replace(/\/$/, "");
const BUILD = path.join(__dirname, "..", "build");
const cities = require("../src/lib/cities.json");
const categories = require("../src/lib/seo-categories.json");

const PLACES_RADIUS_KM = 25;
const EVENTS_RADIUS_KM = 20;
const MAX_EVENTS = 15;

const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const fill = (s, c) => s.replace(/\{city\}/g, c.he);
const catsFor = (c) => categories.filter((k) => !k.coastal || c.coastal);
const eventSlug = (ev) => String(ev.id).replace(/[^A-Za-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
const eventPath = (ev) => `/events/${eventSlug(ev)}/`;

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

const HE_DATE = new Intl.DateTimeFormat("he-IL", { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" });
const heDate = (iso) => HE_DATE.format(new Date(`${iso}T12:00:00Z`));
const whenText = (ev) =>
  `${heDate(ev.date)}${ev.end_date && ev.end_date !== ev.date ? ` – ${heDate(ev.end_date)}` : ""}${ev.time ? `, ${ev.time}` : ""}`;

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
    url: `${SITE}${eventPath(ev)}`,
    location: {
      "@type": "Place",
      name: ev.venue || ev.city,
      address: { "@type": "PostalAddress", addressLocality: ev.city || undefined, addressCountry: "IL" },
    },
  };
  if (ev.end_date) data.endDate = ev.end_date;
  if (ev.image) data.image = [ev.image];
  if (ev.description) data.description = ev.description;
  if (ev.family) data.typicalAgeRange = "2-12";
  // "</" inside a JSON string would close the <script> tag.
  return `<script type="application/ld+json">${JSON.stringify(data).replace(/</g, "\\u003c")}</script>`;
}

// ---------- Pages built from the app's index.html (the app boots on top) ----------

function withHead(template, { title, desc, url, extraHead = "" }) {
  return template
    .replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
    .replace(/<meta name="description" content="[^"]*"\s*\/?>/, `<meta name="description" content="${esc(desc)}"/>`)
    .replace(/<meta property="og:title" content="[^"]*"\s*\/?>/, `<meta property="og:title" content="${esc(title)}"/>`)
    .replace(/<meta property="og:description" content="[^"]*"\s*\/?>/, `<meta property="og:description" content="${esc(desc)}"/>`)
    .replace(/<meta property="og:url" content="[^"]*"\s*\/?>/, `<meta property="og:url" content="${url}"/>`)
    .replace(/<link rel="canonical" href="[^"]*"\s*\/?>/, `<link rel="canonical" href="${url}"/>`)
    .replace("</head>", `${extraHead}</head>`);
}

const shell = (inner) =>
  `<div id="root"><main style="max-width:720px;margin:40px auto;padding:0 16px;font-family:sans-serif">${inner}</main></div>`;

const placesList = (title, places) =>
  places.length
    ? `<h2>${esc(title)}</h2><ul>` +
      places.map((p) => `<li><strong>${esc(p.name)}</strong> (${esc(p.city)}) — ${esc(p.description)}</li>`).join("") +
      `</ul>`
    : "";

const eventsList = (title, events) =>
  events.length
    ? `<h2>${esc(title)}</h2><ul>` +
      events.map((e) => `<li><a href="${eventPath(e)}"><strong>${esc(e.name)}</strong></a> — ${esc(whenText(e))}` +
        `${e.venue ? `, ${esc(e.venue)}` : ""}</li>`).join("") +
      `</ul>`
    : "";

function cityPage(template, c, places, events) {
  const title = `פעילויות ואירועים לילדים ב${c.he} | SababaKids`;
  const desc =
    `פארקים, חופים, מוזיאונים, מעיינות, הצגות ואירועים לילדים ב${c.he} ובסביבה, לפי מרחק מכם. ` +
    `Activités et événements pour enfants à ${c.fr}. Kids activities in ${c.en}.`;
  const inner =
    `<h1>${esc(`פעילויות לילדים ב${c.he}`)}</h1><p>${esc(desc)}</p>` +
    `<h2>${esc(`לפי סוג ב${c.he}`)}</h2><ul>` +
    catsFor(c).map((k) => `<li><a href="/${c.slug}/${k.slug}/">${esc(`${k.he} ב${c.he}`)}</a></li>`).join("") + `</ul>` +
    placesList(`מקומות מומלצים ב${c.he} ובסביבה`, places) +
    eventsList(`אירועים קרובים לילדים ב${c.he}`, events) +
    `<nav>${cities.filter((o) => o.slug !== c.slug).map((o) => `<a href="/${o.slug}/">${esc(o.he)}</a>`).join(" · ")}</nav>`;
  return withHead(template, { title, desc, url: `${SITE}/${c.slug}/`, extraHead: events.map(eventJsonLd).join("") })
    .replace(/<div id="root"><\/div>/, shell(inner));
}

function categoryPage(template, c, k, places) {
  const title = `${k.he} ב${c.he} לילדים | SababaKids`;
  const desc = `${fill(k.intro, c)} ${k.fr} à ${c.fr} · ${k.en} in ${c.en}.`;
  const inner =
    `<h1>${esc(`${k.he} ב${c.he}`)}</h1><p>${esc(fill(k.intro, c))}</p>` +
    `<p>${esc("הרשימה המלאה מוצגת לפי מרחק, עם שעות פתיחה, דירוג וניווט ב-Waze או Google Maps.")}</p>` +
    placesList(`${k.he} מומלצים ב${c.he} ובסביבה`, places) +
    `<h2>${esc(`עוד ב${c.he}`)}</h2><ul>` +
    `<li><a href="/${c.slug}/">${esc(`כל הפעילויות לילדים ב${c.he}`)}</a></li>` +
    catsFor(c).filter((o) => o.id !== k.id).map((o) => `<li><a href="/${c.slug}/${o.slug}/">${esc(`${o.he} ב${c.he}`)}</a></li>`).join("") +
    `</ul><nav>${cities.filter((o) => o.slug !== c.slug && (!k.coastal || o.coastal))
      .map((o) => `<a href="/${o.slug}/${k.slug}/">${esc(`${k.he} ב${o.he}`)}</a>`).join(" · ")}</nav>`;
  return withHead(template, { title, desc, url: `${SITE}/${c.slug}/${k.slug}/` })
    .replace(/<div id="root"><\/div>/, shell(inner));
}

// ---------- Standalone event pages (no app: fast, shareable on WhatsApp) ----------

function eventPage(ev, city) {
  const url = `${SITE}${eventPath(ev)}`;
  const title = `${ev.name} — ${whenText(ev)} | SababaKids`;
  const desc = `${ev.name}: ${whenText(ev)}${ev.venue ? `, ${ev.venue}` : ""}${ev.city ? `, ${ev.city}` : ""}. ` +
    (ev.description && ev.description !== ev.venue ? ev.description : "אירוע לילדים ולמשפחות.");
  const dir = ev.rtl === false ? "ltr" : "rtl";
  const back = city
    ? `<a href="/${city.slug}/">${esc(`כל האירועים והפעילויות לילדים ב${city.he}`)}</a>`
    : `<a href="/">${esc("כל הפעילויות לילדים")}</a>`;
  return `<!doctype html>
<html lang="he" dir="${dir}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="theme-color" content="#E05A47"/>
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc.slice(0, 300))}"/>
<link rel="canonical" href="${url}"/>
<link rel="icon" href="/favicon.ico" sizes="48x48"/>
<meta property="og:type" content="article"/>
<meta property="og:site_name" content="SababaKids"/>
<meta property="og:title" content="${esc(ev.name)}"/>
<meta property="og:description" content="${esc(desc.slice(0, 300))}"/>
<meta property="og:url" content="${url}"/>
<meta property="og:image" content="${esc(ev.image || `${SITE}/og-image.png`)}"/>
<meta name="twitter:card" content="summary_large_image"/>
${eventJsonLd(ev)}
<style>
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#FBF8F3;color:#1f2937;line-height:1.5}
main{max-width:640px;margin:0 auto;padding:20px 16px 48px}
header a{color:#E05A47;font-weight:800;text-decoration:none;font-size:20px}
img{width:100%;border-radius:20px;margin:16px 0;aspect-ratio:16/10;object-fit:cover;background:#eee}
h1{font-size:26px;line-height:1.25;margin:16px 0 8px}
.meta{color:#4b5563;margin:4px 0}
.btn{display:inline-block;margin:16px 8px 0 0;padding:12px 18px;border-radius:14px;background:#E05A47;color:#fff;text-decoration:none;font-weight:700}
.btn.alt{background:#fff;color:#1f2937;border:1px solid #e5e7eb}
footer{margin-top:32px;font-size:14px}
footer a{color:#E05A47}
@media (prefers-color-scheme:dark){body{background:#151311;color:#f3f4f6}.meta{color:#9ca3af}.btn.alt{background:#262320;color:#f3f4f6;border-color:#3f3a35}}
</style>
</head>
<body>
<main>
<header><a href="/">SababaKids</a></header>
${ev.image ? `<img src="${esc(ev.image)}" alt="${esc(ev.name)}"/>` : ""}
<h1>${esc(ev.name)}</h1>
<p class="meta">📅 ${esc(whenText(ev))}</p>
${ev.venue || ev.city ? `<p class="meta">📍 ${esc([ev.venue, ev.city].filter(Boolean).join(", "))}</p>` : ""}
${ev.price_text ? `<p class="meta">🎟️ ${esc(ev.price_text)}</p>` : ""}
${ev.description && ev.description !== ev.venue ? `<p>${esc(ev.description)}</p>` : ""}
${ev.ticket_url ? `<a class="btn" href="${esc(ev.ticket_url)}" rel="nofollow noopener">${esc("פרטים והרשמה")}</a>` : ""}
<a class="btn alt" href="https://wa.me/?text=${encodeURIComponent(`${ev.name} — ${whenText(ev)}\n${url}`)}">${esc("שיתוף בוואטסאפ")}</a>
<footer><p>${back}</p><p>${esc(`מקור: ${ev.source || ""}`)}</p></footer>
</main>
</body>
</html>
`;
}

// ---------- Data ----------

async function loadData() {
  const empty = { curated: [], events: {} };
  if (!API) {
    console.warn("prerender: no backend URL, pages get generic content only");
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

function write(relDir, html) {
  const dir = path.join(BUILD, relDir);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "index.html"), html);
}

async function main() {
  const template = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");
  const { curated, events } = await loadData();
  const urls = [`${SITE}/`];
  const eventPages = new Map(); // slug -> [event, city it was listed under]

  for (const c of cities) {
    const near = curated
      .filter((p) => p.lat != null && km(c, p) <= PLACES_RADIUS_KM)
      .sort((a, b) => km(c, a) - km(c, b));
    const evs = events[c.slug] || [];
    write(c.slug, cityPage(template, c, near, evs));
    urls.push(`${SITE}/${c.slug}/`);
    for (const k of catsFor(c)) {
      write(path.join(c.slug, k.slug), categoryPage(template, c, k, near.filter((p) => p.category === k.id)));
      urls.push(`${SITE}/${c.slug}/${k.slug}/`);
    }
    for (const ev of evs) if (!eventPages.has(eventSlug(ev))) eventPages.set(eventSlug(ev), [ev, c]);
  }

  for (const [slug, [ev, c]] of eventPages) {
    write(path.join("events", slug), eventPage(ev, c));
    urls.push(`${SITE}/events/${slug}/`);
  }

  const today = new Date().toISOString().slice(0, 10);
  fs.writeFileSync(
    path.join(BUILD, "sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
      urls.map((u) => `  <url><loc>${u}</loc><lastmod>${today}</lastmod></url>`).join("\n") +
      `\n</urlset>\n`
  );
  fs.writeFileSync(path.join(BUILD, "robots.txt"), `User-agent: *\nAllow: /\nSitemap: ${SITE}/sitemap.xml\n`);
  console.log(`prerendered ${cities.length} city pages, ${urls.length - 1 - cities.length - eventPages.size} category pages, ` +
    `${eventPages.size} event pages (${curated.length} curated places) + sitemap.xml (${urls.length} URLs) + robots.txt`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
