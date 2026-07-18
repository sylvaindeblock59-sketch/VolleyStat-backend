import uuid
from sqlalchemy import Column, String, Integer, Date, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class Season(Base):
    __tablename__ = "seasons"
    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom      = Column(String(20), nullable=False)          # ex. "2025-2026"
    club     = Column(String(60), default="VBC Bailleulois")
    division = Column(String(30), default="N3F")           # "N3F", "Nat2", "Régionale"…
    poule    = Column(String(30), default="")              # "Poule A", "Poule B", "?"…
    active   = Column(Boolean, default=False)
    roster   = Column(JSON, default=list)                  # [{number,prenom,nom,poste}]
    matches  = relationship("Match", back_populates="season", passive_deletes=True)


class Match(Base):
    __tablename__ = "matches"
    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date      = Column(Date, nullable=False)
    equipe_a  = Column(String(50), nullable=False)
    equipe_b  = Column(String(50), nullable=False)
    season_id = Column(UUID(as_uuid=True), ForeignKey("seasons.id", ondelete="SET NULL"), nullable=True)
    source_url = Column(String(500), nullable=True)   # lien FFVB competition pour référence
    fdm_pdf    = Column(String, nullable=True)         # PDF base64 (feuille de match)
    season    = relationship("Season", back_populates="matches")
    sets      = relationship("Set", back_populates="match", cascade="all, delete", order_by="Set.num")


class Set(Base):
    __tablename__ = "sets"
    id       = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False)
    num      = Column(Integer, nullable=False)
    score_a  = Column(Integer, default=0)
    score_b  = Column(Integer, default=0)
    match    = relationship("Match", back_populates="sets")
    stats    = relationship("PlayerStat", back_populates="set", cascade="all, delete")


class PlayerStat(Base):
    __tablename__ = "player_stats"
    id     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    set_id = Column(UUID(as_uuid=True), ForeignKey("sets.id"), nullable=False)
    nom    = Column(String(50), nullable=False)
    stats  = Column(JSON, default=dict)
    set    = relationship("Set", back_populates="stats")
    # ============================================================
# A AJOUTER A LA SUITE DE TON FICHIER models.py EXISTANT
# Ne remplace pas le fichier : copie-colle ce bloc en bas du fichier actuel.
# Les imports (uuid, Column, String, etc.) sont déjà en haut de ton fichier,
# pas besoin de les répéter.
# ============================================================

class Categorie(Base):
    __tablename__ = "categories"
    id          = Column(Integer, primary_key=True)
    code        = Column(String(50), nullable=False)
    libelle     = Column(String(80), nullable=False)
    couleur_hex = Column(String(10), nullable=True)


class Niveau(Base):
    __tablename__ = "niveaux"
    id      = Column(Integer, primary_key=True)
    code    = Column(String(50), nullable=False)
    libelle = Column(String(80), nullable=False)
    ordre   = Column(Integer, nullable=False)


class Tag(Base):
    __tablename__ = "tags"
    id      = Column(Integer, primary_key=True)
    libelle = Column(String(80), nullable=False)


class Exercice(Base):
    __tablename__ = "exercices"
    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom                  = Column(String(200), nullable=False)
    description          = Column(String, nullable=True)
    objectif_pedagogique = Column(String, nullable=True)
    consignes_coaching   = Column(String, nullable=True)
    categorie_id         = Column(Integer, ForeignKey("categories.id"), nullable=True)
    niveau_id            = Column(Integer, ForeignKey("niveaux.id"), nullable=True)
    effectif_min         = Column(Integer, nullable=True)
    effectif_max         = Column(Integer, nullable=True)
    duree_min            = Column(Integer, nullable=True)
    materiel_necessaire  = Column(String, nullable=True)
    source_url           = Column(String(500), nullable=True)
    source_auteur        = Column(String(150), nullable=True)
    source_pays          = Column(String(80), nullable=True)
    source_type          = Column(String(30), nullable=True)
    schema_svg            = Column(String, nullable=True)
    est_favori             = Column(Boolean, default=False)
    cree_par               = Column(String(100), nullable=True)

    categorie = relationship("Categorie")
    niveau    = relationship("Niveau")
    medias     = relationship("Media", back_populates="exercice", cascade="all, delete")
    variantes  = relationship("Variante", back_populates="exercice_parent", cascade="all, delete")


class ExerciceTag(Base):
    __tablename__ = "exercice_tags"
    exercice_id = Column(UUID(as_uuid=True), ForeignKey("exercices.id"), primary_key=True)
    tag_id      = Column(Integer, ForeignKey("tags.id"), primary_key=True)


class Media(Base):
    __tablename__ = "medias"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exercice_id   = Column(UUID(as_uuid=True), ForeignKey("exercices.id"), nullable=False)
    type          = Column(String(30), nullable=False)
    url_ou_chemin = Column(String(500), nullable=False)
    legende       = Column(String(200), nullable=True)
    ordre         = Column(Integer, default=0)

    exercice = relationship("Exercice", back_populates="medias")


class Variante(Base):
    __tablename__ = "variantes"
    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exercice_parent_id  = Column(UUID(as_uuid=True), ForeignKey("exercices.id"), nullable=False)
    nom                 = Column(String(200), nullable=False)
    description          = Column(String, nullable=True)
    complexite_relative  = Column(Integer, nullable=True)

    exercice_parent = relationship("Exercice", back_populates="variantes")


class SessionEntrainement(Base):
    """Nommé ainsi (et pas 'Session') pour ne pas entrer en conflit avec la
    Session de SQLAlchemy elle-même, utilisée partout ailleurs dans le code."""
    __tablename__ = "sessions"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom              = Column(String(200), nullable=False)
    date_prevue      = Column(Date, nullable=True)
    equipe           = Column(String(50), nullable=True)
    theme            = Column(String(150), nullable=True)
    duree_totale_min = Column(Integer, nullable=True)
    notes            = Column(String, nullable=True)
    cree_par          = Column(String(100), nullable=True)

    exercices_lies = relationship("SessionExercice", back_populates="session", cascade="all, delete", order_by="SessionExercice.ordre")


class SessionExercice(Base):
    __tablename__ = "session_exercices"
    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id        = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    exercice_id       = Column(UUID(as_uuid=True), ForeignKey("exercices.id"), nullable=False)
    ordre             = Column(Integer, nullable=False)
    duree_allouee_min = Column(Integer, nullable=True)
    notes_specifiques = Column(String, nullable=True)

    session  = relationship("SessionEntrainement", back_populates="exercices_lies")
    exercice = relationship("Exercice")


class Joueuse(Base):
    __tablename__ = "joueuses"
    id     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nom    = Column(String(100), nullable=False)
    poste  = Column(String(50), nullable=True)
    equipe = Column(String(50), nullable=True)
    actif  = Column(Boolean, default=True)


class Presence(Base):
    __tablename__ = "presences"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    joueuse_id = Column(UUID(as_uuid=True), ForeignKey("joueuses.id"), nullable=False)
    statut     = Column(String(20), default="present")
    remarque   = Column(String, nullable=True)
