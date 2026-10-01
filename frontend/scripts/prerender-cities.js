/**
 * Post-build SEO step: one static page per city (/haifa/index.html, ...) with its
 * own title, description, canonical URL and readable content, plus sitemap.xml.
 * The React app then boots on that page and opens the matching city.
 *
 * Run automatically by `yarn build` (see package.json).
 */
const fs = require("fs");
const path = require("path");

const SITE = (process.env.PUBLIC_SITE_URL || "https://sababakids.onrender.com").replace(/\/$/, "");
const BUILD = path.join(__dirname, "..", "build");
const cities = require("../src/lib/cities.json");

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const template = fs.readFileSync(path.join(BUILD, "index.html"), "utf8");

function cityPage(c) {
  const title = `פעילויות ואירועים לילדים ב${c.he} | Activités enfants à ${c.fr} | SababaKids`;
  const desc =
    `פארקים, חופים, מוזיאונים, מעיינות, הצגות ואירועים לילדים ב${c.he} ובסביבה. ` +
    `Parcs, plages, musées, spectacles et événements pour enfants à ${c.fr}. ` +
    `Kids activities and family events in ${c.en}.`;
  const url = `${SITE}/${c.slug}/`;
  const body =
    `<div id="root"><main style="max-width:720px;margin:40px auto;padding:0 16px;font-family:sans-serif">` +
    `<h1>${esc(`פעילויות לילדים ב${c.he}`)}</h1>` +
    `<p>${esc(desc)}</p>` +
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
    .replace(/<div id="root"><\/div>/, body);
}

for (const c of cities) {
  const dir = path.join(BUILD, c.slug);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "index.html"), cityPage(c));
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
console.log(`prerendered ${cities.length} city pages + sitemap.xml + robots.txt`);
