// Privacy-friendly usage stats with GoatCounter (no cookies, no personal data,
// no consent banner needed). Enabled only when REACT_APP_GOATCOUNTER is set at
// build time, e.g. "sababakids" for https://sababakids.goatcounter.com.
const CODE = process.env.REACT_APP_GOATCOUNTER;

export function initAnalytics() {
  if (!CODE || typeof document === "undefined") return;
  const s = document.createElement("script");
  s.async = true;
  s.src = "https://gc.zgo.at/count.js";
  s.dataset.goatcounter = `https://${CODE}.goatcounter.com/count`;
  document.head.appendChild(s);
}

// Count a custom event, e.g. track("search", "category-park").
export function track(kind, label) {
  if (!CODE) return;
  try {
    window.goatcounter?.count?.({ path: `${kind}/${label}`, title: kind, event: true });
  } catch {}
}
