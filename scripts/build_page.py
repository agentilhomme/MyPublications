#!/usr/bin/env python3
"""Build index.html: an interactive publications page with citation charts.

Usage:
    python -X utf8 scripts/build_page.py

Run from the repository root. Reads data/publications.json (see
fetch_publications.py), computes headline stats and per-year citation
series, and writes a single self-contained index.html (inline CSS/JS,
hand-rolled SVG charts, no external dependencies) per the design plan in
TODO-20260721-page.md.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "publications.json"
OUT_PATH = ROOT / "index.html"
IMAGES_DIR = ROOT / "images"
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")

TAGLINE = "Oceanographer with a focus in Microbiology, Extremophiles, Proteomic-based Mass Spectrometry, and Astrobiology"
BIO = (
    "I study how microorganisms survive and adapt in extreme "
    "environments — from cold-adapted bacteria in polar seas to "
    "psychrophiles growing under perchlorate-laced, subzero conditions "
    "relevant to the search for life on Mars. My work spans genomics and "
    "proteomics, using mass-spectrometry-based approaches to understand "
    "microbial adaptation in some of Earth's most extreme habitats."
)


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text)


def find_image(stem):
    """Return a relative path (as a URL) to images/<stem>.<ext> if it exists."""
    for ext in IMAGE_EXTS:
        candidate = IMAGES_DIR / f"{stem}{ext}"
        if candidate.exists():
            return f"images/{candidate.name}"
    return None


def find_gallery_images(prefix="fieldwork", max_count=6):
    if not IMAGES_DIR.exists():
        return []
    matches = sorted(
        p for p in IMAGES_DIR.iterdir()
        if p.suffix.lower() in IMAGE_EXTS and p.stem.startswith(prefix)
    )
    return [f"images/{p.name}" for p in matches[:max_count]]


def render_avatar_html():
    headshot = find_image("headshot")
    if headshot:
        return f'<img class="avatar-photo" src="{headshot}" alt="Anais S. Gentilhomme">'
    return (
        '<div class="avatar-placeholder" title="Drop a photo at images/headshot.jpg '
        'and rerun scripts/build_page.py">'
        '<span>📷</span></div>'
    )


def render_gallery_html():
    images = find_gallery_images()
    if images:
        items = "\n".join(
            f'<div class="gallery-item"><img src="{src}" alt="Fieldwork photo"></div>'
            for src in images
        )
        return f'<div class="gallery-grid">\n{items}\n</div>'

    placeholders = "\n".join(
        '<div class="gallery-item gallery-placeholder">'
        f'<span>📷</span><span class="gallery-hint">images/fieldwork-{i}.jpg</span></div>'
        for i in range(1, 4)
    )
    return f'<div class="gallery-grid">\n{placeholders}\n</div>'


def compute_h_index(citation_counts):
    counts = sorted(citation_counts, reverse=True)
    h = 0
    for i, c in enumerate(counts, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def build_year_series(works, min_year, max_year):
    years = list(range(min_year, max_year + 1))
    per_paper = []
    total_cumulative = {y: 0 for y in years}
    for w in works:
        counts = w.get("cited_by_count_by_year", {})
        cumulative = []
        running = 0
        for y in years:
            running += counts.get(str(y), 0)
            cumulative.append(running)
            total_cumulative[y] += counts.get(str(y), 0)
        per_paper.append(cumulative)

    running_total = 0
    total_series = []
    for y in years:
        running_total += total_cumulative[y]
        total_series.append(running_total)
    return years, per_paper, total_series


def main():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    works = sorted(data["works"], key=lambda w: (w["year"] or 0), reverse=True)

    citation_counts = [w["cited_by_count_total"] for w in works]
    total_citations = sum(citation_counts)
    paper_count = len(works)
    h_index = compute_h_index(citation_counts)
    most_cited = max(works, key=lambda w: w["cited_by_count_total"])

    pub_years = [w["year"] for w in works if w.get("year")]
    all_years_with_counts = set()
    for w in works:
        all_years_with_counts.update(int(y) for y in w.get("cited_by_count_by_year", {}))
    min_year = min(pub_years)
    max_year = max([*all_years_with_counts, *pub_years])

    years, per_paper_cumulative, total_series = build_year_series(works, min_year, max_year)

    papers_payload = []
    for w, cumulative in zip(works, per_paper_cumulative):
        papers_payload.append(
            {
                "id": f"p{w['year']}-{abs(hash(w['title'])) % 10000}",
                "title": strip_html(w["title"]),
                "year": w["year"],
                "venue": w["venue"],
                "type": w["type"],
                "link": w["link"],
                "authors": w.get("authors", []),
                "cited_by_count_total": w["cited_by_count_total"],
                "cumulative_by_year": cumulative,
            }
        )

    payload = {
        "years": years,
        "total_series": total_series,
        "papers": papers_payload,
        "stats": {
            "total_citations": total_citations,
            "paper_count": paper_count,
            "h_index": h_index,
            "most_cited": {
                "title": strip_html(most_cited["title"]),
                "year": most_cited["year"],
                "link": most_cited["link"],
                "count": most_cited["cited_by_count_total"],
            },
        },
        "tagline": TAGLINE,
        "bio": BIO,
        "name": "Anais S. Gentilhomme",
    }

    data_json = json.dumps(payload)
    html = (
        HTML_TEMPLATE
        .replace("__DATA_JSON__", data_json)
        .replace("__AVATAR_HTML__", render_avatar_html())
        .replace("__GALLERY_HTML__", render_gallery_html())
    )
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({len(papers_payload)} papers, {min_year}-{max_year})")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Anais S. Gentilhomme — Publications</title>
<style>
:root {
  color-scheme: light;
  --page-plane:      #f9f9f7;
  --surface-1:       #fcfcfb;
  --text-primary:    #0b0b0b;
  --text-secondary:  #52514e;
  --text-muted:      #898781;
  --gridline:        #e1e0d9;
  --baseline:        #c3c2b7;
  --border:          rgba(11,11,11,0.10);
  --accent:          #1baf7a;
  --accent-ink:      #0d8a5f;
  --series-1:        #2a78d6;
  --series-2:        #008300;
  --series-3:        #e87ba4;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --page-plane:      #0d0d0d;
  --surface-1:       #1a1a19;
  --text-primary:    #ffffff;
  --text-secondary:  #c3c2b7;
  --text-muted:      #898781;
  --gridline:        #2c2c2a;
  --baseline:        #383835;
  --border:          rgba(255,255,255,0.10);
  --accent:          #199e70;
  --accent-ink:      #4fd8a4;
  --series-1:        #3987e5;
  --series-2:        #008300;
  --series-3:        #d55181;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) {
    color-scheme: dark;
    --page-plane:      #0d0d0d;
    --surface-1:       #1a1a19;
    --text-primary:    #ffffff;
    --text-secondary:  #c3c2b7;
    --text-muted:      #898781;
    --gridline:        #2c2c2a;
    --baseline:        #383835;
    --border:          rgba(255,255,255,0.10);
    --accent:          #199e70;
    --accent-ink:      #4fd8a4;
    --series-1:        #3987e5;
    --series-2:        #008300;
    --series-3:        #d55181;
  }
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--page-plane);
  color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.5;
}
h1, h2, h3 { font-family: Georgia, "Times New Roman", serif; font-weight: 600; margin: 0 0 0.3em; }
a { color: var(--accent-ink); }
.tabular { font-variant-numeric: tabular-nums; }

.page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 2rem 1.5rem 4rem;
}

header.masthead {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
  margin-bottom: 2rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--border);
}
header.masthead .masthead-main {
  display: flex;
  align-items: flex-start;
  gap: 1.2rem;
}
header.masthead h1 { font-size: 1.9rem; }
header.masthead .tagline { color: var(--accent-ink); font-weight: 600; margin-bottom: 0.6em; }
header.masthead .bio { max-width: 62ch; color: var(--text-secondary); }

.avatar-photo, .avatar-placeholder {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  flex-shrink: 0;
  object-fit: cover;
}
.avatar-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-1);
  border: 1px dashed var(--border);
  font-size: 1.6rem;
  color: var(--text-muted);
}

section.gallery { margin-top: 2.5rem; }
section.gallery h2 { font-size: 1.2rem; margin-bottom: 1rem; }
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}
.gallery-item {
  aspect-ratio: 4 / 3;
  border-radius: 10px;
  overflow: hidden;
  background: var(--surface-1);
  border: 1px solid var(--border);
}
.gallery-item img { width: 100%; height: 100%; object-fit: cover; display: block; }
.gallery-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.4em;
  border-style: dashed;
  color: var(--text-muted);
  font-size: 1.8rem;
}
.gallery-hint { font-size: 0.7rem; font-family: system-ui, sans-serif; }

#theme-toggle {
  border: 1px solid var(--border);
  background: var(--surface-1);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 0.5rem 0.9rem;
  font-size: 0.85rem;
  cursor: pointer;
  white-space: nowrap;
}
#theme-toggle:hover { border-color: var(--accent); }

.layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 2rem;
  align-items: start;
}
@media (max-width: 820px) {
  .layout { grid-template-columns: 1fr; }
}

aside.sidebar {
  position: sticky;
  top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}
@media (max-width: 820px) {
  aside.sidebar { position: static; }
}

.card {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.1rem 1.2rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.9rem;
}
.stat-tile .stat-value {
  font-size: 1.7rem;
  font-weight: 600;
  color: var(--text-primary);
}
.stat-tile .stat-label {
  font-size: 0.78rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.most-cited {
  margin-top: 0.9rem;
  padding-top: 0.9rem;
  border-top: 1px solid var(--gridline);
}
.most-cited .stat-label { margin-bottom: 0.3em; }
.most-cited a { display: block; font-size: 0.92rem; color: var(--text-primary); text-decoration: none; }
.most-cited a:hover { color: var(--accent-ink); }
.most-cited .count { color: var(--accent-ink); font-weight: 600; }

.chart-card h3 { font-size: 0.95rem; margin-bottom: 0.2em; }
.chart-card .chart-sub { font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.6em; }

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem 1rem;
  margin: 0.6em 0 0.2em;
  font-size: 0.78rem;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 0.4em;
  cursor: pointer;
  color: var(--text-secondary);
  user-select: none;
  background: none;
  border: none;
  padding: 0;
  font: inherit;
}
.legend-item.off { opacity: 0.35; }
.legend-key { width: 14px; height: 2px; border-radius: 1px; display: inline-block; }

svg.chart { width: 100%; height: auto; display: block; overflow: visible; }
.gridline { stroke: var(--gridline); stroke-width: 1; }
.baseline { stroke: var(--baseline); stroke-width: 1; }
.axis-label { fill: var(--text-muted); font-size: 10px; font-family: system-ui, sans-serif; }
.chart-line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.chart-dot { r: 4; stroke-width: 2; }
.crosshair { stroke: var(--baseline); stroke-width: 1; opacity: 0; pointer-events: none; }
.hover-dot { r: 4; opacity: 0; pointer-events: none; }
.end-label { font-size: 11px; font-family: system-ui, sans-serif; font-weight: 600; }

#tooltip {
  position: fixed;
  pointer-events: none;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.5rem 0.7rem;
  font-size: 0.78rem;
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
  opacity: 0;
  transition: opacity 0.08s ease;
  z-index: 50;
  max-width: 220px;
}
#tooltip .tt-year { color: var(--text-muted); margin-bottom: 0.3em; }
#tooltip .tt-row { display: flex; align-items: center; gap: 0.4em; }
#tooltip .tt-key { width: 10px; height: 2px; display: inline-block; flex-shrink: 0; }
#tooltip .tt-value { font-weight: 700; color: var(--text-primary); }
#tooltip .tt-label { color: var(--text-secondary); }

section.papers h2 { font-size: 1.2rem; margin-bottom: 1rem; }

.paper-row {
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-left: 3px solid transparent;
  border-radius: 10px;
  padding: 1rem 1.15rem;
  margin-bottom: 0.9rem;
  display: grid;
  grid-template-columns: 1fr 130px;
  gap: 1rem;
  align-items: center;
  cursor: pointer;
  transition: border-color 0.1s ease;
}
.paper-row:hover { border-color: var(--accent); }
.paper-row.active { border-left-color: var(--row-color, var(--accent)); }
.paper-row .p-title { font-weight: 600; font-size: 1rem; margin-bottom: 0.25em; }
.paper-row .p-title a { color: var(--text-primary); text-decoration: none; }
.paper-row .p-title a:hover { color: var(--accent-ink); text-decoration: underline; }
.paper-row .p-meta { font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 0.3em; }
.badge {
  display: inline-block;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  background: var(--gridline);
  color: var(--text-secondary);
  border-radius: 4px;
  padding: 0.1em 0.5em;
  margin-right: 0.4em;
}
.paper-row .p-authors { font-size: 0.78rem; color: var(--text-muted); }
.paper-row .p-cites { font-size: 0.78rem; color: var(--text-muted); margin-top: 0.3em; }
.paper-row .p-cites .tabular { color: var(--accent-ink); font-weight: 700; font-size: 0.95rem; }
.sparkline-wrap { display: flex; align-items: center; justify-content: center; }

footer.page-footer {
  margin-top: 3rem;
  padding-top: 1.2rem;
  border-top: 1px solid var(--border);
  font-size: 0.78rem;
  color: var(--text-muted);
}
footer.page-footer a { color: var(--text-muted); }
</style>
</head>
<body>
<div class="page">

  <header class="masthead">
    <div class="masthead-main">
      __AVATAR_HTML__
      <div>
        <h1 id="author-name"></h1>
        <p class="tagline" id="author-tagline"></p>
        <p class="bio" id="author-bio"></p>
      </div>
    </div>
    <button id="theme-toggle" type="button" aria-label="Toggle dark mode">🌙 Dark mode</button>
  </header>

  <div class="layout">
    <aside class="sidebar">
      <div class="card">
        <div class="stats-grid">
          <div class="stat-tile">
            <div class="stat-value tabular" id="stat-total-citations"></div>
            <div class="stat-label">Total citations</div>
          </div>
          <div class="stat-tile">
            <div class="stat-value tabular" id="stat-paper-count"></div>
            <div class="stat-label">Papers</div>
          </div>
          <div class="stat-tile">
            <div class="stat-value tabular" id="stat-h-index"></div>
            <div class="stat-label">h-index</div>
          </div>
        </div>
        <div class="most-cited">
          <div class="stat-label">Most-cited paper</div>
          <a id="most-cited-link" href="#" target="_blank" rel="noopener"></a>
          <span class="count tabular" id="most-cited-count"></span>
        </div>
      </div>

      <div class="card chart-card">
        <h3>Cumulative citations</h3>
        <div class="chart-sub">Total citations across all papers, by year</div>
        <svg class="chart" id="chart-total" viewBox="0 0 320 160" preserveAspectRatio="xMidYMid meet"></svg>
      </div>

      <div class="card chart-card">
        <h3>Per-paper comparison</h3>
        <div class="chart-sub">Click a paper below to toggle its line</div>
        <div class="legend" id="comparison-legend"></div>
        <svg class="chart" id="chart-comparison" viewBox="0 0 320 160" preserveAspectRatio="xMidYMid meet"></svg>
      </div>
    </aside>

    <section class="papers">
      <h2>Papers</h2>
      <div id="paper-list"></div>
    </section>
  </div>

  <section class="gallery">
    <h2>Fieldwork &amp; research</h2>
    __GALLERY_HTML__
  </section>

  <footer class="page-footer">
    Data from <a href="https://openalex.org" target="_blank" rel="noopener">OpenAlex</a>.
    Generated by <code>scripts/build_page.py</code> from <code>data/publications.json</code>.
  </footer>
</div>

<div id="tooltip"></div>

<script id="pub-data" type="application/json">__DATA_JSON__</script>
<script>
(function () {
  "use strict";

  var DATA = JSON.parse(document.getElementById("pub-data").textContent);
  var SERIES_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

  // ---- Theme toggle ----
  var root = document.documentElement;
  var toggleBtn = document.getElementById("theme-toggle");
  function applyTheme(theme) {
    if (theme === "dark") {
      root.setAttribute("data-theme", "dark");
      toggleBtn.textContent = "☀️ Light mode";
    } else {
      root.setAttribute("data-theme", "light");
      toggleBtn.textContent = "🌙 Dark mode";
    }
  }
  var savedTheme = localStorage.getItem("theme");
  if (savedTheme) applyTheme(savedTheme);
  else applyTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  toggleBtn.addEventListener("click", function () {
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    localStorage.setItem("theme", next);
  });

  // ---- Header content ----
  document.getElementById("author-name").textContent = DATA.name;
  document.getElementById("author-tagline").textContent = DATA.tagline;
  document.getElementById("author-bio").textContent = DATA.bio;

  // ---- Stats ----
  document.getElementById("stat-total-citations").textContent = DATA.stats.total_citations;
  document.getElementById("stat-paper-count").textContent = DATA.stats.paper_count;
  document.getElementById("stat-h-index").textContent = DATA.stats.h_index;
  var mc = DATA.stats.most_cited;
  var mcLink = document.getElementById("most-cited-link");
  mcLink.textContent = mc.title + " (" + mc.year + ")";
  mcLink.href = mc.link || "#";
  document.getElementById("most-cited-count").textContent = mc.count + " citations";

  // ---- Tooltip ----
  var tooltip = document.getElementById("tooltip");
  function showTooltip(x, y, rows, yearLabel) {
    tooltip.innerHTML = "";
    var yearEl = document.createElement("div");
    yearEl.className = "tt-year";
    yearEl.textContent = yearLabel;
    tooltip.appendChild(yearEl);
    rows.forEach(function (r) {
      var row = document.createElement("div");
      row.className = "tt-row";
      var key = document.createElement("span");
      key.className = "tt-key";
      key.style.background = r.color;
      var value = document.createElement("span");
      value.className = "tt-value";
      value.textContent = r.value;
      var label = document.createElement("span");
      label.className = "tt-label";
      label.textContent = r.label;
      row.appendChild(key);
      row.appendChild(value);
      row.appendChild(label);
      tooltip.appendChild(row);
    });
    tooltip.style.left = (x + 14) + "px";
    tooltip.style.top = (y + 14) + "px";
    tooltip.style.opacity = "1";
  }
  function hideTooltip() { tooltip.style.opacity = "0"; }

  // ---- Generic SVG line chart ----
  // series: [{ id, label, color, data: [values...] (aligned to DATA.years) }]
  function renderChart(svg, years, series, opts) {
    opts = opts || {};
    var W = 320, H = 160;
    var padL = 30, padR = 10, padT = 10, padB = 20;
    var plotW = W - padL - padR, plotH = H - padT - padB;

    var maxVal = 0;
    series.forEach(function (s) {
      s.data.forEach(function (v) { if (v > maxVal) maxVal = v; });
    });
    if (maxVal === 0) maxVal = 1;
    var yMax = niceCeil(maxVal);

    function xPos(i) { return padL + (plotW * i) / Math.max(1, years.length - 1); }
    function yPos(v) { return padT + plotH - (plotH * v) / yMax; }

    while (svg.firstChild) svg.removeChild(svg.firstChild);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);

    var svgNS = "http://www.w3.org/2000/svg";

    // gridlines (0, mid, max) + y labels
    [0, 0.5, 1].forEach(function (frac) {
      var val = yMax * frac;
      var y = yPos(val);
      var line = document.createElementNS(svgNS, "line");
      line.setAttribute("class", "gridline");
      line.setAttribute("x1", padL);
      line.setAttribute("x2", W - padR);
      line.setAttribute("y1", y);
      line.setAttribute("y2", y);
      svg.appendChild(line);

      var label = document.createElementNS(svgNS, "text");
      label.setAttribute("class", "axis-label");
      label.setAttribute("x", padL - 6);
      label.setAttribute("y", y + 3);
      label.setAttribute("text-anchor", "end");
      label.textContent = Math.round(val);
      svg.appendChild(label);
    });

    // x-axis year labels: first, mid, last
    var xIdxs = years.length > 1 ? [0, Math.floor((years.length - 1) / 2), years.length - 1] : [0];
    xIdxs.forEach(function (i) {
      var label = document.createElementNS(svgNS, "text");
      label.setAttribute("class", "axis-label");
      label.setAttribute("x", xPos(i));
      label.setAttribute("y", H - 4);
      label.setAttribute("text-anchor", i === 0 ? "start" : (i === years.length - 1 ? "end" : "middle"));
      label.textContent = years[i];
      svg.appendChild(label);
    });

    // baseline
    var base = document.createElementNS(svgNS, "line");
    base.setAttribute("class", "baseline");
    base.setAttribute("x1", padL);
    base.setAttribute("x2", W - padR);
    base.setAttribute("y1", padT + plotH);
    base.setAttribute("y2", padT + plotH);
    svg.appendChild(base);

    // crosshair (hidden until hover)
    var crosshair = document.createElementNS(svgNS, "line");
    crosshair.setAttribute("class", "crosshair");
    crosshair.setAttribute("y1", padT);
    crosshair.setAttribute("y2", padT + plotH);
    svg.appendChild(crosshair);

    var seriesEls = series.map(function (s) {
      var visible = opts.isVisible ? opts.isVisible(s.id) : true;
      var pathD = s.data.map(function (v, i) {
        return (i === 0 ? "M" : "L") + xPos(i).toFixed(1) + "," + yPos(v).toFixed(1);
      }).join(" ");
      var path = document.createElementNS(svgNS, "path");
      path.setAttribute("class", "chart-line");
      path.setAttribute("d", pathD);
      path.setAttribute("stroke", s.color);
      path.style.display = visible ? "" : "none";
      svg.appendChild(path);

      if (opts.endLabel && visible) {
        var lastI = s.data.length - 1;
        var lbl = document.createElementNS(svgNS, "text");
        lbl.setAttribute("class", "end-label");
        lbl.setAttribute("x", xPos(lastI) - 4);
        lbl.setAttribute("y", yPos(s.data[lastI]) - 6);
        lbl.setAttribute("text-anchor", "end");
        lbl.setAttribute("fill", s.color);
        lbl.textContent = s.data[lastI];
        svg.appendChild(lbl);
      }

      var hoverDot = document.createElementNS(svgNS, "circle");
      hoverDot.setAttribute("class", "hover-dot");
      hoverDot.setAttribute("fill", s.color);
      hoverDot.setAttribute("stroke", "var(--surface-1)");
      svg.appendChild(hoverDot);

      return { s: s, path: path, hoverDot: hoverDot, visible: visible };
    });

    // hover hit area
    var hit = document.createElementNS(svgNS, "rect");
    hit.setAttribute("x", padL);
    hit.setAttribute("y", padT);
    hit.setAttribute("width", plotW);
    hit.setAttribute("height", plotH);
    hit.setAttribute("fill", "transparent");
    svg.appendChild(hit);

    function onMove(evt) {
      var rect = svg.getBoundingClientRect();
      var scaleX = W / rect.width;
      var localX = (evt.clientX - rect.left) * scaleX;
      var idx = Math.round(((localX - padL) / plotW) * (years.length - 1));
      idx = Math.max(0, Math.min(years.length - 1, idx));

      crosshair.setAttribute("x1", xPos(idx));
      crosshair.setAttribute("x2", xPos(idx));
      crosshair.style.opacity = "1";

      var rows = [];
      seriesEls.forEach(function (se) {
        var visNow = opts.isVisible ? opts.isVisible(se.s.id) : true;
        se.hoverDot.style.opacity = visNow ? "1" : "0";
        if (visNow) {
          se.hoverDot.setAttribute("cx", xPos(idx));
          se.hoverDot.setAttribute("cy", yPos(se.s.data[idx]));
          rows.push({ color: se.s.color, value: se.s.data[idx], label: se.s.label });
        }
      });
      showTooltip(evt.clientX, evt.clientY, rows, years[idx]);
    }
    function onLeave() {
      crosshair.style.opacity = "0";
      seriesEls.forEach(function (se) { se.hoverDot.style.opacity = "0"; });
      hideTooltip();
    }
    hit.addEventListener("pointermove", onMove);
    hit.addEventListener("pointerleave", onLeave);

    return {
      setVisible: function (id, visible) {
        seriesEls.forEach(function (se) {
          if (se.s.id === id) {
            se.path.style.display = visible ? "" : "none";
            se.visible = visible;
          }
        });
        // redraw end labels
        renderChart(svg, years, series, opts);
      },
    };
  }

  function niceCeil(v) {
    if (v <= 5) return 5;
    var magnitude = Math.pow(10, Math.floor(Math.log10(v)));
    var residual = v / magnitude;
    var niceResidual = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10;
    return niceResidual * magnitude;
  }

  // ---- Mini sparkline (no axis/tooltip) ----
  function renderSparkline(svg, data) {
    var W = 100, H = 32, pad = 4;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var maxVal = Math.max.apply(null, data.concat([1]));
    var plotW = W - pad * 2, plotH = H - pad * 2;
    function xPos(i) { return pad + (plotW * i) / Math.max(1, data.length - 1); }
    function yPos(v) { return pad + plotH - (plotH * v) / maxVal; }
    var svgNS = "http://www.w3.org/2000/svg";
    var pathD = data.map(function (v, i) {
      return (i === 0 ? "M" : "L") + xPos(i).toFixed(1) + "," + yPos(v).toFixed(1);
    }).join(" ");
    var path = document.createElementNS(svgNS, "path");
    path.setAttribute("class", "chart-line");
    path.setAttribute("d", pathD);
    path.setAttribute("stroke", "var(--accent)");
    svg.appendChild(path);

    var lastI = data.length - 1;
    var dot = document.createElementNS(svgNS, "circle");
    dot.setAttribute("class", "chart-dot");
    dot.setAttribute("cx", xPos(lastI));
    dot.setAttribute("cy", yPos(data[lastI]));
    dot.setAttribute("fill", "var(--accent)");
    dot.setAttribute("stroke", "var(--surface-1)");
    svg.appendChild(dot);
  }

  // ---- Main cumulative chart ----
  renderChart(
    document.getElementById("chart-total"),
    DATA.years,
    [{ id: "total", label: "All papers", color: "var(--accent)", data: DATA.total_series }],
    { endLabel: true }
  );

  // ---- Per-paper comparison chart + legend + list toggling ----
  var visibility = {};
  DATA.papers.forEach(function (p) { visibility[p.id] = true; });

  var comparisonSeries = DATA.papers.map(function (p, i) {
    return {
      id: p.id,
      label: p.year + " — " + p.venue,
      color: SERIES_COLORS[i % SERIES_COLORS.length],
      data: p.cumulative_by_year,
    };
  });

  var comparisonChart = renderChart(
    document.getElementById("chart-comparison"),
    DATA.years,
    comparisonSeries,
    { isVisible: function (id) { return visibility[id]; } }
  );

  function setVisibility(id, visible) {
    visibility[id] = visible;
    comparisonChart.setVisible(id, visible);
    comparisonChart = renderChart(
      document.getElementById("chart-comparison"),
      DATA.years,
      comparisonSeries,
      { isVisible: function (pid) { return visibility[pid]; } }
    );
    syncLegend();
    syncRows();
  }

  var legendEl = document.getElementById("comparison-legend");
  comparisonSeries.forEach(function (s) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "legend-item";
    btn.innerHTML = "";
    var key = document.createElement("span");
    key.className = "legend-key";
    key.style.background = s.color;
    var label = document.createElement("span");
    label.textContent = s.label;
    btn.appendChild(key);
    btn.appendChild(label);
    btn.addEventListener("click", function () {
      setVisibility(s.id, !visibility[s.id]);
    });
    btn.dataset.seriesId = s.id;
    legendEl.appendChild(btn);
  });
  function syncLegend() {
    Array.prototype.forEach.call(legendEl.children, function (btn) {
      btn.classList.toggle("off", !visibility[btn.dataset.seriesId]);
    });
  }

  // ---- Paper list ----
  var listEl = document.getElementById("paper-list");
  var rowEls = {};
  DATA.papers.forEach(function (p, i) {
    var color = SERIES_COLORS[i % SERIES_COLORS.length];
    var row = document.createElement("div");
    row.className = "paper-row active";
    row.style.setProperty("--row-color", color);
    row.dataset.seriesId = p.id;

    var main = document.createElement("div");

    var titleEl = document.createElement("div");
    titleEl.className = "p-title";
    var link = document.createElement("a");
    link.href = p.link || "#";
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = p.title;
    link.addEventListener("click", function (evt) { evt.stopPropagation(); });
    titleEl.appendChild(link);
    main.appendChild(titleEl);

    var meta = document.createElement("div");
    meta.className = "p-meta";
    var badge = document.createElement("span");
    badge.className = "badge";
    badge.textContent = p.type;
    meta.appendChild(badge);
    meta.appendChild(document.createTextNode(p.venue + " · " + p.year));
    main.appendChild(meta);

    if (p.authors && p.authors.length) {
      var authors = document.createElement("div");
      authors.className = "p-authors";
      authors.textContent = p.authors.join(", ");
      main.appendChild(authors);
    }

    var cites = document.createElement("div");
    cites.className = "p-cites";
    var citesValue = document.createElement("span");
    citesValue.className = "tabular";
    citesValue.textContent = p.cited_by_count_total;
    cites.appendChild(citesValue);
    cites.appendChild(document.createTextNode(" total citations"));
    main.appendChild(cites);

    row.appendChild(main);

    var sparkWrap = document.createElement("div");
    sparkWrap.className = "sparkline-wrap";
    var sparkSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    sparkSvg.setAttribute("class", "chart");
    sparkWrap.appendChild(sparkSvg);
    row.appendChild(sparkWrap);
    renderSparkline(sparkSvg, p.cumulative_by_year);

    row.addEventListener("click", function () {
      setVisibility(p.id, !visibility[p.id]);
    });

    rowEls[p.id] = row;
    listEl.appendChild(row);
  });
  function syncRows() {
    DATA.papers.forEach(function (p) {
      rowEls[p.id].classList.toggle("active", visibility[p.id]);
    });
  }
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
