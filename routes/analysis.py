"""
routes/analysis.py
Analyse IA d'un match via l'API Anthropic Claude.
Dépendance : pip install anthropic  (ajouter dans requirements.txt)
Variable d'environnement requise : ANTHROPIC_API_KEY (dans Render env vars)
"""
import os
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Match

router = APIRouter()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")


def build_stats_summary(match: Match) -> dict:
    """Agrège les stats par joueuse sur tous les sets du match."""
    player_totals = {}
    sets_info = []

    for st in match.sets:
        sets_info.append({
            "num": st.num,
            "scoreA": st.score_a,
            "scoreB": st.score_b,
            "won": st.score_a > st.score_b
        })
        for ps in st.stats:
            nom = ps.nom
            s = ps.stats or {}
            if nom not in player_totals:
                player_totals[nom] = {
                    "sets_joues": 0, "titulaire": s.get("titulaire", True),
                    "SG": 0, "S+": 0, "S0": 0, "S-": 0,
                    "R++": 0, "R+": 0, "R0": 0, "R-": 0,
                    "A+": 0, "A0": 0, "A-": 0,
                    "B+": 0, "Bdef": 0, "B-": 0,
                    "P+": 0, "P0": 0, "P-": 0,
                    "D+": 0, "D-": 0, "FF": 0,
                }
            t = player_totals[nom]
            t["sets_joues"] += 1
            for k in ["SG","S+","S0","S-","R++","R+","R0","R-","A+","A0","A-","B+","Bdef","B-","P+","P0","P-","D+","D-","FF"]:
                t[k] += int(s.get(k, 0))

    # Calculer PG, FD, rapport pour chaque joueuse
    for nom, t in player_totals.items():
        t["PG"] = t["SG"] + t["A+"] + t["B+"]
        t["FD"] = t["S-"] + t["A-"] + t["R0"]
        total = t["PG"] + t["FD"]
        t["rapport"] = round(t["PG"] / total * 100) if total > 0 else 0

    return {"sets": sets_info, "joueurs": player_totals}


