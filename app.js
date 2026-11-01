// Versão estática do painel UFC 8-BIT (GitHub Pages).
// Os dados já chegam processados pelo Python em data.json (ver dashboard/build_static.py);
// aqui só montamos as telas, com as mesmas classes CSS do app Dash.

const COLORS = { W: "#4ade80", L: "#ff4d5e", D: "#8f88c0", ink: "#f4f0ff", muted: "#8f88c0",
                 grid: "#2a2456", attempt: "#3a3370", line: "#0c0818" };
const PIXEL_FONT = "'Press Start 2P', monospace";
const TEXT_FONT = "VT323, monospace";

let DB = null;
const screen = document.getElementById("screen");

// ---------------------------------------------------------------- helpers

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const show = (v) => (v === null || v === undefined || v === "" ? "--" : esc(v));
const route = (...parts) => "#/" + parts.map(encodeURIComponent).join("/");
const roster = (division) => DB.fighters.filter((f) => f.division === division);
const fmtDate = (iso) => (iso ? iso.split("-").reverse().join("/") : "--");

function rankBadge(rank) {
  return rank === "C" ? `<span class="rank rank-champ">CHAMP</span>` : `<span class="rank">#${esc(rank)}</span>`;
}

function recordSpans(record) {
  const [w = "-", l = "-", d = "-"] = (record || "").split("-");
  return `<span class="rec-w">${esc(w)}</span><span>-</span><span class="rec-l">${esc(l)}</span>` +
         `<span>-</span><span class="rec-d">${esc(d)}</span>`;
}

const panel = (title, body, cls = "") =>
  `<section class="pixel-box panel ${cls}"><h3 class="panel-title">${title}</h3>${body}</section>`;

// ---------------------------------------------------------------- tela 1: divisões

function divisionsScreen() {
  const cards = DB.divisions.map(({ name, lbs }) => {
    const list = roster(name);
    const champ = list.find((f) => f.rank === "C");
    const face = champ || list[0];
    return `<a class="division-card pixel-box" href="${route("d", name)}">
      <img class="sprite" src="${face.sprite}" alt="${esc(face.name)}">
      <div class="division-name">${esc(name.toUpperCase())}</div>
      <div class="division-lbs">${lbs} LBS</div>
      <div class="division-champ">${champ ? "★ " : ""}${esc(face.name)}</div>
    </a>`;
  }).join("");
  return `<div class="screen">
    <header class="title">
      <h1>UFC <span class="accent">RANKED</span></h1>
      <div class="subtitle">8-BIT EDITION · MEN'S DIVISIONS</div>
    </header>
    <div class="blink section-label">SELECT DIVISION</div>
    <div class="division-grid">${cards}</div>
    <footer class="footer">DATA: ESPN · RANKING: UFC.COM · UPDATED ${esc(DB.updated)}</footer>
  </div>`;
}

// ---------------------------------------------------------------- tela 2: seleção

function flank(f, label) {
  return `<div class="flank">
    <div class="flank-label">${esc(label)}</div>
    <img class="sprite flank-sprite" src="${f.sprite}" alt="${esc(f.name)}">
    <div class="flank-name">${esc(f.name.toUpperCase())}</div>
    <div class="flank-record">${recordSpans(f.record)}</div>
  </div>`;
}

