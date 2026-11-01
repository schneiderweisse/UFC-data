"""
Painel 8-bit dos lutadores ranqueados do UFC.

Telas:
  1. SELECT DIVISION  -> escolhe a categoria de peso
  2. CHOOSE YOUR FIGHTER -> grade de personagens da divisão
  3. Perfil do lutador -> bio, atributos, métodos de vitória, golpes por luta e histórico

Uso:
  py app.py      e abra http://127.0.0.1:8050
"""

import pandas as pd
import plotly.graph_objects as go
from dash import ALL, Dash, Input, Output, ctx, dcc, html, no_update

import data

FONTS = "https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&display=swap"
PIXEL_FONT = "'Press Start 2P', monospace"
TEXT_FONT = "VT323, monospace"
COLORS = {"W": "#4ade80", "L": "#ff4d5e", "D": "#8f88c0", "ink": "#f4f0ff",
          "muted": "#8f88c0", "grid": "#2a2456", "attempt": "#3a3370", "line": "#0c0818"}

app = Dash(__name__, title="UFC 8-BIT", update_title=None, external_stylesheets=[FONTS])

app.layout = html.Div([
    dcc.Store(id="state", data={"screen": "divisions", "arg": ""}),
    dcc.Store(id="scroll-sink"),
    html.Div(id="screen"),
    # pré-carrega todos os sprites para a grade não "piscar" vazia ao abrir uma divisão
    html.Div([html.Img(src=s) for s in data.FIGHTERS["sprite"].unique()], className="preload"),
    # idem para o Plotly (~4 MB): sem isso o primeiro perfil aberto demora a aparecer
    dcc.Graph(figure=go.Figure(), className="preload"),
])


# ---------------------------------------------------------------- helpers

def nav(target, children, className="", **kwargs):
    """Botão que troca de tela. target = 'divisions' | 'select:<divisão>' | 'fighter:<espn_id>'."""
    return html.Button(children, id={"type": "nav", "to": target}, className=className, **kwargs)


def show(value, suffix=""):
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return "--"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value}{suffix}"


def rank_badge(rank):
    return html.Span("CHAMP" if rank == "C" else f"#{rank}",
                     className="rank" + (" rank-champ" if rank == "C" else ""))


def record_spans(record):
    parts = str(record).split("-") if isinstance(record, str) else ["-", "-", "-"]
    w, l, d = (parts + ["0", "0", "0"])[:3]
    return [html.Span(w, className="rec-w"), html.Span("-"),
            html.Span(l, className="rec-l"), html.Span("-"),
            html.Span(d, className="rec-d")]


def panel(title, *children, className=""):
    return html.Section([html.H3(title, className="panel-title"), *children],
                        className="pixel-box panel " + className)


# ---------------------------------------------------------------- tela 1: divisões

def division_card(division, lbs):
    roster = data.fighters_in(division)
    champ = roster[roster["rank"] == "C"]
    face = champ.iloc[0] if len(champ) else roster.iloc[0]
    return nav(f"select:{division}", [
        html.Img(src=face["sprite"], className="sprite"),
        html.Div(division.upper(), className="division-name"),
        html.Div(f"{lbs} LBS", className="division-lbs"),
        html.Div(["★ ", face["name"]] if len(champ) else face["name"], className="division-champ"),
    ], className="division-card pixel-box")


def divisions_screen():
    return html.Div([
        html.Header([
            html.H1(["UFC ", html.Span("RANKED", className="accent")]),
            html.Div("8-BIT EDITION · MEN'S DIVISIONS", className="subtitle"),
        ], className="title"),
        html.Div("SELECT DIVISION", className="blink section-label"),
        html.Div([division_card(d, lbs) for d, lbs in data.DIVISIONS], className="division-grid"),
        html.Footer("DATA: ESPN · RANKING: UFC.COM", className="footer"),
    ], className="screen")


# ---------------------------------------------------------------- tela 2: seleção

def fighter_tile(f):
    return nav(f"fighter:{f['espn_id']}", [
        rank_badge(f["rank"]),
        html.Img(src=f["sprite"], className="sprite"),
        html.Div(f["name"], className="tile-name"),
    ], className="tile pixel-box" + (" tile-champ" if f["rank"] == "C" else ""),
        title=f"{f['name']} · {f['record_w_l_d']}")


def flank(f, label):
    return html.Div([
        html.Div(label, className="flank-label"),
        html.Img(src=f["sprite"], className="sprite flank-sprite"),
        html.Div(f["name"].upper(), className="flank-name"),
        html.Div(record_spans(f["record_w_l_d"]), className="flank-record"),
    ], className="flank")


