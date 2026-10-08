from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Season, Match
from pydantic import BaseModel
from typing import List, Optional, Any

router = APIRouter()

# ── Schémas Pydantic ───────────────────────────────────────────────────────

class PlayerIn(BaseModel):
    number: int
    prenom: str
    nom: str
    poste: str = ""

class SeasonIn(BaseModel):
    nom: str
    club: str = "VBC Bailleulois"
    division: str = "N3F"
    poule: str = ""
    active: bool = False
    roster: List[Any] = []

class SeasonPatch(BaseModel):
    nom: Optional[str] = None
    club: Optional[str] = None
    division: Optional[str] = None
    poule: Optional[str] = None
    active: Optional[bool] = None
    roster: Optional[List[Any]] = None

# ── Sérialisation ──────────────────────────────────────────────────────────

def serialize_season(s: Season, match_count: int = 0):
    return {
        "id":        str(s.id),
        "nom":       s.nom,
        "club":      s.club,
        "division":  s.division,
        "poule":     s.poule,
        "active":    s.active,
        "roster":    s.roster or [],
        "matchCount": match_count,
    }

# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/")
def list_seasons(db: Session = Depends(get_db)):
    seasons = db.query(Season).order_by(Season.nom.desc()).all()
    result = []
    for s in seasons:
        count = db.query(Match).filter(Match.season_id == s.id).count()
        result.append(serialize_season(s, count))
    return result


@router.get("/active")
def get_active_season(db: Session = Depends(get_db)):
    s = db.query(Season).filter(Season.active == True).first()
    if not s:
        return None
    count = db.query(Match).filter(Match.season_id == s.id).count()
    return serialize_season(s, count)


@router.get("/{season_id}")
def get_season(season_id: str, db: Session = Depends(get_db)):
    s = db.query(Season).filter(Season.id == season_id).first()
    if not s:
        raise HTTPException(404, "Saison introuvable")
    count = db.query(Match).filter(Match.season_id == s.id).count()
    return serialize_season(s, count)


@router.post("/")
def create_season(payload: SeasonIn, db: Session = Depends(get_db)):
    # Si la nouvelle saison est active, désactiver les autres
    if payload.active:
        db.query(Season).update({"active": False})
    s = Season(
        nom=payload.nom, club=payload.club, division=payload.division,
        poule=payload.poule, active=payload.active, roster=payload.roster,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return serialize_season(s)


@router.patch("/{season_id}")
def update_season(season_id: str, payload: SeasonPatch, db: Session = Depends(get_db)):
    s = db.query(Season).filter(Season.id == season_id).first()
    if not s:
        raise HTTPException(404, "Saison introuvable")
    # Si on active cette saison, désactiver les autres
    if payload.active is True:
        db.query(Season).filter(Season.id != season_id).update({"active": False})
    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(s, field, val)
    db.commit()
    db.refresh(s)
    count = db.query(Match).filter(Match.season_id == s.id).count()
    return serialize_season(s, count)


@router.delete("/{season_id}")
def delete_season(season_id: str, db: Session = Depends(get_db)):
    s = db.query(Season).filter(Season.id == season_id).first()
    if not s:
        raise HTTPException(404, "Saison introuvable")
    count = db.query(Match).filter(Match.season_id == s.id).count()
    if count > 0:
        raise HTTPException(400, f"Impossible de supprimer : {count} match(s) rattaché(s) à cette saison.")
    db.delete(s)
    db.commit()
    return {"ok": True}
