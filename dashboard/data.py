"""
Carrega os CSVs de Fighter data/ e prepara as tabelas usadas pelo painel.
"""

from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "Fighter data"
SPRITE_DIR = Path(__file__).resolve().parent / "assets" / "sprites"

DIVISIONS = [
    ("Flyweight", 125), ("Bantamweight", 135), ("Featherweight", 145),
    ("Lightweight", 155), ("Welterweight", 170), ("Middleweight", 185),
    ("Light Heavyweight", 205), ("Heavyweight", 265),
]

# (coluna, rótulo, formato) — atributos estilo RPG mostrados no perfil
ATTRIBUTES = [
    ("str_acc", "STRIKE ACC", "{:.0%}"),
    ("sig_per_fight", "SIG STR/FIGHT", "{:.1f}"),
    ("kd_per_fight", "KNOCKDOWNS/FIGHT", "{:.2f}"),
    ("td_acc", "TAKEDOWN ACC", "{:.0%}"),
    ("td_per_fight", "TAKEDOWNS/FIGHT", "{:.2f}"),
    ("sub_per_fight", "SUB ATT/FIGHT", "{:.2f}"),
]
MIN_FIGHTS_FOR_RANKING = 3  # mínimo de lutas com estatística para entrar no percentil

KEY = ["espn_id", "event_uid"]


def _read(name):
    return pd.read_csv(DATA_DIR / name, encoding="utf-8-sig", dtype={"espn_id": str})


def method_group(decision):
    d = str(decision).lower()
    if "no contest" in d or "draw" in d or "dq" in d or "disqualif" in d:
        return "OTHER"
    if "ko" in d:
        return "KO/TKO"
    if "sub" in d:
        return "SUB"
    if "dec" in d:
        return "DEC"
    return "OTHER"


def rank_order(rank):
    return 0 if rank == "C" else int(rank)


def _per_fight_stats():
    striking = _read("stats_striking.csv")
    clinch = _read("stats_clinch.csv")
    ground = _read("stats_ground.csv")
    cols_c = KEY + ["TDL", "TDA", "SCHL", "SCBL", "SCLL"]
    cols_g = KEY + ["SM", "SGHL", "SGBL", "SGLL"]
    df = striking.merge(clinch[cols_c], on=KEY, how="left").merge(ground[cols_g], on=KEY, how="left")

    num = ["SSL", "SSA", "TSL", "TSA", "KD", "TDL", "TDA", "SM"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    # Lutas antigas / fora do UFC vêm zeradas: só conta luta com algum golpe ou queda tentada
    df = df[(df["TSA"].fillna(0) + df["TDA"].fillna(0)) > 0].copy()
    return df


def _attributes(stats):
    g = stats.groupby("espn_id")
    agg = pd.DataFrame({
        "fights_with_stats": g.size(),
        "SSL": g["SSL"].sum(), "SSA": g["SSA"].sum(), "KD": g["KD"].sum(),
        "TDL": g["TDL"].sum(), "TDA": g["TDA"].sum(), "SM": g["SM"].sum(),
    })
    n = agg["fights_with_stats"]
    agg["str_acc"] = agg["SSL"] / agg["SSA"].replace(0, np.nan)
    agg["sig_per_fight"] = agg["SSL"] / n
    agg["kd_per_fight"] = agg["KD"] / n
    agg["td_acc"] = agg["TDL"] / agg["TDA"].replace(0, np.nan)
    agg["td_per_fight"] = agg["TDL"] / n
    agg["sub_per_fight"] = agg["SM"] / n

    eligible = agg[n >= MIN_FIGHTS_FOR_RANKING]
    for col, _, _ in ATTRIBUTES:
        agg[col + "_pct"] = agg[col].apply(
            lambda v, ref=eligible[col].dropna(): np.nan if pd.isna(v) else (ref < v).mean() + (ref == v).mean() / 2
        )
    return agg


def load():
    ranked = _read("ranked_fighters.csv")
    ranked = ranked[ranked["espn_id"].notna()].copy()
    bio = _read("bio.csv").drop(columns=["fighter", "ufc_division", "ufc_rank"])
    fighters = ranked.merge(bio, on="espn_id", how="left")
    fighters["rank_order"] = fighters["rank"].map(rank_order)
    fighters["sprite"] = fighters["espn_id"].map(
        lambda i: f"/assets/sprites/{i}.png" if (SPRITE_DIR / f"{i}.png").exists()
        else "/assets/sprites/unknown.png")
    fighters = fighters.sort_values(["division", "rank_order"])

    history = _read("fight_history.csv")
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history["method"] = history["decision"].map(method_group)
    history = history.drop_duplicates(KEY).sort_values("date", ascending=False)

    stats = _per_fight_stats().drop_duplicates(KEY)
    attrs = _attributes(stats)
    return fighters, history, stats, attrs


FIGHTERS, HISTORY, STATS, ATTRS = load()


def fighters_in(division):
    return FIGHTERS[FIGHTERS["division"] == division]


def fighter(espn_id):
    rows = FIGHTERS[FIGHTERS["espn_id"] == espn_id]
    return rows.iloc[0] if len(rows) else None


def history_of(espn_id):
    return HISTORY[HISTORY["espn_id"] == espn_id]


def stats_of(espn_id):
    return STATS[STATS["espn_id"] == espn_id].sort_values("date")


def attributes_of(espn_id):
    return ATTRS.loc[espn_id] if espn_id in ATTRS.index else None