def build_prompt(match: Match, context: str = "") -> str:
    data = build_stats_summary(match)
    sets = data["sets"]
    joueurs = data["joueurs"]

    sets_won = sum(1 for s in sets if s["won"])
    sets_lost = sum(1 for s in sets if not s["won"])
    result_str = "Victoire" if sets_won > sets_lost else "Défaite"
    score_sets = f"{sets_won}-{sets_lost}"
    detail_sets = " | ".join(f"S{s['num']}: {s['scoreA']}-{s['scoreB']}" for s in sets)

    # Construire tableau stats lisible
    lines = [
        f"MATCH : {match.equipe_a} vs {match.equipe_b} — {result_str} {score_sets}",
        f"Date : {match.date}",
        f"Sets : {detail_sets}",
        "",
        f"{'Joueuse':<22} {'Jeux':>4} {'PG':>4} {'FD':>4} {'Rapp':>5} {'SG':>3} {'S-':>3} {'R++':>4} {'R+':>3} {'R0':>3} {'A+':>3} {'A-':>3} {'B+':>3} {'P+':>4}",
        "-" * 90,
    ]
    for nom, t in sorted(joueurs.items(), key=lambda x: -x[1]["PG"]):
        lines.append(
            f"{nom:<22} {t['sets_joues']:>4} {t['PG']:>4} {t['FD']:>4} {t['rapport']:>4}% "
            f"{t['SG']:>3} {t['S-']:>3} {t['R++']:>4} {t['R+']:>3} {t['R0']:>3} "
            f"{t['A+']:>3} {t['A-']:>3} {t['B+']:>3} {t['P+']:>4}"
        )
    team_pg = sum(t["PG"] for t in joueurs.values())
    team_fd = sum(t["FD"] for t in joueurs.values())
    total = team_pg + team_fd
    team_rapport = round(team_pg / total * 100) if total > 0 else 0
    lines.append("-" * 90)
    lines.append(f"{'ÉQUIPE':<22} {'':>4} {team_pg:>4} {team_fd:>4} {team_rapport:>4}%")

    stats_text = "\n".join(lines)
    equipe_name = match.equipe_b if match.equipe_a != "Bailleul" else match.equipe_a

    prompt = f"""Tu es un analyste sportif expert en volleyball de haut niveau (Nationale 2 Féminine française). Tu travailles pour Deblock Sylvain, entraîneur du VBC Bailleulois.

Voici les statistiques complètes du match à analyser :

{stats_text}

{f"Contexte additionnel fourni par le coach : {context}" if context else ""}

LÉGENDE des colonnes :
- PG = Points Gagnants (SG + A+ + B+)
- FD = Fautes Directes (S- + A- + R0)
- Rapp = Rapport PG/(PG+FD) en %
- SG = Service Gagnant | S- = Faute Service
- R++ = Réception excellente | R+ = Bonne réception | R0 = Réception faute directe
- A+ = Attaque gagnante | A- = Attaque faute
- B+ = Bloc point | P+ = Passe parfaite

Génère une analyse sportive complète, factuelle et actionnable. Sois précis en t'appuyant TOUJOURS sur les chiffres exacts. Réponds UNIQUEMENT en JSON valide selon cette structure :

{{
  "verdict": "Résumé percutant en 1 phrase avec le score et le résultat",
  "note_globale": 7,
  "bilan_general": "Analyse synthétique en 3-4 phrases (performance collective, points saillants, contexte tactique observé dans les chiffres)",
  "points_forts": [
    {{"titre": "Titre court (3-5 mots)", "detail": "Explication avec chiffres précis à l'appui", "icone": "✅"}},
    {{"titre": "Titre court", "detail": "Explication avec chiffres", "icone": "✅"}},
    {{"titre": "Titre court", "detail": "Explication avec chiffres", "icone": "✅"}}
  ],
  "axes_amelioration": [
    {{"titre": "Titre court", "detail": "Problème identifié + recommandation d'entraînement concrète", "icone": "⚠️"}},
    {{"titre": "Titre court", "detail": "Problème + recommandation", "icone": "⚠️"}},
    {{"titre": "Titre court", "detail": "Problème + recommandation", "icone": "⚠️"}}
  ],
  "joueuse_du_match": {{
    "nom": "Prénom Nom",
    "justification": "Justification chiffrée en 2 phrases pourquoi elle mérite ce titre"
  }},
  "analyse_par_secteur": {{
    "service": {{"resume": "Synthèse service équipe", "note": 7, "detail": "Analyse détaillée avec chiffres"}},
    "reception": {{"resume": "Synthèse réception", "note": 7, "detail": "Analyse détaillée avec chiffres"}},
    "attaque": {{"resume": "Synthèse attaque", "note": 7, "detail": "Analyse détaillée avec chiffres"}},
    "bloc_defense": {{"resume": "Synthèse bloc/défense", "note": 7, "detail": "Analyse détaillée avec chiffres"}}
  }},
  "focus_joueuses": [
    {{"nom": "Prénom Nom", "role": "Passeuse/Attaquante/Libéro/etc", "analyse": "Analyse individuelle concise avec ses stats clés", "conseil": "1 conseil technique personnalisé"}},
    {{"nom": "Prénom Nom", "role": "...", "analyse": "...", "conseil": "..."}},
    {{"nom": "Prénom Nom", "role": "...", "analyse": "...", "conseil": "..."}}
  ],
  "recommandations_seance": [
    "Exercice ou point technique prioritaire 1 — avec justification chiffrée",
    "Exercice ou point technique prioritaire 2",
    "Exercice ou point technique prioritaire 3"
  ],
  "message_equipe": "Message motivant du coach à l'équipe (3-4 phrases, ton positif et exigeant)"
}}"""
    return prompt


@router.post("/{match_id}")
async def analyze_match(
    match_id: str,
    payload: dict = {},
    db: Session = Depends(get_db),
):
    """Analyse IA d'un match via Claude. Payload optionnel : {"context": "infos supplémentaires"}"""
    if not ANTHROPIC_KEY:
        raise HTTPException(
            503,
            detail="ANTHROPIC_API_KEY non configurée. Ajoute-la dans les Variables d'environnement de Render (Settings > Environment)."
        )

    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(404, detail="Match introuvable")

    has_stats = any(
        len(st.stats) > 0 and any(
            any(int(v) > 0 for k, v in (ps.stats or {}).items() if k not in ("titulaire",) and isinstance(v, (int, float, str)) and str(v).isdigit())
            for ps in st.stats
        )
        for st in m.sets
    )
    if not m.sets:
        raise HTTPException(400, detail="Ce match n'a pas encore de sets enregistrés.")

    try:
        import anthropic
    except ImportError:
        raise HTTPException(500, detail="Package 'anthropic' non installé — ajoute 'anthropic' à requirements.txt")

    context = payload.get("context", "") if isinstance(payload, dict) else ""
    prompt = build_prompt(m, context)

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()

        # Extraire le JSON si entouré de ```json ... ```
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        analysis = json.loads(raw)
        analysis["_meta"] = {
            "match_id": str(m.id),
            "equipeA": m.equipe_a,
            "equipeB": m.equipe_b,
            "date": m.date.isoformat(),
        }
        return analysis

    except json.JSONDecodeError as e:
        raise HTTPException(500, detail=f"Réponse IA invalide (JSON malformé) : {str(e)[:200]}")
    except Exception as e:
        err = str(e)
        if "authentication" in err.lower() or "api_key" in err.lower():
            raise HTTPException(401, detail="Clé API Anthropic invalide. Vérifie ANTHROPIC_API_KEY dans Render.")
        raise HTTPException(500, detail=f"Erreur API Claude : {err[:300]}")
