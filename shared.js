/* Shared helpers for the hackathon gallery (landing + per-hackathon pages). */

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function teamLinks(members) {
  if (!Array.isArray(members) || members.length === 0) return "";
  return (
    '<div class="team">by ' +
    members
      .map((m) => {
        const name = escapeHtml(m.name || m.handle || "?");
        const url = m.url || (m.handle ? "https://devpost.com/" + m.handle : null);
        return url
          ? '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">' + name + "</a>"
          : "<span>" + name + "</span>";
      })
      .join(", ") +
    "</div>"
  );
}

function projectCard(p) {
  const title = escapeHtml(p.title || "Untitled");
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

  return (
    '<article class="card">' +
    '<span class="tag">' + escapeHtml(cat) + "</span>" +
    '<h3><a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">' + title + "</a></h3>" +
    (desc ? '<p class="desc">' + desc + "</p>" : "") +
    '<div class="meta">' +
    teamLinks(p.members) +
    (links.length ? '<div class="links">' + links.join("") + "</div>" : "") +
    "</div>" +
    "</article>"
  );
}
