from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Season
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter()


# ── Schémas ────────────────────────────────────────────────────────────────

class SeasonIn(BaseModel):
    nom: str
    club: Optional[str] = "VBC Bailleulois"
    division: Optional[str] = "N3F"
    poule: Optional[str] = ""
    active: bool = False
    roster: List[Dict[str, Any]] = []


class SeasonUpdate(BaseModel):
    nom: Optional[str] = None
    club: Optional[str] = None
    division: Optional[str] = None
    poule: Optional[str] = None
    active: Optional[bool] = None
    roster: Optional[List[Dict[str, Any]]] = None


# ── Sérialisation ──────────────────────────────────────────────────────────

def serialize_season(s: Season):
    return {
        "id": str(s.id),
        "nom": s.nom,
        "club": s.club,
        "division": s.division,
        "poule": s.poule,
        "active": s.active,
        "roster": s.roster,
    }


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/")
def list_seasons(db: Session = Depends(get_db)):
    seasons = db.query(Season).order_by(Season.nom.desc()).all()
    return [serialize_season(s) for s in seasons]


@router.get("/{season_id}")
def get_season(season_id: str, db: Session = Depends(get_db)):
    s = db.query(Season).filter(Season.id == season_id).first()
    if not s:
        raise HTTPException(404, "Saison introuvable")
    return serialize_season(s)


@router.post("/")
def create_season(payload: SeasonIn, db: Session = Depends(get_db)):
    s = Season(**payload.dict())
    db.add(s)
    db.commit()
    db.refresh(s)
    return serialize_season(s)


@router.patch("/{season_id}")
def update_season(season_id: str, payload: SeasonUpdate, db: Session = Depends(get_db)):
    s = db.query(Season).filter(Season.id == season_id).first()
    if not s:
        raise HTTPException(404, "Saison introuvable")
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(s, key, value)
    db.commit()
    db.refresh(s)
    return serialize_season(s)


@router.delete("/{season_id}")
def delete_season(season_id: str, db: Session = Depends(get_db)):
    s = db.query(Season).filter(Season.id == season_id).first()
    if not s:
        raise HTTPException(404, "Saison introuvable")
    db.delete(s)
    db.commit()
    return {"ok": True}
