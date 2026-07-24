/* Devpost Build Week — Liquid Glass gallery
 * Loads data/projects.json (from scrape.py). Falls back to demo data so the
 * gallery is never empty, then renders frosted cards with live filters.
 */
(async function () {
  const grid = document.getElementById("grid");
  const emptyEl = document.getElementById("empty");
  const searchEl = document.getElementById("search");
  const filtersEl = document.getElementById("filters");
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

  /* palette for category tags / covers */
  const PALETTE = [
    ["#2f6bff", "#00c6b8"],
    ["#7c3aed", "#ec4899"],
    ["#0ea5e9", "#22d3ee"],
    ["#f59e0b", "#ef4444"],
    ["#10b981", "#84cc16"],
    ["#6366f1", "#a855f7"],
  ];
  function hash(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
    return h;
  }
  function coverBg(seed) {
    const [a, b] = PALETTE[hash(seed) % PALETTE.length];
    const angle = 110 + (hash(seed + "x") % 80);
    return `linear-gradient(${angle}deg, ${a}, ${b})`;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function initials(name) {
    const parts = String(name).trim().split(/\s+/).slice(0, 2);
    return parts.map((p) => p[0] || "").join("").toUpperCase() || "?";
  }

  function teamBlock(members) {
    if (!Array.isArray(members) || members.length === 0)
      return '<div class="team"><span class="names">Solo project</span></div>';
    const shown = members.slice(0, 3);
    const extra = members.length - shown.length;
    const av = shown
      .map((m) => {
        const name = m.name || m.handle || "?";
        const [a] = PALETTE[hash(name) % PALETTE.length];
        return `<span class="avatar" style="background:${a}" title="${escapeHtml(name)}">${initials(name)}</span>`;
      })
      .join("");
    const more = extra > 0 ? `<span class="avatar more">+${extra}</span>` : "";
    const names = members
      .slice(0, 2)
      .map((m) => escapeHtml(m.name || m.handle || "?"))
      .join(", ") + (extra > 0 ? ` +${extra}` : "");
    return `<div class="team"><div class="avatars">${av}${more}</div><span class="names">${names}</span></div>`;
  }

  function cardHtml(p, i) {
    const title = p.title || "Untitled";
    const slug = p.slug || "";
    const url = p.url || (slug ? "https://devpost.com/software/" + slug : "#");
    const desc = p.description || p.tagline || "";
    const cat = p.category || "Uncategorized";
    const seed = slug || title;

    const links = [];
    if (url && url !== "#")
      links.push(`<a href="${escapeHtml(url)}" target="_blank" rel="noopener">Devpost ↗</a>`);
    if (p.repo_url)
      links.push(`<a href="${escapeHtml(p.repo_url)}" target="_blank" rel="noopener">Code ↗</a>`);
    if (p.demo_url)
      links.push(`<a href="${escapeHtml(p.demo_url)}" target="_blank" rel="noopener">Demo ↗</a>`);

    return (
      `<article class="card" style="--i:${i}">` +
      `<div class="card-cover" style="background:${coverBg(seed)}"></div>` +
      `<div class="card-body">` +
      `<span class="tag">${escapeHtml(cat)}</span>` +
      `<h3><a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(title)}</a></h3>` +
      (desc ? `<p class="desc">${escapeHtml(desc)}</p>` : "") +
      teamBlock(p.members) +
      (links.length ? `<div class="links">${links.join("")}</div>` : "") +
      `</div>` +
      `</article>`
    );
  }

  /* build filter chips dynamically from data */
  function buildFilters() {
    const counts = {};
    CATEGORY_ORDER.forEach((c) => (counts[c] = 0));
    projects.forEach((p) => {
      const c = p.category || "Uncategorized";
      counts[c] = (counts[c] || 0) + 1;
    });
    const cats = CATEGORY_ORDER.filter((c) => counts[c] > 0);
    // include any unexpected categories too
    Object.keys(counts).forEach((c) => {
      if (c !== "Uncategorized" && !cats.includes(c) && counts[c] > 0) cats.push(c);
    });

    const all = filtersEl.querySelector('[data-cat="all"]');
    all.querySelector("[data-count]").textContent = projects.length;

    cats.forEach((c) => {
      const btn = document.createElement("button");
      btn.className = "chip";
      btn.dataset.cat = c;
      btn.innerHTML = `${escapeHtml(c)}<span class="chip-count">${counts[c]}</span>`;
      filtersEl.appendChild(btn);
    });
  }

  function apply() {
    const q = query.trim().toLowerCase();
    const filtered = projects.filter((p) => {
      if (activeCat !== "all" && (p.category || "Uncategorized") !== activeCat) return false;
      if (!q) return true;
      const hay = [p.title, p.description, p.tagline, p.category, ...(p.members || []).map((m) => m.name || m.handle)]
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });

    grid.innerHTML = filtered.map((p, i) => cardHtml(p, i)).join("");
    emptyEl.hidden = filtered.length > 0;
    revealCards();
    renderStats(filtered.length);
  }

  function renderStats(shown) {
    document.querySelector('[data-stat="total"]').textContent = projects.length;
    document.querySelector('[data-stat="shown"]').textContent = shown;
  }

  /* scroll-reveal with stagger */
  let io;
  function revealCards() {
    if (!("IntersectionObserver" in window)) {
      grid.querySelectorAll(".card").forEach((c) => c.classList.add("in"));
      return;
    }
    if (io) io.disconnect();
    io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const idx = [...grid.children].indexOf(e.target);
            e.target.style.transitionDelay = (idx % 12) * 35 + "ms";
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 }
    );
    grid.querySelectorAll(".card").forEach((c) => io.observe(c));
  }

  /* ---- events ---- */
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

  /* ---- demo fallback so the gallery is never empty ---- */
  const DEMO = [
    {
      title: "Lumen — AI Reading Companion",
      slug: "lumen-ai-reading",
      category: "Education",
      description: "Turns any PDF into an adaptive, chat-driven study guide that quizzes you on the concepts you’re weakest at.",
      members: [{ name: "Maya Chen" }, { name: "Dev Patel" }],
      repo_url: "https://github.com/example/lumen",
      demo_url: "https://lumen.example.dev",
    },
    {
      title: "Cadence — Focus Timer for Deep Work",
      slug: "cadence-focus",
      category: "Apps for Your Life",
      description: "A liquid-glass pomodoro that scores your focus sessions and gently reschedules your day around your energy dips.",
      members: [{ name: "Sofia Reyes" }],
      demo_url: "https://cadence.example.dev",
    },
    {
      title: "Patchwork — AI Code Review Bot",
      slug: "patchwork-review",
      category: "Developer Tools",
      description: "Drops contextual, line-level review comments on every PR, catching bugs and suggesting tests before humans look.",
      members: [{ name: "Alex Kim" }, { name: "Jordan Lee" }, { name: "Priya Nair" }],
      repo_url: "https://github.com/example/patchwork",
    },
    {
      title: "Briefly — Meeting Notes That Write Themselves",
      slug: "briefly-notes",
      category: "Work & Productivity",
      description: "Joins your calls, drafts action items, and files them into the right project doc automatically.",
      members: [{ name: "Tomás García" }, { name: "Lena Müller" }],
      demo_url: "https://briefly.example.dev",
    },
    {
      title: "Recipeal — Snap a Fridge, Get Dinner",
      slug: "recipeal",
      category: "Apps for Your Life",
      description: "Photos your fridge and generates recipes you can actually cook, with a one-tap grocery list.",
      members: [{ name: "Hana Sato" }],
      repo_url: "https://github.com/example/recipeal",
    },
    {
      title: "Tutorly — 1:1 Math Tutor for Kids",
      slug: "tutorly",
      category: "Education",
      description: "A patient, voice-first tutor that adapts explanations to a child’s grade level and mood.",
      members: [{ name: "Omar Hassan" }, { name: "Ella Brooks" }],
      demo_url: "https://tutorly.example.dev",
    },
    {
      title: "Shipwright — Scaffold Apps from a Prompt",
      slug: "shipwright",
      category: "Developer Tools",
      description: "Describe the app you want and get a runnable full-stack repo with tests, CI, and a deploy button.",
      members: [{ name: "Nina Volkov" }, { name: "Sam O’Neil" }, { name: "Kai Tanaka" }],
      repo_url: "https://github.com/example/shipwright",
    },
    {
      title: "Flowstate — Team Standups Without the Meeting",
      slug: "flowstate",
      category: "Work & Productivity",
      description: "Async standups that summarize blockers and auto-ping the right person to unblock the team.",
      members: [{ name: "Ravi Menon" }],
      demo_url: "https://flowstate.example.dev",
    },
    {
      title: "Verba — Language Practice That Feels Real",
      slug: "verba",
      category: "Education",
      description: "Role-plays real-world conversations in 30 languages, correcting you mid-sentence like a native friend.",
      members: [{ name: "Yuki Mori" }, { name: "Carla Díaz" }],
      repo_url: "https://github.com/example/verba",
    },
    {
      title: "Pocket Chef — Healthy Meals on a Budget",
      slug: "pocket-chef",
      category: "Apps for Your Life",
      description: "Plans a week of cheap, healthy meals around what’s on sale at your local store.",
      members: [{ name: "Ben Carter" }, { name: "Aïsha Diallo" }],
      demo_url: "https://pocketchef.example.dev",
    },
    {
      title: "Lintlight — Instant API Docs from Code",
      slug: "lintlight",
      category: "Developer Tools",
      description: "Watches your repo and keeps your API docs in sync with the actual endpoints — no more stale READMEs.",
      members: [{ name: "Felix Wolf" }],
      repo_url: "https://github.com/example/lintlight",
    },
    {
      title: "Clarity — Summarize Long Docs in Seconds",
      slug: "clarity-docs",
      category: "Work & Productivity",
      description: "Drops a browser overlay that summarizes any page, thread, or PDF into a five-bullet brief.",
      members: [{ name: "Grace Liu" }, { name: "Diego Santos" }],
      demo_url: "https://clarity.example.dev",
    },
  ];

  /* ---- load ---- */
  grid.innerHTML = '<div class="loading">Loading projects…</div>';
  try {
    const res = await fetch("data/projects.json", { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    const loaded = Array.isArray(data) ? data : data.projects || [];
    if (loaded.length > 0) {
      projects = loaded;
      if (data.generated_at) {
        const d = new Date(data.generated_at);
        freshEl.textContent = "Last updated " + d.toUTCString().replace("GMT", "UTC");
      }
    } else {
      projects = DEMO;
      freshEl.textContent = "Showing demo projects — run the scraper to load live submissions.";
    }
  } catch (err) {
    projects = DEMO;
    freshEl.textContent = "Showing demo projects — run the scraper to load live submissions.";
  }

  buildFilters();
  apply();
})();
