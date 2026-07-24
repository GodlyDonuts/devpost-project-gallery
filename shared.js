/* Shared helpers for the hackathon gallery (landing + per-hackathon pages). */

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/* ---- liquid-glass palette helpers ---- */
const GLASS_PALETTE = [
  ["#2f6bff", "#00c6b8"],
  ["#7c3aed", "#ec4899"],
  ["#0ea5e9", "#22d3ee"],
  ["#f59e0b", "#ef4444"],
  ["#10b981", "#84cc16"],
  ["#6366f1", "#a855f7"],
];
function _hash(str) {
  let h = 0;
  const s = String(str || "");
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}
function coverGradient(seed) {
  const [a, b] = GLASS_PALETTE[_hash(seed) % GLASS_PALETTE.length];
  const angle = 110 + (_hash(seed + "x") % 80);
  return `linear-gradient(${angle}deg, ${a}, ${b})`;
}
function avatarColor(name) {
  return GLASS_PALETTE[_hash(name) % GLASS_PALETTE.length][0];
}
function initials(name) {
  const parts = String(name).trim().split(/\s+/).slice(0, 2);
  return (parts.map((p) => p[0] || "").join("") || "?").toUpperCase();
}

/* avatar stack for a project's members */
function teamBlock(members) {
  if (!Array.isArray(members) || members.length === 0)
    return '<div class="team"><span class="names">Solo project</span></div>';
  const shown = members.slice(0, 3);
  const extra = members.length - shown.length;
  const avatars = shown
    .map((m) => {
      const name = m.name || m.handle || "?";
      return `<span class="avatar" style="background:${avatarColor(name)}" title="${escapeHtml(name)}">${initials(name)}</span>`;
    })
    .join("");
  const more = extra > 0 ? `<span class="avatar more">+${extra}</span>` : "";
  const names =
    members.slice(0, 2).map((m) => escapeHtml(m.name || m.handle || "?")).join(", ") +
    (extra > 0 ? ` +${extra}` : "");
  return `<div class="team"><div class="avatars">${avatars}${more}</div><span class="names">${names}</span></div>`;
}

/* shared project card — glassy, with cover gradient + avatar stack */
function projectCard(p) {
  const title = p.title || "Untitled";
  const slug = p.slug || "";
  const url = p.url || (slug ? "https://devpost.com/software/" + slug : "#");
  const desc = escapeHtml(p.description || p.tagline || "");
  const cat = p.category || "Uncategorized";
  const links = [];
  if (url && url !== "#")
    links.push('<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">Devpost ↗</a>');
  if (p.repo_url)
    links.push('<a href="' + escapeHtml(p.repo_url) + '" target="_blank" rel="noopener">Code ↗</a>');
  if (p.demo_url)
    links.push('<a href="' + escapeHtml(p.demo_url) + '" target="_blank" rel="noopener">Demo ↗</a>');

  const seed = slug || title;
  const coverEl = p.image
    ? '<div class="card-cover"><img class="card-thumb" src="' +
      escapeHtml(p.image) +
      '" alt="' +
      escapeHtml(title) +
      '" loading="lazy" onerror="this.closest(\'.card-cover\').classList.add(\'no-img\')" /></div>'
    : '<div class="card-cover" style="background:' + coverGradient(seed) + '"></div>';

  return (
    '<article class="card">' +
    coverEl +
    '<div class="card-body">' +
    '<span class="tag">' + escapeHtml(cat) + "</span>" +
    '<h3><a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">' + escapeHtml(title) + "</a></h3>" +
    (desc ? '<p class="desc">' + desc + "</p>" : "") +
    teamBlock(p.members) +
    (links.length ? '<div class="links">' + links.join("") + "</div>" : "") +
    "</div>" +
    "</article>"
  );
}

/* scroll-reveal: add .in to cards as they enter viewport, staggered */
let _revealObserver = null;
function revealCards(container) {
  const cards = container ? container.querySelectorAll(".card") : [];
  if (!("IntersectionObserver" in window) || cards.length === 0) {
    cards.forEach((c) => c.classList.add("in"));
    return;
  }
  if (_revealObserver) _revealObserver.disconnect();
  _revealObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          const idx = [...e.target.parentNode.children].indexOf(e.target);
          e.target.style.transitionDelay = (idx % 12) * 35 + "ms";
          e.target.classList.add("in");
          _revealObserver.unobserve(e.target);
        }
      });
    },
    { rootMargin: "0px 0px -8% 0px", threshold: 0.05 }
  );
  cards.forEach((c) => _revealObserver.observe(c));
}
