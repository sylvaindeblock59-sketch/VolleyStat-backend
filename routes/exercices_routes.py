from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db
from models import (
    Exercice, ExerciceTag, Tag, Categorie, Niveau, Media, Variante,
    SessionEntrainement, SessionExercice, Joueuse, Presence,
)
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import date as date_type

router = APIRouter()


# ── Schémas ────────────────────────────────────────────────────────────────

class ExerciceIn(BaseModel):
    nom: str
    description: Optional[str] = None
    objectif_pedagogique: Optional[str] = None
    consignes_coaching: Optional[str] = None
    categorie_id: Optional[int] = None
    niveau_id: Optional[int] = None
    effectif_min: Optional[int] = None
    effectif_max: Optional[int] = None
    duree_min: Optional[int] = None
    materiel_necessaire: Optional[str] = None
    source_url: Optional[str] = None
    source_auteur: Optional[str] = None
    source_pays: Optional[str] = None
    source_type: Optional[str] = None
    schema_svg: Optional[str] = None
    tags: List[str] = []


class SessionExerciceIn(BaseModel):
    exercice_id: str
    ordre: int
    duree_allouee_min: Optional[int] = None
    notes_specifiques: Optional[str] = None


class SessionIn(BaseModel):
    nom: str
    date_prevue: Optional[date_type] = None
    equipe: Optional[str] = None
    theme: Optional[str] = None
    notes: Optional[str] = None
    exercices: List[SessionExerciceIn] = []


class ReordonnerItem(BaseModel):
    session_exercice_id: str
    ordre: int


# ── Sérialisation ──────────────────────────────────────────────────────────

def serialize_exercice(e: Exercice):
    return {
        "id": str(e.id),
        "nom": e.nom,
        "description": e.description,
        "objectif_pedagogique": e.objectif_pedagogique,
        "consignes_coaching": e.consignes_coaching,
        "categorie": e.categorie.libelle if e.categorie else None,
        "categorie_id": e.categorie_id,
        "niveau": e.niveau.libelle if e.niveau else None,
        "niveau_id": e.niveau_id,
        "effectif_min": e.effectif_min,
        "effectif_max": e.effectif_max,
        "duree_min": e.duree_min,
        "materiel_necessaire": e.materiel_necessaire,
        "source_url": e.source_url,
        "source_auteur": e.source_auteur,
        "source_pays": e.source_pays,
        "source_type": e.source_type,
        "schema_svg": e.schema_svg,
        "medias": [
            {"id": str(m.id), "type": m.type, "url": m.url_ou_chemin, "legende": m.legende}
            for m in e.medias
        ],
    }


def serialize_session(s: SessionEntrainement):
    return {
        "id": str(s.id),
        "nom": s.nom,
        "date_prevue": s.date_prevue.isoformat() if s.date_prevue else None,
        "equipe": s.equipe,
        "theme": s.theme,
        "notes": s.notes,
        "exercices": [
            {
                "id": str(se.id),
                "exercice_id": str(se.exercice_id),
                "nom": se.exercice.nom if se.exercice else None,
                "ordre": se.ordre,
                "duree_allouee_min": se.duree_allouee_min,
                "notes_specifiques": se.notes_specifiques,
            }
            for se in s.exercices_lies
        ],
    }


def _sync_tags(db: Session, exercice: Exercice, tag_labels: List[str]):
    """Remplace les tags d'un exercice - crée les tags manquants."""
    db.query(ExerciceTag).filter(ExerciceTag.exercice_id == exercice.id).delete()
    for label in tag_labels:
        label = label.strip().lower()
        if not label:
            continue
        tag = db.query(Tag).filter(Tag.libelle == label).first()
        if not tag:
            tag = Tag(libelle=label)
            db.add(tag)
            db.flush()
        db.add(ExerciceTag(exercice_id=exercice.id, tag_id=tag.id))


# ── Routes : catégories & niveaux (pour peupler les filtres côté frontend) ──