function selectScreen(division) {
  const list = roster(division);
  if (!list.length) return divisionsScreen();
  const lbs = DB.divisions.find((d) => d.name === division).lbs;
  const champ = list[0];
  const contender = list[1] || champ;
  const tiles = list.map((f) => `
    <a class="tile pixel-box${f.rank === "C" ? " tile-champ" : ""}" href="${route("f", f.id)}"
       title="${esc(f.name)} · ${esc(f.record)}">
      ${rankBadge(f.rank)}
      <img class="sprite" src="${f.sprite}" alt="${esc(f.name)}">
      <div class="tile-name">${esc(f.name)}</div>
    </a>`).join("");
  return `<div class="screen">
    <div class="topbar">
      <a class="btn" href="#/">◄ DIVISIONS</a>
      <h2>${esc(division.toUpperCase())}<span class="muted"> ${lbs} LBS</span></h2>
      <div></div>
    </div>
    <div class="blink section-label">CHOOSE YOUR FIGHTER</div>
    <div class="select-layout">
      ${flank(champ, champ.rank === "C" ? "CHAMPION" : `#${champ.rank}`)}
      <div class="fighter-grid">${tiles}</div>
      ${flank(contender, `#${contender.rank} CONTENDER`)}
    </div>
  </div>`;
}

// ---------------------------------------------------------------- tela 3: perfil

function attributesPanel(f) {
  if (!f.attrs) return panel("ATTRIBUTES", `<p class="muted">NO FIGHT STATS ON ESPN</p>`);
  const rows = f.attrs.map(([label, text, blocks]) => {
    const level = blocks <= 3 ? "lvl-low" : blocks <= 6 ? "lvl-mid" : "lvl-high";
    const blks = Array.from({ length: 10 }, (_, i) => `<span class="blk${i < blocks ? " on" : ""}"></span>`).join("");
    return `<div class="attr-row"><span class="attr-label">${label}</span>
      <div class="attr-bar ${level}">${blks}</div><span class="attr-val">${esc(text)}</span></div>`;
  }).join("");
  const note = `BARS = PERCENTILE VS RANKED MEN · ${f.fights_with_stats} FIGHTS WITH STATS`;
  return panel("ATTRIBUTES", rows + `<p class="note">${note}</p>`);
}

function bioPanel(f) {
  const items = f.bio.map(([k, v]) => `<dt>${k}</dt><dd>${show(v)}</dd>`).join("");
  return panel("BIO", `<dl class="bio-list">${items}</dl>`);
}

function methodsPanel(f) {
  const rows = Object.entries(f.methods)
    .filter(([m, [w, l, d]]) => m !== "OTHER" || w + l + d > 0)
    .map(([m, [w, l, d]]) => {
      const pips = `<span class="pip pip-W"></span>`.repeat(w) + `<span class="pip pip-L"></span>`.repeat(l) +
                   `<span class="pip pip-D"></span>`.repeat(d);
      return `<div class="method-row"><span class="method-label">${m}</span><div class="pips">${pips}</div>
        <span class="method-count"><span class="rec-w">W${w}</span> <span class="rec-l">L${l}</span></span></div>`;
    }).join("");
  const legend = `<p class="note legend"><span class="pip pip-W"></span><span>WIN</span>
    <span class="pip pip-L"></span><span>LOSS</span><span class="pip pip-D"></span><span>DRAW/NC</span></p>`;
  return panel("WIN / LOSS METHODS", rows + legend);
}

function formPanel(f) {
  const boxes = f.history.slice(0, 5).map(([, res, opp, dec]) => `
    <div class="form-item" title="${esc(opp)} · ${esc(dec)}">
      <div class="form-box res-${esc(res)}">${esc(res)}</div>
      <div class="form-opp">${esc(String(opp).split(" ").pop().toUpperCase())}</div>
    </div>`).join("");
  return panel("LAST 5 FIGHTS", `<div class="form-row">${boxes}</div>`);
}

function historyPanel(f) {
  const head = ["DATE", "RES", "OPPONENT", "METHOD", "RD", "TIME", "EVENT"].map((h) => `<th>${h}</th>`).join("");
  const rows = f.history.map(([d, res, opp, dec, rd, time, event, title]) => `<tr>
    <td>${fmtDate(d)}</td><td><span class="res-badge res-${esc(res)}">${esc(res)}</span></td>
    <td>${esc(opp)}</td><td>${show(dec)}</td><td>${show(rd)}</td><td>${show(time)}</td>
    <td>${title ? `<span class="belt" title="Title fight">★ </span>` : ""}${show(event)}</td></tr>`).join("");
  return panel(`FIGHT HISTORY · ${f.history.length} PRO FIGHTS`,
    `<div class="table-wrap"><table class="history"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`,
    "wide");
}

function strikesPanel(f) {
  if (!f.strikes.length) {
    return panel("SIGNIFICANT STRIKES PER FIGHT", `<p class="muted">NO FIGHT STATS ON ESPN</p>`, "wide");
  }
  return panel("SIGNIFICANT STRIKES PER FIGHT",
    `<p class="note">BAR COLOR = RESULT (GREEN WIN · RED LOSS)</p><div id="strikes-chart" style="height:330px"></div>`,
    "wide");
}

function drawStrikes(f) {
  const el = document.getElementById("strikes-chart");
  if (!el) return;
  if (!window.Plotly) { setTimeout(() => drawStrikes(f), 200); return; }  // Plotly ainda carregando
  const x = f.strikes.map(([d]) => fmtDate(d).replace(/\/(\d\d)(\d\d)$/, "/$2"));
  const custom = f.strikes.map(([, opp, event]) => [opp, event]);
  const hover = "%{customdata[0]}<br>%{customdata[1]}<br>%{y} %{fullData.name}<extra></extra>";
  const traces = [
    { type: "bar", x, y: f.strikes.map((s) => s[5]), name: "ATTEMPTED", customdata: custom,
      hovertemplate: hover, marker: { color: COLORS.attempt, line: { color: COLORS.line, width: 2 } } },
    { type: "bar", x, y: f.strikes.map((s) => s[4]), name: "LANDED", width: 0.55, customdata: custom,
      hovertemplate: hover,
      marker: { color: f.strikes.map((s) => COLORS[s[3]] || COLORS.D), line: { color: COLORS.line, width: 2 } } },
  ];
  const layout = {
    barmode: "overlay", height: 330, margin: { l: 48, r: 12, t: 36, b: 70 }, bargap: 0.25,
    paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: PIXEL_FONT, size: 8, color: COLORS.ink },
    legend: { orientation: "h", x: 0, y: 1.14, font: { size: 8 } },
    hoverlabel: { font: { family: TEXT_FONT, size: 18 }, bgcolor: "#18143a", bordercolor: COLORS.ink },
    xaxis: { type: "category", tickangle: -60, showgrid: false, linecolor: COLORS.muted },
    yaxis: { gridcolor: COLORS.grid, griddash: "dot", zeroline: false },
  };
  Plotly.newPlot(el, traces, layout, { displayModeBar: false, responsive: true });
}

function fighterScreen(id) {
  const f = DB.fighters.find((x) => x.id === id);
  if (!f) return divisionsScreen();
  const list = roster(f.division);
  const i = list.indexOf(f);
  const prev = list[(i - 1 + list.length) % list.length];
  const next = list[(i + 1) % list.length];
  const nick = f.nickname ? `“${esc(f.nickname)}”` : "";
  return `<div class="screen">
    <div class="topbar">
      <a class="btn" href="${route("d", f.division)}">◄ SELECT</a>
      <h2>${esc(f.division.toUpperCase())} · ${rankBadge(f.rank)}</h2>
      <div class="cycle">
        <a class="btn btn-sq" href="${route("f", prev.id)}" title="Previous fighter">◄</a>
        <a class="btn btn-sq" href="${route("f", next.id)}" title="Next fighter">►</a>
      </div>
    </div>
    <div class="profile">
      <section class="pixel-box panel hero">
        <img class="sprite hero-sprite" src="${f.sprite}" alt="${esc(f.name)}">
        <h2 class="hero-name">${esc(f.name.toUpperCase())}</h2>
        <div class="hero-nick">${nick}</div>
        <div class="hero-record">${recordSpans(f.record)}</div>
        <div class="muted tiny">W - L - D</div>
        <div class="hero-sub">
          <div><span class="muted">(T)KO W-L</span><span>${show(f.ko)}</span></div>
          <div><span class="muted">SUB W-L</span><span>${show(f.sub)}</span></div>
        </div>
        <a class="ext-link" href="${esc(f.espn_url)}" target="_blank" rel="noopener">ESPN PROFILE ►</a>
      </section>
      <div class="col">${attributesPanel(f)}${methodsPanel(f)}</div>
      <div class="col">${bioPanel(f)}${formPanel(f)}</div>
      ${strikesPanel(f)}
      ${historyPanel(f)}
    </div>
  </div>`;
}

// ---------------------------------------------------------------- roteamento

function render() {
  const [kind, arg] = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  if (kind === "d") {
    screen.innerHTML = selectScreen(arg);
  } else if (kind === "f") {
    const f = DB.fighters.find((x) => x.id === arg);
    screen.innerHTML = fighterScreen(arg);
    if (f) drawStrikes(f);
  } else {
    screen.innerHTML = divisionsScreen();
  }
  window.scrollTo(0, 0);
}

fetch("data.json")
  .then((r) => r.json())
  .then((db) => {
    DB = db;
    // pré-carrega os sprites para a grade não aparecer vazia ao abrir uma divisão
    DB.fighters.forEach((f) => { new Image().src = f.sprite; });
    window.addEventListener("hashchange", render);
    render();
  })
  .catch(() => {
    screen.innerHTML = `<div class="screen"><div class="section-label">ERROR LOADING DATA</div></div>`;
  });
