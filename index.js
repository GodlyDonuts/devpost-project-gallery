/* Landing page: list every hackathon from data/hackathons.json. */
(async function () {
  const grid = document.getElementById("hacks");
  grid.innerHTML = '<div class="loading">Loading hackathons…</div>';
  try {
    const res = await fetch("data/hackathons.json", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    const hs = data.hackathons || [];
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
          '<div class="muted">' + cats + " categories · updated " + updated + "</div>" +
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
