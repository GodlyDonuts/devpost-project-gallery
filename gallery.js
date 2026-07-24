/* Per-hackathon gallery: reads ?h=<slug>, loads data/<slug>.json, renders cards. */
(async function () {
  const grid = document.getElementById("grid");
  const emptyEl = document.getElementById("empty");
  const searchEl = document.getElementById("search");
  const filtersEl = document.getElementById("filters");
  const titleEl = document.getElementById("hack-title");
  const freshEl = document.getElementById("freshness");

  const params = new URLSearchParams(location.search);
  const slug = params.get("h");
  if (!slug) {
    location.href = "index.html";
    return;
  }

  let projects = [];
  let categories = [];
  let activeCat = "all";
  let query = "";

  function renderChips() {
    const chips = [
      '<button class="chip active" data-cat="all">All<span class="chip-count">' + projects.length + "</span></button>",
    ].concat(
      categories.map((c) => {
        const n = projects.filter((p) => p.category === c).length;
        return (
          '<button class="chip" data-cat="' + escapeHtml(c) + '">' +
          escapeHtml(c) + '<span class="chip-count">' + n + "</span></button>"
        );
      })
    );
    filtersEl.innerHTML = chips.join("");
  }

  function renderStats(shown) {
    const statsEl = document.getElementById("stats");
    if (!statsEl) return;
    statsEl.innerHTML =
      '<div class="stat"><span class="num">' + projects.length + '</span><span class="lbl">Projects</span></div>' +
      '<div class="stat"><span class="num">' + shown + '</span><span class="lbl">Showing</span></div>';
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
    grid.innerHTML = filtered.map(projectCard).join("");
    emptyEl.hidden = filtered.length > 0;
    revealCards(grid);
    renderStats(filtered.length);
  }

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

  grid.innerHTML = '<div class="loading">Loading projects…</div>';
  try {
    const res = await fetch("data/" + encodeURIComponent(slug) + ".json", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    projects = data.projects || [];
    categories = data.categories || [];
    if (titleEl) titleEl.textContent = data.name || slug;
    if (freshEl && data.generated_at)
      freshEl.textContent = "Last updated " + new Date(data.generated_at).toUTCString().replace("GMT", "UTC");

    renderChips();
    if (projects.length === 0) {
      grid.innerHTML =
        '<div class="loading">No projects collected yet. The scraper runs on a schedule and backfills once the official gallery publishes.</div>';
      renderStats(0);
      return;
    }
    apply();
  } catch (err) {
    grid.innerHTML =
      '<div class="loading">Could not load data for "' + escapeHtml(slug) + '".</div>';
  }
})();
