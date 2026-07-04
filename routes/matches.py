from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Match, Set, PlayerStat
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import date as date_type

router = APIRouter()


# ── Schémas ────────────────────────────────────────────────────────────────

class PlayerStatIn(BaseModel):
    nom: str
    titulaire: bool = True
    stats: Dict[str, Any] = {}

class SetIn(BaseModel):
    num: int
    scoreA: int = 0
    scoreB: int = 0
    stats: List[PlayerStatIn] = []

class MatchIn(BaseModel):
    date: date_type
    equipeA: str
    equipeB: str
    season_id: Optional[str] = None
    sets: List[SetIn]

class StatUpdateIn(BaseModel):
    nom: str
    setNum: int
    stats: Dict[str, Any]

class ScoreUpdateItem(BaseModel):
    num: int
    scoreA: int = 0
    scoreB: int = 0


# ── Sérialisation ──────────────────────────────────────────────────────────

def serialize_match(m: Match):
    return {
        "id": str(m.id),
        "date": m.date.isoformat(),
        "equipeA": m.equipe_a,
        "equipeB": m.equipe_b,
        "season_id": str(m.season_id) if m.season_id else None,
        "sets": [
            {
                "id": str(st.id),
                "num": st.num,
                "scoreA": st.score_a,
                "scoreB": st.score_b,
                "stats": [
                    {"id": str(ps.id), "nom": ps.nom, **(ps.stats or {})}
                    for ps in st.stats
                ],
            }
            for st in m.sets
        ],
    }


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/")
def list_matches(db: Session = Depends(get_db)):
    matches = db.query(Match).order_by(Match.date.desc()).all()
    return [serialize_match(m) for m in matches]


@router.get("/{match_id}")
def get_match(match_id: str, db: Session = Depends(get_db)):
    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(404, "Match introuvable")
    return serialize_match(m)


@router.post("/")
def create_match(payload: MatchIn, db: Session = Depends(get_db)):
    import uuid as uuid_mod
    season_id = None
    if payload.season_id:
        try:
            season_id = uuid_mod.UUID(payload.season_id)
        except Exception:
            season_id = None

    m = Match(
        date=payload.date,
        equipe_a=payload.equipeA,
        equipe_b=payload.equipeB,
        season_id=season_id,
    )
    db.add(m)
    db.flush()

    for s_in in payload.sets:
        st = Set(
            match_id=m.id,
            num=s_in.num,
            score_a=s_in.scoreA,
            score_b=s_in.scoreB,
        )
        db.add(st)
        db.flush()
        for p_in in s_in.stats:
            blob = {**p_in.stats, "titulaire": p_in.titulaire}
            db.add(PlayerStat(set_id=st.id, nom=p_in.nom, stats=blob))

    db.commit()
    db.refresh(m)
    return serialize_match(m)


@router.delete("/{match_id}")
def delete_match(match_id: str, db: Session = Depends(get_db)):
    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(404, "Match introuvable")
    db.delete(m)
    db.commit()
    return {"ok": True}


# ── PATCH scores ────────────────────────────────────────────────────────────
@router.patch("/{match_id}/scores")
def update_scores(
    match_id: str,
    payload: List[ScoreUpdateItem],
    db: Session = Depends(get_db),
):
    """Met à jour les scores par set d'un match."""
    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(404, "Match introuvable")

    for item in payload:
        st = next((s for s in m.sets if s.num == item.num), None)
        if st:
            st.score_a = item.scoreA
            st.score_b = item.scoreB
        else:
            # Créer le set s'il n'existe pas encore
            new_set = Set(
                match_id=m.id,
                num=item.num,
                score_a=item.scoreA,
                score_b=item.scoreB,
            )
            db.add(new_set)

    db.commit()
    db.refresh(m)
    return serialize_match(m)


# ── PATCH stats d'une joueuse pour un set ───────────────────────────────────
@router.patch("/{match_id}/stats")
def update_player_stats(
    match_id: str,
    payload: StatUpdateIn,
    db: Session = Depends(get_db),
):
    """
    Met à jour (ou crée) les stats d'une joueuse pour un set donné.
    Payload : { nom, setNum, stats: {SG, S+, …, PG, FD, …} }
    """
    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(404, "Match introuvable")

    # Trouver le set
    target_set = next((s for s in m.sets if s.num == payload.setNum), None)
    if not target_set:
        # Créer le set si absent
        target_set = Set(
            match_id=m.id,
            num=payload.setNum,
            score_a=0,
            score_b=0,
        )
        db.add(target_set)
        db.flush()

    # Trouver la ligne PlayerStat existante
    ps = next((p for p in target_set.stats if p.nom == payload.nom), None)

    if ps:
        # Mettre à jour le blob JSON existant
        current = dict(ps.stats or {})
        current.update(payload.stats)
        ps.stats = current
        # SQLAlchemy ne détecte pas forcément le changement d'un JSON → forcer
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(ps, "stats")
    else:
        # Créer une nouvelle ligne
        db.add(PlayerStat(
            set_id=target_set.id,
            nom=payload.nom,
            stats=payload.stats,
        ))

    db.commit()
    db.refresh(m)
    return serialize_match(m)
