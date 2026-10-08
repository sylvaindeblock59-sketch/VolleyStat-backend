"""
routes/import_ffvb.py
Parse une feuille de match FFVB (PDF) et retourne les données structurées.
Dépendance : pip install pdfplumber python-multipart
"""

import re
import io
import base64
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Match, Set, PlayerStat
import uuid

router = APIRouter()

# ── Mapping de noms de colonnes stats FFVB → codes internes ────────────────
STAT_COL_MAP = {
    # Service
    "sg": "SG", "ace": "SG", "as": "SG", "ace(s)": "SG",
    "s+": "S+", "serv+": "S+", "eff.s": "S+",
    "s0": "S0", "s 0": "S0",
    "s-": "S-", "serv-": "S-", "eff.s-": "S-", "fs": "S-", "sfaute": "S-",
    # Réception
    "r++": "R++", "rec++": "R++", "rcp++": "R++", "parfait": "R++",
    "r+": "R+", "rec+": "R+", "rcp+": "R+",
    "r0": "R0", "rec0": "R0", "rcp0": "R0",
    "r-": "R-", "rec-": "R-", "rcp-": "R-",
    # Attaque
    "a+": "A+", "att+": "A+", "kill": "A+", "attgagnante": "A+",
    "a0": "A0", "att0": "A0",
    "a-": "A-", "att-": "A-", "attfaute": "A-",
    # Bloc
    "b+": "B+", "blc+": "B+", "blgagnant": "B+",
    "bdef": "Bdef", "bd": "Bdef", "b0": "Bdef", "blcdef": "Bdef",
    "b-": "B-", "blc-": "B-",
    # Passe
    "p+": "P+", "pas+": "P+",
    "p0": "P0", "pas0": "P0",
    "p-": "P-", "pas-": "P-",
    # Défense
    "d+": "D+", "def+": "D+",
    "d-": "D-", "def-": "D-",
}

def norm(s: str) -> str:
    """Normalise une chaîne pour correspondance."""
    return re.sub(r"[\s\.\(\)\-_/]", "", str(s)).lower()

def map_col(raw: str):
    return STAT_COL_MAP.get(norm(raw))


# ── Parser principal ────────────────────────────────────────────────────────

