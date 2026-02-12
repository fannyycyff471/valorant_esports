from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from db import Base


class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    source = Column(String(50), nullable=False)
    source_match_id = Column(String(100), nullable=False, unique=True)
    start_time = Column(String(40), nullable=True)
    league = Column(String(200), nullable=True)
    team_a = Column(String(200), nullable=True)
    team_b = Column(String(200), nullable=True)
    score_a = Column(Integer, nullable=True)
    score_b = Column(Integer, nullable=True)
    winner = Column(String(20), nullable=True)
    status = Column(String(50), nullable=True)
    bo = Column(Integer, nullable=True)
    raw_json = Column(Text, nullable=True)

    games = relationship("MatchGame", back_populates="match", cascade="all, delete-orphan")

class MatchGame(Base):
    __tablename__ = "match_games"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    game_no = Column(Integer, nullable=True)
    map_name = Column(String(100), nullable=True)
    score_a = Column(Integer, nullable=True)
    score_b = Column(Integer, nullable=True)
    raw_json = Column(Text, nullable=True)

    match = relationship("Match", back_populates="games")
