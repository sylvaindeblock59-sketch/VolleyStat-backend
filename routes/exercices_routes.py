# ============================================================
# ROUTES FASTAPI - MODULE EXERCICES VOLLEY-BALL
# A intégrer à l'API existante de SlyVolleyStat Pro
# Suppose une connexion Supabase déjà configurée (supabase-py)
# ============================================================

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import date

# --- Import du client Supabase déjà initialisé ailleurs dans ton projet ---
# from app.database import supabase

router = APIRouter(prefix="/exercices", tags=["exercices"])


# ============================================================
# SCHEMAS PYDANTIC
# ============================================================

class ExerciceBase(BaseModel):
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
    tags: List[str] = []  # libellés de tags, résolus/creés côté serveur


class ExerciceCreate(ExerciceBase):
    pass


class ExerciceUpdate(BaseModel):
    nom: Optional[str] = None
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
    tags: Optional[List[str]] = None


class ExerciceOut(ExerciceBase):
    id: UUID


class SessionExerciceIn(BaseModel):
    exercice_id: UUID
    ordre: int
    duree_allouee_min: Optional[int] = None
    notes_specifiques: Optional[str] = None


class SessionCreate(BaseModel):
    nom: str
    date_prevue: Optional[date] = None
    equipe: Optional[str] = None
    theme: Optional[str] = None
    notes: Optional[str] = None
    exercices: List[SessionExerciceIn] = []


# ============================================================
# HELPERS
# ============================================================

def _get_or_create_tag_ids(tag_labels: List[str]) -> List[int]:
    """Résout une liste de libellés de tags en ids, en créant ceux qui n'existent pas."""
    tag_ids = []
    for label in tag_labels:
        label = label.strip().lower()
        if not label:
            continue
        existing = supabase.table("tags").select("id").eq("libelle", label).execute()
        if existing.data:
            tag_ids.append(existing.data[0]["id"])
        else:
            created = supabase.table("tags").insert({"libelle": label}).execute()
            tag_ids.append(created.data[0]["id"])
    return tag_ids


def _sync_exercice_tags(exercice_id: UUID, tag_labels: List[str]):
    """Remplace les tags d'un exercice par la nouvelle liste fournie."""
    supabase.table("exercice_tags").delete().eq("exercice_id", str(exercice_id)).execute()
    tag_ids = _get_or_create_tag_ids(tag_labels)
    if tag_ids:
        rows = [{"exercice_id": str(exercice_id), "tag_id": tid} for tid in tag_ids]
        supabase.table("exercice_tags").insert(rows).execute()


# ============================================================
# ENDPOINTS EXERCICES
# ============================================================

@router.get("/", response_model=List[dict])
def lister_exercices(
    categorie: Optional[str] = Query(None, description="code catégorie, ex: 'bloc'"),
    niveau: Optional[str] = Query(None, description="code niveau, ex: 'confirme'"),
    tag: Optional[str] = Query(None, description="filtrer par tag"),
    recherche: Optional[str] = Query(None, description="recherche texte sur le nom"),
    effectif: Optional[int] = Query(None, description="nb de joueuses disponibles"),
):
    """Liste et filtre les exercices - s'appuie sur la vue v_exercices_recherche."""
    query = supabase.table("v_exercices_recherche").select("*")

    if categorie:
        query = query.eq("categorie", categorie)
    if niveau:
        query = query.eq("niveau", niveau)
    if recherche:
        query = query.ilike("nom", f"%{recherche}%")
    if effectif:
        query = query.lte("effectif_min", effectif).gte("effectif_max", effectif)

    result = query.execute()
    data = result.data

    if tag:
        data = [d for d in data if tag.lower() in (d.get("tags") or "").lower()]

    return data


@router.get("/{exercice_id}", response_model=dict)
def obtenir_exercice(exercice_id: UUID):
    """Détail complet d'un exercice, avec ses tags, médias et variantes."""
    exercice = supabase.table("exercices").select("*").eq("id", str(exercice_id)).execute()
    if not exercice.data:
        raise HTTPException(status_code=404, detail="Exercice introuvable")

    medias = supabase.table("medias").select("*").eq("exercice_id", str(exercice_id)).order("ordre").execute()
    variantes = supabase.table("variantes").select("*").eq("exercice_parent_id", str(exercice_id)).execute()
    tags_liaison = supabase.table("exercice_tags").select("tag_id").eq("exercice_id", str(exercice_id)).execute()

    result = exercice.data[0]
    result["medias"] = medias.data
    result["variantes"] = variantes.data
    result["tag_ids"] = [t["tag_id"] for t in tags_liaison.data]
    return result


