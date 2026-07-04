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