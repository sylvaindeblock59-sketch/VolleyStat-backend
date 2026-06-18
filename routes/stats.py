from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import Match, Set, PlayerStat

router = APIRouter()

def aggregate_stats(stats: list[PlayerStat]) -> dict:
    """Agrège les stats de plusieurs sets pour une joueuse."""
    fields = [
        "SG","S_plus","S_zero","S_minus",
        "R_pp","R_plus","R_zero","R_minus",
        "A_plus","A_zero","A_minus",
        "B_plus","B_def","B_minus",
        "P_plus","P_zero","P_minus",
        "D_plus","D_minus",
        "FF","points_gagnants","fautes_directes",
        "err_service","err_attaque"
    ]
    result = {f: 0 for f in fields}
    for s in stats:
        for f in fields:
            result[f] += getattr(s, f, 0) or 0
    return result

@router.get("/match/{match_id}")
def get_match_stats(match_id: str, db: Session = Depends(get_db)):
    """Stats globales du match (tous sets confondus)."""
    sets = db.query(Set).filter(Set.match_id == match_id).all()
    set_ids = [s.id for s in sets]

    all_stats = db.query(PlayerStat).filter(PlayerStat.set_id.in_(set_ids)).all()

    players: dict[str, list] = {}
    for stat in all_stats:
        players.setdefault(stat.player_name, []).append(stat)

    return {
        "sets": [{"number": s.set_number, "score_home": s.score_home, "score_away": s.score_away} for s in sets],
        "players": {name: aggregate_stats(pstats) for name, pstats in players.items()}
    }

@router.get("/match/{match_id}/set/{set_number}")
def get_set_stats(match_id: str, set_number: int, db: Session = Depends(get_db)):
    """Stats d'un set spécifique."""
    set_obj = db.query(Set).filter(
        Set.match_id == match_id, Set.set_number == set_number
    ).first()
    if not set_obj:
        return {"players": {}}

    stats = db.query(PlayerStat).filter(PlayerStat.set_id == set_obj.id).all()
    return {
        "set": {"number": set_obj.set_number, "score_home": set_obj.score_home, "score_away": set_obj.score_away},
        "players": {s.player_name: aggregate_stats([s]) for s in stats}
    }
