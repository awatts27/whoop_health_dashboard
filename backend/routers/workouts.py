from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_session

router = APIRouter()


@router.get("")
def get_workouts(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_session),
):
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = db.execute(
        text("""
            SELECT date, workout_id, sport_name, duration_ms,
                   strain_score, avg_hr, max_hr, calories
            FROM workouts
            WHERE date >= :since
            ORDER BY date DESC, strain_score DESC NULLS LAST
        """),
        {"since": since},
    ).mappings().all()
    return [dict(r) for r in rows]
