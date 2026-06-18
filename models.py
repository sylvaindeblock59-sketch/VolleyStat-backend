import uuid
from sqlalchemy import Column, String, Integer, Date, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base


class Match(Base):
    __tablename__ = "matches"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False)
    equipe_a = Column(String(50), nullable=False)
    equipe_b = Column(String(50), nullable=False)
    sets = relationship("Set", back_populates="match", cascade="all, delete", order_by="Set.num")


class Set(Base):
    __tablename__ = "sets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    match_id = Column(UUID(as_uuid=True), ForeignKey("matches.id"), nullable=False)
    num = Column(Integer, nullable=False)
    score_a = Column(Integer, default=0)
    score_b = Column(Integer, default=0)
    match = relationship("Match", back_populates="sets")
    stats = relationship("PlayerStat", back_populates="set", cascade="all, delete")


class PlayerStat(Base):
    __tablename__ = "player_stats"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    set_id = Column(UUID(as_uuid=True), ForeignKey("sets.id"), nullable=False)
    nom = Column(String(50), nullable=False)
    stats = Column(JSON, default=dict)  # contient titulaire + SG, S+, S0... tels quels
    set = relationship("Set", back_populates="stats")