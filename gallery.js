/* Per-hackathon gallery: reads ?h=<slug>, loads data/<slug>.json, renders cards. */
(async function () {
  const grid = document.getElementById("projects");
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
    const uncategorized = projects.filter((p) => !p.category).length;
    const availableCategories = categories.filter((c) => projects.some((p) => p.category === c));
    const chips = [
      '<button class="chip active" type="button" aria-pressed="true" data-cat="all">All projects<span class="chip-count">' + projects.length + "</span></button>",
    ].concat(
      availableCategories.map((c) => {
        const n = projects.filter((p) => p.category === c).length;
        return (
          '<button class="chip" type="button" aria-pressed="false" data-cat="' + escapeHtml(c) + '">' +
          escapeHtml(c) + '<span class="chip-count">' + n + "</span></button>"
        );
      })
    );
    if (uncategorized) {
      chips.push('<button class="chip" type="button" aria-pressed="false" data-cat="__uncategorized">Unclassified<span class="chip-count">' + uncategorized + "</span></button>");
    }
    filtersEl.innerHTML = chips.join("");
    const note = document.getElementById("filter-note");
    if (note) note.textContent = uncategorized
      ? "Track labels are not published consistently on public project pages yet."
      : "Track labels are inferred from public project descriptions and may be revised.";
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
      if (activeCat === "__uncategorized" && p.category) return false;
      if (activeCat !== "all" && activeCat !== "__uncategorized" && p.category !== activeCat) return false;
      if (!q) return true;
      const hay = [p.title, p.description, p.tagline, p.category, ...cleanMembers(p.members).map((m) => m.name || m.handle)]
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
    [...filtersEl.children].forEach((c) => c.setAttribute("aria-pressed", String(c === btn)));
    apply();
  });

  grid.innerHTML = '<div class="loading">Loading projects…</div>';
  try {
    const [res, classificationRes, supplementalRes] = await Promise.all([
      fetch("data/" + encodeURIComponent(slug) + ".json", { cache: "no-store" }),
      // Labels are published independently of the long-running crawler, so a
      // crawler checkpoint can never erase an already reviewed category.
      fetch("data/" + encodeURIComponent(slug) + "-classifications.json", { cache: "no-store" }),
      // Directly verified omissions are published here immediately; the main
      // crawler can discover them later without creating duplicate cards.
      fetch("data/" + encodeURIComponent(slug) + "-supplemental-projects.json", { cache: "no-store" }),
    ]);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    let labels = {};
    if (classificationRes.ok) {
      const classificationData = await classificationRes.json();
      labels = classificationData.labels || {};
    }
    let supplemental = [];
    if (supplementalRes.ok) {
      const supplementalData = await supplementalRes.json();
      supplemental = supplementalData.projects || [];
    }
    const projectBySlug = new Map();
    [...(data.projects || []), ...supplemental].forEach((project) => {
      if (project && project.slug && !projectBySlug.has(project.slug)) projectBySlug.set(project.slug, project);
    });
    projects = [...projectBySlug.values()].map((project) => {
      const label = labels[project.slug];
      // Legacy crawler guesses are deliberately not displayed. A track is
      // shown only after the separate classification pipeline validates it.
      return label
        ? { ...project, category: label.category, classification_confidence: label.confidence }
        : { ...project, category: null };
    });
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