def parse_ffvb_pdf(content: bytes) -> dict:
    """
    Extrait les informations d'une feuille de match FFVB.
    Retourne un dict avec : meta, set_scores, players_a, players_b, stats_tables, raw_text, confidence.
    """
    try:
        import pdfplumber
    except ImportError:
        raise HTTPException(500, "pdfplumber non installé — ajoute-le à requirements.txt")

    result = {
        "date": None,
        "equipeA": None,
        "equipeB": None,
        "competition": None,
        "division": None,
        "poule": None,
        "set_scores": [],        # [{scoreA, scoreB}]
        "players_a": [],         # [{number, nom, prenom}]
        "players_b": [],         # [{number, nom, prenom}]
        "stats_tables": [],      # [{set_num, players: [{nom, ...stat fields}]}]
        "raw_text": "",
        "warnings": [],
        "confidence": "low",
    }

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        all_text = ""
        all_tables = []

        for page in pdf.pages:
            text = page.extract_text() or ""
            all_text += text + "\n---PAGE---\n"
            tables = page.extract_tables() or []
            all_tables.extend(tables)

        result["raw_text"] = all_text

        # ── 1. Date ──────────────────────────────────────────────────────
        date_match = re.search(r'\b(\d{2})[/\-](\d{2})[/\-](\d{2,4})\b', all_text)
        if date_match:
            d, m, y = date_match.groups()
            y = y if len(y) == 4 else "20" + y
            result["date"] = f"{y}-{m}-{d}"

        # ── 2. Division / Compétition ────────────────────────────────────
        div_match = re.search(r'(NATIONALE?\s*[23]?[A-Z]?F?|N[23]F|NAT\s*[23]|REGIONAL|R[123]F?)',
                              all_text, re.IGNORECASE)
        if div_match:
            result["division"] = div_match.group(1).strip().upper()

        poule_match = re.search(r'POULE\s+([A-Z0-9]+)', all_text, re.IGNORECASE)
        if poule_match:
            result["poule"] = "Poule " + poule_match.group(1).upper()

        comp_match = re.search(r'(?:NOM DE LA |COMP[ÉE]TITION\s*:?\s*)([^\n]{5,60})', all_text, re.IGNORECASE)
        if comp_match:
            result["competition"] = comp_match.group(1).strip()

        # ── 3. Équipes ────────────────────────────────────────────────────
        # Chercher "EQUIPES" suivi des noms
        teams_match = re.search(
            r'EQUIPES?\s*\n?\s*([A-ZÀ-Ÿ][A-ZÀ-Ÿ0-9\s\-\.]{2,40}?)\s*(?:A\s+ou\s+B\s+)?([A-ZÀ-Ÿ][A-ZÀ-Ÿ0-9\s\-\.]{2,40})',
            all_text, re.IGNORECASE
        )
        if teams_match:
            result["equipeA"] = teams_match.group(1).strip().title()
            result["equipeB"] = teams_match.group(2).strip().title()
        else:
            # Fallback : chercher deux noms en majuscules encadrés par "VS" ou "/"
            vs_match = re.search(r'([A-ZÀ-Ÿ][A-ZÀ-Ÿ\s]{3,30})\s+(?:VS?|\/)\s+([A-ZÀ-Ÿ][A-ZÀ-Ÿ\s]{3,30})',
                                  all_text, re.IGNORECASE)
            if vs_match:
                result["equipeA"] = vs_match.group(1).strip().title()
                result["equipeB"] = vs_match.group(2).strip().title()

        # ── 4. Scores par set ─────────────────────────────────────────────
        # Pattern : séquences de type "25 23" ou "( 25 )" dans une ligne résultats
        score_lines = re.findall(
            r'\b(2[0-9]|3[012])\s+(2[0-9]|3[012])\b|\b([1-2][0-9])\s*[:\-]\s*([1-2][0-9])\b',
            all_text
        )
        seen_scores = []
        for groups in score_lines:
            a = int(groups[0] or groups[2])
            b = int(groups[1] or groups[3])
            if (a, b) not in seen_scores and (max(a, b) >= 15):
                seen_scores.append((a, b))
        result["set_scores"] = [{"scoreA": a, "scoreB": b} for a, b in seen_scores[:5]]

        # ── 5. Listes des joueuses ─────────────────────────────────────────
        # Pattern : numéro (1-2 chiffres) + NOM en majuscules
        player_line = re.compile(
            r'^\s*(\d{1,2})\s+([A-ZÀ-Ÿ][A-ZÀ-Ÿ\s\-\']{2,30}?)(?:\s+\d{6,})?$',
            re.MULTILINE
        )
        all_players = []
        for m in player_line.finditer(all_text):
            num = int(m.group(1))
            name = m.group(2).strip().title()
            if name and len(name) > 2:
                all_players.append({"number": num, "nom": name})

        # Dédupliquer (même numéro/nom peut apparaître deux fois dans le PDF)
        seen = set()
        unique_players = []
        for p in all_players:
            key = (p["number"], p["nom"][:6])
            if key not in seen:
                seen.add(key)
                unique_players.append(p)

        # Répartir entre équipe A (première moitié) et B (deuxième moitié)
        mid = len(unique_players) // 2 if len(unique_players) > 4 else len(unique_players)
        result["players_a"] = unique_players[:mid]
        result["players_b"] = unique_players[mid:]

        # ── 6. Tables de statistiques (si présentes) ──────────────────────
        for table in all_tables:
            if len(table) < 3 or not table[0]:
                continue
            header = [str(c or "").strip() for c in table[0]]
            mapped_cols = {j: map_col(h) for j, h in enumerate(header) if map_col(h)}
            if len(mapped_cols) < 3:
                continue  # pas une table de stats

            # Identifier la colonne nom
            nom_col = next(
                (j for j, h in enumerate(header) if any(w in norm(h) for w in ["nom", "joueuse", "name", "player"])),
                None
            )
            num_col = next(
                (j for j, h in enumerate(header) if re.match(r'^n[o°]?$', norm(h))),
                0
            )

            players_stats = []
            for row in table[1:]:
                if not row or not row[0]:
                    continue
                first = str(row[0] or "").strip()
                if not re.match(r'^\d{1,2}$', first):
                    continue
                p = {"number": int(first)}
                if nom_col is not None and nom_col < len(row):
                    p["nom"] = str(row[nom_col] or "").strip().title()
                for j, field in mapped_cols.items():
                    if j < len(row):
                        try:
                            p[field] = int(str(row[j] or 0).strip() or 0)
                        except ValueError:
                            p[field] = 0
                players_stats.append(p)

            if players_stats:
                result["stats_tables"].append({"players": players_stats, "columns": list(mapped_cols.values())})

    # ── Confiance ──────────────────────────────────────────────────────────
    score = sum([
        2 if result["equipeA"] and result["equipeB"] else 0,
        2 if result["set_scores"] else 0,
        1 if result["date"] else 0,
        1 if result["players_a"] else 0,
        2 if result["stats_tables"] else 0,
    ])
    result["confidence"] = "high" if score >= 6 else "medium" if score >= 3 else "low"

    return result


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/parse")
async def parse_fdm(file: UploadFile = File(...)):
    """
    Reçoit un PDF FFVB et retourne les données extraites (sans créer de match).
    Permet au frontend de montrer un aperçu éditable avant import.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Fichier PDF attendu.")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:  # 20 MB max
        raise HTTPException(400, "Fichier trop volumineux (20 MB max).")
    try:
        data = parse_ffvb_pdf(content)
        # Encoder le PDF en base64 pour stockage optionnel
        data["pdf_b64"] = base64.b64encode(content).decode("utf-8")
        return data
    except Exception as e:
        raise HTTPException(500, f"Erreur d'analyse du PDF : {str(e)}")


@router.post("/create-match")
async def create_match_from_fdm(payload: dict, db: Session = Depends(get_db)):
    """
    Crée un match à partir des données confirmées par l'utilisateur.
    Payload : {date, equipeA, equipeB, season_id, set_scores, players, pdf_b64?}
    """
    from datetime import date as date_type

    try:
        match_date = date_type.fromisoformat(payload["date"])
    except Exception:
        raise HTTPException(400, "Date invalide (format attendu : YYYY-MM-DD).")

    m = Match(
        date=match_date,
        equipe_a=payload["equipeA"],
        equipe_b=payload["equipeB"],
        season_id=payload.get("season_id"),
        fdm_pdf=payload.get("pdf_b64"),   # stockage optionnel du PDF encodé
    )
    db.add(m)
    db.flush()

    set_scores = payload.get("set_scores", [])
    players = payload.get("players", [])

    for i, sc in enumerate(set_scores):
        st = Set(
            match_id=m.id,
            num=i + 1,
            score_a=sc.get("scoreA", 0),
            score_b=sc.get("scoreB", 0),
        )
        db.add(st)
        db.flush()
        for p in players:
            db.add(PlayerStat(
                set_id=st.id,
                nom=p.get("nom", "Inconnue"),
                stats={"titulaire": True, "SG": 0, "S+": 0, "S0": 0, "S-": 0,
                       "R++": 0, "R+": 0, "R0": 0, "R-": 0, "A+": 0, "A0": 0, "A-": 0,
                       "B+": 0, "Bdef": 0, "B-": 0, "P+": 0, "P0": 0, "P-": 0,
                       "D+": 0, "D-": 0, "FF": 0, "PG": 0, "FD": 0},
            ))

    db.commit()
    db.refresh(m)

    from routes.matches import serialize_match
    return serialize_match(m)
