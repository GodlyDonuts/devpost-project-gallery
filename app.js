/* OpenAI Build Week — Community Project Gallery
 * Loads data/projects.json (produced by scrape.py) and renders filterable cards.
 */
(async function () {
  const grid = document.getElementById("grid");
  const emptyEl = document.getElementById("empty");
  const searchEl = document.getElementById("search");
  const filtersEl = document.getElementById("filters");
  const statsEl = document.getElementById("stats");
  const freshEl = document.getElementById("freshness");

  let projects = [];
  let activeCat = "all";
  let query = "";

  const CATEGORY_ORDER = [
    "Apps for Your Life",
    "Work & Productivity",
    "Developer Tools",
    "Education",
  ];

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function categoryClass(cat) {
    return "c" + CATEGORY_ORDER.indexOf(cat); // -1 if unknown
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

  function cardHtml(p) {
    const title = escapeHtml(p.title || "Untitled");
    const slug = p.slug || "";
    const url = p.url || (slug ? "https://devpost.com/software/" + slug : "#");
    const desc = escapeHtml(p.description || p.tagline || "");
    const cat = p.category || "Uncategorized";
    const links = [];
    if (url && url !== "#") links.push('<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">Devpost ↗</a>');
    if (p.repo_url) links.push('<a href="' + escapeHtml(p.repo_url) + '" target="_blank" rel="noopener">Code ↗</a>');
    if (p.demo_url) links.push('<a href="' + escapeHtml(p.demo_url) + '" target="_blank" rel="noopener">Demo ↗</a>');

    return (
      '<article class="card">' +
      '<span class="tag">' + escapeHtml(cat) + "</span>" +
      "<h3><a href=\"" + escapeHtml(url) + '" target="_blank" rel="noopener">' + title + "</a></h3>" +
      (desc ? '<p class="desc">' + desc + "</p>" : "") +
      '<div class="meta">' +
      teamLinks(p.members) +
      (links.length ? '<div class="links">' + links.join("") + "</div>" : "") +
      "</div>" +
      "</article>"
    );
  }

  function apply() {
    const q = query.trim().toLowerCase();
    const filtered = projects.filter((p) => {
      if (activeCat !== "all" && p.category !== activeCat) return false;
      if (!q) return true;
      const hay = [p.title, p.description, p.tagline, p.category, ...(p.members || []).map((m) => m.name || m.handle)]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });

    grid.innerHTML = filtered.map(cardHtml).join("");
    emptyEl.hidden = filtered.length > 0;
    renderStats(filtered.length);
  }

  function renderStats(shown) {
    const total = projects.length;
    statsEl.innerHTML =
      '<div class="stat"><span class="num">' + total + '</span><span class="lbl">Projects</span></div>' +
      '<div class="stat"><span class="num">' + shown + '</span><span class="lbl">Showing</span></div>';
  }

  // ---- events ----
  searchEl.addEventListener("input", (e) => {
    query = e.target.value;
    apply();
  });
  filtersEl.addEventListener("click", (e) => {
    const btn = e.target.closest(".chip");
    if (!btn) return;
    activeCat = btn.dataset.cat;
    [...filtersEl.children].forEach((c) => c.classList.toggle("active", c === btn));
    apply();
  });

  // ---- load ----
  grid.innerHTML = '<div class="loading">Loading projects…</div>';
  try {
    const res = await fetch("data/projects.json", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    projects = Array.isArray(data) ? data : data.projects || [];
    if (data.generated_at) {
      const d = new Date(data.generated_at);
      freshEl.textContent = "Last updated " + d.toUTCString().replace("GMT", "UTC");
    }
    if (projects.length === 0) {
      grid.innerHTML = '<div class="loading">No projects collected yet. The scraper runs on a schedule and backfills once the official gallery publishes.</div>';
      renderStats(0);
      return;
    }
    apply();
  } catch (err) {
    grid.innerHTML =
      '<div class="loading">Could not load project data (' + escapeHtml(err.message) +
      "). Run the scraper to generate <code>data/projects.json</code>.</div>";
  }
})();
