from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Match, Set, PlayerStat
from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import date as date_type

router = APIRouter()


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
    sets: List[SetIn]


class StatUpdateIn(BaseModel):
    nom: str
    setNum: int
    stats: Dict[str, Any]


def serialize_match(m: Match):
    return {
        "id": str(m.id),
        "date": m.date.isoformat(),
        "equipeA": m.equipe_a,
        "equipeB": m.equipe_b,
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
    m = Match(date=payload.date, equipe_a=payload.equipeA, equipe_b=payload.equipeB)
    db.add(m)
    db.flush()
    for s_in in payload.sets:
        st = Set(match_id=m.id, num=s_in.num, score_a=s_in.scoreA, score_b=s_in.scoreB)
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


@router.patch("/{match_id}/stats")
def update_stat(match_id: str, payload: StatUpdateIn, db: Session = Depends(get_db)):
    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(404, "Match introuvable")
    st = next((s for s in m.sets if s.num == payload.setNum), None)
    if not st:
        raise HTTPException(404, "Set introuvable")
    ps = next((p for p in st.stats if p.nom == payload.nom), None)
    if ps:
        ps.stats = payload.stats
    else:
        db.add(PlayerStat(set_id=st.id, nom=payload.nom, stats=payload.stats))
    db.commit()
    db.refresh(m)
    return serialize_match(m)