@router.post("/", response_model=dict, status_code=201)
def creer_exercice(exercice: ExerciceCreate):
    """Crée un nouvel exercice, avec ses tags."""
    payload = exercice.dict(exclude={"tags"})
    created = supabase.table("exercices").insert(payload).execute()
    if not created.data:
        raise HTTPException(status_code=400, detail="Échec de la création")

    exercice_id = created.data[0]["id"]
    if exercice.tags:
        _sync_exercice_tags(exercice_id, exercice.tags)

    return created.data[0]


@router.patch("/{exercice_id}", response_model=dict)
def modifier_exercice(exercice_id: UUID, exercice: ExerciceUpdate):
    """Modifie un exercice existant (mise à jour partielle)."""
    payload = exercice.dict(exclude={"tags"}, exclude_unset=True)
    payload["modifie_le"] = "now()"

    updated = supabase.table("exercices").update(payload).eq("id", str(exercice_id)).execute()
    if not updated.data:
        raise HTTPException(status_code=404, detail="Exercice introuvable")

    if exercice.tags is not None:
        _sync_exercice_tags(exercice_id, exercice.tags)

    return updated.data[0]


@router.delete("/{exercice_id}", status_code=204)
def supprimer_exercice(exercice_id: UUID):
    """Supprime un exercice (cascade sur medias, variantes, tags liés)."""
    deleted = supabase.table("exercices").delete().eq("id", str(exercice_id)).execute()
    if not deleted.data:
        raise HTTPException(status_code=404, detail="Exercice introuvable")
    return None


# ============================================================
# ENDPOINTS SEANCES (constructeur drag & drop)
# ============================================================

@router.post("/sessions/", response_model=dict, status_code=201)
def creer_session(session: SessionCreate):
    """Crée une séance et y attache une liste ordonnée d'exercices."""
    session_payload = session.dict(exclude={"exercices"})
    created = supabase.table("sessions").insert(session_payload).execute()
    if not created.data:
        raise HTTPException(status_code=400, detail="Échec de la création de séance")

    session_id = created.data[0]["id"]

    if session.exercices:
        rows = [
            {
                "session_id": session_id,
                "exercice_id": str(ex.exercice_id),
                "ordre": ex.ordre,
                "duree_allouee_min": ex.duree_allouee_min,
                "notes_specifiques": ex.notes_specifiques,
            }
            for ex in session.exercices
        ]
        supabase.table("session_exercices").insert(rows).execute()

    return created.data[0]


@router.get("/sessions/{session_id}", response_model=dict)
def obtenir_session(session_id: UUID):
    """Détail d'une séance avec ses exercices dans l'ordre."""
    session = supabase.table("sessions").select("*").eq("id", str(session_id)).execute()
    if not session.data:
        raise HTTPException(status_code=404, detail="Séance introuvable")

    exercices = (
        supabase.table("session_exercices")
        .select("*, exercices(nom, categorie_id, duree_min)")
        .eq("session_id", str(session_id))
        .order("ordre")
        .execute()
    )

    result = session.data[0]
    result["exercices"] = exercices.data
    return result


@router.patch("/sessions/{session_id}/reordonner", response_model=dict)
def reordonner_exercices(session_id: UUID, ordres: List[dict]):
    """
    Met à jour l'ordre des exercices d'une séance après un drag & drop.
    Attend une liste [{"session_exercice_id": "...", "ordre": 0}, ...]
    """
    for item in ordres:
        supabase.table("session_exercices").update({"ordre": item["ordre"]}).eq(
            "id", item["session_exercice_id"]
        ).execute()
    return {"status": "ok", "nb_mis_a_jour": len(ordres)}


# ============================================================
# A FAIRE DANS TON APP PRINCIPALE (main.py) :
#
# from app.routes.exercices_routes import router as exercices_router
# app.include_router(exercices_router)
# ============================================================
