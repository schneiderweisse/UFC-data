"""
Extração de dados de lutadores da ESPN (Stats, Fight History e Bio).

Fluxo:
  1. Lê o ranking oficial de ufc.com/rankings (8 divisões masculinas).
  2. Encontra o ID ESPN de cada lutador pela API de busca da ESPN.
  3. Baixa os dados de cada lutador pela API JSON pública da ESPN (a mesma que
     alimenta as abas Stats / Fight History / Bio de
     espn.com/mma/fighter/_/id/<id>):
       - /athletes/<id>        -> Bio + Fight History
       - /athletes/<id>/stats  -> tabelas Striking, Clinch e Ground
  4. Salva tudo em CSV na pasta "Fighter data".

Uso:
  py scrape_espn_fighters.py
"""

import csv
import re
import time
import unicodedata
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "Fighter data"

DELAY = 0.7  # segundos entre requisições, para não sobrecarregar os servidores

UFC_RANKINGS_URL = "https://www.ufc.com/rankings"
ESPN_SEARCH_URL = "https://site.web.api.espn.com/apis/search/v2"
ESPN_ATHLETE_URL = "https://site.web.api.espn.com/apis/common/v3/sports/mma/athletes/{id}"

# Ordem dos blocos em ufc.com/rankings: [P4P masculino, 8 divisões masculinas, P4P feminino, ...]
# O site pode vir em português conforme a região, então mapeamos pela posição.
MEN_DIVISIONS = [
    "Flyweight", "Bantamweight", "Featherweight", "Lightweight",
    "Welterweight", "Middleweight", "Light Heavyweight", "Heavyweight",
]

session = requests.Session()


def get(url, **kwargs):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=30, **kwargs)
            r.raise_for_status()
            time.sleep(DELAY)
            return r
        except requests.RequestException as e:
            print(f"    tentativa {attempt + 1} falhou ({e})")
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Falha ao baixar {url}")


# ---------------------------------------------------------------- ranking UFC

def fetch_ranked_men():
    soup = BeautifulSoup(get(UFC_RANKINGS_URL).text, "html.parser")
    groups = soup.select(".view-grouping")
    if len(groups) < 9:
        raise RuntimeError("Layout de ufc.com/rankings mudou: menos de 9 blocos encontrados")

    fighters = []
    for division, group in zip(MEN_DIVISIONS, groups[1:9]):
        champ = group.select_one(".rankings--athlete--champion h5")
        if champ:
            fighters.append({"division": division, "rank": "C",
                             "name": champ.get_text(" ", strip=True)})
        for tr in group.select("tbody tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            fighters.append({"division": division,
                             "rank": cells[0].get_text(strip=True),
                             "name": cells[1].get_text(" ", strip=True)})
    return fighters


# ---------------------------------------------------------------- busca ESPN