def select_screen(division):
    roster = data.fighters_in(division)
    lbs = dict(data.DIVISIONS)[division]
    champ = roster.iloc[0]
    contender = roster.iloc[1] if len(roster) > 1 else champ
    return html.Div([
        html.Div([
            nav("divisions", "◄ DIVISIONS", className="btn"),
            html.H2([division.upper(), html.Span(f" {lbs} LBS", className="muted")]),
            html.Div(),
        ], className="topbar"),
        html.Div("CHOOSE YOUR FIGHTER", className="blink section-label"),
        html.Div([
            flank(champ, "CHAMPION" if champ["rank"] == "C" else f"#{champ['rank']}"),
            html.Div([fighter_tile(f) for _, f in roster.iterrows()], className="fighter-grid"),
            flank(contender, f"#{contender['rank']} CONTENDER"),
        ], className="select-layout"),
    ], className="screen")


# ---------------------------------------------------------------- tela 3: perfil

def attribute_row(label, fmt, value, pct):
    blocks = 0 if pd.isna(pct) else max(1, round(pct * 10))
    level = "lvl-low" if blocks <= 3 else "lvl-mid" if blocks <= 6 else "lvl-high"
    return html.Div([
        html.Span(label, className="attr-label"),
        html.Div([html.Span(className="blk" + (" on" if i < blocks else "")) for i in range(10)],
                 className="attr-bar " + level),
        html.Span("--" if pd.isna(value) else fmt.format(value), className="attr-val"),
    ], className="attr-row")


def attributes_panel(espn_id):
    a = data.attributes_of(espn_id)
    if a is None:
        return panel("ATTRIBUTES", html.P("NO FIGHT STATS ON ESPN", className="muted"))
    rows = [attribute_row(label, fmt, a[col], a[col + "_pct"]) for col, label, fmt in data.ATTRIBUTES]
    note = f"BARS = PERCENTILE VS RANKED MEN · {int(a['fights_with_stats'])} FIGHTS WITH STATS"
    return panel("ATTRIBUTES", *rows, html.P(note, className="note"))


def bio_panel(f):
    items = [("HEIGHT", f["height"]), ("WEIGHT", f["weight"]), ("REACH", f["reach"]),
             ("AGE", f["age"]), ("BORN", f["birthdate"]), ("STANCE", f["stance"]),
             ("STYLE", f["fighting_style"]), ("TEAM", f["team"]), ("COUNTRY", f["country"])]
    return panel("BIO", html.Dl([el for k, v in items for el in (html.Dt(k), html.Dd(show(v)))],
                                className="bio-list"))


def methods_panel(hist):
    rows = []
    for method in ["KO/TKO", "SUB", "DEC", "OTHER"]:
        sub = hist[hist["method"] == method]
        w, l = (sub["result"] == "W").sum(), (sub["result"] == "L").sum()
        d = len(sub) - w - l
        if method == "OTHER" and len(sub) == 0:
            continue
        pips = ([html.Span(className="pip pip-W")] * w + [html.Span(className="pip pip-L")] * l
                + [html.Span(className="pip pip-D")] * d)
        rows.append(html.Div([
            html.Span(method, className="method-label"),
            html.Div(pips, className="pips"),
            html.Span([html.Span(f"W{w}", className="rec-w"), " ", html.Span(f"L{l}", className="rec-l")],
                      className="method-count"),
        ], className="method-row"))
    legend = [el for cls, txt in [("pip-W", "WIN"), ("pip-L", "LOSS"), ("pip-D", "DRAW/NC")]
              for el in (html.Span(className="pip " + cls), html.Span(txt))]
    return panel("WIN / LOSS METHODS", *rows, html.P(legend, className="note legend"))


def form_panel(hist):
    last = hist.head(5)
    boxes = [html.Div([html.Div(r["result"], className=f"form-box res-{r['result']}"),
                       html.Div(str(r["opponent"]).split()[-1].upper(), className="form-opp")],
                      className="form-item", title=f"{r['opponent']} · {r['decision']}")
             for _, r in last.iterrows()]
    return panel("LAST 5 FIGHTS", html.Div(boxes, className="form-row"))


def strikes_chart(espn_id):
    st = data.stats_of(espn_id)
    if st.empty:
        return panel("SIGNIFICANT STRIKES PER FIGHT", html.P("NO FIGHT STATS ON ESPN", className="muted"),
                     className="wide")
    x = st["date"].dt.strftime("%d/%m/%y")
    hover = st["opponent"] + "<br>" + st["event"] + "<br>%{y} %{fullData.name}<extra></extra>"
    fig = go.Figure([
        go.Bar(x=x, y=st["SSA"], name="ATTEMPTED", marker_color=COLORS["attempt"],
               marker_line=dict(color=COLORS["line"], width=2), hovertemplate=hover),
        go.Bar(x=x, y=st["SSL"], name="LANDED", width=0.55,
               marker_color=[COLORS.get(r, COLORS["D"]) for r in st["result"]],
               marker_line=dict(color=COLORS["line"], width=2), hovertemplate=hover),
    ])
    fig.update_layout(
        barmode="overlay", height=330, margin=dict(l=48, r=12, t=36, b=70),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=PIXEL_FONT, size=8, color=COLORS["ink"]),
        legend=dict(orientation="h", x=0, y=1.14, font=dict(size=8)),
        hoverlabel=dict(font=dict(family=TEXT_FONT, size=18), bgcolor="#18143a", bordercolor=COLORS["ink"]),
        bargap=0.25,
    )
    fig.update_xaxes(type="category", tickangle=-60, showgrid=False, linecolor=COLORS["muted"])
    fig.update_yaxes(gridcolor=COLORS["grid"], griddash="dot", zeroline=False)
    return panel("SIGNIFICANT STRIKES PER FIGHT",
                 html.P("BAR COLOR = RESULT (GREEN WIN · RED LOSS)", className="note"),
                 dcc.Graph(figure=fig, config={"displayModeBar": False}), className="wide")


