/* Landing page: list every hackathon from data/hackathons.json. */
(async function () {
  const grid = document.getElementById("hacks");
  grid.innerHTML = '<div class="loading">Loading hackathons…</div>';
  try {
    const res = await fetch("data/hackathons.json", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    const configured = data.hackathons || [];
    // The crawler writes each gallery independently while it is running.  Do
    // not make the landing page wait for the end-of-run manifest update: use
    // the gallery file itself as the source of truth for its live count.
    const hs = await Promise.all(
      configured.map(async (h) => {
        try {
          const gallery = await fetch("data/" + encodeURIComponent(h.slug) + ".json", { cache: "no-store" });
          if (!gallery.ok) return h;
          const live = await gallery.json();
          return {
            ...h,
            count: Array.isArray(live.projects) ? live.projects.length : (live.count || h.count || 0),
            generated_at: live.generated_at || h.generated_at,
          };
        } catch (_) {
          // The configured manifest remains a safe fallback if a gallery is
          // temporarily unavailable during a local write or deployment.
          return h;
        }
      })
    );
    if (hs.length === 0) {
      grid.innerHTML = '<div class="loading">No hackathons configured yet.</div>';
      return;
    }
    grid.innerHTML = hs
      .map((h) => {
        const slug = encodeURIComponent(h.slug);
        const name = escapeHtml(h.name || h.slug);
        const count = h.count || 0;
        const cats = (h.categories || []).length;
        const updated = h.generated_at
          ? new Date(h.generated_at).toUTCString().replace("GMT", "UTC")
          : "not yet scraped";
        return (
          '<a class="card hack-card" href="gallery.html?h=' + slug + '">' +
          '<div class="card-cover" style="background:' + coverGradient(h.slug || h.name) + '"></div>' +
          "<div class=\"card-body\">" +
          "<h3>" + name + "</h3>" +
          '<div class="meta">' +
          '<div class="stat-row"><span class="num">' + count + '</span><span class="lbl">projects</span></div>' +
          '<div class="muted">' + cats + " track labels · updated " + updated + "</div>" +
          '<span class="go">Open gallery →</span>' +
          "</div>" +
          "</div>" +
          "</a>"
        );
      })
      .join("");
    revealCards(grid);
  } catch (err) {
    grid.innerHTML = '<div class="loading">Could not load hackathon list.</div>';
  }
})();