def normalize(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", ascii_name.lower())


def find_espn_id(name):
    r = get(ESPN_SEARCH_URL, params={"query": name, "limit": 10, "type": "player"})
    players = []
    for block in r.json().get("results", []):
        if block.get("type") == "player":
            players += block.get("contents", [])
    exact = [p for p in players if normalize(p["displayName"]) == normalize(name)]
    mma = [p for p in players if p.get("sport") == "mma"]
    # Prioriza nome idêntico em MMA; depois qualquer resultado de MMA; por fim nome
    # idêntico em outro esporte (a ESPN usa o mesmo ID de atleta entre esportes,
    # ex.: Josh Hokit aparece como jogador da NFL na busca).
    candidates = [p for p in exact if p.get("sport") == "mma"] or mma or exact
    if not candidates:
        return None, None
    if len(candidates) > 1 and normalize(candidates[1]["displayName"]) == normalize(name):
        # Homônimos (ex.: há três "Jean Silva" de MMA): fica com quem tem mais lutas no UFC
        candidates = [max(candidates[:5], key=ufc_fight_count)]
    best = candidates[0]
    espn_id = best["uid"].split("~a:")[-1]
    return espn_id, best["displayName"]


def ufc_fight_count(player):
    espn_id = player["uid"].split("~a:")[-1]
    try:
        events = get(ESPN_ATHLETE_URL.format(id=espn_id)).json().get("eventsMap", {}).values()
    except RuntimeError:
        return -1
    return sum(1 for e in events if str(e.get("name", "")).startswith("UFC"))


# ---------------------------------------------------------------- dados ESPN

def link_href(links, rel):
    for link in links or []:
        if rel in link.get("rel", []):
            return link.get("href", "")
    return ""


def parse_bio(athlete, base):
    summary = {s["abbreviation"]: s["displayValue"]
               for s in (athlete.get("statsSummary") or {}).get("statistics", [])}
    return {
        **base,
        "nickname": athlete.get("nickname", ""),
        "country": athlete.get("citizenship", ""),
        "weight_class": (athlete.get("weightClass") or {}).get("text", ""),
        "height": athlete.get("displayHeight", ""),
        "weight": athlete.get("displayWeight", ""),
        "birthdate": athlete.get("displayDOB", ""),  # dia/mês/ano
        "age": athlete.get("age", ""),
        "reach": athlete.get("displayReach", ""),
        "stance": (athlete.get("stance") or {}).get("text", ""),
        "fighting_style": athlete.get("displayFightingStyle", ""),
        "team": (athlete.get("association") or {}).get("name", ""),
        "gender": athlete.get("gender", ""),
        "status": (athlete.get("status") or {}).get("name", ""),
        "record_w_l_d": summary.get("W-L-D", ""),
        "ko_tko_w_l": summary.get("(T)KO", ""),
        "sub_w_l": summary.get("SUB", ""),
    }


def parse_history(data, base):
    rows = []
    for uid in data.get("events", []):
        e = data["eventsMap"].get(uid, {})
        opp = e.get("opponent") or {}
        status = e.get("status") or {}
        rows.append({
            **base,
            "event_uid": uid,
            "date": (e.get("gameDate") or "")[:10],
            "opponent": opp.get("displayName", ""),
            "opponent_espn_id": opp.get("id", ""),
            "result": e.get("gameResult", ""),
            "decision": (status.get("result") or {}).get("displayName", ""),
            "round": status.get("period", ""),
            "time": status.get("displayClock", ""),
            "event": e.get("name", ""),
            "event_url": link_href(e.get("links"), "summary"),
            "title_fight": e.get("titleFight", False),
        })
    return rows


def parse_stats(stats, history_by_uid, base):
    """Retorna {nome_tabela: linhas} das tabelas striking / clinch / ground."""
    tables = {}
    for cat in stats.get("categories", []):
        name = cat["displayName"].strip().lower()
        cols = [c.strip() for c in cat["labels"]]
        rows = []
        for ev in cat.get("statistics", []):
            fight = history_by_uid.get(ev["uid"], {})
            rows.append({
                **base,
                "event_uid": ev["uid"],
                "date": fight.get("date", ""),
                "opponent": fight.get("opponent", ""),
                "event": fight.get("event", ""),
                "result": fight.get("result", ""),
                **dict(zip(cols, ev["stats"])),
            })
        tables[name] = rows
    return tables


# ---------------------------------------------------------------- CSV

def write_csv(path, rows, fieldnames=None):
    if not rows:
        print(f"  (sem linhas para {path.name})")
        return
    if fieldnames is None:
        fieldnames = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"  {path.name}: {len(rows)} linhas")


# ---------------------------------------------------------------- main

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Lendo ranking oficial do UFC...")
    ranked = fetch_ranked_men()
    print(f"  {len(ranked)} lutadores ranqueados (masculino)")

    bios, history, failed = [], [], []
    stats = {}       # nome_tabela -> linhas
    glossary = {}    # sigla -> descrição

    for i, f in enumerate(ranked, 1):
        print(f"[{i}/{len(ranked)}] {f['division']} #{f['rank']} {f['name']}")
        espn_id, espn_name = find_espn_id(f["name"])
        f["espn_id"] = espn_id or ""
        f["espn_name"] = espn_name or ""
        f["espn_url"] = f"https://www.espn.com/mma/fighter/_/id/{espn_id}" if espn_id else ""
        if not espn_id:
            print("    não encontrado na ESPN")
            failed.append(f)
            continue

        base = {"fighter": espn_name, "espn_id": espn_id,
                "ufc_division": f["division"], "ufc_rank": f["rank"]}
        try:
            data = get(ESPN_ATHLETE_URL.format(id=espn_id)).json()
            bios.append(parse_bio(data["athlete"], base))
            fights = parse_history(data, base)
            history.extend(fights)

            st = get(ESPN_ATHLETE_URL.format(id=espn_id) + "/stats").json()
            by_uid = {r["event_uid"]: r for r in fights}
            for name, rows in parse_stats(st, by_uid, base).items():
                stats.setdefault(name, []).extend(rows)
            for g in st.get("glossary", []):
                glossary[g["abbreviation"].strip()] = g["displayName"]
        except Exception as e:
            print(f"    ERRO: {e}")
            failed.append(f)

    print("\nSalvando CSVs...")
    write_csv(OUT_DIR / "ranked_fighters.csv", ranked)
    write_csv(OUT_DIR / "bio.csv", bios)
    write_csv(OUT_DIR / "fight_history.csv", history)
    for name, rows in stats.items():
        write_csv(OUT_DIR / f"stats_{name}.csv", rows)
    write_csv(OUT_DIR / "stats_glossary.csv",
              [{"column": k, "description": v} for k, v in sorted(glossary.items())])
    if failed:
        print(f"\nAtenção: {len(failed)} lutador(es) sem dados:")
        for f in failed:
            print(f"  - {f['division']} #{f['rank']} {f['name']}")


if __name__ == "__main__":
    main()