def history_panel(hist):
    header = html.Thead(html.Tr([html.Th(h) for h in
                                 ["DATE", "RES", "OPPONENT", "METHOD", "RD", "TIME", "EVENT"]]))
    body = html.Tbody([html.Tr([
        html.Td(r["date"].strftime("%d/%m/%Y") if pd.notna(r["date"]) else "--"),
        html.Td(html.Span(r["result"], className=f"res-badge res-{r['result']}")),
        html.Td(r["opponent"]),
        html.Td(show(r["decision"])),
        html.Td(show(r["round"])),
        html.Td(show(r["time"])),
        html.Td([html.Span("★ ", className="belt", title="Title fight") if r["title_fight"] else None,
                 show(r["event"])]),
    ]) for _, r in hist.iterrows()])
    return panel(f"FIGHT HISTORY · {len(hist)} PRO FIGHTS",
                 html.Div(html.Table([header, body], className="history"), className="table-wrap"),
                 className="wide")


def fighter_screen(espn_id):
    f = data.fighter(espn_id)
    if f is None:
        return divisions_screen()
    roster = data.fighters_in(f["division"])["espn_id"].tolist()
    i = roster.index(espn_id)
    prev_id, next_id = roster[i - 1], roster[(i + 1) % len(roster)]
    hist = data.history_of(espn_id)
    nickname = f"“{f['nickname']}”" if isinstance(f["nickname"], str) and f["nickname"] else ""

    return html.Div([
        html.Div([
            nav(f"select:{f['division']}", "◄ SELECT", className="btn"),
            html.H2([f["division"].upper(), " · ", rank_badge(f["rank"])]),
            html.Div([nav(f"fighter:{prev_id}", "◄", className="btn btn-sq", title="Previous fighter"),
                      nav(f"fighter:{next_id}", "►", className="btn btn-sq", title="Next fighter")],
                     className="cycle"),
        ], className="topbar"),
        html.Div([
            html.Section([
                html.Img(src=f["sprite"], className="sprite hero-sprite"),
                html.H2(f["name"].upper(), className="hero-name"),
                html.Div(nickname, className="hero-nick"),
                html.Div(record_spans(f["record_w_l_d"]), className="hero-record"),
                html.Div("W - L - D", className="muted tiny"),
                html.Div([
                    html.Div([html.Span("(T)KO W-L", className="muted"), html.Span(show(f["ko_tko_w_l"]))]),
                    html.Div([html.Span("SUB W-L", className="muted"), html.Span(show(f["sub_w_l"]))]),
                ], className="hero-sub"),
                html.A("ESPN PROFILE ►", href=f["espn_url"], target="_blank", className="ext-link"),
            ], className="pixel-box panel hero"),
            html.Div([attributes_panel(espn_id), methods_panel(hist)], className="col"),
            html.Div([bio_panel(f), form_panel(hist)], className="col"),
            strikes_chart(espn_id),
            history_panel(hist),
        ], className="profile"),
    ], className="screen")


# ---------------------------------------------------------------- callbacks

@app.callback(Output("state", "data"), Input({"type": "nav", "to": ALL}, "n_clicks"),
              prevent_initial_call=True)
def navigate(_clicks):
    # Ao trocar de tela surgem botões novos com n_clicks=None, que também disparam o callback
    if not ctx.triggered_id or not ctx.triggered[0]["value"]:
        return no_update
    screen, _, arg = ctx.triggered_id["to"].partition(":")
    return {"screen": screen, "arg": arg}


@app.callback(Output("screen", "children"), Input("state", "data"))
def render(state):
    if state["screen"] == "select":
        return select_screen(state["arg"])
    if state["screen"] == "fighter":
        return fighter_screen(state["arg"])
    return divisions_screen()


app.clientside_callback("function(s){ window.scrollTo(0, 0); return null; }",
                        Output("scroll-sink", "data"), Input("state", "data"))


if __name__ == "__main__":
    app.run(debug=False)
