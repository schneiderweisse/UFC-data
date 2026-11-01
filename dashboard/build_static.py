"""
Gera a versão estática do painel (para o GitHub Pages) na pasta docs/.

O GitHub Pages não executa Python, então todo o processamento continua aqui:
este script usa o mesmo data.py do app Dash, calcula atributos, métodos de
vitória, histórico e golpes por luta, e grava tudo em docs/data.json. A página
(static/index.html + static/app.js) só desenha esses dados no navegador,
reaproveitando o mesmo CSS do app Dash (assets/style.css).

Uso:
  py dashboard/build_static.py
"""

import json
import shutil
from datetime import date
from pathlib import Path

import pandas as pd
from PIL import Image

import data

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"
OUT_DIR = HERE.parent / "docs"

BIO_FIELDS = [("HEIGHT", "height"), ("WEIGHT", "weight"), ("REACH", "reach"), ("AGE", "age"),
              ("BORN", "birthdate"), ("STANCE", "stance"), ("STYLE", "fighting_style"),
              ("TEAM", "team"), ("COUNTRY", "country")]
METHODS = ["KO/TKO", "SUB", "DEC", "OTHER"]


def clean(value):
    """Converte NaN/float inteiro/Timestamp em algo que o JSON entenda bem."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if hasattr(value, "item"):  # numpy -> tipo nativo
        return value.item()
    return value


def attributes(espn_id):
    a = data.attributes_of(espn_id)
    if a is None:
        return None, 0
    rows = []
    for col, label, fmt in data.ATTRIBUTES:
        value, pct = a[col], a[col + "_pct"]
        blocks = 0 if pd.isna(pct) else max(1, round(pct * 10))
        rows.append([label, "--" if pd.isna(value) else fmt.format(value), blocks])
    return rows, int(a["fights_with_stats"])


def methods(hist):
    out = {}
    for method in METHODS:
        sub = hist[hist["method"] == method]
        w, l = int((sub["result"] == "W").sum()), int((sub["result"] == "L").sum())
        out[method] = [w, l, len(sub) - w - l]
    return out


def fighter_record(f):
    espn_id = f["espn_id"]
    hist = data.history_of(espn_id)
    stats = data.stats_of(espn_id)
    attrs, n_stats = attributes(espn_id)
    return {
        "id": espn_id,
        "name": f["name"],
        "division": f["division"],
        "rank": f["rank"],
        "sprite": "sprites/" + Path(f["sprite"]).name,
        "nickname": clean(f["nickname"]),
        "record": clean(f["record_w_l_d"]),
        "ko": clean(f["ko_tko_w_l"]),
        "sub": clean(f["sub_w_l"]),
        "espn_url": f["espn_url"],
        "bio": [[label, clean(f[col])] for label, col in BIO_FIELDS],
        "attrs": attrs,
        "fights_with_stats": n_stats,
        "methods": methods(hist),
        "history": [[clean(r["date"]), r["result"], r["opponent"], clean(r["decision"]),
                     clean(r["round"]), clean(r["time"]), clean(r["event"]), bool(r["title_fight"])]
                    for _, r in hist.iterrows()],
        "strikes": [[clean(r["date"]), r["opponent"], r["event"], r["result"],
                     clean(r["SSL"]), clean(r["SSA"])]
                    for _, r in stats.iterrows()],
    }


def banner(fighters, path):
    """Faixa com os sprites dos campeões, usada no README."""
    order = [d for d, _ in data.DIVISIONS]
    champs = sorted((f for f in fighters if f["rank"] == "C"), key=lambda f: order.index(f["division"]))
    size, pad = 144, 16
    img = Image.new("RGBA", (len(champs) * (size + pad) + pad, size + 2 * pad), (11, 10, 26, 255))
    for i, f in enumerate(champs):
        sprite = Image.open(HERE / "assets" / f["sprite"]).resize((size, size), Image.NEAREST)
        img.paste(sprite, (pad + i * (size + pad), pad), sprite)
    img.save(path)


def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    fighters = [fighter_record(f) for _, f in data.FIGHTERS.iterrows()]
    payload = {
        "updated": date.fromtimestamp((data.DATA_DIR / "ranked_fighters.csv").stat().st_mtime).isoformat(),
        "divisions": [{"name": d, "lbs": lbs} for d, lbs in data.DIVISIONS],
        "fighters": fighters,
    }
    with open(OUT_DIR / "data.json", "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, separators=(",", ":"))

    shutil.copytree(HERE / "assets" / "sprites", OUT_DIR / "sprites")
    shutil.copy(HERE / "assets" / "style.css", OUT_DIR / "style.css")
    for src in STATIC_DIR.iterdir():
        shutil.copy(src, OUT_DIR / src.name)
    (OUT_DIR / ".nojekyll").touch()  # o Pages serve os arquivos como estão, sem Jekyll
    banner(fighters, OUT_DIR / "banner.png")

    size_kb = (OUT_DIR / "data.json").stat().st_size / 1024
    print(f"docs/ gerado: {len(fighters)} lutadores, data.json com {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