@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    return [{"id": c.id, "code": c.code, "libelle": c.libelle, "couleur": c.couleur_hex}
            for c in db.query(Categorie).all()]


@router.get("/niveaux")
def list_niveaux(db: Session = Depends(get_db)):
    return [{"id": n.id, "code": n.code, "libelle": n.libelle}
            for n in db.query(Niveau).order_by(Niveau.ordre).all()]


# ── Routes : exercices ───────────────────────────────────────────────────────

@router.get("/")
def list_exercices(
    categorie_id: Optional[int] = None,
    niveau_id: Optional[int] = None,
    recherche: Optional[str] = None,
    effectif: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Exercice)
    if categorie_id:
        query = query.filter(Exercice.categorie_id == categorie_id)
    if niveau_id:
        query = query.filter(Exercice.niveau_id == niveau_id)
    if recherche:
        query = query.filter(Exercice.nom.ilike(f"%{recherche}%"))
    if effectif:
        query = query.filter(
            or_(Exercice.effectif_min == None, Exercice.effectif_min <= effectif),
            or_(Exercice.effectif_max == None, Exercice.effectif_max >= effectif),
        )
    return [serialize_exercice(e) for e in query.all()]


@router.get("/{exercice_id}")
def get_exercice(exercice_id: str, db: Session = Depends(get_db)):
    e = db.query(Exercice).filter(Exercice.id == exercice_id).first()
    if not e:
        raise HTTPException(404, "Exercice introuvable")
    return serialize_exercice(e)


@router.post("/")
def create_exercice(payload: ExerciceIn, db: Session = Depends(get_db)):
    e = Exercice(**payload.dict(exclude={"tags"}))
    db.add(e)
    db.flush()
    if payload.tags:
        _sync_tags(db, e, payload.tags)
    db.commit()
    db.refresh(e)
    return serialize_exercice(e)


@router.patch("/{exercice_id}")
def update_exercice(exercice_id: str, payload: ExerciceIn, db: Session = Depends(get_db)):
    e = db.query(Exercice).filter(Exercice.id == exercice_id).first()
    if not e:
        raise HTTPException(404, "Exercice introuvable")
    data = payload.dict(exclude={"tags"}, exclude_unset=True)
    for key, value in data.items():
        setattr(e, key, value)
    if payload.tags is not None:
        _sync_tags(db, e, payload.tags)
    db.commit()
    db.refresh(e)
    return serialize_exercice(e)


@router.delete("/{exercice_id}")
def delete_exercice(exercice_id: str, db: Session = Depends(get_db)):
    e = db.query(Exercice).filter(Exercice.id == exercice_id).first()
    if not e:
        raise HTTPException(404, "Exercice introuvable")
    db.delete(e)
    db.commit()
    return {"ok": True}


# ── Routes : séances (constructeur drag & drop) ─────────────────────────────

@router.post("/sessions")
def create_session(payload: SessionIn, db: Session = Depends(get_db)):
    s = SessionEntrainement(**payload.dict(exclude={"exercices"}))
    db.add(s)
    db.flush()
    for ex in payload.exercices:
        db.add(SessionExercice(
            session_id=s.id,
            exercice_id=ex.exercice_id,
            ordre=ex.ordre,
            duree_allouee_min=ex.duree_allouee_min,
            notes_specifiques=ex.notes_specifiques,
        ))
    db.commit()
    db.refresh(s)
    return serialize_session(s)


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    s = db.query(SessionEntrainement).filter(SessionEntrainement.id == session_id).first()
    if not s:
        raise HTTPException(404, "Séance introuvable")
    return serialize_session(s)


@router.patch("/sessions/{session_id}/reordonner")
def reordonner(session_id: str, payload: List[ReordonnerItem], db: Session = Depends(get_db)):
    for item in payload:
        se = db.query(SessionExercice).filter(SessionExercice.id == item.session_exercice_id).first()
        if se:
            se.ordre = item.ordre
    db.commit()
    return {"ok": True, "nb_mis_a_jour": len(payload)}
